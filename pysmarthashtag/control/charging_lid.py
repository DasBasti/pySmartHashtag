"""Provides an accessible control of the vehicle's charging lid."""

import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.control.telematics import (
    TELEMATICS_OPERATION_SCHEDULING,
    build_telematics_payload,
    send_telematics_command,
)

_LOGGER = logging.getLogger(__name__)


class ChargingLidControl:
    """Provides the opening and closing of the motorised charging lid.

    Only the Smart #5 has one. Uses the remote charging lid open (RDO) and
    close (RDC) telematics services.
    """

    OPEN_SERVICE_ID = "RDO"
    CLOSE_SERVICE_ID = "RDC"
    LID_PARAMETER = {"key": "target", "value": "front-charge-lid"}
    OPERATION_SCHEDULING = {**TELEMATICS_OPERATION_SCHEDULING, "duration": 0}

    def __init__(self, account: SmartAccount, vin: str):
        """Initialize the charging lid control.

        Args:
        ----
            account: The Smart account instance
            vin: Vehicle identification number

        """
        self.account = account
        self.config = account.config
        self.vin = vin

    def _get_payload(self, service_id: str) -> str:
        """Create the payload for a charging lid command.

        Args:
        ----
            service_id: The telematics service to call (RDO or RDC)

        Returns:
        -------
            JSON string payload for the API request

        """
        return build_telematics_payload(
            service_id,
            [self.LID_PARAMETER],
            operation_scheduling=self.OPERATION_SCHEDULING,
            timestamp_key="timeStamp",
            user_id=str(self.config.authentication.api_user_id),
        )

    async def open(self) -> bool:
        """Open the charging lid.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Opening the charging lid")
        return await send_telematics_command(self.account, self.vin, self._get_payload(self.OPEN_SERVICE_ID))

    async def close(self) -> bool:
        """Close the charging lid.

        Returns
        -------
            True if the command was accepted, False otherwise

        """
        _LOGGER.debug("Closing the charging lid")
        return await send_telematics_command(self.account, self.vin, self._get_payload(self.CLOSE_SERVICE_ID))
