"""Battery models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


def _level_active(level: int | None) -> bool | None:
    """Return whether a heating level means the heating is on."""
    if level is None:
        return None
    return level > 0


@dataclass
class Climate(VehicleDataBase):
    """Provides an accessible version of the vehicle's climate data."""

    air_blower_active: bool | None = None
    """The state of the air blower."""

    cds_climate_active: bool | None = None
    """The state of the climate control system."""

    climate_over_heat_protection_active: bool | None = None
    """The state of the climate overheat protection."""

    curtain_open_status: bool | None = None
    """The state of the curtail open status."""

    curtain_position: int | None = None
    """The position of the curtain."""

    defrosting_active: bool | None = None
    """The state of the defrosting."""

    driver_heating_detail: int | None = None
    """The position of the driver's heating."""

    driver_heating_status: bool | None = None
    """The state of the driver's heating."""

    driver_heating_level: int | None = None
    """The heating level of the driver's seat (0 = off, 1-3)."""

    driver_ventilation_detail: int | None = None
    """The position of the driver's ventilation."""

    driver_ventilation_status: bool | None = None
    """The state of the driver's ventilation."""

    exterior_temperature: ValueWithUnit | None = ValueWithUnit(None, None)
    """The exterior temperature."""

    frag_active: bool | None = None
    """The state of the frag."""

    interior_temperature: ValueWithUnit | None = ValueWithUnit(None, None)
    """The interior temperature."""

    passenger_heating_detail: int | None = None
    """The position of the passenger's heating."""

    passenger_heating_status: bool | None = None
    """The state of the passenger's heating."""

    passenger_heating_level: int | None = None
    """The heating level of the passenger's seat (0 = off, 1-3)."""

    passenger_ventilation_detail: int | None = None
    """The position of the passenger's ventilation."""

    passenger_ventilation_status: bool | None = None
    """The state of the passenger's ventilation."""

    pre_climate_active: bool | None = None
    """The state of the pre-climate."""

    rear_left_heating_detail: int | None = None
    """The position of the left rear heating."""

    rear_left_heating_status: bool | None = None
    """The state of the left rear heating."""

    rear_left_heating_level: int | None = None
    """The heating level of the left rear seat (0 = off, 1-3)."""

    rear_left_ventilation_detail: int | None = None
    """The position of the left rear ventilation."""

    rear_left_ventilation_status: bool | None = None
    """The state of the left rear ventilation."""

    rear_right_heating_detail: int | None = None
    """The position of the right rear heating."""

    rear_right_heating_status: bool | None = None
    """The state of the right rear heating."""

    rear_right_heating_level: int | None = None
    """The heating level of the right rear seat (0 = off, 1-3)."""

    rear_right_ventilation_detail: int | None = None
    """The position of the right rear ventilation."""

    rear_right_ventilation_status: bool | None = None
    """The state of the right rear ventilation."""

    steering_wheel_heating_status: bool | None = None
    """The state of the steering wheel heating."""

    sun_curtain_rear_open_status: bool | None = None
    """The state of the rear sun curtain."""

    sun_curtain_rear_position: int | None = None
    """The position of the rear sun curtain."""

    sunroof_open_status: bool | None = None
    """The state of the sunroof."""

    sunroof_position: int | None = None
    """The position of the sunroof."""

    window_driver_position: int | None = None
    """The position of the driver's window."""

    window_driver_rear_position: int | None = None
    """The position of the rear driver's window."""

    window_passenger_position: int | None = None
    """The position of the passenger's window."""

    window_passenger_rear_position: int | None = None
    """The position of the rear passenger's window."""

    window_driver_status: bool | None = None
    """The state of the driver's window."""

    window_driver_rear_status: bool | None = None
    """The state of the rear driver's window."""

    window_passenger_status: bool | None = None
    """The state of the passenger's window."""

    window_passenger_rear_status: bool | None = None
    """The state of the rear passenger's window."""

    interior_PM25: ValueWithUnit | None = ValueWithUnit(None, None)
    """The interior PM2.5 value."""

    relative_humidity: ValueWithUnit | None = ValueWithUnit(None, None)
    """The relative humidity."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> dict | None:
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
            # The status field carries the heating level 0-3, not a boolean
            retval["driver_heating_level"] = get_field_as_type(evStatus, "drvHeatSts", int)
            retval["driver_heating_status"] = _level_active(retval["driver_heating_level"])
            retval["driver_ventilation_detail"] = get_field_as_type(evStatus, "drvVentDetail", int)
            retval["driver_ventilation_status"] = get_field_as_type(evStatus, "drvVentSts", bool)
            exterior_temp = get_field_as_type(evStatus, "exteriorTemp", float)
            retval["exterior_temperature"] = ValueWithUnit(exterior_temp, "°C") if exterior_temp is not None else None
            retval["frag_active"] = evStatus.get("fragActive")
            interior_temp = get_field_as_type(evStatus, "interiorTemp", float)
            retval["interior_temperature"] = ValueWithUnit(interior_temp, "°C") if interior_temp is not None else None
            retval["passenger_heating_detail"] = get_field_as_type(evStatus, "passHeatingDetail", int)
            # The status field carries the heating level 0-3, not a boolean
            retval["passenger_heating_level"] = get_field_as_type(evStatus, "passHeatingSts", int)
            retval["passenger_heating_status"] = _level_active(retval["passenger_heating_level"])
            retval["passenger_ventilation_detail"] = get_field_as_type(evStatus, "passVentDetail", int)
            retval["passenger_ventilation_status"] = get_field_as_type(evStatus, "passVentSts", bool)
            retval["pre_climate_active"] = evStatus.get("preClimateActive")
            retval["rear_left_heating_detail"] = get_field_as_type(evStatus, "rlHeatingDetail", int)
            # The status field carries the heating level 0-3, not a boolean
            retval["rear_left_heating_level"] = get_field_as_type(evStatus, "rlHeatingSts", int)
            retval["rear_left_heating_status"] = _level_active(retval["rear_left_heating_level"])
            retval["rear_left_ventilation_detail"] = get_field_as_type(evStatus, "rlVentDetail", int)
            retval["rear_left_ventilation_status"] = get_field_as_type(evStatus, "rlVentSts", bool)
            retval["rear_right_heating_detail"] = get_field_as_type(evStatus, "rrHeatingDetail", int)
            # The status field carries the heating level 0-3, not a boolean
            retval["rear_right_heating_level"] = get_field_as_type(evStatus, "rrHeatingSts", int)
            retval["rear_right_heating_status"] = _level_active(retval["rear_right_heating_level"])
            retval["rear_right_ventilation_detail"] = get_field_as_type(evStatus, "rrVentDetail", int)
            retval["rear_right_ventilation_status"] = get_field_as_type(evStatus, "rrVentSts", bool)
            # 1 = on, 2 = off
            steering_wheel_heating = get_field_as_type(evStatus, "steerWhlHeatingSts", int)
            retval["steering_wheel_heating_status"] = (
                steering_wheel_heating == 1 if steering_wheel_heating is not None else None
            )
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
        return retval
