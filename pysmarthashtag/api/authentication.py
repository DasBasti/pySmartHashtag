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
    INTL_APP_ID,
    INTL_CA_KEY,
    INTL_LOGIN_URL,
    INTL_OAUTH_URL,
    INTL_OPERATOR_CODE,
    EndpointUrls,
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
        self.ssl_context: Optional[ssl.SSLContext] = ssl_context
        self.endpoint_urls: EndpointUrls = endpoint_urls if endpoint_urls is not None else EndpointUrls()
        _LOGGER.debug("Device ID initialized")

    async def get_ssl_context(self) -> ssl.SSLContext:
        """Get or create SSL context asynchronously.

        This method returns a cached SSL context if available, or creates
        a new one asynchronously using the shared ssl_context module.
        Thread-safe using asyncio.Lock.

        Returns
        -------
            ssl.SSLContext: An SSL context for secure connections.

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
            _LOGGER.debug("Login successful")
            return True
        except KeyError:
            raise SmartAPIError("Could not login to Smart API")

    async def _refresh_access_token(self):
        """Refresh the access token."""
        try:
            ssl_ctx = await self.get_ssl_context()
            async with SmartLoginClient(ssl_context=ssl_ctx) as _:
                _LOGGER.debug("Refreshing access token via relogin because refresh token is not implemented")
                await self._login()
        except SmartAPIError:
            _LOGGER.debug("Refreshing access token failed. Logging in again")
            return {}

    async def _login(self):
        """Login to Smart web services."""
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
                content=data.encode("utf-8"),
            )
            api_result = r_api_access.json()
            _LOGGER.debug("API access result: %s", sanitize_log_data(api_result))
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


class SmartAuthenticationINTL(SmartAuthentication):
    """Authentication handler for Smart International (INTL) API.

    This class handles authentication for the Hello Smart International app,
    which is used in Australia, Singapore, Israel, and other international markets.

    The INTL auth flow is different from EU:
    1. POST login with email/password to sg-app-api.smart.com -> get accessToken, idToken
    2. GET oauth20/authorize with accessToken -> get authCode
    3. POST session/secure with authCode to apiv2.ecloudeu.com -> get vehicle API tokens

    Note: The sg-app-api.smart.com endpoints do not require X-Ca-Signature validation,
    which simplifies the authentication process significantly.
    """

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
        super().__init__(
            username=username,
            password=password,
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token,
            ssl_context=ssl_context,
            endpoint_urls=endpoint_urls,
        )
        # INTL-specific tokens
        self.intl_access_token: Optional[str] = None
        self.intl_refresh_token: Optional[str] = None
        self.intl_id_token: Optional[str] = None
        self.intl_user_id: Optional[str] = None
        self.session_id: str = secrets.token_hex(16).upper()
        self.device_identifier: str = secrets.token_hex(16)
        self.client_id: str = "2232193363e44527"  # INTL OAuth client ID
        self.api_client_id: Optional[str] = None  # Client ID from session response
        _LOGGER.debug("SmartAuthenticationINTL initialized for INTL region")

    def _generate_intl_headers(self, auth_token: str = "") -> dict[str, str]:
        """Generate headers for INTL API requests (sg-app-api.smart.com).

        The sg-app-api.smart.com endpoints do not validate X-Ca-Signature,
        so we can use empty or minimal signatures.
        """
        import time
        import uuid

        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4()).upper()

        headers = {
            "Host": "sg-app-api.smart.com",
            "User-Agent": "GlobalSmart/1.0.7 (iPhone; iOS 18.6.1; Scale/3.00)",
            "X-Ca-Key": INTL_CA_KEY,
            "X-Ca-Timestamp": timestamp,
            "X-Ca-Nonce": nonce,
            "X-Ca-Signature-Method": "HmacSHA256",
            "X-Ca-Signature": "",  # Not validated by server
            "X-Ca-Signature-Headers": (
                "Accept-Language,User-Agent,X-Ca-Nonce,X-Ca-Timestamp,"
                "Xs-App-Ver,Xs-Auth-Token,Xs-Client-Id,Xs-Di,Xs-Os,Xs-Session-Id,Xs-Ui"
            ),
            "Xs-Os": "iOS",
            "Xs-App-Ver": "1.0.7",
            "Xs-Session-Id": self.session_id,
            "Xs-Di": self.device_identifier,
            "Xs-Ui": secrets.token_hex(16),
            "Xs-Auth-Token": auth_token,
            "Xs-Client-Id": self.client_id,
            "Accept": "*/*",
            "Accept-Language": "en-AU;q=1",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
        }

        return headers

    def _generate_vehicle_api_headers(self, body: str = None) -> dict[str, str]:
        """Generate headers for vehicle API (ecloudeu) requests.

        These headers are used for the session/secure endpoint on apiv2.ecloudeu.com.
        The x-signature is calculated using the INTL signing secret.
        """
        import time
        import uuid

        timestamp = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4()).upper()

        headers = {
            "x-app-id": INTL_APP_ID,
            "x-operator-code": INTL_OPERATOR_CODE,
            "x-agent-type": "iOS",
            "x-agent-version": "18.6.1",
            "x-device-type": "mobile",
            "x-device-identifier": self.device_identifier,
            "x-device-manufacture": "Apple",
            "x-device-brand": "Apple",
            "x-device-model": "iPhone",
            "x-env-type": "production",
            "x-api-signature-version": "1.0",
            "x-api-signature-nonce": nonce,
            "x-timestamp": timestamp,
            "platform": "NON-CMA",
            "accept": "application/json;responseformat=3",
            "accept-language": "en_US",
            "content-type": "application/json",
            "user-agent": "GlobalSmart/1.0.7 (iPhone; iOS 18.6.1; Scale/3.00)",
        }

        # Calculate signature using INTL secret
        if body is not None:
            headers["x-signature"] = utils._create_sign(
                nonce=nonce,
                params={"identity_type": "smart-israel"},
                timestamp=timestamp,
                method="POST",
                url=API_SESION_URL,
                body=body,
                use_intl=True,
            )

        return headers

    async def _login(self):
        """Login to Smart INTL web services.

        INTL login flow (uses sg-app-api.smart.com which doesn't require signatures):
        1. POST to login endpoint with email/password -> accessToken, idToken
        2. GET oauth20/authorize with accessToken -> authCode
        3. POST session/secure to apiv2.ecloudeu.com with authCode -> vehicle API tokens
        """
        ssl_ctx = await self.get_ssl_context()
        async with SmartLoginClient(ssl_context=ssl_ctx) as client:
            _LOGGER.info("INTL: Acquiring access token via Hello Smart International API")

            # Step 1: Login with email/password (no signature required!)
            _LOGGER.debug("INTL: Step 1 - Logging in with credentials")
            login_data = json.dumps(
                {
                    "email": self.username,
                    "password": self.password,
                }
            )

            r_login = await client.post(
                INTL_LOGIN_URL,
                content=login_data,
                headers=self._generate_intl_headers(),
            )

            try:
                login_result = r_login.json()
                _LOGGER.debug("INTL login response code: %s", login_result.get("code"))

                if login_result.get("code") != "200":
                    error_msg = login_result.get("message", "Unknown error")
                    _LOGGER.error("INTL login failed: %s", error_msg)
                    raise SmartAPIError(f"INTL login failed: {error_msg}")

                result = login_result.get("result", {})
                self.intl_access_token = result.get("accessToken")
                self.intl_refresh_token = result.get("refreshToken")
                self.intl_id_token = result.get("idToken")
                self.intl_user_id = result.get("userId")
                expires_in = result.get("expiresIn", 86400)

                expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)

                _LOGGER.info("INTL: Login successful for user %s", self.intl_user_id)

            except (KeyError, ValueError, TypeError) as e:
                raise SmartAPIError(f"Could not parse INTL login response: {e}")

            # Step 2: Exchange accessToken for authCode via OAuth
            # Note: OAuth uses just accessToken in URL param, and idToken in Xs-Auth-Token header
            _LOGGER.debug("INTL: Step 2 - Exchanging accessToken for authCode")

            oauth_url = f"{INTL_OAUTH_URL}?accessToken={self.intl_access_token}"

            oauth_headers = self._generate_intl_headers(self.intl_id_token)

            r_oauth = await client.get(
                oauth_url,
                headers=oauth_headers,
            )

            try:
                oauth_result = r_oauth.json()
                _LOGGER.debug("INTL OAuth response code: %s", oauth_result.get("code"))

                if oauth_result.get("code") != "200":
                    error_msg = oauth_result.get("message", "Unknown error")
                    _LOGGER.error("INTL OAuth failed: %s", error_msg)
                    raise SmartAPIError(f"INTL OAuth failed: {error_msg}")

                # Result is directly the authCode string (e.g., "CODE-xxx")
                auth_code = oauth_result.get("result")
                if isinstance(auth_code, dict):
                    auth_code = auth_code.get("authCode", auth_code)

                _LOGGER.debug("INTL: Got authCode: %s...", str(auth_code)[:30] if auth_code else "None")

            except (KeyError, ValueError, TypeError) as e:
                raise SmartAPIError(f"Could not parse INTL OAuth response: {e}")

            # Step 3: Exchange authCode for vehicle API session
            _LOGGER.debug("INTL: Step 3 - Exchanging authCode for vehicle API session")

            session_url = f"{self.endpoint_urls.get_api_base_url_v2()}{API_SESION_URL}?identity_type=smart-israel"
            session_data = json.dumps({"authCode": auth_code}, separators=(",", ":"))

            session_headers = self._generate_vehicle_api_headers(body=session_data)

            r_session = await client.post(
                session_url,
                content=session_data,
                headers=session_headers,
            )

            try:
                session_result = r_session.json()
                _LOGGER.debug("INTL Session response: %s", sanitize_log_data(session_result))

                if session_result.get("code") != 1000:
                    error_msg = session_result.get("message", "Unknown error")
                    _LOGGER.error("INTL session failed: %s (code: %s)", error_msg, session_result.get("code"))
                    raise SmartAPIError(f"INTL session failed: {error_msg}")

                data = session_result.get("data", {})
                api_access_token = data.get("accessToken")
                api_refresh_token = data.get("refreshToken")
                api_user_id = data.get("userId")
                api_client_id = data.get("clientId")

                # Store client_id on the auth object for use in API requests
                self.api_client_id = api_client_id

                _LOGGER.info("INTL: Successfully authenticated, user ID: %s", api_user_id)

            except (KeyError, ValueError, TypeError) as e:
                raise SmartAPIError(f"Could not parse INTL session response: {e}")

        return {
            "access_token": api_access_token,
            "refresh_token": api_refresh_token,
            "api_access_token": api_access_token,
            "api_refresh_token": api_refresh_token,
            "api_user_id": api_user_id,
            "expires_at": expires_at,
        }

    async def _refresh_access_token(self):
        """Refresh the INTL access token.

        For INTL, we simply re-login as the refresh flow is complex
        and the login endpoint doesn't require signatures.
        """
        _LOGGER.debug("INTL: Refresh requested, performing full re-login")
        return {}  # Return empty to trigger full login


def get_retry_wait_time(response: httpx.Response) -> int:
    """Get the wait time to wait twice as long before retrying."""
    try:
        retry_after = next(iter([int(i) for i in response.json().get("message", "") if i.isdigit()]))
    except Exception:
        retry_after = 2
    return math.ceil(retry_after * 2)
