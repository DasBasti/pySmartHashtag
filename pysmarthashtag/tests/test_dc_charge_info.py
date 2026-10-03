"""Tests for the Smart #5 DC charge info (qrvs endpoint)."""

import httpx
import pytest
import respx

from pysmarthashtag.const import API_BASE_URL, API_BASE_URL_V2
from pysmarthashtag.models import ValueWithUnit
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles
from pysmarthashtag.tests.test_dc_charging import create_vehicle_data_with_dc_charging
from pysmarthashtag.vehicle.battery import Battery

QRVS_PATH = "/geelyTCAccess/tcservices/vehicle/status/qrvs/"
# chargeI 17880 -> (17880 - 16380) / 10 = 150 A, chargeU 1600 -> 1600 / 4 = 400 V
DC_CHARGE_INFO = {"chargeI": "17880", "chargeU": "1600"}


def _vehicle_data(series_code: str, dc_dc_connect_status: str, dc_charge_info: dict | None) -> dict:
    data = create_vehicle_data_with_dc_charging(charge_level=55, dc_charge_current=-1650.0, series_code=series_code)
    data["vehicleStatus"]["additionalVehicleStatus"]["electricVehicleStatus"][
        "dcDcConnectStatus"
    ] = dc_dc_connect_status
    if dc_charge_info is not None:
        data["dcChargeInfo"] = dc_charge_info
    return data


def _qrvs_calls(router: respx.Router) -> list:
    return [c for c in router.calls if QRVS_PATH in c.request.url.path]


def test_smart_5_uses_measured_dc_values():
    """Test that a #5 on a DC charger uses the measured qrvs current and voltage."""
    battery = Battery.from_vehicle_data(_vehicle_data("HY11", "3", DC_CHARGE_INFO))

    assert battery.charging_current == ValueWithUnit(150.0, "A")
    assert battery.charging_voltage == ValueWithUnit(400.0, "V")
    assert battery.charging_power == ValueWithUnit(60000, "W")


@pytest.mark.parametrize(
    ("series_code", "dc_dc_connect_status", "dc_charge_info"),
    [
        ("HY11", "0", DC_CHARGE_INFO),  # charger no longer connected: stale info is ignored
        ("HY11", "3", None),  # no info fetched
        ("HY11", "3", {"chargeI": "17880"}),  # incomplete info
        ("HX11", "3", DC_CHARGE_INFO),  # not a #5
    ],
)
def test_measured_dc_values_not_used(series_code: str, dc_dc_connect_status: str, dc_charge_info):
    """Test that the estimate from dcChargeIAct is kept when the measured values do not apply."""
    battery = Battery.from_vehicle_data(_vehicle_data(series_code, dc_dc_connect_status, dc_charge_info))

    assert battery.charging_current != ValueWithUnit(150.0, "A")
    assert battery.charging_voltage != ValueWithUnit(400.0, "V")


@pytest.mark.asyncio
async def test_dc_charge_info_fetched_for_smart_5_dc_charging(smart_fixture: respx.Router):
    """Test that the #5 test vehicle (DC charging, dcDcConnectStatus 3) gets the measured values."""
    account = await prepare_account_with_vehicles()
    calls_before = len(_qrvs_calls(smart_fixture))

    await account.get_vehicle_information("TestVIN0000000002")

    assert len(_qrvs_calls(smart_fixture)) == calls_before + 1
    battery = account.vehicles["TestVIN0000000002"].battery
    assert battery.charging_current == ValueWithUnit(150.0, "A")
    assert battery.charging_voltage == ValueWithUnit(400.0, "V")


@pytest.mark.asyncio
async def test_dc_charge_info_not_fetched_for_smart_1(smart_fixture: respx.Router):
    """Test that no qrvs request is made for a #1."""
    account = await prepare_account_with_vehicles()
    calls_before = len(_qrvs_calls(smart_fixture))

    await account.get_vehicle_information("TestVIN0000000001")

    assert len(_qrvs_calls(smart_fixture)) == calls_before


@pytest.mark.asyncio
async def test_dc_charge_info_failure_keeps_status_update(smart_fixture: respx.Router):
    """Test that a failing qrvs call falls back to the estimate and drops values from the previous poll."""
    account = await prepare_account_with_vehicles()
    vehicle = account.vehicles["TestVIN0000000002"]
    vehicle.data["dcChargeInfo"] = DC_CHARGE_INFO  # left over from an earlier poll
    for base_url in (API_BASE_URL, API_BASE_URL_V2):
        smart_fixture.get(f"{base_url}{QRVS_PATH}TestVIN0000000002").mock(
            return_value=httpx.Response(500, json={"code": "5000", "message": "server error"})
        )

    data = await account.get_vehicle_information("TestVIN0000000002")

    assert data
    assert "dcChargeInfo" not in vehicle.data
    assert vehicle.battery.charging_current != ValueWithUnit(150.0, "A")
