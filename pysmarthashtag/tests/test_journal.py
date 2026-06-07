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


def test_from_response_handles_non_list_payload_fields():
    """Coerce non-list payload fields to empty list, never raise on indexing.

    ``data.list`` and per-trip ``trackpoints`` could in principle drift to
    non-list types in a future cloud schema; this guards against that.
    """
    # ``data.list`` is a dict (cloud schema drift) — parser returns None
    # because there are no usable trip records, NOT a TypeError.
    assert TripJournal.from_response({"data": {"list": {"unexpected": "shape"}}}) is None
    # ``trackpoints`` is a string instead of a list — parser still returns
    # the trip but with start/end positions = None.
    parsed = TripJournal.from_response(
        {
            "data": {
                "pagination": {"totleSize": 1},
                "list": [
                    {
                        "tripId": "drift-trackpoints",
                        "startTime": 1734246000000,
                        "endTime": 1734247230000,
                        "trackpoints": "not-a-list",
                    }
                ],
            }
        }
    )
    assert parsed is not None
    assert parsed.trip_id == "drift-trackpoints"
    assert parsed.start_position is None
    assert parsed.end_position is None


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
async def test_grant_authorization_caches_per_vin_token(smart_fixture: respx.Router):
    """Repeat-grant calls under the same access_token short-circuit via cache.

    The grant POST rotates the access_token server-side (observed empirically
    against the live cloud). Without caching, every poll would burn 2x calls
    (failed call + token-refresh + retry). The cache stores the token under
    which the grant was accepted; subsequent calls under the *same* token
    are no-ops; ``force=True`` bypasses; token rotation auto-invalidates.
    """
    account = await prepare_account_with_vehicles()
    vin = "TestVIN0000000001"

    # The mock router registered POST /authorization/insert during fixture
    # setup; find it and count calls.
    import re
    insert_route = next(
        r for r in smart_fixture.routes
        if re.search(r"authorization/insert", str(r.pattern))
        and "POST" in str(r.pattern)
    )
    insert_route.calls.reset()

    # First call: should POST and cache.
    ok = await account.grant_journal_authorization(vin)
    assert ok is True
    assert insert_route.calls.call_count == 1
    cached_token = account._journal_grant_cache.get(vin)
    assert cached_token is not None

    # Second call under the same token: should NOT POST.
    ok2 = await account.grant_journal_authorization(vin)
    assert ok2 is True
    assert insert_route.calls.call_count == 1, "second call should hit the cache"

    # force=True bypasses the cache.
    ok3 = await account.grant_journal_authorization(vin, force=True)
    assert ok3 is True
    assert insert_route.calls.call_count == 2, "force=True should re-POST"

    # Manually rotate the token; cache should auto-invalidate on the
    # next call (token mismatch in the lookup).
    account.config.authentication.api_access_token = "rotated-token-xyz"
    ok4 = await account.grant_journal_authorization(vin)
    assert ok4 is True
    assert insert_route.calls.call_count == 3, "token rotation should invalidate cache"


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
