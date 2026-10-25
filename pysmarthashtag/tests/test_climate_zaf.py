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


def test_start_with_ventilation():
    ctrl = _ctrl()
    ctrl.conditioning_temp = 21.0
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 2)
    ctrl.set_heating_level(HeatingLocation.PASSENGER_SEAT, 3)
    payload = json.loads(ctrl._get_zaf_payload(True))
    assert payload["serviceId"] == "ZAF"
    assert payload["command"] == "start"
    assert payload["userId"] == "42"
    assert payload["latest"] is False
    params = _params(json.dumps(payload))
    assert params["operation"] == "4"
    assert params["AC"] == "true" and params["AC.temp"] == "21.0"
    assert params["SV.11"] == "true" and params["SV.11.level"] == "2"
    assert params["SH.12"] == "true" and params["SH.12.level"] == "3"
    assert params["SH.11"] == "false" and "SH.11.level" not in params
    assert params["SV.12"] == "false"


def test_heating_and_ventilation_are_exclusive():
    ctrl = _ctrl()
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 1)
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 3)
    assert ctrl.heating_levels[HeatingLocation.DRIVER_SEAT] == 0
    ctrl.set_heating_level(HeatingLocation.DRIVER_SEAT, 2)
    assert ctrl.ventilation_levels[VentilationLocation.DRIVER_SEAT] == 0


def test_stop_is_all_off():
    ctrl = _ctrl()
    ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 2)
    params = _params(ctrl._get_zaf_payload(False))
    assert json.loads(ctrl._get_zaf_payload(False))["command"] == "start"
    assert params["operation"] == "4"
    for key in ("AC", "SH.11", "SH.12", "SH.21", "SH.22", "SW", "DF", "SV.11", "SV.12"):
        assert params[key] == "false"


def test_invalid_level_and_legacy_rejected():
    ctrl = _ctrl()
    with pytest.raises(ValueError):
        ctrl.set_ventilation_level(VentilationLocation.DRIVER_SEAT, 4)
    with pytest.raises(NotImplementedError):
        _ctrl(use_zaf=False).set_ventilation_level(VentilationLocation.DRIVER_SEAT, 1)


def test_rear_heating_and_all_keys_string_values():
    from pysmarthashtag.control.climate import RearHeatingLocation

    ctrl = _ctrl()
    ctrl.set_rear_heating_level(RearHeatingLocation.REAR_LEFT, 2)
    params = _params(ctrl._get_zaf_payload(True))
    assert params["SH.21"] == "true" and params["SH.21.level"] == "2"
    assert params["SH.22"] == "false" and "SH.22.level" not in params
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
    assert all(p["value"] == "false" or p["key"] == "operation" for p in json.loads(sent[0])["serviceParameters"])
    with pytest.raises(TypeError):
        await ctrl.set_climate_conditioning("garbage", True)
    assert len(sent) == 1


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
    payload = json.loads(sent[0])
    assert payload["serviceId"] == "ZAF"
    params = _params(sent[0])
    assert params == {
        "operation": "4",
        "SH.11": "true",
        "SH.11.level": "3",
        "SH.11.duration": "15",
        "SH.12": "true",
        "SH.12.level": "2",
        "SH.12.duration": "15",
    }
    assert ctrl.heating_levels[HeatingLocation.DRIVER_SEAT] == 0

    assert await ctrl.set_heating(False, {HeatingLocation.STEERING_WHEEL: 0}) is True
    assert _params(sent[1]) == {"operation": "4", "SW": "false"}


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
