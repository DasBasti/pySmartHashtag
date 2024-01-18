"""Generals models used for pysmarthastag."""

import logging
from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import Dict, List, NamedTuple, Optional, Tuple, Union

_LOGGER = logging.getLogger(__name__)

class StrEnum(str, Enum):
    """Enumerate strings."""
    
    @classmethod
    def _missing_(cls, value):
        has_unknown = False
        for member in cls:
            if member.value.upper() == 'UNKNOWN':
                has_unknown = True
            if member.value.upper() == value.upper():
                return member
        if has_unknown:
            _LOGGER.warning("Unknown value %s for enum %s", value, cls.__name__)
            return getattr(cls, 'UNKNOWN')
        raise ValueError("%s is not a valid %s" % (value, cls.__name__))
    

@dataclass
class VehicleDataBase:
    """Base class for vehicle data."""

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


class SmartQuotaError(SmartAPIError):
    """Quota exceeded on Smart web API."""


class SmartRemoteServiceError(SmartAPIError):
    """Error when executing web services."""