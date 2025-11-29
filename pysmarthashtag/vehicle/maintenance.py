"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class Maintenance(VehicleDataBase):
    """Provides an accessible version of the vehicle's maintenance data."""

    days_to_service: Optional[int] = None
    """Days to service."""

    engine_hours_to_service: Optional[int] = None
    """Engine hours to service."""

    odometer: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Odometer."""

    break_fluid_level_status: Optional[int] = None
    """Break fluid level status."""

    main_battery_state_of_charge: Optional[int] = None
    """Main battery state of charge."""

    main_battery_charge_level: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Main battery charge level."""

    main_battery_energy_level: Optional[int] = None
    """Main battery energy level."""

    main_battery_state_of_health: Optional[int] = None
    """Main battery state of health."""

    main_batter_power_level: Optional[int] = None
    """Main battery power level."""

    main_battery_voltage: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Main battery voltage."""

    distance_to_service: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Distance to service."""

    service_warning_status: Optional[int] = None
    """Service warning status."""

    washer_fluid_level_status: Optional[int] = None
    """Washer fluid level status."""

    @classmethod
    def from_vehicle_data(self, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = self._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return self(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(self, vehicle_data: dict) -> Optional[dict]:
        """Parse the maintenance data based on Ids."""
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["maintenanceStatus"]
            _LOGGER.debug("Parsing maintenance data")

            mainBatteryStatus = evStatus.get("mainBatteryStatus")
            if mainBatteryStatus:
                retval["main_battery_state_of_charge"] = get_field_as_type(mainBatteryStatus, "stateOfCharge", int)
                charge_level = get_field_as_type(mainBatteryStatus, "chargeLevel", float)
                retval["main_battery_charge_level"] = (
                    ValueWithUnit(charge_level, "%") if charge_level is not None else None
                )
                retval["main_battery_energy_level"] = get_field_as_type(mainBatteryStatus, "energyLevel", int)
                retval["main_battery_state_of_health"] = get_field_as_type(mainBatteryStatus, "stateOfHealth", int)
                retval["main_batter_power_level"] = get_field_as_type(mainBatteryStatus, "powerLevel", int)
                voltage = get_field_as_type(mainBatteryStatus, "voltage", float)
                retval["main_battery_voltage"] = ValueWithUnit(voltage, "V") if voltage is not None else None

            odometer = get_field_as_type(evStatus, "odometer", float)
            retval["odometer"] = ValueWithUnit(int(odometer), "km") if odometer is not None else None
            retval["days_to_service"] = get_field_as_type(evStatus, "daysToService", int)
            distance_to_service = get_field_as_type(evStatus, "distanceToService", int)
            retval["distance_to_service"] = (
                ValueWithUnit(distance_to_service, "km") if distance_to_service is not None else None
            )
            retval["service_warning_status"] = get_field_as_type(evStatus, "serviceWarningStatus", int)
            retval["break_fluid_level_status"] = get_field_as_type(evStatus, "brakeFluidLevelStatus", int)
            retval["washer_fluid_level_status"] = get_field_as_type(evStatus, "washerFluidLevelStatus", int)
            retval["engine_hours_to_service"] = get_field_as_type(evStatus, "engineHrsToService", int)

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.error(f"Maintenance info not available: {e}")
        finally:
            return retval
