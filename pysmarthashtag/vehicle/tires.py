"""Tire models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase

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
        """Parse the battery data based on Ids."""
        _LOGGER.debug("Parsing tire data")
        retval: dict[str, Any] = {}
        try:
            maintenance_status = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["maintenanceStatus"]
            retval["temperature"] = [
                ValueWithUnit(float(maintenance_status["tyreTempDriver"]), "C"),
                ValueWithUnit(float(maintenance_status["tyreTempDriverRear"]), "C"),
                ValueWithUnit(float(maintenance_status["tyreTempPassenger"]), "C"),
                ValueWithUnit(float(maintenance_status["tyreTempPassengerRear"]), "C"),
            ]
            retval["temperature_pre_warning"] = [
                maintenance_status["tyrePreWarningDriver"] == "1",
                maintenance_status["tyrePreWarningDriverRear"] == "1",
                maintenance_status["tyrePreWarningPassenger"] == "1",
                maintenance_status["tyrePreWarningPassengerRear"] == "1",
            ]
            retval["tire_pressure"] = [
                ValueWithUnit(float(maintenance_status["tyreStatusDriver"]), "kPa"),
                ValueWithUnit(float(maintenance_status["tyreStatusDriverRear"]), "kPa"),
                ValueWithUnit(float(maintenance_status["tyreStatusPassenger"]), "kPa"),
                ValueWithUnit(float(maintenance_status["tyreStatusPassengerRear"]), "kPa"),
            ]
            retval["temperature_warning"] = [
                maintenance_status["tyreTempWarningDriver"] == "1",
                maintenance_status["tyreTempWarningDriverRear"] == "1",
                maintenance_status["tyreTempWarningPassenger"] == "1",
                maintenance_status["tyreTempWarningPassengerRear"] == "1",
            ]

        except KeyError as e:
            _LOGGER.debug(f"Tire info not available: {e}")
        finally:
            return retval
