"""Shared sender for remote telematics commands."""

import asyncio
import json
import logging
from typing import Any

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_TELEMATICS_URL
from pysmarthashtag.models import (
    SmartCommandPendingError,
    SmartHumanCarConnectionError,
    SmartTokenRefreshNecessary,
    SmartVehicleNotInUseError,
)

_LOGGER = logging.getLogger(__name__)

TELEMATICS_OPERATION_SCHEDULING = {
    "duration": 6,
    "interval": 0,
    "occurs": 1,
    "recurrentOperation": False,
}

# The cloud takes one remote command per vehicle at a time and answers 8070
# until the vehicle has executed the previous one.
COMMAND_PENDING_DELAY = 5.0
COMMAND_PENDING_RETRIES = 6


def build_telematics_payload(
    service_id: str,
    parameters: list[dict[str, str]],
    command: str = "start",
    operation_scheduling: dict[str, Any] | None = None,
    timestamp_key: str = "timestamp",
    user_id: str | None = None,
) -> str:
    """Create the compact JSON body of a remote telematics command.

    Args:
    ----
        service_id: The telematics service to call, e.g. RDL_2 or RWS_2
        parameters: The service parameters as key/value dicts
        command: "start" or "stop"
        operation_scheduling: Overrides the default operation scheduling
        timestamp_key: Name of the timestamp field ("timestamp" or "timeStamp")
        user_id: Adds a "userId" field, for the services that require it

    Returns:
    -------
        JSON string payload for the API request

    """
    payload = {
        "creator": "tc",
        "command": command,
        "operationScheduling": dict(operation_scheduling or TELEMATICS_OPERATION_SCHEDULING),
        "serviceId": service_id,
        timestamp_key: utils.create_correct_timestamp(),
        "serviceParameters": parameters,
    }
    if user_id is not None:
        payload["userId"] = user_id
    return json.dumps(payload).replace(" ", "")


async def send_telematics_command(account: SmartAccount, vin: str, params: str) -> bool:
    """Send a remote telematics command to the vehicle.

    The command is bound to the VIN via headers. An expired session token is
    refreshed and a lost VIN binding re-established before retrying. While the
    vehicle is still busy with the previous command (8070), the command is sent
    again after a pause.

    Args:
    ----
        account: The Smart account instance
        vin: Vehicle identification number
        params: JSON body created by build_telematics_payload

    Returns:
    -------
        True if the command was accepted, False otherwise

    """
    # Ensure SSL context is created before using the client
    await account._ensure_ssl_context()

    await account.select_active_vehicle(vin)

    async with SmartClient(account.config) as client:
        retry = 0
        pending_retries = 0
        while retry < 3:
            try:
                response = await client.put(
                    account.vehicles[vin].base_url + API_TELEMATICS_URL + vin,
                    headers={
                        **utils.generate_default_header(
                            client.config.authentication.device_id,
                            client.config.authentication.api_access_token,
                            params={},
                            method="PUT",
                            url=API_TELEMATICS_URL + vin,
                            body=params,
                            vin=vin,
                            model_code=account._vin_model_code(vin),
                        )
                    },
                    content=params.encode("utf-8"),
                )
                api_result = response.json()
                return api_result["success"]
            except SmartTokenRefreshNecessary:
                _LOGGER.debug("Session token expired; refreshing (retry %d)", retry)
                await account.config.authentication.refresh()
                retry += 1
            except (SmartHumanCarConnectionError, SmartVehicleNotInUseError):
                _LOGGER.debug("VIN binding lost (8006/4038); re-binding vehicle (retry %d)", retry)
                await account.select_active_vehicle(vin)
                retry += 1
            except SmartCommandPendingError:
                if pending_retries >= COMMAND_PENDING_RETRIES:
                    _LOGGER.warning("Vehicle is still busy with the previous command (8070); giving up")
                    return False
                pending_retries += 1
                _LOGGER.debug(
                    "Previous command not yet executed (8070); waiting %.0f s (retry %d)",
                    COMMAND_PENDING_DELAY,
                    pending_retries,
                )
                await asyncio.sleep(COMMAND_PENDING_DELAY)
    return False
