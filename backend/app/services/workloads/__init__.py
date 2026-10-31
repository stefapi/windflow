"""Socle WorkloadAdapter — famille de workload pilotée par adapter (STORY-174.1).

Contrat commun spec 02 § Interface WorkloadAdapter + adapters Docker
(enveloppement des exécuteurs/services existants — aucune duplication).
Les adapters K8s/Helm/Swarm/VM suivent la Roadmap (arbitrage F7).
Voir `README.md <./README.md>`_ pour le contrat complet.
"""

from typing import Any

from .base import ActionNotImplementedError, AppAdapter, WorkloadAdapter
from .compose_stack import ComposeStackAdapter
from .docker_container import DockerContainerAdapter

__all__ = [
    "ActionNotImplementedError",
    "AppAdapter",
    "ComposeStackAdapter",
    "DockerContainerAdapter",
    "WorkloadAdapter",
    "get_app_adapter",
]


def get_app_adapter(profile: str, **kwargs: Any) -> AppAdapter:
    """Résout l'adapter App pour un profil canonique (spec 02).

    Args:
        profile: Profil du workload (``docker_container``, ``docker_compose``).
        **kwargs: Arguments du constructeur de l'adapter (identifiant du
            workload, services injectés…).

    Returns:
        L'adapter instancié pour le profil.

    Raises:
        ValueError: Profil inconnu — jamais de fallback silencieux (les
            adapters non-Docker sont Roadmap).
    """
    adapters = {
        "docker_container": DockerContainerAdapter,
        "docker_compose": ComposeStackAdapter,
    }
    try:
        adapter_cls = adapters[profile]
    except KeyError:
        available = ", ".join(sorted(adapters))
        raise ValueError(
            f"Profil de workload non supporté : {profile!r} "
            f"(adapters disponibles : {available} ; K8s/Helm/VM : Roadmap)"
        ) from None
    return adapter_cls(**kwargs)
