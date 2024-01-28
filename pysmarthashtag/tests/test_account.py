import pytest
import respx

from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


@pytest.mark.asyncio
async def test_login(smart_fixture: respx.Router):
    """Test the login flow."""
    account = prepare_account_with_vehicles()
    assert account is not None
