"""Tests for SSL context async creation."""

import ssl

import pytest

from pysmarthashtag.api.ssl_context import (
    create_ssl_context_async,
    get_ssl_context,
    get_ssl_context_async,
)


class TestSslContextSync:
    """Tests for synchronous SSL context creation."""

    def test_get_ssl_context_returns_ssl_context(self):
        """Test that get_ssl_context returns an SSL context."""
        ctx = get_ssl_context()
        assert isinstance(ctx, ssl.SSLContext)

    def test_get_ssl_context_is_cached(self):
        """Test that get_ssl_context returns the same cached context."""
        ctx1 = get_ssl_context()
        ctx2 = get_ssl_context()
        # Same object should be returned due to lru_cache
        assert ctx1 is ctx2


class TestSslContextAsync:
    """Tests for asynchronous SSL context creation."""

    @pytest.mark.asyncio
    async def test_create_ssl_context_async_returns_ssl_context(self):
        """Test that create_ssl_context_async returns an SSL context."""
        ctx = await create_ssl_context_async()
        assert isinstance(ctx, ssl.SSLContext)

    @pytest.mark.asyncio
    async def test_get_ssl_context_async_returns_ssl_context(self):
        """Test that get_ssl_context_async returns an SSL context."""
        ctx = await get_ssl_context_async()
        assert isinstance(ctx, ssl.SSLContext)

    @pytest.mark.asyncio
    async def test_get_ssl_context_async_is_cached(self):
        """Test that get_ssl_context_async returns the same cached context."""
        ctx1 = await get_ssl_context_async()
        ctx2 = await get_ssl_context_async()
        # Same object should be returned due to caching
        assert ctx1 is ctx2

    @pytest.mark.asyncio
    async def test_ssl_context_has_default_verify_mode(self):
        """Test that the SSL context has certificate verification enabled."""
        ctx = await get_ssl_context_async()
        # Default context should have certificate verification
        assert ctx.verify_mode == ssl.CERT_REQUIRED
