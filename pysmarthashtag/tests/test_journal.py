"""Tests for the trip journal endpoint and parser."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from pysmarthashtag.const import API_BASE_URL, API_BASE_URL_V2
from pysmarthashtag.tests import RESPONSE_DIR, load_response
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles
from pysmarthashtag.vehicle.journal import TripJournal


def test_from_response_handles_none():
    """A None or non-dict input must not blow up."""
    assert TripJournal.from_response(None) is None
    assert TripJournal.from_response("not a dict") is None  # type: ignore[arg-type]


def test_from_response_handles_empty_body():
    """Empty body / missing data block returns None."""
    assert TripJournal.from_response({}) is None
    assert TripJournal.from_response({"code": 8153, "message": "Connection interruption"}) is None


def test_from_response_handles_no_logs_with_total():
    """Cloud reported a total but no logs — we still surface total_trips."""
    parsed = TripJournal.from_response(
        {"data": {"pagination": {"totleSize": 0}, "list": []}}
    )
    assert parsed is not None
    assert parsed.total_trips == 0
    assert parsed.trip_id == ""
    assert parsed.start_address == ""


def test_from_response_parses_full_record():
    """All fields populate from the canonical response shape."""
    parsed = TripJournal.from_response(load_response(RESPONSE_DIR / "journal_response.json"))
    assert parsed is not None
    # Cloud uses an int tripId; we coerce to string for stable consumer-side IDs.
    assert parsed.trip_id == "1734246000"
    assert parsed.distance.value == 15.4
    assert parsed.distance.unit == "km"
    # Duration is computed from start/end timestamps (cloud doesn't provide it).
    assert parsed.duration == 1230  # (1734247230000 - 1734246000000) / 1000
    # ``electricConsumption`` is the average (kWh/100km); we compute the
    # absolute total as avg * distance / 100.
    assert parsed.avg_energy_consumption.value == 20.8
    assert parsed.avg_energy_consumption.unit == "kWh/100km"
    assert parsed.energy_consumption.value == round(20.8 * 15.4 / 100, 3)
    assert parsed.energy_consumption.unit == "kWh"
    assert parsed.avg_speed.value == 45.0
    # The cloud doesn't provide max_speed (would require trackpoint analysis).
    assert parsed.max_speed is None
    # Tz-aware UTC datetime (HA's TIMESTAMP device class needs tzinfo).
    assert parsed.start_time == datetime.fromtimestamp(1734246000000 / 1000, tz=timezone.utc)
    assert parsed.end_time == datetime.fromtimestamp(1734247230000 / 1000, tz=timezone.utc)
    assert parsed.start_time.tzinfo is not None
    assert parsed.regenerated_energy.value == 0.8
    assert parsed.start_address == "123 Test Street, Test City"
    assert parsed.end_address == "15 Other Road, Test City"
    # Positions come from trackpoints[0] and trackpoints[-1] (raw int milliarcseconds).
    assert parsed.start_position == (217414695, 80626712)
    assert parsed.end_position == (217384510, 80573036)
    assert parsed.total_trips == 42


def test_from_response_handles_missing_optional_fields():
    """Missing optional fields default to None, not crash."""
    parsed = TripJournal.from_response(
        {
            "data": {
                "pagination": {"totleSize": 1},
                "list": [
                    {
                        "tripId": "minimal-trip",
                        # All metric fields absent.
                    }
                ],
            }
        }
    )
    assert parsed is not None
    assert parsed.trip_id == "minimal-trip"
    assert parsed.distance is None
    assert parsed.duration is None
    assert parsed.energy_consumption is None
    assert parsed.start_time is None
    assert parsed.start_address == ""


def test_from_response_handles_bogus_timestamp():
    """A non-numeric startTime must not crash the parser."""
    parsed = TripJournal.from_response(
        {
            "data": {
                "pagination": {"totleSize": 1},
                "list": [
                    {
                        "tripId": "broken-time",
                        "startTime": "not-a-number",
                        "endTime": None,
                    }
                ],
            }
        }
    )
    assert parsed is not None
    assert parsed.start_time is None
    assert parsed.end_time is None


@pytest.mark.asyncio
async def test_get_vehicles_populates_last_trip(smart_fixture: respx.Router):
    """End-to-end: get_vehicles() → vehicle.last_trip is set from journalLogV4."""
    account = await prepare_account_with_vehicles()
    vehicle = account.vehicles["TestVIN0000000001"]
    assert vehicle.last_trip is not None
    assert vehicle.last_trip.trip_id == "1734246000"
    assert vehicle.last_trip.start_address == "123 Test Street, Test City"
    assert vehicle.last_trip.end_address == "15 Other Road, Test City"
    assert vehicle.last_trip.total_trips == 42


@pytest.mark.asyncio
async def test_get_vehicles_survives_journal_error(smart_fixture: respx.Router):
    """If journalLogV4 returns 8153 / etc., the rest of the refresh still works.

    Override both VINs' journal routes via ``side_effect`` (the only way
    respx reliably replaces a route registered by a prior fixture call).
    """

    def _error_response(_request):
        # The SmartClient response hook compares ``code`` as a string.
        return httpx.Response(
            200,
            json={"code": "8153", "message": "Connection interruption"},
        )

    import re
    for base in (API_BASE_URL, API_BASE_URL_V2):
        for vin in ("TestVIN0000000001", "TestVIN0000000002"):
            # Override the regex route registered by SmartMockRouter (journalLogV4
            # carries query params now, so the existing route is registered with
            # a regex prefix); match that regex exactly so respx replaces it.
            smart_fixture.get(re.compile(re.escape(
                base + f"/geelyTCAccess/tcservices/vehicle/status/journalLogV4/{vin}"
            ) + r".*")).mock(side_effect=_error_response)

    account = await prepare_account_with_vehicles()
    # Vehicles still loaded; just no last_trip populated.
    assert len(account.vehicles) == 2
    for vehicle in account.vehicles.values():
        assert vehicle.last_trip is None
