"""Authentication management for Smart APIs."""

import asyncio
import datetime
import json
import logging
import math
import re
import secrets
import ssl
from collections import defaultdict
from collections.abc import AsyncGenerator, Generator
from typing import Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from httpx._models import Request, Response

from pysmarthashtag.api import utils
from pysmarthashtag.api.log_sanitizer import sanitize_log_data
from pysmarthashtag.const import (
    API_SESION_URL,
    HTTPX_TIMEOUT,
    MAX_REDIRECT_HOPS,
    WEBVIEW_USER_AGENT,
    EndpointUrls,
)
from pysmarthashtag.models import SmartAPIError

EXPIRES_AT_OFFSET = datetime.timedelta(seconds=HTTPX_TIMEOUT * 2)

_LOGGER = logging.getLogger(__name__)


# PATCH: shared breaker state so HA's config_entries retry storm (which
# creates fresh SmartAuthentication instances) cannot bypass the quiet
# window. Keyed by username — state persists for the lifetime of the
# Python process.
class _BackoffState:
    __slots__ = ("backoff", "quiet_until")

    def __init__(self, backoff: datetime.timedelta) -> None:
        self.backoff: datetime.timedelta = backoff
        self.quiet_until: Optional[datetime.datetime] = None


_BACKOFF_REGISTRY: dict[str, _BackoffState] = {}


class SmartAuthentication(httpx.Auth):
    """Authentication and Retry Handler for the Smart API."""

    # PATCH: Adaptive rate-limit backoff (AIMD).
    # On rate-limit failure (HTTP 403/429), multiply current backoff by GROW (capped at CAP).
    # On success, subtract SHRINK (floored at FLOOR). On non-rate-limit failure,
    # use a fixed short backoff so transient blips don't grow the window.
    _BACKOFF_FLOOR = datetime.timedelta(minutes=2)
    _BACKOFF_CAP = datetime.timedelta(minutes=90)
    _BACKOFF_GROW = 1.5
    _BACKOFF_SHRINK = datetime.timedelta(minutes=1)
    _OTHER_FAILURE_BACKOFF = datetime.timedelta(seconds=60)

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
        # PATCH: shared adaptive-backoff state (per username, module-scoped).
        # Sharing across instances is essential because HA's config_entries
        # retry mechanism creates fresh SmartAuthentication instances on
        # every retry — per-instance state would never accumulate.
        if username not in _BACKOFF_REGISTRY:
            _BACKOFF_REGISTRY[username] = _BackoffState(self._BACKOFF_FLOOR)
        self._state: _BackoffState = _BACKOFF_REGISTRY[username]
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

    def _invalidate_session(self) -> None:
        """Drop all cached session identity so the next login starts fresh.

        A half-completed login must not leave a stale ``api_user_id`` /
        ``api_access_token`` behind: ``SmartAccount.get_vehicles()`` only
        forces a fresh ``login()`` when ``api_user_id is None``, so a
        lingering value makes it replay a dead token every poll (the cloud
        answers 1402/4038/8040) and the session never self-heals — only a
        full integration reload recovers it. Clearing the identity here lets
        the next poll re-enter the complete login journey.
        """
        self.access_token = None
        self.refresh_token = None
        self.api_access_token = None
        self.api_refresh_token = None
        self.api_user_id = None
        self.expires_at = None

    async def login(self) -> None:
        """Login to the Smart API."""
        _LOGGER.debug("Logging in to Smart API")
        token_data = {}
        try:
            if self.refresh_token:
                token_data = await self._refresh_access_token()
            if not token_data:
                token_data = await self._login()
        except Exception:
            # Any failure in the login journey (rate-limit, WAF, failed
            # session exchange, ...) must invalidate whatever partial state
            # we hold so the next attempt starts clean rather than replaying
            # a stale token. The exception still propagates to the caller.
            self._invalidate_session()
            raise
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
        except (KeyError, TypeError) as err:
            self._invalidate_session()
            raise SmartAPIError("Could not login to Smart API") from err

    async def _refresh_access_token(self):
        """Refresh the access token.

        The refresh-token grant is not implemented server-side, so this
        performs a full re-login and RETURNS its token data. Returning the
        result (rather than discarding it) is essential: ``login()`` falls
        back to a second ``_login()`` whenever this returns falsy, so
        discarding the data caused two full login flows per refresh —
        doubling auth pressure against the rate-limited Smart gateway.
        """
        try:
            ssl_ctx = await self.get_ssl_context()
            async with SmartLoginClient(ssl_context=ssl_ctx) as _:
                _LOGGER.debug("Refreshing access token via relogin because refresh token is not implemented")
                return await self._login()
        except SmartAPIError:
            _LOGGER.debug("Refreshing access token failed. Logging in again")
            return {}

    async def _login(self) -> dict:
        """Login to Smart web services with adaptive rate-limit backoff.

        Wraps the actual EU login flow (implemented in ``_do_login``) with:
          * an in-memory circuit breaker (shared per-username) that suppresses
            calls while inside an adaptive quiet window, and
          * AIMD backoff: rate-limit failures grow the window geometrically,
            successes shrink it additively.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        if self._state.quiet_until is not None and now < self._state.quiet_until:
            wait_s = int((self._state.quiet_until - now).total_seconds())
            raise SmartAPIError(
                "Smart API in adaptive quiet window for another "
                f"{wait_s}s (until "
                f"{self._state.quiet_until.isoformat(timespec='seconds')}, "
                f"backoff={self._state.backoff})"
            )
        try:
            result = await self._do_login()
        except (SmartAPIError, httpx.HTTPStatusError) as exc:
            self._on_login_failure(exc)
            raise
        else:
            self._on_login_success()
            return result

    def _on_login_failure(self, exc: Exception) -> None:
        """Update backoff state after a failed login attempt."""
        now = datetime.datetime.now(datetime.timezone.utc)
        if self._is_rate_limit_error(exc):
            new_backoff = min(self._state.backoff * self._BACKOFF_GROW, self._BACKOFF_CAP)
            self._state.backoff = new_backoff
            self._state.quiet_until = now + new_backoff
            _LOGGER.warning(
                "Smart API rate-limit detected (%s). Adaptive quiet window: %s, until %s",
                sanitize_log_data(exc),
                new_backoff,
                self._state.quiet_until.isoformat(timespec="seconds"),
            )
        else:
            self._state.quiet_until = now + self._OTHER_FAILURE_BACKOFF
            _LOGGER.info(
                "Smart API login failed (%s). Short retry-suppress until %s",
                exc,
                self._state.quiet_until.isoformat(timespec="seconds"),
            )

    def _on_login_success(self) -> None:
        """Update backoff state after a successful login."""
        prev = self._state.backoff
        new_backoff = max(self._state.backoff - self._BACKOFF_SHRINK, self._BACKOFF_FLOOR)
        self._state.backoff = new_backoff
        self._state.quiet_until = None
        if prev > self._BACKOFF_FLOOR:
            _LOGGER.info("Smart API login succeeded; backoff %s -> %s", prev, new_backoff)

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        """Heuristic: determine whether *exc* was caused by WAF/rate-limiting."""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in (403, 429)
        text = str(exc).lower()
        return (
            "rate limit" in text
            or "rate-limit" in text
            or "quota" in text
            or "http 403" in text
            or "http 429" in text
            or "forbidden" in text
            # Throttle wording the cloud may return as an HTTP-200 error body
            # (surfaced into the exception text by _do_login's session-exchange
            # handler). Kept deliberately narrow so genuine one-off failures
            # (e.g. "Could not get access token from auth page") are unaffected.
            or "too many" in text
            or "throttl" in text
            or "try again later" in text
        )

    async def _do_login(self) -> dict:
        """Login to Smart web services.

        Implements the EU 4.5-step OIDC + Gigya flow that the live cloud
        currently expects:

        1. Walk the OIDC redirect chain looking for ``?context=`` (it now
           lives on hop 2: ``app.id.smart.com/proxy``, not hop 1).
        1.5. Bootstrap a Gigya session via ``socialize.getIDs`` to obtain
           a fresh ``gmid`` + ``ucid`` and build the
           ``gig_bootstrap_<APIKey>=auth_ver4`` cookie.
        2. POST ``accounts.login`` with the bootstrap cookie.
        3. Walk ``authorize/continue`` redirects looking for
           ``access_token`` (in query OR fragment).
        4. Exchange the OAuth access token for an API session via
           ``/auth/account/session/secure``.
        """
        ssl_ctx = await self.get_ssl_context()
        async with SmartLoginClient(ssl_context=ssl_ctx) as client:
            _LOGGER.info("Acquiring access token.")
            api_key = self.endpoint_urls.get_api_key()

            # ---- Step 1: walk redirects to find ?context= -----------------
            # Smart's chain currently looks like:
            #   awsapi.future.smart.com -> auth.smart.com/oidc/.../authorize
            #     -> app.id.smart.com/proxy?context=<JWT>&...
            # The context= used to be on hop 1; it moved to hop 2 (different
            # host). Walking up to MAX_REDIRECT_HOPS keeps this resilient if
            # Smart shifts hops again.
            context_headers = {
                "x-app-id": "SmartAPPEU",
                "accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                "x-requested-with": "com.smart.hellosmart",
                "user-agent": WEBVIEW_USER_AGENT,
                "content-type": "application/json; charset=utf-8",
            }
            current_url = self.endpoint_urls.get_server_url()
            context: Optional[str] = None
            last_status: Optional[int] = None
            last_location = ""
            for hop in range(MAX_REDIRECT_HOPS):
                r_context = await client.get(
                    current_url,
                    headers=context_headers,
                    follow_redirects=False,
                )
                last_status = r_context.status_code
                last_location = r_context.headers.get("location", "")
                if last_status not in (301, 302, 303, 307, 308):
                    if hop == 0 and last_status == 403:
                        _LOGGER.error(
                            "EU auth gateway rejected request (HTTP 403): possible UA filtering or API change",
                        )
                    break

                if not last_location:
                    _LOGGER.error("Redirect at hop %d missing Location header", hop + 1)
                    break

                parsed_location = urlparse(last_location)
                params = parse_qs(parsed_location.query)
                if "context" in params:
                    context = params["context"][0]
                    _LOGGER.debug(
                        "Step 1: extracted context= at redirect hop %d (host=%s)",
                        hop + 1,
                        parsed_location.hostname or "?",
                    )
                    break
                current_url = urljoin(current_url, last_location)

            if not context:
                _LOGGER.error(
                    "Context extraction failed: redirect chain ended without "
                    "context= parameter (last_status=%s, last_host=%s)",
                    last_status,
                    urlparse(last_location).hostname or "?",
                )
                raise SmartAPIError("Could not get context from login page")

            # ---- Step 1.5: bootstrap a Gigya session ----------------------
            # Smart's Gigya tenant won't accept accounts.login from a "fresh"
            # client; it expects gmid + ucid + hasGmid + gig_bootstrap
            # cookies. socialize.getIDs is the canonical endpoint that issues
            # these to a JS-SDK client.
            ids_url = (
                f"{self.endpoint_urls.get_gigya_socialize_url()}/socialize.getIDs"
                f"?APIKey={api_key}&format=json&includeTicket=true"
            )
            r_ids = await client.get(ids_url)
            try:
                ids_data = r_ids.json()
            except ValueError as err:
                raise SmartAPIError("Gigya socialize.getIDs returned non-JSON") from err

            if ids_data.get("errorCode") != 0:
                _LOGGER.error(
                    "socialize.getIDs failed: code=%s message=%s",
                    ids_data.get("errorCode"),
                    sanitize_log_data(ids_data.get("errorMessage")),
                )
                raise SmartAPIError("Gigya socialize.getIDs failed: cannot bootstrap session")

            gmid = ids_data.get("gmid", "")
            ucid = ids_data.get("ucid", "")
            if not gmid:
                raise SmartAPIError("Gigya gmid missing — cannot proceed")

            gigya_cookie = f"gmid={gmid}; ucid={ucid}; hasGmid=ver4; gig_bootstrap_{api_key}=auth_ver4"
            _LOGGER.debug("Step 1.5: Gigya bootstrap cookies built")

            # ---- Step 2: POST Gigya login --------------------------------
            r_login = await client.post(
                self.endpoint_urls.get_login_url(),
                data={
                    "loginID": self.username,
                    "password": self.password,
                    "sessionExpiration": 2592000,
                    "targetEnv": "jssdk",
                    "include": "profile,data,emails,subscriptions,preferences,",
                    "includeUserInfo": True,
                    "loginMode": "standard",
                    "lang": "de",
                    "APIKey": api_key,
                    "source": "showScreenSet",
                    "sdk": "js_latest",
                    "pageURL": "https://app.id.smart.com/login?gig_ui_locales=de-DE",
                    "sdkBuild": 15482,
                    "format": "json",
                },
                headers={
                    "accept": "*/*",
                    "accept-language": "de",
                    "content-type": "application/x-www-form-urlencoded",
                    "x-requested-with": "com.smart.hellosmart",
                    "cookie": gigya_cookie,
                    "origin": "https://app.id.smart.com",
                    "user-agent": WEBVIEW_USER_AGENT,
                },
            )
            try:
                login_result = r_login.json()
            except ValueError as err:
                raise SmartAPIError("Gigya login returned non-JSON") from err

            # Gigya returns 200 even on errors; surface the code/message.
            if login_result.get("errorCode", 0) != 0:
                gigya_code = login_result.get("errorCode")
                gigya_message = login_result.get("errorMessage", "")
                _LOGGER.error(
                    "Gigya login error: code=%s message=%s",
                    gigya_code,
                    sanitize_log_data(gigya_message),
                )
                raise SmartAPIError(f"Gigya login error (code={gigya_code}): {gigya_message}")

            try:
                session_info = login_result["sessionInfo"]
                login_token = session_info["login_token"]
                expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                    seconds=int(session_info["expires_in"])
                )
            except (KeyError, ValueError) as err:
                # PATCH: include status + body so the breaker can classify.
                # Body is run through sanitize_log_data() so any tokens/PII are masked.
                raise SmartAPIError(
                    "Could not get login token from login page "
                    f"(HTTP {r_login.status_code}, "
                    f"body={sanitize_log_data(r_login.text[:200])!r})"
                ) from err

            # ---- Step 3: walk authorize/continue redirects ---------------
            # Smart returns the OAuth tokens on the LAST hop of a 2-hop chain,
            # in the URL's query string (newer flow) or fragment (older flow).
            # Handle both for forward compatibility. The /authorize/continue
            # handler authenticates via cookies, not query params: the Gigya
            # bootstrap cookie PLUS glt_<APIKey>=<login_token>.
            auth_url = "{}?{}".format(
                self.endpoint_urls.get_auth_url(),
                urlencode({"context": context, "login_token": login_token}),
            )
            authorize_cookie = f"{gigya_cookie}; glt_{api_key}={login_token}"
            authorize_headers = {
                "accept": "*/*",
                "cookie": authorize_cookie,
                "accept-language": "de-DE,de;q=0.9,en-DE;q=0.8,en-US;q=0.7,en;q=0.6",
                "x-requested-with": "com.smart.hellosmart",
                "user-agent": WEBVIEW_USER_AGENT,
            }
            access_token: Optional[str] = None
            refresh_token: Optional[str] = None
            current_url = auth_url
            for hop in range(MAX_REDIRECT_HOPS):
                r_auth = await client.get(
                    current_url,
                    headers=authorize_headers,
                    follow_redirects=False,
                )
                last_status = r_auth.status_code
                last_location = r_auth.headers.get("location", "")
                if last_status not in (301, 302, 303, 307, 308):
                    break

                if not last_location:
                    _LOGGER.error("Authorize redirect at hop %d missing Location header", hop + 1)
                    break

                parsed_redirect = urlparse(urljoin(current_url, last_location))
                fragment_params = parse_qs(parsed_redirect.fragment)
                query_params = parse_qs(parsed_redirect.query)

                # Smart surfaces auth errors via redirect to /proxy?mode=error
                if query_params.get("mode", [None])[0] == "error":
                    err_code = query_params.get("errorCode", [""])[0]
                    err_msg = query_params.get("errorMessage", [""])[0]
                    _LOGGER.error(
                        "authorize/continue redirected to error page: code=%s message=%s",
                        err_code,
                        err_msg,
                    )
                    raise SmartAPIError(f"authorize/continue error (code={err_code}): {err_msg}")

                access_token = (
                    query_params.get("access_token", [None])[0] or fragment_params.get("access_token", [None])[0]
                )
                refresh_token = (
                    query_params.get("refresh_token", [None])[0] or fragment_params.get("refresh_token", [None])[0]
                )
                if access_token:
                    _LOGGER.debug(
                        "Step 3: access_token extracted from redirect hop %d (host=%s, source=%s)",
                        hop + 1,
                        parsed_redirect.hostname or "?",
                        "query" if query_params.get("access_token") else "fragment",
                    )
                    break

                current_url = urljoin(current_url, last_location)

            if not access_token:
                _LOGGER.error(
                    "Access token extraction failed after %d hops; last_status=%s last_host=%s",
                    MAX_REDIRECT_HOPS,
                    last_status,
                    urlparse(last_location).hostname or "?",
                )
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
            except (KeyError, TypeError) as err:
                # The OAuth flow succeeded but the final API-session exchange
                # did not return a session. Surface the cloud's own code +
                # message (mirrors the Gigya-login step above) instead of a
                # fixed generic string. Two reasons this matters:
                #   * diagnosability — the log now says *why* it failed;
                #   * classification — _is_rate_limit_error() can only see the
                #     exception text, so a throttle/WAF block hidden here would
                #     otherwise be mistaken for a transient blip and get the
                #     short 60s suppress instead of the geometric backoff.
                api_code = api_result.get("code") if isinstance(api_result, dict) else None
                api_message = api_result.get("message", "") if isinstance(api_result, dict) else ""
                http_status = r_api_access.status_code
                _LOGGER.error(
                    "API session exchange failed (HTTP %s, code=%s): %s",
                    http_status,
                    api_code,
                    sanitize_log_data(api_message),
                )
                raise SmartAPIError(
                    "Could not get API access token from API "
                    f"(HTTP {http_status}, code={api_code}): {api_message}"
                ) from err

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
        raise RuntimeError("Cannot use an async authentication class with httpx.Client")

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
    retry_after = 2
    try:
        retry_after_header = response.headers.get("Retry-After")
        if retry_after_header and retry_after_header.isdigit():
            retry_after = int(retry_after_header)
        else:
            match = re.search(r"\d+", response.json().get("message", ""))
            if match:
                retry_after = int(match.group())
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        _LOGGER.debug(
            "Failed to parse retry_after from response: retry_after_header=%s, error=%s",
            retry_after_header if 'retry_after_header' in locals() else 'undefined',
            exc,
        )
    return math.ceil(retry_after * 2)
