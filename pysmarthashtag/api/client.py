import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Optional

import httpx

from pysmarthashtag.api.authentication import SmartAuthentication
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

RESPONSE_STORE: Deque[AnonymizedResponse] = deque(maxlen=10)


@dataclass
class SmartClientConfiguration:
    """Stores global settings for SmartClient."""

    authentication: SmartAuthentication
    log_responses: Optional[bool] = False

    def set_log_responses(self, log_responses: bool) -> None:
        """Set if responses are logged and clear response store."""

        self.log_responses = log_responses
        RESPONSE_STORE.clear()


class SmartClient(httpx.AsyncClient):
    """Async HTTP client based on `httpx.AsyncClient` with automated OAuth token refresh."""

    last_message: str = ""

    def __init__(self, config: SmartClientConfiguration, *args, **kwargs):
        self.config = config

        # Add authentication
        # kwargs["auth"] = self.config.authentication

        # Increase timeout
        kwargs["timeout"] = httpx.Timeout(HTTPX_TIMEOUT)

        # Set default values
        kwargs["base_url"] = kwargs.get("base_url") or SERVER_URL

        # Register event hooks
        kwargs["event_hooks"] = defaultdict(list, **kwargs.get("event_hooks", {}))

        async def log_request(request):
            if request.method == "POST":
                await request.aread()
                _LOGGER.debug(
                    f"Request: {request.method} {request.url} - {request.headers} - {request.content.decode()}"
                )
            else:
                _LOGGER.debug(f"Request: {request.method} {request.url} - {request.headers}")

        async def log_response(response):
            await response.aread()
            request = response.request
            _LOGGER.debug(f"Response: {request.method} {request.url} - Status {response.status_code}")

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
