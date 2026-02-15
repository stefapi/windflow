"""
Rate limiting utilities for WindFlow API.

Provides conditional rate limiting based on configuration:
- If rate limiting is enabled (RATE_LIMIT_ENABLED=true) and Redis is configured,
  uses fastapi-limiter for distributed rate limiting
- Otherwise, allows all requests through (no-op)
"""

from typing import Callable, Optional
from fastapi import Request
from fastapi_limiter.depends import RateLimiter

from ..config import settings


def conditional_rate_limiter(times: int, seconds: int) -> Optional[Callable]:
    """
    Create a conditional rate limiter dependency.

    Returns a RateLimiter if rate limiting is enabled and properly configured,
    otherwise returns a no-op dependency that allows all requests.

    Args:
        times: Number of requests allowed
        seconds: Time window in seconds

    Returns:
        RateLimiter instance if enabled, otherwise a no-op function

    Example:
        @router.get("/", dependencies=[Depends(conditional_rate_limiter(30, 60))])
        async def endpoint():
            ...
    """
    if settings.rate_limit_enabled and settings.rate_limit_storage_url:
        # Rate limiting is enabled and Redis is configured
        return RateLimiter(times=times, seconds=seconds)
    else:
        # Rate limiting is disabled or not properly configured
        # Return a no-op dependency that always allows requests
        async def no_op_limiter(request: Request):
            """No-op rate limiter when rate limiting is disabled."""
            pass

        return no_op_limiter


# Convenient aliases for common rate limits
def rate_limit_strict():
    """Strict rate limit: 5 requests per minute (for auth endpoints)."""
    return conditional_rate_limiter(5, 60)


def rate_limit_moderate():
    """Moderate rate limit: 30 requests per minute (for normal endpoints)."""
    return conditional_rate_limiter(30, 60)


def rate_limit_relaxed():
    """Relaxed rate limit: 100 requests per minute (for read operations)."""
    return conditional_rate_limiter(100, 60)
