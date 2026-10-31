"""
Patterns de résilience pour WindFlow.

Implémente Circuit Breaker et Retry Policies pour la robustesse du système.

STORY-250.1 : les classes HealthCheck/HealthCheckRegistry (orphelines,
redondantes avec le health-check des hosts) ont été purgées — le sort du
CircuitBreaker restant est arbitré par STORY-251.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """États du Circuit Breaker."""

    CLOSED = "closed"  # Fonctionnement normal
    OPEN = "open"  # Circuit ouvert, requêtes bloquées
    HALF_OPEN = "half_open"  # Test de récupération


class HealthStatus(str, Enum):
    """Statuts de santé des composants."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitBreaker:
    """
    Implémentation du pattern Circuit Breaker.

    Protège le système contre les défaillances en cascade en
    coupant temporairement les appels à un service défaillant.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        half_open_timeout: int = 30,
    ):
        """
        Initialise le Circuit Breaker.

        Args:
            name: Nom du circuit (pour logging)
            failure_threshold: Nombre d'échecs avant ouverture
            success_threshold: Nombre de succès pour fermer en half-open
            timeout: Durée d'ouverture en secondes
            half_open_timeout: Durée en half-open avant nouvelle tentative
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_timeout = half_open_timeout

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()

    def _should_attempt_call(self) -> bool:
        """Détermine si un appel peut être tenté."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Vérifier si le timeout est écoulé
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout:
                    logger.info(f"Circuit {self.name}: Transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    self.last_state_change = datetime.utcnow()
                    return True
            return False

        # HALF_OPEN: permettre des tentatives limitées
        return True

    def _on_success(self) -> None:
        """Gère un appel réussi."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit {self.name}: Transitioning to CLOSED")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = datetime.utcnow()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _on_failure(self) -> None:
        """Gère un appel échoué."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit {self.name}: Opening due to {self.failure_count} failures"
                )
                self.state = CircuitState.OPEN
                self.last_state_change = datetime.utcnow()

        elif self.state == CircuitState.HALF_OPEN:
            logger.warning(
                f"Circuit {self.name}: Reopening due to failure in HALF_OPEN"
            )
            self.state = CircuitState.OPEN
            self.last_state_change = datetime.utcnow()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Exécute une fonction protégée par le circuit breaker.

        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés

        Returns:
            Résultat de la fonction

        Raises:
            RuntimeError: Si le circuit est ouvert
            Exception: Exception originale de la fonction
        """
        if not self._should_attempt_call():
            if self.last_failure_time is None:
                raise RuntimeError(
                    f"Circuit breaker {self.name} is OPEN. Service unavailable."
                )
            raise RuntimeError(
                f"Circuit breaker {self.name} is OPEN. "
                f"Service unavailable until {self.last_failure_time + timedelta(seconds=self.timeout)}"
            )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            logger.error(f"Circuit {self.name}: Call failed - {e}")
            raise

    def get_state(self) -> Dict[str, Any]:
        """Retourne l'état actuel du circuit."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_state_change": self.last_state_change.isoformat(),
        }


def circuit_breaker(name: str, failure_threshold: int = 5, timeout: int = 60):
    """
    Décorateur pour appliquer un circuit breaker à une fonction.

    Args:
        name: Nom du circuit
        failure_threshold: Nombre d'échecs avant ouverture
        timeout: Durée d'ouverture en secondes

    Example:
        @circuit_breaker("external_api", failure_threshold=3, timeout=30)
        async def call_external_api():
            # Code appelant un service externe
            pass
    """
    cb = CircuitBreaker(name, failure_threshold=failure_threshold, timeout=timeout)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb.call(func, *args, **kwargs)

        return wrapper

    return decorator


class RetryPolicy:
    """
    Politique de retry avec backoff exponentiel.

    Implémente des tentatives automatiques avec délai croissant
    entre chaque tentative.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialise la politique de retry.

        Args:
            max_retries: Nombre maximum de tentatives
            initial_delay: Délai initial en secondes
            max_delay: Délai maximum en secondes
            exponential_base: Base pour le backoff exponentiel
            jitter: Ajouter un jitter aléatoire
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def _calculate_delay(self, attempt: int) -> float:
        """Calcule le délai pour une tentative donnée."""
        delay = min(
            self.initial_delay * (self.exponential_base**attempt), self.max_delay
        )

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random())

        return delay

    async def execute(
        self,
        func: Callable,
        *args,
        retryable_exceptions: tuple = (Exception,),
        **kwargs,
    ) -> Any:
        """
        Exécute une fonction avec retry automatique.

        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels
            retryable_exceptions: Tuple des exceptions à retry
            **kwargs: Arguments nommés

        Returns:
            Résultat de la fonction

        Raises:
            Exception: Dernière exception après épuisement des retries
        """
        last_exception: Optional[BaseException] = None

        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except retryable_exceptions as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries + 1} attempts failed. Last error: {e}"
                    )

        raise last_exception  # type: ignore[misc]


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (Exception,),
):
    """
    Décorateur pour appliquer une politique de retry.

    Args:
        max_retries: Nombre maximum de tentatives
        initial_delay: Délai initial en secondes
        max_delay: Délai maximum en secondes
        retryable_exceptions: Tuple des exceptions à retry

    Example:
        @retry(max_retries=3, initial_delay=2.0)
        async def unstable_operation():
            # Code pouvant échouer
            pass
    """
    policy = RetryPolicy(
        max_retries=max_retries, initial_delay=initial_delay, max_delay=max_delay
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await policy.execute(
                func, *args, retryable_exceptions=retryable_exceptions, **kwargs
            )

        return wrapper

    return decorator
