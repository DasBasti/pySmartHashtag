"""Tests for the remote charging lid control."""

import json

import pytest
import respx

from pysmarthashtag.const import API_BASE_URL_V2
from pysmarthashtag.tests import RESPONSE_DIR, load_response
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles

SMART_5_VIN = "TestVIN0000000002"


def _last_telematics_payload(router: respx.Router) -> dict:
    """Return the JSON body of the most recent telematics PUT request."""
    calls = [c for c in router.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path]
    assert calls, "No telematics request was sent"
    return json.loads(calls[-1].request.content)


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "service_id"), [("open", "RDO"), ("close", "RDC")])
async def test_charging_lid_commands(smart_fixture: respx.Router, method: str, service_id: str):
    """Test that each charging lid command sends the matching telematics service."""
    smart_fixture.put(API_BASE_URL_V2 + "/remote-control/vehicle/telematics/" + SMART_5_VIN).respond(
        200, json=load_response(RESPONSE_DIR / "climate_success.json")
    )
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information(SMART_5_VIN)
    lid_ctrl = account.vehicles[SMART_5_VIN].charging_lid_control
    assert lid_ctrl is not None

    result = await getattr(lid_ctrl, method)()

    assert result
    payload = _last_telematics_payload(smart_fixture)
    assert payload["serviceId"] == service_id
    assert payload["command"] == "start"
    assert payload["serviceParameters"] == [{"key": "target", "value": "front-charge-lid"}]
    assert payload["userId"] == str(account.config.authentication.api_user_id)
    assert payload["operationScheduling"]["duration"] == 0
    assert "timeStamp" in payload


@pytest.mark.asyncio
async def test_charging_lid_control_smart_5_only(smart_fixture: respx.Router):
    """Test that only the Smart #5 gets a charging lid control."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    await account.get_vehicle_information(SMART_5_VIN)

    assert account.vehicles["TestVIN0000000001"].charging_lid_control is None
    assert account.vehicles[SMART_5_VIN].charging_lid_control is not None
