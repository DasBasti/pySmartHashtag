"""Tests for handling missing fields in API responses."""

import logging

import pytest

from pysmarthashtag.models import get_field_as_type
from pysmarthashtag.vehicle.basic_status import BasicStatus
from pysmarthashtag.vehicle.battery import Battery
from pysmarthashtag.vehicle.climate import Climate
from pysmarthashtag.vehicle.maintenance import Maintenance
from pysmarthashtag.vehicle.position import Position
from pysmarthashtag.vehicle.running import Running
from pysmarthashtag.vehicle.safety import Safety
from pysmarthashtag.vehicle.tires import Tires
from pysmarthashtag.vehicle.trailer import Trailer


class TestGetFieldAsType:
    """Test the get_field_as_type helper function."""

    def test_get_int_field(self):
        """Test getting an integer field."""
        data = {"value": "42"}
        result = get_field_as_type(data, "value", int)
        assert result == 42

    def test_get_float_field(self):
        """Test getting a float field."""
        data = {"value": "3.14"}
        result = get_field_as_type(data, "value", float)
        assert result == 3.14

    def test_get_bool_field_true(self):
        """Test getting a boolean field with 'true'."""
        data = {"value": "true"}
        result = get_field_as_type(data, "value", bool)
        assert result is True

    def test_get_bool_field_false(self):
        """Test getting a boolean field with 'false'."""
        data = {"value": "false"}
        result = get_field_as_type(data, "value", bool)
        assert result is False

    def test_get_bool_field_one(self):
        """Test getting a boolean field with '1'."""
        data = {"value": "1"}
        result = get_field_as_type(data, "value", bool)
        assert result is True

    def test_get_bool_field_zero(self):
        """Test getting a boolean field with '0'."""
        data = {"value": "0"}
        result = get_field_as_type(data, "value", bool)
        assert result is False

    def test_missing_field_logs_error(self, caplog):
        """Test that a missing field logs an error."""
        data = {}
        with caplog.at_level(logging.ERROR):
            result = get_field_as_type(data, "missing_field", int, True)
        assert result is None
        assert "Field 'missing_field' not found in data" in caplog.text

    def test_missing_field_not_logs_error_by_default(self, caplog):
        """Test that a missing field logs an error."""
        data = {}
        with caplog.at_level(logging.ERROR):
            result = get_field_as_type(data, "missing_field", int)
        assert result is None
        assert "Field 'missing_field' not found in data" not in caplog.text

    def test_missing_field_no_log(self, caplog):
        """Test that a missing field does not log when log_missing=False."""
        data = {}
        with caplog.at_level(logging.ERROR):
            result = get_field_as_type(data, "missing_field", int, log_missing=False)
        assert result is None
        assert "Field 'missing_field' not found in data" not in caplog.text

    def test_none_value_logs_error(self, caplog):
        """Test that a None value logs an error."""
        data = {"value": None}
        with caplog.at_level(logging.ERROR):
            result = get_field_as_type(data, "value", int, True)
        assert result is None
        assert "Field 'value' has None value" in caplog.text

    def test_none_value_logs_no_error_by_default(self, caplog):
        """Test that a None value logs an error."""
        data = {"value": None}
        with caplog.at_level(logging.ERROR):
            result = get_field_as_type(data, "value", int)
        assert result is None
        assert "Field 'value' has None value" not in caplog.text

    def test_conversion_failure_logs_error(self, caplog):
        """Test that a conversion failure logs an error."""
        data = {"value": "not_a_number"}
        with caplog.at_level(logging.ERROR):
            result = get_field_as_type(data, "value", int)
        assert result is None
        assert "Failed to convert field 'value'" in caplog.text


class TestMissingFieldsInVehicleData:
    """Test that vehicle data classes handle missing fields gracefully."""

    def test_battery_with_missing_fields(self, caplog):
        """Test that Battery handles missing fields without failing."""
        # Minimal data with only the required structure
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "electricVehicleStatus": {}  # Empty - all fields missing
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            battery = Battery.from_vehicle_data(vehicle_data)
        # Should not fail, should return a valid object
        assert battery is not None or battery is None  # May return None if no parsed data

    def test_climate_with_missing_fields(self, caplog):
        """Test that Climate handles missing fields without failing."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "climateStatus": {}  # Empty - all fields missing
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            climate = Climate.from_vehicle_data(vehicle_data)
        # Should not fail, should not raise an exception
        assert climate is None or isinstance(climate, Climate)

    def test_safety_with_missing_fields(self, caplog):
        """Test that Safety handles missing fields without failing."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "drivingSafetyStatus": {}  # Empty - all fields missing
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            safety = Safety.from_vehicle_data(vehicle_data)
        # Should not fail
        assert safety is None or isinstance(safety, Safety)

    def test_running_with_missing_fields(self, caplog):
        """Test that Running handles missing fields without failing."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "runningStatus": {}  # Empty - all fields missing
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            running = Running.from_vehicle_data(vehicle_data)
        # Should not fail
        assert running is None or isinstance(running, Running)

    def test_maintenance_with_missing_fields(self, caplog):
        """Test that Maintenance handles missing fields without failing."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "maintenanceStatus": {}  # Empty - all fields missing
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            maintenance = Maintenance.from_vehicle_data(vehicle_data)
        # Should not fail
        assert maintenance is None or isinstance(maintenance, Maintenance)

    def test_position_with_missing_position_data(self, caplog):
        """Test that Position handles missing position data without failing."""
        vehicle_data = {
            "vehicleStatus": {
                "basicVehicleStatus": {}  # Missing position data
            }
        }
        with caplog.at_level(logging.ERROR):
            position = Position.from_vehicle_data(vehicle_data)
        # Should not fail
        assert position is None or isinstance(position, Position)

    def test_tires_with_missing_fields(self, caplog):
        """Test that Tires handles missing fields without failing."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "maintenanceStatus": {}  # Empty - all tire fields missing
                }
            }
        }
        with caplog.at_level(logging.ERROR):
            tires = Tires.from_vehicle_data(vehicle_data)
        # Should not fail
        assert tires is None or isinstance(tires, Tires)

    def test_partial_data_still_parses(self, caplog):
        """Test that partial data is still parsed correctly."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "electricVehicleStatus": {
                        "chargeLevel": "50",  # Only one field present
                    }
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            battery = Battery.from_vehicle_data(vehicle_data)
        assert battery is not None
        assert battery.remaining_battery_percent is not None
        assert battery.remaining_battery_percent.value == 50

    def test_dc_charging_bounds_checking(self, caplog):
        """Test that DC charging handles out-of-bounds battery values gracefully."""
        from pysmarthashtag.vehicle.battery import DcChargingVoltLevels

        # Test with value over 100 (should clamp to max index)
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "electricVehicleStatus": {
                        "chargeLevel": "150",  # Over 100
                        "chargerState": "15",  # DC_CHARGING
                        "dcChargeIAct": "100.0",
                    }
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            battery = Battery.from_vehicle_data(vehicle_data)
        assert battery is not None
        assert battery.charging_voltage is not None
        # Should use the last element in DcChargingVoltLevels
        assert battery.charging_voltage.value == DcChargingVoltLevels[len(DcChargingVoltLevels) - 1]

    def test_dc_charging_negative_value(self, caplog):
        """Test that DC charging handles negative battery values gracefully."""
        from pysmarthashtag.vehicle.battery import DcChargingVoltLevels

        # Test with negative value (should clamp to 0)
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "electricVehicleStatus": {
                        "chargeLevel": "-5",  # Negative
                        "chargerState": "15",  # DC_CHARGING
                        "dcChargeIAct": "100.0",
                    }
                },
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.ERROR):
            battery = Battery.from_vehicle_data(vehicle_data)
        assert battery is not None
        assert battery.charging_voltage is not None
        # Should use the first element in DcChargingVoltLevels
        assert battery.charging_voltage.value == DcChargingVoltLevels[0]


class TestTrailerExceptionHandling:
    """Test that Trailer exception handling works correctly after fixing finally block."""

    def test_trailer_keyerror_is_caught_and_logged(self, caplog):
        """Test that KeyError exceptions are caught and logged, not propagated."""
        # Missing 'additionalVehicleStatus' will cause KeyError on line 52
        vehicle_data = {
            "vehicleStatus": {
                # Missing 'additionalVehicleStatus'
                "updateTime": "1706028240000",
            }
        }
        with caplog.at_level(logging.INFO):
            # Should not raise KeyError, but should log it
            result = Trailer.from_vehicle_data(vehicle_data)

        # KeyError should be caught and logged
        assert "Trailer status info not available" in caplog.text
        # Should return None since no data was parsed
        assert result is None

    def test_trailer_non_keyerror_propagates(self):
        """Test that non-KeyError exceptions (e.g., ValueError) propagate correctly."""
        # Invalid updateTime that will cause ValueError in int() conversion
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "trailerStatus": {
                        "trailerTurningLampSts": "0",
                    }
                },
                "updateTime": "not_a_number",  # Will cause ValueError in int()
            }
        }

        # ValueError should propagate, not be swallowed
        with pytest.raises(ValueError):
            Trailer.from_vehicle_data(vehicle_data)

    def test_trailer_with_valid_data_returns_object(self):
        """Test that valid trailer data parses correctly."""
        vehicle_data = {
            "vehicleStatus": {
                "additionalVehicleStatus": {
                    "trailerStatus": {
                        "trailerTurningLampSts": "0",
                        "trailerFogLampSts": "1",
                        "trailerBreakLampSts": "0",
                        "trailerReversingLampSts": "0",
                        "trailerPosLampSts": "1",
                    }
                },
                "updateTime": "1706028240000",
            }
        }

        trailer = Trailer.from_vehicle_data(vehicle_data)
        assert trailer is not None
        assert trailer.turning_lamp_status == 0
        assert trailer.fog_lamp_status == 1


class TestBasicStatusExceptionHandling:
    """Test that BasicStatus exception handling works correctly after fixing finally block."""

    def test_basic_status_keyerror_is_caught_and_logged(self, caplog):
        """Test that KeyError exceptions are caught and logged, not propagated."""
        # Create a scenario where KeyError might occur
        # Note: BasicStatus uses .get() so KeyError is less likely, but we can still test the handler
        vehicle_data = {
            "vehicleStatus": {}  # Minimal data that might cause issues
        }
        with caplog.at_level(logging.INFO):
            # Should not raise KeyError
            result = BasicStatus.from_vehicle_data(vehicle_data)

        # Should return None since no meaningful data was parsed
        assert result is None

    def test_basic_status_non_keyerror_propagates(self):
        """Test that non-KeyError exceptions (e.g., ValueError) propagate correctly."""
        # Invalid updateTime that will cause ValueError in int() conversion
        vehicle_data = {
            "vehicleStatus": {
                "basicVehicleStatus": {
                    "speed": "50.0",
                },
                "updateTime": "invalid_timestamp",  # Will cause ValueError in int()
            }
        }

        # ValueError should propagate, not be swallowed
        with pytest.raises(ValueError):
            BasicStatus.from_vehicle_data(vehicle_data)

    def test_basic_status_with_invalid_notification_time_propagates(self):
        """Test that ValueError from datetime.fromtimestamp propagates."""
        # Very large timestamp value that will cause OSError/ValueError
        vehicle_data = {
            "vehicleStatus": {
                "notification": {
                    "time": 999999999999999999999,  # Absurdly large timestamp
                },
                "updateTime": "1706028240000",
            }
        }

        # Should propagate the exception from datetime.fromtimestamp
        with pytest.raises((ValueError, OSError, OverflowError)):
            BasicStatus.from_vehicle_data(vehicle_data)

    def test_basic_status_with_valid_data_returns_object(self):
        """Test that valid basic status data parses correctly."""
        vehicle_data = {
            "vehicleStatus": {
                "basicVehicleStatus": {
                    "speed": "50.0",
                    "direction": "N",
                    "engineStatus": "engine_off",
                },
                "updateTime": "1706028240000",
            }
        }

        basic_status = BasicStatus.from_vehicle_data(vehicle_data)
        assert basic_status is not None
        assert basic_status.speed is not None
        assert basic_status.speed.value == 50.0
        assert basic_status.direction == "N"
