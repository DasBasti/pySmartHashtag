"""Shared sender for remote telematics commands."""

import asyncio
import json
import logging
from typing import Any

import httpx

from pysmarthashtag.account import SmartAccount, _cloud_code
from pysmarthashtag.api import utils
from pysmarthashtag.api.client import SmartClient
from pysmarthashtag.const import API_TELEMATICS_URL
from pysmarthashtag.models import (
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

# Cloud code: "The last request has not yet been executed, please send the command later!"
# The cloud takes one remote command per vehicle at a time, so the next one has to wait.
COMMAND_PENDING_CODE = "8070"
COMMAND_PENDING_RETRIES = 5
COMMAND_PENDING_DELAY = 3.0


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
    vehicle has not executed the previous command yet (8070), the command is
    sent again after a short pause.

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
            except httpx.HTTPStatusError as exc:
                if _cloud_code(exc) != COMMAND_PENDING_CODE:
                    raise
                if pending_retries >= COMMAND_PENDING_RETRIES:
                    _LOGGER.warning(
                        "Vehicle still busy with the previous command after %d retries (8070), giving up",
                        COMMAND_PENDING_RETRIES,
                    )
                    return False
                pending_retries += 1
                _LOGGER.debug(
                    "Previous command not executed yet (8070), retry %d in %.0f s",
                    pending_retries,
                    COMMAND_PENDING_DELAY,
                )
                await asyncio.sleep(COMMAND_PENDING_DELAY)
    return False
