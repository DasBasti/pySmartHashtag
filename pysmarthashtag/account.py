"""Access to Smart account for your vehicles therin."""

import datetime
import json
import logging
from dataclasses import InitVar, dataclass, field
from typing import Optional

import httpx

from pysmarthashtag.api import utils
from pysmarthashtag.api.authentication import SmartAuthentication
from pysmarthashtag.api.client import SmartClient, SmartClientConfiguration
from pysmarthashtag.api.log_sanitizer import sanitize_log_data
from pysmarthashtag.const import API_CARS_URL, API_SELECT_CAR_URL, EndpointUrls
from pysmarthashtag.models import SmartAuthError, SmartHumanCarConnectionError, SmartTokenRefreshNecessary
from pysmarthashtag.vehicle.trackpoints import TripTrackpoints, parse_trackpoints_response
from pysmarthashtag.vehicle.vehicle import SmartVehicle

# Path prefix for the per-trip GPS trackpoints endpoint. Cloud-side
# service is ``vehicle-history-service / journal-service`` (same
# ``apiv2.ecloudeu.com`` host as journalLogV4); the trailing ``history``
# segment is the cloud's own naming.
TRIP_TRACKPOINTS_PATH_PREFIX = "/vehicle-history-service/journal-service/vehicle/status/history/"

# Default page size for the trackpoints endpoint, matching the cap the
# cloud advertises in its own ``pagination`` block. In observed responses
# ``totleSize`` never exceeded this cap; the wrapper logs a WARNING if it
# ever does so a future maintainer knows to add pagination here.
TRIP_TRACKPOINTS_PAGE_SIZE = 500

# Cloud status code returned by both journalLogV4 and the trackpoints
# endpoint when there's no data to report. The SDK raises
# :class:`httpx.HTTPStatusError` for any non-1000 code with a
# ``message`` key; 8153 surfaces here so callers can normalise it to an
# empty result without propagating to the caller.
_BENIGN_EMPTY_CODE = "8153"

VALID_UNTIL_OFFSET = datetime.timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


def _is_benign_empty(exc: httpx.HTTPStatusError) -> bool:
    """Return True iff ``exc`` carries the cloud's 8153 "data unavailable" code.

    The SDK's :func:`raise_for_status_event_handler` raises for any
    non-1000 ``code`` with a ``message`` key. ``8153`` is the cloud's
    end-of-data signal for journal endpoints — callers normalise it to
    an empty result rather than propagating it as an error.
    """
    response = exc.response
    if response is None:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    return str(body.get("code")) == _BENIGN_EMPTY_CODE


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

    _journal_grant_cache: dict[str, str] = field(default_factory=dict, init=False)
    """Per-VIN cache of the access_token under which the trip-journal
    authorization grant was last accepted. ``{vin: access_token_string}``.
    Used to skip the redundant grant POST when the same token is still
    valid; auto-invalidates as soon as the token rotates (any reason —
    expiry, manual relogin, future refresh-token flow). Maintained by
    :meth:`grant_journal_authorization`.
    """

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
            # Trip journal is best-effort: the endpoint can return 8153
            # ("data unavailable") on vehicles where on-vehicle trip
            # recording is OFF, or transiently when the per-session auth
            # grant hasn't been accepted yet. Never let an empty journal
            # fail the whole refresh.
            journal_response = None
            try:
                journal_response = await self.get_trip_journal(vin)
            except Exception:  # noqa: BLE001  # Best-effort: any failure (8153, transport, parse) must not break refresh.
                _LOGGER.debug(
                    "Trip journal fetch failed for %s", sanitize_log_data(vin), exc_info=True
                )
            vehicle.combine_data(
                vehicle_info,
                charging_settings=vehicle_soc,
                ota_info=vehicle_ota_info,
                journal_response=journal_response,
            )

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
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params={},
                                method="POST",
                                url=API_SELECT_CAR_URL,
                                body=data,
                            )
                        },
                        content=data.encode("utf-8"),
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

    async def grant_journal_authorization(self, vin, force: bool = False) -> bool:
        """Grant cloud-side authorization for trip-journal data access.

        ``POST /remote-control/user/authorization/insert`` with
        ``{"serviceCode": "travelLogBusiCode", "authStatus": 1, "vin": <vin>}``.
        This is a per-session handshake that unlocks the journalLogV4
        endpoint — without it, journalLogV4 returns ``code: 8153``
        ("data unavailable") even on vehicles where the on-vehicle
        recording flag is set and trip data exists cloud-side.

        Cached per-VIN per-access-token. The grant POST is observed to
        rotate the access_token server-side (every poll without the cache
        returns ``1402 token invalid`` on the next call, forcing a
        re-login). The cache stores the access_token under which the
        grant was accepted; subsequent calls under the *same* token
        skip the redundant POST. The cache auto-invalidates as soon as
        the token rotates (relogin, refresh, expiry — any reason).

        Args:
            vin: Vehicle identification number.
            force: If True, ignore the cache and re-issue the grant.
                Use this for explicit init flows where you want to be
                certain the grant is fresh.

        Returns:
            True if the grant succeeded (or was already cached);
            False if the POST failed.

        """
        token = self.config.authentication.api_access_token
        if not force and token and self._journal_grant_cache.get(vin) == token:
            _LOGGER.debug(
                "Journal authorization cached for %s under current token; skipping POST",
                sanitize_log_data(vin),
            )
            return True

        _LOGGER.debug("Granting journal authorization for %s", sanitize_log_data(vin))
        path = "/remote-control/user/authorization/insert"
        body = json.dumps({"serviceCode": "travelLogBusiCode", "authStatus": 1, "vin": vin})
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    r = await client.post(
                        self.vehicles[vin].base_url + path,
                        headers={
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params={},
                                method="POST",
                                url=path,
                                body=body,
                            )
                        },
                        content=body.encode("utf-8"),
                    )
                    payload = r.json()
                    success = bool(payload.get("success") or payload.get("code") == "1000")
                    if success:
                        # Record the token under which this grant was accepted.
                        # Re-read after the POST since the server may have rotated
                        # it during the call.
                        self._journal_grant_cache[vin] = (
                            self.config.authentication.api_access_token
                        )
                    return success
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Token refresh needed during auth-grant retry %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Human-car connection error during auth-grant retry %d", retry)
                    await self.select_active_vehicle(vin)
                    continue
                break
        return False

    async def get_trip_journal(self, vin, page_size: int = 20, window_days: int = 14) -> dict:
        """Fetch the most recent trip-journal entries for a vehicle.

        Hits ``/geelyTCAccess/tcservices/vehicle/status/journalLogV4/{vin}``
        — the endpoint that carries server-side reverse-geocoded start/end
        addresses alongside per-trip energy/distance/speed metrics.

        Sends ``startTime`` / ``endTime`` (ms-epoch window), ``pageIndex``,
        ``pageSize``, and ``userId`` as query params. The endpoint requires
        a per-session authorization grant
        (:meth:`grant_journal_authorization`), which this method calls
        first; without it the endpoint returns ``code: 8153``. The grant
        is cached per-VIN per-access-token, so subsequent calls under the
        same token skip the grant POST.

        Returns the raw response dict (with ``code``/``message``/``data``)
        or an empty dict when the request fails server-side; raising is
        avoided so a single flaky vehicle doesn't break the whole refresh.
        """
        await self.grant_journal_authorization(vin)
        _LOGGER.debug("Getting trip journal for vehicle")
        end_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        start_ms = end_ms - window_days * 86400 * 1000
        params = {
            "endTime": str(end_ms),
            "pageIndex": "1",
            "pageSize": str(page_size),
            "startTime": str(start_ms),
            "userId": str(self.config.authentication.api_user_id),
        }
        path = "/geelyTCAccess/tcservices/vehicle/status/journalLogV4/" + vin
        url = path + "?" + utils.join_url_params(params)
        data: dict = {}
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    r_journal = await client.get(
                        self.vehicles[vin].base_url + url,
                        headers={
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params=params,
                                method="GET",
                                url=path,
                            )
                        },
                    )
                    _LOGGER.debug("Got response %d", r_journal.status_code)
                    data = r_journal.json()
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    await self.select_active_vehicle(vin)
                    continue
                break
        return data

    async def get_trip_trackpoints(
        self,
        vin: str,
        start_time_ms: int,
        end_time_ms: int,
        page_size: int = TRIP_TRACKPOINTS_PAGE_SIZE,
    ) -> TripTrackpoints:
        """Fetch the per-trip GPS trackpoints for one finished trip.

        Hits ``/vehicle-history-service/journal-service/vehicle/status/history/{vin}``
        on the same host as journalLogV4, with the ``(startTime, endTime)``
        window identifying the trip (the cloud has no separate trip-id
        for this endpoint — the time window IS the identifier).

        Unlike :meth:`get_trip_journal`, this endpoint does NOT require
        :meth:`grant_journal_authorization` — calling that defensively
        before each fetch would burn an extra cloud round-trip per trip.
        The minimum required flow is auth (already done by
        :meth:`get_vehicles` at session startup) plus the single signed
        ``GET`` to ``/.../history/{VIN}``.

        Cloud direction is ``desc`` (newest-first); the returned
        :attr:`TripTrackpoints.points` are reversed to chronological
        order so callers don't need to know the wire format.

        Three benign-empty cloud responses all map to
        ``TripTrackpoints(points=[], total_size=0)``:

        * ``code: "1000"`` with ``data.list = []``
        * ``code: "1000"`` with ``data: null``
        * ``code: "8153"`` ("data unavailable" — surfaces as
          :class:`httpx.HTTPStatusError` from the SDK)

        Other ``HTTPStatusError`` exceptions (cloud 5xx, network,
        non-1402 auth failure) propagate up so the caller can decide
        whether to retry or surface the error.

        Pagination is intentionally NOT implemented: the cloud's own
        ``pagination`` block reports ``pageSize=500`` as the cap, and in
        observed responses ``totleSize`` never exceeded it. If a future
        trip ever does, this method logs a WARNING so we know to revisit.
        """
        _LOGGER.debug("Getting trip trackpoints for vehicle")
        params = {
            "endTime": str(end_time_ms),
            "pageIndex": "0",
            "pageSize": str(page_size),
            "source": "tc",
            "startTime": str(start_time_ms),
        }
        path = TRIP_TRACKPOINTS_PATH_PREFIX + vin
        url = path + "?" + utils.join_url_params(params)
        async with SmartClient(self.config) as client:
            for retry in range(3):
                try:
                    response = await client.get(
                        self.vehicles[vin].base_url + url,
                        headers={
                            **utils.generate_default_header(
                                client.config.authentication.device_id,
                                client.config.authentication.api_access_token,
                                params=params,
                                method="GET",
                                url=path,
                            )
                        },
                    )
                    _LOGGER.debug("Got response %d", response.status_code)
                    body = response.json()
                except SmartTokenRefreshNecessary:
                    _LOGGER.debug("Got Token Error, retry: %d", retry)
                    continue
                except SmartHumanCarConnectionError:
                    _LOGGER.debug("Got Human Car Connection Error, retry: %d", retry)
                    await self.select_active_vehicle(vin)
                    continue
                except httpx.HTTPStatusError as exc:
                    if _is_benign_empty(exc):
                        _LOGGER.debug(
                            "trackpoints endpoint returned 8153 (data unavailable) for %s; treating as empty",
                            sanitize_log_data(vin),
                        )
                        return TripTrackpoints(points=[], total_size=0)
                    raise
                break
        trackpoints = parse_trackpoints_response(body)
        if trackpoints.total_size > page_size:
            _LOGGER.warning(
                "Trackpoints page-size cap exceeded for %s: totleSize=%d > pageSize=%d. "
                "Wrapper does not loop pageIndex; returned points are the head only. "
                "Add pagination if this fires for real trips.",
                sanitize_log_data(vin),
                trackpoints.total_size,
                page_size,
            )
        return trackpoints

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
