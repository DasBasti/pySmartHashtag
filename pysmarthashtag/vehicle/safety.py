"""Safety models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pysmarthashtag.models import VehicleDataBase

_LOGGER = logging.getLogger(__name__)


@dataclass
class Safety(VehicleDataBase):
    """Provides an accessible version of the vehicle's safety data."""

    central_locking_status: Optional[int] = None
    """The state of the central locking."""

    door_lock_status_driver: Optional[int] = None
    """The state of the driver's door lock."""

    door_lock_status_driver_rear: Optional[int] = None
    """The state of the driver's rear door lock."""

    door_lock_status_passenger: Optional[int] = None
    """The state of the passenger's door lock."""

    door_lock_status_passenger_rear: Optional[int] = None
    """The state of the passenger's rear door lock."""

    door_open_status_driver: Optional[int] = None
    """The state of the driver's door."""

    door_open_status_driver_rear: Optional[int] = None
    """The state of the driver's rear door."""

    door_open_status_passenger: Optional[int] = None
    """The state of the passenger's door."""

    door_open_status_passenger_rear: Optional[int] = None
    """The state of the passenger's rear door."""

    door_pos_driver: Optional[int] = None
    """The position of the driver's door."""

    door_pos_driver_rear: Optional[int] = None
    """The position of the driver's rear door."""

    door_pos_passenger: Optional[int] = None
    """The position of the passenger's door."""

    door_pos_passenger_rear: Optional[int] = None
    """The position of the passenger's rear door."""

    electric_park_brake_status: Optional[int] = None
    """The state of the electric park brake."""

    engine_hood_open_status: Optional[int] = None
    """The state of the engine hood."""

    seat_belt_status_driver: Optional[bool] = None
    """The state of the driver's seat belt."""

    seat_belt_status_driver_rear: Optional[bool] = None
    """The state of the driver's rear seat belt."""

    seat_belt_status_mid_rear: Optional[bool] = None
    """The state of the middle rear seat belt."""

    seat_belt_status_passenger: Optional[bool] = None
    """The state of the passenger's seat belt."""

    seat_belt_status_passenger_rear: Optional[bool] = None
    """The state of the passenger's rear seat belt."""

    seat_belt_status_th_driver_rear: Optional[bool] = None
    """The state of the driver's rear seat belt."""

    seat_belt_status_th_passenger_rear: Optional[bool] = None
    """The state of the passenger's rear seat belt."""

    srs_crash_status: Optional[int] = None
    """The state of the SRS crash."""

    tank_flap_status: Optional[int] = None
    """The state of the tank flap."""

    trunk_lock_status: Optional[int] = None
    """The state of the trunk lock."""

    trunk_open_status: Optional[int] = None
    """The state of the trunk."""

    vehicle_alarm: Optional[Dict] = None
    """The state of the vehicle alarm."""

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
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: Dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["drivingSafetyStatus"]

            retval["central_locking_status"] = int(evStatus.get("centralLockingStatus"))
            retval["door_lock_status_driver"] = int(evStatus.get("doorLockStatusDriver"))
            retval["door_lock_status_driver_rear"] = int(evStatus.get("doorLockStatusDriverRear"))
            retval["door_lock_status_passenger"] = int(evStatus.get("doorLockStatusPassenger"))
            retval["door_lock_status_passenger_rear"] = int(evStatus.get("doorLockStatusPassengerRear"))
            retval["door_open_status_driver"] = int(evStatus.get("doorOpenStatusDriver"))
            retval["door_open_status_driver_rear"] = int(evStatus.get("doorOpenStatusDriverRear"))
            retval["door_open_status_passenger"] = int(evStatus.get("doorOpenStatusPassenger"))
            retval["door_open_status_passenger_rear"] = int(evStatus.get("doorOpenStatusPassengerRear"))
            retval["door_pos_driver"] = int(evStatus.get("doorPosDriver"))
            retval["door_pos_driver_rear"] = int(evStatus.get("doorPosDriverRear"))
            retval["door_pos_passenger"] = int(evStatus.get("doorPosPassenger"))
            retval["door_pos_passenger_rear"] = int(evStatus.get("doorPosPassengerRear"))
            retval["electric_park_brake_status"] = int(evStatus.get("electricParkBrakeStatus"))
            retval["engine_hood_open_status"] = int(evStatus.get("engineHoodOpenStatus"))
            retval["seat_belt_status_driver"] = bool(evStatus.get("seatBeltStatusDriver"))
            retval["seat_belt_status_driver_rear"] = bool(evStatus.get("seatBeltStatusDriverRear"))
            retval["seat_belt_status_mid_rear"] = bool(evStatus.get("seatBeltStatusMidRear"))
            retval["seat_belt_status_passenger"] = bool(evStatus.get("seatBeltStatusPassenger"))
            retval["seat_belt_status_passenger_rear"] = bool(evStatus.get("seatBeltStatusPassengerRear"))
            retval["seat_belt_status_th_driver_rear"] = bool(evStatus.get("seatBeltStatusThDriverRear"))
            retval["seat_belt_status_th_passenger_rear"] = bool(evStatus.get("seatBeltStatusThPassengerRear"))
            retval["srs_crash_status"] = int(evStatus.get("srsCrashStatus"))
            retval["tank_flap_status"] = int(evStatus.get("tankFlapStatus"))
            retval["trunk_lock_status"] = int(evStatus.get("trunkLockStatus"))
            retval["trunk_open_status"] = int(evStatus.get("trunkOpenStatus"))
            retval["vehicle_alarm"] = evStatus.get("vehicleAlarm")

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.warning(f"Safety info not available: {e}")
        finally:
            return retval
