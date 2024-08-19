"""Fixtures for Smart tests."""

import respx

from pysmarthashtag.const import (
    API_BASE_URL,
    API_CARS_URL,
    API_SELECT_CAR_URL,
    API_SESION_URL,
    AUTH_URL,
    CONTEXT_URL,
    LOGIN_URL,
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
        """Add routes for login."""

        # Login context
        self.get(CONTEXT_URL).respond(302, headers={"location": load_response(RESPONSE_DIR / "auth_context.url")})
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
        self.post(API_BASE_URL + API_SESION_URL + "?identity_type=smart").respond(
            200,
            json=load_response(RESPONSE_DIR / "api_access.json"),
        )
        self.get(API_BASE_URL + API_CARS_URL + "?needSharedCar=1&userId=112233").respond(
            200,
            json=load_response(RESPONSE_DIR / "vehicle_response.json"),
        )
        self.post(API_BASE_URL + API_SELECT_CAR_URL).respond(200, json={})
        self.get(
            API_BASE_URL
            + "/remote-control/vehicle/status/TestVIN0000000001?latest=True&target=basic%2Cmore&userId=112233"
        ).respond(
            200,
            json=load_response(RESPONSE_DIR / "vehicle_info.json"),
        )
        self.get(
            API_BASE_URL
            + "/remote-control/vehicle/status/TestVIN0000000002?latest=True&target=basic%2Cmore&userId=112233"
        ).respond(
            200,
            json=load_response(RESPONSE_DIR / "vehicle_info_dc_charging.json"),
        )
        self.put(API_BASE_URL + "/remote-control/vehicle/telematics/TestVIN0000000001").respond(
            200, json=load_response(RESPONSE_DIR / "climate_success.json")
        )
        self.get(API_BASE_URL + "/remote-control/vehicle/status/soc/TestVIN0000000001?setting=charging").respond(
            200,
            json=load_response(RESPONSE_DIR / "soc_90.json"),
        )
        self.get(API_BASE_URL + "/remote-control/vehicle/status/soc/TestVIN0000000002?setting=charging").respond(
            200,
            json=load_response(RESPONSE_DIR / "soc_90.json"),
        )
