"""Log sanitization utilities to hide sensitive data from logs."""

import re
from typing import Any, Union

# Fields that should be masked in log output
SENSITIVE_FIELDS = frozenset(
    {
        # VIN
        "vin",
        # User identifiers
        "username",
        "userid",
        "user_id",
        "loginid",
        "login_id",
        "apiuserid",
        "api_user_id",
        # Tokens
        "accesstoken",
        "access_token",
        "refreshtoken",
        "refresh_token",
        "apiaccesstoken",
        "api_access_token",
        "apirefreshtoken",
        "api_refresh_token",
        "sessiontoken",
        "session_token",
        "login_token",
        "logintoken",
        "authorization",
        "token",
        # Session identifiers
        "deviceid",
        "device_id",
        "sessionid",
        "session_id",
    }
)

# Regex patterns for VIN and tokens in text
VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
TOKEN_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-]+\.?[A-Za-z0-9_\-]*\.?[A-Za-z0-9_\-]*")

# Pre-computed normalized sensitive field names for efficient lookup
_NORMALIZED_SENSITIVE_FIELDS = frozenset(f.replace("_", "") for f in SENSITIVE_FIELDS)


def _mask_value(value: str, visible_chars: int = 4) -> str:
    """Mask a sensitive value, showing only the last few characters.

    Args:
    ----
        value: The value to mask
        visible_chars: Number of characters to show at the end

    Returns:
    -------
        Masked string with '***' prefix

    """
    if not isinstance(value, str):
        return "***"
    if len(value) <= visible_chars:
        return "***"
    return f"***{value[-visible_chars:]}"


def _sanitize_dict(data: dict, depth: int = 0, max_depth: int = 10) -> dict:
    """Recursively sanitize a dictionary by masking sensitive fields.

    Args:
    ----
        data: Dictionary to sanitize
        depth: Current recursion depth
        max_depth: Maximum recursion depth to prevent infinite loops

    Returns:
    -------
        Sanitized dictionary copy

    """
    if depth > max_depth:
        return {"...": "max depth reached"}

    result = {}
    for key, value in data.items():
        lower_key = key.lower().replace("-", "").replace("_", "")
        if lower_key in _NORMALIZED_SENSITIVE_FIELDS:
            result[key] = _mask_value(str(value)) if value else value
        elif isinstance(value, dict):
            result[key] = _sanitize_dict(value, depth + 1, max_depth)
        elif isinstance(value, list):
            result[key] = _sanitize_list(value, depth + 1, max_depth)
        else:
            result[key] = value
    return result


def _sanitize_list(data: list, depth: int = 0, max_depth: int = 10) -> list:
    """Recursively sanitize a list.

    Args:
    ----
        data: List to sanitize
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
    -------
        Sanitized list copy

    """
    if depth > max_depth:
        return ["...max depth reached"]

    result = []
    for item in data:
        if isinstance(item, dict):
            result.append(_sanitize_dict(item, depth + 1, max_depth))
        elif isinstance(item, list):
            result.append(_sanitize_list(item, depth + 1, max_depth))
        else:
            result.append(item)
    return result


def _sanitize_string(data: str) -> str:
    """Sanitize a string by masking VINs, tokens, and potentially sensitive content.

    Args:
    ----
        data: String to sanitize

    Returns:
    -------
        Sanitized string

    """
    # Mask VINs
    result = VIN_PATTERN.sub(lambda m: _mask_value(m.group()), data)
    # Mask Bearer tokens
    result = TOKEN_PATTERN.sub(r"\1***", result)

    # As a defensive fallback, avoid logging very long or opaque strings in full.
    # This helps when upstream services accidentally include secrets in generic
    # "message" fields that do not match our specific patterns.
    max_visible_length = 80
    if len(result) > max_visible_length:
        # Preserve only a short prefix/suffix to keep logs useful while hiding content.
        prefix = result[:40]
        suffix = result[-10:]
        return f"{prefix}***{suffix}"

    return result


def sanitize_log_data(data: Any) -> Any:
    """Sanitize data for logging by masking sensitive fields.

    This function handles dicts, lists, and strings, recursively
    sanitizing nested structures.

    Args:
    ----
        data: Data to sanitize (dict, list, or str)

    Returns:
    -------
        Sanitized copy of the data

    """
    if isinstance(data, dict):
        return _sanitize_dict(data)
    elif isinstance(data, list):
        return _sanitize_list(data)
    elif isinstance(data, str):
        return _sanitize_string(data)

    # For any other type (including numbers, custom objects, etc.), avoid
    # returning the raw value to prevent accidental leakage of sensitive data.
    # Represent the value generically instead.
    return f"<sanitized {type(data).__name__}>"


def get_data_summary(data: dict, include_keys: Union[list, None] = None) -> str:
    """Create a concise summary of data for logging.

    Instead of logging the entire data object, this creates a brief summary
    showing key information.

    Args:
    ----
        data: Data dictionary to summarize
        include_keys: Specific keys to include in summary, or None for auto-detection

    Returns:
    -------
        A brief summary string

    """
    if not isinstance(data, dict):
        return f"<{type(data).__name__}>"

    if include_keys:
        items = [(k, data.get(k)) for k in include_keys if k in data]
    else:
        # Auto-detect: include non-sensitive, non-nested keys
        items = [
            (k, v)
            for k, v in data.items()
            if k.lower().replace("-", "").replace("_", "") not in _NORMALIZED_SENSITIVE_FIELDS
            and not isinstance(v, (dict, list))
        ][:5]  # Limit to 5 items

    if not items:
        return f"<dict with {len(data)} keys>"

    summary_parts = [f"{k}={v}" for k, v in items]
    return f"{{{', '.join(summary_parts)}}}"
