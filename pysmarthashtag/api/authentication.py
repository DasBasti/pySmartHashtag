"""Authentication management for Smart APIs."""

import asyncio
import datetime
import json
import logging
import math
import secrets
from collections import defaultdict
from typing import AsyncGenerator, Generator, Optional

import httpx
from httpx._models import Request, Response

from pysmarthashtag.api import utils
from pysmarthashtag.const import (
    API_BASE_URL,
    API_KEY,
    API_SESION_URL,
    AUTH_URL,
    CONTEXT_URL,
    HTTPX_TIMEOUT,
    LOGIN_URL,
)
from pysmarthashtag.models import SmartAPIError

EXPIRES_AT_OFFSET = datetime.timedelta(seconds=HTTPX_TIMEOUT * 2)

_LOGGER = logging.getLogger(__name__)


class SmartAuthentication(httpx.Auth):
    """Authentication and Retry Handler for the Smart API."""

    def __init__(
        self,
        username: str,
        password: str,
        access_token: Optional[str] = None,
        expires_at: Optional[datetime.datetime] = None,
        refresh_token: Optional[str] = None,
    ):
        self.username: str = username
        self.password: str = password
        self.access_token: Optional[str] = access_token
        self.expires_at: Optional[datetime.datetime] = expires_at
        self.refresh_token: Optional[str] = refresh_token
        self.device_id: str = secrets.token_hex(8)
        self._lock: Optional[asyncio.Lock] = None
        self.api_access_token: Optional[str] = None
        self.api_refresh_token: Optional[str] = None
        self.api_user_id: Optional[str] = None
        _LOGGER.debug("Device ID: %s", self.device_id)

    @property
    def login_lock(self) -> asyncio.Lock:
        """Make sure there is only one login at a time."""
        if not self._lock:
            self._lock = asyncio.Lock()
        return self._lock

    def sync_auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Handle synchronous authentication flow for requests."""
        raise RuntimeError("Cannot use an async authentication class with httpx.Client")

    async def async_auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        """Asynchronous authentication flow for handling requests."""
        _LOGGER.debug("Handling request %s", request.url)
        # Get an initial login on first call
        async with self.login_lock:
            if not self.access_token:
                await self.login()
        request.headers["Authorization"] = f"Bearer {self.access_token}"

        response: httpx.Response = yield request

        if response.is_success:
            return

        await response.aread()

        retry_count = 0
        while (
            response.status_code == 429 or (response.status_code == 403 and "quota" in response.text.lower())
        ) and retry_count < 3:
            wait_time = get_retry_wait_time(response)
            _LOGGER.debug("Rate limit exceeded. Waiting %s seconds", wait_time)
            await asyncio.sleep(wait_time)
            response = yield request
            await response.aread()
            retry_count += 1

        if response.status_code == 401:
            async with self.login_lock:
                _LOGGER.debug("Token expired. Refreshing token")
                await self.login()
                request.headers["Authorization"] = f"Bearer {self.access_token}"

            _LOGGER.debug("Token expired. Refreshing token")
            await self.login()
            request.headers["Authorization"] = f"Bearer {self.access_token}"
            response = yield request
            await response.aread()

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _LOGGER.error(
                "Error handling request %s: %s",
                request.url,
                exc,
            )
            raise

    async def login(self) -> None:
        """Login to the Smart API."""
        _LOGGER.debug("Logging in to Smart API")
        token_data = {}
        if self.refresh_token:
            token_data = await self._refresh_access_token()
        if not token_data:
            token_data = await self._login()
        try:
            token_data["expires_at"] = token_data["expires_at"] - EXPIRES_AT_OFFSET

            self.access_token = token_data["access_token"]
            self.refresh_token = token_data["refresh_token"]
            self.api_access_token = token_data["api_access_token"]
            self.api_refresh_token = token_data["api_refresh_token"]
            self.api_user_id = token_data["api_user_id"]
            self.expires_at = token_data["expires_at"]
            _LOGGER.debug(f"Login successful: {token_data}")
            return True
        except KeyError:
            raise SmartAPIError("Could not login to Smart API")

    async def _refresh_access_token(self):
        """Refresh the access token."""
        try:
            async with SmartLoginClient() as _:
                _LOGGER.debug("Refreshing access token via relogin because refresh token is not implemented")
                await self._login()
        except SmartAPIError:
            _LOGGER.debug("Refreshing access token failed. Logging in again")
            return {}

    async def _login(self):
        """Login to Smart web services."""
        async with SmartLoginClient() as client:
            _LOGGER.info("Aquiring access token.")

            # Get Context
            r_context = await client.get(
                CONTEXT_URL,
                headers={
                    "x-app-id": "SmartAPPEU",
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                    "x-requested-with": "com.smart.hellosmart",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "content-type": "application/json; charset=utf-8",
                },
                follow_redirects=True,
            )
            try:
                context = r_context.url.params["context"]
                _LOGGER.debug("Context: %s", context)
            except KeyError:
                raise SmartAPIError("Could not get context from login page")

            # Get login token from Smart API
            r_login = await client.post(
                LOGIN_URL,
                data={
                    "loginID": self.username,
                    "password": self.password,
                    "sessionExpiration": 2592000,
                    "targetEnv": "jssdk",
                    "include": "profile%2Cdata%2Cemails%2Csubscriptions%2Cpreferences%2C",
                    "includeUserInfo": True,
                    "loginMode": "standard",
                    "lang": "de",
                    "APIKey": API_KEY,
                    "source": "showScreenSet",
                    "sdk": "js_latest",
                    "pageURL": "https%3A%2F%2Fapp.id.smart.com%2Flogin%3Fgig_ui_locales%3Dde-DE",
                    "sdkBuild": 15482,
                    "format": "json",
                    "riskContext": "%7B%22b0%22%3A41187%2C%22b1%22%3A%5B0%2C2%2C3%2C1%5D%2C%22b2%22%3A4%2C%22b3%22%3A%5B%22-23%7C0.383%22%2C%22-81.33333587646484%7C0.236%22%5D%2C%22b4%22%3A3%2C%22b5%22%3A1%2C%22b6%22%3A%22Mozilla%2F5.0%20%28Linux%3B%20Android%209%3B%20ANE-LX1%20Build%2FHUAWEIANE-L21%3B%20wv%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Version%2F4.0%20Chrome%2F118.0.0.0%20Mobile%20Safari%2F537.36%22%2C%22b7%22%3A%5B%5D%2C%22b8%22%3A%2216%3A33%3A26%22%2C%22b9%22%3A-60%2C%22b10%22%3Anull%2C%22b11%22%3Afalse%2C%22b12%22%3A%7B%22charging%22%3Atrue%2C%22chargingTime%22%3Anull%2C%22dischargingTime%22%3Anull%2C%22level%22%3A0.58%7D%2C%22b13%22%3A%5B5%2C%22360%7C760%7C24%22%2Cfalse%2Ctrue%5D%7D",
                },
                headers={
                    "accept": "*/*",
                    "accept-language": "de",
                    "content-type": "application/x-www-form-urlencoded",
                    "x-requested-with": "com.smart.hellosmart",
                    "cookie": "gmid=gmid.ver4.AcbHPqUK5Q.xOaWPhRTb7gy-6-GUW6cxQVf_t7LhbmeabBNXqqqsT6dpLJLOWCGWZM07EkmfM4j.u2AMsCQ9ZsKc6ugOIoVwCgryB2KJNCnbBrlY6pq0W2Ww7sxSkUa9_WTPBIwAufhCQYkb7gA2eUbb6EIZjrl5mQ.sc3; ucid=hPzasmkDyTeHN0DinLRGvw; hasGmid=ver4; gig_bootstrap_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a=auth_ver4",
                    "origin": "https://app.id.smart.com",
                    "user-agent": "Hello smart/1.4.0 (iPhone; iOS 17.1; Scale/3.00)",
                },
            )
            try:
                login_result = r_login.json()
                login_token = login_result["sessionInfo"]["login_token"]
                expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                    seconds=int(login_result["sessionInfo"]["expires_in"])
                )
            except (KeyError, ValueError):
                raise SmartAPIError("Could not get login token from login page")

            auth_url = AUTH_URL + "?context=" + context + "&login_token=" + login_token
            cookie = f"gmid=gmid.ver4.AcbHPqUK5Q.xOaWPhRTb7gy-6-GUW6cxQVf_t7LhbmeabBNXqqqsT6dpLJLOWCGWZM07EkmfM4j.u2AMsCQ9ZsKc6ugOIoVwCgryB2KJNCnbBrlY6pq0W2Ww7sxSkUa9_WTPBIwAufhCQYkb7gA2eUbb6EIZjrl5mQ.sc3; ucid=hPzasmkDyTeHN0DinLRGvw; hasGmid=ver4; gig_bootstrap_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a=auth_ver4; glt_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a={login_token}"
            r_auth = await client.get(
                auth_url,
                headers={
                    "accept": "*/*",
                    "cookie": cookie,
                    "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                    "x-requested-with": "com.smart.hellosmart",
                    "user-agent": "Mozilla/5.0 (Linux; Android 9; ANE-LX1 Build/HUAWEIANE-L21; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36",
                },
            )
            if "location" not in r_auth.headers:
                raise SmartAPIError("Could not get location from auth page")

            r_auth = await client.get(
                r_auth.headers["location"],
                headers={
                    "accept": "*/*",
                    "cookie": cookie,
                    "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                    "x-requested-with": "com.smart.hellosmart",
                    "user-agent": "Mozilla/5.0 (Linux; Android 9; ANE-LX1 Build/HUAWEIANE-L21; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36",
                },
            )
            try:
                auth_result = httpx.URL(r_auth.headers["location"])
                access_token = auth_result.params["access_token"]
                refresh_token = auth_result.params["refresh_token"]
            except KeyError:
                raise SmartAPIError("Could not get access token from auth page")

            data = json.dumps({"accessToken": access_token}).replace(" ", "")
            r_api_access = await client.post(
                API_BASE_URL + API_SESION_URL + "?identity_type=smart",
                headers={
                    **utils.generate_default_header(
                        self.device_id,
                        None,
                        params={
                            "identity_type": "smart",
                        },
                        method="POST",
                        url=API_SESION_URL,
                        body=data,
                    )
                },
                data=data,
            )
            api_result = r_api_access.json()
            _LOGGER.debug("API access result: %s", api_result)
            try:
                api_access_token = api_result["data"]["accessToken"]
                api_refresh_token = api_result["data"]["refreshToken"]
                api_user_id = api_result["data"]["userId"]
            except KeyError:
                raise SmartAPIError("Could not get API access token from API")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "api_access_token": api_access_token,
            "api_refresh_token": api_refresh_token,
            "api_user_id": api_user_id,
            "expires_at": expires_at,
        }


class SmartLoginClient(httpx.AsyncClient):
    """Client to login to the Smart API."""

    def __init__(self, *args, **kwargs):
        # Increase timeout to 30 seconds
        kwargs["timeout"] = httpx.Timeout(HTTPX_TIMEOUT)

        # Register event hooks
        kwargs["event_hooks"] = defaultdict(list, **kwargs.get("event_hooks", {}))

        # Event hook for raise_for_status on all requests
        async def raise_for_status_handler(response: httpx.Response):
            """Eventhandler that automaticvalle raises HTTPStatusError when attached to a request.

            Only raise on 4xx/5xx errors but not on 429.
            """
            if response.is_error and response.status_code != 429:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    _LOGGER.error(
                        "Error handling request %s: %s",
                        response.url,
                        exc,
                    )
                    raise

        kwargs["event_hooks"]["response"].append(raise_for_status_handler)

        async def log_request(request):
            if request.method == "POST":
                await request.aread()
                _LOGGER.debug(
                    f"Request: {request.method} {request.url} - {request.content.decode()} - {request.headers}"
                )
            else:
                _LOGGER.debug(f"Request: {request.method} {request.url}")

        async def log_response(response):
            await response.aread()
            request = response.request
            _LOGGER.debug(f"Response: {request.method} {request.url} - Status {response.status_code}")

        kwargs["event_hooks"]["response"].append(log_response)
        kwargs["event_hooks"]["request"].append(log_request)

        super().__init__(**kwargs)


class SmartLoginRetry(httpx.Auth):
    """httpx.Auth uses as waorkauround to retry and sleep in 429."""

    def sync_auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        raise RuntimeError("Cannot use a async authentication class with httpx.Client")

    async def async_auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        # Try getting a response
        response: httpx.Response = yield request

        for _ in range(3):
            if response.status_code == 429:
                await response.aread()
                wait_time = get_retry_wait_time(response)
                _LOGGER.debug("Rate limit exceeded. Waiting %s seconds", wait_time)
                await asyncio.sleep(wait_time)
                response = yield request

                # Only checking for 429 errors, all other errors are raised in SmartLoginClient
                if response.status_code == 429:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        _LOGGER.error(
                            "Error handling request %s: %s",
                            request.url,
                            exc,
                        )
                        raise


def get_retry_wait_time(response: httpx.Response) -> int:
    """Get the wait time to wait twice as long before retrying."""
    try:
        retry_after = next(iter([int(i) for i in response.json().get("message", "") if i.isdigit()]))
    except Exception:
        retry_after = 2
    return math.ceil(retry_after * 2)
