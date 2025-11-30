"""SSL context creation utilities for async operations.

This module provides utilities to create SSL contexts asynchronously,
avoiding blocking calls in the async event loop.
"""

import asyncio
import ssl
from functools import lru_cache
from typing import Optional


def _create_ssl_context() -> ssl.SSLContext:
    """Create an SSL context with default certificate verification.

    This function creates an SSL context with the default CA certificates.
    It is a blocking operation and should be called via run_in_executor
    when used in async code.
    """
    return ssl.create_default_context()


@lru_cache(maxsize=1)
def get_ssl_context() -> ssl.SSLContext:
    """Get a cached SSL context.

    This returns a cached SSL context to avoid recreating it multiple times.
    Note: This should only be called from a thread (via run_in_executor)
    or during module initialization.
    """
    return _create_ssl_context()


async def create_ssl_context_async() -> ssl.SSLContext:
    """Create an SSL context asynchronously.

    This function runs the blocking SSL context creation in a thread pool
    executor to avoid blocking the async event loop.

    Returns
    -------
        ssl.SSLContext: An SSL context with default certificate verification.

    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_ssl_context)


# Module-level SSL context cache with lock for thread safety
_ssl_context_cache: Optional[ssl.SSLContext] = None
_ssl_context_lock: Optional[asyncio.Lock] = None


async def get_ssl_context_async() -> ssl.SSLContext:
    """Get or create an SSL context asynchronously.

    This function returns a cached SSL context if available, or creates
    a new one asynchronously if not. Thread-safe using asyncio.Lock.

    Returns
    -------
        ssl.SSLContext: An SSL context with default certificate verification.

    """
    global _ssl_context_cache, _ssl_context_lock

    # Fast path: return cached context if available
    if _ssl_context_cache is not None:
        return _ssl_context_cache

    # Lazy initialization of lock within async context
    if _ssl_context_lock is None:
        _ssl_context_lock = asyncio.Lock()

    # Slow path: create context with lock protection
    async with _ssl_context_lock:
        # Double-check after acquiring lock
        if _ssl_context_cache is None:
            _ssl_context_cache = await create_ssl_context_async()

    return _ssl_context_cache
