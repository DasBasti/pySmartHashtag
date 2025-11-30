import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
async def test_start_charging(smart_fixture: respx.Router):
    """Test the start_charging method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].charging_control
    charging_ctrl = account.vehicles["TestVIN0000000001"].charging_control
    result = await charging_ctrl.start_charging()
    assert result


@pytest.mark.asyncio
async def test_stop_charging(smart_fixture: respx.Router):
    """Test the stop_charging method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].charging_control
    charging_ctrl = account.vehicles["TestVIN0000000001"].charging_control
    result = await charging_ctrl.stop_charging()
    assert result
