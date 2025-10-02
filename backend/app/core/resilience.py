"""
Patterns de résilience pour WindFlow.

Implémente Circuit Breaker, Retry Policies, et Health Checks multi-niveau
pour assurer la robustesse du système.
"""

from typing import Optional, Callable, Any, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
from functools import wraps
import time

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """États du Circuit Breaker."""
    CLOSED = "closed"      # Fonctionnement normal
    OPEN = "open"          # Circuit ouvert, requêtes bloquées
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
        half_open_timeout: int = 30
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
            logger.warning(f"Circuit {self.name}: Reopening due to failure in HALF_OPEN")
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
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_state_change": self.last_state_change.isoformat(),
        }


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout: int = 60
):
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
        jitter: bool = True
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
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
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
        **kwargs
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
        last_exception = None

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

        raise last_exception


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (Exception,)
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
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay
    )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await policy.execute(
                func,
                *args,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper

    return decorator


class HealthCheck:
    """
    Health check pour un composant système.

    Permet de surveiller l'état de santé des différents composants
    (database, Redis, services externes, etc.).
    """

    def __init__(
        self,
        name: str,
        check_func: Callable,
        timeout: float = 5.0,
        critical: bool = False
    ):
        """
        Initialise un health check.

        Args:
            name: Nom du composant
            check_func: Fonction async de vérification
            timeout: Timeout en secondes
            critical: Si True, l'échec rend le système UNHEALTHY
        """
        self.name = name
        self.check_func = check_func
        self.timeout = timeout
        self.critical = critical
        self.last_check: Optional[datetime] = None
        self.last_status: HealthStatus = HealthStatus.UNKNOWN
        self.last_error: Optional[str] = None

    async def check(self) -> Dict[str, Any]:
        """
        Exécute le health check.

        Returns:
            Résultat du check avec statut et détails
        """
        start_time = time.time()

        try:
            # Exécuter avec timeout
            result = await asyncio.wait_for(
                self.check_func(),
                timeout=self.timeout
            )

            duration = time.time() - start_time
            self.last_status = HealthStatus.HEALTHY
            self.last_error = None
            self.last_check = datetime.utcnow()

            return {
                "name": self.name,
                "status": self.last_status.value,
                "critical": self.critical,
                "duration_ms": round(duration * 1000, 2),
                "timestamp": self.last_check.isoformat(),
                "details": result if isinstance(result, dict) else {}
            }

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            self.last_status = HealthStatus.UNHEALTHY
            self.last_error = f"Timeout after {self.timeout}s"
            self.last_check = datetime.utcnow()

            logger.error(f"Health check {self.name} timed out")

            return {
                "name": self.name,
                "status": self.last_status.value,
                "critical": self.critical,
                "duration_ms": round(duration * 1000, 2),
                "timestamp": self.last_check.isoformat(),
                "error": self.last_error
            }

        except Exception as e:
            duration = time.time() - start_time
            self.last_status = HealthStatus.UNHEALTHY
            self.last_error = str(e)
            self.last_check = datetime.utcnow()

            logger.error(f"Health check {self.name} failed: {e}")

            return {
                "name": self.name,
                "status": self.last_status.value,
                "critical": self.critical,
                "duration_ms": round(duration * 1000, 2),
                "timestamp": self.last_check.isoformat(),
                "error": self.last_error
            }


class HealthCheckRegistry:
    """
    Registre centralisé des health checks.

    Permet de gérer tous les health checks du système
    et de déterminer l'état global de santé.
    """

    def __init__(self):
        """Initialise le registre."""
        self.checks: Dict[str, HealthCheck] = {}

    def register(self, check: HealthCheck) -> None:
        """
        Enregistre un health check.

        Args:
            check: Health check à enregistrer
        """
        self.checks[check.name] = check
        logger.info(f"Health check registered: {check.name}")

    def unregister(self, name: str) -> None:
        """
        Désenregistre un health check.

        Args:
            name: Nom du check à retirer
        """
        if name in self.checks:
            del self.checks[name]
            logger.info(f"Health check unregistered: {name}")

    async def check_all(self) -> Dict[str, Any]:
        """
        Exécute tous les health checks.

        Returns:
            Résultat global avec statut et détails de chaque check
        """
        results = []

        # Exécuter tous les checks en parallèle
        tasks = [check.check() for check in self.checks.values()]
        check_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in check_results:
            if isinstance(result, Exception):
                logger.error(f"Health check crashed: {result}")
                results.append({
                    "name": "unknown",
                    "status": HealthStatus.UNHEALTHY.value,
                    "error": str(result)
                })
            else:
                results.append(result)

        # Déterminer le statut global
        overall_status = self._determine_overall_status(results)

        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results
        }

    def _determine_overall_status(self, results: List[Dict[str, Any]]) -> HealthStatus:
        """Détermine le statut global depuis les résultats individuels."""
        if not results:
            return HealthStatus.UNKNOWN

        # Si un check critique est UNHEALTHY, tout le système est UNHEALTHY
        for result in results:
            if result.get("critical") and result.get("status") == HealthStatus.UNHEALTHY.value:
                return HealthStatus.UNHEALTHY

        # Si tous les checks sont HEALTHY
        if all(r.get("status") == HealthStatus.HEALTHY.value for r in results):
            return HealthStatus.HEALTHY

        # Si au moins un check est UNHEALTHY (non critique)
        if any(r.get("status") == HealthStatus.UNHEALTHY.value for r in results):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_check(self, name: str) -> Optional[HealthCheck]:
        """Retourne un health check par son nom."""
        return self.checks.get(name)

    def list_checks(self) -> List[str]:
        """Retourne la liste des noms de checks enregistrés."""
        return list(self.checks.keys())


# Instance globale du registre
_health_registry: Optional[HealthCheckRegistry] = None


def get_health_registry() -> HealthCheckRegistry:
    """
    Retourne l'instance globale du registre (singleton).

    Returns:
        Instance du HealthCheckRegistry
    """
    global _health_registry

    if _health_registry is None:
        _health_registry = HealthCheckRegistry()

    return _health_registry
