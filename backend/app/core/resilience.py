"""
Patterns de résilience pour WindFlow.

Implémente Circuit Breaker et Retry Policies pour la robustesse du système.

STORY-251 : le :class:`CircuitBreaker` est **câblé** sur les appels
externes (démon Docker via les WorkloadAdapters ``docker_engine``,
registre de plugins ``plugin_registry``, exécutions SSH ``ssh:{host_id}``)
à travers le :class:`CircuitBreakerRegistry` — seuils configurés via
les settings ``circuit_breaker_*``. Le retry des déploiements reste
porté par ``DeploymentOrchestrator`` : le breaker coupe sans re-tenir
(aucune duplication, plan §2.G).

Le décorateur générique :func:`retry` / :class:`RetryPolicy` est
conservé tel quel (utilitaire non câblé).
"""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

from ..config import settings
from .exceptions import CircuitBreakerOpenError
from .metrics import record_circuit_failure, record_circuit_state

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """États du Circuit Breaker."""

    CLOSED = "closed"  # Fonctionnement normal
    OPEN = "open"  # Circuit ouvert, requêtes bloquées
    HALF_OPEN = "half_open"  # Test de récupération


#: Valeur exposée par la Gauge ``windflow_circuit_breaker_state`` :
#: 0 = closed, 1 = half_open, 2 = open (sémantique STORY-251 D7).
_STATE_METRIC_VALUES: Dict[CircuitState, int] = {
    CircuitState.CLOSED: 0,
    CircuitState.HALF_OPEN: 1,
    CircuitState.OPEN: 2,
}


class CircuitBreaker:
    """
    Implémentation du pattern Circuit Breaker.

    Protège le système contre les défaillances en cascade en coupant
    temporairement les appels à un service défaillant (spec 04
    § Résilience et fiabilité).

    Cycle de vie :

    - CLOSED : comptage des échecs consécutifs ;
    - OPEN après ``failure_threshold`` échecs — les appels suivants
      sont rejetés **immédiatement, sans tentative réseau**
      (:class:`~app.core.exceptions.CircuitBreakerOpenError`) ;
    - HALF_OPEN après ``timeout`` secondes — une sonde est autorisée ;
    - CLOSED après ``success_threshold`` succès consécutifs en
      half-open (retour OPEN au premier échec).

    Concurrence (STORY-251 R1) : les transitions d'état et les
    compteurs sont protégés par un :class:`asyncio.Lock`. Le verrou
    couvre chaque section critique (admission, report de succès ou
    d'échec) mais **pas** l'exécution de la fonction protégée — le
    breaker ne sérialise pas les appels réseau concurrents.

    Sécurité (rules 40) : les logs ne portent jamais le message d'une
    exception — uniquement ``type(exc).__name__`` (les commandes/stderr
    peuvent contenir du contexte sensible).

    Args:
        name: Nom du circuit — sert de label Prometheus ; nom statique
            (``docker_engine``, ``plugin_registry``) ou ``ssh:{host_id}``
            (UUID), jamais de hostname libre (cardinalité bornée, rules 45).
        failure_threshold: Nombre d'échecs consécutifs avant ouverture.
        success_threshold: Nombre de succès en half-open avant fermeture.
        timeout: Durée d'ouverture (secondes) avant qu'une sonde
            half-open soit autorisée.
        half_open_timeout: Réservé (conservé pour compatibilité avec
            le socle historique) — la sonde half-open est autorisée
            dès ``timeout`` écoulé.
        clock: Horloge injectable (tests : transition half-open sans
            sleep réel) ; défaut UTC aware.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60,
        half_open_timeout: float = 30,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_timeout = half_open_timeout
        self._clock: Callable[[], datetime] = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = self._clock()
        self._lock = asyncio.Lock()

    # ─── Transitions internes (appelées sous lock) ────────────

    def _set_state(self, new_state: CircuitState) -> None:
        """Change l'état si nécessaire (log + métrique sur transition)."""
        old = self.state
        if old is new_state:
            return
        self.state = new_state
        self.last_state_change = self._clock()
        self._notify_transition(old, new_state)

    def _notify_transition(self, old: CircuitState, new: CircuitState) -> None:
        """Log structuré + métrique d'une transition (AC 3).

        Le correlation_id vient du contextvar (STORY-251 D8) quand il
        est disponible — ``None`` hors requête HTTP (exécutions
        scheduler, hypothèse H3). Import paresseux : ``core/`` reste
        framework-agnostic (rules 55).
        """
        correlation_id: Optional[str] = None
        try:
            from ..middleware.correlation import get_correlation_id

            correlation_id = get_correlation_id()
        except Exception:  # pragma: no cover — best-effort, jamais bloquant
            correlation_id = None
        # Message générique : aucun détail interne (rules 40)
        logger.warning(
            "Circuit breaker state transition",
            extra={
                "circuit": self.name,
                "old_state": old.value,
                "new_state": new.value,
                "correlation_id": correlation_id,
            },
        )
        record_circuit_state(self.name, _STATE_METRIC_VALUES[new])

    def _should_attempt_call(self) -> bool:
        """Détermine si un appel peut être tenté (appelé sous lock)."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Vérifier si le timeout est écoulé → sonde half-open
            if self.last_failure_time is not None:
                elapsed = (self._clock() - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout:
                    self._set_state(CircuitState.HALF_OPEN)
                    self.success_count = 0
                    return True
            return False

        # HALF_OPEN : sonde autorisée
        return True

    def _on_success(self) -> None:
        """Gère un appel réussi (appelé sous lock)."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._set_state(CircuitState.CLOSED)
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # Un succès réinitialise la série d'échecs consécutifs
            self.failure_count = 0

    def _on_failure(self) -> None:
        """Gère un appel échoué (appelé sous lock)."""
        self.failure_count += 1
        self.last_failure_time = self._clock()
        record_circuit_failure(self.name)

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._set_state(CircuitState.OPEN)
        elif self.state == CircuitState.HALF_OPEN:
            # Un seul échec en half-open → réouverture
            self._set_state(CircuitState.OPEN)

    # ─── API asynchrone ────────────────────────────────────────

    async def call(
        self,
        func: Callable,
        *args: Any,
        failure_filter: Optional[Callable[[BaseException], bool]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Exécute une fonction protégée par le circuit breaker.

        Args:
            func: Fonction à exécuter (sync ou async).
            *args: Arguments positionnels.
            failure_filter: Prédicat optionnel — une exception ne
                compte comme échec que si le filtre l'accepte (ex. SSH :
                exit 124/255 = transport uniquement, risque H4) ; une
                exception filtrée est re-levée **sans** comptage.
            **kwargs: Arguments nommés.

        Returns:
            Résultat de la fonction.

        Raises:
            CircuitBreakerOpenError: Circuit ouvert — rejet immédiat,
                ``func`` n'est jamais appelée.
            Exception: Exception originale de la fonction (re-levée).
        """
        async with self._lock:
            if not self._should_attempt_call():
                raise CircuitBreakerOpenError(self.name)

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
        except asyncio.CancelledError:
            # Annulation ≠ défaillance de la dépendance : jamais comptée
            raise
        except BaseException as exc:
            counts_as_failure = failure_filter is None or failure_filter(exc)
            if counts_as_failure:
                async with self._lock:
                    self._on_failure()
            # Jamais le message brut en log — type uniquement (rules 40)
            logger.warning(
                "Circuit %s: échec de l'appel protégé — %s (compté=%s)",
                self.name,
                type(exc).__name__,
                counts_as_failure,
            )
            raise

        async with self._lock:
            self._on_success()
        return result

    async def report_success(self) -> None:
        """Reporte un succès externe (résultat tuple ``(True, msg)``).

        Les couches d'exécution Docker retournent des tuples
        ``(bool, msg)`` au lieu de lever : les WorkloadAdapters
        rapportent le booléen via cette API publique (STORY-251 D4).
        """
        async with self._lock:
            self._on_success()

    async def report_failure(self) -> None:
        """Reporte un échec externe (résultat tuple ``(False, msg)``)."""
        async with self._lock:
            self._on_failure()

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


class CircuitBreakerRegistry:
    """Registre de circuits nommés (STORY-251 — décision D1).

    ``get_or_create`` est idempotent : le premier appel construit le
    circuit avec les seuils des settings ``circuit_breaker_*`` (lus une
    fois, à la création), les appels suivants retournent la même
    instance — l'état est partagé par nom dans le process.

    Noms de circuits (cardinalité bornée, rules 45) :

    - ``docker_engine`` — démon Docker (unique/local aujourd'hui,
      hypothèse H1 ; découpage par cible = Roadmap multi-hôtes) ;
    - ``plugin_registry`` — fetch HTTP du registre officiel ;
    - ``ssh:{host_id}`` — exécutions distantes, UUID d'hôte stable
      (jamais de hostname libre en label de métrique).
    """

    def __init__(self) -> None:
        self._circuits: Dict[str, CircuitBreaker] = {}

    def get_or_create(self, name: str) -> CircuitBreaker:
        """Retourne le circuit nommé (créé avec les settings au besoin)."""
        circuit = self._circuits.get(name)
        if circuit is None:
            circuit = CircuitBreaker(
                name,
                failure_threshold=settings.circuit_breaker_failure_threshold,
                success_threshold=settings.circuit_breaker_success_threshold,
                timeout=settings.circuit_breaker_timeout,
                half_open_timeout=settings.circuit_breaker_half_open_timeout,
            )
            self._circuits[name] = circuit
        return circuit

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """États de tous les circuits enregistrés."""
        return {name: circuit.get_state() for name, circuit in self._circuits.items()}

    def reset_all(self) -> None:
        """Oublie tous les circuits (isolation des tests — risque R2)."""
        self._circuits.clear()


#: Instance module-level (décision D1) — singleton du process.
_registry = CircuitBreakerRegistry()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Accesseur du registre global des circuits (STORY-251)."""
    return _registry


def is_circuit_breaker_enabled() -> bool:
    """Le câblage breaker est-il actif ?

    ``circuit_breaker_enabled=False`` → pass-through intégral : les
    points de câblage (adapters, SSH, registre) appellent directement
    la couche d'exécution, zéro instrumentation (STORY-251 D4).
    """
    return settings.circuit_breaker_enabled


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
