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
    """
    Generate a timestamp string representing the current time in milliseconds since the Unix epoch.
    
    Returns:
        timestamp (str): Current time in milliseconds since 1970-01-01 UTC, formatted as a decimal string.
    """
    return str(int(time.time() * 1000))


def _ensure_bytes(body: Optional[object]) -> Optional[bytes]:
    """
    Normalize a request body to a UTF-8 bytes object when present.
    
    Parameters:
        body (Optional[object]): The value to normalize. If `None`, no conversion is performed.
    
    Returns:
        Optional[bytes]: `None` if input is `None`; the input unchanged if already `bytes`; otherwise the UTF-8 encoding of `str(body)`.
    """
    if body is None:
        return None
    if isinstance(body, bytes):
        return body
    return str(body).encode("utf-8")


def _global_md5_base64(body: bytes) -> str:
    """
    Return the first 24 characters of the base64-encoded MD5 digest of `body`.
    
    Parameters:
        body (bytes): Input bytes to hash.
    
    Returns:
        str: First 24 characters of the base64-encoded MD5 digest.
    """
    md5_hash = hashlib.md5(body).digest()
    return base64.b64encode(md5_hash).decode("utf-8")[:24]


def _build_global_string_to_sign(
    method: str,
    path: str,
    headers: dict[str, str],
    content_md5: str = "",
) -> str:
    """
    Construct the canonical string used to compute the HMAC-SHA256 signature for a Global API request.
    
    The resulting newline-separated string contains, in order: HTTP method, Accept header, the provided content MD5 value, Content-Type header, Date header, all `x-ca-*` headers (each as `key:value` on its own line), and the request path. This canonical string is intended to be the message passed to the signing HMAC.
    
    Parameters:
        method (str): HTTP method (e.g., "GET", "POST").
        path (str): Request path, including query string if applicable.
        headers (dict[str, str]): Request headers; values for "accept", "content-type", "date", and any `x-ca-*` headers are used.
        content_md5 (str): Base64-encoded MD5 of the request body when present, or an empty string if absent.
    
    Returns:
        str: The canonical string to sign with HMAC-SHA256.
    """
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
    """
    Create the HMAC-SHA256 signature used for Global API requests.
    
    If a request body is provided, its MD5 (base64, truncated to 24 chars) is computed and inserted into headers["content-md5"] before signing. The function builds the canonical string-to-sign from method, path, and headers, then returns the base64-encoded HMAC-SHA256 of that string using app_secret as the key.
    
    Parameters:
        headers (dict[str, str]): Request headers; this dict will be mutated to include "content-md5" when a body is provided.
    
    Returns:
        str: The base64-encoded HMAC-SHA256 signature.
    """
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
    """
    Builds HTTP headers for a Global API request and signs them with HMAC-SHA256.
    
    Assembles standard headers (date, content-type, host, user-agent, x-ca-timestamp, x-ca-nonce, x-ca-key, etc.), conditionally includes Authorization/x-smart-id/Xs-Auth-Token when provided, merges any extra_headers, and computes the `x-ca-signature` header using the provided `app_secret`.
    
    Parameters:
        method (str): HTTP method (e.g., "GET", "POST") used when computing the signature.
        path (str): Request path (URI) used in the signature calculation.
        host (str): Host header value for the request.
        app_key (str): Application key inserted as `x-ca-key`.
        app_secret (str): Secret used to compute the HMAC-SHA256 signature.
        body (Optional[object]): Request body; if provided it will be converted to bytes and included in the signature computation.
        content_type (str): Value for `content-type` and `accept` headers. Defaults to "application/json".
        access_token (Optional[str]): If provided, added as `Authorization: Bearer <token>`.
        user_id (Optional[str]): If provided, added as `x-smart-id`.
        id_token (Optional[str]): If provided, added as `Xs-Auth-Token` (and `Xs-App-Ver` is set).
        extra_headers (Optional[dict[str, str]]): Additional headers to merge into the final header set.
    
    Returns:
        dict[str, str]: A dictionary of HTTP headers ready to attach to the request, including the computed `x-ca-signature`.
    """
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