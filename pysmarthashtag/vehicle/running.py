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

    trip_meter1: Optional[float] = None
    """Trip meter 1."""

    trip_meter2: Optional[float] = None
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

    average_speed: Optional[float] = None
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
            retval["ahbc_status"] = evStatus.get("ahbcStatus")
            retval["goodbye"] = evStatus.get("goodbye")
            retval["home_safe"] = evStatus.get("homeSafe")
            retval["corner_light"] = evStatus.get("cornerLight")
            retval["front_fog_light"] = evStatus.get("frontFogLight")
            retval["stop_light"] = evStatus.get("stopLight")
            retval["trip_meter1"] = evStatus.get("tripMeter1")
            retval["trip_meter2"] = evStatus.get("tripMeter2")
            retval["approach"] = evStatus.get("approach")
            retval["high_beam"] = evStatus.get("highBeam")
            retval["engine_coolant_level_status"] = evStatus.get("engineCoolantLevelStatus")
            retval["low_beam"] = evStatus.get("lowBeam")
            retval["position_light_rear"] = evStatus.get("positionLightRear")
            retval["light_show"] = evStatus.get("lightShow")
            retval["welcome"] = evStatus.get("welcome")
            retval["drl"] = evStatus.get("drl")
            retval["ahl"] = evStatus.get("ahl")
            retval["trun_indicator_left"] = evStatus.get("turnIndicatorLeft")
            retval["trun_indicator_right"] = evStatus.get("turnIndicatorRight")
            retval["adaptive_front_light"] = evStatus.get("adaptiveFrontLight")
            retval["dbl"] = evStatus.get("dbl")
            retval["average_speed"] = evStatus.get("averageSpeed")
            retval["position_light_front"] = evStatus.get("positionLightFront")
            retval["reverse_light"] = evStatus.get("reverseLight")
            retval["highway_light"] = evStatus.get("highwayLight")
            retval["rear_fog_light"] = evStatus.get("rearFogLight")
            retval["flash_light"] = evStatus.get("flashLight")
            retval["all_weather_light"] = evStatus.get("allWeatherLight")

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.warning(f"Running info not available: {e}")
        finally:
            return retval
