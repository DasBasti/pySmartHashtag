"""State and remote services of one vehicle."""

import datetime
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type

from pysmarthashtag.models import StrEnum

_LOGGER = logging.getLogger(__name__)

class SmartVehicle:
    """Models state and remote services of one vehicle.

    :param account: The account associated with the vehicle.
    :param attributes: attributes of the vehicle as provided by the server.
    """

    def __init__(
        self,
        account: "SmartAccount",
        vehicle_base: dict,
        vehicle_state: Optional[dict] = None,
        charging_settings: Optional[dict] = None,
        fetched_at: Optional[datetime.datetime] = None,
    ) -> None:
        """Initialize the vehicle."""
        self.account = account
        self.data = self.combine_data(vehicle_base, vehicle_state, charging_settings, fetched_at)

    def combine_data(
        self,
        vehicle_base: dict,
        vehicle_state: Optional[dict] = None,
        charging_settings: Optional[dict] = None,
        fetched_at: Optional[datetime.datetime] = None,
    ) -> dict:
        """Combine all data into one dictionary."""
        data = vehicle_base.copy()
        if vehicle_state:
            data.update(vehicle_state)
        if charging_settings:
            data.update(charging_settings)
        if fetched_at:
            data["fetched_at"] = fetched_at
        return data
