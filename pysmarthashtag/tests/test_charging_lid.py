"""Tests for the charging lid status."""

import pytest

from pysmarthashtag.tests import RESPONSE_DIR, load_response
from pysmarthashtag.vehicle.battery import Battery


def create_vehicle_data(ev_status: dict) -> dict:
    """Create minimal vehicle data carrying the given electric vehicle status."""
    return {
        "vehicleStatus": {
            "updateTime": "1716485767970",
            "additionalVehicleStatus": {"electricVehicleStatus": {"chargeLevel": "50", **ev_status}},
        },
    }


@pytest.mark.parametrize(
    ("lid_status", "expected"),
    [
        ("1", True),
        ("2", False),
        ("0", False),
    ],
)
def test_charging_lid_status(lid_status: str, expected: bool):
    """Only chargeLidDcAcStatus "1" means the lid is open."""
    battery = Battery.from_vehicle_data(create_vehicle_data({"chargeLidDcAcStatus": lid_status}))

    assert battery is not None
    assert battery.is_charging_lid_open is expected


@pytest.mark.parametrize("ev_status", [{}, {"chargeLidDcAcStatus": None}, {"chargeLidDcAcStatus": "n/a"}])
def test_charging_lid_unknown(ev_status: dict):
    """A vehicle that does not report the lid never reads as closed."""
    battery = Battery.from_vehicle_data(create_vehicle_data(ev_status))

    assert battery is not None
    assert battery.is_charging_lid_open is None


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ("vehicle_info.json", False),
        ("vehicle_info_dc_charging.json", True),
    ],
)
def test_charging_lid_from_api_response(response: str, expected: bool):
    """The recorded API responses report a closed lid, and an open one while DC charging."""
    vehicle_data = load_response(RESPONSE_DIR / response)["data"]

    assert Battery.from_vehicle_data(vehicle_data).is_charging_lid_open is expected
