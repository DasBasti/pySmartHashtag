"""Tests for the per-trip GPS-trackpoints endpoint and parser."""

import logging
import re

import httpx
import pytest
import respx

from pysmarthashtag.account import (
    TRIP_TRACKPOINTS_PAGE_SIZE,
    TRIP_TRACKPOINTS_PATH_PREFIX,
)
from pysmarthashtag.const import API_BASE_URL, API_BASE_URL_V2
from pysmarthashtag.tests import RESPONSE_DIR, load_response
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles
from pysmarthashtag.vehicle.trackpoints import (
    Trackpoint,
    TripTrackpoints,
    parse_trackpoints_response,
)

# Cloud reports lat/lon in milliarcseconds; consumers see decimal degrees.
_MAS_PER_DEGREE = 3_600_000.0


def test_parse_handles_none_and_non_dict():
    """A None or non-dict input must yield an empty result, not crash."""
    assert parse_trackpoints_response(None) == TripTrackpoints(points=[], total_size=0)
    assert parse_trackpoints_response("not a dict") == TripTrackpoints(points=[], total_size=0)  # type: ignore[arg-type]


def test_parse_handles_empty_data_block():
    """``data: null`` (alternate cloud-side empty shape) → empty result."""
    assert parse_trackpoints_response({"code": "1000", "data": None}) == TripTrackpoints(
        points=[], total_size=0
    )


def test_parse_handles_empty_list_with_zero_total():
    """``code 1000`` with ``data.list = []`` and ``totleSize: 0`` → empty result."""
    parsed = parse_trackpoints_response(
        {
            "code": "1000",
            "data": {"pagination": {"totleSize": 0}, "list": []},
        }
    )
    assert parsed.points == []
    assert parsed.total_size == 0


def test_parse_reverses_to_chronological_order():
    """Reverse cloud's desc list to chronological so ``points[0]`` is trip start.

    Cloud sends ``direction=desc`` (newest-first); we reverse at the
    parser boundary so every consumer sees the same orientation.
    """
    body = load_response(RESPONSE_DIR / "trackpoints_response.json")
    parsed = parse_trackpoints_response(body)
    assert parsed.total_size == 4
    # Fixture's wire-order list[0] (newest) lat=217471769; last entry's
    # lat=217468000. Chronological reversal → points[0].lat comes from
    # the wire-order LAST entry.
    assert parsed.points[0].lat == pytest.approx(217468000 / _MAS_PER_DEGREE)
    assert parsed.points[0].lon == pytest.approx(80505500 / _MAS_PER_DEGREE)
    assert parsed.points[-1].lat == pytest.approx(217471769 / _MAS_PER_DEGREE)
    assert parsed.points[-1].lon == pytest.approx(80503026 / _MAS_PER_DEGREE)


def test_parse_milliarcsecond_to_degree_scaling():
    """Cloud reports integer mas; parser divides by 3,600,000 for degrees."""
    parsed = parse_trackpoints_response(
        {
            "code": "1000",
            "data": {
                "pagination": {"totleSize": 1},
                "list": [
                    {"basicVehicleStatus": {"position": {"latitude": 3_600_000, "longitude": 7_200_000}}}
                ],
            },
        }
    )
    # 3 600 000 mas == 1.0 degree exactly.
    assert parsed.points == [Trackpoint(lat=1.0, lon=2.0)]


def test_parse_handles_degraded_per_point_payload():
    """Degraded shapes yield ``Trackpoint(lat=None, lon=None)``, not crashes.

    A missing ``basicVehicleStatus`` / ``position`` block, or non-dict
    entries, must NOT drop the rest of the trip — sequence integrity
    matters more than per-point completeness.
    """
    parsed = parse_trackpoints_response(
        {
            "code": "1000",
            "data": {
                "pagination": {"totleSize": 4},
                "list": [
                    "not-a-dict",
                    {},
                    {"basicVehicleStatus": "not-a-dict"},
                    {"basicVehicleStatus": {"position": {"latitude": None, "longitude": None}}},
                ],
            },
        }
    )
    # All four entries become null trackpoints; none is dropped.
    assert len(parsed.points) == 4
    for tp in parsed.points:
        assert tp == Trackpoint(lat=None, lon=None)


def test_parse_non_list_payload_coerces_to_empty():
    """``data.list`` drifting to a non-list type yields empty points."""
    parsed = parse_trackpoints_response(
        {
            "code": "1000",
            "data": {
                "pagination": {"totleSize": 0},
                "list": {"unexpected": "shape"},
            },
        }
    )
    assert parsed.points == []
    assert parsed.total_size == 0


@pytest.mark.asyncio
async def test_get_trip_trackpoints_returns_chronological_points(smart_fixture: respx.Router):
    """End-to-end: ``get_trip_trackpoints()`` returns chronological points."""
    account = await prepare_account_with_vehicles()
    trackpoints = await account.get_trip_trackpoints(
        "TestVIN0000000001", start_time_ms=1_000_000, end_time_ms=2_000_000
    )
    assert trackpoints.total_size == 4
    assert len(trackpoints.points) == 4
    # Same chronological-reversal assertion as the parser test.
    assert trackpoints.points[0].lat == pytest.approx(217468000 / _MAS_PER_DEGREE)
    assert trackpoints.points[-1].lat == pytest.approx(217471769 / _MAS_PER_DEGREE)


@pytest.mark.asyncio
async def test_get_trip_trackpoints_does_not_call_grant(smart_fixture: respx.Router):
    """Trackpoints endpoint must NOT trigger ``authorization/insert``.

    The cloud does not gate this call behind the per-session grant
    handshake that ``journalLogV4`` requires; calling it defensively
    per-fetch burns a cloud round-trip and risks transient 7065 errors
    on back-to-back grants. Verify by counting calls on the auth-grant
    route — registered for completeness in case the grant ever IS
    introduced, currently dormant.
    """
    account = await prepare_account_with_vehicles()
    # Register an auth-grant route so we can detect any call to it; the
    # base SmartMockRouter doesn't ship one on this branch (no
    # journalLogV4 route either — this branch predates PR #194).
    grant_calls = []

    def _track_grant(_request):
        grant_calls.append(_request)
        return httpx.Response(200, json={"code": "1000", "success": True})

    for base in (API_BASE_URL, API_BASE_URL_V2):
        smart_fixture.post(base + "/remote-control/user/authorization/insert").mock(
            side_effect=_track_grant
        )

    await account.get_trip_trackpoints(
        "TestVIN0000000001", start_time_ms=1_000_000, end_time_ms=2_000_000
    )
    assert grant_calls == [], "trackpoints endpoint must not call auth-grant"


@pytest.mark.asyncio
async def test_get_trip_trackpoints_normalises_8153(smart_fixture: respx.Router):
    """Cloud ``code=8153`` ("data unavailable") → empty result, no raise."""

    def _8153_response(_request):
        return httpx.Response(
            200,
            json={"code": "8153", "message": "Connection interruption"},
        )

    for base in (API_BASE_URL, API_BASE_URL_V2):
        for vin in ("TestVIN0000000001", "TestVIN0000000002"):
            smart_fixture.get(re.compile(re.escape(
                base + TRIP_TRACKPOINTS_PATH_PREFIX + vin
            ) + r".*")).mock(side_effect=_8153_response)

    account = await prepare_account_with_vehicles()
    trackpoints = await account.get_trip_trackpoints(
        "TestVIN0000000001", start_time_ms=1_000_000, end_time_ms=2_000_000
    )
    assert trackpoints == TripTrackpoints(points=[], total_size=0)


@pytest.mark.asyncio
async def test_get_trip_trackpoints_propagates_other_http_errors(smart_fixture: respx.Router):
    """Non-8153 cloud errors propagate; only 8153 is normalised."""

    def _500_response(_request):
        return httpx.Response(
            200,
            json={"code": "5000", "message": "Internal server error"},
        )

    for base in (API_BASE_URL, API_BASE_URL_V2):
        for vin in ("TestVIN0000000001", "TestVIN0000000002"):
            smart_fixture.get(re.compile(re.escape(
                base + TRIP_TRACKPOINTS_PATH_PREFIX + vin
            ) + r".*")).mock(side_effect=_500_response)

    account = await prepare_account_with_vehicles()
    with pytest.raises(httpx.HTTPStatusError):
        await account.get_trip_trackpoints(
            "TestVIN0000000001", start_time_ms=1_000_000, end_time_ms=2_000_000
        )


@pytest.mark.asyncio
async def test_get_trip_trackpoints_warns_on_oversize_total(
    smart_fixture: respx.Router, caplog: pytest.LogCaptureFixture
):
    """If cloud reports ``totleSize > pageSize``, log WARNING but still return head."""
    big_total_body = {
        "code": "1000",
        "data": {
            "pagination": {"totleSize": TRIP_TRACKPOINTS_PAGE_SIZE + 1, "pageSize": TRIP_TRACKPOINTS_PAGE_SIZE},
            "list": [
                {"basicVehicleStatus": {"position": {"latitude": 100, "longitude": 200}}}
            ],
        },
    }

    def _oversize_response(_request):
        return httpx.Response(200, json=big_total_body)

    for base in (API_BASE_URL, API_BASE_URL_V2):
        for vin in ("TestVIN0000000001", "TestVIN0000000002"):
            smart_fixture.get(re.compile(re.escape(
                base + TRIP_TRACKPOINTS_PATH_PREFIX + vin
            ) + r".*")).mock(side_effect=_oversize_response)

    account = await prepare_account_with_vehicles()
    with caplog.at_level(logging.WARNING, logger="pysmarthashtag.account"):
        trackpoints = await account.get_trip_trackpoints(
            "TestVIN0000000001", start_time_ms=1_000_000, end_time_ms=2_000_000
        )
    assert trackpoints.total_size == TRIP_TRACKPOINTS_PAGE_SIZE + 1
    assert len(trackpoints.points) == 1
    assert any(
        "page-size cap exceeded" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    )
