"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pysmarthashtag.models import StrEnum, ValueWithUnit, VehicleDataBase

_LOGGER = logging.getLogger(__name__)

class ChargingState(StrEnum):
    """Charging state of electric vehicle."""

    DEFAULT = "DEFAULT"
    CHARGING = "CHARGING"
    ERROR = "ERROR"
    COMPLETE = "COMPLETE"
    FULLY_CHARGED = "FULLY_CHARGED"
    FINISHED_FULLY_CHARGED = "FINISHED_FULLY_CHARGED"
    FINISHED_NOT_FULL = "FINISHED_NOT_FULL"
    INVALID = "INVALID"
    NOT_CHARGING = "NOT_CHARGING"
    PLUGGED_IN = "PLUGGED_IN"
    WAITING_FOR_CHARGING = "WAITING_FOR_CHARGING"
    TARGET_REACHED = "TARGET_REACHED"
    UNKNOWN = "UNKNOWN"

@dataclass
class Battery(VehicleDataBase):
    """Provides an accessible version of the vehicle's battery data."""

    remaining_range: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining range of the vehicle."""

    remaining_battery_percent: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining battery percent of the vehicle."""

    charging_status: Optional[ChargingState] = None
    """Charging status of the vehicle."""

    is_charger_connected: bool = False
    """Is the charger connected to the vehicle."""

    charging_target_soc: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging target state of charge."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: Dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None
    
    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: Dict) -> Optional[Dict]:
        """Parse the battery data based on Ids."""
        retval: Dict[str, Any] = {}
        _LOGGER.debug("Parsing battery data: {}".format(vehicle_data))
        raise NotImplementedError()