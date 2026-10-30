"""Tests d'intégration du cache unifié avec Redis réel (STORY-168, AC 2).

Skippés si Redis n'est pas joignable (``WINDFLOW_TEST_REDIS_URL``, défaut
``redis://localhost:6379/15`` — DB dédiée aux tests, éphémère ; pattern
``test_events_pubsub.py``).

Familles :

- ``set`` → clé lisible côté Redis via un client témoin (``GET``, préfixe
  ``rbac``) ; TTL exposé > 0 ; ``delete`` → clé absente ;
- ``clear_prefix`` vérifié par ``SCAN`` côté témoin ;
- échec Redis en cours d'exécution (client fermé) → bascule mémoire avec
  log, sans exception remontée à l'appelant.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.cache import RedisCache, _safe_redis_url, resolve_cache_redis_url

REDIS_TEST_URL = os.environ.get("WINDFLOW_TEST_REDIS_URL", "redis://localhost:6379/15")

pytestmark = pytest.mark.integration


def _redis_available() -> bool:
    """Probe Redis de test (import + ping synchrone, timeout court)."""
    try:
        import redis  # noqa: PLC0415 — probe dédiée

        client = redis.from_url(REDIS_TEST_URL, socket_connect_timeout=1)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def redis_url() -> str:
    if not _redis_available():
        pytest.skip(f"Redis de test indisponible ({REDIS_TEST_URL})")
    return REDIS_TEST_URL


async def test_set_key_visible_in_redis_with_ttl(redis_url):
    """AC 2 : set → clé lisible côté témoin, TTL exposé > 0."""
    import redis.asyncio as aioredis

    witness = aioredis.from_url(redis_url)
    cache = RedisCache(witness)
    key = f"rbac:role:integ-{uuid.uuid4().hex[:8]}"

    try:
        assert await cache.set(key, "admin", ttl=120) is True

        raw = await witness.get(key)
        assert raw is not None, "clé absente côté Redis"
        assert json.loads(raw) == "admin"  # valeur JSON-sérialisée

        ttl = await witness.ttl(key)
        assert 0 < ttl <= 120  # TTL exposé par Redis
    finally:
        await witness.delete(key)
        await witness.aclose()


async def test_get_round_trip_and_delete(redis_url):
    """AC 2 : get round-trip puis delete → clé absente côté témoin."""
    import redis.asyncio as aioredis

    witness = aioredis.from_url(redis_url)
    cache = RedisCache(witness)
    key = f"rbac:role:integ-{uuid.uuid4().hex[:8]}"

    try:
        await cache.set(key, "viewer", ttl=60)
        assert await cache.get(key) == "viewer"  # round-trip JSON

        assert await cache.delete(key) is True
        assert await witness.get(key) is None  # supprimée côté Redis
    finally:
        await witness.delete(key)
        await witness.aclose()


async def test_dict_value_round_trip(redis_url):
    """Valeurs structurées : dict JSON round-trip via le cache Redis."""
    import redis.asyncio as aioredis

    witness = aioredis.from_url(redis_url)
    cache = RedisCache(witness)
    key = f"llm:integ-{uuid.uuid4().hex[:8]}"
    payload = {"content": "compose-gen", "cached": False}

    try:
        await cache.set(key, payload, ttl=30)
        assert await cache.get(key) == payload
    finally:
        await witness.delete(key)
        await witness.aclose()


async def test_clear_prefix_removes_only_matching_keys(redis_url):
    """clear_prefix : SCAN côté témoin → seules les clés du préfixe disparaissent."""
    import redis.asyncio as aioredis

    witness = aioredis.from_url(redis_url)
    cache = RedisCache(witness)
    marker = uuid.uuid4().hex[:8]
    in_prefix = [f"rbac:role:integ-{marker}-{i}" for i in range(3)]
    outside = [f"llm:integ-{marker}-{i}" for i in range(2)]

    try:
        for key in in_prefix + outside:
            await cache.set(key, "x", ttl=60)

        await cache.clear_prefix(f"rbac:role:integ-{marker}")

        for key in in_prefix:
            assert await witness.get(key) is None
        for key in outside:
            assert await witness.get(key) is not None
    finally:
        for key in in_prefix + outside:
            await witness.delete(key)
        await witness.aclose()


async def test_midflight_failure_switches_to_memory_without_raising(redis_url, caplog):
    """AC 2 : échec Redis en cours d'exécution → bascule mémoire + log.

    Une ``ConnectionError`` est injectée sur les commandes du client
    réellement connecté (le pool redis-py se reconnecterait sinon
    automatiquement — la fermeture seule ne produit pas d'échec).
    Les opérations suivantes basculent sur le fallback mémoire et
    n'échouent jamais côté appelant.
    """
    import redis.asyncio as aioredis

    witness = aioredis.from_url(redis_url)
    cache = RedisCache(witness)
    key = f"rbac:role:integ-{uuid.uuid4().hex[:8]}"

    # Connexion réelle validée, puis panne simulée en cours de route
    await witness.ping()
    witness.get = AsyncMock(side_effect=ConnectionError("connection lost"))
    witness.set = AsyncMock(side_effect=ConnectionError("connection lost"))
    witness.delete = AsyncMock(side_effect=ConnectionError("connection lost"))

    with caplog.at_level(logging.WARNING, logger="windflow.cache"):
        # set bascule mémoire sans lever
        assert await cache.set(key, "operator", ttl=60) is True
        assert await cache.get(key) == "operator"  # servi par le fallback
        assert await cache.delete(key) is True

    assert any("memory fallback" in r.getMessage() for r in caplog.records)


async def test_health_check_reflects_connectivity(redis_url):
    """health_check : True client joignable, False commande en échec."""
    import redis.asyncio as aioredis

    witness = aioredis.from_url(redis_url)
    cache = RedisCache(witness)
    assert await cache.health_check() is True

    witness.ping = AsyncMock(side_effect=ConnectionError("connection lost"))
    assert await cache.health_check() is False


def test_safe_redis_url_masks_credentials():
    """Sécurité (rules 40) : l'URL témoin avec password n'expose pas le secret."""
    masked = _safe_redis_url("redis://:secret@host:6379/1")
    assert "secret" not in masked


def test_resolve_prefers_cache_url_setting(monkeypatch):
    """Résolution : cache_url prioritaire, sinon rate_limit_storage_url."""
    from app.core import cache as cache_module

    monkeypatch.setattr(
        cache_module.settings, "cache_url", "redis://cache:6379/1", raising=False
    )
    monkeypatch.setattr(
        cache_module.settings,
        "rate_limit_storage_url",
        "redis://rl:6379/0",
        raising=False,
    )
    assert resolve_cache_redis_url() == "redis://cache:6379/1"

    monkeypatch.setattr(cache_module.settings, "cache_url", None, raising=False)
    assert resolve_cache_redis_url() == "redis://rl:6379/0"
