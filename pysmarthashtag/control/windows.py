"""Provides an accessible control of the vehicle's windows."""

import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.control.telematics import (
    TELEMATICS_OPERATION_SCHEDULING,
    build_telematics_payload,
    send_telematics_command,
)

_LOGGER = logging.getLogger(__name__)


class WindowControl:
    """Provides an accessible control of the vehicle's windows.

    Uses the remote window service (RWS_2). "start" opens, "stop" closes.
    """

    SERVICE_ID = "RWS_2"
    # SMore# sends window commands with duration 0
    OPERATION_SCHEDULING = {**TELEMATICS_OPERATION_SCHEDULING, "duration": 0}

    def __init__(self, account: SmartAccount, vin: str):
        """Initialize the window control.

        Args:
        ----
            account: The Smart account instance
            vin: Vehicle identification number

        """
        self.account = account
        self.config = account.config
        self.vin = vin

    def _get_payload(self, target: str, open_: bool) -> str:
        """Create the payload for a window command.

        Args:
        ----
            target: What to move, e.g. "ventilate"
            open_: True to open ("start"), False to close ("stop")

        Returns:
        -------
            JSON string payload for the API request

        """
        return build_telematics_payload(
            self.SERVICE_ID,
            [{"key": "target", "value": target}],
            command="start" if open_ else "stop",
            operation_scheduling=self.OPERATION_SCHEDULING,
        )

    async def set_ventilation(self, active: bool) -> bool:
        """Open the windows to the ventilation position, or close them.

        Args:
        ----
            active: True to open for ventilation, False to close the windows

        Returns:
        -------
            True if the command was accepted, False otherwise

        """
        if not isinstance(active, bool):
            raise TypeError("Ventilation state must be a boolean")
        _LOGGER.debug("Setting window ventilation: active=%s", active)
        return await send_telematics_command(self.account, self.vin, self._get_payload("ventilate", active))
