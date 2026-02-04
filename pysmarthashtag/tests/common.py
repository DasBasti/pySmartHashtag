"""Fixtures for Smart tests."""

import respx

from pysmarthashtag.const import (
    API_BASE_URL,
    API_BASE_URL_V2,
    API_CARS_URL,
    API_SELECT_CAR_URL,
    API_SESION_URL,
    AUTH_URL,
    EU_OAUTH_BASE_URL,
    LOGIN_URL,
    OTA_SERVER_URL,
    SERVER_URL,
)
from pysmarthashtag.tests import RESPONSE_DIR, load_response


class SmartMockRouter(respx.MockRouter):
    """Stateful MockRouter for Smart APIs."""

    def __init__(
        self,
    ) -> None:
        """Initialize the SmartMockRouter with clean responses."""
        super().__init__(assert_all_called=False)

        self.add_login_routes()

    # # # # # # # # # # # # # # # # # # # # # # # #
    # Routes
    # # # # # # # # # # # # # # # # # # # # # # # #

    def add_login_routes(self) -> None:
        """
        Register mocked HTTP routes for the Smart API login flow and related endpoints.
        
        This sets up a stateful sequence of mocked responses used by tests, including:
        - initial server redirect and authentication context endpoints,
        - login endpoint returning a test session token and intermediate redirect,
        - OAuth token endpoint returning access/refresh/id tokens,
        - SMART session and vehicle-related endpoints (for both API_BASE_URL and API_BASE_URL_V2) used to fetch car lists, select a car, retrieve vehicle status and SOC, and perform telematics/remote-control actions,
        - OTA app info endpoints for test VINs.
        
        Responses use predefined JSON fixtures loaded from the test RESPONSE_DIR.
        """

        # Login context
        self.get(SERVER_URL).respond(302, headers={"location": load_response(RESPONSE_DIR / "auth_context.url")})
        self.get(load_response(RESPONSE_DIR / "auth_context.url")).respond(
            200,
        )
        self.post(LOGIN_URL).respond(
            200,
            json={"sessionInfo": {"login_token": "TestToken", "expires_in": 3600}},
            headers={"location": load_response(RESPONSE_DIR / "auth_intermediate.url")},
        )
        self.get(
            AUTH_URL + "?context=eu1_tk1.WTygkw2cU6QLANxlBVba0lP4ndHARZgp14RhsVBRiVE.1705656141&login_token=TestToken"
        ).respond(302, headers={"location": "https://auth.smart.com" + load_response(RESPONSE_DIR / "auth_result.url")})
        self.get("https://auth.smart.com" + load_response(RESPONSE_DIR / "auth_result.url")).respond(
            200,
            json=load_response(RESPONSE_DIR / "login_result.json"),
            headers={"location": load_response(RESPONSE_DIR / "auth_result.url")},
        )
        self.post(EU_OAUTH_BASE_URL + "token").respond(
            200,
            json={
                "accessToken": "TestAccessToken",
                "refreshToken": "TestRefreshToken",
                "idToken": "TestIdToken",
                "expiresIn": 3600,
            },
        )
        for base_url in [API_BASE_URL, API_BASE_URL_V2]:
            self.post(base_url + API_SESION_URL + "?identity_type=smart").respond(
                200,
                json=load_response(RESPONSE_DIR / "api_access.json"),
            )
            self.get(base_url + API_CARS_URL + "?needSharedCar=1&userId=112233").respond(
                200,
                json=load_response(RESPONSE_DIR / "vehicle_response.json"),
            )
            self.post(base_url + API_SELECT_CAR_URL).respond(200, json={})
            self.get(
                base_url
                + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
            ).respond(
                200,
                json=load_response(RESPONSE_DIR / "vehicle_info.json"),
            )
            self.get(
                base_url
                + "/remote-control/vehicle/status/TestVIN0000000002?latest=True&target=basic%2Cmore&userId=112233"
            ).respond(
                200,
                json=load_response(RESPONSE_DIR / "vehicle_info_dc_charging.json"),
            )
            self.put(base_url + "/remote-control/vehicle/telematics/TestVIN0000000001").respond(
                200, json=load_response(RESPONSE_DIR / "climate_success.json")
            )
            self.get(base_url + "/remote-control/vehicle/status/soc/TestVIN0000000001?setting=charging").respond(
                200,
                json=load_response(RESPONSE_DIR / "soc_90.json"),
            )
            self.get(base_url + "/remote-control/vehicle/status/soc/TestVIN0000000002?setting=charging").respond(
                200,
                json=load_response(RESPONSE_DIR / "soc_90.json"),
            )

        self.get(OTA_SERVER_URL + "app/info/TestVIN0000000001").respond(
            200,
            json=load_response(RESPONSE_DIR / "ota_response.json"),
        )
        self.get(OTA_SERVER_URL + "app/info/TestVIN0000000002").respond(
            200,
            json=load_response(RESPONSE_DIR / "ota_response.json"),
        )