"""Tests for the remote door lock control."""

import json

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
        ("open_trunk", "RDU_2", {"key": "target", "value": "trunk"}),
        ("close_trunk", "RDL_2", {"key": "target", "value": "trunk"}),
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
