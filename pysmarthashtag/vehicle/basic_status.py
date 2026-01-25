"""Basic vehicle status models for pysmarthashtag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pysmarthashtag.models import ValueWithUnit, VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class BasicStatus(VehicleDataBase):
    """Provides an accessible version of the vehicle's basic status data.

    This includes data from basicVehicleStatus, notification, eg (eGuard),
    parkTime, and configuration sections of the API response.
    """

    # Basic vehicle status
    speed: Optional[ValueWithUnit] = None
    """Current vehicle speed."""

    speed_validity: Optional[bool] = None
    """Whether the speed value is valid."""

    direction: Optional[str] = None
    """Vehicle heading direction."""

    engine_status: Optional[str] = None
    """Engine status (e.g., 'engine_off', 'engine_on')."""

    car_mode: Optional[int] = None
    """Car mode. 0=normal."""

    usage_mode: Optional[int] = None
    """Usage mode. 0=normal."""

    car_locator_upload_enabled: Optional[bool] = None
    """Whether car locator status upload is enabled."""

    # Notification (emergency call) status
    emergency_call_status: Optional[int] = None
    """Emergency call notification status. 0=no active call."""

    notification_reason: Optional[int] = None
    """Reason code for notification."""

    notification_time: Optional[datetime] = None
    """Timestamp of the notification."""

    notification_parameters: Optional[str] = None
    """JSON string of notification parameters."""

    # eGuard status
    eguard_running: Optional[bool] = None
    """Whether eGuard is running."""

    eguard_blocked_status: Optional[int] = None
    """eGuard blocked status. 0=not blocked."""

    panic_status: Optional[bool] = None
    """Whether panic mode is active."""

    # Park time
    park_time: Optional[datetime] = None
    """Timestamp when the vehicle was last parked."""

    # Configuration
    propulsion_type: Optional[int] = None
    """Propulsion type. 4=electric."""

    fuel_type: Optional[int] = None
    """Fuel type. 4=electric."""

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the basic status data based on the vehicle data dict."""
        _LOGGER.debug("Parsing basic status data")
        if "vehicleStatus" not in vehicle_data:
            return None
        retval: dict[str, Any] = {}
        try:
            vehicle_status = vehicle_data["vehicleStatus"]

            # Parse basicVehicleStatus
            basic_status = vehicle_status.get("basicVehicleStatus", {})
            if basic_status:
                speed = get_field_as_type(basic_status, "speed", float)
                if speed is not None:
                    retval["speed"] = ValueWithUnit(speed, "km/h")
                retval["speed_validity"] = get_field_as_type(basic_status, "speedValidity", bool)
                retval["direction"] = get_field_as_type(basic_status, "direction", str)
                retval["engine_status"] = get_field_as_type(basic_status, "engineStatus", str)
                retval["car_mode"] = get_field_as_type(basic_status, "carMode", int)
                retval["usage_mode"] = get_field_as_type(basic_status, "usageMode", int)

                # Position info within basicVehicleStatus
                position = basic_status.get("position", {})
                if position:
                    car_locator = get_field_as_type(position, "carLocatorStatUploadEn", bool)
                    retval["car_locator_upload_enabled"] = car_locator

            # Parse notification
            notification = vehicle_status.get("notification", {})
            if notification:
                retval["emergency_call_status"] = get_field_as_type(notification, "notifForEmgyCallStatus", int)
                retval["notification_reason"] = get_field_as_type(notification, "reason", int)
                notif_time = get_field_as_type(notification, "time", int)
                if notif_time is not None:
                    retval["notification_time"] = datetime.fromtimestamp(notif_time)
                retval["notification_parameters"] = get_field_as_type(notification, "parameters", str)

            # Parse eGuard (eg)
            eg = vehicle_status.get("eg", {})
            if eg:
                retval["eguard_running"] = get_field_as_type(eg, "enableRunning", bool)
                retval["panic_status"] = get_field_as_type(eg, "panicStatus", bool)
                blocked = eg.get("blocked", {})
                if blocked:
                    retval["eguard_blocked_status"] = get_field_as_type(blocked, "status", int)

            # Parse parkTime
            park_time = vehicle_status.get("parkTime", {})
            if park_time:
                park_status = get_field_as_type(park_time, "status", int)
                if park_status is not None:
                    retval["park_time"] = datetime.fromtimestamp(park_status / 1000)

            # Parse configuration
            config = vehicle_status.get("configuration", {})
            if config:
                retval["propulsion_type"] = get_field_as_type(config, "propulsionType", int)
                retval["fuel_type"] = get_field_as_type(config, "fuelType", int)

            # Timestamp
            if "updateTime" in vehicle_status:
                retval["timestamp"] = datetime.fromtimestamp(int(vehicle_status["updateTime"]) / 1000)

        except KeyError as e:
            _LOGGER.info(f"Basic status info not available: {e}")
        finally:
            return retval
