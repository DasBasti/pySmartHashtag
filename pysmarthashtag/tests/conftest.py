"""Fixtures for Smart tests."""

from typing import Generator

import pytest
import respx

from pysmarthashtag.account import SmartAccount

from . import (
    TEST_PASSWORD,
    TEST_USERNAME,
)
from .common import SmartMockRouter


@pytest.fixture
def smart_fixture(request: pytest.FixtureRequest) -> Generator[respx.MockRouter, None, None]:
    """Patch Smart login API calls."""
    # Now we can start patching the API calls
    router = SmartMockRouter()

    with router:
        yield router


async def prepare_account_with_vehicles():
    """Initialize account and get vehicles."""
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD)
    await account.get_vehicles()
    return account
