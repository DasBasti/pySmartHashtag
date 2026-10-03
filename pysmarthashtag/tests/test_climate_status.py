"""Tests for parsing the seat and steering wheel heating status."""

import pytest

from pysmarthashtag.vehicle.climate import Climate


def _climate(**climate_status) -> Climate:
    return Climate.from_vehicle_data({"vehicleStatus": {"additionalVehicleStatus": {"climateStatus": climate_status}}})


@pytest.mark.parametrize(
    ("value", "level", "active"),
    [("0", 0, False), ("1", 1, True), ("2", 2, True), ("3", 3, True), (3, 3, True)],
)
@pytest.mark.parametrize(
    ("key", "name"),
    [
        ("drvHeatSts", "driver"),
        ("passHeatingSts", "passenger"),
        ("rlHeatingSts", "rear_left"),
        ("rrHeatingSts", "rear_right"),
    ],
)
def test_seat_heating_status_is_level(key: str, name: str, value, level: int, active: bool):
    """Test that seat heating status fields are parsed as level, and any level above 0 is on."""
    climate = _climate(**{key: value})

    assert getattr(climate, f"{name}_heating_level") == level
    assert getattr(climate, f"{name}_heating_status") is active


@pytest.mark.parametrize(
    ("value", "active"),
    [("1", True), ("2", False), (2, False), ("0", False)],
)
def test_steering_wheel_heating_status(value, active: bool):
    """Test that the steering wheel heating status uses 1 = on, 2 = off."""
    assert _climate(steerWhlHeatingSts=value).steering_wheel_heating_status is active


def test_missing_heating_status_is_none():
    """Test that missing heating fields stay None instead of reading as off."""
    climate = _climate()

    assert climate.driver_heating_level is None
    assert climate.driver_heating_status is None
    assert climate.steering_wheel_heating_status is None
