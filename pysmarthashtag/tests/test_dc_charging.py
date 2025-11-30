"""Tests for DC charging data handling."""

import math

from pysmarthashtag.models import ValueWithUnit
from pysmarthashtag.vehicle.battery import Battery, ChargingState, DcChargingVoltLevels


def create_vehicle_data_with_dc_charging(charge_level: int, dc_charge_current: float) -> dict:
    """Create test vehicle data with DC charging parameters.

    Args:
        charge_level: Battery charge level percentage (0-100)
        dc_charge_current: DC charging current in Amps (negative for charging)

    Returns:
        dict: Vehicle data structure for testing

    """
    return {
        "vehicleStatus": {
            "updateTime": "1716485767970",
            "additionalVehicleStatus": {
                "electricVehicleStatus": {
                    "distanceToEmptyOnBatteryOnly": "285",
                    "distanceToEmptyOnBattery100Soc": "427",
                    "chargerState": "15",  # DC_CHARGING
                    "chargeLevel": str(charge_level),
                    "statusOfChargerConnection": "1",
                    "dcChargeIAct": str(dc_charge_current),
                    "chargeUAct": "0.0",
                    "chargeIAct": "0.000",
                    "timeToFullyCharged": "37",
                    "averPowerConsumption": "-102.3",
                }
            },
        }
    }


class TestDcChargingDataHandling:
    """Test DC charging data handling."""

    def test_dc_charging_at_low_battery_level(self):
        """Test DC charging at low battery level (0%)."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=0, dc_charge_current=-150.0)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "DC_CHARGING"
        assert battery.is_charger_connected is True
        assert battery.charging_current == ValueWithUnit(value=150.0, unit="A")
        # Voltage at index 0 is 370V
        assert battery.charging_voltage == ValueWithUnit(value=DcChargingVoltLevels[0], unit="V")
        # Power = current * voltage = 150 * 370 = 55500W
        expected_power = math.floor(150.0 * DcChargingVoltLevels[0])
        assert battery.charging_power == ValueWithUnit(value=expected_power, unit="W")

    def test_dc_charging_at_mid_battery_level(self):
        """Test DC charging at 50% battery level."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=50, dc_charge_current=-120.0)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "DC_CHARGING"
        assert battery.is_charger_connected is True
        assert battery.charging_current == ValueWithUnit(value=120.0, unit="A")
        # Voltage at index 50 from the lookup table
        assert battery.charging_voltage == ValueWithUnit(value=DcChargingVoltLevels[50], unit="V")
        expected_power = math.floor(120.0 * DcChargingVoltLevels[50])
        assert battery.charging_power == ValueWithUnit(value=expected_power, unit="W")

    def test_dc_charging_at_high_battery_level(self):
        """Test DC charging at high battery level (100%)."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=100, dc_charge_current=-50.0)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "DC_CHARGING"
        assert battery.is_charger_connected is True
        assert battery.charging_current == ValueWithUnit(value=50.0, unit="A")
        # Index 100 is the last valid index in the table
        assert battery.charging_voltage == ValueWithUnit(value=DcChargingVoltLevels[100], unit="V")
        expected_power = math.floor(50.0 * DcChargingVoltLevels[100])
        assert battery.charging_power == ValueWithUnit(value=expected_power, unit="W")

    def test_dc_charging_at_67_percent(self):
        """Test DC charging at 67% battery level (matching existing test data)."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=67, dc_charge_current=-102.6)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "DC_CHARGING"
        assert battery.is_charger_connected is True
        assert battery.charging_current == ValueWithUnit(value=102.6, unit="A")
        # Voltage at index 67 is 429V
        assert battery.charging_voltage == ValueWithUnit(value=429, unit="V")
        # Power = 102.6 * 429 = 44015 (floored)
        assert battery.charging_power == ValueWithUnit(value=44015, unit="W")

    def test_dc_charging_clamping_above_table_bounds(self):
        """Test DC charging with battery level above the lookup table bounds (>100)."""
        # Create data with charge level above 100 to test bounds clamping
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=110, dc_charge_current=-30.0)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "DC_CHARGING"
        # Should clamp to max index (100)
        assert battery.charging_voltage == ValueWithUnit(value=DcChargingVoltLevels[100], unit="V")
        assert battery.charging_current == ValueWithUnit(value=30.0, unit="A")
        expected_power = math.floor(30.0 * DcChargingVoltLevels[100])
        assert battery.charging_power == ValueWithUnit(value=expected_power, unit="W")

    def test_dc_charging_with_positive_current(self):
        """Test DC charging with positive current value (should use absolute value)."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=50, dc_charge_current=100.0)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        # Current should be absolute value
        assert battery.charging_current == ValueWithUnit(value=100.0, unit="A")

    def test_dc_charging_time_remaining(self):
        """Test that time remaining is correctly parsed during DC charging."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=67, dc_charge_current=-102.6)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_time_remaining == ValueWithUnit(value=37, unit="min")

    def test_dc_charging_battery_percent(self):
        """Test that battery percentage is correctly parsed during DC charging."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=67, dc_charge_current=-102.6)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.remaining_battery_percent == ValueWithUnit(value=67, unit="%")

    def test_dc_charging_range_values(self):
        """Test that range values are correctly parsed during DC charging."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=67, dc_charge_current=-102.6)
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.remaining_range == ValueWithUnit(value=285, unit="km")
        assert battery.remaining_range_at_full_charge == ValueWithUnit(value=427, unit="km")


class TestChargingStateEnum:
    """Test charging state handling."""

    def test_dc_charging_state_index(self):
        """Test that chargerState 15 maps to DC_CHARGING."""
        assert ChargingState[15] == "DC_CHARGING"

    def test_charging_state_list_length(self):
        """Test the charging state list has expected length."""
        assert len(ChargingState) == 16


class TestDcChargingVoltLevels:
    """Test DC charging voltage lookup table."""

    def test_voltage_table_length(self):
        """Test the voltage lookup table has expected length."""
        assert len(DcChargingVoltLevels) == 101

    def test_voltage_table_bounds(self):
        """Test voltage values at table bounds."""
        # First value
        assert DcChargingVoltLevels[0] == 370
        # Last value
        assert DcChargingVoltLevels[100] == 465

    def test_voltage_table_monotonic_tendency(self):
        """Test that voltage values generally increase with battery level."""
        # While not strictly monotonic, the table should trend upward
        assert DcChargingVoltLevels[0] < DcChargingVoltLevels[100]
        assert DcChargingVoltLevels[0] < DcChargingVoltLevels[50]
        assert DcChargingVoltLevels[50] < DcChargingVoltLevels[100]
