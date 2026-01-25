"""Trailer status models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class Trailer(VehicleDataBase):
    """Provides an accessible version of the vehicle's trailer status data.

    This includes all trailer lamp status information from the trailerStatus
    section of the API response.
    """

    turning_lamp_status: Optional[int] = None
    """Trailer turning lamp status. 0=off."""

    fog_lamp_status: Optional[int] = None
    """Trailer fog lamp status. 0=off."""

    brake_lamp_status: Optional[int] = None
    """Trailer brake lamp status. 0=off."""

    reversing_lamp_status: Optional[int] = None
    """Trailer reversing lamp status. 0=off."""

    position_lamp_status: Optional[int] = None
    """Trailer position lamp status. 0=off."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the trailer status data based on the vehicle data dict."""
        _LOGGER.debug("Parsing trailer status data")
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: dict[str, Any] = {}
        try:
            trailer_status = vehicle_data["vehicleStatus"]["additionalVehicleStatus"].get("trailerStatus", {})
            if not trailer_status:
                return None

            retval["turning_lamp_status"] = get_field_as_type(trailer_status, "trailerTurningLampSts", int)
            retval["fog_lamp_status"] = get_field_as_type(trailer_status, "trailerFogLampSts", int)
            retval["brake_lamp_status"] = get_field_as_type(trailer_status, "trailerBreakLampSts", int)
            retval["reversing_lamp_status"] = get_field_as_type(trailer_status, "trailerReversingLampSts", int)
            retval["position_lamp_status"] = get_field_as_type(trailer_status, "trailerPosLampSts", int)

            # Timestamp
            if "updateTime" in vehicle_data["vehicleStatus"]:
                retval["timestamp"] = datetime.fromtimestamp(
                    int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000
                )

        except KeyError as e:
            _LOGGER.info(f"Trailer status info not available: {e}")
        finally:
            return retval
