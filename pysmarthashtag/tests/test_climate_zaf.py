"""Tests for the Smart #5 ZAF climate payload with seat ventilation."""

import json
from types import SimpleNamespace

import httpx
import pytest

from pysmarthashtag.control.climate import (
    ZAF_PENDING_DELAY,
    ZAF_PENDING_RETRIES,
    ClimateControll,
    HeatingLocation,
    VentilationLocation,
)


def _ctrl(use_zaf: bool = True) -> ClimateControll:
    account = SimpleNamespace(config=SimpleNamespace(authentication=SimpleNamespace(api_user_id=42)))
    return ClimateControll(account, "VIN", use_zaf=use_zaf)


def _params(payload: str) -> dict:
    return {p["key"]: p["value"] for p in json.loads(payload)["serviceParameters"]}


AC_ON = {"operation": "4", "AC": "true", "AC.temp": "20.0", "AC.duration": "180"}
AC_OFF = {"operation": "4", "AC": "false"}


def test_start_sends_ac_first_then_each_seat_by_itself():
    ctrl = _ctrl()
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 2)
    ctrl.set_heating_level(HeatingLocation.PASSENGER_SEAT, 3)
    payloads = ctrl._get_zaf_payloads(True)
    assert len(payloads) == 3
    for raw in payloads:
        payload = json.loads(raw)
        assert payload["serviceId"] == "ZAF"
        assert payload["command"] == "start"
        assert payload["userId"] == "42"
        assert payload["latest"] is False
    assert [_params(p) for p in payloads] == [
        AC_ON,
        {"operation": "4", "SH.19": "true", "SH.19.level": "3", "SH.19.duration": "15"},
        {"operation": "4", "SV.11": "true", "SV.11.level": "2"},
    ]


def test_start_without_selection_sends_only_ac():
    assert [_params(p) for p in _ctrl()._get_zaf_payloads(True)] == [AC_ON]


def test_heating_and_ventilation_are_exclusive():
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 1)
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 3)
    assert ctrl.heating_levels[HeatingLocation.DRIVER_SEAT] == 0
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)
    assert ctrl.ventilation_levels[VentilationLocation.DRIVER_SEAT] == 0


def test_stop_switches_ac_and_selected_functions_off_separately():
    ctrl = _ctrl()
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 2)
    payloads = ctrl._get_zaf_payloads(False)
    assert all(json.loads(p)["command"] == "start" for p in payloads)
    assert [_params(p) for p in payloads] == [AC_OFF, {"operation": "4", "SV.11": "false"}]


def test_stop_without_selection_only_switches_ac_off():
    assert [_params(p) for p in _ctrl()._get_zaf_payloads(False)] == [AC_OFF]


def test_invalid_level_and_legacy_rejected():
    ctrl = _ctrl()
    with pytest.raises(ValueError):
        ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 4)
    with pytest.raises(NotImplementedError):
        _ctrl(use_zaf=False).set_ventilation_level(VentilationLocation.DRIVER_SEAT, 1)


def test_rear_heating_is_its_own_request():
    from pysmarthashtag.control.climate import RearHeatingLocation

    ctrl = _ctrl()
    ctrl.set_rear_heating_level(RearHeatingLocation.REAR_LEFT, 2)
    assert [_params(p) for p in ctrl._get_zaf_payloads(True)] == [
        AC_ON,
        {"operation": "4", "SH.21": "true", "SH.21.level": "2", "SH.21.duration": "15"},
    ]
    with pytest.raises(ValueError):
        ctrl.set_rear_heating_level(RearHeatingLocation.REAR_LEFT, 4)
    with pytest.raises(NotImplementedError):
        _ctrl(use_zaf=False).set_rear_heating_level(RearHeatingLocation.REAR_LEFT, 1)


@pytest.mark.asyncio
async def test_stop_works_with_corrupt_temperature(monkeypatch):
    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return True

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)
    assert await ctrl.set_climate_conditioning("garbage", False) is True
    assert [_params(raw) for raw in sent] == [AC_OFF, {"operation": "4", "SH.11": "false"}]
    with pytest.raises(TypeError):
        await ctrl.set_climate_conditioning("garbage", True)
    assert len(sent) == 2


@pytest.mark.asyncio
async def test_start_sends_one_request_per_seat_and_reports_failure(monkeypatch):
    from pysmarthashtag.control.climate import RearHeatingLocation

    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return len(sent) != 2

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 1)
    ctrl.set_rear_heating_level(RearHeatingLocation.REAR_LEFT, 2)
    # the second request fails, the third is still sent
    assert await ctrl.set_climate_conditioning(21.0, True) is False
    assert [_params(raw) for raw in sent] == [
        {"operation": "4", "AC": "true", "AC.temp": "21.0", "AC.duration": "180"},
        {"operation": "4", "SH.11": "true", "SH.11.level": "1", "SH.11.duration": "15"},
        {"operation": "4", "SH.21": "true", "SH.21.level": "2", "SH.21.duration": "15"},
    ]


@pytest.mark.asyncio
async def test_start_without_seats_sends_the_ac(monkeypatch):
    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return True

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    assert await _ctrl().set_climate_conditioning(26, True) is True
    assert [_params(raw) for raw in sent] == [{"operation": "4", "AC": "true", "AC.temp": "26.0", "AC.duration": "180"}]


def _pending_error() -> httpx.HTTPStatusError:
    request = httpx.Request("PUT", "https://example.invalid/remote-control/vehicle/telematics/VIN")
    response = httpx.Response(
        200,
        request=request,
        json={"code": 8070, "message": "The last request has not yet been executed, please send the command later!"},
    )
    return httpx.HTTPStatusError(response=response, request=request, message="8070: pending")


@pytest.mark.asyncio
async def test_pending_request_is_sent_again_after_a_pause(monkeypatch):
    sent = []
    sleeps = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        # the cloud is busy for the first two tries of the second request
        if len(sent) in (2, 3):
            raise _pending_error()
        return True

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    monkeypatch.setattr("pysmarthashtag.control.climate.asyncio.sleep", fake_sleep)
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)
    assert await ctrl.set_climate_conditioning(21.0, False) is True
    assert [_params(raw) for raw in sent] == [AC_OFF] + [{"operation": "4", "SH.11": "false"}] * 3
    assert sleeps == [ZAF_PENDING_DELAY, ZAF_PENDING_DELAY]


@pytest.mark.asyncio
async def test_pending_request_gives_up_but_sends_the_rest(monkeypatch):
    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        if _params(payload) == AC_OFF:
            raise _pending_error()
        return True

    async def fake_sleep(seconds):
        return None

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    monkeypatch.setattr("pysmarthashtag.control.climate.asyncio.sleep", fake_sleep)
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)
    assert await ctrl.set_climate_conditioning(21.0, False) is False
    assert len(sent) == ZAF_PENDING_RETRIES + 1 + 1
    assert _params(sent[-1]) == {"operation": "4", "SH.11": "false"}


@pytest.mark.asyncio
async def test_other_cloud_errors_are_not_retried(monkeypatch):
    calls = []

    async def fake_send(account, vin, payload):
        calls.append(payload)
        request = httpx.Request("PUT", "https://example.invalid/x")
        response = httpx.Response(200, request=request, json={"code": 9999, "message": "other"})
        raise httpx.HTTPStatusError(response=response, request=request, message="9999: other")

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    with pytest.raises(httpx.HTTPStatusError):
        await _ctrl().set_climate_conditioning(21.0, True)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_set_heating_on_smart5_uses_zaf_without_ac(monkeypatch):
    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return True

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    ctrl = _ctrl()
    levels = {HeatingLocation.DRIVER_SEAT: 3, HeatingLocation.PASSENGER_SEAT: 2}
    assert await ctrl.set_heating(True, levels) is True
    assert len(sent) == 2
    assert json.loads(sent[0])["serviceId"] == "ZAF"
    assert _params(sent[0]) == {"operation": "4", "SH.11": "true", "SH.11.level": "3", "SH.11.duration": "15"}
    assert _params(sent[1]) == {"operation": "4", "SH.19": "true", "SH.19.level": "2", "SH.19.duration": "15"}
    assert ctrl.heating_levels[HeatingLocation.DRIVER_SEAT] == 0

    assert await ctrl.set_heating(False, {HeatingLocation.STEERING_WHEEL: 0}) is True
    assert _params(sent[2]) == {"operation": "4", "SW": "false"}


@pytest.mark.asyncio
async def test_set_defrost_on_smart5_uses_zaf(monkeypatch):
    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return True

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    ctrl = _ctrl()
    assert await ctrl.set_defrost(True) is True
    assert json.loads(sent[0])["serviceId"] == "ZAF"
    assert _params(sent[0]) == {"operation": "4", "DF": "true"}
    await ctrl.set_defrost(False)
    assert _params(sent[1]) == {"operation": "4", "DF": "false"}


@pytest.mark.asyncio
async def test_set_rear_heating_sends_each_seat_by_itself(monkeypatch):
    from pysmarthashtag.control.climate import RearHeatingLocation

    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return True

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    ctrl = _ctrl()
    levels = {RearHeatingLocation.REAR_LEFT: 2, RearHeatingLocation.REAR_RIGHT: 3}
    assert await ctrl.set_rear_heating(True, levels) is True
    assert [_params(raw) for raw in sent] == [
        {"operation": "4", "SH.21": "true", "SH.21.level": "2", "SH.21.duration": "15"},
        {"operation": "4", "SH.29": "true", "SH.29.level": "3", "SH.29.duration": "15"},
    ]
    assert ctrl.rear_heating_levels[RearHeatingLocation.REAR_LEFT] == 0

    sent.clear()
    assert await ctrl.set_rear_heating(False, {RearHeatingLocation.REAR_RIGHT: 0}) is True
    assert [_params(raw) for raw in sent] == [{"operation": "4", "SH.29": "false"}]

    with pytest.raises(ValueError):
        await ctrl.set_rear_heating(True, {RearHeatingLocation.REAR_LEFT: 4})
    with pytest.raises(NotImplementedError):
        await _ctrl(use_zaf=False).set_rear_heating(True, levels)
