"""
Rate limiting utilities for WindFlow API.

Trois modes selon la configuration (plus aucune dégradation silencieuse) :
- Redis distribué : si ``RATE_LIMIT_ENABLED=true`` **et** ``RATE_LIMIT_STORAGE_URL``
  configuré → fastapi-limiter (comptage partagé entre workers).
- Mémoire process-local : si ``RATE_LIMIT_ENABLED=true`` sans URL → limiteur
  mémoire à fenêtre glissante (compteur NON partagé entre workers — warning
  unique émis au premier usage).
- Désactivé : si ``RATE_LIMIT_ENABLED=false`` → no-op explicite (loggé une fois).

La façade ``conditional_rate_limiter(times, seconds)`` garde une signature
inchangée pour les ~110 call-sites existants.
"""

import logging
import time
from collections import deque
from typing import Callable

from fastapi import Request
from fastapi_limiter.depends import RateLimiter

from ..config import settings
from .exceptions import RateLimitError

logger = logging.getLogger("windflow.rate_limit")

# Intervalle (secondes) entre deux purges globales des fenêtres expirées
# (amortisé : appelé depuis check(), au plus une fois par intervalle).
MEMORY_LIMITER_PURGE_INTERVAL: int = 300


class MemoryRateLimiter:
    """
    Limiteur mémoire process-local à fenêtre glissante.

    Chaque clé (ex. ``"{ip}:{path}"``) possède une deque de timestamps
    monotones ; un hit est autorisé si moins de ``times`` timestamps sont
    dans la fenêtre des ``seconds`` dernières secondes.

    Notes :
    - **Process-local** : les compteurs ne sont PAS partagés entre workers
      (mode léger sans Redis) — le warning de démarrage le mentionne.
    - Sûr en event loop unique (asyncio) : chaque ``check()`` s'exécute sans
      ``await`` intermédiaire, les mutations sont donc atomiques.
    - Purge des timestamps expirés à chaque ``check()`` + purge globale
      périodique des clés vides (garde-fou fuite mémoire).
    """

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = {}
        self._last_purge: float = time.monotonic()

    def check(self, key: str, times: int, seconds: float) -> bool:
        """
        Enregistre un hit pour ``key`` et indique s'il est autorisé.

        Args:
            key: Identifiant du compteur (ex. "1.2.3.4:/api/v1/auth/login").
            times: Nombre maximum de hits dans la fenêtre.
            seconds: Taille de la fenêtre glissante en secondes.

        Returns:
            True si le hit est autorisé, False si le quota est dépassé.
        """
        now = time.monotonic()
        self._maybe_purge(now)

        window = self._windows.get(key)
        if window is None:
            window = deque()
            self._windows[key] = window

        # Purge des timestamps expirés pour cette clé
        cutoff = now - seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if not window:
            del self._windows[key]
            window = deque()
            self._windows[key] = window

        if len(window) >= times:
            return False

        window.append(now)
        return True

    def purge_expired(self, max_age: float = 600.0) -> None:
        """
        Purge globale : supprime les timestamps plus vieux que ``max_age``
        et évite les clés à deque vide (garde-fou fuite mémoire sur les
        clés à usage unique).
        """
        cutoff = time.monotonic() - max_age
        empty_keys: list[str] = []
        for key, window in self._windows.items():
            while window and window[0] <= cutoff:
                window.popleft()
            if not window:
                empty_keys.append(key)
        for key in empty_keys:
            del self._windows[key]

    def _maybe_purge(self, now: float) -> None:
        """Déclenche la purge globale au plus une fois par intervalle."""
        if now - self._last_purge >= MEMORY_LIMITER_PURGE_INTERVAL:
            self._last_purge = now
            self.purge_expired()

    def reset(self) -> None:
        """Vide tout l'état (utilisé par les tests)."""
        self._windows.clear()
        self._last_purge = time.monotonic()


# Instance module-level partagée par toutes les dépendances mémoire
# (cohérent avec le compteur global de fastapi-limiter en mode Redis).
_memory_limiter = MemoryRateLimiter()

# Flags « warning unique » (le module peut être consommé avant le lifespan,
# les décorateurs s'exécutant à l'import des routers).
_memory_warning_emitted: bool = False
_disabled_info_emitted: bool = False


def _emit_memory_warning_once() -> None:
    """Émet une seule fois le warning du mode mémoire process-local."""
    global _memory_warning_emitted
    if _memory_warning_emitted:
        return
    _memory_warning_emitted = True
    logger.warning(
        "Rate limiting actif en mode mémoire process-local (RATE_LIMIT_STORAGE_URL "
        "absent) — les compteurs ne sont PAS partagés entre workers ; définir "
        "RATE_LIMIT_STORAGE_URL=redis://... pour un comptage distribué"
    )


def _emit_disabled_info_once() -> None:
    """Émet une seule fois le log explicite du mode désactivé."""
    global _disabled_info_emitted
    if _disabled_info_emitted:
        return
    _disabled_info_emitted = True
    logger.info(
        "Rate limiting désactivé (RATE_LIMIT_ENABLED=false) — choix explicite "
        "de configuration"
    )


def conditional_rate_limiter(times: int, seconds: int) -> Callable:
    """
    Create a conditional rate limiter dependency.

    Trois modes (plus de no-op silencieux) :
    1. Redis configuré (enabled + URL) → ``RateLimiter`` fastapi-limiter
       (comptage distribué, inchangé).
    2. Enabled sans URL → dépendance mémoire à fenêtre glissante
       (process-local, warning unique au premier usage).
    3. Disabled → no-op explicite (loggé une fois).

    Args:
        times: Number of requests allowed
        seconds: Time window in seconds

    Returns:
        RateLimiter instance (Redis), memory dependency ou no-op function

    Example:
        @router.get("/", dependencies=[Depends(conditional_rate_limiter(30, 60))])
        async def endpoint():
            ...
    """
    if settings.rate_limit_enabled and settings.rate_limit_storage_url:
        # Mode 1 : Redis distribué — chemin strictement inchangé
        return RateLimiter(times=times, seconds=seconds)

    if settings.rate_limit_enabled:
        # Mode 2 : fallback mémoire process-local — effectif sans Redis
        _emit_memory_warning_once()

        async def memory_limiter(request: Request) -> None:
            """Limiteur mémoire : 429 au-delà du quota dans la fenêtre."""
            client_host = request.client.host if request.client else "unknown"
            key = f"{client_host}:{request.url.path}"
            if not _memory_limiter.check(key, times, seconds):
                # STORY-127 : 429 typé — Retry-After transporté via headers
                raise RateLimitError(
                    "Too many requests",
                    headers={"Retry-After": str(seconds)},
                )

        return memory_limiter

    # Mode 3 : désactivé explicitement
    _emit_disabled_info_once()

    async def no_op_limiter(request: Request):
        """No-op rate limiter when rate limiting is disabled (choix explicite)."""

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
