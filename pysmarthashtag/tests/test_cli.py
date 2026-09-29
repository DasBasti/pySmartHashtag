"""Tests for the command line interface helpers."""

import pytest
import respx

from pysmarthashtag.cli import _select_vin
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
async def test_select_vin_defaults_to_first_vehicle(smart_fixture: respx.Router):
    """Test that the first vehicle is selected when no VIN is given."""
    account = await prepare_account_with_vehicles()

    assert _select_vin(account, None) == next(iter(account.vehicles))


@pytest.mark.asyncio
async def test_select_vin_accepts_known_vin(smart_fixture: respx.Router):
    """Test that a VIN belonging to the account is returned unchanged."""
    account = await prepare_account_with_vehicles()

    assert _select_vin(account, "TestVIN0000000002") == "TestVIN0000000002"


@pytest.mark.asyncio
async def test_select_vin_rejects_unknown_vin(smart_fixture: respx.Router):
    """Test that a VIN not in the account is rejected with the available VINs."""
    account = await prepare_account_with_vehicles()

    with pytest.raises(SystemExit, match="VIN UnknownVIN not found in this account") as excinfo:
        _select_vin(account, "UnknownVIN")
    assert "TestVIN0000000001" in str(excinfo.value)


@pytest.mark.parametrize("vin", [None, "TestVIN0000000001"])
def test_select_vin_rejects_account_without_vehicles(vin):
    """Test that an account without vehicles is rejected."""

    class _EmptyAccount:
        vehicles: dict = {}

    with pytest.raises(SystemExit, match="No vehicles found"):
        _select_vin(_EmptyAccount(), vin)
