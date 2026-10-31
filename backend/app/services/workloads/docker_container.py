"""Adapter App profil ``docker_container`` (spec 02 — STORY-174.1).

Enveloppe les services/exécuteurs Docker existants **sans duplication**
(AC 1) : :class:`~app.services.docker_service.DockerService` (substitution,
validation, déploiement), :class:`~app.services.docker_executor.DockerExecutor`
(cycle de vie) et :class:`~app.services.docker_client_service.
DockerClientService` (inspection Engine). Ces couches restent la couche
d'exécution — l'adapter traduit le contrat spec 02.

Le point d'extension ``update()`` délègue au recreate du client Docker ;
il est rebranché sur le recreate **sécurisé** par la STORY-174.2.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ...enums.workload import WorkloadFamily
from ...schemas.workloads import (
    AppComponent,
    ContextualAction,
    HealthStatus,
    NativeConfig,
    TechnicalComponent,
    WorkloadMetrics,
)
from ..docker_client_service import DockerClientService
from ..docker_service import DockerService
from .base import ActionNotImplementedError, AppAdapter

logger = logging.getLogger(__name__)

# Catalogue ContextualActions — spec 02 § Catalogue par profil App
# (docker_container). Déclaratif dans cette story : l'exécution passe par
# les endpoints Docker existants (force restart/pause, edit env/limits,
# volume snapshot, commit/export/inspect, force remove).
_DOCKER_CONTAINER_ACTIONS: List[ContextualAction] = [
    ContextualAction(
        id="force_restart", label="Force restart", section="lifecycle", danger=False
    ),
    ContextualAction(id="pause", label="Pause", section="lifecycle", danger=False),
    ContextualAction(
        id="edit_env", label="Edit env", section="configuration", danger=False
    ),
    ContextualAction(
        id="edit_limits", label="Edit limits", section="configuration", danger=False
    ),
    ContextualAction(
        id="volume_snapshot", label="Volume snapshot", section="data", danger=False
    ),
    ContextualAction(
        id="commit_image", label="Commit image", section="advanced", danger=False
    ),
    ContextualAction(id="export", label="Export", section="advanced", danger=False),
    ContextualAction(id="inspect", label="Inspect", section="advanced", danger=False),
    ContextualAction(
        id="force_remove", label="Force remove", section="danger", danger=True
    ),
]


class DockerContainerAdapter(AppAdapter):
    """App de profil ``docker_container`` — container Docker individuel."""

    def __init__(
        self,
        container_id: str,
        service: Optional[DockerService] = None,
        client: Optional[DockerClientService] = None,
    ) -> None:
        self.container_id = container_id
        self._service = service or DockerService()
        self._client = client

    # ─── Identité ─────────────────────────────────────────────
    def family(self) -> WorkloadFamily:
        return WorkloadFamily.APP

    def profile(self) -> str:
        return "docker_container"

    def profile_label(self) -> str:
        return "Container Docker"

    # ─── Internes ─────────────────────────────────────────────
    async def _get_client(self) -> DockerClientService:
        """Client Engine (lazy — partagé si injecté, fermé sinon par l'appelant)."""
        return self._client if self._client is not None else DockerClientService()

    def _owns_client(self) -> bool:
        return self._client is None

    # ─── Métriques et santé ──────────────────────────────────
    async def get_metrics(self) -> WorkloadMetrics:
        """Métriques unifiées depuis l'inspection Engine.

        Les compteurs CPU/RAM temps réel exigent le stream ``stats`` du
        démon (consommé par le canal WebSocket dédié) — l'adapter sert
        une vue d'inspection dégradée à 0 par défaut (jamais d'exception
        sur une métrique indisponible).
        """
        detail = await self._inspect()
        return (
            WorkloadMetrics(
                cpu_percent=0.0,
                memory_used=0,
                memory_limit=0,
                network_rx=0,
                network_tx=0,
            )
            if detail is None
            else WorkloadMetrics(
                cpu_percent=0.0,
                memory_used=0,
                memory_limit=0,
                network_rx=0,
                network_tx=0,
            )
        )

    async def health(self) -> HealthStatus:
        """Santé depuis ``State`` de l'inspection (healthcheck si présent)."""
        detail = await self._inspect()
        if detail is None:
            return HealthStatus(status="unknown", detail="container introuvable")
        state = detail.get("State", {}) if isinstance(detail, dict) else {}
        running = bool(state.get("Running"))
        health = state.get("Health", {}) or {}
        if health:
            raw_status = str(health.get("Status", "unknown"))
            if raw_status == "healthy":
                return HealthStatus(status="healthy", detail=state.get("Error"))
            if raw_status == "unhealthy":
                return HealthStatus(status="unhealthy", detail=state.get("Error"))
            if raw_status == "starting":
                return HealthStatus(status="starting", detail=state.get("Error"))
        if running:
            return HealthStatus(status="healthy", detail=state.get("Status"))
        return HealthStatus(status="unhealthy", detail=state.get("Status"))

    async def _inspect(self) -> Optional[Dict[str, Any]]:
        """Inspection Engine du container (dict brut ou None)."""
        client = await self._get_client()
        try:
            return await client.inspect_container(self.container_id)
        except Exception as exc:
            logger.debug("inspect %s indisponible: %s", self.container_id, exc)
            return None
        finally:
            if self._owns_client():
                await client.close()

    # ─── ContextualActions ───────────────────────────────────
    def contextual_actions(self, context: str = "detail") -> List[ContextualAction]:
        return list(_DOCKER_CONTAINER_ACTIONS)

    def child_actions(self, child_kind: str, child_id: str) -> List[ContextualAction]:
        return []  # un container Docker n'a pas d'enfants

    # ─── Mode Infra ──────────────────────────────────────────
    async def get_native_config(self) -> NativeConfig:
        """Inspection Engine complète (JSON — Mode Infra « Manifest »)."""
        detail = await self._inspect()
        import json as _json

        return NativeConfig(
            format="json",
            content=_json.dumps(detail or {}, indent=2, default=str),
        )

    async def get_technical_components(self) -> List[TechnicalComponent]:
        detail = await self._inspect()
        state = detail.get("State", {}) if isinstance(detail, dict) else {}
        status = str(state.get("Status", "unknown")) if state else "unknown"
        return [
            TechnicalComponent(kind="container", name=self.container_id, status=status)
        ]

    # ─── Accès applicatif ────────────────────────────────────
    async def get_open_url(self) -> Optional[str]:
        """Premier port hôte publié (``HostConfig.PortBindings``), sinon None."""
        detail = await self._inspect()
        if not isinstance(detail, dict):
            return None
        bindings = detail.get("HostConfig", {}).get("PortBindings", {}) or {}
        for _container_port, host_bindings in bindings.items():
            if host_bindings:
                host_port = host_bindings[0].get("HostPort")
                if host_port:
                    return f"http://localhost:{host_port}"
        return None

    async def list_services_or_pods(self) -> List[AppComponent]:
        """Container unique : l'App EST le composant."""
        detail = await self._inspect()
        state = detail.get("State", {}) if isinstance(detail, dict) else {}
        image = (
            detail.get("Config", {}).get("Image") if isinstance(detail, dict) else None
        )
        return [
            AppComponent(
                name=(
                    str(detail.get("Name", self.container_id)).lstrip("/")
                    if isinstance(detail, dict)
                    else self.container_id
                ),
                status=str(state.get("Status", "unknown")) if state else "unknown",
                image=image,
            )
        ]

    # ─── Verbes universels ───────────────────────────────────
    async def start(self) -> None:
        ok, msg = await self._service.start_container(self.container_id)
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"start {self.container_id} échoué: {msg}")

    async def stop(self) -> None:
        ok, msg = await self._service.stop_container(self.container_id)
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"stop {self.container_id} échoué: {msg}")

    async def restart(self) -> None:
        ok, msg = await self._service.restart_container(self.container_id)
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"restart {self.container_id} échoué: {msg}")

    async def update(self, config: Optional[Dict[str, Any]] = None) -> Any:
        """Mettre à jour = recreate à configuration préservée (spec 02).

        Délègue au recreate **sécurisé** du client Engine (STORY-174.2) :
        capture de l'ancienne image avant pull, renommage ``-old``,
        rebase par valeur, rollback automatique, secrets ``***``.
        """
        client = await self._get_client()
        try:
            # STORY-174.2 : recreate sécurisé (rebase par valeur,
            # rollback automatique, secrets `***` résolus).
            new_id, _new_detail = await client.recreate_container_secure(
                self.container_id,
                image=(config or {}).get("image"),
                pull_image=bool((config or {}).get("pull_image", False)),
                env=(config or {}).get("env"),
                labels=(config or {}).get("labels"),
            )
            return new_id
        finally:
            if self._owns_client():
                await client.close()

    async def deploy(
        self, config: Dict[str, Any], container_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Déploiement initial par template (chemin background_tasks — AC 2).

        Délègue à ``DockerService.deploy_container`` (substitution et
        validation déjà faites en amont par l'appelant historique).
        """
        return await self._service.deploy_container(config, container_name)

    async def backup(self) -> Any:
        raise ActionNotImplementedError(
            "backup : verbe Sauvegarder porté par l'initiative backup (F8)"
        )

    async def configure(self, config: Dict[str, Any]) -> None:
        raise ActionNotImplementedError(
            "configure : édition env/limits via l'endpoint recreate existant"
        )

    async def stream_logs(self, tail: int = 100) -> str:
        ok, logs = await self._service.get_container_logs(self.container_id, tail)
        if not ok:
            from ...core.exceptions import WindFlowException

            raise WindFlowException(f"logs {self.container_id} indisponibles: {logs}")
        return logs

    async def open_console(self, command: Optional[List[str]] = None) -> Any:
        raise ActionNotImplementedError(
            "open_console : terminal interactif porté par terminal_service (WS)"
        )
