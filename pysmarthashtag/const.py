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

    def get_api_key(self) -> str:
        """Get the API key, using the default if not set."""
        return self.api_key if self.api_key is not None else API_KEY

    def get_server_url(self) -> str:
        """Get the server URL, using the default if not set."""
        return self.server_url if self.server_url is not None else SERVER_URL

    def get_auth_url(self) -> str:
        """Get the auth URL, using the default if not set."""
        if self.auth_url is not None:
            return self.auth_url
        # Reconstruct AUTH_URL using the current API key
        return f"https://auth.smart.com/oidc/op/v1.0/{self.get_api_key()}/authorize/continue"

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
