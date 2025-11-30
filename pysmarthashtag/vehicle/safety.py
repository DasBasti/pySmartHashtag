"""Safety models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import VehicleDataBase, get_field_as_type

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

    vehicle_alarm: Optional[dict] = None
    """The state of the vehicle alarm."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the safety data based on Ids."""
        _LOGGER.debug("Parsing safety data")
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["drivingSafetyStatus"]

            retval["central_locking_status"] = get_field_as_type(evStatus, "centralLockingStatus", int)
            retval["door_lock_status_driver"] = get_field_as_type(evStatus, "doorLockStatusDriver", int)
            retval["door_lock_status_driver_rear"] = get_field_as_type(evStatus, "doorLockStatusDriverRear", int)
            retval["door_lock_status_passenger"] = get_field_as_type(evStatus, "doorLockStatusPassenger", int)
            retval["door_lock_status_passenger_rear"] = get_field_as_type(evStatus, "doorLockStatusPassengerRear", int)
            retval["door_open_status_driver"] = get_field_as_type(evStatus, "doorOpenStatusDriver", int)
            retval["door_open_status_driver_rear"] = get_field_as_type(evStatus, "doorOpenStatusDriverRear", int)
            retval["door_open_status_passenger"] = get_field_as_type(evStatus, "doorOpenStatusPassenger", int)
            retval["door_open_status_passenger_rear"] = get_field_as_type(evStatus, "doorOpenStatusPassengerRear", int)
            retval["door_pos_driver"] = get_field_as_type(evStatus, "doorPosDriver", int)
            retval["door_pos_driver_rear"] = get_field_as_type(evStatus, "doorPosDriverRear", int)
            retval["door_pos_passenger"] = get_field_as_type(evStatus, "doorPosPassenger", int)
            retval["door_pos_passenger_rear"] = get_field_as_type(evStatus, "doorPosPassengerRear", int)
            retval["electric_park_brake_status"] = get_field_as_type(evStatus, "electricParkBrakeStatus", int)
            retval["engine_hood_open_status"] = get_field_as_type(evStatus, "engineHoodOpenStatus", int)
            retval["seat_belt_status_driver"] = get_field_as_type(evStatus, "seatBeltStatusDriver", bool)
            retval["seat_belt_status_driver_rear"] = get_field_as_type(evStatus, "seatBeltStatusDriverRear", bool)
            retval["seat_belt_status_mid_rear"] = get_field_as_type(evStatus, "seatBeltStatusMidRear", bool)
            retval["seat_belt_status_passenger"] = get_field_as_type(evStatus, "seatBeltStatusPassenger", bool)
            retval["seat_belt_status_passenger_rear"] = get_field_as_type(evStatus, "seatBeltStatusPassengerRear", bool)
            retval["seat_belt_status_th_driver_rear"] = get_field_as_type(evStatus, "seatBeltStatusThDriverRear", bool)
            retval["seat_belt_status_th_passenger_rear"] = get_field_as_type(
                evStatus, "seatBeltStatusThPassengerRear", bool
            )
            retval["srs_crash_status"] = get_field_as_type(evStatus, "srsCrashStatus", int)
            retval["tank_flap_status"] = get_field_as_type(evStatus, "tankFlapStatus", int)
            retval["trunk_lock_status"] = get_field_as_type(evStatus, "trunkLockStatus", int)
            retval["trunk_open_status"] = get_field_as_type(evStatus, "trunkOpenStatus", int)
            retval["vehicle_alarm"] = evStatus.get("vehicleAlarm")

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.error(f"Safety info not available: {e}")
        finally:
            return retval
