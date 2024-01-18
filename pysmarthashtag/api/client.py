import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

import httpx

from pysmarthashtag.api.authentication import SmartAuthentication
from pysmarthashtag.const import (
    HTTPX_TIMEOUT,
    SERVER_URL,
)
from pysmarthashtag.models import AnonymizedResponse

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

    def __init__(self, config: SmartClientConfiguration, *args, **kwargs):
        self.config = config

        # Add authentication
        kwargs["auth"] = self.config.authentication

        # Increase timeout
        kwargs["timeout"] = httpx.Timeout(HTTPX_TIMEOUT)

        # Set default values
        kwargs["base_url"] = kwargs.get("base_url") or SERVER_URL

        # Register event hooks
        kwargs["event_hooks"] = defaultdict(list, **kwargs.get("event_hooks", {}))

        # Event hook for logging content
        async def log_response(response: httpx.Response):
            await response.aread()
            RESPONSE_STORE.append(response)

        if config.log_responses:
            kwargs["event_hooks"]["response"].append(log_response)

        # Event hook which calls raise_for_status on all requests
        async def raise_for_status_event_handler(response: httpx.Response):
            """Event handler that automatically raises HTTPStatusErrors when attached.

            Will only raise on 4xx/5xx errors but not 401/429 which are handled `self.auth`.
            """
            if response.is_error and response.status_code not in [401, 429]:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    _LOGGER.error(
                        "Error handling request %s: %s",
                        response.url,
                        ex,
                    )
                    raise

        kwargs["event_hooks"]["response"].append(raise_for_status_event_handler)

        super().__init__(*args, **kwargs)

    def generate_default_header(self, params, method: str, url: str) -> Dict[str, str]:
        """Generate a header for HTTP requests to the server."""
        timestamp = int(time.time())
        nonce = secrets.token_hex(8)
        sign = self._create_sign(nonce, params, timestamp, method, url)
        header = {
            "x-app-id": "SmartAPPEU",
            "accept": "application/json;responseformat=3",
            "x-agent-type": "iOS",
            "x-device-type": "mobile",
            "x-operator-code": "SMART",
            "x-device-identifier": self.config.authentication.device_id,
            "x-env-type": "production",
            "x-version": "smartNew",
            "accept-language": "en_US",
            "x-api-signature-version": "1.0",
            "x-api-signature-nonce": nonce,
            "x-device-manufacture": "Apple",
            "x-device-brand": "Apple",
            "x-device-model": "iPhone",
            "x-agent-version": "17.1",
            "authorization": self.config.authentication.access_token or "",
            "content-type": "application/json; charset=utf-8",
            "user-agent": "Hello smart/1.4.0 (iPhone; iOS 17.1; Scale/3.00)",
            "x-signature": sign,
            "x-timestamp": str(timestamp)
        }
        _LOGGER.debug("Header: %s", header)
        return header

    def _create_sign(self, nonce, params, timestamp, method, url, body=None):
        """Create a signature for the request."""
        md5sum = hashlib.md5(json.dumps(body).encode('utf-8')) if body else "1B2M2Y8AsgTpgAmY7PhCfg=="
        url_params = "&".join([f"{key}={value}" for key, value in params.items()])
        payload = f"""application/json;responseformat=3
x-api-signature-nonce:{nonce}
x-api-signature-version:1.0

{url_params}
{md5sum}
{timestamp}
{method}
{url}"""
        _LOGGER.debug("Payload: %s", payload)
        secret = base64.b64decode("NzRlNzQ2OWFmZjUwNDJiYmJlZDdiYmIxYjM2YzE1ZTk=")
        payload = payload.encode("utf-8")
        hashed = hmac.new(secret, payload, hashlib.sha1).digest()
        signature = base64.b64encode(hashed)
        _LOGGER.debug("Signature: %s", signature)
        return signature
