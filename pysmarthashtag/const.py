"""URLs for different services and error code mapping."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

API_KEY = "3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a"
SERVER_URL = "https://awsapi.future.smart.com/login-app/api/v1/authorize?uiLocales=de-DE"
AUTH_URL = f"https://auth.smart.com/oidc/op/v1.0/{API_KEY}/authorize/continue"
LOGIN_URL = "https://auth.smart.com/accounts.login"
API_BASE_URL = "https://api.ecloudeu.com"
API_BASE_URL_V2 = "https://apiv2.ecloudeu.com"
API_CARS_URL = "/device-platform/user/vehicle/secure"
API_SESION_URL = "/auth/account/session/secure"
API_SELECT_CAR_URL = "/device-platform/user/session/update"
API_TELEMATICS_URL = "/remote-control/vehicle/telematics/"

GLOBAL_API_BASE_URL = "https://sg-app-api.smart.com"
GLOBAL_APP_KEY = "204587190"
GLOBAL_APP_SECRET = "vxnzkHbpQrkKKQKmFBZlOnL780rjXLFT"

EU_OAUTH_BASE_URL = "https://api.app-auth.srv.smart.com/v1/"
EU_OAUTH_API_KEY = "yHpsjnd9vzLq7GMowxBa"

OTA_SERVER_URL = "https://ota.srv.smart.com/"

HTTPX_TIMEOUT = 30.0


class SmartRegion(str, Enum):
    """Region presets for Smart API endpoints.

    Use these region presets to easily configure the API for different geographic regions.
    - EU: European region (default) - for users with Hello Smart EU app
    - INTL: International region (Asia-Pacific) - for users with Hello Smart International app
           (Australia, Singapore, and other international markets)
    """

    EU = "eu"
    INTL = "intl"
    GLOBAL = "global"


class SmartAuthMode(str, Enum):
    """Authentication mode for Smart APIs."""

    EU_OAUTH = "eu_oauth"
    GLOBAL_HMAC = "global_hmac"


def get_endpoint_urls_for_region(region: SmartRegion) -> "EndpointUrls":
    """Get pre-configured EndpointUrls for a specific region.

    Args:
    ----
        region: The region to get endpoint URLs for.

    Returns:
    -------
        EndpointUrls configured for the specified region.

    Example:
    -------
        >>> from pysmarthashtag.const import SmartRegion, get_endpoint_urls_for_region
        >>> from pysmarthashtag.account import SmartAccount
        >>>
        >>> # For Australian/International users
        >>> endpoint_urls = get_endpoint_urls_for_region(SmartRegion.INTL)
        >>> account = SmartAccount("user@example.com", "password", endpoint_urls=endpoint_urls)
        >>>
        >>> # For European users (default)
        >>> endpoint_urls = get_endpoint_urls_for_region(SmartRegion.EU)
        >>> account = SmartAccount("user@example.com", "password", endpoint_urls=endpoint_urls)

    """
    if region == SmartRegion.EU:
        # European region - uses default endpoints
        return EndpointUrls()
    elif region == SmartRegion.INTL:
        # International region (Asia-Pacific) - for Hello Smart International app
        # Used in Australia, Singapore, and other international markets
        return EndpointUrls(
            api_base_url="https://api.ecloudap.com",
            api_base_url_v2="https://apiv2.ecloudap.com",
        )
    elif region == SmartRegion.GLOBAL:
        # Global app region (Australia/Israel) - uses sg-app-api endpoints
        return EndpointUrls(
            api_base_url=GLOBAL_API_BASE_URL,
            api_base_url_v2=GLOBAL_API_BASE_URL,
        )
    else:
        raise ValueError(f"Unknown region: {region}")


@dataclass
class EndpointUrls:
    """Configuration for API endpoint URLs.

    This allows customization of API endpoints for different regions (e.g., international).
    If any value is None, the default constant value will be used.
    """

    api_key: Optional[str] = None
    server_url: Optional[str] = None
    auth_url: Optional[str] = None
    login_url: Optional[str] = None
    api_base_url: Optional[str] = None
    api_base_url_v2: Optional[str] = None
    ota_server_url: Optional[str] = None
    oauth_base_url: Optional[str] = None
    oauth_api_key: Optional[str] = None
    global_app_key: Optional[str] = None
    global_app_secret: Optional[str] = None

    def get_api_key(self) -> str:
        """Get the API key, using the default if not set."""
        return self.api_key if self.api_key is not None else API_KEY

    def get_server_url(self) -> str:
        """Get the server URL, using the default if not set."""
        return self.server_url if self.server_url is not None else SERVER_URL

    def get_auth_url(self) -> str:
        """Get the auth URL, using the default if not set.

        Note: For international endpoints, you should provide a complete custom auth_url
        rather than relying on the api_key override, as the auth domain may differ.
        """
        if self.auth_url is not None:
            return self.auth_url
        # Use the default AUTH_URL constant, which includes the default API key
        # For custom API keys with the same auth domain, users should provide auth_url explicitly
        return AUTH_URL

    def get_login_url(self) -> str:
        """Get the login URL, using the default if not set."""
        return self.login_url if self.login_url is not None else LOGIN_URL

    def get_api_base_url(self) -> str:
        """Get the API base URL, using the default if not set."""
        return self.api_base_url if self.api_base_url is not None else API_BASE_URL

    def get_api_base_url_v2(self) -> str:
        """Get the API base URL v2, using the default if not set."""
        return self.api_base_url_v2 if self.api_base_url_v2 is not None else API_BASE_URL_V2

    def get_ota_server_url(self) -> str:
        """
        Return the configured OTA server URL or the module default.
        
        Returns:
            str: The OTA server URL; the configured `ota_server_url` when present, otherwise `OTA_SERVER_URL`.
        """
        return self.ota_server_url if self.ota_server_url is not None else OTA_SERVER_URL

    def get_oauth_base_url(self) -> str:
        """
        Return the OAuth base URL to use for token requests.
        
        Returns:
            The configured OAuth base URL string, or `EU_OAUTH_BASE_URL` if no override is set.
        """
        return self.oauth_base_url if self.oauth_base_url is not None else EU_OAUTH_BASE_URL

    def get_oauth_api_key(self) -> str:
        """
        Return the configured OAuth API key or the default if none is configured.
        
        Returns:
            str: The configured OAuth API key if set, otherwise the module default `EU_OAUTH_API_KEY`.
        """
        return self.oauth_api_key if self.oauth_api_key is not None else EU_OAUTH_API_KEY

    def get_oauth_token_url(self) -> str:
        """
        Builds the OAuth token endpoint URL for the configured OAuth base URL.
        
        Returns:
            The full token endpoint URL (the OAuth base URL with a single trailing '/token').
        """
        return f"{self.get_oauth_base_url().rstrip('/')}/token"

    def get_global_app_key(self) -> str:
        """
        Return the configured global app key or the default.
        
        Returns:
            global_app_key (str): The configured global app key if set, otherwise the module default GLOBAL_APP_KEY.
        """
        return self.global_app_key if self.global_app_key is not None else GLOBAL_APP_KEY

    def get_global_app_secret(self) -> str:
        """
        Return the configured global app secret for this endpoint.
        
        Returns:
            str: The global app secret set on this instance, or the module default `GLOBAL_APP_SECRET` if none is configured.
        """
        return self.global_app_secret if self.global_app_secret is not None else GLOBAL_APP_SECRET

    def _is_global_api_base_url(self, api_base_url: str) -> bool:
        """
        Determine whether `api_base_url` matches the module's global API base URL (ignoring a trailing slash).
        
        Returns:
            True if `api_base_url` equals `GLOBAL_API_BASE_URL` after removing a trailing slash, False otherwise.
        """
        normalized = api_base_url.rstrip("/")
        # Default global API base URL, plus any additional explicit variants if needed.
        global_base = GLOBAL_API_BASE_URL.rstrip("/")
        return normalized == global_base

    def infer_auth_mode(self) -> SmartAuthMode:
        """
        Selects the authentication mode to use based on the configured API base URL.
        
        Returns:
            SmartAuthMode: `SmartAuthMode.GLOBAL_HMAC` if the configured API base URL matches the global API base URL, `SmartAuthMode.EU_OAUTH` otherwise.
        """
        api_base_url = self.get_api_base_url()
        if self._is_global_api_base_url(api_base_url):
            return SmartAuthMode.GLOBAL_HMAC
        return SmartAuthMode.EU_OAUTH