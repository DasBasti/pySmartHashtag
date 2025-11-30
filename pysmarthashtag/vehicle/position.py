"""Position models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_element_from_dict_maybe, get_field_as_type

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
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the position data based on Ids."""
        _LOGGER.debug("Parsing position data")
        retval: dict[str, Any] = {}
        position = get_element_from_dict_maybe(vehicle_data, "vehicleStatus", "basicVehicleStatus", "position")
        if position is None:
            _LOGGER.error("Position data not available in vehicle data")
            return retval
        try:
            altitude = get_field_as_type(position, "altitude", int)
            retval["altitude"] = ValueWithUnit(altitude, "m") if altitude is not None else None
            retval["latitude"] = get_field_as_type(position, "latitude", int)
            retval["longitude"] = get_field_as_type(position, "longitude", int)
            retval["position_can_be_trusted"] = get_field_as_type(position, "posCanBeTrusted", bool)

        except KeyError as e:
            _LOGGER.error(f"Position info not available: {e}")
        finally:
            return retval
