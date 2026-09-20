"""Tests for OTA info fetching.

The OTA endpoint is optional data, so its failures must never cost the
session. In particular cloud code 1003 ("no OTA record for this VIN",
observed on Smart #5) used to fall into the unmapped-code branch, which
refreshed the authentication session on every single poll — 153 times in
one day in the report — without ever clearing the 1003.
"""

import httpx
import pytest
import respx
from httpx import Response

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.const import OTA_SERVER_URL
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles

_OTA_URL = OTA_SERVER_URL + "app/info/TestVIN0000000001"


def _count_refreshes(account: SmartAccount) -> list[int]:
    """Replace ``authentication.refresh`` with a counting no-op."""
    calls: list[int] = []

    async def fake_refresh() -> None:
        calls.append(1)

    account.config.authentication.refresh = fake_refresh
    return calls


@pytest.mark.asyncio
async def test_ota_1003_returns_empty_without_refresh(smart_fixture: respx.Router) -> None:
    """Code 1003 is normalised to "no OTA info" — no refresh, no retry."""
    account = await prepare_account_with_vehicles()
    refreshes = _count_refreshes(account)

    route = smart_fixture.get(_OTA_URL).mock(
        return_value=Response(200, json={"code": "1003", "message": "no ota info"})
    )
    # respx reuses the route registered by the fixture, so its counter already
    # carries the OTA call made while setting the account up.
    before = route.call_count

    assert await account.get_vehicle_ota_info("TestVIN0000000001") == {}
    assert refreshes == [], "1003 must not refresh the session"
    assert route.call_count - before == 1, "1003 must not be retried"


@pytest.mark.asyncio
async def test_ota_1003_does_not_break_refresh_cycle(smart_fixture: respx.Router) -> None:
    """A permanent 1003 still leaves every other vehicle sensor populated."""
    smart_fixture.get(_OTA_URL).mock(return_value=Response(200, json={"code": "1003", "message": "no ota info"}))

    account = await prepare_account_with_vehicles()

    vehicle = account.vehicles["TestVIN0000000001"]
    assert vehicle.vin == "TestVIN0000000001"
    assert "ota" not in vehicle.data


@pytest.mark.asyncio
async def test_ota_unmapped_code_still_refreshes_once(smart_fixture: respx.Router) -> None:
    """Regression guard: other unmapped codes keep the one-refresh remedy."""
    account = await prepare_account_with_vehicles()
    refreshes = _count_refreshes(account)

    smart_fixture.get(_OTA_URL).mock(return_value=Response(200, json={"code": "9999", "message": "something new"}))

    with pytest.raises(httpx.HTTPStatusError):
        await account.get_vehicle_ota_info("TestVIN0000000001")
    assert len(refreshes) == 1, "unmapped codes still get exactly one refresh"
