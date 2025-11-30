"""Provides an accessible control of the vehicle's charging functions."""

import json
import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_TELEMATICS_URL
from pysmarthashtag.models import SmartHumanCarConnectionError, SmartTokenRefreshNecessary

_LOGGER = logging.getLogger(__name__)


class ChargingControl:
    """Provides an accessible control of the vehicle's charging functions."""

    BASE_PAYLOAD_TEMPLATE = {
        "creator": "tc",
        "operationScheduling": {
            "scheduledTime": None,
            "interval": 0,
            "occurs": 1,
            "recurrentOperation": 0,
            "duration": 6,
        },
        "serviceId": "rcs",
    }

    def __init__(self, account: SmartAccount, vin: str):
        """Initialize the charging control.

        Args:
        ----
            account: The Smart account instance
            vin: Vehicle identification number

        """
        self.account = account
        self.config = account.config
        self.vin = vin

    def _get_payload(self, start: bool) -> str:
        """Create the payload for start/stop charging.

        Args:
        ----
            start: True to start charging, False to stop

        Returns:
        -------
            JSON string payload for the API request

        """
        _payload = self.BASE_PAYLOAD_TEMPLATE.copy()
        _payload["operationScheduling"] = self.BASE_PAYLOAD_TEMPLATE["operationScheduling"].copy()
        _payload["command"] = "start"
        _payload["timeStamp"] = utils.create_correct_timestamp()
        _payload["serviceParameters"] = [
            {"key": "operation", "value": "1" if start else "0"},
            {"key": "rcs.restart" if start else "rcs.terminate", "value": "1"},
        ]
        return json.dumps(_payload).replace(" ", "")

    async def start_charging(self) -> bool:
        """Start charging the vehicle.

        Returns
        -------
            True if the command was successful, False otherwise

        """
        return await self._set_charging(start=True)

    async def stop_charging(self) -> bool:
        """Stop charging the vehicle.

        Returns
        -------
            True if the command was successful, False otherwise

        """
        return await self._set_charging(start=False)

    async def _set_charging(self, start: bool) -> bool:
        """Set the charging state.

        Args:
        ----
            start: True to start charging, False to stop

        Returns:
        -------
            True if the command was successful, False otherwise

        """
        # Ensure SSL context is created before using the client
        await self.account._ensure_ssl_context()

        await self.account.select_active_vehicle(self.vin)

        async with SmartClient(self.config) as client:
            params = self._get_payload(start)
            action = "start" if start else "stop"
            _LOGGER.debug("Setting charging: %s", action)
            for retry in range(3):
                try:
                    response = await client.put(
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
                        data=params,
                    )
                    api_result = response.json()
                    return api_result["success"]
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    continue
        return False
