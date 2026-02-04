"""Test authentication module."""

import datetime
import logging

import pytest
import respx
from httpx import Response

from pysmarthashtag.api.authentication import SmartAuthentication
from pysmarthashtag.const import (
    GLOBAL_API_BASE_URL,
    SmartAuthMode,
    SmartRegion,
    get_endpoint_urls_for_region,
)
from pysmarthashtag.tests import RESPONSE_DIR, TEST_PASSWORD, TEST_USERNAME, load_response

_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_login_global():
    """Test the Global HMAC login flow."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global login endpoint
        login_route = respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/login").mock(
            return_value=Response(200, json=load_response(RESPONSE_DIR / "global_login_result.json"))
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            endpoint_urls=endpoint_urls,
        )

        # Verify auth_mode is correctly inferred
        assert auth.auth_mode == SmartAuthMode.GLOBAL_HMAC

        # Call _login_global directly
        result = await auth._login_global()

        # Verify the login endpoint was called
        assert login_route.called

        # Verify the result contains all expected fields
        assert "access_token" in result
        assert "refresh_token" in result
        assert "api_access_token" in result
        assert "api_refresh_token" in result
        assert "api_user_id" in result
        assert "id_token" in result
        assert "expires_at" in result

        # Verify the token values are correct
        assert result["access_token"] == "TestGlobalAccessToken"
        assert result["refresh_token"] == "TestGlobalRefreshToken"
        assert result["api_access_token"] == "TestGlobalAccessToken"
        assert result["api_refresh_token"] == "TestGlobalRefreshToken"
        assert result["api_user_id"] == "global123456"
        assert result["id_token"] == "TestGlobalIdToken"

        # Verify expires_at is a datetime in the future
        assert isinstance(result["expires_at"], datetime.datetime)
        assert result["expires_at"] > datetime.datetime.now(datetime.timezone.utc)


@pytest.mark.asyncio
async def test_refresh_access_token_global():
    """Test the Global HMAC token refresh flow."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global refresh endpoint
        refresh_route = respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/refresh/").mock(
            return_value=Response(200, json=load_response(RESPONSE_DIR / "global_refresh_result.json"))
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            refresh_token="TestGlobalRefreshToken",
            endpoint_urls=endpoint_urls,
        )

        # Verify auth_mode is correctly inferred
        assert auth.auth_mode == SmartAuthMode.GLOBAL_HMAC

        # Call _refresh_access_token_global directly
        result = await auth._refresh_access_token_global()

        # Verify the refresh endpoint was called
        assert refresh_route.called

        # Verify the result contains all expected fields
        assert "access_token" in result
        assert "refresh_token" in result
        assert "api_access_token" in result
        assert "api_refresh_token" in result
        assert "api_user_id" in result
        assert "id_token" in result
        assert "expires_at" in result

        # Verify the token values are correct
        assert result["access_token"] == "TestGlobalRefreshedAccessToken"
        assert result["refresh_token"] == "TestGlobalRefreshedRefreshToken"
        assert result["api_access_token"] == "TestGlobalRefreshedAccessToken"
        assert result["api_refresh_token"] == "TestGlobalRefreshedRefreshToken"
        assert result["api_user_id"] == "global123456"
        assert result["id_token"] == "TestGlobalRefreshedIdToken"

        # Verify expires_at is a datetime in the future
        assert isinstance(result["expires_at"], datetime.datetime)
        assert result["expires_at"] > datetime.datetime.now(datetime.timezone.utc)


@pytest.mark.asyncio
async def test_refresh_access_token_global_no_refresh_token():
    """Test the Global HMAC token refresh returns empty dict when no refresh token."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    auth = SmartAuthentication(
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        endpoint_urls=endpoint_urls,
    )

    # Verify auth_mode is correctly inferred
    assert auth.auth_mode == SmartAuthMode.GLOBAL_HMAC

    # Call _refresh_access_token_global directly without refresh token
    result = await auth._refresh_access_token_global()

    # Should return empty dict
    assert result == {}


@pytest.mark.asyncio
async def test_auth_mode_selection_global():
    """Test that auth_mode selection triggers Global HMAC code paths."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global login endpoint
        login_route = respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/login").mock(
            return_value=Response(200, json=load_response(RESPONSE_DIR / "global_login_result.json"))
        )

        # Mock API session endpoint
        respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/session?identity_type=smart").mock(
            return_value=Response(200, json=load_response(RESPONSE_DIR / "api_access.json"))
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            endpoint_urls=endpoint_urls,
        )

        # Verify auth_mode is correctly inferred as GLOBAL_HMAC
        assert auth.auth_mode == SmartAuthMode.GLOBAL_HMAC

        # Call the main _login method which should route to _login_global
        result = await auth._login()

        # Verify the global login endpoint was called (not EU OAuth)
        assert login_route.called

        # Verify the result contains global tokens
        assert result["access_token"] == "TestGlobalAccessToken"
        assert result["api_user_id"] == "global123456"


@pytest.mark.asyncio
async def test_auth_mode_selection_global_refresh():
    """Test that auth_mode selection triggers Global HMAC refresh code path."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global refresh endpoint
        refresh_route = respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/refresh/").mock(
            return_value=Response(200, json=load_response(RESPONSE_DIR / "global_refresh_result.json"))
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            refresh_token="TestGlobalRefreshToken",
            endpoint_urls=endpoint_urls,
        )

        # Verify auth_mode is correctly inferred as GLOBAL_HMAC
        assert auth.auth_mode == SmartAuthMode.GLOBAL_HMAC

        # Call the main _refresh_access_token method which should route to _refresh_access_token_global
        result = await auth._refresh_access_token()

        # Verify the global refresh endpoint was called (not EU OAuth)
        assert refresh_route.called

        # Verify the result contains refreshed global tokens
        assert result["access_token"] == "TestGlobalRefreshedAccessToken"
        assert result["api_user_id"] == "global123456"


@pytest.mark.asyncio
async def test_login_global_missing_access_token():
    """Test that _login_global raises error when access token is missing."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global login endpoint with incomplete response
        respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/login").mock(
            return_value=Response(
                200, json={"code": "0000", "message": "Success", "data": {"userId": "global123456", "expiresIn": 3600}}
            )
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            endpoint_urls=endpoint_urls,
        )

        # Should raise SmartAPIError when access_token is missing
        with pytest.raises(Exception) as exc_info:
            await auth._login_global()

        assert "Could not get access token from global login" in str(exc_info.value)


@pytest.mark.asyncio
async def test_login_global_missing_user_id():
    """Test that _login_global raises error when user ID is missing."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global login endpoint with incomplete response
        respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/login").mock(
            return_value=Response(
                200,
                json={"code": "0000", "message": "Success", "data": {"accessToken": "TestToken", "expiresIn": 3600}},
            )
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            endpoint_urls=endpoint_urls,
        )

        # Should raise SmartAPIError when userId is missing
        with pytest.raises(Exception) as exc_info:
            await auth._login_global()

        assert "Could not get access token from global login" in str(exc_info.value)


@pytest.mark.asyncio
async def test_login_global_no_data_field():
    """Test that _login_global raises error when data field is missing."""
    endpoint_urls = get_endpoint_urls_for_region(SmartRegion.GLOBAL)

    with respx.mock:
        # Mock the global login endpoint with no data field
        respx.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/login").mock(
            return_value=Response(200, json={"code": "1001", "message": "Invalid credentials"})
        )

        auth = SmartAuthentication(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            endpoint_urls=endpoint_urls,
        )

        # Should raise SmartAPIError when data is missing
        with pytest.raises(Exception) as exc_info:
            await auth._login_global()

        assert "Could not get tokens from global login" in str(exc_info.value)
        assert "Invalid credentials" in str(exc_info.value)
