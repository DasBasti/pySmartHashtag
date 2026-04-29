import base64
import hashlib
import hmac
import logging
import secrets
import time
from typing import Optional
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

# EU signing secret (base64 encoded)
EU_SECRET = base64.b64decode("NzRlNzQ2OWFmZjUwNDJiYmJlZDdiYmIxYjM2YzE1ZTk=")

# INTL (International) signing secret - used for Australia, Singapore, Israel, etc.
INTL_SECRET = b"30fb4a7b7fab4e2e8b52120d0087efdd"


def join_url_params(args: dict) -> str:
    """Join params for adding to URL."""
    return "&".join([f"{key}={value}" for key, value in args.items()])


def _create_sign(
    nonce: str,
    params: dict,
    timestamp: str,
    method: str,
    url: str,
    body: Optional[str] = None,
    use_intl: bool = False,
    url_encode_params: bool = False,
) -> str:
    """Create a signature for the request.

    Args:
    ----
        nonce: Random nonce for the request
        params: URL parameters as a dict
        timestamp: Timestamp in milliseconds
        method: HTTP method (GET, POST, etc.)
        url: API URL path (without domain)
        body: Request body for POST requests
        use_intl: If True, use INTL secret instead of EU secret
        url_encode_params: If True, URL-encode special chars in params (required for INTL GET requests)

    Returns:
    -------
        Base64-encoded HMAC-SHA1 signature.

    """
    md5sum = base64.b64encode(hashlib.md5(body.encode()).digest()).decode() if body else "1B2M2Y8AsgTpgAmY7PhCfg=="

    # URL encode params if needed (INTL GET requests require this for special chars like commas)
    if url_encode_params and params:
        encoded_params = {}
        for k, v in params.items():
            # URL encode special characters (commas, spaces, etc.)
            encoded_params[k] = quote(str(v), safe="")
        url_params = join_url_params(encoded_params)
    else:
        url_params = join_url_params(params) if params else ""

    payload = f"""application/json;responseformat=3
x-api-signature-nonce:{nonce}
x-api-signature-version:1.0

{url_params}
{md5sum}
{timestamp}
{method}
{url}"""
    _LOGGER.debug("Creating signature for request (INTL=%s)", use_intl)

    # Choose secret based on region
    secret = INTL_SECRET if use_intl else EU_SECRET

    payload_bytes = payload.encode("utf-8")
    hashed = hmac.new(secret, payload_bytes, hashlib.sha1).digest()
    signature = base64.b64encode(hashed).decode()
    return signature


def generate_default_header(
    device_id: str, access_token: str, params: dict, method: str, url: str, body: Optional[str] = None
) -> dict[str, str]:
    """Generate a header for HTTP requests to the server."""
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

    _LOGGER.debug("Constructed request header for %s %s", method, url)
    return header


def generate_intl_header(
    device_id: str,
    access_token: str,
    params: dict,
    method: str,
    url: str,
    body: Optional[str] = None,
    client_id: Optional[str] = None,
) -> dict[str, str]:
    """Generate a header for HTTP requests to the INTL (International) API.

    This is used for vehicles registered in Australia, Singapore, Israel,
    and other international markets using the Hello Smart International app.

    Args:
    ----
        device_id: Unique device identifier
        access_token: API access token from session/secure
        params: URL parameters as a dict
        method: HTTP method (GET, POST, etc.)
        url: API URL path (without domain)
        body: Request body for POST requests
        client_id: Client ID from session response

    Returns:
    -------
        Dict of headers for the request.

    """
    import uuid

    timestamp = create_correct_timestamp()
    nonce = str(uuid.uuid4()).upper()

    # INTL requires URL-encoded params in signature for GET requests with special chars
    url_encode_params = method.upper() == "GET"
    sign = _create_sign(nonce, params, timestamp, method, url, body, use_intl=True, url_encode_params=url_encode_params)

    # Get vehicle series from params if available (passed as _vehicle_series)
    vehicle_series = params.pop("_vehicle_series", None) if params else None
    if not vehicle_series:
        raise ValueError("vehicle_series is required for INTL API requests. Pass it in params as '_vehicle_series'.")

    header = {
        "x-app-id": "SMARTAPP-ISRAEL",
        "accept": "application/json;responseformat=3",
        "x-agent-type": "iOS",
        "x-device-type": "mobile",
        "x-operator-code": "SMART-ISRAEL",
        "x-device-identifier": device_id,
        "x-env-type": "production",
        "accept-language": "en_US",
        "x-api-signature-version": "1.0",
        "x-api-signature-nonce": nonce,
        "x-device-manufacture": "Apple",
        "x-device-brand": "Apple",
        "x-device-model": "iPhone",
        "x-agent-version": "18.6.1",
        "content-type": "application/json",
        "user-agent": "GlobalSmart/1.0.7 (iPhone; iOS 18.6.1; Scale/3.00)",
        "x-signature": sign,
        "x-timestamp": timestamp,
        "platform": "NON-CMA",
        "x-vehicle-series": vehicle_series,
    }

    if access_token:
        header["authorization"] = access_token

    if client_id:
        header["x-client-id"] = client_id

    _LOGGER.debug("Constructed INTL request header for %s %s", method, url)
    return header


def create_correct_timestamp() -> str:
    """Create a correct timestamp for the request."""
    return str(int(time.time() * 1000))
