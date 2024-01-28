"""Tire models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

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

    temperature: Optional[List[ValueWithUnit]] = None
    """Temperature of the tires."""

    temperature_waring: Optional[List[bool]] = None
    """Temperature warning of the tires."""

    temperature_pre_waring: Optional[List[bool]] = None
    """Temperature pre warning of the tires."""

    temperature_status: Optional[List[ValueWithUnit]] = None
    """Temperature status of the tires."""

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
        retval: Dict[str, Any] = {}
        try:
            tire_status = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]
            retval["temperature"] = [
                ValueWithUnit(float(tire_status["tyreTempDriver"]), "C"),
                ValueWithUnit(float(tire_status["tyreTempDriverRear"]), "C"),
                ValueWithUnit(float(tire_status["tyreTempPassenger"]), "C"),
                ValueWithUnit(float(tire_status["tyreTempPassengerRear"]), "C"),
            ]
            retval["temperature_pre_warning"] = [
                True if tire_status["tyrePreWarningDriver"] == "1" else False,
                True if tire_status["tyrePreWarningDriverRear"] == "1" else False,
                True if tire_status["tyrePreWarningPassenger"] == "1" else False,
                True if tire_status["tyrePreWarningPassengerRear"] == "1" else False,
            ]
            retval["temperature_status"] = [
                ValueWithUnit(float(tire_status["tyreStatusDriver"]), "psi"),
                ValueWithUnit(float(tire_status["tyreStatusDriverRear"]), "psi"),
                ValueWithUnit(float(tire_status["tyreStatusPassenger"]), "psi"),
                ValueWithUnit(float(tire_status["tyreStatusPassengerRear"]), "psi"),
            ]
            maintenance_status = vehicle_data["vehicleStatus"]["additionalVehicleStatus"][",maintenanceStatus"]
            retval["temperature_pre_warning"] = [
                True if maintenance_status["tyreTempWarningDriver"] == "1" else False,
                True if maintenance_status["tyreTempWarningDriverRear"] == "1" else False,
                True if maintenance_status["tyreTempWarningPassenger"] == "1" else False,
                True if maintenance_status["tyreTempWarningPassengerRear"] == "1" else False,
            ]

        except KeyError as e:
            _LOGGER.debug(f"Tire info not available: {e}")
        finally:
            return retval
