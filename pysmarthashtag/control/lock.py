"""Provides an accessible control of the vehicle's door locks."""

import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.control.telematics import build_telematics_payload, send_telematics_command

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
        return build_telematics_payload(service_id, [parameter])

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

    async def _send_command(self, params: str) -> bool:
        """Send a door lock command to the vehicle."""
        return await send_telematics_command(self.account, self.vin, params)
