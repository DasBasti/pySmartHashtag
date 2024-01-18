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
        self.data = self.combine_data(account, vehicle_base, vehicle_state, charging_settings, fetched_at)
        #self.remote_services = 

        