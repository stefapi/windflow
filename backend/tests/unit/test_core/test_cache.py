"""Tests unitaires du cache des rôles RBAC (STORY-122.1).

Couverture :
- ``MemoryRoleCache`` : set/get, TTL expiré → miss + purge paresseuse,
  delete, clear_prefix, absence d'expiration si ttl=None ;
- ``RedisRoleCache`` : client mocké (pas de Redis réel en unitaire),
  fallback mémoire transparent sur échec Redis ;
- ``get_role_cache()`` : factory — sans URL Redis configurée → mémoire.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import cache as cache_module
from app.core.cache import (
    MemoryRoleCache,
    RedisRoleCache,
    get_role_cache,
    reset_role_cache,
)


@pytest.fixture(autouse=True)
def _fresh_role_cache_singleton():
    """Réinitialise le singleton de la factory autour de chaque test."""
    reset_role_cache()
    yield
    reset_role_cache()


class TestMemoryRoleCache:
    """MemoryRoleCache — store process-local à TTL monotone."""

    async def test_set_then_get_returns_value(self):
        """Cas nominal : set puis get retourne la valeur."""
        store = MemoryRoleCache()
        assert await store.set("rbac:role:user-1", "admin", ttl=300) is True
        assert await store.get("rbac:role:user-1") == "admin"

    async def test_get_missing_key_returns_none(self):
        """Clé absente → None."""
        store = MemoryRoleCache()
        assert await store.get("rbac:role:unknown") is None

    async def test_expired_ttl_returns_none_and_purges(self):
        """TTL expiré → miss (None) et entrée purgée paresseusement."""
        store = MemoryRoleCache()
        await store.set("rbac:role:user-1", "viewer", ttl=1)
        # Simule l'écoulement du TTL : l'entrée expire au prochain tick monotonic
        key = "rbac:role:user-1"
        stored_value, stored_expiry = store._store[key]
        store._store[key] = (stored_value, stored_expiry - 10)
        assert await store.get(key) is None
        # Purge paresseuse : l'entrée a été retirée du store
        assert key not in store._store

    async def test_no_ttl_never_expires(self):
        """ttl=None → aucune expiration (entrées permanentes)."""
        store = MemoryRoleCache()
        await store.set("rbac:role:user-1", "operator", ttl=None)
        key = "rbac:role:user-1"
        _, stored_expiry = store._store[key]
        assert stored_expiry == float("inf")
        assert await store.get(key) == "operator"

    async def test_delete_existing_key(self):
        """delete retire la clé et retourne True."""
        store = MemoryRoleCache()
        await store.set("rbac:role:user-1", "admin", ttl=300)
        assert await store.delete("rbac:role:user-1") is True
        assert await store.get("rbac:role:user-1") is None

    async def test_delete_missing_key_returns_false(self):
        """delete d'une clé absente → False."""
        store = MemoryRoleCache()
        assert await store.delete("rbac:role:unknown") is False

    async def test_clear_prefix_removes_matching_keys_only(self):
        """clear_prefix supprime les clés du préfixe, épargne les autres."""
        store = MemoryRoleCache()
        await store.set("rbac:role:user-1", "viewer", ttl=300)
        await store.set("rbac:role:user-2", "admin", ttl=300)
        await store.set("other:key", "value", ttl=300)
        await store.clear_prefix("rbac:role:")
        assert await store.get("rbac:role:user-1") is None
        assert await store.get("rbac:role:user-2") is None
        assert await store.get("other:key") == "value"


class TestRedisRoleCache:
    """RedisRoleCache — client mocké, fallback mémoire sur échec."""

    async def test_get_returns_decoded_string(self):
        """Cas nominal : valeur bytes Redis décodée en str."""
        client = MagicMock()
        client.get = AsyncMock(return_value=b"admin")
        store = RedisRoleCache(client)
        assert await store.get("rbac:role:user-1") == "admin"

    async def test_get_missing_key_returns_none(self):
        """Clé absente côté Redis → None."""
        client = MagicMock()
        client.get = AsyncMock(return_value=None)
        store = RedisRoleCache(client)
        assert await store.get("rbac:role:user-1") is None

    async def test_set_uses_native_ttl(self):
        """set délègue à Redis avec ex=ttl (TTL native)."""
        client = MagicMock()
        client.set = AsyncMock(return_value=True)
        store = RedisRoleCache(client)
        assert await store.set("rbac:role:user-1", "admin", ttl=300) is True
        client.set.assert_awaited_once_with("rbac:role:user-1", "admin", ex=300)

    async def test_delete_calls_redis_and_memory(self):
        """delete supprime côté Redis et purge le fallback mémoire."""
        client = MagicMock()
        client.delete = AsyncMock(return_value=1)
        store = RedisRoleCache(client)
        await store._memory_fallback.set("rbac:role:user-1", "admin", ttl=300)
        assert await store.delete("rbac:role:user-1") is True
        client.delete.assert_awaited_once_with("rbac:role:user-1")
        assert await store._memory_fallback.get("rbac:role:user-1") is None

    async def test_get_failure_falls_back_to_memory(self):
        """Échec Redis get → warning + fallback mémoire transparent."""
        client = MagicMock()
        client.get = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisRoleCache(client)
        await store._memory_fallback.set("rbac:role:user-1", "viewer", ttl=300)
        assert await store.get("rbac:role:user-1") == "viewer"

    async def test_set_failure_falls_back_to_memory(self):
        """Échec Redis set → fallback mémoire, l'écriture n'échoue jamais."""
        client = MagicMock()
        client.set = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisRoleCache(client)
        assert await store.set("rbac:role:user-1", "operator", ttl=300) is True
        assert await store._memory_fallback.get("rbac:role:user-1") == "operator"

    async def test_publish_is_best_effort(self):
        """publish best-effort : échec Redis loggé sans lever."""
        client = MagicMock()
        client.publish = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisRoleCache(client)
        await store.publish("rbac:role:invalidate", "user-1")  # ne lève pas

    async def test_publish_success(self):
        """Cas nominal : publish délègue au client Redis."""
        client = MagicMock()
        client.publish = AsyncMock(return_value=1)
        store = RedisRoleCache(client)
        await store.publish("rbac:role:invalidate", "user-1")
        client.publish.assert_awaited_once_with("rbac:role:invalidate", "user-1")


class TestGetRoleCacheFactory:
    """Factory get_role_cache — sélection du backend."""

    async def test_without_redis_url_returns_memory(self, monkeypatch):
        """Sans URL Redis configurée → MemoryRoleCache (mode léger)."""
        monkeypatch.setattr(
            cache_module.settings, "rate_limit_storage_url", None, raising=False
        )
        backend = await get_role_cache()
        assert isinstance(backend, MemoryRoleCache)

    async def test_factory_is_memoized(self):
        """Résolution paresseuse mémosée : même instance aux appels suivants."""
        first = await get_role_cache()
        second = await get_role_cache()
        assert first is second

    async def test_unreachable_redis_falls_back_to_memory(self, monkeypatch):
        """URL configurée mais Redis injoignable → fallback mémoire."""
        monkeypatch.setattr(
            cache_module.settings,
            "rate_limit_storage_url",
            "redis://localhost:1/9",
            raising=False,
        )
        backend = await get_role_cache()
        assert isinstance(backend, MemoryRoleCache)
