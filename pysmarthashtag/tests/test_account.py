import logging

import httpx
import pytest
import respx
from httpx import Request, Response

from pysmarthashtag.const import API_BASE_URL, API_SELECT_CAR_URL
from pysmarthashtag.models import SmartTokenRefreshNecessary, ValueWithUnit
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
    assert len(vehicles) == 2
    assert vehicles["TestVIN0000000001"].vin == "TestVIN0000000001"
    assert vehicles["TestVIN0000000002"].vin == "TestVIN0000000002"


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


@pytest.mark.asyncio
async def test_unmapped_code_refreshes_once_then_recovers(smart_fixture: respx.Router):
    """A cloud code with no typed remedy gets one refresh, then the retry succeeds."""

    def switch_response(request: Request, route: respx.Route) -> Response:
        if route.call_count == 1:
            return Response(200, json={"code": "9999", "message": "something new"})
        name = "vehicle_info.json" if route.call_count == 0 else "vehicle_info2.json"
        return Response(200, json=load_response(RESPONSE_DIR / name))

    smart_fixture.get(
        API_BASE_URL + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
    ).mock(side_effect=switch_response)

    account = await prepare_account_with_vehicles()
    assert account.vehicles["TestVIN0000000001"].engine_state == "engine_off"

    await account.get_vehicle_information("TestVIN0000000001")
    assert account.vehicles["TestVIN0000000001"].engine_state == "engine_running"


@pytest.mark.asyncio
async def test_unmapped_code_surfaces_if_refresh_does_not_help(smart_fixture: respx.Router):
    """The refresh is tried once only; a persistent unmapped code still surfaces."""
    account = await prepare_account_with_vehicles()

    smart_fixture.get(
        API_BASE_URL + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
    ).mock(return_value=Response(200, json={"code": "9999", "message": "still broken"}))

    with pytest.raises(httpx.HTTPStatusError):
        await account.get_vehicle_information("TestVIN0000000001")


@pytest.mark.asyncio
async def test_no_human_car_connection(smart_fixture: respx.Router):
    """Test the get_vehicles method."""

    did_call_car_selection = 0

    def switch_response(request: Request, route: respx.Route) -> Response:
        json_responsees = [
            "Human_and_vehicle_relationship_does_not_exist.json",
            "vehicle_info.json",
        ]
        _LOGGER.warning("Switching response to %s", json_responsees[did_call_car_selection])
        return Response(200, json=load_response(RESPONSE_DIR / json_responsees[did_call_car_selection]))

    def count_car_selection(request: Request, route: respx.Route) -> Response:
        nonlocal did_call_car_selection
        did_call_car_selection += 1
        return Response(200, json={})

    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None

    vehicle_status = smart_fixture.get(
        API_BASE_URL + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
    ).mock(side_effect=switch_response)
    car_connection = smart_fixture.post(API_BASE_URL + API_SELECT_CAR_URL).mock(side_effect=count_car_selection)

    await account.get_vehicle_information("TestVIN0000000001")
    assert car_connection.call_count == 2  # 2 times for the connection refresh
    assert vehicle_status.call_count == 3  # 2 times for the token refresh and 1 time for the inital call


@pytest.mark.asyncio
async def test_get_vehicle_chargin_dc(smart_fixture: respx.Router):
    """Test the get_vehicles method."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.vehicles is not None
    vehicles = account.vehicles
    assert len(vehicles) == 2
    # TODO: missing ac charging
    # TODO: missing 3-phase charging
    assert vehicles["TestVIN0000000002"].battery.charging_status == "DC_CHARGING"
    assert vehicles["TestVIN0000000002"].battery.is_charger_connected
    # VIN ...002 has a Smart #5 series code, so the raw "dcChargeIAct" of -102.6 is
    # read as deci-ampere and scaled down to 10.26 A (issue #459).
    assert vehicles["TestVIN0000000002"].battery.charging_current == ValueWithUnit(value=10.26, unit="A")
    assert vehicles["TestVIN0000000002"].battery.charging_voltage == ValueWithUnit(value=429, unit="V")
    assert vehicles["TestVIN0000000002"].battery.charging_power == ValueWithUnit(value=4401, unit="W")


@pytest.mark.asyncio
async def test_exhausted_retries_surface_real_cause(smart_fixture: respx.Router):
    """When every retry fails, the underlying cause is raised, not a generic auth error.

    A transient cloud failure should stay transient so the caller can retry,
    instead of being reported as an authentication problem.
    """
    account = await prepare_account_with_vehicles()

    # Every attempt now fails with 1402, so the retry loop is exhausted.
    smart_fixture.get(
        API_BASE_URL + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
    ).mock(return_value=Response(200, json=load_response(RESPONSE_DIR / "token_expired.json")))

    with pytest.raises(SmartTokenRefreshNecessary):
        await account.get_vehicle_information("TestVIN0000000001")
