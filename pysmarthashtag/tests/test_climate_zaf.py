"""Tests for the Smart #5 ZAF climate payload with seat ventilation."""

import json
from types import SimpleNamespace

import pytest

from pysmarthashtag.control.climate import ClimateControll, HeatingLocation, VentilationLocation


def _ctrl(use_zaf: bool = True) -> ClimateControll:
    account = SimpleNamespace(config=SimpleNamespace(authentication=SimpleNamespace(api_user_id=42)))
    return ClimateControll(account, "VIN", use_zaf=use_zaf)


def _params(payload: str) -> dict:
    return {p["key"]: p["value"] for p in json.loads(payload)["serviceParameters"]}


def test_start_sends_each_seat_by_itself_without_ac():
    ctrl = _ctrl()
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 2)
    ctrl.set_heating_level(HeatingLocation.PASSENGER_SEAT, 3)
    payloads = ctrl._get_zaf_payloads(True)
    assert len(payloads) == 2
    for raw in payloads:
        payload = json.loads(raw)
        assert payload["serviceId"] == "ZAF"
        assert payload["command"] == "start"
        assert payload["userId"] == "42"
        assert payload["latest"] is False
    assert [_params(p) for p in payloads] == [
        {"operation": "4", "SH.12": "true", "SH.12.level": "3", "SH.12.duration": "15"},
        {"operation": "4", "SV.11": "true", "SV.11.level": "2"},
    ]


def test_start_without_selection_sends_nothing():
    assert _ctrl()._get_zaf_payloads(True) == []


def test_heating_and_ventilation_are_exclusive():
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 1)
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 3)
    assert ctrl.heating_levels[HeatingLocation.DRIVER_SEAT] == 0
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)
    assert ctrl.ventilation_levels[VentilationLocation.DRIVER_SEAT] == 0


def test_stop_switches_every_function_off_separately():
    ctrl = _ctrl()
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 2)
    payloads = ctrl._get_zaf_payloads(False)
    assert all(json.loads(p)["command"] == "start" for p in payloads)
    assert [_params(p) for p in payloads] == [
        {"operation": "4", key: "false"} for key in ("SH.11", "SH.12", "SH.21", "SH.22", "SW", "DF", "SV.11", "SV.19")
    ]


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
        {"operation": "4", "SH.21": "true", "SH.21.level": "2", "SH.21.duration": "15"}
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
    assert await ctrl.set_climate_conditioning("garbage", False) is True
    assert len(sent) == 8
    assert all(v == "false" for raw in sent for k, v in _params(raw).items() if k != "operation")
    with pytest.raises(TypeError):
        await ctrl.set_climate_conditioning("garbage", True)
    assert len(sent) == 8


@pytest.mark.asyncio
async def test_start_sends_one_request_per_seat_and_reports_failure(monkeypatch):
    from pysmarthashtag.control.climate import RearHeatingLocation

    sent = []

    async def fake_send(account, vin, payload):
        sent.append(payload)
        return len(sent) != 1

    monkeypatch.setattr("pysmarthashtag.control.climate.send_telematics_command", fake_send)
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 1)
    ctrl.set_rear_heating_level(RearHeatingLocation.REAR_LEFT, 2)
    # the first request fails, the second is still sent
    assert await ctrl.set_climate_conditioning(21.0, True) is False
    assert [_params(raw) for raw in sent] == [
        {"operation": "4", "SH.11": "true", "SH.11.level": "1", "SH.11.duration": "15"},
        {"operation": "4", "SH.21": "true", "SH.21.level": "2", "SH.21.duration": "15"},
    ]

    sent.clear()
    assert await _ctrl().set_climate_conditioning(21.0, True) is False
    assert sent == []


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
    assert _params(sent[1]) == {"operation": "4", "SH.12": "true", "SH.12.level": "2", "SH.12.duration": "15"}
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
        {"operation": "4", "SH.22": "true", "SH.22.level": "3", "SH.22.duration": "15"},
    ]
    assert ctrl.rear_heating_levels[RearHeatingLocation.REAR_LEFT] == 0

    sent.clear()
    assert await ctrl.set_rear_heating(False, {RearHeatingLocation.REAR_RIGHT: 0}) is True
    assert [_params(raw) for raw in sent] == [{"operation": "4", "SH.22": "false"}]

    with pytest.raises(ValueError):
        await ctrl.set_rear_heating(True, {RearHeatingLocation.REAR_LEFT: 4})
    with pytest.raises(NotImplementedError):
        await _ctrl(use_zaf=False).set_rear_heating(True, levels)
