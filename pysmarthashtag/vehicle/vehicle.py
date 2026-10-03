"""State and remote services of one vehicle."""

import datetime
import logging
from typing import Optional

from pysmarthashtag.const import (
    API_BASE_URL,
    API_BASE_URL_V2,
    SERIES_CODE_PREFIX_SMART_1,
    SERIES_CODE_PREFIX_SMART_3,
    SERIES_CODE_PREFIX_SMART_5,
)
from pysmarthashtag.models import ValueWithUnit, get_element_from_dict_maybe
from pysmarthashtag.vehicle.battery import Battery
from pysmarthashtag.vehicle.climate import Climate
from pysmarthashtag.vehicle.journal import TripJournal
from pysmarthashtag.vehicle.maintenance import Maintenance
from pysmarthashtag.vehicle.position import Position
from pysmarthashtag.vehicle.running import Running
from pysmarthashtag.vehicle.safety import Safety
from pysmarthashtag.vehicle.tires import Tires
from pysmarthashtag.vehicle.vehicle_state import VehicleState

_LOGGER = logging.getLogger(__name__)


class SmartVehicle:
    """Models state and remote services of one vehicle.

    :param account: The account associated with the vehicle.
    :param attributes: attributes of the vehicle as provided by the server.
    """

    data: dict
    """The raw data of the vehicle."""

    odometer: ValueWithUnit | None = None
    """The odometer of the vehicle."""

    battery: Battery | None = None
    """The battery of the vehicle."""

    tires: Tires | None = None
    """The tires of the vehicle."""

    position: Position | None = None
    """The position of the vehicle."""

    last_update: datetime.datetime | None = None
    """The last time the vehicle data was updated."""

    service: dict | None = {}

    maintenance: Maintenance | None = None
    """The maintenance status of the vehicle."""

    running: Running | None = None
    """The running status of the vehicle."""

    climate: Climate | None = None
    """The climate status of the vehicle."""

    safety: Safety | None = None
    """The safety status of the vehicle."""

    last_trip: TripJournal | None = None
    """The most recent trip from the journal log (server-side reverse-geocoded)."""

    state: VehicleState | None = None
    """Per-VIN TBox-side state flags from the GetCarState endpoint
    (journal recording, valet mode, privacy, next wakeup, etc.)."""

    climate_control: Optional["ClimateControll"] = None  # noqa: F821

    charging_control: Optional["ChargingControl"] = None  # noqa: F821
    """Control for starting/stopping charging."""

    journal_recording_control: Optional["JournalRecordingControl"] = None  # noqa: F821
    """Control for enabling/disabling on-vehicle trip recording."""

    door_lock_control: Optional["DoorLockControl"] = None  # noqa: F821
    """Control for remotely locking/unlocking the doors."""

    window_control: Optional["WindowControl"] = None  # noqa: F821
    """Control for opening/closing the windows."""

    horn_light_control: Optional["HornLightControl"] = None  # noqa: F821
    """Control for honking the horn and flashing the lights."""

    engine_state: str | None = None
    """The state of the engine."""

    base_url: str = API_BASE_URL

    def __init__(
        self,
        account: "SmartAccount",  # noqa: F821
        vehicle_base: dict,
        vehicle_state: dict | None = None,
        charging_settings: dict | None = None,
        fetched_at: datetime.datetime | None = None,
    ) -> None:
        """Initialize the vehicle."""
        self.account = account
        self.data = {}
        self.combine_data(vehicle_base, vehicle_state, charging_settings, None, fetched_at)
        if self.data["seriesCodeVs"].startswith(SERIES_CODE_PREFIX_SMART_1):
            _LOGGER.debug("Selected Vehicle is Smart #1 use V1 API")
            self.base_url = API_BASE_URL
        elif self.data["seriesCodeVs"].startswith(SERIES_CODE_PREFIX_SMART_3):
            _LOGGER.debug("Selected Vehicle is Smart #3 use V1 API")
            self.base_url = API_BASE_URL
        elif self.data["seriesCodeVs"].startswith(SERIES_CODE_PREFIX_SMART_5):
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
        vehicle_state: dict | None = None,
        charging_settings: dict | None = None,
        ota_info: dict | None = None,
        fetched_at: datetime.datetime | None = None,
        journal_response: dict | None = None,
        state_response: dict | None = None,
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
        if journal_response is not None:
            # Only overwrite when the caller actually has fresh journal data.
            # Other endpoints (e.g. status, SOC, OTA) call combine_data without
            # this kwarg and must not blow away an already-populated trip.
            self.last_trip = TripJournal.from_response(journal_response)
        if state_response is not None:
            # Same best-effort overwrite semantics as last_trip — only refresh
            # when the GetCarState fetch actually succeeded for this poll.
            self.state = VehicleState.from_response(state_response)

        from pysmarthashtag.control.climate import ClimateControll

        self.climate_control = ClimateControll(self.account, self.vin)

        from pysmarthashtag.control.charging import ChargingControl

        self.charging_control = ChargingControl(self.account, self.vin)

        from pysmarthashtag.control.journal import JournalRecordingControl

        self.journal_recording_control = JournalRecordingControl(self.account, self.vin)

        from pysmarthashtag.control.lock import DoorLockControl

        self.door_lock_control = DoorLockControl(self.account, self.vin)

        from pysmarthashtag.control.windows import WindowControl

        self.window_control = WindowControl(self.account, self.vin)

        from pysmarthashtag.control.horn_light import HornLightControl

        self.horn_light_control = HornLightControl(self.account, self.vin)

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
            self.last_update = datetime.datetime.fromtimestamp(int(last_update) / 1000, datetime.UTC)
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
