"""Provides an accessible controll of the vehicle's climate functions."""

import json
import logging

from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_BASE_URL, API_TELEMATICS_URL
from pysmarthashtag.models import SmartHumanCarConnectionError, SmartTokenRefreshNecessary

_LOGGER = logging.getLogger(__name__)


class ClimateControll:
    """Provides an accessible controll of the vehicle's climate functions."""

    def __init__(self, config, vin):
        """Initialize the vehicle."""
        self.config = config
        self.vin = vin

    async def set_climate_conditioning(self, temp: float, active: bool) -> bool:
        """Set the climate conditioning."""

        if temp < 16 or temp > 30:
            raise ValueError("Temperature must be between 16 and 30 degrees.")

        async with SmartClient(self.config) as client:
            params = json.dumps(
                {
                    "command": "start" if active else "stop",
                    "creator": "tc",
                    "operationScheduling": {
                        "duration": 180,
                        "interval": 0,
                        "occurs": 1,
                        "recurrentOperation": False,
                    },
                    "serviceId": "RCE_2",
                    "serviceParameters": [
                        {
                            "key": "rce.conditioner",
                            "value": "1",
                        },
                        {
                            "key": "rce.temp",
                            "value": f"{temp:.1f}",
                        },
                    ],
                    "timestamp": utils.create_correct_timestamp(),
                }
            ).replace(" ", "")
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

    async def set_climate_seatheating(self, level: int, active: bool) -> bool:
        """Set the climate conditioning."""

        if level > 3 or (level < 1 and active):
            raise ValueError("Seat heating level must be between 0 and 3.")

        async with SmartClient(self.config) as client:
            params = json.dumps(
                {
                    "command": "start" if active else "stop",
                    "creator": "tc",
                    "operationScheduling": {
                        "duration": 15,
                        "interval": 0,
                        "occurs": 1,
                        "recurrentOperation": False,
                    },
                    "serviceId": "RCE_2",
                    "serviceParameters": [
                        {
                            "key": "rce.heat",
                            "value": "front-left",
                        },
                        {
                            "key": "rce.level",
                            "value": f"{level}",
                        },
                    ],
                    "timestamp": utils.create_correct_timestamp(),
                }
            ).replace(" ", "")
            _LOGGER.debug(f"Setting seatheating conditioning: {params}")
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
