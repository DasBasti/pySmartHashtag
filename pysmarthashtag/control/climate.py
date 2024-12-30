"""Provides an accessible controll of the vehicle's climate functions."""

import json
import logging
from enum import Enum
from typing import TypedDict

from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_BASE_URL, API_TELEMATICS_URL
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

    def __init__(self, config, vin):
        """Initialize the vehicle."""
        self.config = config
        self.vin = vin
        self.conditioning_temp = 20.0
        self.heating_levels: dict[HeatingLocation, int] = {
            HeatingLocation.DRIVER_SEAT: 0,
            HeatingLocation.PASSENGER_SEAT: 0,
            HeatingLocation.STEERING_WHEEL: 0,
        }

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

    async def set_climate_conditioning(self, temp: float, active: bool) -> bool:
        """Set the climate conditioning."""

        if not isinstance(temp, (int, float)):
            raise TypeError("Temperature must be a number")
        if temp < 16 or temp > 30:
            raise ValueError("Temperature must be between 16 and 30 degrees.")
        self.conditioning_temp = float(temp)

        async with SmartClient(self.config) as client:
            params = self._get_payload(active)
            _LOGGER.debug(f"Setting climate conditioning: {params}")
            for retry in range(2):
                try:
                    vehicles_response = await client.put(
                        API_BASE_URL + API_TELEMATICS_URL + self.vin,
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
                        data=params,
                    )
                    api_result = vehicles_response.json()
                    return api_result["success"]
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug(f"Got Token Error, retry: {retry}")
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug(f"Got Human Car Connection Error, retry: {retry}")
                    continue
