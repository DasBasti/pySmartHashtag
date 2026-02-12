"""Tests for EndpointUrls configuration."""

import pytest
import respx

from pysmarthashtag.account import SmartAccount
from pysmarthashtag.api.authentication import SmartAuthentication
from pysmarthashtag.const import (
    API_BASE_URL,
    API_KEY,
    AUTH_URL,
    LOGIN_URL,
    OTA_SERVER_URL,
    SERVER_URL,
    EndpointUrls,
    SmartRegion,
    get_endpoint_urls_for_region,
)
from pysmarthashtag.tests import TEST_PASSWORD, TEST_USERNAME
from pysmarthashtag.tests.conftest import prepare_account_with_vehicles


class TestEndpointUrls:
    """Test EndpointUrls dataclass."""

    def test_default_values(self):
        """Test that EndpointUrls returns default constants when no overrides are given."""
        urls = EndpointUrls()
        assert urls.get_api_key() == API_KEY
        assert urls.get_server_url() == SERVER_URL
        assert urls.get_auth_url() == AUTH_URL
        assert urls.get_login_url() == LOGIN_URL
        assert urls.get_api_base_url() == API_BASE_URL
        assert urls.get_ota_server_url() == OTA_SERVER_URL

    def test_custom_api_key(self):
        """Test that custom API key is used."""
        custom_api_key = "custom_api_key_12345"
        urls = EndpointUrls(api_key=custom_api_key)
        assert urls.get_api_key() == custom_api_key
        # Auth URL returns the default when not explicitly set
        # For custom API keys, users should provide auth_url explicitly
        assert urls.get_auth_url() == AUTH_URL

    def test_custom_server_url(self):
        """Test that custom server URL is used."""
        custom_server_url = "https://custom.server.com/api"
        urls = EndpointUrls(server_url=custom_server_url)
        assert urls.get_server_url() == custom_server_url
        # Other defaults should still work
        assert urls.get_api_key() == API_KEY

    def test_custom_login_url(self):
        """Test that custom login URL is used."""
        custom_login_url = "https://custom.auth.com/login"
        urls = EndpointUrls(login_url=custom_login_url)
        assert urls.get_login_url() == custom_login_url

    def test_custom_api_base_url(self):
        """Test that custom API base URL is used."""
        custom_api_base_url = "https://api.custom.com"
        urls = EndpointUrls(api_base_url=custom_api_base_url)
        assert urls.get_api_base_url() == custom_api_base_url

    def test_custom_ota_server_url(self):
        """Test that custom OTA server URL is used."""
        custom_ota_url = "https://ota.custom.com/"
        urls = EndpointUrls(ota_server_url=custom_ota_url)
        assert urls.get_ota_server_url() == custom_ota_url

    def test_custom_auth_url(self):
        """Test that custom auth URL is used instead of derived."""
        custom_auth_url = "https://auth.custom.com/authorize"
        urls = EndpointUrls(auth_url=custom_auth_url)
        assert urls.get_auth_url() == custom_auth_url

    def test_partial_override(self):
        """Test that partial overrides work while keeping other defaults."""
        custom_api_base = "https://api.international.com"
        custom_ota = "https://ota.international.com/"

        urls = EndpointUrls(
            api_base_url=custom_api_base,
            ota_server_url=custom_ota,
        )

        # Custom values
        assert urls.get_api_base_url() == custom_api_base
        assert urls.get_ota_server_url() == custom_ota

        # Default values
        assert urls.get_api_key() == API_KEY
        assert urls.get_server_url() == SERVER_URL
        assert urls.get_login_url() == LOGIN_URL


class TestSmartAuthenticationWithEndpointUrls:
    """Test SmartAuthentication with custom EndpointUrls."""

    def test_authentication_accepts_endpoint_urls(self):
        """Test that SmartAuthentication accepts endpoint_urls parameter."""
        custom_urls = EndpointUrls(api_base_url="https://custom.api.com")
        auth = SmartAuthentication(
            username="test@example.com",
            password="testpass",
            endpoint_urls=custom_urls,
        )
        assert auth.endpoint_urls.get_api_base_url() == "https://custom.api.com"

    def test_authentication_uses_default_urls(self):
        """Test that SmartAuthentication uses default URLs when none provided."""
        auth = SmartAuthentication(
            username="test@example.com",
            password="testpass",
        )
        assert auth.endpoint_urls.get_api_base_url() == API_BASE_URL
        assert auth.endpoint_urls.get_server_url() == SERVER_URL


class TestSmartAccountWithEndpointUrls:
    """Test SmartAccount with custom EndpointUrls."""

    def test_account_accepts_endpoint_urls(self):
        """Test that SmartAccount accepts endpoint_urls parameter."""
        custom_urls = EndpointUrls(
            api_base_url="https://custom.api.com",
            ota_server_url="https://custom.ota.com/",
        )
        account = SmartAccount(
            username="test@example.com",
            password="testpass",
            endpoint_urls=custom_urls,
        )
        assert account.endpoint_urls.get_api_base_url() == "https://custom.api.com"
        assert account.endpoint_urls.get_ota_server_url() == "https://custom.ota.com/"

    def test_account_uses_default_urls(self):
        """Test that SmartAccount uses default URLs when none provided."""
        account = SmartAccount(
            username="test@example.com",
            password="testpass",
        )
        assert account.endpoint_urls.get_api_base_url() == API_BASE_URL
        assert account.endpoint_urls.get_ota_server_url() == OTA_SERVER_URL

    def test_account_passes_endpoint_urls_to_authentication(self):
        """Test that SmartAccount passes endpoint_urls to authentication."""
        custom_urls = EndpointUrls(api_base_url="https://custom.api.com")
        account = SmartAccount(
            username="test@example.com",
            password="testpass",
            endpoint_urls=custom_urls,
        )
        assert account.config.authentication.endpoint_urls.get_api_base_url() == "https://custom.api.com"


@pytest.mark.asyncio
async def test_account_with_default_urls(smart_fixture: respx.Router):
    """Test that SmartAccount works with default URLs."""
    account = await prepare_account_with_vehicles()
    assert account is not None
    assert account.endpoint_urls.get_api_base_url() == API_BASE_URL
    assert len(account.vehicles) == 2


@pytest.mark.asyncio
async def test_account_with_explicit_default_urls(smart_fixture: respx.Router):
    """Test that SmartAccount works with explicitly set default URLs."""
    # Create an EndpointUrls with all defaults (None values)
    urls = EndpointUrls()
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD, endpoint_urls=urls)
    await account.get_vehicles()
    assert account is not None
    assert len(account.vehicles) == 2


class TestSmartRegion:
    """Test SmartRegion enum and get_endpoint_urls_for_region function."""

    def test_region_eu_returns_default_endpoints(self):
        """Test that EU region returns default (European) endpoints."""
        urls = get_endpoint_urls_for_region(SmartRegion.EU)
        assert urls.get_api_base_url() == API_BASE_URL
        assert urls.get_api_base_url_v2() == "https://apiv2.ecloudeu.com"
        assert urls.get_server_url() == SERVER_URL
        assert urls.get_login_url() == LOGIN_URL
        assert urls.get_auth_url() == AUTH_URL
        assert urls.get_ota_server_url() == OTA_SERVER_URL

    def test_region_intl_returns_asia_pacific_endpoints(self):
        """Test that INTL region returns EU endpoints (same cloud infrastructure)."""
        urls = get_endpoint_urls_for_region(SmartRegion.INTL)
        # International region uses EU cloud endpoints (shared infrastructure)
        assert urls.get_api_base_url() == "https://api.ecloudeu.com"
        assert urls.get_api_base_url_v2() == "https://apiv2.ecloudeu.com"
        # INTL uses different auth URLs (sg-app-api.smart.com)
        assert urls.get_login_url() == "https://sg-app-api.smart.com/iam/service/api/v1/login"
        assert urls.get_auth_url() == "https://sg-app-api.smart.com/iam/service/api/v1/oauth20/authorize"
        assert urls.get_server_url() == "https://sg-app-api.smart.com/iam/service/api/v1/login"

    def test_region_enum_values(self):
        """Test that SmartRegion enum has expected values."""
        assert SmartRegion.EU.value == "eu"
        assert SmartRegion.INTL.value == "intl"

    def test_account_with_eu_region(self):
        """Test creating SmartAccount with EU region preset."""
        urls = get_endpoint_urls_for_region(SmartRegion.EU)
        account = SmartAccount(
            username="test@example.com",
            password="testpass",
            endpoint_urls=urls,
        )
        assert account.endpoint_urls.get_api_base_url() == API_BASE_URL

    def test_account_with_intl_region(self):
        """Test creating SmartAccount with INTL region preset."""
        urls = get_endpoint_urls_for_region(SmartRegion.INTL)
        account = SmartAccount(
            username="test@example.com",
            password="testpass",
            endpoint_urls=urls,
        )
        assert account.endpoint_urls.get_api_base_url() == "https://api.ecloudeu.com"
        assert account.endpoint_urls.get_api_base_url_v2() == "https://apiv2.ecloudeu.com"

    def test_authentication_with_intl_region(self):
        """Test SmartAuthentication with INTL region preset."""
        urls = get_endpoint_urls_for_region(SmartRegion.INTL)
        auth = SmartAuthentication(
            username="test@example.com",
            password="testpass",
            endpoint_urls=urls,
        )
        assert auth.endpoint_urls.get_api_base_url() == "https://api.ecloudeu.com"
