import pytest
import respx

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
