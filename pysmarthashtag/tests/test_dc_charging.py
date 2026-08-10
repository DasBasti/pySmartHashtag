"""Tests for DC charging data handling."""

import math

from pysmarthashtag.models import ValueWithUnit
from pysmarthashtag.vehicle.battery import Battery, ChargingState, DcChargingVoltLevels


def create_vehicle_data_with_dc_charging(
    charge_level: int, dc_charge_current: float, series_code: str = "HX11"
) -> dict:
    """Create test vehicle data with DC charging parameters.

    Args:
    ----
        charge_level: Battery charge level percentage (0-100)
        dc_charge_current: DC charging current as reported by the API
            (negative for charging, deci-ampere on the Smart #5)
        series_code: Value of the "seriesCodeVs" field selecting the vehicle model

    Returns:
    -------
        dict: Vehicle data structure for testing

    """
    return {
        "seriesCodeVs": series_code,
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
        },
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
        # Voltage should match lookup table at index 67
        assert battery.charging_voltage == ValueWithUnit(value=DcChargingVoltLevels[67], unit="V")
        # Power = 102.6 * voltage (floored)
        expected_power = math.floor(102.6 * DcChargingVoltLevels[67])
        assert battery.charging_power == ValueWithUnit(value=expected_power, unit="W")

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


class TestDcChargingSmart5Scaling:
    """Test that the Smart #5 deci-ampere DC current is scaled down (issue #459)."""

    def test_smart_5_dc_current_is_divided_by_ten(self):
        """Test that a #5 reporting 1650 deci-ampere yields 165 A instead of 1650 A."""
        vehicle_data = create_vehicle_data_with_dc_charging(
            charge_level=55, dc_charge_current=-1650.0, series_code="HY11"
        )
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "DC_CHARGING"
        assert battery.charging_current == ValueWithUnit(value=165.0, unit="A")
        # Voltage is unaffected by the scaling
        assert battery.charging_voltage == ValueWithUnit(value=DcChargingVoltLevels[55], unit="V")
        expected_power = math.floor(165.0 * DcChargingVoltLevels[55])
        assert battery.charging_power == ValueWithUnit(value=expected_power, unit="W")

    def test_smart_1_dc_current_is_not_scaled(self):
        """Test that the #1 keeps reporting DC current in ampere."""
        vehicle_data = create_vehicle_data_with_dc_charging(
            charge_level=55, dc_charge_current=-165.0, series_code="HX11"
        )
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_current == ValueWithUnit(value=165.0, unit="A")

    def test_smart_3_dc_current_is_not_scaled(self):
        """Test that the #3 keeps reporting DC current in ampere."""
        vehicle_data = create_vehicle_data_with_dc_charging(
            charge_level=55, dc_charge_current=-165.0, series_code="HC11"
        )
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_current == ValueWithUnit(value=165.0, unit="A")

    def test_missing_series_code_is_not_scaled(self):
        """Test that data without a series code falls back to the unscaled V1 behaviour."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=55, dc_charge_current=-165.0)
        del vehicle_data["seriesCodeVs"]
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_current == ValueWithUnit(value=165.0, unit="A")

    def test_smart_5_ac_current_is_not_scaled(self):
        """Test that AC charging on a #5 is passed through unscaled."""
        vehicle_data = create_vehicle_data_with_dc_charging(charge_level=55, dc_charge_current=0.0, series_code="HY11")
        evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["electricVehicleStatus"]
        evStatus["chargerState"] = "2"  # CHARGING (AC)
        evStatus["chargeUAct"] = "230.0"
        evStatus["chargeIAct"] = "16.000"
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charging_status == "CHARGING"
        assert battery.charging_current == ValueWithUnit(value=16.0, unit="A")
        assert battery.charging_voltage == ValueWithUnit(value=230.0, unit="V")
        assert battery.charging_power == ValueWithUnit(value=230.0 * 16.0, unit="W")


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

    def test_voltage_table_covers_full_soc_range(self):
        """Test the voltage lookup table covers 0-100% SOC range."""
        # Table should have at least 101 entries to cover 0-100 indices
        assert len(DcChargingVoltLevels) >= 101
        # Verify we can access indices 0 and 100
        _ = DcChargingVoltLevels[0]
        _ = DcChargingVoltLevels[100]

    def test_voltage_values_in_expected_range(self):
        """Test voltage values are within expected DC charging voltage range."""
        # DC charging typically occurs between 300-500V for EV batteries
        for voltage in DcChargingVoltLevels:
            assert 300 <= voltage <= 500, f"Voltage {voltage} outside expected range 300-500V"

    def test_voltage_table_monotonic_tendency(self):
        """Test that voltage values generally increase with battery level."""
        # While not strictly monotonic, the table should trend upward
        assert DcChargingVoltLevels[0] < DcChargingVoltLevels[100]
        assert DcChargingVoltLevels[0] < DcChargingVoltLevels[50]
        assert DcChargingVoltLevels[50] < DcChargingVoltLevels[100]
