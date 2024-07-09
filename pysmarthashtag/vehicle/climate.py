"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase

_LOGGER = logging.getLogger(__name__)


@dataclass
class Climate(VehicleDataBase):
    """Provides an accessible version of the vehicle's climate data."""

    air_blower_active: Optional[bool] = None
    """The state of the air blower."""

    cds_climate_active: Optional[bool] = None
    """The state of the climate control system."""

    climate_over_heat_protection_active: Optional[bool] = None
    """The state of the climate overheat protection."""

    curtain_open_status: Optional[bool] = None
    """The state of the curtail open status."""

    curtain_position: Optional[int] = None
    """The position of the curtain."""

    defrosting_active: Optional[bool] = None
    """The state of the defrosting."""

    driver_heating_detail: Optional[int] = None
    """The position of the driver's heating."""

    driver_heating_status: Optional[bool] = None
    """The state of the driver's heating."""

    driver_ventilation_detail: Optional[int] = None
    """The position of the driver's ventilation."""

    driver_ventilation_status: Optional[bool] = None
    """The state of the driver's ventilation."""

    exterior_temperature: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """The exterior temperature."""

    frag_active: Optional[bool] = None
    """The state of the frag."""

    interior_temperature: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """The interior temperature."""

    passenger_heating_detail: Optional[int] = None
    """The position of the passenger's heating."""

    passenger_heating_status: Optional[bool] = None
    """The state of the passenger's heating."""

    passenger_ventilation_detail: Optional[int] = None
    """The position of the passenger's ventilation."""

    passenger_ventilation_status: Optional[bool] = None
    """The state of the passenger's ventilation."""

    pre_climate_active: Optional[bool] = None
    """The state of the pre-climate."""

    rear_left_heating_detail: Optional[int] = None
    """The position of the left rear heating."""

    rear_left_heating_status: Optional[bool] = None
    """The state of the left rear heating."""

    rear_left_ventilation_detail: Optional[int] = None
    """The position of the left rear ventilation."""

    rear_left_ventilation_status: Optional[bool] = None
    """The state of the left rear ventilation."""

    rear_right_heating_detail: Optional[int] = None
    """The position of the right rear heating."""

    rear_right_heating_status: Optional[bool] = None
    """The state of the right rear heating."""

    rear_right_ventilation_detail: Optional[int] = None
    """The position of the right rear ventilation."""

    rear_right_ventilation_status: Optional[bool] = None
    """The state of the right rear ventilation."""

    steering_wheel_heating_status: Optional[bool] = None
    """The state of the steering wheel heating."""

    sun_curtain_rear_open_status: Optional[bool] = None
    """The state of the rear sun curtain."""

    sun_curtain_rear_position: Optional[int] = None
    """The position of the rear sun curtain."""

    sunroof_open_status: Optional[bool] = None
    """The state of the sunroof."""

    sunroof_position: Optional[int] = None
    """The position of the sunroof."""

    window_driver_position: Optional[int] = None
    """The position of the driver's window."""

    window_driver_rear_position: Optional[int] = None
    """The position of the rear driver's window."""

    window_passenger_position: Optional[int] = None
    """The position of the passenger's window."""

    window_passenger_rear_position: Optional[int] = None
    """The position of the rear passenger's window."""

    window_driver_status: Optional[bool] = None
    """The state of the driver's window."""

    window_driver_rear_status: Optional[bool] = None
    """The state of the rear driver's window."""

    window_passenger_status: Optional[bool] = None
    """The state of the passenger's window."""

    window_passenger_rear_status: Optional[bool] = None
    """The state of the rear passenger's window."""

    interior_PM25: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """The interior PM2.5 value."""

    relative_humidity: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """The relative humidity."""

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
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["climateStatus"]

            retval["air_blower_active"] = True if evStatus["airBlowerActive"] == "true" else False
            retval["cds_climate_active"] = True if evStatus["cdsClimateActive"] == "true" else False
            retval["climate_over_heat_protection_active"] = (
                True if evStatus["climateOverHeatProActive"] == "true" else False
            )
            retval["curtain_open_status"] = True if evStatus["curtainOpenStatus"] == "1" else False
            retval["curtain_position"] = int(evStatus["curtainPos"])
            retval["defrosting_active"] = True if evStatus["defrost"] == "true" else False
            retval["driver_heating_detail"] = int(evStatus["drvHeatDetail"])
            retval["driver_heating_status"] = True if evStatus["drvHeatSts"] == "true" else False
            retval["driver_ventilation_detail"] = int(evStatus["drvVentDetail"])
            retval["driver_ventilation_status"] = True if evStatus["drvVentSts"] == "true" else False
            retval["exterior_temperature"] = ValueWithUnit(float(evStatus["exteriorTemp"]), "°C")
            retval["frag_active"] = evStatus["fragActive"]
            retval["interior_temperature"] = ValueWithUnit(float(evStatus["interiorTemp"]), "°C")
            retval["passenger_heating_detail"] = int(evStatus["passHeatingDetail"])
            retval["passenger_heating_status"] = True if evStatus["passHeatingSts"] == "true" else False
            retval["passenger_ventilation_detail"] = int(evStatus["passVentDetail"])
            retval["passenger_ventilation_status"] = True if evStatus["passVentSts"] == "true" else False
            retval["pre_climate_active"] = evStatus["preClimateActive"]
            retval["rear_left_heating_detail"] = int(evStatus["rlHeatingDetail"])
            retval["rear_left_heating_status"] = True if evStatus["rlHeatingSts"] == "true" else False
            retval["rear_left_ventilation_detail"] = int(evStatus["rlVentDetail"])
            retval["rear_left_ventilation_status"] = True if evStatus["rlVentSts"] == "true" else False
            retval["rear_right_heating_detail"] = int(evStatus["rrHeatingDetail"])
            retval["rear_right_heating_status"] = True if evStatus["rrHeatingSts"] == "true" else False
            retval["rear_right_ventilation_detail"] = int(evStatus["rrVentDetail"])
            retval["rear_right_ventilation_status"] = True if evStatus["rrVentSts"] == "true" else False
            retval["steering_wheel_heating_status"] = True if evStatus["steerWhlHeatingSts"] == "true" else False
            retval["sun_curtain_rear_open_status"] = True if evStatus["sunCurtainRearOpenStatus"] == "true" else False
            retval["sun_curtain_rear_position"] = int(evStatus["sunCurtainRearPos"])
            retval["sunroof_open_status"] = True if evStatus["sunroofOpenStatus"] == "true" else False
            retval["sunroof_position"] = int(evStatus["sunroofPos"])
            retval["window_driver_position"] = int(evStatus["winPosDriver"])
            retval["window_driver_rear_position"] = int(evStatus["winPosDriverRear"])
            retval["window_passenger_position"] = int(evStatus["winPosPassenger"])
            retval["window_passenger_rear_position"] = int(evStatus["winPosPassengerRear"])
            retval["window_driver_status"] = int(evStatus["winStatusDriver"])
            retval["window_driver_rear_status"] = int(evStatus["winStatusDriverRear"])
            retval["window_passenger_status"] = int(evStatus["winStatusPassenger"])
            retval["window_passenger_rear_status"] = int(evStatus["winStatusPassengerRear"])

            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["pollutionStatus"]

            retval["interior_PM25"] = ValueWithUnit(float(evStatus["interiorPM25"]), "μg/m³")
            retval["relative_humidity"] = ValueWithUnit(float(evStatus["relHumSts"]), "%")

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.warning(f"Climate info not available: {e}")
        finally:
            return retval
