"""Tests for the remote door lock control."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


def _last_telematics_payload(router: respx.Router) -> dict:
    """Return the JSON body of the most recent telematics PUT request."""
    calls = [c for c in router.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path]
    assert calls, "No telematics request was sent"
    return json.loads(calls[-1].request.content)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "service_id", "parameter"),
    [
        ("lock", "RDL_2", {"key": "door", "value": "all"}),
        ("unlock", "RDU_2", {"key": "door", "value": "all"}),
        ("lock_trunk", "RDL_2", {"key": "target", "value": "trunk"}),
        ("unlock_trunk", "RDU_2", {"key": "target", "value": "trunk"}),
    ],
)
async def test_door_lock_commands(smart_fixture: respx.Router, method: str, service_id: str, parameter: dict):
    """Test that each lock command sends the matching telematics service."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    lock_ctrl = account.vehicles["TestVIN0000000001"].door_lock_control
    assert lock_ctrl is not None

    result = await getattr(lock_ctrl, method)()

    assert result
    payload = _last_telematics_payload(smart_fixture)
    assert payload["serviceId"] == service_id
    assert payload["command"] == "start"
    assert payload["serviceParameters"] == [parameter]


TELEMATICS_URL = "https://api.ecloudeu.com/remote-control/vehicle/telematics/TestVIN0000000001"
SUCCESS = {"code": 1000, "success": True, "message": "operation succeed", "data": {}}


def _last_telematics_request(router: respx.Router):
    calls = [c for c in router.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path]
    assert calls, "No telematics request was sent"
    return calls[-1].request


@pytest.mark.asyncio
async def test_door_lock_sends_vin_headers(smart_fixture: respx.Router):
    """Test that lock commands are bound to the VIN instead of the active vehicle."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")

    await account.vehicles["TestVIN0000000001"].door_lock_control.lock()

    request = _last_telematics_request(smart_fixture)
    assert request.headers["X-Vehicle-IDENTIFIER"] == "TestVIN0000000001"
    assert request.headers["X-VEHICLE-MODEL"] == "TestVIN0000000001"


@pytest.mark.asyncio
async def test_door_lock_refreshes_token_before_retry(smart_fixture: respx.Router):
    """Test that an expired session token is refreshed before retrying."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    smart_fixture.put(TELEMATICS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"code": "1402", "message": "token expired"}),
            httpx.Response(200, json=SUCCESS),
        ]
    )

    with patch.object(account.config.authentication, "refresh", new=AsyncMock()) as refresh:
        result = await account.vehicles["TestVIN0000000001"].door_lock_control.unlock()

    assert result
    refresh.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["8006", "4038"])
async def test_door_lock_rebinds_vehicle_before_retry(smart_fixture: respx.Router, code: str):
    """Test that a lost vehicle binding is restored before retrying."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    smart_fixture.put(TELEMATICS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"code": code, "message": "binding lost"}),
            httpx.Response(200, json=SUCCESS),
        ]
    )

    with patch.object(account, "select_active_vehicle", new=AsyncMock()) as select:
        result = await account.vehicles["TestVIN0000000001"].door_lock_control.lock()

    assert result
    # Once before the first attempt, once more before the retry
    assert select.await_count == 2
    select.assert_awaited_with("TestVIN0000000001")
