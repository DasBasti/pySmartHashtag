import base64
import hashlib
import hmac
import logging
import secrets
import time
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

# Endpoints that must NOT carry the per-request X-Vehicle-* headers (the VIN is
# irrelevant there / already travels in the request body).
_VIN_HEADER_BLACKLIST = ("/user/session/update", "/geelyTCAccess/tcservices/capability/")


def join_url_params(args: dict) -> str:
    """Join params for adding to URL."""
    return "&".join([f"{key}={value}" for key, value in args.items()])


def _create_sign(nonce: str, params: dict, timestamp: str, method: str, url: str, body=None) -> str:
    """Create a signature for the request."""
    md5sum = base64.b64encode(hashlib.md5(body.encode()).digest()).decode() if body else "1B2M2Y8AsgTpgAmY7PhCfg=="
    url_params = join_url_params(params)
    payload = f"""application/json;responseformat=3
x-api-signature-nonce:{nonce}
x-api-signature-version:1.0

{url_params}
{md5sum}
{timestamp}
{method}
{url}"""
    _LOGGER.debug("Creating signature for request")
    secret = base64.b64decode("NzRlNzQ2OWFmZjUwNDJiYmJlZDdiYmIxYjM2YzE1ZTk=")
    payload = payload.encode("utf-8")
    hashed = hmac.new(secret, payload, hashlib.sha1).digest()
    signature = base64.b64encode(hashed).decode()
    return signature


def generate_default_header(
    device_id: str,
    access_token: str,
    params: dict,
    method: str,
    url: str,
    body=None,
    vin: str = None,
    model_code: str = None,
) -> dict[str, str]:
    """Generate a header for HTTP requests to the server.

    With ``vin`` and ``model_code`` (the vehicle ``matCode``), adds the
    per-request VIN headers so the server does not rely on the account-wide
    "active vehicle" binding, which another client can steal by switching cars.
    """
    timestamp = create_correct_timestamp()
    nonce = secrets.token_hex(8)
    sign = _create_sign(nonce, params, timestamp, method, url, body)
    header = {
        "x-app-id": "SmartAPPEU",
        "accept": "application/json;responseformat=3",
        "x-agent-type": "iOS",
        "x-device-type": "mobile",
        "x-operator-code": "SMART",
        "x-device-identifier": device_id,
        "x-env-type": "production",
        "x-version": "smartNew",
        "accept-language": "en_US",
        "x-api-signature-version": "1.0",
        "x-api-signature-nonce": nonce,
        "x-device-manufacture": "Apple",
        "x-device-brand": "Apple",
        "x-device-model": "iPhone",
        "x-agent-version": "17.1",
        "content-type": "application/json; charset=utf-8",
        "user-agent": "Hello smart/1.4.0 (iPhone; iOS 17.1; Scale/3.00)",
        "x-signature": sign,
        "x-timestamp": str(timestamp),
    }
    if access_token:
        header["authorization"] = access_token

    # Per-request VIN-binding headers (see docstring). Skip blacklisted endpoints.
    if vin and model_code and not any(b in url for b in _VIN_HEADER_BLACKLIST):
        encoded = quote(model_code, safe="")
        header["X-Vehicle-IDENTIFIER"] = vin
        header["X-VEHICLE-SERIES"] = encoded
        header["X-VEHICLE-MODEL"] = encoded

    _LOGGER.debug("Constructed request header for %s %s", method, url)
    return header


def create_correct_timestamp() -> str:
    """Create a correct timestamp for the request."""
    return str(int(time.time() * 1000))
