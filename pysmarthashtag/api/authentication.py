"""Authentication management for Smart APIs."""

import asyncio
import datetime
import json
import logging
import math
import secrets
import ssl
from collections import defaultdict
from collections.abc import AsyncGenerator, Generator
from typing import Optional

import httpx
from httpx._models import Request, Response

from pysmarthashtag.api import utils
from pysmarthashtag.api.log_sanitizer import sanitize_log_data
from pysmarthashtag.const import (
    API_SESION_URL,
    HTTPX_TIMEOUT,
    EndpointUrls,
    SmartAuthMode,
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
        ssl_context: Optional[ssl.SSLContext] = None,
        endpoint_urls: Optional[EndpointUrls] = None,
    ):
        """
        Initialize the authentication manager with credentials, optional tokens, SSL context, and endpoint configuration.
        
        Parameters:
            username (str): Account username used for authentication.
            password (str): Account password used for authentication.
            access_token (Optional[datetime.datetime]): Existing OAuth access token, if available.
            expires_at (Optional[datetime.datetime]): Expiration time of `access_token`; used to determine when refresh/login is needed.
            refresh_token (Optional[str]): Refresh token associated with `access_token`, if available.
            ssl_context (Optional[ssl.SSLContext]): Optional SSL context to use for login requests to avoid creating one lazily.
            endpoint_urls (Optional[EndpointUrls]): Endpoint configuration; if omitted a default is created and the authentication mode is inferred from it.
        
        Behavior:
            Stores provided values on the instance, generates a random device identifier, initializes internal locks and API session token placeholders, and sets `auth_mode` by inferring it from `endpoint_urls`.
        """
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
        self.id_token: Optional[str] = None
        self.ssl_context: Optional[ssl.SSLContext] = ssl_context
        self.endpoint_urls: EndpointUrls = endpoint_urls if endpoint_urls is not None else EndpointUrls()
        self.auth_mode: SmartAuthMode = self.endpoint_urls.infer_auth_mode()
        _LOGGER.debug("Device ID initialized")

    async def get_ssl_context(self) -> ssl.SSLContext:
        """
        Obtain the SSLContext used for secure connections, creating and caching it if necessary.
        
        This method returns the cached SSLContext when present; otherwise it asynchronously acquires a new SSLContext and stores it for subsequent calls. The operation is safe for concurrent callers.
        
        Returns:
            ssl.SSLContext: SSL context configured for secure HTTP connections.
        """
        if self.ssl_context is None:
            # Import here to avoid circular imports
            from pysmarthashtag.api.ssl_context import get_ssl_context_async

            self.ssl_context = await get_ssl_context_async()
        return self.ssl_context

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
        """Asynchronous authentication flow for handling requests and retrying on rate limit errors."""
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
        """
        Perform authentication with the Smart API and store retrieved tokens and expiry.
        
        Attempts to refresh the access token when a refresh token is available; otherwise performs a full login. On success, normalizes and stores `access_token`, `refresh_token`, `api_access_token`, `api_refresh_token`, `api_user_id`, optional `id_token`, and `expires_at` (adjusted by EXPIRES_AT_OFFSET) on the instance.
        
        Raises:
            SmartAPIError: If required token fields are missing from the login response.
        """
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
            self.id_token = token_data.get("id_token")
            self.expires_at = token_data["expires_at"]
            _LOGGER.debug("Login successful")
            return True
        except KeyError:
            raise SmartAPIError("Could not login to Smart API")

    async def _refresh_access_token(self):
        """
        Attempt to refresh the stored access (and related) tokens using the configured authentication mode.
        
        Tries a mode-specific refresh (global HMAC refresh when configured, otherwise the EU refresh). If the refresh succeeds, returns a dict with refreshed token data (e.g., `access_token`, `refresh_token`, `expires_at`, and optional `id_token`); if the refresh fails, returns an empty dict to indicate a full login is required.
        """
        if self.auth_mode == SmartAuthMode.GLOBAL_HMAC:
            try:
                return await self._refresh_access_token_global()
            except (SmartAPIError, httpx.HTTPError, ValueError):
                _LOGGER.debug("Refreshing access token failed. Logging in again")
                return {}

        try:
            return await self._refresh_access_token_eu()
        except (SmartAPIError, httpx.HTTPError, ValueError):
            _LOGGER.debug("Refreshing access token failed. Logging in again")
            return {}

    async def _login(self):
        """
        Selects and executes the appropriate login flow for the configured authentication mode.
        
        Dispatches to the global HMAC login when auth_mode is SmartAuthMode.GLOBAL_HMAC; otherwise runs the EU OAuth login flow.
        
        Returns:
            token_data (dict): Authentication tokens and related metadata such as `access_token`, `refresh_token`, `expires_at`, and optionally `id_token` and API session fields.
        """
        if self.auth_mode == SmartAuthMode.GLOBAL_HMAC:
            return await self._login_global()
        return await self._login_eu()

    async def _login_eu(self):
        """
        Perform the EU OAuth login flow, exchange the OAuth access token for API session tokens, and return the resulting tokens and expiry.
        
        Returns:
            dict: Mapping with the following keys:
                access_token (str): OAuth access token obtained from the authorization redirect.
                refresh_token (str): OAuth refresh token obtained from the authorization redirect.
                api_access_token (str): API session access token exchanged from the OAuth access token.
                api_refresh_token (str): API session refresh token exchanged from the OAuth access token.
                api_user_id (str): User identifier returned by the API session exchange.
                expires_at (datetime.datetime): UTC timestamp when the OAuth access token expires.
        
        Raises:
            SmartAPIError: If the login context, login token, redirect location, or access/refresh tokens cannot be obtained.
        """
        ssl_ctx = await self.get_ssl_context()
        async with SmartLoginClient(ssl_context=ssl_ctx) as client:
            _LOGGER.info("Acquiring access token.")

            # Get Context
            r_context = await client.get(
                self.endpoint_urls.get_server_url(),
                headers={
                    "x-app-id": "SmartAPPEU",
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",  # noqa: E501
                    "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                    "x-requested-with": "com.smart.hellosmart",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",  # noqa: E501
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
                self.endpoint_urls.get_login_url(),
                data={
                    "loginID": self.username,
                    "password": self.password,
                    "sessionExpiration": 2592000,
                    "targetEnv": "jssdk",
                    "include": "profile%2Cdata%2Cemails%2Csubscriptions%2Cpreferences%2C",
                    "includeUserInfo": True,
                    "loginMode": "standard",
                    "lang": "de",
                    "APIKey": self.endpoint_urls.get_api_key(),
                    "source": "showScreenSet",
                    "sdk": "js_latest",
                    "pageURL": "https%3A%2F%2Fapp.id.smart.com%2Flogin%3Fgig_ui_locales%3Dde-DE",
                    "sdkBuild": 15482,
                    "format": "json",
                    "riskContext": "%7B%22b0%22%3A41187%2C%22b1%22%3A%5B0%2C2%2C3%2C1%5D%2C%22b2%22%3A4%2C%22b3%22%3A%5B%22-23%7C0.383%22%2C%22-81.33333587646484%7C0.236%22%5D%2C%22b4%22%3A3%2C%22b5%22%3A1%2C%22b6%22%3A%22Mozilla%2F5.0%20%28Linux%3B%20Android%209%3B%20ANE-LX1%20Build%2FHUAWEIANE-L21%3B%20wv%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Version%2F4.0%20Chrome%2F118.0.0.0%20Mobile%20Safari%2F537.36%22%2C%22b7%22%3A%5B%5D%2C%22b8%22%3A%2216%3A33%3A26%22%2C%22b9%22%3A-60%2C%22b10%22%3Anull%2C%22b11%22%3Afalse%2C%22b12%22%3A%7B%22charging%22%3Atrue%2C%22chargingTime%22%3Anull%2C%22dischargingTime%22%3Anull%2C%22level%22%3A0.58%7D%2C%22b13%22%3A%5B5%2C%22360%7C760%7C24%22%2Cfalse%2Ctrue%5D%7D",  # noqa: E501
                },
                headers={
                    "accept": "*/*",
                    "accept-language": "de",
                    "content-type": "application/x-www-form-urlencoded",
                    "x-requested-with": "com.smart.hellosmart",
                    "cookie": "gmid=gmid.ver4.AcbHPqUK5Q.xOaWPhRTb7gy-6-GUW6cxQVf_t7LhbmeabBNXqqqsT6dpLJLOWCGWZM07EkmfM4j.u2AMsCQ9ZsKc6ugOIoVwCgryB2KJNCnbBrlY6pq0W2Ww7sxSkUa9_WTPBIwAufhCQYkb7gA2eUbb6EIZjrl5mQ.sc3; ucid=hPzasmkDyTeHN0DinLRGvw; hasGmid=ver4; gig_bootstrap_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a=auth_ver4",  # noqa: E501
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

            auth_url = self.endpoint_urls.get_auth_url() + "?context=" + context + "&login_token=" + login_token
            cookie = f"gmid=gmid.ver4.AcbHPqUK5Q.xOaWPhRTb7gy-6-GUW6cxQVf_t7LhbmeabBNXqqqsT6dpLJLOWCGWZM07EkmfM4j.u2AMsCQ9ZsKc6ugOIoVwCgryB2KJNCnbBrlY6pq0W2Ww7sxSkUa9_WTPBIwAufhCQYkb7gA2eUbb6EIZjrl5mQ.sc3; ucid=hPzasmkDyTeHN0DinLRGvw; hasGmid=ver4; gig_bootstrap_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a=auth_ver4; glt_3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a={login_token}"  # noqa: E501
            r_auth = await client.get(
                auth_url,
                headers={
                    "accept": "*/*",
                    "cookie": cookie,
                    "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                    "x-requested-with": "com.smart.hellosmart",
                    "user-agent": "Mozilla/5.0 (Linux; Android 9; ANE-LX1 Build/HUAWEIANE-L21; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36",  # noqa: E501
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
                    "user-agent": "Mozilla/5.0 (Linux; Android 9; ANE-LX1 Build/HUAWEIANE-L21; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36",  # noqa: E501
                },
            )
            try:
                auth_result = httpx.URL(r_auth.headers["location"])
                access_token = auth_result.params["access_token"]
                refresh_token = auth_result.params["refresh_token"]
            except KeyError:
                raise SmartAPIError("Could not get access token from auth page")

            api_access_token, api_refresh_token, api_user_id = await self._get_api_session(client, access_token)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "api_access_token": api_access_token,
            "api_refresh_token": api_refresh_token,
            "api_user_id": api_user_id,
            "expires_at": expires_at,
        }

    async def _get_api_session(self, client: "SmartLoginClient", access_token: str) -> tuple[str, str, str]:
        """
        Exchange an OAuth access token for the API session tokens and the associated user id.
        
        Posts the given OAuth `access_token` to the API session endpoint and returns the API-level
        access token, refresh token, and user identifier obtained from the response.
        
        Returns:
            tuple[str, str, str]: (api_access_token, api_refresh_token, api_user_id)
        
        Raises:
            SmartAPIError: If the response does not contain the expected token or user id fields.
        """
        data = json.dumps({"accessToken": access_token}).replace(" ", "")
        r_api_access = await client.post(
            # we do not know what type of car we have in our list so we fall back to the old API URL
            self.endpoint_urls.get_api_base_url() + API_SESION_URL + "?identity_type=smart",
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
        _LOGGER.debug("API access result: %s", sanitize_log_data(api_result))
        try:
            api_access_token = api_result["data"]["accessToken"]
            api_refresh_token = api_result["data"]["refreshToken"]
            api_user_id = api_result["data"]["userId"]
        except KeyError:
            raise SmartAPIError("Could not get API access token from API")
        return api_access_token, api_refresh_token, api_user_id

    async def _refresh_access_token_eu(self) -> dict:
        """
        Attempt to refresh the EU (OAuth) access token and exchange it for API session tokens.
        
        If a refresh token is available, sends a refresh request to the OAuth token URL, computes a new expiry timestamp, exchanges the returned OAuth access token for API session tokens, and returns a mapping of tokens and metadata. Returns an empty dict if no refresh token is configured or if the refresh response does not yield an access token.
        
        Returns:
            dict: A mapping with the following keys when successful:
                - "access_token" (str): The refreshed OAuth access token.
                - "refresh_token" (str): The refreshed OAuth refresh token (or the previous refresh token if not provided).
                - "api_access_token" (str): The exchanged API access token for subsequent API calls.
                - "api_refresh_token" (str): The exchanged API refresh token for API session renewal.
                - "api_user_id" (str): The user identifier returned by the API session exchange.
                - "id_token" (str | None): The ID token returned by the OAuth refresh response, if present.
                - "expires_at" (datetime.datetime): UTC timestamp when the OAuth access token expires.
            Returns an empty dict if no refresh was possible or the refresh response lacked an access token.
        """
        if not self.refresh_token:
            return {}

        ssl_ctx = await self.get_ssl_context()
        async with SmartLoginClient(ssl_context=ssl_ctx) as client:
            payload = {
                "accessToken": "",
                "refreshToken": self.refresh_token,
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "hello-smart/2.0.5 (Android)",
                "X-API-Key": self.endpoint_urls.get_oauth_api_key(),
            }
            r_refresh = await client.post(
                self.endpoint_urls.get_oauth_token_url(),
                json=payload,
                headers=headers,
            )
            refresh_result = r_refresh.json()
            access_token = refresh_result.get("accessToken") or refresh_result.get("access_token")
            refresh_token = refresh_result.get("refreshToken") or refresh_result.get("refresh_token")
            id_token = refresh_result.get("idToken") or refresh_result.get("id_token")
            expires_in = refresh_result.get("expiresIn") or refresh_result.get("expires_in")
            if not access_token:
                return {}

            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=int(expires_in) if expires_in else HTTPX_TIMEOUT * 2
            )
            api_access_token, api_refresh_token, api_user_id = await self._get_api_session(client, access_token)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token or self.refresh_token,
                "api_access_token": api_access_token,
                "api_refresh_token": api_refresh_token,
                "api_user_id": api_user_id,
                "id_token": id_token,
                "expires_at": expires_at,
            }

    async def _login_global(self) -> dict:
        """
        Perform the global (HMAC) login flow and return obtained tokens and related metadata.
        
        Returns:
            dict: Mapping with the following keys:
                - access_token (str): OAuth access token from the global login.
                - refresh_token (str|None): Refresh token from the global login, if provided.
                - api_access_token (str): API session access token (same as `access_token` for global flow).
                - api_refresh_token (str|None): API session refresh token (same as `refresh_token` for global flow).
                - api_user_id (str): User identifier returned by the global login.
                - id_token (str|None): ID token returned by the global login, if present.
                - expires_at (datetime.datetime): UTC timestamp when the access token expires.
        """
        ssl_ctx = await self.get_ssl_context()
        async with SmartLoginClient(ssl_context=ssl_ctx) as client:
            _LOGGER.info("Acquiring access token (global app).")

            path = "/iam/service/api/v1/login"
            payload = {
                "email": self.username,
                "password": self.password,
                "imageSessionId": "",
                "imageCode": "",
            }
            body = json.dumps(payload)
            host = httpx.URL(self.endpoint_urls.get_api_base_url()).host
            headers = utils.generate_global_header(
                method="POST",
                path=path,
                host=host,
                app_key=self.endpoint_urls.get_global_app_key(),
                app_secret=self.endpoint_urls.get_global_app_secret(),
                body=body,
            )

            r_login = await client.post(
                self.endpoint_urls.get_api_base_url() + path,
                headers=headers,
                content=body,
            )
            login_result = r_login.json()
            _LOGGER.debug("Login result: %s", sanitize_log_data(login_result))
            data = login_result.get("data") or login_result.get("result") or {}
            if not data:
                message = login_result.get("message", "Unknown error")
                code = login_result.get("code", "unknown")
                raise SmartAPIError(f"Could not get tokens from global login: {code} {message}")

            access_token = data.get("accessToken")
            refresh_token = data.get("refreshToken")
            id_token = data.get("idToken")
            api_user_id = data.get("userId")
            expires_in = data.get("expiresIn") or data.get("expires_in")
            if not access_token or not api_user_id:
                raise SmartAPIError("Could not get access token from global login")

            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=int(expires_in) if expires_in else HTTPX_TIMEOUT * 2
            )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "api_access_token": access_token,
            "api_refresh_token": refresh_token,
            "api_user_id": api_user_id,
            "id_token": id_token,
            "expires_at": expires_at,
        }

    async def _refresh_access_token_global(self) -> dict:
        """
        Refresh the Global app access token and return the refreshed token set.
        
        Returns:
            dict: Mapping with refreshed token and session fields:
                - `access_token` (str): OAuth access token.
                - `refresh_token` (str): OAuth refresh token (may be original if not returned).
                - `api_access_token` (str): API session access token (same as `access_token`).
                - `api_refresh_token` (str): API session refresh token (same as `refresh_token`).
                - `api_user_id` (str): API user identifier.
                - `id_token` (str | None): ID token if provided by the server.
                - `expires_at` (datetime.datetime): UTC timestamp when the access token expires.
            Returns an empty dict if no refresh token is available or the refresh attempt fails.
        """
        if not self.refresh_token:
            return {}

        ssl_ctx = await self.get_ssl_context()
        async with SmartLoginClient(ssl_context=ssl_ctx) as client:
            path = "/iam/service/api/v1/refresh/"
            payload = {"refreshToken": self.refresh_token}
            body = json.dumps(payload)
            host = httpx.URL(self.endpoint_urls.get_api_base_url()).host
            headers = utils.generate_global_header(
                method="POST",
                path=path,
                host=host,
                app_key=self.endpoint_urls.get_global_app_key(),
                app_secret=self.endpoint_urls.get_global_app_secret(),
                body=body,
            )
            r_refresh = await client.post(
                self.endpoint_urls.get_api_base_url() + path,
                headers=headers,
                content=body,
            )
            refresh_result = r_refresh.json()
            _LOGGER.debug("Refresh result: %s", sanitize_log_data(refresh_result))
            data = refresh_result.get("data") or refresh_result.get("result") or {}
            if not data:
                return {}

            access_token = data.get("accessToken")
            refresh_token = data.get("refreshToken") or self.refresh_token
            id_token = data.get("idToken")
            api_user_id = data.get("userId")
            expires_in = data.get("expiresIn") or data.get("expires_in")
            if not access_token or not api_user_id:
                return {}

            expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=int(expires_in) if expires_in else HTTPX_TIMEOUT * 2
            )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "api_access_token": access_token,
            "api_refresh_token": refresh_token,
            "api_user_id": api_user_id,
            "id_token": id_token,
            "expires_at": expires_at,
        }


class SmartLoginClient(httpx.AsyncClient):
    """Client to login to the Smart API."""

    def __init__(self, ssl_context: Optional[ssl.SSLContext] = None, *args, **kwargs):
        """Initialize the login client.

        Args:
        ----
            ssl_context: Pre-created SSL context to avoid blocking calls.
                        If not provided, SSL verification is still enabled
                        but may cause blocking warnings in async environments.
            *args: Additional arguments passed to httpx.AsyncClient
            **kwargs: Additional keyword arguments passed to httpx.AsyncClient

        """
        # Increase timeout to 30 seconds
        kwargs["timeout"] = httpx.Timeout(HTTPX_TIMEOUT)

        # Use pre-created SSL context if provided to avoid blocking calls
        if ssl_context is not None:
            kwargs["verify"] = ssl_context

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
            _LOGGER.debug("Request: %s %s", request.method, request.url)

        async def log_response(response):
            await response.aread()
            request = response.request
            _LOGGER.debug("Response: %s %s - Status %d", request.method, request.url, response.status_code)

        kwargs["event_hooks"]["response"].append(log_response)
        kwargs["event_hooks"]["request"].append(log_request)

        super().__init__(**kwargs)


class SmartLoginRetry(httpx.Auth):
    """httpx.Auth uses as waorkauround to retry and sleep in case of status code 429."""

    def sync_auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        """Handle synchronous authentication flow for requests."""
        raise RuntimeError("Cannot use a async authentication class with httpx.Client")

    async def async_auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        """Asynchronous authentication flow for handling requests and retrying on rate limit errors."""
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