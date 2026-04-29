"""State and remote services of one vehicle."""

import datetime
import logging
from typing import Optional

from pysmarthashtag.const import API_BASE_URL, API_BASE_URL_V2
from pysmarthashtag.models import ValueWithUnit, get_element_from_dict_maybe
from pysmarthashtag.vehicle.basic_status import BasicStatus
from pysmarthashtag.vehicle.battery import Battery
from pysmarthashtag.vehicle.climate import Climate
from pysmarthashtag.vehicle.maintenance import Maintenance
from pysmarthashtag.vehicle.position import Position
from pysmarthashtag.vehicle.running import Running
from pysmarthashtag.vehicle.safety import Safety
from pysmarthashtag.vehicle.tires import Tires
from pysmarthashtag.vehicle.trailer import Trailer

_LOGGER = logging.getLogger(__name__)


class SmartVehicle:
    """Models state and remote services of one vehicle.

    :param account: The account associated with the vehicle.
    :param attributes: attributes of the vehicle as provided by the server.
    """

    data: dict
    """The raw data of the vehicle."""

    odometer: Optional[ValueWithUnit] = None
    """The odometer of the vehicle."""

    battery: Optional[Battery] = None
    """The battery of the vehicle."""

    tires: Optional[Tires] = None
    """The tires of the vehicle."""

    position: Optional[Position] = None
    """The position of the vehicle."""

    last_update: Optional[datetime.datetime] = None
    """The last time the vehicle data was updated."""

    service: Optional[dict] = {}

    maintenance: Optional[Maintenance] = None
    """The maintenance status of the vehicle."""

    running: Optional[Running] = None
    """The running status of the vehicle."""

    climate: Optional[Climate] = None
    """The climate status of the vehicle."""

    safety: Optional[Safety] = None
    """The safety status of the vehicle."""

    basic_status: Optional[BasicStatus] = None
    """The basic status of the vehicle (speed, engine, eGuard, park time, etc.)."""

    trailer: Optional[Trailer] = None
    """The trailer status of the vehicle."""

    climate_control: Optional["ClimateControll"] = None  # noqa: F821

    charging_control: Optional["ChargingControl"] = None  # noqa: F821
    """Control for starting/stopping charging."""

    engine_state: Optional[str] = None
    """The state of the engine."""

    base_url: str = API_BASE_URL

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
        self.data = {}
        self.combine_data(vehicle_base, vehicle_state, charging_settings, None, fetched_at)
        if self.data["seriesCodeVs"].startswith("HX"):
            _LOGGER.debug("Selected Vehicle is Smart #1 use V1 API")
            self.base_url = API_BASE_URL
        elif self.data["seriesCodeVs"].startswith("HC"):
            _LOGGER.debug("Selected Vehicle is Smart #3 use V1 API")
            self.base_url = API_BASE_URL
        elif self.data["seriesCodeVs"].startswith("HY"):
            _LOGGER.debug("Selected Vehicle is Smart #5 use V2 API")
            self.base_url = API_BASE_URL_V2
        else:
            _LOGGER.warning("Unknown Series Code Prefix %s use default API", self.data["seriesCodeVs"])
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
        ota_info: Optional[dict] = None,
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
        if ota_info:
            self.data["ota"] = {**ota_info}
        self._parse_data()
        self.battery = Battery.from_vehicle_data(self.data)
        self.tires = Tires.from_vehicle_data(self.data)
        self.position = Position.from_vehicle_data(self.data)
        self.maintenance = Maintenance.from_vehicle_data(self.data)
        self.running = Running.from_vehicle_data(self.data)
        self.climate = Climate.from_vehicle_data(self.data)
        self.safety = Safety.from_vehicle_data(self.data)
        self.basic_status = BasicStatus.from_vehicle_data(self.data)
        self.trailer = Trailer.from_vehicle_data(self.data)

        from pysmarthashtag.control.climate import ClimateControll

        self.climate_control = ClimateControll(self.account, self.vin)

        from pysmarthashtag.control.charging import ChargingControl

        self.charging_control = ChargingControl(self.account, self.vin)

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
        last_update = get_element_from_dict_maybe(self.data, "vehicleStatus", "updateTime")
        if last_update:
            self.last_update = datetime.datetime.fromtimestamp(int(last_update) / 1000, datetime.timezone.utc)
        days_to_service = get_element_from_dict_maybe(
            self.data, "vehicleStatus", "additionalVehicleStatus", "maintenanceStatus", "daysToService"
        )
        distance_to_service = get_element_from_dict_maybe(
            self.data, "vehicleStatus", "additionalVehicleStatus", "maintenanceStatus", "distanceToService"
        )
        self.service["daysToService"] = int(days_to_service) if days_to_service else None
        self.service["distanceToService"] = ValueWithUnit(distance_to_service, "km") if distance_to_service else None

        self.engine_state = get_element_from_dict_maybe(
            self.data, "vehicleStatus", "basicVehicleStatus", "engineStatus"
        )
