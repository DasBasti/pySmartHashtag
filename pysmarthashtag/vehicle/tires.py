"""Tire models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)

"""Charging state of electric vehicle."""


class TireLocation(Enum):
    """Enumeration of tire locations."""

    DRIVER = 0
    DRIVER_REAR = 1
    PASSANGER = 2
    PASSENAGER_REAR = 3


@dataclass
class Tires(VehicleDataBase):
    """Provides an accessible version of the vehicle's battery data."""

    temperature: Optional[list[ValueWithUnit]] = None
    """Temperature of the tires."""

    temperature_warning: Optional[list[bool]] = None
    """Temperature warning of the tires."""

    temperature_pre_warning: Optional[list[bool]] = None
    """Temperature pre warning of the tires."""

    tire_pressure: Optional[list[ValueWithUnit]] = None
    """Temperature status of the tires."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the tire data based on Ids."""
        _LOGGER.debug("Parsing tire data")
        retval: dict[str, Any] = {}
        try:
            maintenance_status = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["maintenanceStatus"]

            # Parse temperature values
            temp_driver = get_field_as_type(maintenance_status, "tyreTempDriver", float)
            temp_driver_rear = get_field_as_type(maintenance_status, "tyreTempDriverRear", float)
            temp_passenger = get_field_as_type(maintenance_status, "tyreTempPassenger", float)
            temp_passenger_rear = get_field_as_type(maintenance_status, "tyreTempPassengerRear", float)

            retval["temperature"] = [
                ValueWithUnit(temp_driver, "C") if temp_driver is not None else ValueWithUnit(None, "C"),
                ValueWithUnit(temp_driver_rear, "C") if temp_driver_rear is not None else ValueWithUnit(None, "C"),
                ValueWithUnit(temp_passenger, "C") if temp_passenger is not None else ValueWithUnit(None, "C"),
                ValueWithUnit(temp_passenger_rear, "C")
                if temp_passenger_rear is not None
                else ValueWithUnit(None, "C"),
            ]

            # Parse pre-warning values
            retval["temperature_pre_warning"] = [
                get_field_as_type(maintenance_status, "tyrePreWarningDriver", bool),
                get_field_as_type(maintenance_status, "tyrePreWarningDriverRear", bool),
                get_field_as_type(maintenance_status, "tyrePreWarningPassenger", bool),
                get_field_as_type(maintenance_status, "tyrePreWarningPassengerRear", bool),
            ]

            # Parse tire pressure values
            pressure_driver = get_field_as_type(maintenance_status, "tyreStatusDriver", float)
            pressure_driver_rear = get_field_as_type(maintenance_status, "tyreStatusDriverRear", float)
            pressure_passenger = get_field_as_type(maintenance_status, "tyreStatusPassenger", float)
            pressure_passenger_rear = get_field_as_type(maintenance_status, "tyreStatusPassengerRear", float)

            retval["tire_pressure"] = [
                ValueWithUnit(pressure_driver, "kPa") if pressure_driver is not None else ValueWithUnit(None, "kPa"),
                ValueWithUnit(pressure_driver_rear, "kPa")
                if pressure_driver_rear is not None
                else ValueWithUnit(None, "kPa"),
                ValueWithUnit(pressure_passenger, "kPa")
                if pressure_passenger is not None
                else ValueWithUnit(None, "kPa"),
                ValueWithUnit(pressure_passenger_rear, "kPa")
                if pressure_passenger_rear is not None
                else ValueWithUnit(None, "kPa"),
            ]

            # Parse temperature warning values
            retval["temperature_warning"] = [
                get_field_as_type(maintenance_status, "tyreTempWarningDriver", bool),
                get_field_as_type(maintenance_status, "tyreTempWarningDriverRear", bool),
                get_field_as_type(maintenance_status, "tyreTempWarningPassenger", bool),
                get_field_as_type(maintenance_status, "tyreTempWarningPassengerRear", bool),
            ]

        except KeyError as e:
            _LOGGER.info(f"Tire info not available: {e}")
        finally:
            return retval
