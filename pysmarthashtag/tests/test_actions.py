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
