"""
Tests du rate limiting avec fallback mémoire (STORY-102 / P0-3).

Couvre :
- MemoryRateLimiter : fenêtre glissante, seuil exact, clés distinctes,
  purge des entrées expirées, reset ;
- conditional_rate_limiter v2 : 3 branches (Redis inchangé / mémoire avec
  warning unique / désactivé explicite), 429 + Retry-After, clé IP+path.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi_limiter.depends import RateLimiter

from app.core import cache as cache_module
from app.core import rate_limit
from app.core.exceptions import RateLimitError
from app.core.rate_limit import (
    MemoryRateLimiter,
    _memory_limiter,
    conditional_rate_limiter,
    rate_limit_moderate,
    rate_limit_relaxed,
    rate_limit_strict,
)


@pytest.fixture(autouse=True)
def _reset_state():
    """Isole chaque test : store mémoire vide + flags de warning réinitialisés.

    STORY-168 : le warning mémoire process-local est porté par le helper
    partagé ``core.cache.emit_degraded_warning_once`` — le flag réinitialisé
    est donc celui du module cache.
    """
    _memory_limiter.reset()
    cache_module._degraded_warning_emitted = False
    rate_limit._disabled_info_emitted = False
    yield
    _memory_limiter.reset()
    cache_module._degraded_warning_emitted = False
    rate_limit._disabled_info_emitted = False


def _make_request(host: str = "1.2.3.4", path: str = "/api/v1/auth/login"):
    """Construit une Request mockée avec client.host et url.path."""
    request = MagicMock()
    request.client.host = host
    request.url.path = path
    return request


class TestMemoryRateLimiter:
    """Tests purs de la classe (sans FastAPI)."""

    def test_allows_under_threshold_then_blocks(self):
        """5 hits OK puis 6e refusé (seuil exact, pas de off-by-one)."""
        limiter = MemoryRateLimiter()
        for _ in range(5):
            assert limiter.check("k", 5, 60) is True
        assert limiter.check("k", 5, 60) is False

    def test_exact_threshold_boundary(self):
        """Exactement `times` appels autorisés, le suivant refusé."""
        limiter = MemoryRateLimiter()
        assert limiter.check("k", 3, 60) is True
        assert limiter.check("k", 3, 60) is True
        assert limiter.check("k", 3, 60) is True
        assert limiter.check("k", 3, 60) is False

    def test_window_resets_after_expiry(self):
        """Après expiration de la fenêtre (temps avancé), le quota revient."""
        limiter = MemoryRateLimiter()
        with patch.object(rate_limit.time, "monotonic", return_value=100.0):
            for _ in range(5):
                assert limiter.check("k", 5, 60) is True
            assert limiter.check("k", 5, 60) is False
        # 61 s plus tard : fenêtre vidée
        with patch.object(rate_limit.time, "monotonic", return_value=161.0):
            assert limiter.check("k", 5, 60) is True

    def test_distinct_keys_per_identifier(self):
        """Clé A épuisée → clé B toujours autorisée (isolation IP+path)."""
        limiter = MemoryRateLimiter()
        for _ in range(5):
            assert limiter.check("1.1.1.1:/login", 5, 60) is True
        assert limiter.check("1.1.1.1:/login", 5, 60) is False
        assert limiter.check("2.2.2.2:/login", 5, 60) is True
        assert limiter.check("1.1.1.1:/other", 5, 60) is True

    def test_expired_entries_cleanup(self):
        """purge_expired() supprime les timestamps expirés et les clés vides."""
        limiter = MemoryRateLimiter()
        with patch.object(rate_limit.time, "monotonic", return_value=100.0):
            limiter.check("old-key", 5, 60)
            limiter.check("another", 5, 60)
        assert len(limiter._windows) == 2
        # Beaucoup plus tard : tout est expiré
        with patch.object(rate_limit.time, "monotonic", return_value=1000.0):
            limiter.purge_expired(max_age=600.0)
        assert len(limiter._windows) == 0

    def test_check_purges_on_each_call(self):
        """Les timestamps expirés sont purgés à chaque check de la clé."""
        limiter = MemoryRateLimiter()
        with patch.object(rate_limit.time, "monotonic", return_value=100.0):
            for _ in range(3):
                limiter.check("k", 10, 60)
        assert len(limiter._windows["k"]) == 3
        # Fenêtre expirée → le check purge la deque avant de décider
        with patch.object(rate_limit.time, "monotonic", return_value=200.0):
            assert limiter.check("k", 10, 60) is True
        assert len(limiter._windows["k"]) == 1

    def test_reset_clears_all_state(self):
        """reset() vide toutes les fenêtres."""
        limiter = MemoryRateLimiter()
        limiter.check("a", 5, 60)
        limiter.check("b", 5, 60)
        limiter.reset()
        assert limiter._windows == {}


class TestConditionalRateLimiterV2:
    """Tests de la façade à 3 branches."""

    def test_redis_path_unchanged_when_configured(self):
        """AC 3 : URL configurée → RateLimiter fastapi-limiter exact."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(
            rate_limit.settings,
            "rate_limit_storage_url",
            "redis://localhost:6379/0",
        ):
            limiter = conditional_rate_limiter(5, 60)
        assert isinstance(limiter, RateLimiter)
        assert limiter.times == 5
        # fastapi-limiter 0.1.6 stocke la fenêtre en millisecondes
        assert limiter.milliseconds == 60_000

    def test_no_repeated_warning_in_logs(self, caplog):
        """AC 5 : 2 appels sans URL → warning mémoire émis une seule fois.

        STORY-168 : le warning émane du helper partagé ``windflow.cache``
        (flag unique cache + rate limiter) — un seul record même après
        appels croisés.
        """
        with caplog.at_level(logging.WARNING, logger="windflow.cache"):
            with patch.object(
                rate_limit.settings, "rate_limit_enabled", True
            ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
                conditional_rate_limiter(5, 60)
                conditional_rate_limiter(30, 60)
        warnings = [r for r in caplog.records if "process-local" in r.getMessage()]
        assert len(warnings) == 1

    def test_warning_mentions_process_local_limitation(self, caplog):
        """AC 2 : le warning mentionne process-local et workers."""
        with caplog.at_level(logging.WARNING, logger="windflow.cache"):
            with patch.object(
                rate_limit.settings, "rate_limit_enabled", True
            ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
                conditional_rate_limiter(5, 60)
        message = caplog.records[-1].getMessage()
        assert "process-local" in message
        assert "workers" in message

    @pytest.mark.asyncio
    async def test_cross_consumer_warning_emitted_once(self, caplog):
        """STORY-168 : appels croisés cache + limiter → un seul warning."""
        from app.core.cache import get_cache, reset_cache

        reset_cache()
        with caplog.at_level(logging.WARNING, logger="windflow.cache"):
            with patch.object(
                rate_limit.settings, "rate_limit_enabled", True
            ), patch.object(
                rate_limit.settings, "rate_limit_storage_url", None
            ), patch.object(
                cache_module.settings, "cache_url", None
            ):
                await get_cache()
                conditional_rate_limiter(5, 60)
                conditional_rate_limiter(30, 60)
        reset_cache()
        warnings = [r for r in caplog.records if "process-local" in r.getMessage()]
        assert len(warnings) == 1

    @pytest.mark.asyncio
    async def test_memory_limiter_returns_429_after_threshold(self):
        """AC 5 : 6e hit dans la fenêtre → RateLimitError 429 (STORY-127)."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            limiter = conditional_rate_limiter(5, 60)

        request = _make_request()
        for _ in range(5):
            await limiter(request)  # pas d'exception

        with pytest.raises(RateLimitError) as exc_info:
            await limiter(request)
        assert exc_info.value.status_code == 429
        assert exc_info.value.message == "Too many requests"

    @pytest.mark.asyncio
    async def test_memory_dependency_returns_429_with_retry_after(self):
        """Le 429 embarque le header Retry-After."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            limiter = conditional_rate_limiter(3, 60)

        request = _make_request()
        for _ in range(3):
            await limiter(request)
        with pytest.raises(RateLimitError) as exc_info:
            await limiter(request)
        assert exc_info.value.http_headers == {"Retry-After": "60"}

    @pytest.mark.asyncio
    async def test_memory_key_uses_ip_and_path(self):
        """La clé du store est f"{ip}:{path}" (cohérent fastapi-limiter)."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            limiter = conditional_rate_limiter(100, 60)

        await limiter(_make_request(host="1.2.3.4", path="/api/v1/auth/login"))
        assert "1.2.3.4:/api/v1/auth/login" in _memory_limiter._windows

    @pytest.mark.asyncio
    async def test_memory_limiter_window_resets_after_expiry(self):
        """AC 5 : après la fenêtre, le quota est rétabli."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            limiter = conditional_rate_limiter(2, 60)

        request = _make_request()
        await limiter(request)
        await limiter(request)
        with pytest.raises(RateLimitError):
            await limiter(request)

        # Temps avancé au-delà de la fenêtre
        with patch.object(
            rate_limit.time, "monotonic", return_value=rate_limit.time.monotonic() + 999
        ):
            await limiter(request)  # à nouveau autorisé

    @pytest.mark.asyncio
    async def test_memory_limiter_distinct_keys_per_identifier(self):
        """AC 5 : IP différente → compteur distinct."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            limiter = conditional_rate_limiter(1, 60)

        await limiter(_make_request(host="1.1.1.1"))  # quota IP1 épuisé
        with pytest.raises(RateLimitError):
            await limiter(_make_request(host="1.1.1.1"))
        await limiter(_make_request(host="2.2.2.2"))  # IP2 OK

    def test_disabled_returns_explicit_noop(self, caplog):
        """AC 4 : disabled → no-op callable + log INFO explicite unique."""
        with caplog.at_level(logging.INFO, logger="windflow.rate_limit"):
            with patch.object(
                rate_limit.settings, "rate_limit_enabled", False
            ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
                limiter = conditional_rate_limiter(5, 60)
                conditional_rate_limiter(30, 60)  # 2e appel
        assert callable(limiter)
        infos = [r for r in caplog.records if "désactivé" in r.getMessage()]
        assert len(infos) == 1

    @pytest.mark.asyncio
    async def test_aliases_return_effective_limiters(self):
        """Les alias strict/moderate/relaxed sont effectifs sans Redis."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            strict = rate_limit_strict()
            moderate = rate_limit_moderate()
            relaxed = rate_limit_relaxed()

        request = _make_request()
        # strict = 5/min : 6e refusé
        for _ in range(5):
            await strict(request)
        with pytest.raises(RateLimitError):
            await strict(request)

        # moderate = 30/min, relaxed = 100/min : callables effectifs
        await moderate(request)
        await relaxed(request)

    @pytest.mark.asyncio
    async def test_unknown_client_uses_fallback_key(self):
        """Request sans client → clé "unknown:{path}" (pas de crash)."""
        with patch.object(
            rate_limit.settings, "rate_limit_enabled", True
        ), patch.object(rate_limit.settings, "rate_limit_storage_url", None):
            limiter = conditional_rate_limiter(5, 60)

        request = MagicMock()
        request.client = None
        request.url.path = "/x"
        await limiter(request)  # ne lève pas
        assert "unknown:/x" in _memory_limiter._windows
