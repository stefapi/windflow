"""
Cache des rôles RBAC — implémentations concrètes à TTL (STORY-122.1).

Première implémentation concrète de cache du core (l'ABC ``CacheManager``
de ``core/abstractions.py`` n'avait aucune implémentation applicative),
spécialisée pour le cache des rôles RBAC (spec 08 § Implémentation) :

- ``MemoryRoleCache`` : dict process-local + horloge monotone, purge
  paresseuse des entrées expirées — mode léger sans Redis et tests unitaires.
- ``RedisRoleCache`` : client ``redis.asyncio`` (TTL native via ``ex=``) ;
  en cas d'échec Redis → log warning + fallback transparent vers le
  stockage mémoire interne (résilience, cf. règles 20-architecture-and-api).
- ``get_role_cache()`` : factory singleton à résolution paresseuse — Redis
  si une URL est configurée (``settings.rate_limit_storage_url``) **et**
  joignable, sinon mémoire.

Convention de clés : les rôles sont stockés par l'appelant sous
``rbac:role:{user_id}`` (préfixe ``rbac:`` posé par ``AuthorizationService``,
namespacing Redis inclus) ; les backends ci-dessous restent translucides
(clés utilisées telles quelles) pour rester interchangeables.

Aucune donnée sensible n'est stockée : clé = user_id, valeur = libellé de
rôle public (viewer | operator | admin | super_admin).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Protocol

from ..config import settings

logger = logging.getLogger("windflow.cache")

# Import conditionnel de redis.asyncio (le mode léger n'exige pas Redis)
try:  # pragma: no cover - couvert indirectement selon l'environnement
    import redis.asyncio as aioredis

    REDIS_AVAILABLE: bool = True
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False


class RoleCacheProtocol(Protocol):
    """Interface du cache des rôles RBAC (protocol typing — mock simple en tests)."""

    async def get(self, key: str) -> Optional[str]:
        """Retourne la valeur cachée pour ``key``, ``None`` si absente/expirée."""
        ...

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Stocke ``value`` sous ``key`` pour ``ttl`` secondes (sans expiration si None)."""
        ...

    async def delete(self, key: str) -> bool:
        """Supprime ``key`` du cache. Retourne True si la clé existait."""
        ...

    async def clear_prefix(self, prefix: str) -> None:
        """Supprime toutes les clés commençant par ``prefix``."""
        ...


class MemoryRoleCache:
    """Cache mémoire process-local des rôles (mode léger, tests).

    Chaque entrée du store est ``(valeur, expiration)`` où ``expiration``
    est un timestamp ``time.monotonic()`` — une entrée expirée est un miss
    et est purgée paresseusement au passage (pattern ``_is_cache_valid``
    du ``plugin_registry_service``).

    Sûr en event loop unique (asyncio) : chaque opération s'exécute sans
    ``await`` intermédiaire, les mutations sont donc atomiques (même garde-fou
    que ``MemoryRateLimiter``).
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}

    async def get(self, key: str) -> Optional[str]:
        """Retourne la valeur si elle existe et n'a pas expiré (purge paresseuse)."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() >= expires_at:
            # TTL expiré → miss + purge paresseuse
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Stocke la valeur avec expiration monotone (jamais si ``ttl`` est None)."""
        expires_at = time.monotonic() + ttl if ttl is not None else float("inf")
        self._store[key] = (value, expires_at)
        return True

    async def delete(self, key: str) -> bool:
        """Supprime la clé. Retourne True si elle existait (expirée = inexistante)."""
        return self._store.pop(key, None) is not None

    async def clear_prefix(self, prefix: str) -> None:
        """Supprime toutes les clés commençant par ``prefix``."""
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]

    def reset(self) -> None:
        """Vide tout l'état (utilisé par les tests)."""
        self._store.clear()


class RedisRoleCache:
    """Cache Redis des rôles avec fallback mémoire transparent (résilience).

    Délègue à un client ``redis.asyncio`` (TTL native ``ex=``) ; en cas
    d'échec Redis (connexion perdue, timeout…), l'opération bascule vers
    une instance ``MemoryRoleCache`` interne après un log warning — la
    dégradation n'interrompt jamais le flux d'autorisation (moindre privilège
    garanti par la re-requête SQL en cas de miss).
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        self._memory_fallback = MemoryRoleCache()

    async def get(self, key: str) -> Optional[str]:
        """Retourne la valeur depuis Redis (fallback mémoire sur échec)."""
        try:
            value = await self._client.get(key)
        except Exception as exc:
            logger.warning(
                "RBAC role cache: Redis get failed (%s) — memory fallback", exc
            )
            return await self._memory_fallback.get(key)
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else str(value)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Stocke la valeur dans Redis avec TTL (fallback mémoire sur échec)."""
        try:
            await self._client.set(key, value, ex=ttl)
            return True
        except Exception as exc:
            logger.warning(
                "RBAC role cache: Redis set failed (%s) — memory fallback", exc
            )
            return await self._memory_fallback.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Supprime la clé de Redis (fallback mémoire sur échec)."""
        try:
            deleted = await self._client.delete(key)
            await self._memory_fallback.delete(key)
            return bool(deleted)
        except Exception as exc:
            logger.warning(
                "RBAC role cache: Redis delete failed (%s) — memory fallback", exc
            )
            return await self._memory_fallback.delete(key)

    async def clear_prefix(self, prefix: str) -> None:
        """Supprime toutes les clés Redis commençant par ``prefix`` (scan + delete)."""
        try:
            keys = [key async for key in self._client.scan_iter(match=f"{prefix}*")]
            if keys:
                await self._client.delete(*keys)
        except Exception as exc:
            logger.warning(
                "RBAC role cache: Redis clear_prefix failed (%s) — memory fallback", exc
            )
            await self._memory_fallback.clear_prefix(prefix)

    async def publish(self, channel: str, message: str) -> None:
        """Publie un message sur un canal Redis (best-effort, spec 08 § Invalidation).

        Utilisé pour diffuser l'invalidation du cache des rôles aux autres
        workers (mode standard multi-workers). Un échec de publication est
        loggé sans interrompre le flux — la TTL (300 s) garantit la
        convergence au pire cas.
        """
        try:
            await self._client.publish(channel, message)
        except Exception as exc:
            logger.warning(
                "RBAC role cache: Redis publish failed (%s) — TTL guarantees convergence",
                exc,
            )


# Singleton mémorisé de la factory (résolution paresseuse au premier appel)
_role_cache: Optional[RoleCacheProtocol] = None


async def get_role_cache() -> RoleCacheProtocol:
    """Factory singleton du cache des rôles.

    Choix du backend :
    - Redis si le package ``redis`` est importable, qu'une URL est configurée
      (``settings.rate_limit_storage_url``) **et** que le ``ping`` réussit
      (mode standard multi-workers) ;
    - mémoire sinon (mode léger — cache process-local non partagé).

    La résolution est paresseuse et mémosée : le choix n'est refait qu'après
    un ``reset_role_cache()`` (tests / reconfiguration).

    Returns:
        Instance singleton implémentant ``RoleCacheProtocol``.
    """
    global _role_cache
    if _role_cache is not None:
        return _role_cache

    redis_url = settings.rate_limit_storage_url
    if REDIS_AVAILABLE and redis_url:
        try:
            client = aioredis.from_url(redis_url)
            await client.ping()
            _role_cache = RedisRoleCache(client)
            logger.info("RBAC role cache: backend Redis actif")
            return _role_cache
        except Exception as exc:
            logger.warning(
                "RBAC role cache: Redis indisponible (%s) — fallback mémoire", exc
            )
    else:
        logger.info(
            "RBAC role cache: backend mémoire (mode léger — cache process-local, "
            "non partagé entre workers)"
        )

    _role_cache = MemoryRoleCache()
    return _role_cache


def reset_role_cache() -> None:
    """Réinitialise le singleton de la factory (utilisé par les tests)."""
    global _role_cache
    _role_cache = None
