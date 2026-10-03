"""Tests for sending a destination to the vehicle navigation."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles

VIN = "TestVIN0000000001"
SEND_TO_CAR_URL = f"https://api.ecloudeu.com/geelyTCAccess/tcservices/ihu/send/to/car?vin={VIN}"
SUCCESS = {"code": "1000", "success": True, "message": "operation succeed", "data": None}


async def _account(router: respx.Router, *responses: httpx.Response):
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information(VIN)
    router.post(SEND_TO_CAR_URL).mock(side_effect=list(responses) or [httpx.Response(200, json=SUCCESS)])
    return account


def _send_to_car_requests(router: respx.Router) -> list[httpx.Request]:
    return [c.request for c in router.calls if c.request.url.path.endswith("/ihu/send/to/car")]


@pytest.mark.asyncio
async def test_send_destination_to_car(smart_fixture: respx.Router):
    """Test that the destination is posted with VIN query, VIN headers and a compact body."""
    account = await _account(smart_fixture)

    result = await account.send_destination_to_car(VIN, 48.137154, 11.576124, "Marienplatz", "Marienplatz 1, München")

    assert result
    requests = _send_to_car_requests(smart_fixture)
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url.params["vin"] == VIN
    assert request.headers["X-Vehicle-IDENTIFIER"] == VIN
    assert json.loads(request.content) == {
        "lat": 48.137154,
        "lon": 11.576124,
        "name": "Marienplatz",
        "address": "Marienplatz 1, München",
    }
    # Spaces inside name and address must survive (SMore# strips them)
    assert b"Marienplatz 1," in request.content


@pytest.mark.asyncio
async def test_send_destination_refreshes_token_before_retry(smart_fixture: respx.Router):
    """Test that an expired session token is refreshed before retrying."""
    account = await _account(
        smart_fixture,
        httpx.Response(200, json={"code": "1402", "message": "token expired"}),
        httpx.Response(200, json=SUCCESS),
    )

    with patch.object(account.config.authentication, "refresh", new=AsyncMock()) as refresh:
        result = await account.send_destination_to_car(VIN, 48.1, 11.5, "Home")

    assert result
    refresh.assert_awaited_once()
    assert len(_send_to_car_requests(smart_fixture)) == 2


@pytest.mark.asyncio
async def test_send_destination_rejected(smart_fixture: respx.Router):
    """Test that a response without success returns False."""
    account = await _account(smart_fixture, httpx.Response(200, json={"code": "1000", "success": False}))

    assert not await account.send_destination_to_car(VIN, 48.1, 11.5, "Home")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latitude", "longitude", "name", "address", "exc"),
    [
        (91, 11.5, "Home", "", ValueError),
        (48.1, -181, "Home", "", ValueError),
        (48.1, 11.5, "  ", "", ValueError),
        ("48.1", 11.5, "Home", "", TypeError),
        (True, 11.5, "Home", "", TypeError),
        (48.1, 11.5, "Home", None, TypeError),
    ],
)
async def test_send_destination_invalid_input(smart_fixture: respx.Router, latitude, longitude, name, address, exc):
    """Test that invalid input is rejected before sending."""
    account = await _account(smart_fixture)

    with pytest.raises(exc):
        await account.send_destination_to_car(VIN, latitude, longitude, name, address)

    assert not _send_to_car_requests(smart_fixture)
