"""URLs for different services and error code mapping."""
from enum import Enum

API_KEY = "3_L94eyQ-wvJhWm7Afp1oBhfTGXZArUfSHHW9p9Pncg513hZELXsxCfMWHrF8f5P5a"
SERVER_URL = "https://awsapi.future.smart.com/login-app/api/v1/authorize?uiLocales=de-DE"

CONTEXT_URL = "https://awsapi.future.smart.com/login-app/api/v1/authorize?uiLocales=de-DE&uiLocales=de-DE"

AUTH_URL = f"https://auth.smart.com/oidc/op/v1.0/{API_KEY}/authorize/continue"

LOGIN_URL = "https://auth.smart.com/accounts.login"
HTTPX_TIMEOUT = 30.0