import json
import logging

import pytest
import respx

from pysmarthashtag.control.climate import HeatingLocation
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
async def test_enable_climate(smart_fixture: respx.Router):
    """Test the set_climate_conditioning method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].climate_control
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control
    result = await climate_ctrl.set_climate_conditioning(20, True)
    assert result


@pytest.mark.asyncio
async def test_disable_climate(smart_fixture: respx.Router):
    """Test the set_climate_conditioning method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].climate_control
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control
    result = await climate_ctrl.set_climate_conditioning(20, False)
    assert result


@pytest.mark.asyncio
async def test_enable_climate_invalid_temperature(smart_fixture: respx.Router):
    """Test the set_climate_conditioning method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].climate_control
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control
    with pytest.raises(ValueError) as excinfo:
        await climate_ctrl.set_climate_conditioning(-20, True)
    assert str(excinfo.value) == "Temperature must be between 16 and 30 degrees."


@pytest.mark.asyncio
async def test_enable_seatheating(smart_fixture: respx.Router):
    """Test the set_climate_conditioning method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].climate_control
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control
    for loc in HeatingLocation:
        climate_ctrl.set_heating_level(loc, 3)
    result = await climate_ctrl.set_climate_conditioning(20, True)
    assert result


@pytest.mark.asyncio
async def test_enable_seatheating_invalid_level(smart_fixture: respx.Router):
    """Test the set_climate_conditioning method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].climate_control
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control
    with pytest.raises(ValueError) as excinfo:
        climate_ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 4)
    assert str(excinfo.value) == "Seat heating level must be between 0 and 3."


def _last_telematics_payload(router: respx.Router) -> dict:
    """Return the JSON body of the most recent telematics PUT request."""
    calls = [c for c in router.calls if c.request.method == "PUT" and "/vehicle/telematics/" in c.request.url.path]
    assert calls, "No telematics request was sent"
    return json.loads(calls[-1].request.content)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("active", "command", "duration"),
    [(True, "start", 90), (False, "stop", 0)],
)
async def test_set_defrost(smart_fixture: respx.Router, active: bool, command: str, duration: int):
    """Test that set_defrost sends the RCE_2 defrost command."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    result = await climate_ctrl.set_defrost(active)

    assert result
    payload = _last_telematics_payload(smart_fixture)
    assert payload["serviceId"] == "RCE_2"
    assert payload["command"] == command
    assert payload["operationScheduling"]["duration"] == duration
    assert payload["serviceParameters"] == [
        {"key": "rce.conditioner", "value": "2"},
        {"key": "rce.level", "value": "2"},
    ]


@pytest.mark.asyncio
async def test_set_defrost_does_not_touch_conditioning_template(smart_fixture: respx.Router):
    """Test that a defrost command leaves the climate conditioning payload unchanged."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    await climate_ctrl.set_defrost(True)
    await climate_ctrl.set_climate_conditioning(20, True)

    payload = _last_telematics_payload(smart_fixture)
    assert payload["operationScheduling"]["duration"] == 180
    assert {"key": "rce.conditioner", "value": "1"} in payload["serviceParameters"]


@pytest.mark.asyncio
async def test_set_defrost_invalid_state(smart_fixture: respx.Router):
    """Test that set_defrost rejects non-boolean states."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    with pytest.raises(TypeError):
        await climate_ctrl.set_defrost("on")


@pytest.mark.asyncio
async def test_rce_command_logs_payload_and_response(smart_fixture: respx.Router, caplog: pytest.LogCaptureFixture):
    """Test that RCE commands log the sent payload and the API response for debugging."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control
    climate_ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)

    with caplog.at_level(logging.DEBUG, logger="pysmarthashtag.control.climate"):
        await climate_ctrl.set_climate_conditioning(20, True)

    assert "Sending RCE command (seriesCodeVs=" in caplog.text
    assert '{"key":"rce.heat","value":"front-left"}' in caplog.text
    assert "RCE command response:" in caplog.text


@pytest.mark.asyncio
async def test_set_heating_start_sends_heat_only(smart_fixture: respx.Router):
    """Test that set_heating starts heating without climate conditioning parameters."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    result = await climate_ctrl.set_heating(True, {HeatingLocation.DRIVER_SEAT: 3, HeatingLocation.PASSENGER_SEAT: 1})

    assert result
    payload = _last_telematics_payload(smart_fixture)
    assert payload["serviceId"] == "RCE_2"
    assert payload["command"] == "start"
    assert payload["serviceParameters"] == [
        {"key": "rce.heat", "value": "front-left"},
        {"key": "rce.level", "value": "3"},
        {"key": "rce.heat", "value": "front-right"},
        {"key": "rce.level", "value": "1"},
    ]


@pytest.mark.asyncio
async def test_set_heating_stop_sets_level_zero(smart_fixture: respx.Router):
    """Test that set_heating stops all given locations with level 0."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    await climate_ctrl.set_heating(False, {HeatingLocation.STEERING_WHEEL: 0})

    payload = _last_telematics_payload(smart_fixture)
    assert payload["command"] == "stop"
    assert payload["serviceParameters"] == [
        {"key": "rce.heat", "value": "steering_wheel"},
        {"key": "rce.level", "value": "0"},
    ]


@pytest.mark.asyncio
async def test_set_heating_does_not_change_conditioning_levels(smart_fixture: respx.Router):
    """Test that set_heating leaves the levels used for climate conditioning untouched."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    await climate_ctrl.set_heating(True, {HeatingLocation.DRIVER_SEAT: 3})

    assert climate_ctrl.heating_levels[HeatingLocation.DRIVER_SEAT] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("active", "levels", "exc"),
    [
        (True, {}, ValueError),
        (True, {HeatingLocation.DRIVER_SEAT: 0}, ValueError),
        (True, {HeatingLocation.DRIVER_SEAT: 4}, ValueError),
        (True, {HeatingLocation.DRIVER_SEAT: "3"}, TypeError),
        ("on", {HeatingLocation.DRIVER_SEAT: 3}, TypeError),
    ],
)
async def test_set_heating_invalid_input(smart_fixture: respx.Router, active, levels, exc):
    """Test that set_heating rejects invalid input."""
    account = await prepare_account_with_vehicles()
    await account.get_vehicle_information("TestVIN0000000001")
    climate_ctrl = account.vehicles["TestVIN0000000001"].climate_control

    with pytest.raises(exc):
        await climate_ctrl.set_heating(active, levels)
