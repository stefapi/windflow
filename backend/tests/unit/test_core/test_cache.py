"""Tests unitaires du cache unifié (STORY-122.1 + STORY-168).

Couverture :
- ``MemoryCache`` : set/get valeurs ``Any`` (str, dict, int), TTL expiré →
  miss + purge paresseuse, ttl=None → permanent, delete, clear_prefix,
  **borne ``cache_memory_max_entries``** (éviction FIFO), contrat ABC
  ``CacheManager`` (exists/clear/health_check) ;
- ``RedisCache`` : sérialisation JSON round-trip, TTL native ``ex=``,
  fallback mémoire transparent sur échec Redis (get/set/delete), warning
  d'épisode dégradé émis une fois, publish best-effort ;
- Factory ``get_cache()`` : sans URL → mémoire + warning de dégradation
  unique, ``cache_url`` prioritaire sur ``rate_limit_storage_url``, URL
  configurée mais ping KO → mémoire + warning, singleton mémosé,
  ``reset_cache()`` / ``shutdown_cache()`` idempotente ;
- Compatibilité STORY-122.1 : aliases ``MemoryRoleCache``/``RedisRoleCache``,
  ``get_role_cache()`` → même singleton, round-trip des libellés de rôle ;
- Sécurité (rules 40) : masquage des credentials Redis dans les logs.
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core import cache as cache_module
from app.core.cache import (
    MemoryCache,
    MemoryRoleCache,
    RedisCache,
    RedisRoleCache,
    _safe_redis_url,
    get_cache,
    get_role_cache,
    reset_cache,
    reset_role_cache,
    shutdown_cache,
)


@pytest.fixture(autouse=True)
def _fresh_cache_singleton():
    """Réinitialise le singleton + le flag de warning autour de chaque test."""
    reset_cache()
    cache_module._degraded_warning_emitted = False
    yield
    reset_cache()
    cache_module._degraded_warning_emitted = False


def _fake_redis_client(*, ping_ok: bool = True, fail: bool = False) -> MagicMock:
    """Construit un client redis mocké (ping OK/KO ou échec systématique)."""
    client = MagicMock()
    if fail:
        client.ping = AsyncMock(side_effect=ConnectionError("redis down"))
        client.get = AsyncMock(side_effect=ConnectionError("redis down"))
        client.set = AsyncMock(side_effect=ConnectionError("redis down"))
        client.delete = AsyncMock(side_effect=ConnectionError("redis down"))
    else:
        client.ping = AsyncMock(return_value=ping_ok)
    return client


def _fake_aioredis(client: MagicMock) -> MagicMock:
    """Construit un module redis.asyncio factice dont from_url → client."""
    fake = MagicMock()
    fake.from_url = MagicMock(return_value=client)
    return fake


class TestMemoryCache:
    """MemoryCache — store process-local à TTL monotone, borné (AC 1, 4)."""

    async def test_set_then_get_returns_str_value(self):
        """Cas nominal : set puis get retourne la valeur str."""
        store = MemoryCache()
        assert await store.set("rbac:role:user-1", "admin", ttl=300) is True
        assert await store.get("rbac:role:user-1") == "admin"

    async def test_set_get_any_values_round_trip(self):
        """Valeurs Any : str, dict, int — round-trip exact (généralisation)."""
        store = MemoryCache()
        await store.set("llm:k1", {"content": "x", "cached": False}, ttl=60)
        await store.set("llm:k2", 42, ttl=60)
        assert await store.get("llm:k1") == {"content": "x", "cached": False}
        assert await store.get("llm:k2") == 42

    async def test_get_missing_key_returns_none(self):
        """Clé absente → None."""
        store = MemoryCache()
        assert await store.get("rbac:role:unknown") is None

    async def test_expired_ttl_returns_none_and_purges(self):
        """TTL expiré → miss (None) et entrée purgée paresseusement."""
        store = MemoryCache()
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
        store = MemoryCache()
        await store.set("rbac:role:user-1", "operator", ttl=None)
        key = "rbac:role:user-1"
        _, stored_expiry = store._store[key]
        assert stored_expiry == float("inf")
        assert await store.get(key) == "operator"

    async def test_delete_existing_key(self):
        """delete retire la clé et retourne True."""
        store = MemoryCache()
        await store.set("rbac:role:user-1", "admin", ttl=300)
        assert await store.delete("rbac:role:user-1") is True
        assert await store.get("rbac:role:user-1") is None

    async def test_delete_missing_key_returns_false(self):
        """delete d'une clé absente → False."""
        store = MemoryCache()
        assert await store.delete("rbac:role:unknown") is False

    async def test_clear_prefix_removes_matching_keys_only(self):
        """clear_prefix supprime les clés du préfixe, épargne les autres."""
        store = MemoryCache()
        await store.set("rbac:role:user-1", "viewer", ttl=300)
        await store.set("rbac:role:user-2", "admin", ttl=300)
        await store.set("other:key", "value", ttl=300)
        await store.clear_prefix("rbac:role:")
        assert await store.get("rbac:role:user-1") is None
        assert await store.get("rbac:role:user-2") is None
        assert await store.get("other:key") == "value"

    async def test_max_entries_evicts_fifo_without_error(self):
        """AC 4 : au-delà de la borne, éviction FIFO de la plus ancienne."""
        store = MemoryCache(max_entries=2)
        await store.set("k1", "v1", ttl=300)
        await store.set("k2", "v2", ttl=300)
        await store.set("k3", "v3", ttl=300)  # sans erreur
        assert await store.get("k1") is None  # plus ancienne évictionnée
        assert await store.get("k2") == "v2"
        assert await store.get("k3") == "v3"

    async def test_max_entries_purges_expired_before_fifo(self):
        """AC 4 : les expirées sont purgées AVANT l'éviction FIFO."""
        store = MemoryCache(max_entries=2)
        await store.set("k1", "v1", ttl=300)
        await store.set("expired", "x", ttl=1)
        # Force l'expiration de la 2e entrée
        value, expires_at = store._store["expired"]
        store._store["expired"] = (value, expires_at - 10)
        await store.set("k3", "v3", ttl=300)
        # k1 survit : la place a été libérée par la purge de l'expirée
        assert await store.get("k1") == "v1"
        assert await store.get("k3") == "v3"

    async def test_max_entries_reinsert_refreshes_fifo_position(self):
        """Ré-écriture d'une clé existante : position FIFO rafraîchie."""
        store = MemoryCache(max_entries=2)
        await store.set("k1", "v1", ttl=300)
        await store.set("k2", "v2", ttl=300)
        await store.set("k1", "v1-bis", ttl=300)  # ré-écriture, pas d'éviction
        await store.set("k3", "v3", ttl=300)  # évictionne k2 (plus ancienne)
        assert await store.get("k1") == "v1-bis"
        assert await store.get("k2") is None

    async def test_setting_bound_from_settings(self):
        """La borne est résolue depuis settings.cache_memory_max_entries."""
        store = MemoryCache()
        with patch.object(cache_module.settings, "cache_memory_max_entries", 1):
            await store.set("k1", "v1", ttl=300)
            await store.set("k2", "v2", ttl=300)
            assert await store.get("k1") is None
            assert await store.get("k2") == "v2"

    async def test_abc_contract_exists_clear_health_check(self):
        """Contrat ABC CacheManager : exists/clear/health_check + subclassing."""
        store = MemoryCache()
        assert issubclass(MemoryCache, cache_module.CacheManager)
        await store.set("k", "v", ttl=10)
        assert await store.exists("k") is True
        assert await store.exists("missing") is False
        assert await store.clear() is True
        assert await store.get("k") is None
        assert await store.health_check() is True


class TestRedisCache:
    """RedisCache — client mocké, JSON round-trip, fallback mémoire."""

    async def test_get_returns_decoded_string(self):
        """Valeur bytes Redis (JSON) décodée en str."""
        client = MagicMock()
        client.get = AsyncMock(return_value=json.dumps("admin").encode())
        store = RedisCache(client)
        assert await store.get("rbac:role:user-1") == "admin"

    async def test_get_dict_round_trip(self):
        """Valeurs dict : sérialisation JSON round-trip."""
        payload = {"content": "resp", "cached": False}
        client = MagicMock()
        client.get = AsyncMock(return_value=json.dumps(payload).encode())
        store = RedisCache(client)
        assert await store.get("llm:abc") == payload

    async def test_get_legacy_raw_string_still_readable(self):
        """Rétrocompatibilité : valeur str brute (pré-STORY-168) lue telle quelle."""
        client = MagicMock()
        client.get = AsyncMock(return_value=b"admin")  # pas du JSON valide
        store = RedisCache(client)
        assert await store.get("rbac:role:user-1") == "admin"

    async def test_get_missing_key_returns_none(self):
        """Clé absente côté Redis → None."""
        client = MagicMock()
        client.get = AsyncMock(return_value=None)
        store = RedisCache(client)
        assert await store.get("rbac:role:user-1") is None

    async def test_set_uses_native_ttl_and_json(self):
        """set délègue à Redis avec ex=ttl et valeur JSON-sérialisée."""
        client = MagicMock()
        client.set = AsyncMock(return_value=True)
        store = RedisCache(client)
        assert await store.set("rbac:role:user-1", "admin", ttl=300) is True
        client.set.assert_awaited_once_with(
            "rbac:role:user-1", json.dumps("admin"), ex=300
        )

    async def test_delete_calls_redis_and_memory(self):
        """delete supprime côté Redis et purge le fallback mémoire."""
        client = MagicMock()
        client.delete = AsyncMock(return_value=1)
        store = RedisCache(client)
        await store._memory_fallback.set("rbac:role:user-1", "admin", ttl=300)
        assert await store.delete("rbac:role:user-1") is True
        client.delete.assert_awaited_once_with("rbac:role:user-1")
        assert await store._memory_fallback.get("rbac:role:user-1") is None

    async def test_get_failure_falls_back_to_memory(self, caplog):
        """AC 2 : échec Redis get → warning + fallback mémoire transparent."""
        client = MagicMock()
        client.get = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisCache(client)
        await store._memory_fallback.set("rbac:role:user-1", "viewer", ttl=300)
        with caplog.at_level(logging.WARNING, logger="windflow.cache"):
            assert await store.get("rbac:role:user-1") == "viewer"
        assert any("memory fallback" in r.getMessage() for r in caplog.records)

    async def test_set_failure_falls_back_to_memory(self):
        """AC 2 : échec Redis set → fallback mémoire, l'écriture n'échoue jamais."""
        client = MagicMock()
        client.set = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisCache(client)
        assert await store.set("rbac:role:user-1", "operator", ttl=300) is True
        assert await store._memory_fallback.get("rbac:role:user-1") == "operator"

    async def test_delete_failure_falls_back_to_memory(self):
        """AC 2 : échec Redis delete → fallback mémoire sans lever."""
        client = MagicMock()
        client.delete = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisCache(client)
        await store._memory_fallback.set("k", "v", ttl=10)
        assert await store.delete("k") is True

    async def test_degraded_episode_warning_emitted_once(self, caplog):
        """Warning d'épisode dégradé : émis une fois malgré N échecs."""
        client = MagicMock()
        client.get = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisCache(client)
        with caplog.at_level(logging.WARNING, logger="windflow.cache"):
            await store.get("k1")
            await store.get("k2")
            await store.get("k3")
        warnings = [r for r in caplog.records if "memory fallback" in r.getMessage()]
        assert len(warnings) == 1

    async def test_publish_is_best_effort(self):
        """publish best-effort : échec Redis loggé sans lever."""
        client = MagicMock()
        client.publish = AsyncMock(side_effect=ConnectionError("redis down"))
        store = RedisCache(client)
        await store.publish("rbac:role:invalidate", "user-1")  # ne lève pas

    async def test_publish_success(self):
        """Cas nominal : publish délègue au client Redis."""
        client = MagicMock()
        client.publish = AsyncMock(return_value=1)
        store = RedisCache(client)
        await store.publish("rbac:role:invalidate", "user-1")
        client.publish.assert_awaited_once_with("rbac:role:invalidate", "user-1")

    async def test_health_check_ping_ok_and_ko(self):
        """health_check : True si ping OK, False si ping KO (diagnostic)."""
        ok = RedisCache(_fake_redis_client(ping_ok=True))
        assert await ok.health_check() is True
        ko = RedisCache(_fake_redis_client(fail=True))
        assert await ko.health_check() is False

    async def test_clear_scopes_to_managed_prefixes(self):
        """clear ne supprime que les préfixes gérés (jamais FLUSHDB)."""
        client = MagicMock()

        async def fake_scan_iter(match):
            for key in ("other:x", "rbac:role:u1", "llm:h1"):
                if key.startswith(match.rstrip("*")):
                    yield key

        client.scan_iter = fake_scan_iter
        client.delete = AsyncMock(return_value=2)
        store = RedisCache(client)
        assert await store.clear() is True
        # Seuls rbac:/llm: sont ciblés — "other:x" n'est jamais supprimé
        deleted_args = [call.args[0] for call in client.delete.await_args_list]
        flat = [
            key
            for args in deleted_args
            for key in (args if isinstance(args, tuple) else (args,))
        ]
        assert "other:x" not in flat
        assert "rbac:role:u1" in flat

    async def test_exists_uses_redis(self):
        """exists délègue au client Redis."""
        client = MagicMock()
        client.exists = AsyncMock(return_value=1)
        store = RedisCache(client)
        assert await store.exists("k") is True
        client.exists.assert_awaited_once_with("k")


class TestGetCacheFactory:
    """Factory get_cache — sélection du backend (AC 1, 2)."""

    async def test_without_url_returns_memory_and_warns_once(self, caplog):
        """AC 1 : sans URL → MemoryCache + warning de dégradation unique."""
        with patch.object(cache_module.settings, "cache_url", None), patch.object(
            cache_module.settings, "rate_limit_storage_url", None
        ):
            with caplog.at_level(logging.WARNING, logger="windflow.cache"):
                backend = await get_cache()
                assert isinstance(backend, MemoryCache)
                # N appels : le warning n'apparaît qu'une fois
                await get_cache()
                await get_cache()
        warnings = [r for r in caplog.records if "process-local" in r.getMessage()]
        assert len(warnings) == 1

    async def test_cache_url_takes_priority_over_rate_limit_url(self):
        """cache_url prioritaire sur rate_limit_storage_url (résolution unifiée)."""
        client = _fake_redis_client()
        fake_aioredis = _fake_aioredis(client)
        with patch.object(
            cache_module.settings, "cache_url", "redis://cache-priority:6379/1"
        ), patch.object(
            cache_module.settings,
            "rate_limit_storage_url",
            "redis://rate-limit:6379/0",
        ), patch.object(
            cache_module, "aioredis", fake_aioredis
        ):
            backend = await get_cache()
            assert isinstance(backend, RedisCache)
            fake_aioredis.from_url.assert_called_once_with(
                "redis://cache-priority:6379/1"
            )

    async def test_rate_limit_url_used_when_cache_url_absent(self):
        """Fallback de résolution : rate_limit_storage_url seul (comportement RBAC)."""
        client = _fake_redis_client()
        fake_aioredis = _fake_aioredis(client)
        with patch.object(cache_module.settings, "cache_url", None), patch.object(
            cache_module.settings, "rate_limit_storage_url", "redis://rl:6379/0"
        ), patch.object(cache_module, "aioredis", fake_aioredis):
            backend = await get_cache()
            assert isinstance(backend, RedisCache)
            fake_aioredis.from_url.assert_called_once_with("redis://rl:6379/0")

    async def test_unreachable_redis_falls_back_to_memory(self, monkeypatch):
        """URL configurée mais ping KO → fallback mémoire."""
        with patch.object(
            cache_module.settings, "cache_url", "redis://localhost:1/9"
        ), patch.object(
            cache_module.settings, "rate_limit_storage_url", None
        ), patch.object(
            cache_module, "aioredis", _fake_aioredis(_fake_redis_client(fail=True))
        ):
            backend = await get_cache()
        assert isinstance(backend, MemoryCache)

    async def test_factory_is_memoized(self):
        """Résolution paresseuse mémosée : même instance aux appels suivants."""
        first = await get_cache()
        second = await get_cache()
        assert first is second

    async def test_reset_cache_forces_new_instance(self):
        """reset_cache() → nouvelle instance au prochain appel."""
        first = await get_cache()
        reset_cache()
        second = await get_cache()
        assert first is not second

    async def test_shutdown_cache_closes_redis_client_once(self):
        """shutdown_cache : fermeture idempotente du client Redis (T7)."""
        client = _fake_redis_client()  # ping OK → backend Redis retenu
        client.aclose = AsyncMock()
        fake_aioredis = _fake_aioredis(client)
        with patch.object(
            cache_module.settings, "cache_url", "redis://x:6379/1"
        ), patch.object(
            cache_module.settings, "rate_limit_storage_url", None
        ), patch.object(
            cache_module, "aioredis", fake_aioredis
        ):
            await get_cache()
            await shutdown_cache()
            await shutdown_cache()  # idempotente
        client.aclose.assert_awaited_once()

    async def test_shutdown_cache_noop_in_memory(self):
        """shutdown_cache : no-op en mode mémoire (aucune erreur)."""
        with patch.object(cache_module.settings, "cache_url", None), patch.object(
            cache_module.settings, "rate_limit_storage_url", None
        ):
            await get_cache()
            await shutdown_cache()  # ne lève pas


class TestRoleCacheCompatibility:
    """Compatibilité STORY-122.1 — noms publics historiques préservés."""

    def test_aliases_are_unified_classes(self):
        """MemoryRoleCache/RedisRoleCache sont des aliases exacts."""
        assert MemoryRoleCache is MemoryCache
        assert RedisRoleCache is RedisCache
        assert issubclass(RedisRoleCache, cache_module.CacheManager)

    async def test_get_role_cache_returns_unified_singleton(self):
        """get_role_cache() → même instance que get_cache()."""
        unified = await get_cache()
        role_cache = await get_role_cache()
        assert role_cache is unified

    async def test_role_labels_round_trip(self):
        """Libellés de rôle publics : round-trip mémoire ET JSON Redis."""
        for label in ("viewer", "operator", "admin", "super_admin"):
            memory = MemoryCache()
            await memory.set("rbac:role:u", label, ttl=300)
            assert await memory.get("rbac:role:u") == label

            client = MagicMock()
            client.get = AsyncMock(return_value=json.dumps(label).encode())
            redis_store = RedisCache(client)
            assert await redis_store.get("rbac:role:u") == label

    def test_reset_role_cache_aliases_reset_cache(self):
        """reset_role_cache() délègue à reset_cache()."""
        reset_role_cache()
        assert cache_module._cache is None


class TestSecurity:
    """Sécurité (rules 40) — logs sans credentials, valeurs non sensibles."""

    def test_safe_redis_url_masks_credentials(self):
        """_safe_redis_url masque :password@ — 'secret' jamais exposé."""
        masked = _safe_redis_url("redis://:secret@host:6379/1")
        assert "secret" not in masked
        assert masked == "redis://***@host:6379/1"

    def test_safe_redis_url_no_credentials_untouched(self):
        """URL sans credentials : laissée intacte."""
        url = "redis://host:6379/1"
        assert _safe_redis_url(url) == url

    async def test_role_cache_stores_only_public_labels(self):
        """La valeur RBAC cachée est un libellé public, pas un token/secret."""
        store = MemoryCache()
        await store.set("rbac:role:u1", "admin", ttl=300)
        value = await store.get("rbac:role:u1")
        assert value in ("viewer", "operator", "admin", "super_admin")
