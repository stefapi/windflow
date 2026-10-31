"""Garde circuit breaker partagé des adapters Docker (STORY-251).

Les couches d'exécution Docker (``DockerService``,
``DockerComposeService``) retournent des tuples ``(bool, msg)`` au lieu
de lever : ce module convertit un tuple ``(False, msg)`` en échec
interne :class:`_TupleFailure` pour que le circuit ``docker_engine``
compte **exactement un** succès ou un échec par appel (pas de double
comptage en half-open), puis restitue le tuple d'origine à l'appelant.

Le comportement visible des adapters (contrat STORY-174.1) est
inchangé : mêmes tuples retournés, mêmes exceptions transport
re-levées ; seul s'ajoute le rejet rapide
:class:`~app.core.exceptions.CircuitBreakerOpenError` quand le circuit
est ouvert.
"""

from typing import Any, Callable

from ...core.resilience import (
    get_circuit_breaker_registry,
    is_circuit_breaker_enabled,
)

#: Nom du circuit Docker (démon unique local aujourd'hui — hypothèse
#: H1 ; le découpage par cible suit la Roadmap multi-hôtes).
DOCKER_ENGINE_CIRCUIT = "docker_engine"


class _TupleFailure(Exception):
    """Représentation interne d'un tuple ``(False, msg)`` pour le circuit.

    Jamais propagée à l'appelant : interceptée par
    :func:`guarded_docker_call` qui restitue le tuple d'origine.
    """

    def __init__(self, payload: Any) -> None:
        super().__init__("docker tuple failure")
        self.payload = payload


def _is_failed_tuple(result: Any) -> bool:
    """Un résultat est-il un tuple d'échec ``(False, msg)`` ?"""
    return isinstance(result, tuple) and bool(result) and result[0] is False


async def guarded_docker_call(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Exécute ``func`` sous le circuit breaker ``docker_engine``.

    - ``circuit_breaker_enabled=False`` → pass-through intégral
      (zéro instrumentation, comportement STORY-174.1 inchangé) ;
    - circuit ouvert → :class:`CircuitBreakerOpenError` levée **sans
      appeler** ``func`` (échec rapide, aucune tentative réseau — AC 1) ;
    - exception transport → comptée comme échec puis re-levée ;
    - tuple ``(False, msg)`` → compté comme échec, tuple restitué ;
    - tout autre résultat → compté comme succès, restitué.
    """
    if not is_circuit_breaker_enabled():
        return await func(*args, **kwargs)

    circuit = get_circuit_breaker_registry().get_or_create(DOCKER_ENGINE_CIRCUIT)

    async def _probe() -> Any:
        result = await func(*args, **kwargs)
        if _is_failed_tuple(result):
            raise _TupleFailure(result)
        return result

    try:
        return await circuit.call(_probe)
    except _TupleFailure as guarded:
        return guarded.payload
