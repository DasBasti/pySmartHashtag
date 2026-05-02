"""Provides client-side control of the vehicle's on-vehicle trip-recording flag.

When the flag is OFF, the vehicle's TBox does not write to the cloud-side
journal log, so ``SmartAccount.get_trip_journal()`` returns ``code:8153``
"data unavailable". Toggling the flag ON causes subsequent trips to be
written to the journal log, after which ``get_trip_journal()`` returns
populated trip records.

Modeled on ``pysmarthashtag.control.charging.ChargingControl``.
"""

import json
import logging

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_JOURNAL_TOGGLE_URL
from pysmarthashtag.models import SmartHumanCarConnectionError, SmartTokenRefreshNecessary

_LOGGER = logging.getLogger(__name__)


class JournalRecordingControl:
    """Toggle the on-vehicle trip-recording flag (``journalLogState``)."""

    def __init__(self, account: SmartAccount, vin: str):
        self.account = account
        self.config = account.config
        self.vin = vin

    def _get_payload(self, enable: bool) -> str:
        payload = {
            "creator": "tc",
            "timestamp": utils.create_correct_timestamp(),
            "latest": False,
            "command": "start" if enable else "stop",
            "serviceId": "JOU",
            "serviceParameters": [
                {"key": "jou", "value": "enable" if enable else "disable"},
            ],
            "operationScheduling": {
                "scheduledTime": 0,
                "interval": 0,
                "occurs": 0,
                "recurrentOperation": True,
                "duration": 60,
            },
        }
        return json.dumps(payload).replace(" ", "")

    async def enable_recording(self) -> bool:
        """Turn on-vehicle trip recording ON."""
        return await self._set_recording(enable=True)

    async def disable_recording(self) -> bool:
        """Turn on-vehicle trip recording OFF."""
        return await self._set_recording(enable=False)

    async def _set_recording(self, enable: bool) -> bool:
        await self.account._ensure_ssl_context()
        await self.account.select_active_vehicle(self.vin)

        path = API_JOURNAL_TOGGLE_URL + self.vin
        body = self._get_payload(enable)
        action = "enable" if enable else "disable"
        _LOGGER.debug("Setting trip-recording: %s", action)

        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    response = await client.put(
                        self.account.vehicles[self.vin].base_url + path,
                        headers={
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params={},
                                method="PUT",
                                url=path,
                                body=body,
                            )
                        },
                        content=body.encode("utf-8"),
                    )
                    api_result = response.json()
                    return bool(api_result.get("success"))
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    continue
        return False
