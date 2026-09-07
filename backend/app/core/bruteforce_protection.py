"""
Protection brute-force du login — compteur d'échecs par username (STORY-104 / P0-5).

Distinction des deux couches de protection (elles coexistent, spec 07-authentification.md) :
- **Volumétrique par IP** (STORY-102, ``core/rate_limit.py``) : limite le nombre
  de requêtes par IP (ex. 5/min sur ``/auth/login``) — ce module ne la remplace pas.
- **Identité par username** (ce module) : compte les échecs d'authentification pour
  un même username normalisé sur une fenêtre glissante et arme un blocage
  temporaire — un attaquant distribué sur plusieurs IP déclenche quand même le
  blocage (le compteur est indexé par username, pas par IP seule).

Stockage — même décision de stockage que STORY-102, sans double implémentation
divergente :
- **Redis** quand un client partagé est disponible (``FastAPILimiter.redis``,
  initialisé au lifespan depuis ``RATE_LIMIT_STORAGE_URL``) — comptage partagé
  entre workers ;
- **Mémoire process-local sinon** (mode léger) — NON partagé entre workers.

Sûreté : aucune donnée sensible n'est stockée — username normalisé + timestamps
uniquement (jamais le mot de passe, jamais d'IP dans les clés ; l'IP est loggée
en amont par l'endpoint).
"""

import logging
import math
import time
from collections import deque
from typing import Any, Optional

from ..config import settings

logger = logging.getLogger("windflow.bruteforce")

# Intervalle (secondes) entre deux purges globales mémoire (amorti : appelé
# depuis register_failure(), au plus une fois par intervalle).
BRUTEFORCE_PURGE_INTERVAL: int = 300


def _monotonic() -> float:
    """Horloge monotone (branche mémoire) — wrapper patchable pour les tests."""
    return time.monotonic()


def _wall() -> float:
    """Horloge murale epoch (scores Redis) — wrapper patchable pour les tests."""
    return time.time()


def normalize_username(username: str) -> str:
    """
    Normalise un username pour la clé de compteur (anti-bypass casse/espaces).

    Le lookup DB du login reste inchangé : seule la clé du store est normalisée.
    """
    return username.strip().lower()


class BruteforceProtector:
    """
    Compteur d'échecs de login par username avec blocage temporaire.

    - Fenêtre glissante ``window_seconds`` : seuls les échecs récents comptent.
    - Au ``max_attempts``-ième échec dans la fenêtre → blocage ``lockout_seconds``.
    - ``reset()`` est appelé par l'endpoint après un login réussi (spec 07).

    Notes :
    - **Branche mémoire process-local** : les compteurs ne sont PAS partagés
      entre workers (mode léger sans Redis — parité ``MemoryRateLimiter``).
    - Sûr en event loop unique (asyncio) : chaque branche mémoire s'exécute
      sans ``await`` intermédiaire.
    - Aucune donnée sensible : username normalisé + timestamps uniquement.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        lockout_seconds: int = 300,
        window_seconds: int = 600,
    ) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self.window_seconds = window_seconds
        # État mémoire (mode léger, process-local)
        self._failures: dict[str, deque[float]] = {}
        self._lockout_until: dict[str, float] = {}
        self._last_purge: float = _monotonic()

    # ------------------------------------------------------------------ #
    # Clés Redis                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fail_key(username: str) -> str:
        """Clé du sorted set des échecs (score = timestamp epoch)."""
        return f"wf:bf:fail:{username}"

    @staticmethod
    def _lock_key(username: str) -> str:
        """Clé du blocage (string avec TTL = lockout_seconds)."""
        return f"wf:bf:lock:{username}"

    def _redis(self) -> Optional[Any]:
        """
        Retourne le client Redis partagé (``FastAPILimiter.redis``, initialisé
        au lifespan par STORY-102 depuis ``rate_limit_storage_url``) si le
        module est initialisé, sinon ``None`` (→ stratégie mémoire).
        """
        from fastapi_limiter import FastAPILimiter

        return FastAPILimiter.redis

    # ------------------------------------------------------------------ #
    # API publique                                                        #
    # ------------------------------------------------------------------ #

    async def is_locked_out(self, username: str) -> tuple[bool, int]:
        """
        Indique si le username est bloqué et la durée restante (secondes).

        Returns:
            ``(True, retry_after)`` si bloqué, ``(False, 0)`` sinon.
        """
        key = normalize_username(username)
        redis = self._redis()
        if redis is not None:
            ttl = await redis.ttl(self._lock_key(key))
            if ttl > 0:
                return (True, int(ttl))
            return (False, 0)

        now = _monotonic()
        until = self._lockout_until.get(key)
        if until is not None:
            if until > now:
                return (True, math.ceil(until - now))
            # Blocage expiré : purge de l'entrée
            del self._lockout_until[key]
        return (False, 0)

    async def register_failure(self, username: str) -> int:
        """
        Enregistre un échec de login et retourne le nombre d'échecs dans la
        fenêtre. Au seuil ``max_attempts`` : arme le blocage et vide le compteur.
        """
        key = normalize_username(username)
        redis = self._redis()
        if redis is not None:
            return await self._register_failure_redis(redis, key)
        return self._register_failure_memory(key)

    async def reset(self, username: str) -> None:
        """Supprime échecs + blocage du username (login réussi — spec 07)."""
        key = normalize_username(username)
        redis = self._redis()
        if redis is not None:
            await redis.delete(self._fail_key(key), self._lock_key(key))
            return
        self._failures.pop(key, None)
        self._lockout_until.pop(key, None)

    # ------------------------------------------------------------------ #
    # Branche Redis                                                       #
    # ------------------------------------------------------------------ #

    async def _register_failure_redis(self, redis: Any, key: str) -> int:
        fail_key = self._fail_key(key)
        lock_key = self._lock_key(key)
        now = _wall()
        # Fenêtre glissante : purge des scores hors fenêtre, ajout, GC de la clé
        await redis.zremrangebyscore(fail_key, 0, now - self.window_seconds)
        await redis.zadd(fail_key, {str(now): now})
        await redis.expire(fail_key, self.window_seconds)
        count = int(await redis.zcard(fail_key))
        if count >= self.max_attempts:
            await redis.setex(lock_key, self.lockout_seconds, "1")
            await redis.delete(fail_key)
        return count

    # ------------------------------------------------------------------ #
    # Branche mémoire                                                     #
    # ------------------------------------------------------------------ #

    def _register_failure_memory(self, key: str) -> int:
        now = _monotonic()
        self._maybe_purge(now)

        failures = self._failures.get(key)
        if failures is None:
            failures = deque()
            self._failures[key] = failures

        # Fenêtre glissante : purge des timestamps expirés
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()

        failures.append(now)
        count = len(failures)
        if count >= self.max_attempts:
            # Blocage armé : il remplace le compteur (deque vidée)
            self._lockout_until[key] = now + self.lockout_seconds
            del self._failures[key]
        return count

    def purge_expired(self) -> None:
        """Purge mémoire : deques vides/périmées et lockouts expirés."""
        now = _monotonic()
        stale_failures = [
            key
            for key, timestamps in self._failures.items()
            if not timestamps or timestamps[-1] <= now - self.window_seconds
        ]
        for key in stale_failures:
            del self._failures[key]
        expired_locks = [
            key for key, until in self._lockout_until.items() if until <= now
        ]
        for key in expired_locks:
            del self._lockout_until[key]

    def _maybe_purge(self, now: float) -> None:
        """Déclenche la purge globale au plus une fois par intervalle."""
        if now - self._last_purge >= BRUTEFORCE_PURGE_INTERVAL:
            self._last_purge = now
            self.purge_expired()

    def reset_all(self) -> None:
        """Vide tout l'état mémoire (utilisé par les tests)."""
        self._failures.clear()
        self._lockout_until.clear()
        self._last_purge = _monotonic()


# Singleton module-level consommé par l'endpoint (paramètres des settings).
# Les tests unitaires instancient directement la classe avec des paramètres
# réduits ; les tests d'intégration patchent les attributs du singleton.
bruteforce_protector = BruteforceProtector(
    max_attempts=settings.auth_max_attempts,
    lockout_seconds=settings.auth_lockout_seconds,
    window_seconds=settings.auth_attempt_window_seconds,
)
