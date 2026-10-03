"""Tests for the remote horn and light control."""

import json

import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "action"), [("flash_lights", "light-flash"), ("honk_horn", "horn")])
async def test_horn_light_commands(smart_fixture: respx.Router, method: str, action: str):
    """Test that horn and light commands send RHL with the matching action."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    horn_light_ctrl = account.vehicles["TestVIN0000000001"].horn_light_control

    assert await getattr(horn_light_ctrl, method)()

    calls = [
        c for c in smart_fixture.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path
    ]
    assert calls, "No telematics request was sent"
    payload = json.loads(calls[-1].request.content)
    assert payload["serviceId"] == "RHL"
    assert payload["command"] == "start"
    assert payload["operationScheduling"]["duration"] == 0
    assert payload["serviceParameters"] == [{"key": "rhl", "value": action}]
