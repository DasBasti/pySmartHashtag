"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase

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
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["runningStatus"]
            _LOGGER.debug(f"Parsing running data: {evStatus}")
            retval["ahbc_status"] = int(evStatus.get("ahbc"))
            retval["goodbye"] = int(evStatus.get("goodbye"))
            retval["home_safe"] = int(evStatus.get("homeSafe"))
            retval["corner_light"] = int(evStatus.get("cornrgLi"))
            retval["front_fog_light"] = int(evStatus.get("frntFog"))
            retval["stop_light"] = int(evStatus.get("stopLi"))
            retval["trip_meter1"] = ValueWithUnit(float(evStatus.get("tripMeter1")), "km")
            retval["trip_meter2"] = ValueWithUnit(float(evStatus.get("tripMeter2")), "km")
            retval["approach"] = int(evStatus.get("approach"))
            retval["high_beam"] = int(evStatus.get("hiBeam"))
            retval["engine_coolant_level_status"] = int(evStatus.get("engineCoolantLevelStatus"))
            retval["low_beam"] = int(evStatus.get("loBeam"))
            retval["position_light_rear"] = int(evStatus.get("posLiRe"))
            retval["light_show"] = int(evStatus.get("ltgShow"))
            retval["welcome"] = int(evStatus.get("welcome"))
            retval["drl"] = int(evStatus.get("drl"))
            retval["ahl"] = int(evStatus.get("ahl"))
            retval["trun_indicator_left"] = int(evStatus.get("trunIndrLe"))
            retval["trun_indicator_right"] = int(evStatus.get("trunIndrRi"))
            retval["adaptive_front_light"] = int(evStatus.get("afs"))
            retval["dbl"] = int(evStatus.get("dbl"))
            retval["average_speed"] = ValueWithUnit(float(evStatus.get("avgSpeed")), "km/h")
            retval["position_light_front"] = int(evStatus.get("posLiFrnt"))
            retval["reverse_light"] = int(evStatus.get("reverseLi"))
            retval["highway_light"] = int(evStatus.get("hwl"))
            retval["rear_fog_light"] = int(evStatus.get("reFog"))
            retval["flash_light"] = int(evStatus.get("flash"))
            retval["all_weather_light"] = int(evStatus.get("allwl"))

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.warning(f"Running info not available: {e}")
        finally:
            return retval
