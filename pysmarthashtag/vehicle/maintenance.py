"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase

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
    def from_vehicle_data(self, vehicle_data: Dict):
        """Create a new instance based on data from API."""
        parsed = self._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return self(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(self, vehicle_data: Dict) -> Optional[Dict]:
        """Parse the battery data based on Ids."""
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: Dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["maintenanceStatus"]
            _LOGGER.debug(f"Parsing maintenance data: {evStatus}")
            retval["main_battery_state_of_charge"] = int(evStatus["mainBatteryStatus"]["stateOfCharge"])
            retval["main_battery_charge_level"] = ValueWithUnit(
                float(evStatus["mainBatteryStatus"]["chargeLevel"]), "%"
            )
            retval["main_battery_energy_level"] = int(evStatus["mainBatteryStatus"]["energyLevel"])
            retval["main_battery_state_of_health"] = int(evStatus["mainBatteryStatus"]["stateOfHealth"])
            retval["main_batter_power_level"] = int(evStatus["mainBatteryStatus"]["powerLevel"])
            retval["main_battery_voltage"] = ValueWithUnit(float(evStatus["mainBatteryStatus"]["voltage"]), "V")

            retval["odometer"] = ValueWithUnit(int(float(evStatus["odometer"])), "km")
            retval["days_to_service"] = int(evStatus["daysToService"])
            retval["distance_to_service"] = ValueWithUnit(int(evStatus["distanceToService"]), "km")
            retval["service_warning_status"] = int(evStatus["serviceWarningStatus"])
            retval["break_fluid_level_status"] = int(evStatus["brakeFluidLevelStatus"])
            retval["washer_fluid_level_status"] = int(evStatus["washerFluidLevelStatus"])
            retval["engine_hours_to_service"] = int(evStatus["engineHrsToService"])

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.warning(f"Battery info not available: {e}")
        finally:
            return retval
