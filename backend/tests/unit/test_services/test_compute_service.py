"""
Tests unitaires pour compute_service.py.

Teste l'agrégation des données DB + Docker pour la vue globale Compute.
Les dépendances externes (DB, Docker) sont mockées.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.compute_service import (
    _classify_containers,
    _format_memory,
    get_compute_global,
    get_compute_stats,
)
from app.schemas.compute import ComputeGlobalView, ComputeStatsResponse, TargetGroup


# =============================================================================
# Helpers — fabrique de ContainerInfo mockés
# =============================================================================


def _make_container(
    container_id: str = "abc123",
    name: str = "my-container",
    image: str = "nginx:latest",
    state: str = "running",
    labels: dict | None = None,
) -> MagicMock:
    """Crée un ContainerInfo mocké."""
    c = MagicMock()
    c.id = container_id
    c.name = name
    c.image = image
    c.state = state
    c.labels = labels or {}
    return c


def _wf_labels(stack_id: str) -> dict:
    """Labels WindFlow pour un container managé."""
    return {"windflow.managed": "true", "windflow.stack_id": stack_id}


def _compose_labels(project: str, config_file: str | None = None) -> dict:
    """Labels Docker Compose pour un container découvert."""
    labels = {"com.docker.compose.project": project}
    if config_file:
        labels["com.docker.compose.project.config_files"] = config_file
    return labels


# =============================================================================
# Tests _format_memory
# =============================================================================


class TestFormatMemory:
    def test_zero_returns_zero_m(self) -> None:
        assert _format_memory(0) == "0M"

    def test_negative_returns_zero_m(self) -> None:
        assert _format_memory(-100) == "0M"

    def test_kilobytes(self) -> None:
        # 512 KB
        result = _format_memory(512 * 1024)
        assert result.endswith("K")

    def test_megabytes(self) -> None:
        # 100 MB
        result = _format_memory(100 * 1024 * 1024)
        assert result.endswith("M")

    def test_gigabytes(self) -> None:
        # 2 GB
        result = _format_memory(2 * 1024 * 1024 * 1024)
        assert result.endswith("G")


# =============================================================================
# Tests _classify_containers
# =============================================================================


class TestClassifyContainers:
    def test_windflow_managed_goes_to_managed(self) -> None:
        c = _make_container(labels=_wf_labels("stack-001"))
        managed, discovered, standalone = _classify_containers([c])
        assert "stack-001" in managed
        assert len(managed["stack-001"]) == 1
        assert discovered == {}
        assert standalone == []

    def test_compose_project_goes_to_discovered(self) -> None:
        c = _make_container(labels=_compose_labels("myapp"))
        managed, discovered, standalone = _classify_containers([c])
        assert managed == {}
        assert "myapp" in discovered
        assert standalone == []

    def test_no_labels_goes_to_standalone(self) -> None:
        c = _make_container(labels={})
        managed, discovered, standalone = _classify_containers([c])
        assert managed == {}
        assert discovered == {}
        assert len(standalone) == 1

    def test_windflow_takes_priority_over_compose(self) -> None:
        """Un container avec les deux labels est classé dans managed (WindFlow prioritaire)."""
        labels = {**_wf_labels("stack-x"), **_compose_labels("myproject")}
        c = _make_container(labels=labels)
        managed, discovered, standalone = _classify_containers([c])
        assert "stack-x" in managed
        assert discovered == {}

    def test_multiple_containers_mixed(self) -> None:
        c1 = _make_container("id1", labels=_wf_labels("stack-1"))
        c2 = _make_container("id2", labels=_compose_labels("proj-a"))
        c3 = _make_container("id3", labels={})
        c4 = _make_container("id4", labels=_compose_labels("proj-a"))
        managed, discovered, standalone = _classify_containers([c1, c2, c3, c4])
        assert len(managed["stack-1"]) == 1
        assert len(discovered["proj-a"]) == 2
        assert len(standalone) == 1

    def test_grouped_by_stack_id(self) -> None:
        """Plusieurs containers de la même stack sont regroupés."""
        c1 = _make_container("id1", labels=_wf_labels("stack-A"))
        c2 = _make_container("id2", labels=_wf_labels("stack-A"))
        c3 = _make_container("id3", labels=_wf_labels("stack-B"))
        managed, _, _ = _classify_containers([c1, c2, c3])
        assert len(managed["stack-A"]) == 2
        assert len(managed["stack-B"]) == 1


# =============================================================================
# Tests get_compute_stats
# =============================================================================


class TestGetComputeStats:
    @pytest.fixture
    def mock_db(self):
        """Session DB mockée retournant des scalaires."""
        db = AsyncMock()
        # execute retourne un résultat avec scalar()
        result_stacks = MagicMock()
        result_stacks.scalar.return_value = 3
        result_targets = MagicMock()
        result_targets.scalar.return_value = 2
        db.execute = AsyncMock(side_effect=[result_stacks, result_targets])
        return db

    @pytest.mark.asyncio
    async def test_docker_unavailable_returns_zeros(self, mock_db) -> None:
        """Quand Docker n'est pas disponible, les compteurs Docker sont à 0."""
        with patch(
            "app.services.compute_service.DockerClientService"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = False
            mock_cls.return_value = mock_instance

            result = await get_compute_stats(mock_db, org_id="org-1")

        assert isinstance(result, ComputeStatsResponse)
        assert result.stacks_count == 3
        assert result.targets_count == 2
        assert result.total_containers == 0
        assert result.running_containers == 0
        assert result.stacks_services_count == 0
        assert result.discovered_count == 0
        assert result.discovered_targets_count == 0
        assert result.standalone_count == 0
        assert result.standalone_targets_count == 0

    @pytest.mark.asyncio
    async def test_docker_exception_returns_zeros(self, mock_db) -> None:
        """Une exception Docker retourne des compteurs à 0 sans lever d'erreur."""
        with patch(
            "app.services.compute_service.DockerClientService"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.side_effect = ConnectionError("socket unreachable")
            mock_cls.return_value = mock_instance

            result = await get_compute_stats(mock_db, org_id=None)

        assert result.total_containers == 0
        assert result.running_containers == 0

    @pytest.mark.asyncio
    async def test_docker_available_returns_correct_counts(self) -> None:
        """Quand Docker est disponible, les compteurs sont corrects."""
        mock_db = AsyncMock()
        result_stacks = MagicMock()
        result_stacks.scalar.return_value = 1
        result_targets = MagicMock()
        result_targets.scalar.return_value = 1
        mock_db.execute = AsyncMock(side_effect=[result_stacks, result_targets])

        containers = [
            _make_container("c1", state="running", labels=_wf_labels("stack-1")),
            _make_container("c2", state="running", labels=_wf_labels("stack-1")),
            _make_container("c3", state="exited", labels=_compose_labels("proj")),
            _make_container("c4", state="running", labels={}),
        ]

        with patch(
            "app.services.compute_service.DockerClientService"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = True
            mock_instance.list_containers.return_value = containers
            mock_cls.return_value = mock_instance

            result = await get_compute_stats(mock_db, org_id=None)

        assert result.total_containers == 4
        assert result.running_containers == 3
        assert result.stacks_services_count == 2   # 2 containers windflow
        assert result.discovered_count == 1         # 1 projet compose
        assert result.standalone_count == 1         # 1 standalone


# =============================================================================
# Tests get_compute_global
# =============================================================================


def _make_stack(stack_id: str = "s1", name: str = "My Stack", deployments=None) -> MagicMock:
    """Crée un Stack mocké."""
    stack = MagicMock()
    stack.id = stack_id
    stack.name = name
    stack.target_type = "docker"
    stack.deployments = deployments or []
    return stack


def _make_target(target_id: str = "t1", name: str = "My Target") -> MagicMock:
    """Crée un Target mocké."""
    t = MagicMock()
    t.id = target_id
    t.name = name
    t.host = "192.168.1.1"
    t.type = MagicMock()
    t.type.value = "docker"
    return t


def _make_mock_db(stacks=None, targets=None):
    """Crée une DB mockée qui retourne des stacks et targets."""
    db = AsyncMock()

    # scalars().all() pour stacks
    stacks_scalars = MagicMock()
    stacks_scalars.scalars.return_value.all.return_value = stacks or []

    # scalars().all() pour targets
    targets_scalars = MagicMock()
    targets_scalars.scalars.return_value.all.return_value = targets or []

    # La requête locale target (retourne None)
    local_target_result = MagicMock()
    local_target_result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(
        side_effect=[stacks_scalars, targets_scalars, local_target_result]
    )
    return db


class TestGetComputeGlobal:
    @pytest.mark.asyncio
    async def test_no_docker_returns_stacks_stopped(self) -> None:
        """Sans Docker, les stacks DB sont retournées avec statut 'stopped'."""
        stack = _make_stack("s1", "My Stack")
        mock_db = _make_mock_db(stacks=[stack])

        with patch(
            "app.services.compute_service.DockerClientService"
        ) as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = False
            mock_cls.return_value = mock_instance

            result = await get_compute_global(mock_db, org_id=None)

        assert isinstance(result, ComputeGlobalView)
        assert len(result.managed_stacks) == 1
        assert result.managed_stacks[0].status == "stopped"
        assert result.discovered_items == []
        assert result.standalone_containers == []

    @pytest.mark.asyncio
    async def test_returns_all_sections(self) -> None:
        """La vue globale contient les 3 sections correctement remplies."""
        stack = _make_stack("s1", "WindFlow Stack")
        mock_db = _make_mock_db(stacks=[stack])

        containers = [
            _make_container("c1", "wf-svc", state="running", labels=_wf_labels("s1")),
            _make_container("c2", "compose-app", state="running", labels=_compose_labels("proj")),
            _make_container("c3", "standalone", state="exited", labels={}),
        ]

        with patch("app.services.compute_service.DockerClientService") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = True
            mock_instance.list_containers.return_value = containers
            mock_cls.return_value = mock_instance

            result = await get_compute_global(mock_db, org_id=None)

        assert isinstance(result, ComputeGlobalView)
        assert len(result.managed_stacks) == 1
        assert result.managed_stacks[0].name == "WindFlow Stack"
        assert result.managed_stacks[0].services_running == 1
        assert result.managed_stacks[0].status == "running"

        assert len(result.discovered_items) == 1
        assert result.discovered_items[0].name == "proj"
        assert result.discovered_items[0].technology == "docker-compose"

        assert len(result.standalone_containers) == 1
        assert result.standalone_containers[0].name == "standalone"

    @pytest.mark.asyncio
    async def test_group_by_target_returns_target_groups(self) -> None:
        """group_by=target retourne une liste de TargetGroup."""
        stack = _make_stack("s1", "My Stack")
        mock_db = _make_mock_db(stacks=[stack])

        containers = [
            _make_container("c1", labels=_wf_labels("s1"), state="running"),
            _make_container("c2", labels={}, state="running"),
        ]

        with patch("app.services.compute_service.DockerClientService") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = True
            mock_instance.list_containers.return_value = containers
            mock_cls.return_value = mock_instance

            result = await get_compute_global(mock_db, org_id=None, group_by="target")

        assert isinstance(result, list)
        assert all(isinstance(g, TargetGroup) for g in result)

    @pytest.mark.asyncio
    async def test_search_filter_applies_to_all_sections(self) -> None:
        """Le filtre search filtre correctement dans les 3 sections."""
        stack_nginx = _make_stack("s1", "nginx-stack")
        stack_redis = _make_stack("s2", "redis-stack")
        mock_db = _make_mock_db(stacks=[stack_nginx, stack_redis])

        containers = [
            _make_container("c1", "nginx-compose", labels=_compose_labels("nginx-proj")),
            _make_container("c2", "redis-standalone", labels={}),
        ]

        with patch("app.services.compute_service.DockerClientService") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = True
            mock_instance.list_containers.return_value = containers
            mock_cls.return_value = mock_instance

            result = await get_compute_global(mock_db, org_id=None, search="nginx")

        assert isinstance(result, ComputeGlobalView)
        assert len(result.managed_stacks) == 1
        assert result.managed_stacks[0].name == "nginx-stack"
        assert len(result.discovered_items) == 1
        assert result.discovered_items[0].name == "nginx-proj"
        assert len(result.standalone_containers) == 0

    @pytest.mark.asyncio
    async def test_type_filter_managed_hides_others(self) -> None:
        """type=managed masque discovered et standalone."""
        stack = _make_stack("s1")
        mock_db = _make_mock_db(stacks=[stack])

        containers = [
            _make_container("c1", labels=_compose_labels("proj")),
            _make_container("c2", labels={}),
        ]

        with patch("app.services.compute_service.DockerClientService") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.ping.return_value = True
            mock_instance.list_containers.return_value = containers
            mock_cls.return_value = mock_instance

            result = await get_compute_global(mock_db, org_id=None, type_filter="managed")

        assert isinstance(result, ComputeGlobalView)
        assert result.discovered_items == []
        assert result.standalone_containers == []
