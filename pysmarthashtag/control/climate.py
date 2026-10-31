"""Provides an accessible controll of the vehicle's climate functions."""

import asyncio
import json
import logging
from enum import Enum
from typing import TypedDict

import httpx

from pysmarthashtag.account import SmartAccount, _cloud_code
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
ZAF_SEAT_HEATING_DURATION = "15"
ZAF_ALL_COMFORT_KEYS = ("SH.11", "SH.19", "SH.21", "SH.29", "SW", "DF", "SV.11", "SV.19")
# Cabin air conditioning of the Smart #5 (format from DasBasti/SmartHashtag#479)
ZAF_AC_KEY = "AC"
ZAF_AC_DURATION = "180"

# Cloud code: "The last request has not yet been executed, please send the command later!"
# The #5 takes one ZAF request at a time, so the next one has to wait.
ZAF_PENDING_CODE = "8070"
ZAF_PENDING_RETRIES = 5
ZAF_PENDING_DELAY = 3.0


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

    def _selected_comfort(self) -> list[tuple[str, int, bool]]:
        """Comfort functions with a level > 0 as (ZAF key, level, with duration)."""
        comfort = [
            *(
                (ZAF_HEATING_KEYS[loc], lvl, loc != HeatingLocation.STEERING_WHEEL)
                for loc, lvl in self.heating_levels.items()
            ),
            *((ZAF_VENTILATION_KEYS[loc], lvl, False) for loc, lvl in self.ventilation_levels.items()),
            *((ZAF_REAR_HEATING_KEYS[loc], lvl, True) for loc, lvl in self.rear_heating_levels.items()),
        ]
        return [entry for entry in comfort if entry[1] > 0]

    def _get_zaf_payloads(self, active: bool) -> list[str]:
        """Build the Smart #5 ZAF requests for climate conditioning.

        The air conditioning is its own request and always comes first, then
        one request per selected seat, the steering wheel and the ventilation
        (the cloud does not take several of them in one request).

        A stop switches the air conditioning off, then every comfort function
        that a start with the current selection switched on. Start and stop
        both use ``command: start``.
        """
        if not active:
            return [
                self._build_zaf_payload({"operation": "4", ZAF_AC_KEY: "false"}),
                *(self._build_zaf_payload({"operation": "4", key: "false"}) for key, _, _ in self._selected_comfort()),
            ]
        ac_params = {
            "operation": "4",
            ZAF_AC_KEY: "true",
            f"{ZAF_AC_KEY}.temp": f"{self.conditioning_temp:.1f}",
            f"{ZAF_AC_KEY}.duration": ZAF_AC_DURATION,
        }
        return [
            self._build_zaf_payload(ac_params),
            *(
                self._build_zaf_payload(self._zaf_level_params(key, level, with_duration))
                for key, level, with_duration in self._selected_comfort()
            ),
        ]

    @staticmethod
    def _zaf_level_params(key: str, level: int, with_duration: bool) -> dict[str, str]:
        """Service parameters that switch a single comfort function on."""
        params = {"operation": "4", key: "true", f"{key}.level": str(level)}
        if with_duration:
            params[f"{key}.duration"] = ZAF_SEAT_HEATING_DURATION
        return params

    def _build_zaf_payload(self, params: dict[str, str]) -> str:
        """Wrap ZAF service parameters in the request body. Start and stop both use ``command: start``."""
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

    async def _send_zaf_commands(self, payloads: list[str]) -> bool:
        """Send the ZAF requests one after the other and log what was sent and answered.

        The #5 takes one ZAF request at a time: while the previous one is not
        executed yet the cloud answers 8070. Such a request is sent again
        after a short pause instead of failing the whole call.

        Every request is sent even if an earlier one failed, so a stop always
        tries to switch everything off. Returns True only if all were accepted.
        """
        if not payloads:
            _LOGGER.debug("No ZAF command to send")
            return False
        results = []
        for params in payloads:
            _LOGGER.debug("Sending ZAF command: %s", params)
            result = await self._send_zaf_command_when_free(params)
            _LOGGER.debug("ZAF command result: %s", result)
            results.append(result is True)
        return all(results)

    async def _send_zaf_command_when_free(self, params: str) -> bool:
        """Send one ZAF request, repeating it while the cloud reports 8070."""
        for attempt in range(ZAF_PENDING_RETRIES + 1):
            try:
                return await send_telematics_command(self.account, self.vin, params)
            except httpx.HTTPStatusError as exc:
                if _cloud_code(exc) != ZAF_PENDING_CODE:
                    raise
                if attempt == ZAF_PENDING_RETRIES:
                    _LOGGER.warning(
                        "Smart #5 still busy with the previous request after %d retries (8070), giving up: %s",
                        ZAF_PENDING_RETRIES,
                        params,
                    )
                    return False
                _LOGGER.debug(
                    "Previous request not executed yet (8070), retry %d in %.0f s",
                    attempt + 1,
                    ZAF_PENDING_DELAY,
                )
                await asyncio.sleep(ZAF_PENDING_DELAY)
        return False

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
            return await self._send_zaf_commands(self._get_zaf_payloads(active))
        return await self._send_rce_command(self._get_payload(active))

    def _get_heating_payload(self, active: bool, levels: dict[HeatingLocation, int]) -> str:
        _payload = self.BASE_PAYLOAD_TEMPLATE.copy()
        _payload["command"] = "start" if active else "stop"
        _payload["timestamp"] = utils.create_correct_timestamp()
        _payload["serviceParameters"] = []
        if active:
            for loc, level in levels.items():
                _payload["serviceParameters"] += self._add_rce_heating_service(loc, f"{level}")
        else:
            # Same as the Hello Smart app: list every location, then level 0
            for loc in levels:
                _payload["serviceParameters"].append({"key": "rce.heat", "value": loc})
            _payload["serviceParameters"].append({"key": "rce.level", "value": "0"})
        return json.dumps(_payload).replace(" ", "")

    async def set_heating(self, active: bool, levels: dict[HeatingLocation, int]) -> bool:
        """Start or stop seat / steering wheel heating without climate conditioning.

        Unlike set_climate_conditioning, the RCE_2 command carries no
        rce.conditioner / rce.temp, so the air conditioning is not started.
        The levels given here are used as-is and do not change heating_levels.

        Args:
        ----
            active: True to start heating, False to stop it
            levels: Heating level (1-3) per location; only the keys are used to stop

        """
        self._check_heating_request(active, levels)

        _LOGGER.debug("Setting heating: active=%s, levels=%s", active, levels)
        if self.use_zaf:
            return await self._send_zaf_commands(self._get_zaf_heating_payloads(active, levels))
        return await self._send_rce_command(self._get_heating_payload(active, levels))

    @staticmethod
    def _check_heating_request(active: bool, levels: dict) -> None:
        """Validate the arguments of set_heating / set_rear_heating."""
        if not isinstance(active, bool):
            raise TypeError("Heating state must be a boolean")
        if not levels:
            raise ValueError("At least one heating location is required.")
        for level in levels.values():
            if not isinstance(level, int):
                raise TypeError("Heating level must be an integer")
            if active and (level > 3 or level < 1):
                raise ValueError("Heating level must be between 1 and 3 to start heating.")

    async def set_rear_heating(self, active: bool, levels: dict[RearHeatingLocation, int]) -> bool:
        """Start or stop the rear seat heating on its own (Smart #5 only).

        Every seat in ``levels`` is sent as its own request, without climate conditioning.
        The levels given here are used as-is and do not change rear_heating_levels.
        """
        if not self.use_zaf:
            raise NotImplementedError("Rear seat heating is only supported on the Smart #5")
        self._check_heating_request(active, levels)
        _LOGGER.debug("Setting rear heating: active=%s, levels=%s", active, levels)
        return await self._send_zaf_commands(self._get_zaf_heating_payloads(active, levels))

    def _get_zaf_heating_payloads(
        self, active: bool, levels: dict[HeatingLocation, int] | dict[RearHeatingLocation, int]
    ) -> list[str]:
        """Build one Smart #5 ZAF request per seat / steering wheel in ``levels``."""
        payloads = []
        for loc, level in levels.items():
            key = {**ZAF_HEATING_KEYS, **ZAF_REAR_HEATING_KEYS}[loc]
            if active:
                params = self._zaf_level_params(key, level, loc != HeatingLocation.STEERING_WHEEL)
            else:
                params = {"operation": "4", key: "false"}
            payloads.append(self._build_zaf_payload(params))
        return payloads

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
        if self.use_zaf:
            params = {"operation": "4", "DF": "true" if active else "false"}
            return await self._send_zaf_commands([self._build_zaf_payload(params)])
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
