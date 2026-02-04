"""Access to Smart account for your vehicles therin."""

import datetime
import json
import logging
from dataclasses import InitVar, dataclass, field
from typing import Optional

import httpx

from pysmarthashtag.api import utils
from pysmarthashtag.api.authentication import SmartAuthentication, SmartLoginClient
from pysmarthashtag.api.client import SmartClient, SmartClientConfiguration
from pysmarthashtag.api.log_sanitizer import sanitize_log_data
from pysmarthashtag.const import API_CARS_URL, API_SELECT_CAR_URL, EndpointUrls, SmartAuthMode
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

    vehicles: dict[str, SmartVehicle] = field(default_factory=dict, init=False)
    """Vehicles associated with the account."""

    def __post_init__(self, password, log_responses):
        """Initialize the account."""
        # Ensure endpoint_urls is set
        if self.endpoint_urls is None:
            self.endpoint_urls = EndpointUrls()

        if self.config is None:
            self.config = SmartClientConfiguration(
                SmartAuthentication(self.username, password, endpoint_urls=self.endpoint_urls),
                log_responses=log_responses,
            )

    def _is_global_auth(self) -> bool:
        """Return True when using the Global app authentication mode."""
        return self.config.authentication.auth_mode == SmartAuthMode.GLOBAL_HMAC

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
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
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

    async def _init_vehicles_global(self) -> None:
        """Initialize vehicles from Smart Global servers."""
        _LOGGER.debug("Getting initial vehicle list (global)")
        await self._ensure_ssl_context()

        fetched_at = datetime.datetime.now(datetime.timezone.utc)
        async with SmartLoginClient(ssl_context=self.config.ssl_context) as client:
            path = "/vc/vehicle/v1/ownership/list"
            body = json.dumps({})
            host = httpx.URL(self.endpoint_urls.get_api_base_url()).host
            headers = utils.generate_global_header(
                method="POST",
                path=path,
                host=host,
                app_key=self.endpoint_urls.get_global_app_key(),
                app_secret=self.endpoint_urls.get_global_app_secret(),
                body=body,
                access_token=self.config.authentication.access_token,
                user_id=self.config.authentication.api_user_id,
                id_token=self.config.authentication.id_token,
            )
            vehicles_response = await client.post(
                self.endpoint_urls.get_api_base_url() + path,
                headers=headers,
                content=body,
            )
            data = vehicles_response.json()
            vehicles = data.get("result") or data.get("data") or []
            for vehicle in vehicles:
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
            if self._is_global_auth():
                await self._init_vehicles_global()
            else:
                await self._init_vehicles()

        if self._is_global_auth():
            await self._update_global_vehicle_details()
            return

        for vin, vehicle in self.vehicles.items():
            _LOGGER.debug("Getting vehicle data")
            await self.select_active_vehicle(vin)
            vehicle_info = await self.get_vehicle_information(vin)
            vehicle_soc = await self.get_vehicle_soc(vin)
            vehicle_ota_info = await self.get_vehicle_ota_info(vin)
            vehicle.combine_data(vehicle_info, charging_settings=vehicle_soc, ota_info=vehicle_ota_info)

    async def select_active_vehicle(self, vin) -> None:
        """Select the active vehicle."""
        if self._is_global_auth():
            return
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
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
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
        if self._is_global_auth():
            return await self._get_vehicle_details_global(vin)
        _LOGGER.debug("Getting information for vehicle")
        params = {
            "latest": True,
            "target": "basic%2Cmore",
            "userId": self.config.authentication.api_user_id,
        }
        data = {}
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    r_car_info = await client.get(
                        self.vehicles[vin].base_url
                        + "/remote-control/vehicle/status/"
                        + vin
                        + "?"
                        + utils.join_url_params(params),
                        headers={
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params=params,
                                method="GET",
                                url="/remote-control/vehicle/status/" + vin,
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
        if self._is_global_auth():
            return {}
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
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
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
        if self._is_global_auth():
            return {}
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

    async def _update_global_vehicle_details(self) -> None:
        """Fetch global vehicle details and abilities."""
        for vin in list(self.vehicles.keys()):
            await self._get_vehicle_details_global(vin)
            await self._get_vehicle_abilities_global(vin)

    async def _get_vehicle_details_global(self, vin) -> dict:
        """Get global vehicle details."""
        _LOGGER.debug("Getting global vehicle details")
        await self._ensure_ssl_context()
        async with SmartLoginClient(ssl_context=self.config.ssl_context) as client:
            path = "/vc/vehicle/v1/vehicleCustomerInfo"
            body = json.dumps({"vin": vin})
            host = httpx.URL(self.endpoint_urls.get_api_base_url()).host
            headers = utils.generate_global_header(
                method="POST",
                path=path,
                host=host,
                app_key=self.endpoint_urls.get_global_app_key(),
                app_secret=self.endpoint_urls.get_global_app_secret(),
                body=body,
                access_token=self.config.authentication.access_token,
                user_id=self.config.authentication.api_user_id,
                id_token=self.config.authentication.id_token,
            )
            response = await client.post(
                self.endpoint_urls.get_api_base_url() + path,
                headers=headers,
                content=body,
            )
            data = response.json()
            details = data.get("result") or data.get("data") or []
            if isinstance(details, list):
                details = details[0] if details else {}
            if details:
                self.vehicles.get(vin).combine_data(details)
            return details or {}

    async def _get_vehicle_abilities_global(self, vin) -> dict:
        """Get global vehicle abilities."""
        _LOGGER.debug("Getting global vehicle abilities")
        await self._ensure_ssl_context()
        vehicle = self.vehicles.get(vin)
        model_code = vehicle.data.get("modelCode") if vehicle else None
        if not model_code:
            return {}
        async with SmartLoginClient(ssl_context=self.config.ssl_context) as client:
            path = f"/vc/vehicle/v1/ability/{model_code}/{vin}"
            host = httpx.URL(self.endpoint_urls.get_api_base_url()).host
            headers = utils.generate_global_header(
                method="GET",
                path=path,
                host=host,
                app_key=self.endpoint_urls.get_global_app_key(),
                app_secret=self.endpoint_urls.get_global_app_secret(),
                access_token=self.config.authentication.access_token,
                user_id=self.config.authentication.api_user_id,
                id_token=self.config.authentication.id_token,
            )
            response = await client.get(
                self.endpoint_urls.get_api_base_url() + path,
                headers=headers,
            )
            data = response.json()
            abilities = data.get("result") or data.get("data") or {}
            if abilities and vehicle:
                vehicle.data["abilities"] = abilities
            return abilities or {}
