"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class Running(VehicleDataBase):
    """Provides an accessible version of the vehicle's running data."""

    ahbc_status: int | None = None
    """Adaptive high beam control status."""

    goodbye: int | None = None
    """Goodbye Light."""

    home_safe: int | None = None
    """Home Safe Light."""

    corner_light: int | None = None
    """Corner light."""

    front_fog_light: int | None = None
    """Front Fog light."""

    stop_light: int | None = None
    """Stop light."""

    trip_meter1: ValueWithUnit | None = ValueWithUnit(None, None)
    """Trip meter 1."""

    trip_meter2: ValueWithUnit | None = ValueWithUnit(None, None)
    """Trip meter 2."""

    approach: int | None = None
    """Approach light."""

    high_beam: int | None = None
    """High beam light."""

    engine_coolant_level_status: int | None = None
    """Engine coolant level status."""

    low_beam: int | None = None
    """Low beam light."""

    position_light_rear: int | None = None
    """Position light rear."""

    light_show: int | None = None
    """Light show."""

    welcome: int | None = None
    """Welcome light."""

    drl: int | None = None
    """Daytime running light."""

    ahl: int | None = None
    """Adaptive headlight."""

    trun_indicator_left: int | None = None
    """Turn indicator left."""

    trun_indicator_right: int | None = None
    """Turn indicator right."""

    adaptive_front_light: int | None = None
    """Adaptive front lighting system."""

    dbl: int | None = None
    """Double light."""

    average_speed: ValueWithUnit | None = ValueWithUnit(None, None)
    """Average speed."""

    position_light_front: int | None = None
    """Position light front."""

    reverse_light: int | None = None
    """Reverse light."""

    highway_light: int | None = None
    """Highway light."""

    rear_fog_light: int | None = None
    """Rear fog light."""

    flash_light: int | None = None
    """Flash light."""

    all_weather_light: int | None = None
    """All weather light."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> dict | None:
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
            _LOGGER.info("Running info not available: %s", e)
        return retval
