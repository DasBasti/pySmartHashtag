"""Tests for the adaptive rate-limit backoff in ``SmartAuthentication``.

These tests stub ``_do_login`` so no network calls happen and exercise:

* AIMD growth on rate-limit failures (HTTP 403/429)
* Circuit-breaker suppression while the quiet window is active
* Multiplicative shrink on successful login
* Fixed short suppress (no growth) on non-rate-limit failures
* Floor invariant after many successes
* Module-level state shared across ``SmartAuthentication`` instances
  for the same username
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import httpx
import pytest

from pysmarthashtag.api.authentication import (
    _BACKOFF_REGISTRY,
    SmartAPIError,
    SmartAuthentication,
)


def _make_auth(username: str = "user@example.com") -> SmartAuthentication:
    """Reset shared backoff state for ``username`` and return a fresh auth."""
    _BACKOFF_REGISTRY.pop(username, None)
    return SmartAuthentication(username=username, password="p")


def _http_403() -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://example/")
    resp = httpx.Response(403, request=req, content=b'{"message":"Forbidden"}')
    return httpx.HTTPStatusError("forbidden", request=req, response=resp)


def _login_ok() -> dict:
    return {
        "access_token": "a",
        "refresh_token": "r",
        "api_access_token": "x",
        "api_refresh_token": "y",
        "api_user_id": "z",
        "expires_at": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=1),
    }


class TestAdaptiveBackoff:
    """Adaptive AIMD rate-limit backoff."""

    @pytest.mark.asyncio
    async def test_grow_on_rate_limit(self):
        """Each rate-limit hit grows the backoff up to ``_BACKOFF_CAP``."""
        auth = _make_auth()
        floor_min = auth._BACKOFF_FLOOR.total_seconds() / 60
        cap_min = auth._BACKOFF_CAP.total_seconds() / 60
        grow = auth._BACKOFF_GROW

        expected: list[float] = []
        v = floor_min
        for _ in range(11):
            v = min(v * grow, cap_min)
            expected.append(round(v, 6))

        async def boom():
            raise _http_403()

        seen: list[float] = []
        with patch.object(auth, "_do_login", boom):
            for _ in expected:
                # Pretend the previous quiet window has just elapsed so
                # this probe is allowed through to ``_do_login``.
                auth._state.quiet_until = None
                with pytest.raises((SmartAPIError, httpx.HTTPStatusError)):
                    await auth._login()
                seen.append(round(auth._state.backoff.total_seconds() / 60, 6))

        assert seen == expected
        assert auth._state.backoff <= auth._BACKOFF_CAP

    @pytest.mark.asyncio
    async def test_breaker_blocks_during_quiet_window(self):
        """During the quiet window the breaker must skip ``_do_login``."""
        auth = _make_auth()

        async def boom():
            raise _http_403()

        with patch.object(auth, "_do_login", boom):
            with pytest.raises((SmartAPIError, httpx.HTTPStatusError)):
                await auth._login()

            calls = {"n": 0}

            async def count_calls():
                calls["n"] += 1
                raise _http_403()

            with patch.object(auth, "_do_login", count_calls):
                with pytest.raises(SmartAPIError) as excinfo:
                    await auth._login()

        assert calls["n"] == 0, "breaker did not suppress the second probe"
        assert "quiet window" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_shrink_on_success(self):
        """Success shrinks the backoff and clears the quiet window."""
        auth = _make_auth()
        auth._state.backoff = datetime.timedelta(minutes=30)
        auth._state.quiet_until = None

        async def ok():
            return _login_ok()

        with patch.object(auth, "_do_login", ok):
            await auth._login()

        assert auth._state.backoff == datetime.timedelta(minutes=29)
        assert auth._state.quiet_until is None

    @pytest.mark.asyncio
    async def test_other_failure_uses_fixed_suppress_no_grow(self):
        """Non-rate-limit failures only set a short suppress, no grow."""
        auth = _make_auth()
        before = auth._state.backoff

        async def boom():
            raise SmartAPIError("Could not get access token from auth page")

        with patch.object(auth, "_do_login", boom):
            with pytest.raises(SmartAPIError):
                await auth._login()

        assert auth._state.backoff == before, "backoff grew on non-rate-limit failure"
        assert auth._state.quiet_until is not None

        delta = auth._state.quiet_until - datetime.datetime.now(datetime.timezone.utc)
        # Allow a small clock-skew tolerance below the configured suppress window.
        lower_bound = auth._OTHER_FAILURE_BACKOFF - datetime.timedelta(seconds=5)
        assert lower_bound < delta <= auth._OTHER_FAILURE_BACKOFF

    @pytest.mark.asyncio
    async def test_floor_invariant(self):
        """Repeated successes never push the backoff below the floor."""
        auth = _make_auth()

        async def ok():
            return _login_ok()

        with patch.object(auth, "_do_login", ok):
            for _ in range(20):
                await auth._login()

        assert auth._state.backoff == auth._BACKOFF_FLOOR

    @pytest.mark.asyncio
    async def test_state_shared_across_instances_same_user(self):
        """Two ``SmartAuthentication`` objects for the same user share state."""
        a1 = _make_auth("shared_user")

        async def boom():
            raise _http_403()

        with patch.object(a1, "_do_login", boom):
            a1._state.quiet_until = None
            with pytest.raises((SmartAPIError, httpx.HTTPStatusError)):
                await a1._login()

        grew_to = a1._state.backoff
        assert grew_to > a1._BACKOFF_FLOOR

        # New instance for the same username — must reuse the same state.
        a2 = SmartAuthentication(username="shared_user", password="p")
        assert a2._state is a1._state
        assert a2._state.backoff == grew_to

        calls = {"n": 0}

        async def count_calls():
            calls["n"] += 1
            raise _http_403()

        with patch.object(a2, "_do_login", count_calls):
            with pytest.raises(SmartAPIError):
                await a2._login()

        assert calls["n"] == 0, "shared quiet window did not suppress second instance"
