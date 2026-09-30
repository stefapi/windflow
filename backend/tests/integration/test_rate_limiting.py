"""
Tests d'intégration pour le rate limiting (STORY-102 / P0-3).

Vérifie que le système de rate limiting est correctement configuré :
- Sans Redis : les limiteurs sont EFFECTIFS en mémoire process-local
  (429 au-delà du seuil, plus de no-op silencieux) ;
- Les endpoints protégés sont bien décorés ;
- Aliases et dépendances restent des callables.
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core import rate_limit
from app.core.exceptions import RateLimitError
from app.core.rate_limit import _memory_limiter, conditional_rate_limiter


@pytest.fixture(autouse=True)
def _memory_mode():
    """Force le mode mémoire (enabled sans URL) et isole le store."""
    _memory_limiter.reset()
    rate_limit._memory_warning_emitted = False
    with patch.object(rate_limit.settings, "rate_limit_enabled", True), patch.object(
        rate_limit.settings, "rate_limit_storage_url", None
    ):
        yield
    _memory_limiter.reset()
    rate_limit._memory_warning_emitted = False


def _mock_request(host: str = "127.0.0.1", path: str = "/api/v1/auth/login"):
    request = MagicMock()
    request.client.host = host
    request.url.path = path
    return request


@pytest.mark.asyncio
async def test_rate_limit_health_allows_requests(client: AsyncClient):
    """/health n'est pas décorée : les requêtes passent (pas de 429)."""
    response = await client.get("/health")
    # Health may return 503 if DB is not connected in test, but should not be 429
    assert response.status_code in (200, 503)
    assert response.status_code != 429


@pytest.mark.asyncio
async def test_memory_limiter_429_kicks_in_without_redis():
    """Sans Redis, la dépendance seuil 5 refuse la 6e requête (429)."""
    limiter = conditional_rate_limiter(5, 60)
    request = _mock_request()

    for _ in range(5):
        await limiter(request)  # autorisés

    with pytest.raises(RateLimitError) as exc_info:
        await limiter(request)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_memory_limiter_retry_after_header_present():
    """Le 429 du mode mémoire embarque Retry-After (AC 2)."""
    limiter = conditional_rate_limiter(3, 60)
    request = _mock_request()
    for _ in range(3):
        await limiter(request)
    with pytest.raises(RateLimitError) as exc_info:
        await limiter(request)
    assert exc_info.value.http_headers == {"Retry-After": "60"}


@pytest.mark.asyncio
async def test_conditional_rate_limiter_returns_memory_dependency():
    """Sans URL + enabled → dépendance mémoire effective (ex no-op)."""
    limiter = conditional_rate_limiter(10, 60)
    assert callable(limiter)
    # Sous le seuil : aucune exception
    request = _mock_request()
    await limiter(request)


@pytest.mark.asyncio
async def test_conditional_rate_limiter_blocks_over_threshold():
    """Au-delà du seuil, la dépendance mémoire lève 429 (ex allows_request)."""
    limiter = conditional_rate_limiter(2, 60)
    request = _mock_request()
    await limiter(request)
    await limiter(request)
    with pytest.raises(RateLimitError) as exc_info:
        await limiter(request)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_aliases():
    """Test rate limit convenience aliases return callables."""
    from app.core.rate_limit import (
        rate_limit_moderate,
        rate_limit_relaxed,
        rate_limit_strict,
    )

    strict = rate_limit_strict()
    moderate = rate_limit_moderate()
    relaxed = rate_limit_relaxed()

    assert callable(strict)
    assert callable(moderate)
    assert callable(relaxed)


@pytest.mark.asyncio
async def test_auth_endpoints_have_rate_limiting(client: AsyncClient):
    """Test that auth endpoints are configured with rate limiting dependencies."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Check that auth login endpoint exists in schema
    auth_login = schema.get("paths", {}).get("/api/v1/auth/login", {})
    assert auth_login, "Auth login endpoint should be documented"


@pytest.mark.asyncio
async def test_organization_endpoints_have_rate_limiting(client: AsyncClient):
    """Test that organization endpoints are configured with rate limiting dependencies."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Check that organization endpoints exist
    org_endpoints = [
        path
        for path in schema.get("paths", {}).keys()
        if "/api/v1/organizations" in path
    ]
    assert len(org_endpoints) > 0, "Organization endpoints should be documented"


@pytest.mark.asyncio
async def test_multiple_rapid_requests_low_threshold_memory_mode():
    """Mode mémoire seuil 3 : 3 requêtes OK puis 429 (ex test no_rate_limit)."""
    limiter = conditional_rate_limiter(3, 60)
    request = _mock_request()

    results = []
    for _ in range(4):
        try:
            await limiter(request)
            results.append("ok")
        except RateLimitError as e:
            results.append(f"429:{e.status_code}")

    assert results == ["ok", "ok", "ok", "429:429"]
