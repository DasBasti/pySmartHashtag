"""Access to Smart account for your vehicles therin."""

import datetime
import json
import logging
import secrets
from dataclasses import InitVar, dataclass, field
from typing import List, Optional

import httpx

from pysmarthashtag.api.authentication import SmartAuthentication, SmartLoginClient
from pysmarthashtag.api.client import SmartClient, SmartClientConfiguration
from pysmarthashtag.const import API_BASE_URL, API_CARS_URL, SERVER_URL
from pysmarthashtag.vehicle.vehicle import SmartVehicle

VALID_UNTIL_OFFSET = datetime.timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

@dataclass
class SmartAccount:
    """Create a new connection to the Smart web service."""

    username: str
    """Username for the Smart account."""

    password: InitVar[str]
    """Password for the Smart account."""

    config: SmartClientConfiguration = None
    """Configuration for the Smart client."""

    log_responses: InitVar[bool] = False
    """Optional. If set, all responses from the server will be logged to this directory."""

    vehicles: List[SmartVehicle] = field(default_factory=list, init=False)

    def __post_init__(self, password, log_responses):
        """Initialize the account."""

        if self.config is None:
            self.config = SmartClientConfiguration(
                SmartAuthentication(self.username, password),
                log_responses=log_responses,
            )

    async def _init_vehicles(self) -> None:
        """Initialize vehicles from BMW servers."""
        _LOGGER.debug("Getting initial vehicle list")

        fetched_at = datetime.datetime.now(datetime.timezone.utc)

        async with SmartClient(self.config) as client:
            header = client.generate_default_header(
                params = {
                    "needSharedCar": 1,
                    "userId": self.username,
                },
                method="GET",
                url=API_CARS_URL,
            )
            vehicles_responses: List[httpx.Response] = [
                await client.get(
                    API_BASE_URL + API_CARS_URL + "?needSharedCar=1&userId=" + self.username,
                    headers=header,
                )
            ]

            for response in vehicles_responses:
                _LOGGER.debug(f"Got response {response.status_code} from {response.text}")
                for vehicle_base in response.json():
                    _LOGGER.debug(f"Found vehicle {vehicle_base}")
                    self.add_vehicle(vehicle_base, None, None, fetched_at)

    async def get_vehicles(self, force_init: bool = False) -> None:
        """Get the vehicles associated with the account."""
        _LOGGER.debug("Getting vehicles for account %s", self.username)
        fetched_at = datetime.datetime.now(datetime.timezone.utc)

        if len(self.vehicles) ==0 or force_init:
            await self._init_vehicles()

        async with SmartClient(self.config) as client:
            for vehicle in self.vehicles:
                try:
                    return
                    response = await client.get("https://api.smart.com/vehicles")
                    response.raise_for_status()
                    vehicles = response.json()
                    self.vehicles = [SmartVehicle(self, vehicle) for vehicle in vehicles]
                except httpx.HTTPStatusError as ex:
                    _LOGGER.error(
                        "Error getting vehicle list for account %s: %s",
                        self.username,
                        ex,
                    )
                    raise