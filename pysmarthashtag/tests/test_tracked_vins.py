"""Only the configured VIN should be tracked; shared/other cars are ignored."""

import pytest

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.tests import TEST_PASSWORD, TEST_USERNAME


@pytest.mark.asyncio
async def test_tracked_vins_filters_out_other_vehicles(smart_fixture):
    """With tracked_vins set, only that VIN is added — others are ignored."""
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD, tracked_vins=["TestVIN0000000001"])
    await account.get_vehicles()
    assert set(account.vehicles.keys()) == {"TestVIN0000000001"}


@pytest.mark.asyncio
async def test_no_tracked_vins_keeps_all(smart_fixture):
    """Default (None) preserves the previous all-vehicles behaviour."""
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD)
    await account.get_vehicles()
    assert "TestVIN0000000002" in account.vehicles
