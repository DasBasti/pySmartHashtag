"""Tests for the per-request X-Vehicle-* binding headers (anti binding-theft)."""

from __future__ import annotations

from urllib.parse import quote

from pysmarthashtag.api import utils

_VIN = "TESTVIN123"
_MODEL = "HX11 EUL/Premium"  # contains chars that must be url-encoded


def _hdr(url, vin=None, model_code=None):
    return utils.generate_default_header(
        "dev", "tok", params={}, method="GET", url=url, vin=vin, model_code=model_code
    )


def test_vin_headers_added_for_data_request():
    h = _hdr("/remote-control/vehicle/status/" + _VIN, vin=_VIN, model_code=_MODEL)
    assert h["X-Vehicle-IDENTIFIER"] == _VIN
    assert h["X-VEHICLE-SERIES"] == quote(_MODEL, safe="")
    assert h["X-VEHICLE-MODEL"] == quote(_MODEL, safe="")


def test_no_vin_headers_without_vin_or_model():
    assert "X-Vehicle-IDENTIFIER" not in _hdr("/remote-control/vehicle/status/x")
    # vin but no model_code -> omitted
    assert "X-Vehicle-IDENTIFIER" not in _hdr("/remote-control/vehicle/status/x", vin=_VIN)
    # model_code but no vin -> omitted
    assert "X-Vehicle-IDENTIFIER" not in _hdr("/remote-control/vehicle/status/x", model_code=_MODEL)


def test_vin_headers_skipped_for_blacklisted_endpoints():
    # session/update (the re-bind) and capability are excluded, matching the app
    for url in ("/device-platform/user/session/update", "/geelyTCAccess/tcservices/capability/foo"):
        h = _hdr(url, vin=_VIN, model_code=_MODEL)
        assert "X-Vehicle-IDENTIFIER" not in h, url
