"""Tests for setting the charging limit."""

import json

import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


def _last_telematics_payload(router: respx.Router) -> dict:
    calls = [c for c in router.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path]
    assert calls, "No telematics request was sent"
    return json.loads(calls[-1].request.content)


async def _charging_control():
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    return account.vehicles["TestVIN0000000001"].charging_control


@pytest.mark.asyncio
@pytest.mark.parametrize(("percent", "soc"), [(50, "500"), (80, "800"), (100, "1000")])
async def test_set_charging_limit_payload(smart_fixture: respx.Router, percent: int, soc: str):
    """Test that the charging limit is sent as rcs operation 4 in percent x 10."""
    charging_ctrl = await _charging_control()

    assert await charging_ctrl.set_charging_limit(percent)

    payload = _last_telematics_payload(smart_fixture)
    assert payload["serviceId"] == "rcs"
    assert payload["command"] == "start"
    assert payload["operationScheduling"]["duration"] == 6
    assert "timeStamp" in payload
    assert payload["serviceParameters"] == [
        {"key": "soc", "value": soc},
        {"key": "operation", "value": "4"},
        {"key": "rcs.setting", "value": "1"},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("percent", "exc"),
    [(45, ValueError), (105, ValueError), (82, ValueError), (80.0, TypeError), ("80", TypeError), (True, TypeError)],
)
async def test_set_charging_limit_invalid(smart_fixture: respx.Router, percent, exc):
    """Test that invalid charging limits are rejected before sending."""
    charging_ctrl = await _charging_control()

    with pytest.raises(exc):
        await charging_ctrl.set_charging_limit(percent)

    assert not [c for c in smart_fixture.calls if c.request.method == "PUT"]
