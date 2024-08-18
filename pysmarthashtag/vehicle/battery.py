"""Battery models for pysmarthashtag."""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase

_LOGGER = logging.getLogger(__name__)

"""Charging state of electric vehicle."""
ChargingState = [
    "NOT_CHARGING",
    "DEFAULT",
    "CHARGING",
    "ERROR",
    "COMPLETE",
    "FULLY_CHARGED",
    "FINISHED_FULLY_CHARGED",
    "FINISHED_NOT_FULL",
    "INVALID",
    "PLUGGED_IN",
    "WAITING_FOR_CHARGING",
    "TARGET_REACHED",
    "UNKNOWN",
    "UNKNOWN",
    "UNKNOWN",
    "DC_CHARGING",
]


@dataclass
class Battery(VehicleDataBase):
    """Provides an accessible version of the vehicle's battery data."""

    remaining_range: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining range of the vehicle."""

    remaining_range_at_full_charge: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining range at full charge of the vehicle."""

    remaining_battery_percent: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining battery percent of the vehicle."""

    charging_status: Optional[str] = None
    """Charging status of the vehicle as string."""

    charging_status_raw: Optional[int] = None
    """Charging status of the vehicle."""

    charger_connection_status: Optional[int] = None
    """Charger connection status of the vehicle."""

    is_charger_connected: bool = False
    """Is the charger connected to the vehicle."""

    charging_voltage: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging voltage of the vehicle."""

    charging_current: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging current of the vehicle."""

    charging_power: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging power of the vehicle."""

    charging_time_remaining: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging time remaining of the vehicle."""

    charging_target_soc: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging target state of charge."""

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
        _LOGGER.debug(f"Parsing battery data: {vehicle_data}")
        retval: Dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["electricVehicleStatus"]
            retval["remaining_range"] = ValueWithUnit(int(evStatus["distanceToEmptyOnBatteryOnly"]), "km")
            retval["remaining_range_at_full_charge"] = ValueWithUnit(
                int(evStatus["distanceToEmptyOnBattery100Soc"]), "km"
            )
            retval["remaining_battery_percent"] = ValueWithUnit(int(evStatus["chargeLevel"]), "%")
            status = int(evStatus["chargerState"])
            retval["charging_status"] = ChargingState[status] if status < len(ChargingState) else "UNKNOWN"
            retval["charging_status_raw"] = int(evStatus["chargerState"])
            retval["charger_connection_status"] = int(evStatus["statusOfChargerConnection"])
            retval["is_charger_connected"] = (
                retval["charging_status"] == "PLUGGED_IN"
                or retval["charging_status"] == "CHARGING"
                or retval["charging_status"] == "DC_CHARGING"
                or retval["charging_status"] == "COMPLETE"
            )

            if retval["charging_status"] == "DC_CHARGING":
                # TODO: The DC voltage value is not in the curretn response. We need to find the correct request first
                retval["charging_voltage"] = ValueWithUnit(0.0, "V")
                retval["charging_current"] = ValueWithUnit(abs(float(evStatus["dcChargeIAct"])), "A")
            else:
                retval["charging_voltage"] = ValueWithUnit(float(evStatus["chargeUAct"]), "V")
                retval["charging_current"] = ValueWithUnit(float(evStatus["chargeIAct"]), "A")

            retval["charging_power"] = ValueWithUnit(
                float(evStatus["chargeUAct"]) * float(evStatus["chargeIAct"])
                if retval["charging_voltage"].value < 300
                else float(evStatus["chargeUAct"]) * float(evStatus["chargeIAct"]) * math.sqrt(3),
                "W",
            )

            retval["charging_time_remaining"] = (
                ValueWithUnit(int(evStatus["timeToFullyCharged"]), "min")
                if evStatus["timeToFullyCharged"] != "2047"
                else None
            )

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
            # retval["charging_target_soc"] = raise NotImplementedError()
        except KeyError as e:
            _LOGGER.debug(f"Battery info not available: {e}")
        except Exception as e:
            _LOGGER.error(f"Error parsing battery data: {e}")
        finally:
            return retval
