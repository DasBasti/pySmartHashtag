"""Provides an accessible controll of the vehicle's climate functions."""

import json
import logging
from enum import Enum
from typing import TypedDict

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_TELEMATICS_URL
from pysmarthashtag.control.telematics import send_telematics_command
from pysmarthashtag.models import SmartHumanCarConnectionError, SmartTokenRefreshNecessary

_LOGGER = logging.getLogger(__name__)


class ServiceParameter(TypedDict):
    """TypedDict for service parameters."""

    key: str
    value: str


class HeatingLocation(str, Enum):
    """Enum for heating locations in the vehicle."""

    DRIVER_SEAT = "front-left"
    PASSENGER_SEAT = "front-right"
    STEERING_WHEEL = "steering_wheel"


class VentilationLocation(str, Enum):
    """Enum for ventilated seats (Smart #5 only)."""

    DRIVER_SEAT = "front-left"
    PASSENGER_SEAT = "front-right"


class RearHeatingLocation(str, Enum):
    """Enum for heated rear seats (Smart #5 only)."""

    REAR_LEFT = "rear-left"
    REAR_RIGHT = "rear-right"


# ZAF service parameter keys of the Smart #5 comfort functions
ZAF_HEATING_KEYS = {
    HeatingLocation.DRIVER_SEAT: "SH.11",
    HeatingLocation.PASSENGER_SEAT: "SH.19",
    HeatingLocation.STEERING_WHEEL: "SW",
}
ZAF_VENTILATION_KEYS = {
    VentilationLocation.DRIVER_SEAT: "SV.11",
    VentilationLocation.PASSENGER_SEAT: "SV.19",
}
ZAF_REAR_HEATING_KEYS = {
    RearHeatingLocation.REAR_LEFT: "SH.21",
    RearHeatingLocation.REAR_RIGHT: "SH.29",
}
ZAF_ALL_COMFORT_KEYS = ("AC", "SH.11", "SH.19", "SH.21", "SH.29", "SW", "DF", "SV.11", "SV.19")


class ClimateControll:
    """Provides an accessible controll of the vehicle's climate functions."""

    BASE_PAYLOAD_TEMPLATE = {
        "creator": "tc",
        "operationScheduling": {
            "duration": 180,
            "interval": 0,
            "occurs": 1,
            "recurrentOperation": False,
        },
        "serviceId": "RCE_2",
    }
    DEFROST_DURATION = 90

    def __init__(self, account: SmartAccount, vin: str, use_zaf: bool = False):
        """Initialize the vehicle.

        ``use_zaf`` selects the newer ZAF request format used by the Smart #5
        instead of the legacy RCE_2 payload of the #1/#3.
        """
        self.use_zaf = use_zaf
        self.account = account
        self.config = account.config
        self.vin = vin
        self.conditioning_temp = 20.0
        self.heating_levels: dict[HeatingLocation, int] = {
            HeatingLocation.DRIVER_SEAT: 0,
            HeatingLocation.PASSENGER_SEAT: 0,
            HeatingLocation.STEERING_WHEEL: 0,
        }
        self.ventilation_levels: dict[VentilationLocation, int] = {
            VentilationLocation.DRIVER_SEAT: 0,
            VentilationLocation.PASSENGER_SEAT: 0,
        }
        self.rear_heating_levels: dict[RearHeatingLocation, int] = {
            RearHeatingLocation.REAR_LEFT: 0,
            RearHeatingLocation.REAR_RIGHT: 0,
        }

    def _get_zaf_payload(self, active: bool) -> str:
        """Build the Smart #5 ZAF request. Start and stop both use ``command: start``."""
        params: dict[str, str] = {"operation": "4"}
        if active:
            params["AC"] = "true"
            params["AC.temp"] = f"{self.conditioning_temp:.1f}"
            params["AC.duration"] = "180"
            for key in ZAF_ALL_COMFORT_KEYS[1:]:
                params[key] = "false"
            comfort = {
                **{ZAF_HEATING_KEYS[loc]: lvl for loc, lvl in self.heating_levels.items()},
                **{ZAF_VENTILATION_KEYS[loc]: lvl for loc, lvl in self.ventilation_levels.items()},
                **{ZAF_REAR_HEATING_KEYS[loc]: lvl for loc, lvl in self.rear_heating_levels.items()},
            }
            for key, level in comfort.items():
                if level > 0:
                    params[key] = "true"
                    params[f"{key}.level"] = str(level)
        else:
            for key in ZAF_ALL_COMFORT_KEYS:
                params[key] = "false"
        payload = {
            "serviceId": "ZAF",
            "command": "start",
            "creator": "tc",
            "latest": False,
            "timeStamp": utils.create_correct_timestamp(),
            "userId": str(self.config.authentication.api_user_id),
            "operationScheduling": {
                "scheduledTime": None,
                "interval": 0,
                "occurs": 0,
                "recurrentOperation": 1,
                "duration": 60,
            },
            "serviceParameters": [{"key": k, "value": v} for k, v in params.items()],
        }
        return json.dumps(payload).replace(" ", "")

    def set_ventilation_level(self, location: VentilationLocation, level: int):
        """Set the (Smart #5) seat ventilation level; selecting one clears the seat's heating."""
        if not self.use_zaf:
            raise NotImplementedError("Seat ventilation is only supported on the Smart #5")
        if not isinstance(level, int) or isinstance(level, bool):
            raise TypeError("Ventilation level must be an integer")
        if level > 3 or level < 0:
            raise ValueError("Seat ventilation level must be between 0 and 3.")
        self.ventilation_levels[location] = level
        if level > 0:
            self.heating_levels[HeatingLocation(location.value)] = 0

    def set_rear_heating_level(self, location: RearHeatingLocation, level: int):
        """Set the (Smart #5) rear seat heating level."""
        if not self.use_zaf:
            raise NotImplementedError("Rear seat heating is only supported on the Smart #5")
        if not isinstance(level, int) or isinstance(level, bool):
            raise TypeError("Heating level must be an integer")
        if level > 3 or level < 0:
            raise ValueError("Seat heating level must be between 0 and 3.")
        self.rear_heating_levels[location] = level

    def _get_payload(self, active: bool) -> str:
        _payload = self.BASE_PAYLOAD_TEMPLATE.copy()
        _payload["command"] = "stop" if not active else "start"
        _payload["timestamp"] = utils.create_correct_timestamp()
        _payload["serviceParameters"] = []
        _payload["serviceParameters"].append({"key": "rce.conditioner", "value": "1"})
        _payload["serviceParameters"].append({"key": "rce.temp", "value": f"{self.conditioning_temp:.1f}"})
        for loc, level in self.heating_levels.items():
            if level > 0:
                _payload["serviceParameters"] += self._add_rce_heating_service(loc, f"{level}")

        return json.dumps(_payload).replace(" ", "")

    def _add_rce_heating_service(self, value: str, level: int) -> list[ServiceParameter]:
        """Create heating service parameters for the payload.

        Args:
        ----
            value: The heating location identifier
            level: The heating level as a string

        Returns:
        -------
            List of service parameter dictionaries

        """
        payload = [{"key": "rce.heat", "value": value}, {"key": "rce.level", "value": level}]
        return payload

    def set_heating_level(self, location: HeatingLocation, level: int):
        """Set heating level for the specified location."""
        if not isinstance(level, int):
            raise TypeError("Heating level must be an integer")
        if level > 3 or level < 0:
            raise ValueError("Seat heating level must be between 0 and 3.")
        self.heating_levels[location] = level
        if level > 0 and self.use_zaf and location != HeatingLocation.STEERING_WHEEL:
            self.ventilation_levels[VentilationLocation(location.value)] = 0

    async def set_climate_conditioning(self, temp: float, active: bool) -> bool:
        """Set the climate conditioning."""

        # A complete stop on the #5 sends all comfort functions off and needs no temperature
        if active or not self.use_zaf:
            if not isinstance(temp, (int, float)):
                raise TypeError("Temperature must be a number")
            if temp < 16 or temp > 30:
                raise ValueError("Temperature must be between 16 and 30 degrees.")
            self.conditioning_temp = float(temp)

        _LOGGER.debug("Setting climate conditioning: active=%s, temp=%s", active, temp)
        if self.use_zaf:
            return (await send_telematics_command(self.account, self.vin, self._get_zaf_payload(active))) is True
        return await self._send_rce_command(self._get_payload(active))

    def _get_defrost_payload(self, active: bool) -> str:
        _payload = self.BASE_PAYLOAD_TEMPLATE.copy()
        _payload["command"] = "start" if active else "stop"
        _payload["timestamp"] = utils.create_correct_timestamp()
        _payload["operationScheduling"] = {
            **self.BASE_PAYLOAD_TEMPLATE["operationScheduling"],
            "duration": self.DEFROST_DURATION if active else 0,
        }
        _payload["serviceParameters"] = [
            {"key": "rce.conditioner", "value": "2"},
            {"key": "rce.level", "value": "2"},
        ]
        return json.dumps(_payload).replace(" ", "")

    async def set_defrost(self, active: bool) -> bool:
        """Start or stop the front windscreen defrost."""
        if not isinstance(active, bool):
            raise TypeError("Defrost state must be a boolean")
        _LOGGER.debug("Setting front windscreen defrost: active=%s", active)
        return await self._send_rce_command(self._get_defrost_payload(active))

    async def _send_rce_command(self, params: str) -> bool:
        """Send a remote climate command to the vehicle."""
        # Ensure SSL context is created before using the client
        await self.account._ensure_ssl_context()

        await self.account.select_active_vehicle(self.vin)

        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    vehicles_response = await client.put(
                        self.account.vehicles[self.vin].base_url + API_TELEMATICS_URL + self.vin,
                        headers={
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params={},
                                method="PUT",
                                url=API_TELEMATICS_URL + self.vin,
                                body=params,
                            )
                        },
                        content=params.encode("utf-8"),
                    )
                    api_result = vehicles_response.json()
                    return api_result["success"]
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    continue
        return False
