"""Tests for the remote window control."""

import json

import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


def _last_telematics_request(router: respx.Router):
    calls = [c for c in router.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path]
    assert calls, "No telematics request was sent"
    return calls[-1].request


async def _window_control():
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    return account.vehicles["TestVIN0000000001"].window_control


@pytest.mark.asyncio
@pytest.mark.parametrize(("active", "command"), [(True, "start"), (False, "stop")])
async def test_set_ventilation(smart_fixture: respx.Router, active: bool, command: str):
    """Test that ventilation sends RWS_2 target=ventilate, start to open and stop to close."""
    window_ctrl = await _window_control()

    assert await window_ctrl.set_ventilation(active)

    request = _last_telematics_request(smart_fixture)
    payload = json.loads(request.content)
    assert payload["serviceId"] == "RWS_2"
    assert payload["command"] == command
    assert payload["operationScheduling"]["duration"] == 0
    assert payload["serviceParameters"] == [{"key": "target", "value": "ventilate"}]
    assert request.headers["X-Vehicle-IDENTIFIER"] == "TestVIN0000000001"


@pytest.mark.asyncio
async def test_set_ventilation_invalid_state(smart_fixture: respx.Router):
    """Test that a non-boolean state is rejected before sending."""
    window_ctrl = await _window_control()

    with pytest.raises(TypeError):
        await window_ctrl.set_ventilation("open")

    assert not [c for c in smart_fixture.calls if c.request.method == "PUT"]
