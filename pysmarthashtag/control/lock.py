"""Provides an accessible control of the vehicle's door locks."""

import json
import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_TELEMATICS_URL
from pysmarthashtag.models import SmartHumanCarConnectionError, SmartTokenRefreshNecessary

_LOGGER = logging.getLogger(__name__)


class DoorLockControl:
    """Provides an accessible control of the vehicle's door locks.

    Uses the remote door lock (RDL_2) and remote door unlock (RDU_2)
    telematics services.
    """

    LOCK_SERVICE_ID = "RDL_2"
    UNLOCK_SERVICE_ID = "RDU_2"

    def __init__(self, account: SmartAccount, vin: str):
        """Initialize the door lock control.

        Args:
        ----
            account: The Smart account instance
            vin: Vehicle identification number

        """
        self.account = account
        self.config = account.config
        self.vin = vin

    def _get_payload(self, service_id: str, parameter: dict[str, str]) -> str:
        """Create the payload for a door lock command.

        Args:
        ----
            service_id: The telematics service to call (RDL_2 or RDU_2)
            parameter: The service parameter selecting what to (un)lock

        Returns:
        -------
            JSON string payload for the API request

        """
        _payload = {
            "creator": "tc",
            "command": "start",
            "operationScheduling": {
                "duration": 6,
                "interval": 0,
                "occurs": 1,
                "recurrentOperation": False,
            },
            "serviceId": service_id,
            "timestamp": utils.create_correct_timestamp(),
            "serviceParameters": [parameter],
        }
        return json.dumps(_payload).replace(" ", "")

    async def lock(self) -> bool:
        """Lock all doors of the vehicle.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Locking all doors")
        return await self._send_command(self._get_payload(self.LOCK_SERVICE_ID, {"key": "door", "value": "all"}))

    async def unlock(self) -> bool:
        """Unlock all doors of the vehicle.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Unlocking all doors")
        return await self._send_command(self._get_payload(self.UNLOCK_SERVICE_ID, {"key": "door", "value": "all"}))

    async def unlock_trunk(self) -> bool:
        """Unlock the trunk of the vehicle.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Unlocking trunk")
        return await self._send_command(self._get_payload(self.UNLOCK_SERVICE_ID, {"key": "target", "value": "trunk"}))

    async def _send_command(self, params: str) -> bool:
        """Send a door lock command to the vehicle."""
        # Ensure SSL context is created before using the client
        await self.account._ensure_ssl_context()

        await self.account.select_active_vehicle(self.vin)

        async with SmartClient(self.config) as client:
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
                        content=params.encode("utf-8"),
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
