import base64
import hashlib
import hmac
import logging
import secrets
import time
import uuid
from email.utils import formatdate
from typing import Optional

_LOGGER = logging.getLogger(__name__)


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
    device_id: str, access_token: str, params: dict, method: str, url: str, body=None
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


def create_correct_timestamp() -> str:
    """Create a correct timestamp for the request."""
    return str(int(time.time() * 1000))


def _ensure_bytes(body: Optional[object]) -> Optional[bytes]:
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    return str(body).encode("utf-8")


def _global_md5_base64(body: bytes) -> str:
    """Calculate MD5 hash and return the first 24 chars of base64 encoding."""
    md5_hash = hashlib.md5(body).digest()
    return base64.b64encode(md5_hash).decode("utf-8")[:24]


def _build_global_string_to_sign(
    method: str,
    path: str,
    headers: dict[str, str],
    content_md5: str = "",
) -> str:
    """Build the string to sign for HMAC-SHA256 Global API requests."""
    string_to_sign = [
        method,
        headers.get("accept", ""),
        content_md5,
        headers.get("content-type", ""),
        headers.get("date", ""),
    ]

    ca_headers = []
    ca_header_names = []
    for key in sorted(headers.keys()):
        if key.startswith("x-ca-"):
            ca_headers.append(f"{key}:{headers[key]}")
            ca_header_names.append(key)

    if ca_header_names:
        headers["x-ca-signature-headers"] = ",".join(ca_header_names)

    string_to_sign.append("\n".join(ca_headers))
    string_to_sign.append(path)

    return "\n".join(string_to_sign)


def _generate_global_signature(
    app_secret: str,
    method: str,
    path: str,
    headers: dict[str, str],
    body: Optional[bytes] = None,
) -> str:
    """Generate HMAC-SHA256 signature for Global API requests."""
    content_md5 = ""
    if body is not None:
        content_md5 = _global_md5_base64(body)
        headers["content-md5"] = content_md5

    string_to_sign = _build_global_string_to_sign(method, path, headers, content_md5)
    signature = hmac.new(
        app_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def generate_global_header(
    method: str,
    path: str,
    host: str,
    app_key: str,
    app_secret: str,
    body: Optional[object] = None,
    content_type: str = "application/json",
    access_token: Optional[str] = None,
    user_id: Optional[str] = None,
    id_token: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Generate signed headers for Global app requests."""
    timestamp = create_correct_timestamp()
    nonce = str(uuid.uuid4())
    http_date = formatdate(timeval=None, localtime=False, usegmt=True)

    headers = {
        "date": http_date,
        "x-ca-timestamp": timestamp,
        "x-ca-nonce": nonce,
        "x-ca-key": app_key,
        "x-ca-signature-method": "HmacSHA256",
        "CA_VERSION": "1",
        "content-type": content_type,
        "accept": content_type,
        "host": host,
        "user-agent": "ALIYUN-ANDROID-DEMO",
    }

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if user_id:
        headers["x-smart-id"] = user_id
    if id_token:
        headers["Xs-Auth-Token"] = id_token
        headers["Xs-App-Ver"] = "1.0.8"

    if extra_headers:
        headers.update(extra_headers)

    body_bytes = _ensure_bytes(body)
    headers["x-ca-signature"] = _generate_global_signature(
        app_secret,
        method,
        path,
        headers,
        body_bytes,
    )

    _LOGGER.debug("Constructed global request header for %s %s", method, path)
    return headers
