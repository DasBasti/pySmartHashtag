"""Battery models for pysmarthashtag."""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)

"""Charging state of electric vehicle."""
ChargingState = [
    "NOT_CHARGING",
    "DEFAULT",
    "CHARGING",
    "ERROR",
    "COMPLETE",
    "FULLY_CHARGED",
    "FINISHED_FULLY_CHARGED",
    "FINISHED_NOT_FULL",
    "INVALID",
    "PLUGGED_IN",
    "WAITING_FOR_CHARGING",
    "TARGET_REACHED",
    "UNKNOWN",
    "UNKNOWN",
    "UNKNOWN",
    "DC_CHARGING",
]

DcChargingVoltLevels = [
    370,
    374,
    377,
    381,
    385,
    389,
    392,
    396,
    400,
    403,
    407,
    408,
    408,
    409,
    409,
    410,
    410,
    411,
    411,
    412,
    412,
    413,
    413,
    413,
    413,
    414,
    414,
    415,
    416,
    416,
    416,
    416,
    416,
    416,
    417,
    417,
    415,
    416,
    416,
    416,
    417,
    417,
    417,
    416,
    416,
    417,
    417,
    417,
    416,
    417,
    418,
    418,
    417,
    417,
    418,
    419,
    420,
    419,
    419,
    420,
    422,
    423,
    424,
    425,
    426,
    427,
    428,
    429,
    430,
    431,
    433,
    434,
    435,
    436,
    437,
    437,
    439,
    440,
    441,
    440,
    440,
    441,
    443,
    444,
    445,
    446,
    448,
    449,
    450,
    451,
    453,
    454,
    455,
    456,
    458,
    459,
    460,
    461,
    463,
    464,
    465,
]


@dataclass
class Battery(VehicleDataBase):
    """Provides an accessible version of the vehicle's battery data."""

    remaining_range: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining range of the vehicle."""

    remaining_range_at_full_charge: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining range at full charge of the vehicle."""

    remaining_range_at_20_percent: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining range when battery reaches 20% SoC."""

    remaining_battery_percent: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Remaining battery percent of the vehicle."""

    charging_status: Optional[str] = None
    """Charging status of the vehicle as string."""

    charging_status_raw: Optional[int] = None
    """Charging status of the vehicle."""

    charger_connection_status: Optional[int] = None
    """Charger connection status of the vehicle."""

    is_charger_connected: bool = False
    """Is the charger connected to the vehicle."""

    charging_voltage: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging voltage of the vehicle."""

    charging_current: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging current of the vehicle."""

    charging_power: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging power of the vehicle."""

    charging_time_remaining: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging time remaining of the vehicle."""

    charging_target_soc: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Charging target state of charge."""

    average_power_consumption: Optional[ValueWithUnit] = ValueWithUnit(None, "W")
    """Current average consumption"""

    # V2L (Vehicle-to-Load) discharge data
    v2l_discharge_voltage: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """V2L discharge voltage (disChargeUAct)."""

    v2l_discharge_current: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """V2L discharge current (disChargeIAct)."""

    v2l_discharge_power: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """V2L discharge power (calculated from voltage * current)."""

    v2l_connection_status: Optional[int] = None
    """V2L connection status (disChargeConnectStatus). 0=not connected."""

    v2l_time_remaining: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Time to target discharge (timeToTargetDisCharged). 2047=not discharging."""

    # Charge port status
    charge_lid_ac_status: Optional[int] = None
    """AC charge lid status (chargeLidAcStatus). 2=closed."""

    charge_lid_dc_status: Optional[int] = None
    """DC charge lid status (chargeLidDcAcStatus). 2=closed."""

    # Scheduled charging
    scheduled_charging_status: Optional[int] = None
    """Scheduled/book charging status (bookChargeSts). 0=off."""

    # DC-DC converter status
    dcdc_activated: Optional[int] = None
    """DC-DC converter activated status (dcDcActvd). 0=not active."""

    dcdc_connection_status: Optional[int] = None
    """DC-DC connection status (dcDcConnectStatus). 0=not connected."""

    # Wireless charging
    wireless_charging_alignment: Optional[int] = None
    """Wireless power transfer fine alignment status (wptFineAlignt). 0=not aligned."""

    # Instantaneous power consumption
    instant_power_consumption: Optional[ValueWithUnit] = ValueWithUnit(None, None)
    """Instantaneous power consumption (indPowerConsumption)."""

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
        _LOGGER.debug("Parsing battery data")
        retval: dict[str, Any] = {}
        try:
            evStatus = vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["electricVehicleStatus"]

            # Parse range values
            range_only = get_field_as_type(evStatus, "distanceToEmptyOnBatteryOnly", int, log_missing=False)
            if range_only is not None:
                retval["remaining_range"] = ValueWithUnit(range_only, "km")

            range_100 = get_field_as_type(evStatus, "distanceToEmptyOnBattery100Soc", int, log_missing=False)
            if range_100 is not None:
                retval["remaining_range_at_full_charge"] = ValueWithUnit(range_100, "km")

            charge_level = get_field_as_type(evStatus, "chargeLevel", int, log_missing=False)
            if charge_level is not None:
                retval["remaining_battery_percent"] = ValueWithUnit(charge_level, "%")

            charger_state = get_field_as_type(evStatus, "chargerState", int, log_missing=False)
            if charger_state is not None:
                retval["charging_status"] = (
                    ChargingState[charger_state] if charger_state < len(ChargingState) else "UNKNOWN"
                )
                retval["charging_status_raw"] = charger_state
                retval["is_charger_connected"] = (
                    retval["charging_status"] == "PLUGGED_IN"
                    or retval["charging_status"] == "CHARGING"
                    or retval["charging_status"] == "DC_CHARGING"
                    or retval["charging_status"] == "COMPLETE"
                )

            charger_conn = get_field_as_type(evStatus, "statusOfChargerConnection", int, log_missing=False)
            if charger_conn is not None:
                retval["charger_connection_status"] = charger_conn

            charging_status = retval.get("charging_status")
            battery_percent = retval.get("remaining_battery_percent")

            dc_charge_i = get_field_as_type(evStatus, "dcChargeIAct", float, log_missing=False)
            if dc_charge_i is not None and charging_status == "DC_CHARGING" and battery_percent is not None:
                battery_value = battery_percent.value
                # Ensure battery_value is a valid integer index within DcChargingVoltLevels bounds
                if isinstance(battery_value, (int, float)):
                    battery_value = int(battery_value)
                    # Clamp to valid index range: 0 to len(DcChargingVoltLevels) - 1
                    max_index = len(DcChargingVoltLevels) - 1
                    battery_value = max(0, min(battery_value, max_index))
                    retval["charging_voltage"] = ValueWithUnit(DcChargingVoltLevels[battery_value], "V")
                    retval["charging_current"] = ValueWithUnit(abs(dc_charge_i), "A")
                    retval["charging_power"] = ValueWithUnit(
                        math.floor(abs(dc_charge_i) * DcChargingVoltLevels[battery_value]),
                        "W",
                    )
                else:
                    _LOGGER.error(f"Invalid battery_value type for DC charging lookup: {type(battery_value)}")
            else:
                charge_u = get_field_as_type(evStatus, "chargeUAct", float, log_missing=False)
                charge_i = get_field_as_type(evStatus, "chargeIAct", float, log_missing=False)
                if charge_u is not None and charge_i is not None:
                    retval["charging_voltage"] = ValueWithUnit(charge_u, "V")
                    retval["charging_current"] = ValueWithUnit(charge_i, "A")
                    retval["charging_power"] = ValueWithUnit(
                        charge_u * charge_i if charge_u < 260 else charge_u * charge_i * math.sqrt(3),
                        "W",
                    )

            time_to_charged = get_field_as_type(evStatus, "timeToFullyCharged", int, log_missing=False)
            if time_to_charged is not None and time_to_charged != 2047:
                retval["charging_time_remaining"] = ValueWithUnit(time_to_charged, "min")

            avg_consumption = get_field_as_type(evStatus, "averPowerConsumption", float, log_missing=False)
            if avg_consumption is not None:
                retval["average_power_consumption"] = ValueWithUnit(avg_consumption, "W")

            # Range at 20% SoC
            range_20 = get_field_as_type(evStatus, "distanceToEmptyOnBattery20Soc", int, log_missing=False)
            if range_20 is not None:
                retval["remaining_range_at_20_percent"] = ValueWithUnit(range_20, "km")

            # V2L (Vehicle-to-Load) discharge data
            discharge_u = get_field_as_type(evStatus, "disChargeUAct", float, log_missing=False)
            discharge_i = get_field_as_type(evStatus, "disChargeIAct", float, log_missing=False)
            if discharge_u is not None:
                retval["v2l_discharge_voltage"] = ValueWithUnit(discharge_u, "V")
            if discharge_i is not None:
                retval["v2l_discharge_current"] = ValueWithUnit(discharge_i, "A")
            if discharge_u is not None and discharge_i is not None and discharge_u > 0 and discharge_i > 0:
                retval["v2l_discharge_power"] = ValueWithUnit(discharge_u * discharge_i, "W")

            discharge_conn = get_field_as_type(evStatus, "disChargeConnectStatus", int, log_missing=False)
            if discharge_conn is not None:
                retval["v2l_connection_status"] = discharge_conn

            time_to_discharged = get_field_as_type(evStatus, "timeToTargetDisCharged", int, log_missing=False)
            if time_to_discharged is not None and time_to_discharged != 2047:
                retval["v2l_time_remaining"] = ValueWithUnit(time_to_discharged, "min")

            # Charge lid status
            charge_lid_ac = get_field_as_type(evStatus, "chargeLidAcStatus", int, log_missing=False)
            if charge_lid_ac is not None:
                retval["charge_lid_ac_status"] = charge_lid_ac

            charge_lid_dc = get_field_as_type(evStatus, "chargeLidDcAcStatus", int, log_missing=False)
            if charge_lid_dc is not None:
                retval["charge_lid_dc_status"] = charge_lid_dc

            # Scheduled charging
            book_charge = get_field_as_type(evStatus, "bookChargeSts", int, log_missing=False)
            if book_charge is not None:
                retval["scheduled_charging_status"] = book_charge

            # DC-DC converter status
            dcdc_active = get_field_as_type(evStatus, "dcDcActvd", int, log_missing=False)
            if dcdc_active is not None:
                retval["dcdc_activated"] = dcdc_active

            dcdc_conn = get_field_as_type(evStatus, "dcDcConnectStatus", int, log_missing=False)
            if dcdc_conn is not None:
                retval["dcdc_connection_status"] = dcdc_conn

            # Wireless charging alignment
            wpt_align = get_field_as_type(evStatus, "wptFineAlignt", int, log_missing=False)
            if wpt_align is not None:
                retval["wireless_charging_alignment"] = wpt_align

            # Instantaneous power consumption
            instant_consumption = get_field_as_type(evStatus, "indPowerConsumption", float, log_missing=False)
            if instant_consumption is not None:
                retval["instant_power_consumption"] = ValueWithUnit(instant_consumption, "W")

            if "vehicleStatus" in vehicle_data and "updateTime" in vehicle_data["vehicleStatus"]:
                retval["timestamp"] = datetime.fromtimestamp(int(vehicle_data["vehicleStatus"]["updateTime"]) / 1000)

            soc = get_field_as_type(vehicle_data, "soc", float, log_missing=False)
            if soc is not None:
                retval["charging_target_soc"] = ValueWithUnit(soc / 10, "%")
        except KeyError as e:
            _LOGGER.info(f"Battery info not available: {e}")
        except Exception as e:
            _LOGGER.error(f"Error parsing battery data: {e}")
        finally:
            return retval
