"""Adapter App profil ``docker_compose`` (spec 02 — STORY-174.1).

Enveloppe :class:`~app.services.docker_compose_service.DockerComposeService`
et :class:`~app.services.docker_executor.ComposeExecutor` sans duplication
— ces couches restent la couche d'exécution (AC 1).

STORY-251 : les verbes réseau Compose sont protégés par le circuit
breaker ``docker_engine`` (même garde partagé que
``DockerContainerAdapter`, :mod:`._circuit_guard`).
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...enums.workload import WorkloadFamily
from ...schemas.workloads import (
    AppComponent,
    ContextualAction,
    HealthStatus,
    NativeConfig,
    TechnicalComponent,
    WorkloadMetrics,
)
from ..docker_compose_service import DockerComposeService
from ._circuit_guard import guarded_docker_call
from .base import ActionNotImplementedError, AppAdapter

logger = logging.getLogger(__name__)

# Catalogue ContextualActions — spec 02 § Catalogue par profil App
# (docker_compose). Déclaratif : l'exécution passe par les endpoints
# Docker/stacks existants.
_COMPOSE_STACK_ACTIONS: List[ContextualAction] = [
    ContextualAction(
        id="recreate", label="Recreate", section="lifecycle", danger=False
    ),
    ContextualAction(
        id="scale_service", label="Scale service", section="lifecycle", danger=False
    ),
    ContextualAction(
        id="restart_service", label="Restart service", section="lifecycle"
    ),
    ContextualAction(
        id="edit_env", label="Edit env", section="configuration", danger=False
    ),
    ContextualAction(
        id="edit_ports", label="Edit ports", section="configuration", danger=False
    ),
    ContextualAction(
        id="edit_compose_yaml", label="Edit compose YAML", section="configuration"
    ),
    ContextualAction(
        id="pull_images", label="Pull images", section="advanced", danger=False
    ),
    ContextualAction(
        id="logs_per_service", label="Logs per service", section="advanced"
    ),
    ContextualAction(
        id="down_v_rmi", label="down -v --rmi", section="danger", danger=True
    ),
]


class ComposeStackAdapter(AppAdapter):
    """App de profil ``docker_compose`` — stack déployée par projet Compose."""

    def __init__(
        self,
        project_name: str,
        compose_service: Optional[DockerComposeService] = None,
        compose_file: Optional[Path] = None,
    ) -> None:
        self.project_name = project_name
        self._compose_service = compose_service or DockerComposeService()
        # Fichier compose connu (rendu du déploiement) — optionnel pour
        # une stack adoptée non redéployée.
        self._compose_file = compose_file

    # ─── Résilience (STORY-251) ───────────────────────────────
    async def _guarded(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Exécute ``func`` sous le circuit breaker ``docker_engine``."""
        return await guarded_docker_call(func, *args, **kwargs)

    # ─── Identité ─────────────────────────────────────────────
    def family(self) -> WorkloadFamily:
        return WorkloadFamily.APP

    def profile(self) -> str:
        return "docker_compose"

    def profile_label(self) -> str:
        return "Stack Docker Compose"

    # ─── Métriques et santé ──────────────────────────────────
    async def get_metrics(self) -> WorkloadMetrics:
        """Métriques unifiées — vue d'ensemble (détail par service via WS)."""
        return WorkloadMetrics(
            cpu_percent=0.0, memory_used=0, memory_limit=0, network_rx=0, network_tx=0
        )

    async def health(self) -> HealthStatus:
        """Santé agrégée : tous les services up → healthy, sinon partial→unhealthy."""
        ok, status = await self._compose_service.get_compose_status(self.project_name)
        if not ok:
            return HealthStatus(status="unknown", detail=str(status.get("error", "")))
        services: List[dict] = status if isinstance(status, list) else []
        if not services:
            return HealthStatus(status="unknown", detail="aucun service remonté")
        running = sum(
            bool(
                isinstance(svc, dict)
                and str(svc.get("State", svc.get("status", ""))).lower() == "running"
            )
            for svc in services
        )
        if running == len(services):
            return HealthStatus(
                status="healthy", detail=f"{running}/{len(services)} services"
            )
        if running > 0:
            return HealthStatus(
                status="unhealthy",
                detail=f"partiel : {running}/{len(services)} services",
            )
        return HealthStatus(status="unhealthy", detail="0 service running")

    # ─── ContextualActions ───────────────────────────────────
    def contextual_actions(self, context: str = "detail") -> List[ContextualAction]:
        return list(_COMPOSE_STACK_ACTIONS)

    def child_actions(self, child_kind: str, child_id: str) -> List[ContextualAction]:
        """Actions d'un service de la stack (restart/scale/logs)."""
        base = [
            ContextualAction(
                id="restart_service", label=f"Restart {child_id}", section="lifecycle"
            ),
            ContextualAction(
                id="logs_per_service", label=f"Logs {child_id}", section="advanced"
            ),
        ]
        if child_kind == "service":
            base.append(
                ContextualAction(
                    id="scale_service", label=f"Scale {child_id}", section="lifecycle"
                )
            )
        return base

    # ─── Mode Infra ──────────────────────────────────────────
    async def get_native_config(self) -> NativeConfig:
        """Compose YAML du projet (rendu du déploiement si connu)."""
        if self._compose_file is not None and self._compose_file.exists():
            return NativeConfig(
                format="compose", content=self._compose_file.read_text("utf-8")
            )
        return NativeConfig(
            format="compose",
            content=f"# Fichier compose de {self.project_name} non matérialisé "
            "(stack adoptée — Mode Infra partiel)",
        )

    async def get_technical_components(self) -> List[TechnicalComponent]:
        """Services du projet (statut compose → composants techniques)."""
        ok, status = await self._compose_service.get_compose_status(self.project_name)
        services: List[dict] = status if isinstance(status, list) else []
        return [
            TechnicalComponent(
                kind="service",
                name=str(svc.get("Name", svc.get("Service", f"service-{i}"))),
                status=str(svc.get("State", svc.get("status", "unknown"))),
            )
            for i, svc in enumerate(services)
            if isinstance(svc, dict)
        ]

    # ─── Accès applicatif ────────────────────────────────────
    async def get_open_url(self) -> Optional[str]:
        """Aucune URL déterministe pour une stack multi-services → None."""
        return None

    async def list_services_or_pods(self) -> List[AppComponent]:
        ok, status = await self._compose_service.get_compose_status(self.project_name)
        services: List[dict] = status if isinstance(status, list) else []
        return [
            AppComponent(
                name=str(svc.get("Name", svc.get("Service", f"service-{i}"))),
                status=str(svc.get("State", svc.get("status", "unknown"))),
                image=svc.get("Image") if isinstance(svc.get("Image"), str) else None,
            )
            for i, svc in enumerate(services)
            if isinstance(svc, dict)
        ]

    # ─── Verbes universels ───────────────────────────────────
    async def start(self) -> None:
        ok, msg = await self.deploy()
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"start compose {self.project_name} échoué: {msg}")

    async def stop(self) -> None:
        ok, msg = await self._guarded(
            self._compose_service.stop_compose, self.project_name
        )
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"stop compose {self.project_name} échoué: {msg}")

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def update(self, config: Optional[Dict[str, Any]] = None) -> Any:
        """Mise à jour compose : pull des images puis up -d (recreate natif)."""
        ok, msg = await self.deploy(env_vars=(config or {}).get("env_vars"))
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"update compose {self.project_name} échoué: {msg}")
        return msg

    async def _deploy_unguarded(
        self,
        compose_file: Optional[Path] = None,
        project_name: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str]:
        """Déploiement brut (sans breaker) — cible du garde ``deploy``."""
        target_file = compose_file or self._compose_file
        if target_file is None:
            return False, "fichier compose inconnu pour ce projet"
        return await self._compose_service.deploy_compose(
            target_file, project_name or self.project_name, env_vars
        )

    async def deploy(
        self,
        compose_file: Optional[Path] = None,
        project_name: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str]:
        """Déploiement/up du projet (chemin background_tasks — AC 2).

        STORY-251 : sous circuit breaker ``docker_engine`` (tuple
        ``(False, msg)`` = échec compté).
        """
        return await self._guarded(
            self._deploy_unguarded, compose_file, project_name, env_vars
        )

    async def backup(self) -> Any:
        raise ActionNotImplementedError(
            "backup : verbe Sauvegarder porté par l'initiative backup (F8)"
        )

    async def configure(self, config: Dict[str, Any]) -> None:
        raise ActionNotImplementedError(
            "configure : édition compose YAML via l'édition de stack existante"
        )

    async def stream_logs(self, tail: int = 100) -> str:
        ok, logs = await self._guarded(
            self._compose_service.get_compose_logs, self.project_name, tail
        )
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(
                f"logs compose {self.project_name} indisponibles: {logs}"
            )
        return logs

    async def open_console(self, command: Optional[List[str]] = None) -> Any:
        raise ActionNotImplementedError(
            "open_console : terminal interactif porté par terminal_service (WS)"
        )
