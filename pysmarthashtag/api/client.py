import logging
import ssl
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

import httpx

from pysmarthashtag.api.authentication import SmartAuthentication
from pysmarthashtag.api.ssl_context import get_ssl_context_async
from pysmarthashtag.const import (
    HTTPX_TIMEOUT,
    SERVER_URL,
)
from pysmarthashtag.models import (
    AnonymizedResponse,
    SmartHumanCarConnectionError,
    SmartMainTokenExpiredError,
    SmartNoPermissionError,
    SmartNonceError,
    SmartTokenRefreshNecessary,
    SmartVehicleNotInUseError,
    SmartVehicleUnboundError,
)

_LOGGER = logging.getLogger(__name__)

RESPONSE_STORE: deque[AnonymizedResponse] = deque(maxlen=10)


@dataclass
class SmartClientConfiguration:
    """Stores global settings for SmartClient."""

    authentication: SmartAuthentication
    log_responses: Optional[bool] = False
    ssl_context: Optional[ssl.SSLContext] = field(default=None)

    def set_log_responses(self, log_responses: bool) -> None:
        """Set if responses are logged and clear response store."""

        self.log_responses = log_responses
        RESPONSE_STORE.clear()

    async def get_ssl_context(self) -> ssl.SSLContext:
        """Get or create SSL context asynchronously."""
        if self.ssl_context is None:
            self.ssl_context = await get_ssl_context_async()
        return self.ssl_context


class SmartClient(httpx.AsyncClient):
    """Async HTTP client based on `httpx.AsyncClient` with automated OAuth token refresh."""

    last_message: str = ""

    def __init__(self, config: SmartClientConfiguration, ssl_context: Optional[ssl.SSLContext] = None, *args, **kwargs):
        """Initialize the Smart client.

        Args:
        ----
            config: Smart client configuration
            ssl_context: Pre-created SSL context to avoid blocking calls.
                        If not provided, SSL verification is still enabled
                        but may cause blocking warnings in async environments.
            *args: Additional arguments passed to httpx.AsyncClient
            **kwargs: Additional keyword arguments passed to httpx.AsyncClient

        """
        self.config = config

        # Add authentication
        # kwargs["auth"] = self.config.authentication

        # Increase timeout
        kwargs["timeout"] = httpx.Timeout(HTTPX_TIMEOUT)

        # Set default values
        kwargs["base_url"] = kwargs.get("base_url") or SERVER_URL

        # Use pre-created SSL context if provided, or use config's SSL context
        if ssl_context is not None:
            kwargs["verify"] = ssl_context
        elif config.ssl_context is not None:
            kwargs["verify"] = config.ssl_context

        # Register event hooks
        kwargs["event_hooks"] = defaultdict(list, **kwargs.get("event_hooks", {}))

        async def log_request(request):
            _LOGGER.debug("Request: %s %s", request.method, request.url)

        async def log_response(response):
            await response.aread()
            request = response.request
            _LOGGER.debug("Response: %s %s - Status %d", request.method, request.url, response.status_code)

        kwargs["event_hooks"]["response"].append(log_response)
        kwargs["event_hooks"]["request"].append(log_request)

        # Event hook which calls raise_for_status on all requests
        async def raise_for_status_event_handler(response: httpx.Response):
            """Event handler that automatically raises HTTPStatusErrors when attached.

            Will read out response JSON for code and message
            """
            response_data = response.json()
            code = str(response_data["code"]) if "code" in response_data else None
            message = response_data.get("message", "")
            if message:
                self.last_message = message
            if code is None or code in ("1000", "200", "0"):
                return
            # Map cloud error codes to typed exceptions and let the CALLER decide
            # the remedy (refresh / re-bind VIN / surface). We intentionally do
            # NOT log in or re-bind here. Collapsing every code into a full
            # re-login is what wedged the integration into `unavailable`.
            if code == "1402":
                raise SmartTokenRefreshNecessary("Session token expired (code=1402)")
            if code == "8006":
                raise SmartHumanCarConnectionError(
                    "Human and vehicle relationship does not exist, select car and do request again."
                )
            if code == "1501":
                raise SmartMainTokenExpiredError(f"Main (OAuth) token expired (code=1501): {message}")
            if code == "8500":
                # Seen once, with an empty message, and it behaved exactly like a
                # main token expiry: requests kept failing until the token was
                # replaced. Treated as 1501 until a counter-example shows up.
                # Logged at WARNING so further occurrences are visible without
                # turning on debug.
                _LOGGER.warning("Cloud returned 8500 (treated as main token expiry). Message: %r", message)
                raise SmartMainTokenExpiredError(f"Main (OAuth) token expired (code=8500): {message}")
            if code == "4038":
                raise SmartVehicleNotInUseError(f"Vehicle not in use (code=4038): {message}")
            if code == "8040":
                raise SmartVehicleUnboundError(f"VIN not bound to account (code=8040): {message}")
            if code == "1443":
                raise SmartNonceError(f"Request nonce repeated (code=1443): {message}")
            if code == "8160":
                raise SmartNoPermissionError(f"No permission (code=8160): {message}")
            raise httpx.HTTPStatusError(
                response=response,
                request=response.request,
                message=f"{code}: {message}",
            )

        kwargs["event_hooks"]["response"].append(raise_for_status_event_handler)

        super().__init__(*args, **kwargs)
