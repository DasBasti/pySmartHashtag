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
    SmartTokenRefreshNecessary,
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
            if "message" in response_data:
                self.last_message = response_data["message"]
            if "code" in response_data and response_data["code"] == "1402":
                await self.config.authentication.login()
                raise SmartTokenRefreshNecessary("Token expired, refresh token, do request again.")
            if "code" in response_data and response_data["code"] == "8006":
                raise SmartHumanCarConnectionError(
                    "Human and vehicle relationship does not exist, selct car and do request again."
                )
            elif "code" in response_data and response_data["code"] != "1000" and "message" in response_data:
                raise httpx.HTTPStatusError(
                    response=response,
                    request=response.request,
                    message=f"{response_data['code']}: {response_data['message']}",
                )

        kwargs["event_hooks"]["response"].append(raise_for_status_event_handler)

        super().__init__(*args, **kwargs)
