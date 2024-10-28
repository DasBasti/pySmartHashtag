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

DcChargingVoltLevels = [
    370,
    374,
    377,
    381,
    385,
    389,
    392,
    396,
    400,
    403,
    407,
    408,
    408,
    409,
    409,
    410,
    410,
    411,
    411,
    412,
    412,
    413,
    413,
    413,
    413,
    414,
    414,
    415,
    416,
    416,
    416,
    416,
    416,
    416,
    417,
    417,
    415,
    416,
    416,
    416,
    417,
    417,
    417,
    416,
    416,
    417,
    417,
    417,
    416,
    417,
    418,
    418,
    417,
    417,
    418,
    419,
    420,
    419,
    419,
    420,
    422,
    423,
    424,
    425,
    426,
    427,
    428,
    429,
    430,
    431,
    433,
    434,
    435,
    436,
    437,
    437,
    439,
    440,
    441,
    440,
    440,
    441,
    443,
    444,
    445,
    446,
    448,
    449,
    450,
    451,
    453,
    454,
    455,
    456,
    458,
    459,
    460,
    461,
    463,
    464,
    465,
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

    average_power_consumption: Optional[ValueWithUnit] = ValueWithUnit(None, "W")
    """Current average consumption"""

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
            if "distanceToEmptyOnBatteryOnly" in evStatus:
                retval["remaining_range"] = ValueWithUnit(int(evStatus["distanceToEmptyOnBatteryOnly"]), "km")
            if "distanceToEmptyOnBattery100Soc" in evStatus:
                retval["remaining_range_at_full_charge"] = ValueWithUnit(
                    int(evStatus["distanceToEmptyOnBattery100Soc"]), "km"
                )
            if "chargeLevel" in evStatus:
                retval["remaining_battery_percent"] = ValueWithUnit(int(evStatus["chargeLevel"]), "%")
            if "chargerState" in evStatus:
                status = int(evStatus["chargerState"])
                retval["charging_status"] = ChargingState[status] if status < len(ChargingState) else "UNKNOWN"
                retval["charging_status_raw"] = int(evStatus["chargerState"])
                retval["is_charger_connected"] = (
                    retval["charging_status"] == "PLUGGED_IN"
                    or retval["charging_status"] == "CHARGING"
                    or retval["charging_status"] == "DC_CHARGING"
                    or retval["charging_status"] == "COMPLETE"
                )
            if "statusOfChargerConnection" in evStatus:
                retval["charger_connection_status"] = int(evStatus["statusOfChargerConnection"])

            if "dcChargeIAct" in evStatus and retval["charging_status"] == "DC_CHARGING":
                retval["charging_voltage"] = ValueWithUnit(
                    DcChargingVoltLevels[retval["remaining_battery_percent"].value], "V"
                )
                retval["charging_current"] = ValueWithUnit(abs(float(evStatus["dcChargeIAct"])), "A")
            elif "chargeUAct" in evStatus and "chargeIAct" in evStatus:
                retval["charging_voltage"] = ValueWithUnit(float(evStatus["chargeUAct"]), "V")
                retval["charging_current"] = ValueWithUnit(float(evStatus["chargeIAct"]), "A")

            if "chargeIAct" in evStatus and "chargeUAct" in evStatus:
                retval["charging_power"] = ValueWithUnit(
                    float(evStatus["chargeUAct"]) * float(evStatus["chargeIAct"])
                    if retval["charging_voltage"].value < 260
                    else float(evStatus["chargeUAct"]) * float(evStatus["chargeIAct"]) * math.sqrt(3),
                    "W",
                )

            if "timeToFullyCharged" in evStatus:
                retval["charging_time_remaining"] = (
                    ValueWithUnit(int(evStatus["timeToFullyCharged"]), "min")
                    if evStatus["timeToFullyCharged"] != "2047"
                    else None
                )

            if "averPowerConsumption" in evStatus:
                retval["average_power_consumption"] = ValueWithUnit(float(evStatus["averPowerConsumption"]), "W")
            if "vehicleStatus" in vehicle_data and "updateTime" in vehicle_data["vehicleStatus"]:
                retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
            if "soc" in vehicle_data:
                retval["charging_target_soc"] = ValueWithUnit(float(vehicle_data["soc"]) / 10, "%")
        except KeyError as e:
            _LOGGER.debug(f"Battery info not available: {e}")
        except Exception as e:
            _LOGGER.error(f"Error parsing battery data: {e}")
        finally:
            return retval
