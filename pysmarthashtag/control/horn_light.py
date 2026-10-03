"""Provides an accessible control of the vehicle's horn and lights."""

import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.control.telematics import (
    TELEMATICS_OPERATION_SCHEDULING,
    build_telematics_payload,
    send_telematics_command,
)

_LOGGER = logging.getLogger(__name__)


class HornLightControl:
    """Provides the find-my-car functions: honk the horn and flash the lights.

    Uses the remote horn and light service (RHL).
    """

    SERVICE_ID = "RHL"
    # SMore# sends horn/light commands with duration 0
    OPERATION_SCHEDULING = {**TELEMATICS_OPERATION_SCHEDULING, "duration": 0}

    def __init__(self, account: SmartAccount, vin: str):
        """Initialize the horn and light control.

        Args:
        ----
            account: The Smart account instance
            vin: Vehicle identification number

        """
        self.account = account
        self.config = account.config
        self.vin = vin

    def _get_payload(self, action: str) -> str:
        """Create the payload for a horn/light command.

        Args:
        ----
            action: "horn" or "light-flash"

        Returns:
        -------
            JSON string payload for the API request

        """
        return build_telematics_payload(
            self.SERVICE_ID,
            [{"key": "rhl", "value": action}],
            operation_scheduling=self.OPERATION_SCHEDULING,
        )

    async def flash_lights(self) -> bool:
        """Flash the lights of the vehicle.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Flashing the lights")
        return await send_telematics_command(self.account, self.vin, self._get_payload("light-flash"))

    async def honk_horn(self) -> bool:
        """Honk the horn of the vehicle.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Honking the horn")
        return await send_telematics_command(self.account, self.vin, self._get_payload("horn"))
