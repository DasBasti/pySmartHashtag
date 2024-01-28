"""State and remote services of one vehicle."""

import datetime
import logging
from typing import Optional

from pysmarthashtag.models import ValueWithUnit, get_element_from_dict_maybe
from pysmarthashtag.vehicle.battery import Battery
from pysmarthashtag.vehicle.position import Position
from pysmarthashtag.vehicle.tires import Tires

_LOGGER = logging.getLogger(__name__)


class SmartVehicle:
    """Models state and remote services of one vehicle.

    :param account: The account associated with the vehicle.
    :param attributes: attributes of the vehicle as provided by the server.
    """

    data: dict = {}
    """The raw data of the vehicle."""

    odometer: Optional[ValueWithUnit] = None
    """The odometer of the vehicle."""

    battery: Optional[Battery] = None
    """The battery of the vehicle."""

    tires: Optional[Tires] = None
    """The tires of the vehicle."""

    position: Optional[Position] = None
    """The position of the vehicle."""

    def __init__(
        self,
        account: "SmartAccount",  # noqa: F821
        vehicle_base: dict,
        vehicle_state: Optional[dict] = None,
        charging_settings: Optional[dict] = None,
        fetched_at: Optional[datetime.datetime] = None,
    ) -> None:
        """Initialize the vehicle."""
        self.account = account
        self.combine_data(vehicle_base, vehicle_state, charging_settings, fetched_at)
        _LOGGER.debug(
            "Initialized vehicle %s (%s)",
            self.name,
            self.vin,
        )

    def combine_data(
        self,
        vehicle_base: dict,
        vehicle_state: Optional[dict] = None,
        charging_settings: Optional[dict] = None,
        fetched_at: Optional[datetime.datetime] = None,
    ) -> dict:
        """Combine all data into one dictionary."""
        self.data.update(vehicle_base)
        if vehicle_state:
            self.data.update(vehicle_state)
        if charging_settings:
            self.data.update(charging_settings)
        if fetched_at:
            self.data["fetched_at"] = fetched_at
        self._parse_data()
        self.battery = Battery.from_vehicle_data(self.data)
        self.tires = Tires.from_vehicle_data(self.data)
        self.position = Position.from_vehicle_data(self.data)

    def _parse_data(self) -> None:
        self.vin = self.data.get("vin")
        self.name = self.data.get("modelName")
        odometer = get_element_from_dict_maybe(
            self.data, "vehicleStatus", "additionalVehicleStatus", "maintenanceStatus", "odometer"
        )
        if odometer:
            self.odometer = ValueWithUnit(
                int(float(odometer)),
                "km",
            )
