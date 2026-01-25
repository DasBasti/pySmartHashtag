"""Access to Smart account for your vehicles therin."""

import datetime
import json
import logging
from dataclasses import InitVar, dataclass, field
from typing import Optional

from pysmarthashtag.api import utils
from pysmarthashtag.api.authentication import SmartAuthentication, SmartAuthenticationINTL
from pysmarthashtag.api.client import SmartClient, SmartClientConfiguration
from pysmarthashtag.api.log_sanitizer import sanitize_log_data
from pysmarthashtag.const import API_CARS_URL, API_SELECT_CAR_URL, EndpointUrls, SmartRegion
from pysmarthashtag.models import SmartAuthError, SmartHumanCarConnectionError, SmartTokenRefreshNecessary
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

    endpoint_urls: Optional[EndpointUrls] = None
    """Optional. Custom endpoint URLs for international API support."""

    region: Optional[SmartRegion] = None
    """Optional. Region preset (EU or INTL). If set, overrides endpoint_urls."""

    vehicles: dict[str, SmartVehicle] = field(default_factory=dict, init=False)
    """Vehicles associated with the account."""

    def __post_init__(self, password, log_responses):
        """Initialize the account."""
        # Import get_endpoint_urls_for_region here to avoid circular imports
        from pysmarthashtag.const import get_endpoint_urls_for_region

        # If region is specified, use it to get endpoint URLs
        if self.region is not None:
            self.endpoint_urls = get_endpoint_urls_for_region(self.region)
        elif self.endpoint_urls is None:
            self.endpoint_urls = EndpointUrls()

        # Choose authentication class based on region
        if self.region == SmartRegion.INTL:
            _LOGGER.info("Using INTL (International) authentication for region: %s", self.region)
            auth = SmartAuthenticationINTL(self.username, password, endpoint_urls=self.endpoint_urls)
        else:
            _LOGGER.info("Using EU authentication (default)")
            auth = SmartAuthentication(self.username, password, endpoint_urls=self.endpoint_urls)

        if self.config is None:
            self.config = SmartClientConfiguration(
                auth,
                log_responses=log_responses,
            )

    def _is_intl_region(self) -> bool:
        """Check if using INTL (International) region."""
        return self.region == SmartRegion.INTL

    def _generate_api_headers(self, params: dict, method: str, url: str, body=None) -> dict[str, str]:
        """Generate API headers based on region (EU or INTL).

        This method automatically selects the correct header generator
        based on whether the account is configured for INTL region.
        """
        auth = self.config.authentication

        if self._is_intl_region():
            # INTL region uses different headers and signing
            client_id = getattr(auth, 'api_client_id', None)
            return utils.generate_intl_header(
                device_id=auth.device_id,
                access_token=auth.api_access_token,
                params=params,
                method=method,
                url=url,
                body=body,
                client_id=client_id,
            )
        else:
            # EU region uses default headers
            return utils.generate_default_header(
                device_id=auth.device_id,
                access_token=auth.api_access_token,
                params=params,
                method=method,
                url=url,
                body=body,
            )

    async def _ensure_ssl_context(self) -> None:
        """Ensure SSL context is created asynchronously.

        This method creates the SSL context in a thread pool executor
        to avoid blocking the async event loop when httpx creates
        SSL connections.
        """
        if self.config.ssl_context is None:
            self.config.ssl_context = await self.config.get_ssl_context()
            # Also set the SSL context on the authentication object
            self.config.authentication.ssl_context = self.config.ssl_context

    async def login(self, force_refresh: bool = False) -> None:
        """Get the vehicles associated with the account."""
        await self._ensure_ssl_context()
        if force_refresh is None:
            self.config.authentication = None
        await self.config.authentication.login()

    async def _init_vehicles(self) -> None:
        """Initialize vehicles from Smart servers."""
        _LOGGER.debug("Getting initial vehicle list")
        await self._ensure_ssl_context()

        fetched_at = datetime.datetime.now(datetime.timezone.utc)

        async with SmartClient(self.config) as client:
            params = {
                "needSharedCar": 1,
                "userId": self.config.authentication.api_user_id,
            }
            for retry in range(3):
                try:
                    vehicles_response = await client.get(
                        # we do not know what type of car we have in our list so we fall back to the old API URL
                        self.endpoint_urls.get_api_base_url() + API_CARS_URL + "?" + utils.join_url_params(params),
                        headers={
                            **self._generate_api_headers(
                                params=params,
                                method="GET",
                                url=API_CARS_URL,
                            )
                        },
                    )
                    _LOGGER.debug("Got response %d", vehicles_response.status_code)
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    self._init_vehicles()
                    continue
                break

            for vehicle in vehicles_response.json()["data"]["list"]:
                _LOGGER.debug("Found vehicle %s", sanitize_log_data(vehicle))
                self.add_vehicle(vehicle, fetched_at)

    def add_vehicle(self, vehicle, fetched_at):
        """Add a vehicle to the account."""
        self.vehicles[vehicle.get("vin")] = SmartVehicle(self, vehicle, fetched_at=fetched_at)

    async def get_vehicles(self, force_init: bool = False) -> None:
        """Get the vehicles associated with the account."""
        await self._ensure_ssl_context()
        if self.config.authentication.api_user_id is None:
            await self.config.authentication.login()

        _LOGGER.debug("Getting vehicles for account")

        if len(self.vehicles) == 0 or force_init:
            await self._init_vehicles()

        for vin, vehicle in self.vehicles.items():
            _LOGGER.debug("Getting vehicle data")
            await self.select_active_vehicle(vin)
            vehicle_info = await self.get_vehicle_information(vin)
            vehicle_soc = await self.get_vehicle_soc(vin)
            vehicle_ota_info = await self.get_vehicle_ota_info(vin)
            vehicle.combine_data(vehicle_info, charging_settings=vehicle_soc, ota_info=vehicle_ota_info)

    async def select_active_vehicle(self, vin) -> None:
        """Select the active vehicle."""
        _LOGGER.debug("Selecting vehicle")
        data = json.dumps(
            {
                "vin": vin,
                "sessionToken": self.config.authentication.api_access_token,
                "language": "",
            }
        )
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    r_car_info = await client.post(
                        self.vehicles[vin].base_url + API_SELECT_CAR_URL,
                        headers={
                            **self._generate_api_headers(
                                params={},
                                method="POST",
                                url=API_SELECT_CAR_URL,
                                body=data,
                            )
                        },
                        data=data,
                    )
                    _LOGGER.debug("Got response %d", r_car_info.status_code)
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    self.select_active_vehicle(vin)
                    continue
                break

    async def get_vehicle_information(self, vin) -> str:
        """Get information about a vehicle."""
        _LOGGER.debug("Getting information for vehicle")

        # INTL uses different API path and parameters than EU
        if self._is_intl_region():
            # INTL: No /api/v1/ prefix, latest=False to get all data including climate/doors/pollution
            params = {
                "latest": False,
                "target": "basic,more",
                "userId": self.config.authentication.api_user_id,
            }
            url_path = "/remote-control/vehicle/status/" + vin
            # INTL uses api.ecloudeu.com without /api/v1/ prefix
            base_url = self.endpoint_urls.get_api_base_url()
        else:
            # EU: Uses /api/v1/ prefix in the base_url setting
            params = {
                "latest": True,
                "target": "basic,more",
                "userId": self.config.authentication.api_user_id,
            }
            url_path = "/remote-control/vehicle/status/" + vin
            base_url = self.vehicles[vin].base_url

        data = {}
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    # Build URL with URL-encoded params for GET request
                    url_params = {k: str(v).replace(",", "%2C") for k, v in params.items()}
                    r_car_info = await client.get(
                        base_url
                        + url_path
                        + "?"
                        + utils.join_url_params(url_params),
                        headers={
                            **self._generate_api_headers(
                                params=params,
                                method="GET",
                                url=url_path,
                            )
                        },
                    )
                    _LOGGER.debug("Got response %d", r_car_info.status_code)
                    self.vehicles.get(vin).combine_data(r_car_info.json()["data"])
                    data = r_car_info.json()["data"]
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    await self.select_active_vehicle(vin)
                    continue
                break
            if retry > 1:
                raise SmartAuthError("Could not get vehicle information")
        return data

    async def get_vehicle_soc(self, vin) -> str:
        """Get information about a vehicle."""
        _LOGGER.debug("Getting vehicle SOC")
        params = {
            "setting": "charging",
        }
        data = {}
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    r_car_info = await client.get(
                        self.vehicles[vin].base_url
                        + "/remote-control/vehicle/status/soc/"
                        + vin
                        + "?"
                        + utils.join_url_params(params),
                        headers={
                            **self._generate_api_headers(
                                params=params,
                                method="GET",
                                url="/remote-control/vehicle/status/soc/" + vin,
                            )
                        },
                    )
                    _LOGGER.debug("Got response %d", r_car_info.status_code)
                    self.vehicles.get(vin).combine_data(r_car_info.json()["data"])
                    data = r_car_info.json()["data"]
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    self.select_active_vehicle(vin)
                    continue
                break
            if retry > 1:
                raise SmartAuthError("Could not get vehicle information")
        return data

    async def get_vehicle_ota_info(self, vin) -> dict:
        """Get information about a vehicle from OTA server."""
        _LOGGER.debug("Getting OTA information for vehicle")
        data = {}
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    r_car_info = await client.get(
                        self.endpoint_urls.get_ota_server_url() + "app/info/" + vin,
                        headers={
                            "host": "ota.srv.smart.com",
                            "accept": "*/*",
                            "cookie": "gmid=gmid.ver4.AcbHPqUK5Q.xOaWPhRTb7gy-6-GUW6cxQVf_t7LhbmeabBNXqqqsT6dpLJLOWCGWZM07EkmfM4j.u2AMsCQ9ZsKc6ugOIoVwCgryB2KJNCnbBrlY6pq0W2Ww7sxSkUa9_WTPBIwAufhCQYkb7gA2eUbb6EIZjrl5mQ.sc3; ucid=hPzasmkDyTeHN0DinLRGvw; hasGmid=ver4; gig_bootstrap_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a=auth_ver4",  # noqa: E501
                            "id-token": client.config.authentication.device_id,
                            "connection": "keep-alive",
                            "user-agent": "Hello%20smart/1 CFNetwork/3826.500.131 Darwin/24.5.0",
                            "access_token": client.config.authentication.access_token,
                            "content-type": "application/json",
                            "accept-encoding": "gzip, deflate, br",
                            "accept-language": "en-US,en;q=0.9",
                        },
                    )
                    _LOGGER.debug("Got response %d", r_car_info.status_code)
                    json_data = r_car_info.json()
                    data = {
                        "target_version": json_data.get("targetVersion"),
                        "current_version": json_data.get("currentVersion"),
                    }
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    self.select_active_vehicle(vin)
                    continue
                break
            if retry > 1:
                raise SmartAuthError("Could not get vehicle information")
        return data
