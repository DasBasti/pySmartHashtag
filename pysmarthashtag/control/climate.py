"""Provides an accessible controll of the vehicle's climate functions."""

import logging
import time

from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_BASE_URL, API_TELEMATICS_URL
from pysmarthashtag.vehicle.vehicle import SmartVehicle

_LOGGER = logging.getLogger(__name__)


class ClimateControll(SmartVehicle):
    """Provides an accessible controll of the vehicle's climate functions."""

    async def set_climate_conditioning(self, temp: float, active: bool) -> None:
        """Set the climate conditioning."""
        async with SmartClient(self.config) as client:
            params = {
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
                        "value": str(temp),
                    },
                ],
                "timestamp": str(time.time() * 1000),
            }
            vehicles_response = await client.put(
                API_BASE_URL + API_TELEMATICS_URL + self.vin,
                headers={
                    **utils.generate_default_header(
                        client.config.authentication.device_id,
                        client.config.authentication.api_access_token,
                        params=params,
                        method="GET",
                        url=API_TELEMATICS_URL + self.vin,
                    )
                },
            )

            _LOGGER.warning(f"Setting climate conditioning: {vehicles_response.json()}")
