"""Position models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_element_from_dict_maybe

_LOGGER = logging.getLogger(__name__)

"""Position of electric vehicle."""


@dataclass
class Position(VehicleDataBase):
    """Provides an accessible version of the vehicle's battery data."""

    altitude: Optional[ValueWithUnit] = None
    """Altitude of the vehicle."""

    latitude: Optional[int] = None
    """Latitude of the vehicle."""

    longitude: Optional[int] = None
    """Longitude of the vehicle."""

    position_can_be_trusted: Optional[bool] = None
    """Position can be trusted."""

    @classmethod
    def from_vehicle_data(self, vehicle_data: Dict):
        """Create a new instance based on data from API."""
        parsed = self._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return self(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(self, vehicle_data: Dict) -> Optional[Dict]:
        """Parse the position data based on Ids."""
        _LOGGER.debug(f"Parsing position data: {vehicle_data}")
        retval: Dict[str, Any] = {}
        position = get_element_from_dict_maybe(vehicle_data, "vehicleStatus", "basicVehicleStatus", "position")
        try:
            retval["altitude"] = ValueWithUnit(int(position["altitude"]), "m")
            retval["latitude"] = int(position["latitude"])
            retval["longitude"] = int(position["longitude"])
            retval["position_can_be_trusted"] = True if position["posCanBeTrusted"] == "true" else False

        except KeyError as e:
            _LOGGER.debug(f"Position info not available: {e}")
        finally:
            return retval
