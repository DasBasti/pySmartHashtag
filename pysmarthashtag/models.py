"""Generals models used for pysmarthastag."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Union

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
    def from_vehicle_data(cls, vehicle_data: Dict):
        """Create a new instance based on data from API."""
        parsed = cls._parse_vehicle_data(vehicle_data) or {}
        if len(parsed) > 0:
            return cls(**parsed)
        return None

    def update_from_vehicle_data(self, vehicle_data: Dict):
        """Update the instance with data from API."""
        parsed = self._parse_vehicle_data(vehicle_data) or {}
        parsed.update(self._update_after_parse(vehicle_data))
        if len(parsed) > 0:
            self.__dict__.update(parsed)

    @classmethod
    def _parse_vehicle_data(cls, vehicle_data: Dict) -> Optional[Dict]:
        """Parse the vehicle data."""
        raise NotImplementedError()

    def _update_after_parse(self, parsed: Dict) -> Dict:
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
    content: Optional[Union[List, Dict, str]] = None


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
