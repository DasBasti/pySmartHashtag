"""Provides an accessible control of the vehicle's charging functions."""

import json
import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_TELEMATICS_URL
from pysmarthashtag.control.telematics import build_telematics_payload, send_telematics_command
from pysmarthashtag.models import SmartHumanCarConnectionError, SmartTokenRefreshNecessary

_LOGGER = logging.getLogger(__name__)


class ChargingControl:
    """Provides an accessible control of the vehicle's charging functions."""

    CHARGING_LIMIT_MIN = 50
    CHARGING_LIMIT_MAX = 100
    CHARGING_LIMIT_STEP = 5

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
        # Create a new payload dictionary to avoid modifying the template
        _payload = {
            "creator": self.BASE_PAYLOAD_TEMPLATE["creator"],
            "operationScheduling": {
                "scheduledTime": None,
                "interval": 0,
                "occurs": 1,
                "recurrentOperation": 0,
                "duration": 6,
            },
            "serviceId": self.BASE_PAYLOAD_TEMPLATE["serviceId"],
        }
        # Per the API specification, command is always "start"
        # The actual operation (start/stop) is controlled by the serviceParameters
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

    def _get_charging_limit_payload(self, percent: int) -> str:
        """Create the payload for setting the charging limit.

        The limit is sent in percent x 10, as it is reported by the
        vehicle status (soc?setting=charging).
        """
        return build_telematics_payload(
            self.BASE_PAYLOAD_TEMPLATE["serviceId"],
            [
                {"key": "soc", "value": str(percent * 10)},
                {"key": "operation", "value": "4"},
                {"key": "rcs.setting", "value": "1"},
            ],
            operation_scheduling=self.BASE_PAYLOAD_TEMPLATE["operationScheduling"],
            timestamp_key="timeStamp",
        )

    async def set_charging_limit(self, percent: int) -> bool:
        """Set the charging limit (target state of charge).

        Args:
        ----
            percent: The limit in percent, 50-100 in steps of 5

        Returns:
        -------
            True if the command was accepted, False otherwise

        """
        if not isinstance(percent, int) or isinstance(percent, bool):
            raise TypeError("Charging limit must be an integer")
        if not self.CHARGING_LIMIT_MIN <= percent <= self.CHARGING_LIMIT_MAX or percent % self.CHARGING_LIMIT_STEP:
            raise ValueError(
                f"Charging limit must be between {self.CHARGING_LIMIT_MIN} and {self.CHARGING_LIMIT_MAX} "
                f"in steps of {self.CHARGING_LIMIT_STEP}."
            )
        _LOGGER.debug("Setting charging limit to %d%%", percent)
        return await send_telematics_command(self.account, self.vin, self._get_charging_limit_payload(percent))

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
