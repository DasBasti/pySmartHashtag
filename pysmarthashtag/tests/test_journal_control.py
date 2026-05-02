"""Tests for the on-vehicle trip-recording toggle."""

import json

import pytest
import respx

from pysmarthashtag.const import API_JOURNAL_TOGGLE_URL
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
async def test_enable_recording(smart_fixture: respx.Router):
    """Calling enable_recording PUTs the JOU-start envelope and returns True."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    ctrl = account.vehicles["TestVIN0000000001"].journal_recording_control
    assert ctrl is not None

    result = await ctrl.enable_recording()
    assert result is True

    # Inspect the captured PUT body — find the route whose pattern includes
    # both the journalLog path and the PUT method.
    route = next(
        r for r in smart_fixture.routes
        if API_JOURNAL_TOGGLE_URL + "TestVIN0000000001" in str(r.pattern)
        and "PUT" in str(r.pattern)
    )
    sent = route.calls.last.request
    body = json.loads(sent.content.decode())
    assert body["command"] == "start"
    assert body["serviceId"] == "JOU"
    assert body["serviceParameters"] == [{"key": "jou", "value": "enable"}]
    assert body["operationScheduling"]["recurrentOperation"] is True
    assert body["operationScheduling"]["duration"] == 60
    assert body["creator"] == "tc"
    assert body["latest"] is False


@pytest.mark.asyncio
async def test_disable_recording(smart_fixture: respx.Router):
    """Calling disable_recording PUTs the JOU-stop envelope and returns True."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    ctrl = account.vehicles["TestVIN0000000001"].journal_recording_control

    result = await ctrl.disable_recording()
    assert result is True

    route = next(
        r for r in smart_fixture.routes
        if API_JOURNAL_TOGGLE_URL + "TestVIN0000000001" in str(r.pattern)
        and "PUT" in str(r.pattern)
    )
    sent = route.calls.last.request
    body = json.loads(sent.content.decode())
    assert body["command"] == "stop"
    assert body["serviceParameters"] == [{"key": "jou", "value": "disable"}]
