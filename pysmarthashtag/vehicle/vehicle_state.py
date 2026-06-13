"""VehicleState model — parses the GetCarState endpoint response.

The smart cloud exposes a small flat-dict state-flag endpoint that's
distinct from the big ``/remote-control/vehicle/status/{vin}`` payload
that ``Battery``/``Maintenance``/etc. parse. Hello # uses this endpoint
to confirm command dispatch (e.g. polls ``journalLogState`` after
flipping the trip-recording toggle).

Source endpoint:
    GET /remote-control/vehicle/status/state/{vin}    (no params)

Response shape (envelope is the standard ``{code, data, success, …}``):
    {"data": {"journalLogState": 0,
              "positionUploadState": 1,
              "carLocatorActive": 1,
              "engineState": 0,
              "powerMode": "1",
              "nextWakeupTime": "1706002216000",
              "valetModeState": 0,
              "campingModeActive": 0, "driftModeActive": 0,
              "washCarModeActive": 0, "chatVideoMainActive": 0,
              "parkComfortState": 1, "privacyMode": 0,
              "pulseHeatActive": 0, "overheatState": 0,
              "btActive": 0, "btTempActive": 0,
              "svtState": 1, "pncStatus": 0,
              "vstdState": 2,
              "vin": "..."}}
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pysmarthashtag.models import VehicleDataBase, get_field_as_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class VehicleState(VehicleDataBase):
    """Per-VIN TBox-side state flags from the GetCarState endpoint."""

    journal_log_state: Optional[int] = None
    """Trip recording on the TBox (0=off, 1=on). Toggled by Hello #'s
    'Record trips on vehicle' setting; required for ``journalLogV4`` to
    return populated trip data."""

    position_upload_state: Optional[int] = None
    """TBox uploading GPS position to cloud (0=off, 1=on)."""

    car_locator_active: Optional[int] = None
    """Car-locator GPS service active (0=off, 1=on)."""

    next_wakeup_time: Optional[datetime] = None
    """Next scheduled TBox wakeup. Useful operationally — remote commands
    sent before this time may be slow (TBox is asleep) or queued."""

    engine_state: Optional[int] = None
    """Engine on/off (0=off, 1=on). Note: integer encoding here is distinct
    from the string ``engineStatus`` (\"engine_off\" / \"engine_on\") in
    the full ``/vehicle/status/{vin}`` response."""

    power_mode: Optional[str] = None
    """Power mode reported as a string (e.g. \"0\", \"1\", \"2\")."""

    valet_mode_state: Optional[int] = None
    """Valet mode active (0=off, 1=on)."""

    camping_mode_active: Optional[int] = None
    """Camping mode (climate keeps running while parked)."""

    drift_mode_active: Optional[int] = None
    """Drift mode (Smart 5 Brabus performance feature)."""

    wash_car_mode_active: Optional[int] = None
    """Car-wash mode (sensors/windows prepped for car wash)."""

    chat_video_main_active: Optional[int] = None
    """In-car video-chat / front-camera mode active."""

    park_comfort_state: Optional[int] = None
    """Park-comfort climate mode."""

    privacy_mode: Optional[int] = None
    """Privacy mode (cameras/microphones disabled)."""

    pulse_heat_active: Optional[int] = None
    """Battery pulse-heating active (winter preconditioning)."""

    overheat_state: Optional[int] = None
    """Cabin overheat protection currently active."""

    bt_active: Optional[int] = None
    """Bluetooth main session active."""

    bt_temp_active: Optional[int] = None
    """Bluetooth temporary session active."""

    svt_state: Optional[int] = None
    """Stolen Vehicle Tracking subsystem state."""

    pnc_status: Optional[int] = None
    """Plug-and-Charge contract status."""

    vstd_state: Optional[int] = None
    """VSTD subsystem state. Read from GetCarState; exact semantics are not
    fully reverse-engineered, surfaced as best-effort for downstream consumers
    that may have observed it in their own captures."""

    vin: Optional[str] = None
    """VIN echoed by the cloud (sanity check that response is for the
    requested vehicle)."""

    @classmethod
    def from_response(cls, response: Any) -> Optional["VehicleState"]:
        """Build a VehicleState from a GetCarState response body.

        Accepts either the full envelope ``{code, data: {...}, success, …}``
        or the unwrapped ``data`` dict directly. Returns ``None`` when the
        response is empty / malformed / a non-success error envelope.
        """
        if not isinstance(response, dict):
            return None
        # If it's a response envelope (has top-level "code"), require a
        # non-empty dict in "data" — otherwise return None (covers error
        # envelopes like {"code": "8153", "data": null}).
        if "code" in response:
            data = response.get("data")
            if not isinstance(data, dict) or not data:
                return None
        else:
            data = response
        if not data:
            return None

        next_wake: Optional[datetime] = None
        nw = data.get("nextWakeupTime")
        if nw is not None:
            try:
                # Cloud reports as epoch milliseconds, sometimes as a string.
                # Use UTC-aware datetime so HA's TIMESTAMP device_class accepts it.
                next_wake = datetime.fromtimestamp(int(nw) / 1000, tz=timezone.utc)
            except (TypeError, ValueError):
                _LOGGER.debug("nextWakeupTime not parseable: %r", nw)

        return cls(
            journal_log_state=get_field_as_type(data, "journalLogState", int),
            position_upload_state=get_field_as_type(data, "positionUploadState", int),
            car_locator_active=get_field_as_type(data, "carLocatorActive", int),
            next_wakeup_time=next_wake,
            engine_state=get_field_as_type(data, "engineState", int),
            power_mode=get_field_as_type(data, "powerMode", str),
            valet_mode_state=get_field_as_type(data, "valetModeState", int),
            camping_mode_active=get_field_as_type(data, "campingModeActive", int),
            drift_mode_active=get_field_as_type(data, "driftModeActive", int),
            wash_car_mode_active=get_field_as_type(data, "washCarModeActive", int),
            chat_video_main_active=get_field_as_type(data, "chatVideoMainActive", int),
            park_comfort_state=get_field_as_type(data, "parkComfortState", int),
            privacy_mode=get_field_as_type(data, "privacyMode", int),
            pulse_heat_active=get_field_as_type(data, "pulseHeatActive", int),
            overheat_state=get_field_as_type(data, "overheatState", int),
            bt_active=get_field_as_type(data, "btActive", int),
            bt_temp_active=get_field_as_type(data, "btTempActive", int),
            svt_state=get_field_as_type(data, "svtState", int),
            pnc_status=get_field_as_type(data, "pncStatus", int),
            vstd_state=get_field_as_type(data, "vstdState", int),
            vin=get_field_as_type(data, "vin", str),
        )
