"""ABC du contrat WorkloadAdapter (spec 02 — STORY-174.1).

Contrat commun aux trois familles de workloads et à l'entité Cluster
(chapitre 02 § Interface WorkloadAdapter) :

- **identité** : ``family()`` / ``profile()`` / ``profile_label()`` ;
- **métriques et santé** (universel) : ``get_metrics()`` / ``health()`` ;
- **ContextualActions** : ``contextual_actions()`` / ``child_actions()`` ;
- **Mode Infra** : ``get_native_config()`` / ``get_technical_components()``.

La spécialisation :class:`AppAdapter` ajoute les verbes de la famille
Apps (start/stop/restart/update/backup/configure/stream_logs/open_console
— spec 02 § Hiérarchie des adapters App).

Implémentations actuelles : ``DockerContainerAdapter`` et
``ComposeStackAdapter`` (STORY-174.1) qui **enveloppent** les
exécuteurs/services Docker existants sans duplication. Les adapters
K8s/Helm/Swarm/VM suivent la Roadmap (arbitrage F7 du plan de
remédiation).

Sémantique d'erreur : toute erreur métier remonte en
:class:`~app.core.exceptions.WindFlowException` (rules 30) — jamais
d'exception Docker/aiohttp brute au-delà de la couche d'exécution.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from ...enums.workload import WorkloadFamily
from ...schemas.workloads import (
    AppComponent,
    ContextualAction,
    HealthStatus,
    NativeConfig,
    TechnicalComponent,
    WorkloadMetrics,
)

# Stubs explicites — terminaison franche, jamais de succès silencieux
# (pattern scheduler_actions — renvoi F8 initiative backup).
from ..scheduler_actions import ActionNotImplementedError  # noqa: F401 (ré-export)

__all__ = [
    "ActionNotImplementedError",
    "AppAdapter",
    "WorkloadAdapter",
]


class WorkloadAdapter(ABC):
    """Base commune aux familles Apps/Machines/Hosts et à l'entité Cluster.

    Contrat spec 02 § Interface WorkloadAdapter — méthodes abstraites,
    implémentées par les adapters de profil (``docker_container``,
    ``docker_compose``, ``vm_kvm``…).
    """

    # ─── Identité ─────────────────────────────────────────────
    @abstractmethod
    def family(self) -> WorkloadFamily:
        """Famille d'appartenance (APP | MACHINE | HOST | CLUSTER)."""

    @abstractmethod
    def profile(self) -> str:
        """Profil canonique (ex. ``docker_compose``, ``vm_kvm``)."""

    @abstractmethod
    def profile_label(self) -> str:
        """Libellé humain du profil (affiché en Mode Infra)."""

    # ─── Métriques et santé (universel) ──────────────────────
    @abstractmethod
    async def get_metrics(self) -> WorkloadMetrics:
        """Métriques ressources unifiées (CPU, RAM, réseau)."""

    @abstractmethod
    async def health(self) -> HealthStatus:
        """État de santé agrégé (healthcheck / statut runtime)."""

    # ─── ContextualActions ───────────────────────────────────
    @abstractmethod
    def contextual_actions(self, context: str = "detail") -> List[ContextualAction]:
        """Actions contextuelles du workload (action bar + menu ``⋯ Plus``).

        Args:
            context: ``detail`` (page détail) ou ``list`` (ligne de liste).
        """

    @abstractmethod
    def child_actions(self, child_kind: str, child_id: str) -> List[ContextualAction]:
        """Actions contextuelles d'un composant enfant (service Compose…)."""

    # ─── Mode Infra ──────────────────────────────────────────
    @abstractmethod
    async def get_native_config(self) -> NativeConfig:
        """Configuration native du moteur (compose YAML, inspection JSON…)."""

    @abstractmethod
    async def get_technical_components(self) -> List[TechnicalComponent]:
        """Composants techniques révélés en Mode Infra."""


class AppAdapter(WorkloadAdapter):
    """Base pour la famille Apps — sémantique service (spec 02).

    Ajoute les verbes universels Apps et l'accès applicatif (URL,
    composants internes).
    """

    # ─── Accès applicatif ────────────────────────────────────
    @abstractmethod
    async def get_open_url(self) -> Optional[str]:
        """URL d'ouverture (port exposé mappé) — ``None`` si aucune."""

    @abstractmethod
    async def list_services_or_pods(self) -> List[AppComponent]:
        """Composants internes : services Compose, pods Helm, container unique."""

    # ─── Verbes universels (Apps) ────────────────────────────
    @abstractmethod
    async def start(self) -> None:
        """Démarre l'App."""

    @abstractmethod
    async def stop(self) -> None:
        """Arrête l'App."""

    @abstractmethod
    async def restart(self) -> None:
        """Redémarre l'App."""

    @abstractmethod
    async def update(self, config: Optional[dict[str, Any]] = None) -> Any:
        """Met à jour l'App (recreate à configuration préservée pour Docker).

        Args:
            config: Overrides optionnels (image, env, labels…) — ``None``
                conserve la configuration courante.
        """

    @abstractmethod
    async def backup(self) -> Any:
        """Sauvegarde l'App (stub — renvoi F8 initiative backup)."""

    @abstractmethod
    async def configure(self, config: dict[str, Any]) -> None:
        """Configure l'App (édition env/limits/ports…)."""

    @abstractmethod
    async def stream_logs(self, tail: int = 100) -> str:
        """Lit les journaux de l'App (les ``tail`` dernières lignes)."""

    @abstractmethod
    async def open_console(self, command: Optional[List[str]] = None) -> Any:
        """Ouvre une console interactive (stub selon profil)."""
