"""Provides an accessible controll of the vehicle's climate functions."""

import json
import logging
import time

from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_BASE_URL, API_TELEMATICS_URL

_LOGGER = logging.getLogger(__name__)


class ClimateControll:
    """Provides an accessible controll of the vehicle's climate functions."""

    def __init__(self, config, vin):
        """Initialize the vehicle."""
        self.config = config
        self.vin = vin

    async def set_climate_conditioning(self, temp: float, active: bool) -> bool:
        """Set the climate conditioning."""
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
            _LOGGER.warning(f"Setting climate conditioning: {params}")
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
