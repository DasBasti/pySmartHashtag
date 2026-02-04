"""Fixtures for Smart tests."""

import json

import httpx
import respx

from pysmarthashtag.const import (
    API_BASE_URL,
    API_BASE_URL_V2,
    API_CARS_URL,
    API_SELECT_CAR_URL,
    API_SESION_URL,
    AUTH_URL,
    EU_OAUTH_BASE_URL,
    GLOBAL_API_BASE_URL,
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
        """Add routes for login."""

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

    def add_global_routes(self) -> None:
        """Add routes for global authentication mode."""
        # Global vehicle ownership list
        self.post(GLOBAL_API_BASE_URL + "/vc/vehicle/v1/ownership/list").respond(
            200,
            json=load_response(RESPONSE_DIR / "global_vehicle_list.json"),
        )
        
        # Global vehicle details - use side_effect to return different responses based on request
        def vehicle_details_handler(request, route):
            body = json.loads(request.content)
            vin = body.get("vin")
            if vin == "TestVIN0000000001":
                return httpx.Response(200, json=load_response(RESPONSE_DIR / "global_vehicle_details.json"))
            elif vin == "TestVIN0000000002":
                return httpx.Response(200, json=load_response(RESPONSE_DIR / "global_vehicle_details2.json"))
            return httpx.Response(404, json={"code": "404", "message": "Vehicle not found"})
        
        self.post(GLOBAL_API_BASE_URL + "/vc/vehicle/v1/vehicleCustomerInfo").mock(side_effect=vehicle_details_handler)
        
        # Global vehicle abilities (need to handle dynamic model codes)
        self.route(method="GET", url__regex=r"^" + GLOBAL_API_BASE_URL + r"/vc/vehicle/v1/ability/.+/.+$").respond(
            200,
            json=load_response(RESPONSE_DIR / "global_vehicle_abilities.json"),
        )


class SmartGlobalMockRouter(respx.MockRouter):
    """Stateful MockRouter for Smart Global APIs."""

    def __init__(
        self,
    ) -> None:
        """Initialize the SmartGlobalMockRouter with clean responses for global auth."""
        super().__init__(assert_all_called=False)

        self.add_login_routes()
        self.add_global_routes()

    def add_login_routes(self) -> None:
        """Add routes for login (global HMAC flow)."""
        # Global login uses a different endpoint
        self.post(GLOBAL_API_BASE_URL + "/iam/service/api/v1/login").respond(
            200,
            json={
                "code": "0000",
                "message": "success",
                "data": {
                    "accessToken": "TestGlobalAccessToken",
                    "refreshToken": "TestGlobalRefreshToken",
                    "idToken": "TestGlobalIdToken",
                    "userId": "112233",
                    "expiresIn": 3600,
                },
            },
        )

    def add_global_routes(self) -> None:
        """Add routes for global authentication mode."""
        # Global vehicle ownership list
        self.post(GLOBAL_API_BASE_URL + "/vc/vehicle/v1/ownership/list").respond(
            200,
            json=load_response(RESPONSE_DIR / "global_vehicle_list.json"),
        )
        
        # Global vehicle details - use side_effect to return different responses based on request
        def vehicle_details_handler(request, route):
            body = json.loads(request.content)
            vin = body.get("vin")
            if vin == "TestVIN0000000001":
                return httpx.Response(200, json=load_response(RESPONSE_DIR / "global_vehicle_details.json"))
            elif vin == "TestVIN0000000002":
                return httpx.Response(200, json=load_response(RESPONSE_DIR / "global_vehicle_details2.json"))
            return httpx.Response(404, json={"code": "404", "message": "Vehicle not found"})
        
        self.post(GLOBAL_API_BASE_URL + "/vc/vehicle/v1/vehicleCustomerInfo").mock(side_effect=vehicle_details_handler)
        
        # Global vehicle abilities (need to handle dynamic model codes)
        self.route(method="GET", url__regex=r"^" + GLOBAL_API_BASE_URL + r"/vc/vehicle/v1/ability/.+/.+$").respond(
            200,
            json=load_response(RESPONSE_DIR / "global_vehicle_abilities.json"),
        )
