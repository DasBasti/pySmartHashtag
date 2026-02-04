"""Tests for Smart Global authentication mode."""

import logging

import pytest
import respx

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.const import GLOBAL_API_BASE_URL, SmartRegion, get_endpoint_urls_for_region
from pysmarthashtag.tests import TEST_PASSWORD, TEST_USERNAME
from pysmarthashtag.tests.common import SmartGlobalMockRouter

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def smart_global_fixture(request: pytest.FixtureRequest):
    """Patch Smart Global API calls."""
    router = SmartGlobalMockRouter()

    with router:
        yield router


async def create_global_account_with_vehicles():
    """Create and initialize account with global endpoints and get vehicles."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD, endpoint_urls=endpoint_urls)
    await account.get_vehicles()
    return account


@pytest.mark.asyncio
async def test_global_login(smart_global_fixture: respx.Router):
    """Test the login flow with global authentication."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD, endpoint_urls=endpoint_urls)
    await account.login()
    assert account.config.authentication.access_token is not None


@pytest.mark.asyncio
async def test_init_vehicles_global(smart_global_fixture: respx.Router):
    """Test _init_vehicles_global() correctly parses vehicles from global API."""
    account = await create_global_account_with_vehicles()
    
    # Verify that vehicles were initialized
    assert account is not None
    assert account.vehicles is not None
    assert len(account.vehicles) == 2
    
    # Verify vehicle VINs
    assert "TestVIN0000000001" in account.vehicles
    assert "TestVIN0000000002" in account.vehicles
    
    # Verify vehicle data
    vehicle1 = account.vehicles["TestVIN0000000001"]
    assert vehicle1.vin == "TestVIN0000000001"
    assert vehicle1.data.get("modelCode") == "HX11_EUL_Premium+_RWD_000"
    assert vehicle1.data.get("modelName") == "Smart #1"
    
    vehicle2 = account.vehicles["TestVIN0000000002"]
    assert vehicle2.vin == "TestVIN0000000002"
    assert vehicle2.data.get("modelCode") == "HY11_EUL_Premium+_RWD_000"
    assert vehicle2.data.get("modelName") == "Smart #3"


@pytest.mark.asyncio
async def test_update_global_vehicle_details(smart_global_fixture: respx.Router):
    """Test _update_global_vehicle_details() correctly populates combine_data and abilities."""
    account = await create_global_account_with_vehicles()
    
    # Verify that vehicles have detailed data from global API
    vehicle1 = account.vehicles["TestVIN0000000001"]
    
    # Check that combine_data was called with details from global API
    # The global_vehicle_details.json contains additional vehicle information
    assert vehicle1.data is not None
    assert vehicle1.data.get("vin") == "TestVIN0000000001"
    
    # Verify that abilities were populated from global API
    assert "abilities" in vehicle1.data
    abilities = vehicle1.data["abilities"]
    assert abilities is not None
    
    # Verify expected abilities structure
    assert "remoteControl" in abilities
    assert "chargingControl" in abilities
    assert "vehicleStatus" in abilities
    
    # Verify specific abilities
    assert abilities["remoteControl"]["climate"] is True
    assert abilities["chargingControl"]["startCharging"] is True
    assert abilities["vehicleStatus"]["battery"] is True


@pytest.mark.asyncio
async def test_global_with_endpoint_urls(smart_global_fixture: respx.Router):
    """Test global authentication using EndpointUrls directly."""
    from pysmarthashtag.const import EndpointUrls
    
    endpoint_urls = EndpointUrls(
        api_base_url=GLOBAL_API_BASE_URL,
        api_base_url_v2=GLOBAL_API_BASE_URL,
    )
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD, endpoint_urls=endpoint_urls)
    await account.get_vehicles()
    
    # Verify vehicles were loaded
    assert len(account.vehicles) == 2
    assert "TestVIN0000000001" in account.vehicles
    assert "TestVIN0000000002" in account.vehicles


@pytest.mark.asyncio
async def test_global_auth_mode_detection(smart_global_fixture: respx.Router):
    """Test that global auth mode is correctly detected."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD, endpoint_urls=endpoint_urls)
    await account.login()
    
    # Verify that the account uses global HMAC authentication
    from pysmarthashtag.const import SmartAuthMode
    assert account.config.authentication.auth_mode == SmartAuthMode.GLOBAL_HMAC
    assert account._is_global_auth() is True
