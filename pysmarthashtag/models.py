"""Generals models used for pysmarthastag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, NamedTuple, Optional, Union

_LOGGER = logging.getLogger(__name__)


class StrEnum(str, Enum):
    """Enumerate strings."""

    @classmethod
    def _missing_(cls, value):
        has_unknown = False
        for member in cls:
            if member.value.upper() == "UNKNOWN":
                has_unknown = True
            if member.value.upper() == value.upper():
                return member
        if has_unknown:
            _LOGGER.warning("Unknown value %s for enum %s", value, cls.__name__)
            return getattr(cls, "UNKNOWN")
        raise ValueError(f"{value} is not a valid {cls.__name__}")


@dataclass
class VehicleDataBase:
    """Base class for vehicle data."""

    timestamp: Optional[datetime] = None

    @classmethod
    def from_vehicle_data(cls, vehicle_data: dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    def update_from_vehicle_data(self, vehicle_data: dict):
        """Update the instance with data from API."""
        parsed = self._parse_vehicle_data(vehicle_data) or {}
        parsed.update(self._update_after_parse(vehicle_data))
        if len(parsed) > 0:
            self.__dict__.update(parsed)

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: dict) -> Optional[dict]:
        """Parse the vehicle data."""
        raise NotImplementedError()

    def _update_after_parse(self, parsed: dict) -> dict:
        """Update the instance with data from API."""
        return parsed


class ValueWithUnit(NamedTuple):
    """A value with a corresponding unit."""

    value: Optional[Union[int, float]]
    unit: Optional[str]


@dataclass
class AnonymizedResponse:
    """An anonymized response."""

    filename: str
    content: Optional[Union[list, dict, str]] = None


class SmartAPIError(Exception):
    """General Smart web API error."""


class SmartAuthError(SmartAPIError):
    """Auth-related error from Smart web API (HTTP status codes 401 and 403)."""


class SmartTokenRefreshNecessary(SmartAPIError):
    """Token refresh is necessary (Response Code 1402)."""


class SmartHumanCarConnectionError(SmartAPIError):
    """Human and vehicle connection does not exist (Response Code 8006)."""


class SmartQuotaError(SmartAPIError):
    """Quota exceeded on Smart web API."""


class SmartRemoteServiceError(SmartAPIError):
    """Error when executing web services."""


def get_element_from_dict_maybe(
    data: dict, *path: str, default: "Any|None" = None
) -> Optional[Union[dict, str, int, float]]:
    """Get an element from a dict by path."""
    if len(path) == 0:
        return data
    if path[0] not in data:
        return default
    return get_element_from_dict_maybe(data[path[0]], *path[1:])


def get_field_as_type(
    data: dict,
    field: str,
    target_type: type,
    log_missing: bool = False,
) -> Optional[Union[int, float, bool, str]]:
    """Get a field from a dict and convert it to the target type.

    This function safely extracts a field from a dictionary and converts it
    to the specified type. If the field is missing or the conversion fails,
    it logs an error and returns None without raising an exception.

    Args:
    ----
        data: The dictionary to extract the field from.
        field: The field name to extract.
        target_type: The target type to convert the value to (int, float, bool, str).
        log_missing: Whether to log an error when the field is missing (default False).

    Returns:
    -------
        The converted value or None if the field is missing or conversion fails.

    """
    if field not in data:
        if log_missing:
            _LOGGER.error("Field '%s' not found in data", field)
        return None

    value = data[field]
    if value is None:
        if log_missing:
            _LOGGER.error("Field '%s' has None value", field)
        return None

    try:
        if target_type is bool:
            # Handle string booleans like "true", "false", "0", "1"
            if isinstance(value, str):
                return value.lower() in ("true", "1")
            return bool(value)
        return target_type(value)
    except (ValueError, TypeError) as e:
        _LOGGER.error("Failed to convert field '%s' value '%s' to %s: %s", field, value, target_type.__name__, e)
        return None
