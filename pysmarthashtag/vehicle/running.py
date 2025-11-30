"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class Running(VehicleDataBase):
    """Provides an accessible version of the vehicle's running data."""

    ahbc_status: Optional[int] = None
    """Adaptive high beam control status."""

    goodbye: Optional[int] = None
    """Goodbye Light."""

    home_safe: Optional[int] = None
    """Home Safe Light."""

    corner_light: Optional[int] = None
    """Corner light."""

    front_fog_light: Optional[int] = None
    """Front Fog light."""

    stop_light: Optional[int] = None
    """Stop light."""

    trip_meter1: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Trip meter 1."""

    trip_meter2: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Trip meter 2."""

    approach: Optional[int] = None
    """Approach light."""

    high_beam: Optional[int] = None
    """High beam light."""

    engine_coolant_level_status: Optional[int] = None
    """Engine coolant level status."""

    low_beam: Optional[int] = None
    """Low beam light."""

    position_light_rear: Optional[int] = None
    """Position light rear."""

    light_show: Optional[int] = None
    """Light show."""

    welcome: Optional[int] = None
    """Welcome light."""

    drl: Optional[int] = None
    """Daytime running light."""

    ahl: Optional[int] = None
    """Adaptive headlight."""

    trun_indicator_left: Optional[int] = None
    """Turn indicator left."""

    trun_indicator_right: Optional[int] = None
    """Turn indicator right."""

    adaptive_front_light: Optional[int] = None
    """Adaptive front lighting system."""

    dbl: Optional[int] = None
    """Double light."""

    average_speed: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Average speed."""

    position_light_front: Optional[int] = None
    """Position light front."""

    reverse_light: Optional[int] = None
    """Reverse light."""

    highway_light: Optional[int] = None
    """Highway light."""

    rear_fog_light: Optional[int] = None
    """Rear fog light."""

    flash_light: Optional[int] = None
    """Flash light."""

    all_weather_light: Optional[int] = None
    """All weather light."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the running data based on Ids."""
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["runningStatus"]
            _LOGGER.debug("Parsing running data")
            retval["ahbc_status"] = get_field_as_type(evStatus, "ahbc", int)
            retval["goodbye"] = get_field_as_type(evStatus, "goodbye", int)
            retval["home_safe"] = get_field_as_type(evStatus, "homeSafe", int)
            retval["corner_light"] = get_field_as_type(evStatus, "cornrgLi", int)
            retval["front_fog_light"] = get_field_as_type(evStatus, "frntFog", int)
            retval["stop_light"] = get_field_as_type(evStatus, "stopLi", int)
            trip_meter1 = get_field_as_type(evStatus, "tripMeter1", float)
            retval["trip_meter1"] = ValueWithUnit(trip_meter1, "km") if trip_meter1 is not None else None
            trip_meter2 = get_field_as_type(evStatus, "tripMeter2", float)
            retval["trip_meter2"] = ValueWithUnit(trip_meter2, "km") if trip_meter2 is not None else None
            retval["approach"] = get_field_as_type(evStatus, "approach", int)
            retval["high_beam"] = get_field_as_type(evStatus, "hiBeam", int)
            retval["engine_coolant_level_status"] = get_field_as_type(evStatus, "engineCoolantLevelStatus", int)
            retval["low_beam"] = get_field_as_type(evStatus, "loBeam", int)
            retval["position_light_rear"] = get_field_as_type(evStatus, "posLiRe", int)
            retval["light_show"] = get_field_as_type(evStatus, "ltgShow", int)
            retval["welcome"] = get_field_as_type(evStatus, "welcome", int)
            retval["drl"] = get_field_as_type(evStatus, "drl", int)
            retval["ahl"] = get_field_as_type(evStatus, "ahl", int)
            retval["trun_indicator_left"] = get_field_as_type(evStatus, "trunIndrLe", int)
            retval["trun_indicator_right"] = get_field_as_type(evStatus, "trunIndrRi", int)
            retval["adaptive_front_light"] = get_field_as_type(evStatus, "afs", int)
            retval["dbl"] = get_field_as_type(evStatus, "dbl", int)
            avg_speed = get_field_as_type(evStatus, "avgSpeed", float)
            retval["average_speed"] = ValueWithUnit(avg_speed, "km/h") if avg_speed is not None else None
            retval["position_light_front"] = get_field_as_type(evStatus, "posLiFrnt", int)
            retval["reverse_light"] = get_field_as_type(evStatus, "reverseLi", int)
            retval["highway_light"] = get_field_as_type(evStatus, "hwl", int)
            retval["rear_fog_light"] = get_field_as_type(evStatus, "reFog", int)
            retval["flash_light"] = get_field_as_type(evStatus, "flash", int)
            retval["all_weather_light"] = get_field_as_type(evStatus, "allwl", int)

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.error(f"Running info not available: {e}")
        finally:
            return retval
