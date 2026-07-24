"""Tests for the layered token/session lifecycle.

Covers the pieces added on ``feat/token-lifecycle``:

* ``_post_api_session``: success parsing (incl. ``clientId``) and typed
  classification of failures (1501 vs generic).
* ``refresh_api_session``: layer-1 refresh updates session fields from the
  stored OAuth token.
* ``refresh``: orchestrates layer 1 to full-login fallback.
* ``login``: captures ``api_client_id``.
* ``SmartClient`` response routing: cloud codes map to typed exceptions and
  no longer log in inline.
"""

from __future__ import annotations

import datetime
import ssl

import httpx
import pytest

import pysmarthashtag.api.authentication as auth_module
from pysmarthashtag.api.authentication import _BACKOFF_REGISTRY, SmartAuthentication
from pysmarthashtag.api.client import SmartClient, SmartClientConfiguration
from pysmarthashtag.models import (
    SmartAPIError,
    SmartHumanCarConnectionError,
    SmartMainTokenExpiredError,
    SmartNoPermissionError,
    SmartNonceError,
    SmartTokenRefreshNecessary,
    SmartVehicleNotInUseError,
    SmartVehicleUnboundError,
)


def _make_auth(username: str = "lifecycle@example.com") -> SmartAuthentication:
    _BACKOFF_REGISTRY.pop(username, None)
    return SmartAuthentication(username=username, password="p")


def _token_data() -> dict:
    return {
        "access_token": "a",
        "refresh_token": "r",
        "api_access_token": "x",
        "api_refresh_token": "y",
        "api_user_id": "z",
        "expires_at": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
    }


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Stand-in for SmartLoginClient exposing only the ``post`` used here."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list = []

    async def post(self, url, headers=None, content=None):
        self.calls.append((url, headers, content))
        return self._response


class _FakeAsyncClient:
    """Async-context stand-in for ``SmartLoginClient`` (put/post + aenter/aexit)."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def put(self, url, headers=None, content=None):
        self.calls.append(("PUT", url, headers, content))
        return self._response

    async def post(self, url, headers=None, content=None):
        self.calls.append(("POST", url, headers, content))
        return self._response


# ---- _post_api_session -----------------------------------------------------


class TestPostApiSession:
    @pytest.mark.asyncio
    async def test_success_captures_client_id(self):
        auth = _make_auth()
        client = _FakeClient(
            _FakeResponse(
                {
                    "code": "1000",
                    "data": {
                        "accessToken": "AT",
                        "refreshToken": "RT",
                        "userId": "UID",
                        "clientId": "CID",
                    },
                }
            )
        )
        tokens = await auth._post_api_session(client, "oauth-token")
        assert tokens == {
            "api_access_token": "AT",
            "api_refresh_token": "RT",
            "api_user_id": "UID",
            "api_client_id": "CID",
        }
        # the OAuth token, not the api token, is sent in the body
        assert "oauth-token" in client.calls[0][2].decode()

    @pytest.mark.asyncio
    async def test_1501_raises_main_token_expired(self):
        auth = _make_auth()
        client = _FakeClient(_FakeResponse({"code": "1501", "message": "main token expired"}))
        with pytest.raises(SmartMainTokenExpiredError):
            await auth._post_api_session(client, "oauth-token")

    @pytest.mark.asyncio
    async def test_generic_error_carries_code(self):
        auth = _make_auth()
        client = _FakeClient(_FakeResponse({"code": "9999", "message": "nope"}))
        with pytest.raises(SmartAPIError) as excinfo:
            await auth._post_api_session(client, "oauth-token")
        assert "9999" in str(excinfo.value)
        assert not isinstance(excinfo.value, SmartMainTokenExpiredError)

    @pytest.mark.asyncio
    async def test_non_json_response_raises_api_error(self):
        """A maintenance/WAF page (HTML, not JSON) surfaces as SmartAPIError.

        Without the guard the raw ValueError escapes the SmartAPIError
        contract refresh()/_login() rely on, defeating the full-login
        fallback and rate-limit backoff.
        """

        class _HtmlResponse:
            status_code = 503
            text = "<html><body>Service under maintenance</body></html>"

            def json(self):
                raise ValueError("no json")

        auth = _make_auth()
        client = _FakeClient(_HtmlResponse())
        with pytest.raises(SmartAPIError) as excinfo:
            await auth._post_api_session(client, "oauth-token")
        assert "503" in str(excinfo.value)
        assert not isinstance(excinfo.value, SmartMainTokenExpiredError)


# ---- refresh_api_session / refresh ----------------------------------------


class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_api_session_updates_fields(self, monkeypatch):
        auth = _make_auth()
        auth.access_token = "oauth-token"

        async def fake_ssl():
            return ssl.create_default_context()

        async def fake_post(client, token):
            assert token == "oauth-token"
            return {
                "api_access_token": "AT2",
                "api_refresh_token": "RT2",
                "api_user_id": "UID2",
                "api_client_id": "CID2",
            }

        monkeypatch.setattr(auth, "get_ssl_context", fake_ssl)
        monkeypatch.setattr(auth, "_post_api_session", fake_post)
        await auth.refresh_api_session()
        assert auth.api_access_token == "AT2"
        assert auth.api_refresh_token == "RT2"
        assert auth.api_user_id == "UID2"
        assert auth.api_client_id == "CID2"

    @pytest.mark.asyncio
    async def test_refresh_api_session_without_oauth_token_raises(self):
        auth = _make_auth()
        auth.access_token = None
        with pytest.raises(SmartMainTokenExpiredError):
            await auth.refresh_api_session()

    @pytest.mark.asyncio
    async def test_refresh_uses_layer1_and_skips_full_login(self, monkeypatch):
        auth = _make_auth()
        calls: list[str] = []

        async def layer1():
            calls.append("layer1")

        async def full_login():
            calls.append("login")

        monkeypatch.setattr(auth, "refresh_api_session", layer1)
        monkeypatch.setattr(auth, "login", full_login)
        await auth.refresh()
        assert calls == ["layer1"], "full login should not run when layer-1 succeeds"

    @pytest.mark.asyncio
    async def test_refresh_1501_uses_layer2_then_reruns_layer1(self, monkeypatch):
        """On 1501, layer-2 recovers the OAuth token, then layer-1 re-runs."""
        auth = _make_auth()
        calls: list[str] = []
        layer1_calls = {"n": 0}

        async def layer1():
            layer1_calls["n"] += 1
            calls.append(f"layer1#{layer1_calls['n']}")
            if layer1_calls["n"] == 1:
                raise SmartMainTokenExpiredError("oauth dead")
            # second call (after layer-2) succeeds

        async def layer2():
            calls.append("layer2")

        async def full_login():
            calls.append("login")

        monkeypatch.setattr(auth, "refresh_api_session", layer1)
        monkeypatch.setattr(auth, "refresh_token_exchange", layer2)
        monkeypatch.setattr(auth, "login", full_login)
        await auth.refresh()
        assert calls == ["layer1#1", "layer2", "layer1#2"], "should recover via layer-2 then re-run layer-1"
        assert "login" not in calls, "must not fall to full login when layer-2 recovers"

    @pytest.mark.asyncio
    async def test_refresh_falls_back_to_login_when_layer2_fails(self, monkeypatch):
        auth = _make_auth()
        calls: list[str] = []

        async def layer1():
            calls.append("layer1")
            raise SmartMainTokenExpiredError("oauth dead")

        async def layer2():
            calls.append("layer2")
            raise SmartAPIError("exchange failed")

        async def full_login():
            calls.append("login")

        monkeypatch.setattr(auth, "refresh_api_session", layer1)
        monkeypatch.setattr(auth, "refresh_token_exchange", layer2)
        monkeypatch.setattr(auth, "login", full_login)
        await auth.refresh()
        assert calls == ["layer1", "layer2", "login"]

    @pytest.mark.asyncio
    async def test_refresh_token_exchange_updates_oauth_token(self, monkeypatch):
        auth = _make_auth()
        auth.api_refresh_token = "SRT"
        auth.api_client_id = "CID"
        fake = _FakeAsyncClient(
            _FakeResponse(
                {"code": "1000", "data": {"accessToken": "NEW_OAUTH", "refreshToken": "SRT2", "clientId": "CID2"}}
            )
        )

        async def fake_ssl():
            return ssl.create_default_context()

        monkeypatch.setattr(auth, "get_ssl_context", fake_ssl)
        monkeypatch.setattr(auth_module, "SmartLoginClient", lambda **kw: fake)
        await auth.refresh_token_exchange()
        assert auth.access_token == "NEW_OAUTH"
        assert auth.api_refresh_token == "SRT2"
        assert auth.api_client_id == "CID2"
        method, url, headers, content = fake.calls[0]
        assert method == "PUT"
        assert headers["X-CLIENT-ID"] == "CID"
        assert "proprietaryPlatform" in content.decode()
        assert "identity_type" not in url  # bare path, no query

    @pytest.mark.asyncio
    async def test_refresh_token_exchange_requires_client_id(self):
        auth = _make_auth()
        auth.api_refresh_token = "SRT"
        auth.api_client_id = None
        with pytest.raises(SmartAPIError):
            await auth.refresh_token_exchange()

    @pytest.mark.asyncio
    async def test_refresh_falls_back_to_login_on_generic_error(self, monkeypatch):
        auth = _make_auth()
        calls: list[str] = []

        async def layer1():
            raise SmartAPIError("boom")

        async def full_login():
            calls.append("login")

        monkeypatch.setattr(auth, "refresh_api_session", layer1)
        monkeypatch.setattr(auth, "login", full_login)
        await auth.refresh()
        assert calls == ["login"]


class TestLoginCapturesClientId:
    @pytest.mark.asyncio
    async def test_login_stores_api_client_id(self, monkeypatch):
        auth = _make_auth()

        async def fake_login():
            data = _token_data()
            data["api_client_id"] = "CID"
            return data

        monkeypatch.setattr(auth, "_login", fake_login)
        await auth.login()
        assert auth.api_client_id == "CID"
        assert auth.api_access_token == "x"


# ---- SmartClient response-code routing ------------------------------------


async def _run_response_hooks(client: SmartClient, payload: dict, status: int = 200) -> None:
    req = httpx.Request("GET", "https://example/api")
    resp = httpx.Response(status, json=payload, request=req)
    for hook in client.event_hooks["response"]:
        await hook(resp)


class TestClientRouting:
    def _client(self) -> SmartClient:
        auth = _make_auth("routing@example.com")
        config = SmartClientConfiguration(authentication=auth)
        return SmartClient(config, ssl_context=ssl.create_default_context())

    @pytest.mark.asyncio
    async def test_success_code_does_not_raise(self):
        client = self._client()
        try:
            await _run_response_hooks(client, {"code": "1000", "data": {}})
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "code,exc",
        [
            ("1402", SmartTokenRefreshNecessary),
            ("8006", SmartHumanCarConnectionError),
            ("1501", SmartMainTokenExpiredError),
            ("8500", SmartMainTokenExpiredError),
            ("4038", SmartVehicleNotInUseError),
            ("8040", SmartVehicleUnboundError),
            ("1443", SmartNonceError),
            ("8160", SmartNoPermissionError),
        ],
    )
    async def test_error_codes_map_to_typed_exceptions(self, code, exc):
        client = self._client()
        try:
            with pytest.raises(exc):
                await _run_response_hooks(client, {"code": code, "message": "m"})
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_8500_without_message_warns(self, caplog):
        """8500 was observed with no message at all, and must still be typed and logged."""
        client = self._client()
        try:
            with pytest.raises(SmartMainTokenExpiredError):
                await _run_response_hooks(client, {"code": "8500"})
            assert "8500" in caplog.text
        finally:
            await client.aclose()

    @pytest.mark.asyncio
    async def test_token_expiry_does_not_login_inline(self, monkeypatch):
        """The event hook must NOT perform the remedy itself anymore."""
        client = self._client()
        logged_in = {"n": 0}

        async def fake_login():
            logged_in["n"] += 1

        monkeypatch.setattr(client.config.authentication, "login", fake_login)
        try:
            with pytest.raises(SmartTokenRefreshNecessary):
                await _run_response_hooks(client, {"code": "1402"})
        finally:
            await client.aclose()
        assert logged_in["n"] == 0, "client hook should not log in inline"


class TestRateLimitClassification:
    """Ported from #213: throttle wording must feed the geometric backoff."""

    @pytest.mark.parametrize(
        "text",
        [
            "Too Many Requests",
            "request throttled, slow down",
            "please try again later",
            "Could not get API access token from API (HTTP 429, code=...): x",
            "HTTP 403 Forbidden",
            "rate limit exceeded",
        ],
    )
    def test_rate_limit_texts_classified(self, text):
        assert SmartAuthentication._is_rate_limit_error(SmartAPIError(text))

    @pytest.mark.parametrize(
        "text",
        [
            "Could not get access token from auth page",
            "Could not get context from login page",
            "some transient network blip",
        ],
    )
    def test_non_rate_limit_texts_not_classified(self, text):
        assert not SmartAuthentication._is_rate_limit_error(SmartAPIError(text))
