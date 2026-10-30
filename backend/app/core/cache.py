"""
Cache unifié WindFlow — interface unique get/set/delete + TTL (STORY-168).

Généralisation du socle posé par STORY-122.1 (cache des rôles RBAC) en
interface de cache unique pour tout le backend, concrétisant l'ABC
``CacheManager`` de ``core/abstractions.py`` (décision E4 — ressusciter
le contrat jusqu'ici non consommé) :

- ``MemoryCache`` : dict process-local + horloge monotone, purge
  paresseuse des entrées expirées, **bornée** à
  ``settings.cache_memory_max_entries`` (purge des expirées puis
  éviction FIFO de la plus ancienne insertion — AC 4) — mode léger sans
  Redis et tests unitaires.
- ``RedisCache`` : client ``redis.asyncio`` (TTL native via ``ex=``),
  sérialisation JSON des valeurs (round-trip ``Any``, lecture tolérante
  des valeurs ``str`` brutes legacy STORY-122.1) ; en cas d'échec Redis
  → log warning + fallback transparent vers le stockage mémoire interne
  par opération (résilience, règles 20-architecture-and-api — AC 2).
- ``get_cache()`` : factory singleton à résolution paresseuse — Redis si
  une URL est configurée (``settings.cache_url`` **en priorité**, sinon
  ``settings.rate_limit_storage_url``) **et** joignable, sinon mémoire
  avec **warning unique de dégradation** (``emit_degraded_warning_once``
  — partagé avec le rate limiter, plus aucune dégradation silencieuse).

Consommateurs et conventions de clés (namespacing Redis inclus, les
backends restent translucides) :

- RBAC (``AuthorizationService``) : ``rbac:role:{user_id}`` — valeur =
  libellé de rôle public (viewer | operator | admin | super_admin) ;
- plugin registry : ``registry:index`` — index public du registre ;
- cache LLM : ``llm:{sha256(provider + prompt)}`` — **clé hashée**,
  jamais de prompt/token en clair (règles 40).

Sécurité (rules 40) : aucune donnée sensible en clair dans les clés ou
valeurs ; les URLs Redis ne sont jamais loggées avec leurs credentials
(``_safe_redis_url``, helper mutualisé avec ``core/events.py``).

Compatibilité STORY-122.1 : les noms publics historiques sont conservés
— ``MemoryRoleCache``/``RedisRoleCache`` (aliases), ``get_role_cache()``
(délègue au singleton unifié), ``reset_role_cache()``, ``RoleCacheProtocol``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional, Protocol

from ..config import settings
from .abstractions import CacheManager

logger = logging.getLogger("windflow.cache")

# Import conditionnel de redis.asyncio (le mode léger n'exige pas Redis)
try:  # pragma: no cover - couvert indirectement selon l'environnement
    import redis.asyncio as aioredis

    REDIS_AVAILABLE: bool = True
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]
    REDIS_AVAILABLE = False

# Préfixes de clés gérés par le cache unifié (conventions documentées
# en tête de module) — ``RedisCache.clear()`` ne supprime QUE ces
# préfixes (jamais FLUSHDB : la base Redis peut être partagée avec
# fastapi-limiter ou d'autres services).
CACHE_KEY_PREFIXES: tuple[str, ...] = ("rbac:", "registry:", "llm:")


def _safe_redis_url(url: str) -> str:
    """Masque les credentials d'une URL Redis pour les logs (rules 40).

    Helper mutualisé avec ``core/events.py`` (STORY-168 — une seule
    implémentation du masquage).
    """
    return re.sub(r"://[^@/]+@", "://***@", url)


def resolve_cache_redis_url() -> Optional[str]:
    """Résout l'URL Redis du cache unifié (détection partagée).

    ``settings.cache_url`` est prioritaire (mode standard STORY-162) ;
    à défaut ``settings.rate_limit_storage_url`` — ce qui conserve le
    comportement RBAC historique quand seul ce setting est posé.

    Returns:
        URL Redis configurée, ou ``None`` (mode léger mémoire).
    """
    return settings.cache_url or settings.rate_limit_storage_url


def _encode_value(value: Any) -> str:
    """Sérialise une valeur pour Redis (JSON — round-trip ``Any``)."""
    return json.dumps(value)


def _decode_value(raw: Any) -> Any:
    """Désérialise une valeur Redis (JSON), tolérante au legacy.

    Les valeurs écrites par ``RedisRoleCache`` avant STORY-168 étaient
    des ``str`` brutes (non JSON) : une ``str`` non parsable en JSON est
    retournée telle quelle (rétrocompatibilité déploiement).
    """
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return str(raw)


class CacheProtocol(Protocol):
    """Interface du cache unifié (protocol typing — mock simple en tests)."""

    async def get(self, key: str) -> Optional[Any]:
        """Retourne la valeur cachée pour ``key``, ``None`` si absente/expirée."""
        ...

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Stocke ``value`` sous ``key`` pour ``ttl`` secondes (sans expiration si None)."""
        ...

    async def delete(self, key: str) -> bool:
        """Supprime ``key`` du cache. Retourne True si la clé existait."""
        ...

    async def clear_prefix(self, prefix: str) -> None:
        """Supprime toutes les clés commençant par ``prefix``."""
        ...


class RoleCacheProtocol(Protocol):
    """Interface historique du cache des rôles RBAC (STORY-122.1 — conservée).

    Toute instance de ``CacheProtocol`` la satisfait structurellement
    (les implémentations unifiées acceptent ``Any``).
    """

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


class MemoryCache(CacheManager):
    """Cache mémoire process-local borné (mode léger, tests).

    Chaque entrée du store est ``(valeur, expiration)`` où ``expiration``
    est un timestamp ``time.monotonic()`` — une entrée expirée est un miss
    et est purgée paresseusement au passage.

    Borne mémoire (AC 4) : ``max_entries`` (défaut
    ``settings.cache_memory_max_entries``, résolu paresseusement pour
    rester sensible à la reconfiguration en tests). Au-delà de la borne,
    les entrées expirées sont d'abord purgées, puis la plus ancienne
    insertion est évictionnée (FIFO — politique d'éviction simple).

    Sûr en event loop unique (asyncio) : chaque opération s'exécute sans
    ``await`` intermédiaire, les mutations sont donc atomiques (même garde-fou
    que ``MemoryRateLimiter``).
    """

    def __init__(self, max_entries: Optional[int] = None) -> None:
        """Initialise le store (borne explicite en override du setting)."""
        self._store: dict[str, tuple[Any, float]] = {}
        self._max_entries_override = max_entries

    @property
    def _max_entries(self) -> int:
        """Borne effective : override constructeur sinon setting (résolution paresseuse)."""
        if self._max_entries_override is not None:
            return self._max_entries_override
        return settings.cache_memory_max_entries

    def _purge_expired(self) -> None:
        """Purge globale des entrées expirées (garde-fou éviction)."""
        now = time.monotonic()
        expired = [
            key for key, (_, expires_at) in self._store.items() if now >= expires_at
        ]
        for key in expired:
            del self._store[key]

    def _evict_to_fit(self) -> None:
        """Libère une place : purge des expirées puis éviction FIFO."""
        self._purge_expired()
        while len(self._store) >= self._max_entries:
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]

    async def get(self, key: str) -> Optional[Any]:
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

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Stocke la valeur avec expiration monotone (jamais si ``ttl`` est None)."""
        expires_at = time.monotonic() + ttl if ttl is not None else float("inf")
        if key in self._store:
            # Ré-écriture : rafraîchit la position FIFO (dernière insertion)
            del self._store[key]
        else:
            self._evict_to_fit()
        self._store[key] = (value, expires_at)
        return True

    async def delete(self, key: str) -> bool:
        """Supprime la clé. Retourne True si elle existait (expirée = inexistante)."""
        return self._store.pop(key, None) is not None

    async def clear(self) -> bool:
        """Vide tout le store."""
        self._store.clear()
        return True

    async def exists(self, key: str) -> bool:
        """Indique si la clé existe et n'a pas expiré."""
        return await self.get(key) is not None

    async def health_check(self) -> bool:
        """Le cache mémoire est toujours disponible."""
        return True

    async def clear_prefix(self, prefix: str) -> None:
        """Supprime toutes les clés commençant par ``prefix``."""
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]

    def reset(self) -> None:
        """Vide tout l'état (utilisé par les tests)."""
        self._store.clear()


class RedisCache(CacheManager):
    """Cache Redis avec fallback mémoire transparent (résilience — AC 2).

    Délègue à un client ``redis.asyncio`` (TTL native ``ex=``) avec
    sérialisation JSON des valeurs ; en cas d'échec Redis (connexion
    perdue, timeout…), l'opération bascule vers une instance
    ``MemoryCache`` interne après un log warning — la dégradation
    n'interrompt jamais l'appelant (le moindre privilège RBAC reste
    garanti par la re-requête SQL en cas de miss).
    """

    def __init__(self, client: Any) -> None:
        """Initialise le cache avec un client ``redis.asyncio`` connecté."""
        self._client = client
        self._memory_fallback = MemoryCache()
        # Flag « un warning par épisode dégradé » : armé au premier échec
        # Redis, désarmé dès qu'une opération réussit (retour à la normale).
        self._episode_warned: bool = False

    def _warn_degraded(self, operation: str, exc: Exception) -> None:
        """Loggue l'épisode dégradé en WARNING une seule fois (puis DEBUG)."""
        if self._episode_warned:
            logger.debug(
                "Cache: Redis %s failed (%s) — memory fallback", operation, exc
            )
            return
        self._episode_warned = True
        logger.warning(
            "Cache: Redis %s failed (%s) — memory fallback (degraded episode)",
            operation,
            exc,
        )

    async def _delete_prefix_redis(self, prefix: str) -> None:
        """Supprime côté Redis toutes les clés du préfixe (SCAN + DELETE)."""
        keys = [key async for key in self._client.scan_iter(match=f"{prefix}*")]
        if keys:
            await self._client.delete(*keys)

    async def get(self, key: str) -> Optional[Any]:
        """Retourne la valeur depuis Redis (fallback mémoire sur échec)."""
        try:
            raw = await self._client.get(key)
        except Exception as exc:
            self._warn_degraded("get", exc)
            return await self._memory_fallback.get(key)
        self._episode_warned = False  # Redis répond : fin d'épisode dégradé
        if raw is None:
            return None
        return _decode_value(raw)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Stocke la valeur dans Redis avec TTL (fallback mémoire sur échec)."""
        try:
            await self._client.set(key, _encode_value(value), ex=ttl)
            self._episode_warned = False
            return True
        except Exception as exc:
            self._warn_degraded("set", exc)
            return await self._memory_fallback.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Supprime la clé de Redis (fallback mémoire sur échec)."""
        try:
            deleted = await self._client.delete(key)
            await self._memory_fallback.delete(key)
            self._episode_warned = False
            return bool(deleted)
        except Exception as exc:
            self._warn_degraded("delete", exc)
            return await self._memory_fallback.delete(key)

    async def clear(self) -> bool:
        """Vide les clés du cache unifié côté Redis (préfixes gérés uniquement).

        Jamais ``FLUSHDB`` : la base Redis peut être partagée avec
        fastapi-limiter ou d'autres services — seuls les préfixes
        ``rbac:`` / ``registry:`` / ``llm:`` appartiennent au cache.
        """
        try:
            for prefix in CACHE_KEY_PREFIXES:
                await self._delete_prefix_redis(prefix)
            return True
        except Exception as exc:
            logger.warning("Cache: Redis clear failed (%s) — memory fallback", exc)
            return await self._memory_fallback.clear()

    async def exists(self, key: str) -> bool:
        """Indique si la clé existe côté Redis (fallback mémoire sur échec)."""
        try:
            return bool(await self._client.exists(key))
        except Exception as exc:
            logger.warning("Cache: Redis exists failed (%s) — memory fallback", exc)
            return await self._memory_fallback.exists(key)

    async def health_check(self) -> bool:
        """Vérifie la santé du backend via ``ping`` (sans fallback — diagnostic)."""
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def clear_prefix(self, prefix: str) -> None:
        """Supprime toutes les clés Redis commençant par ``prefix`` (fallback mémoire)."""
        try:
            await self._delete_prefix_redis(prefix)
        except Exception as exc:
            logger.warning(
                "Cache: Redis clear_prefix failed (%s) — memory fallback", exc
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
                "Cache: Redis publish failed (%s) — TTL guarantees convergence",
                exc,
            )

    async def close(self) -> None:
        """Ferme le client Redis (``aclose`` redis-py ≥5, fallback ``close``)."""
        closer = getattr(self._client, "aclose", None) or getattr(
            self._client, "close", None
        )
        if closer is not None:
            await closer()


# ---------------------------------------------------------------------------
# Warning unique de dégradation (partagé cache unifié + rate limiter —
# STORY-168 : une seule implémentation, plus de double bookkeeping)
# ---------------------------------------------------------------------------

#: Flag « warning unique » — le module peut être consommé avant le lifespan.
_degraded_warning_emitted: bool = False


def emit_degraded_warning_once() -> None:
    """Émet une seule fois le warning du mode dégradé mémoire process-local.

    Partagé par le cache unifié (``get_cache``) et le rate limiter
    (STORY-102) : quel que soit le consommateur qui le déclenche, le
    warning n'apparaît qu'une fois par process (AC 1).
    """
    global _degraded_warning_emitted
    if _degraded_warning_emitted:
        return
    _degraded_warning_emitted = True
    logger.warning(
        "Cache/rate-limiting actifs en mode mémoire process-local (aucune URL "
        "Redis configurée : CACHE_URL / RATE_LIMIT_STORAGE_URL) — les entrées "
        "ne sont PAS partagées entre workers ; définir CACHE_URL=redis://... "
        "pour un cache distribué"
    )


# ---------------------------------------------------------------------------
# Factory singleton du cache unifié
# ---------------------------------------------------------------------------

# Singleton mémorisé de la factory (résolution paresseuse au premier appel)
_cache: Optional[CacheProtocol] = None


async def get_cache() -> CacheProtocol:
    """Factory singleton du cache unifié.

    Choix du backend :
    - Redis si le package ``redis`` est importable, qu'une URL est
      configurée (``settings.cache_url`` en priorité, sinon
      ``settings.rate_limit_storage_url``) **et** que le ``ping`` réussit
      (mode standard multi-workers) ;
    - mémoire sinon (mode léger — cache process-local non partagé,
      warning unique de dégradation).

    La résolution est paresseuse et mémosée : le choix n'est refait qu'après
    un ``reset_cache()`` (tests / reconfiguration).

    Returns:
        Instance singleton implémentant ``CacheProtocol``.
    """
    global _cache
    if _cache is not None:
        return _cache

    redis_url = resolve_cache_redis_url()
    if REDIS_AVAILABLE and redis_url:
        try:
            client = aioredis.from_url(redis_url)
            await client.ping()
            _cache = RedisCache(client)
            logger.info(
                "Cache: backend Redis actif (mode standard, %s)",
                _safe_redis_url(redis_url),
            )
            return _cache
        except Exception as exc:
            logger.warning("Cache: Redis indisponible (%s) — fallback mémoire", exc)
    else:
        emit_degraded_warning_once()
        logger.info(
            "Cache: backend mémoire (mode léger — cache process-local, "
            "non partagé entre workers)"
        )

    _cache = MemoryCache()
    return _cache


def reset_cache() -> None:
    """Réinitialise le singleton de la factory (utilisé par les tests).

    Ne ferme pas le client Redis — la fermeture réseau est du ressort de
    ``shutdown_cache()``.
    """
    global _cache
    _cache = None


async def shutdown_cache() -> None:
    """Ferme le client Redis du cache unifié (cycle de vie — STORY-168 T7).

    Idempotente : les appels suivants sont des no-ops (singleton remis à
    ``None`` au premier appel). No-op en mode mémoire. Appelée par le
    shutdown du lifespan à côté de ``FastAPILimiter.close()``.
    """
    global _cache
    instance = _cache
    _cache = None
    if isinstance(instance, RedisCache):
        try:
            await instance.close()
            logger.info("Cache: client Redis fermé")
        except Exception as exc:
            logger.warning("Cache: erreur à la fermeture du client Redis (%s)", exc)


# ---------------------------------------------------------------------------
# Compatibilité STORY-122.1 — noms publics historiques du cache des rôles
# (importés par ~30 fichiers de tests et authorization_service.py)
# ---------------------------------------------------------------------------

#: Aliases historiques — le cache des rôles EST le cache unifié.
MemoryRoleCache = MemoryCache
RedisRoleCache = RedisCache


async def get_role_cache() -> RoleCacheProtocol:
    """Factory historique du cache des rôles — délègue au singleton unifié.

    Conservée pour ``AuthorizationService`` et les tests STORY-122.x :
    retourne la même instance que ``get_cache()`` (clés ``rbac:role:*``).
    """
    return await get_cache()  # type: ignore[return-value]


def reset_role_cache() -> None:
    """Réinitialise le singleton (alias historique de ``reset_cache``)."""
    reset_cache()
