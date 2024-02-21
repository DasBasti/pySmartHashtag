import logging

import pytest
import respx
from httpx import Request, Response

from pysmarthashtag.const import API_BASE_URL
from pysmarthashtag.tests import RESPONSE_DIR, load_response
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles

_LOGGER = logging.getLogger(__name__)


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


@pytest.mark.asyncio
async def test_get_vehicles_token_expired(smart_fixture: respx.Router):
    """Test the get_vehicles method."""

    def switch_response(request: Request, route: respx.Route) -> Response:
        json_responsees = [
            "vehicle_info.json",
            "token_expired.json",
            "vehicle_info2.json",
        ]
        _LOGGER.warning("Switching response to %s", json_responsees[route.call_count])
        return Response(200, json=load_response(RESPONSE_DIR / json_responsees[route.call_count]))

    smart_fixture.get(
        API_BASE_URL + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
    ).mock(side_effect=switch_response)
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    assert account.vehicles["TestVIN0000000001"].engine_state == "engine_off"
    # now the token is invalid, refetched and data is updated
    await account.get_vehicle_information("TestVIN0000000001")

    assert account.vehicles["TestVIN0000000001"].engine_state == "engine_running"
