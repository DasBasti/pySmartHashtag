import datetime
import logging
from pathlib import Path
from unittest import mock

import httpx
import pytest
import respx

from pysmarthashtag.account import SmartAccount

from . import TEST_PASSWORD, TEST_USERNAME


@pytest.mark.asyncio
async def test_login(smart_fixture: respx.Router):
    """Test the login flow."""
    account = SmartAccount(TEST_USERNAME, TEST_PASSWORD)
    await account.get_vehicles()
    assert account is not None
