"""Shared sender for remote telematics commands."""

import json
import logging
from typing import Any

from pysmarthashtag.account import SmartAccount
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


def build_telematics_payload(
    service_id: str,
    parameters: list[dict[str, str]],
    command: str = "start",
    operation_scheduling: dict[str, Any] | None = None,
    timestamp_key: str = "timestamp",
) -> str:
    """Create the compact JSON body of a remote telematics command.

    Args:
    ----
        service_id: The telematics service to call, e.g. RDL_2 or RWS_2
        parameters: The service parameters as key/value dicts
        command: "start" or "stop"
        operation_scheduling: Overrides the default operation scheduling
        timestamp_key: Name of the timestamp field ("timestamp" or "timeStamp")

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
    return json.dumps(payload).replace(" ", "")


async def send_telematics_command(account: SmartAccount, vin: str, params: str) -> bool:
    """Send a remote telematics command to the vehicle.

    The command is bound to the VIN via headers. An expired session token is
    refreshed and a lost VIN binding re-established before retrying.

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
        for retry in range(3):
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
                continue
            except (SmartHumanCarConnectionError, SmartVehicleNotInUseError):
                _LOGGER.debug("VIN binding lost (8006/4038); re-binding vehicle (retry %d)", retry)
                await account.select_active_vehicle(vin)
                continue
    return False
