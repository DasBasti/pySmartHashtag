import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
async def test_login(smart_fixture: respx.Router):
    """Test the login flow."""
    account = await prepare_account_with_vehicles()
    assert account is not None


@pytest.mark.asyncio
async def test_get_vehicles(smart_fixture: respx.Router):
    """Test the get_vehicles method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    vehicles = account.vehicles
    assert len(vehicles) == 1
    assert vehicles["TestVIN0000000001"].vin == "TestVIN0000000001"
