"""Tests for VehicleState — the GetCarState parser."""

from datetime import datetime

from pysmarthashtag.vehicle.vehicle_state import VehicleState


CANONICAL_RESPONSE = {
    "code": "1000",
    "data": {
        "svtState": 1,
        "parkComfortState": 1,
        "btActive": 0,
        "valetModeState": 0,
        "pulseHeatActive": 0,
        "btTempActive": 0,
        "carLocatorActive": 1,
        "campingModeActive": 0,
        "nextWakeupTime": "1706002216000",  # epoch ms as string (real prod format)
        "driftModeActive": 0,
        "engineState": 0,
        "powerMode": "1",
        "positionUploadState": 1,
        "journalLogState": 0,
        "vstdState": 2,
        "overheatState": 1,
        "privacyMode": 0,
        "pncStatus": 0,
        "chatVideoMainActive": 0,
        "washCarModeActive": 0,
        "vin": "HESYA4C43SG204913",
    },
    "success": True,
    "hint": None,
    "httpStatus": "OK",
    "sessionId": "deadbeef",
    "message": "operation succeed",
}


def test_from_response_unwraps_envelope():
    """The envelope {code,data,success,...} is unwrapped to .data."""
    s = VehicleState.from_response(CANONICAL_RESPONSE)
    assert s is not None
    assert s.journal_log_state == 0
    assert s.position_upload_state == 1
    assert s.car_locator_active == 1
    assert s.svt_state == 1
    assert s.vin == "HESYA4C43SG204913"


def test_from_response_accepts_unwrapped_data():
    """Calling with just the inner data dict works too."""
    s = VehicleState.from_response(CANONICAL_RESPONSE["data"])
    assert s is not None
    assert s.engine_state == 0
    assert s.power_mode == "1"
    assert s.privacy_mode == 0


def test_next_wakeup_time_decoded():
    """Epoch-ms string decodes to a TZ-aware UTC datetime (~Jan 23, 2024 in this fixture)."""
    s = VehicleState.from_response(CANONICAL_RESPONSE)
    assert isinstance(s.next_wakeup_time, datetime)
    assert s.next_wakeup_time.year == 2024
    # Must be timezone-aware — HA TIMESTAMP device_class rejects naive datetimes.
    assert s.next_wakeup_time.tzinfo is not None


def test_next_wakeup_time_handles_garbage():
    """A non-numeric nextWakeupTime is silently dropped, not exception."""
    payload = dict(CANONICAL_RESPONSE["data"])
    payload["nextWakeupTime"] = "not-a-timestamp"
    s = VehicleState.from_response(payload)
    assert s is not None
    assert s.next_wakeup_time is None


def test_from_response_handles_none():
    assert VehicleState.from_response(None) is None
    assert VehicleState.from_response("not a dict") is None  # type: ignore[arg-type]


def test_from_response_handles_empty():
    assert VehicleState.from_response({}) is None
    # Envelope with no data still returns None (rather than empty VehicleState)
    assert VehicleState.from_response({"code": "8153", "data": None}) is None


def test_from_response_handles_partial_data():
    """Missing fields silently become None; doesn't blow up."""
    s = VehicleState.from_response({"data": {"journalLogState": 1}, "code": "1000"})
    assert s is not None
    assert s.journal_log_state == 1
    assert s.engine_state is None
    assert s.privacy_mode is None


def test_journal_log_state_flip_detection():
    """Practical use: did the toggle flip between two snapshots?"""
    before = VehicleState.from_response({"data": {"journalLogState": 0}, "code": "1000"})
    after = VehicleState.from_response({"data": {"journalLogState": 1}, "code": "1000"})
    assert before.journal_log_state != after.journal_log_state
    assert after.journal_log_state == 1
