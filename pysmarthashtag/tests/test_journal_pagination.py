"""Tests for journalLogV4 ``pageIndex`` looping inside :meth:`SmartAccount.get_trip_journal`."""

import logging
import re
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from pysmarthashtag.const import API_BASE_URL, API_BASE_URL_V2
from pysmarthashtag.models import JournalTruncationError
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles

_JOURNAL_PATH = "/geelyTCAccess/tcservices/vehicle/status/journalLogV4/"


def _trip(trip_id: int, start_ms: int = 1_700_000_000_000, end_ms: int = 1_700_000_600_000) -> dict:
    """Build a minimal journalLogV4 trip record."""
    return {
        "tripId": trip_id,
        "startTime": start_ms,
        "endTime": end_ms,
        "traveledDistance": 1.0,
    }


def _page_body(items: list, total: int, page_index: int = 1, page_size: int = 20) -> dict:
    """Build a journalLogV4 page response body."""
    return {
        "code": "1000",
        "message": "operation succeed",
        "success": True,
        "data": {
            "pagination": {
                "pageIndex": page_index,
                "sortField": "startTime",
                "start": 1,
                "pageSize": page_size,
                "totleSize": total,
                "direction": "desc",
            },
            "list": items,
        },
    }


def _install_paginated_routes(
    smart_fixture: respx.Router,
    pages_by_index: dict[int, dict],
    *,
    vin: str = "TestVIN0000000001",
) -> list[httpx.Request]:
    """Install a journalLogV4 mock that dispatches by ``pageIndex`` query param.

    Returns a list that gets a request appended on every call, so tests
    can introspect call ordering. ``pages_by_index`` maps ``pageIndex``
    int → response body. A request whose ``pageIndex`` is missing from
    the dict yields an empty page (defensive — exposes test bugs).
    """
    captured: list[httpx.Request] = []

    def _dispatch(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        qs = parse_qs(urlparse(str(request.url)).query)
        page_index = int((qs.get("pageIndex") or ["0"])[0])
        body = pages_by_index.get(page_index, _page_body([], 0, page_index=page_index))
        return httpx.Response(200, json=body)

    for base in (API_BASE_URL, API_BASE_URL_V2):
        smart_fixture.get(re.compile(re.escape(base + _JOURNAL_PATH + vin) + r".*")).mock(
            side_effect=_dispatch
        )
    return captured


@pytest.mark.asyncio
async def test_loops_until_totleSize_reached(smart_fixture: respx.Router):
    """Loop pages 2..N until accumulated count meets ``totleSize``.

    The cloud reports more trips than ``page_size`` here; the merged
    response must contain entries from every page in cloud order.
    """
    page1 = _page_body([_trip(i) for i in range(2, 0, -1)], total=4, page_size=2)
    page2 = _page_body([_trip(i) for i in range(4, 2, -1)], total=4, page_index=2, page_size=2)
    captured = _install_paginated_routes(smart_fixture, {1: page1, 2: page2})

    account = await prepare_account_with_vehicles()
    merged = await account.get_trip_journal("TestVIN0000000001", page_size=2)

    # Both pages were fetched.
    page_indices = [
        int(parse_qs(urlparse(str(r.url)).query)["pageIndex"][0])
        for r in captured
        if "TestVIN0000000001" in str(r.url)
    ]
    # `prepare_account_with_vehicles` calls get_vehicles, which itself
    # invokes get_trip_journal → page-loop. So the captured list may
    # contain BOTH that initial loop AND ours. Just assert that pages
    # 1 and 2 each appear at least once.
    assert 1 in page_indices
    assert 2 in page_indices

    # Merged data.list contains all 4 trips, in the order they were
    # received (newest-first per cloud direction=desc, preserved
    # across pages).
    assert len(merged["data"]["list"]) == 4
    trip_ids = [trip["tripId"] for trip in merged["data"]["list"]]
    assert trip_ids == [2, 1, 4, 3]
    assert merged["data"]["pagination"]["totleSize"] == 4


@pytest.mark.asyncio
async def test_short_page_stops_loop(smart_fixture: respx.Router):
    """A short page is the cloud's "no more pages" signal.

    Stop looping when the cloud delivers fewer items than ``page_size``,
    even if ``totleSize`` claims more — the cloud doesn't error on
    over-paginating, it just short-pages.
    """
    # totleSize claims 100 but the cloud actually short-pages at 1 entry.
    page1 = _page_body([_trip(1)], total=100, page_size=2)
    captured = _install_paginated_routes(smart_fixture, {1: page1})

    account = await prepare_account_with_vehicles()
    merged = await account.get_trip_journal("TestVIN0000000001", page_size=2)

    # Only page 1 was fetched for this loop (short-page → no page 2).
    # The route DID see page 1 fetched twice though — once during
    # get_vehicles' own get_trip_journal call, and once for ours.
    our_call_indices = [
        int(parse_qs(urlparse(str(r.url)).query)["pageIndex"][0])
        for r in captured
    ]
    assert 2 not in our_call_indices, "short page must short-circuit page 2"

    assert len(merged["data"]["list"]) == 1
    assert merged["data"]["list"][0]["tripId"] == 1


@pytest.mark.asyncio
async def test_mid_loop_8153_breaks_loop(smart_fixture: respx.Router):
    """Mid-loop 8153 is benign end-of-data, not an error.

    Page 2's ``code: 8153`` ("data unavailable") breaks the loop and
    returns what's accumulated; the caller does not see an exception.
    """
    page1 = _page_body([_trip(1), _trip(2)], total=10, page_size=2)

    def _dispatch(request: httpx.Request) -> httpx.Response:
        qs = parse_qs(urlparse(str(request.url)).query)
        page_index = int((qs.get("pageIndex") or ["0"])[0])
        if page_index == 1:
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json={"code": "8153", "message": "Connection interruption"})

    for base in (API_BASE_URL, API_BASE_URL_V2):
        smart_fixture.get(
            re.compile(re.escape(base + _JOURNAL_PATH + "TestVIN0000000001") + r".*")
        ).mock(side_effect=_dispatch)

    account = await prepare_account_with_vehicles()
    # No raise — 8153 mid-loop is benign end-of-data.
    merged = await account.get_trip_journal("TestVIN0000000001", page_size=2)

    # Accumulated only page 1's 2 entries; page 2 was 8153.
    assert len(merged["data"]["list"]) == 2


@pytest.mark.asyncio
async def test_mid_loop_other_error_propagates(smart_fixture: respx.Router):
    """A non-8153 cloud error mid-loop propagates as ``HTTPStatusError``."""
    page1 = _page_body([_trip(1), _trip(2)], total=10, page_size=2)

    def _dispatch(request: httpx.Request) -> httpx.Response:
        qs = parse_qs(urlparse(str(request.url)).query)
        page_index = int((qs.get("pageIndex") or ["0"])[0])
        if page_index == 1:
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json={"code": "5000", "message": "Internal server error"})

    for base in (API_BASE_URL, API_BASE_URL_V2):
        smart_fixture.get(
            re.compile(re.escape(base + _JOURNAL_PATH + "TestVIN0000000001") + r".*")
        ).mock(side_effect=_dispatch)

    account = await prepare_account_with_vehicles()
    with pytest.raises(httpx.HTTPStatusError):
        await account.get_trip_journal("TestVIN0000000001", page_size=2)


@pytest.mark.asyncio
async def test_truncation_warn_when_count_disagrees(
    smart_fixture: respx.Router, caplog: pytest.LogCaptureFixture
):
    """Truncation logs a WARNING by default; loop returns the partial result.

    Routine polls keep going so the next iteration can pick up the
    missing trips, instead of failing the whole refresh on a mismatch.
    """
    # Cloud reports totleSize=10 but only delivers 1 short page → mismatch.
    page1 = _page_body([_trip(1)], total=10, page_size=2)
    _install_paginated_routes(smart_fixture, {1: page1})

    account = await prepare_account_with_vehicles()
    with caplog.at_level(logging.WARNING, logger="pysmarthashtag.account"):
        merged = await account.get_trip_journal("TestVIN0000000001", page_size=2)

    assert len(merged["data"]["list"]) == 1
    assert merged["data"]["pagination"]["totleSize"] == 10
    assert any(
        "page-loop truncation" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    )


@pytest.mark.asyncio
async def test_truncation_raises_when_caller_opts_in(smart_fixture: respx.Router):
    """``raise_on_truncation=True`` upgrades the WARNING to a hard failure."""
    page1 = _page_body([_trip(1)], total=10, page_size=2)
    _install_paginated_routes(smart_fixture, {1: page1})

    account = await prepare_account_with_vehicles()
    with pytest.raises(JournalTruncationError):
        await account.get_trip_journal(
            "TestVIN0000000001", page_size=2, raise_on_truncation=True
        )


@pytest.mark.asyncio
async def test_no_loop_when_first_page_short(smart_fixture: respx.Router):
    """If page 1 is already short and totleSize matches, no second page is fetched."""
    page1 = _page_body([_trip(1), _trip(2)], total=2, page_size=20)

    captured: list[httpx.Request] = []

    def _dispatch(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=page1)

    for base in (API_BASE_URL, API_BASE_URL_V2):
        smart_fixture.get(
            re.compile(re.escape(base + _JOURNAL_PATH + "TestVIN0000000001") + r".*")
        ).mock(side_effect=_dispatch)

    account = await prepare_account_with_vehicles()
    pre_count = len(captured)
    merged = await account.get_trip_journal("TestVIN0000000001")

    # Only one journal request should have been issued by THIS call —
    # `prepare_account_with_vehicles` made its own earlier ones.
    new_calls = captured[pre_count:]
    page_indices = [
        int(parse_qs(urlparse(str(r.url)).query)["pageIndex"][0])
        for r in new_calls
    ]
    assert page_indices == [1], "no page 2 expected: total reached and page is short"

    assert len(merged["data"]["list"]) == 2


@pytest.mark.parametrize(
    ("total_raw", "expected_total"),
    [
        (3, 3),
        (3.0, 3),
        ("3", 3),
        ("  3  ", 3),
        ("3.0", None),
        (None, None),
        (True, None),
        ("not a number", None),
    ],
    ids=["int", "float", "string_digit", "whitespace_padded", "string_float", "none", "bool_true", "garbage_string"],
)
def test_unwrap_journal_page_coerces_totlesize(total_raw, expected_total):
    """``_unwrap_journal_page`` accepts stringified ``totleSize`` and rejects bools/floats-as-string."""
    from pysmarthashtag.account import _unwrap_journal_page

    body = {
        "data": {
            "pagination": {"totleSize": total_raw},
            "list": [_trip(1), _trip(2)],
        }
    }
    items, total = _unwrap_journal_page(body)
    assert len(items) == 2
    assert total == expected_total
