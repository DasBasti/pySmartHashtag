"""URLs for different services and error code mapping."""

from dataclasses import dataclass
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

OTA_SERVER_URL = "https://ota.srv.smart.com/"

# Gigya socialize endpoint used to bootstrap a Gigya session (gmid + ucid)
# before posting accounts.login. Smart's tenant rejects accounts.login from
# a "fresh" client without these identifiers + the gig_bootstrap cookie.
GIGYA_SOCIALIZE_URL = "https://socialize.eu1.gigya.com"

# Browser-shaped User-Agent used by the Hello Smart Android webview.
# Smart's API Gateway (awsapi.future.smart.com) returns 403 for the iOS-app
# UA used elsewhere; the OIDC redirect chain only accepts a webview UA.
WEBVIEW_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; SM-S911B) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)

# Maximum redirect hops to follow when walking the OIDC chain manually.
# Smart's chain is currently 2-3 hops; the upper bound provides slack for
# future shifts without unbounded looping.
MAX_REDIRECT_HOPS = 5

HTTPX_TIMEOUT = 30.0


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
    gigya_socialize_url: Optional[str] = None

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
        """Get the OTA server URL, using the default if not set."""
        return self.ota_server_url if self.ota_server_url is not None else OTA_SERVER_URL

    def get_gigya_socialize_url(self) -> str:
        """Get the Gigya socialize URL, using the default if not set."""
        return self.gigya_socialize_url if self.gigya_socialize_url is not None else GIGYA_SOCIALIZE_URL
