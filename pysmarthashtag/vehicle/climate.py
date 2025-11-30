"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

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
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the climate data based on Ids."""
        _LOGGER.debug("Parsing climate data")
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["climateStatus"]

            retval["air_blower_active"] = get_field_as_type(evStatus, "airBlowerActive", bool)
            retval["cds_climate_active"] = get_field_as_type(evStatus, "cdsClimateActive", bool)
            retval["climate_over_heat_protection_active"] = get_field_as_type(
                evStatus, "climateOverHeatProActive", bool
            )
            retval["curtain_open_status"] = get_field_as_type(evStatus, "curtainOpenStatus", bool)
            retval["curtain_position"] = get_field_as_type(evStatus, "curtainPos", int)
            retval["defrosting_active"] = get_field_as_type(evStatus, "defrost", bool)
            retval["driver_heating_detail"] = get_field_as_type(evStatus, "drvHeatDetail", int)
            retval["driver_heating_status"] = get_field_as_type(evStatus, "drvHeatSts", bool)
            retval["driver_ventilation_detail"] = get_field_as_type(evStatus, "drvVentDetail", int)
            retval["driver_ventilation_status"] = get_field_as_type(evStatus, "drvVentSts", bool)
            exterior_temp = get_field_as_type(evStatus, "exteriorTemp", float)
            retval["exterior_temperature"] = ValueWithUnit(exterior_temp, "°C") if exterior_temp is not None else None
            retval["frag_active"] = evStatus.get("fragActive")
            interior_temp = get_field_as_type(evStatus, "interiorTemp", float)
            retval["interior_temperature"] = ValueWithUnit(interior_temp, "°C") if interior_temp is not None else None
            retval["passenger_heating_detail"] = get_field_as_type(evStatus, "passHeatingDetail", int)
            retval["passenger_heating_status"] = get_field_as_type(evStatus, "passHeatingSts", bool)
            retval["passenger_ventilation_detail"] = get_field_as_type(evStatus, "passVentDetail", int)
            retval["passenger_ventilation_status"] = get_field_as_type(evStatus, "passVentSts", bool)
            retval["pre_climate_active"] = evStatus.get("preClimateActive")
            retval["rear_left_heating_detail"] = get_field_as_type(evStatus, "rlHeatingDetail", int)
            retval["rear_left_heating_status"] = get_field_as_type(evStatus, "rlHeatingSts", bool)
            retval["rear_left_ventilation_detail"] = get_field_as_type(evStatus, "rlVentDetail", int)
            retval["rear_left_ventilation_status"] = get_field_as_type(evStatus, "rlVentSts", bool)
            retval["rear_right_heating_detail"] = get_field_as_type(evStatus, "rrHeatingDetail", int)
            retval["rear_right_heating_status"] = get_field_as_type(evStatus, "rrHeatingSts", bool)
            retval["rear_right_ventilation_detail"] = get_field_as_type(evStatus, "rrVentDetail", int)
            retval["rear_right_ventilation_status"] = get_field_as_type(evStatus, "rrVentSts", bool)
            retval["steering_wheel_heating_status"] = get_field_as_type(evStatus, "steerWhlHeatingSts", bool)
            retval["sun_curtain_rear_open_status"] = get_field_as_type(evStatus, "sunCurtainRearOpenStatus", bool)
            retval["sun_curtain_rear_position"] = get_field_as_type(evStatus, "sunCurtainRearPos", int)
            retval["sunroof_open_status"] = get_field_as_type(evStatus, "sunroofOpenStatus", bool)
            retval["sunroof_position"] = get_field_as_type(evStatus, "sunroofPos", int)
            retval["window_driver_position"] = get_field_as_type(evStatus, "winPosDriver", int)
            retval["window_driver_rear_position"] = get_field_as_type(evStatus, "winPosDriverRear", int)
            retval["window_passenger_position"] = get_field_as_type(evStatus, "winPosPassenger", int)
            retval["window_passenger_rear_position"] = get_field_as_type(evStatus, "winPosPassengerRear", int)
            retval["window_driver_status"] = get_field_as_type(evStatus, "winStatusDriver", int)
            retval["window_driver_rear_status"] = get_field_as_type(evStatus, "winStatusDriverRear", int)
            retval["window_passenger_status"] = get_field_as_type(evStatus, "winStatusPassenger", int)
            retval["window_passenger_rear_status"] = get_field_as_type(evStatus, "winStatusPassengerRear", int)

            pollutionStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"].get("pollutionStatus")
            if pollutionStatus:
                interior_pm25 = get_field_as_type(pollutionStatus, "interiorPM25", float)
                retval["interior_PM25"] = ValueWithUnit(interior_pm25, "μg/m³") if interior_pm25 is not None else None
                rel_hum = get_field_as_type(pollutionStatus, "relHumSts", float)
                retval["relative_humidity"] = ValueWithUnit(rel_hum, "%") if rel_hum is not None else None

            retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)
        except KeyError as e:
            _LOGGER.info(f"Climate info not available: {e}")
        finally:
            return retval
