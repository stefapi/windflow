"""
Tests unitaires pour container_builder.py.

Teste la construction des objets domaine (StackWithServices, DiscoveredItem,
StandaloneContainer, TargetGroup) à partir des données brutes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.deployment import Deployment, DeploymentStatus
from app.services.container_builder import (
    build_discovered_items,
    build_managed_stacks,
    build_standalone_containers,
    build_target_groups,
    get_latest_active_deployment,
)
from app.schemas.compute import (
    DiscoveredItem,
    StandaloneContainer,
    StackWithServices,
    TargetGroup,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_container_info(
    container_id: str = "c1",
    name: str = "my-container",
    image: str = "nginx:latest",
    state: str = "running",
    labels: dict | None = None,
    status: str = "Up 2 hours",
    ports: list | None = None,
) -> MagicMock:
    """Crée un ContainerInfo mocké."""
    c = MagicMock()
    c.id = container_id
    c.name = name
    c.image = image
    c.state = state
    c.labels = labels or {}
    c.status = status
    c.ports = ports or []
    return c


def _make_deployment(
    target_id: str = "t1",
    status: DeploymentStatus = DeploymentStatus.RUNNING,
    created_at=None,
) -> MagicMock:
    """Crée un Deployment ORM mocké."""
    d = MagicMock(spec=Deployment)
    d.target_id = target_id
    d.status = status
    d.created_at = created_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return d


def _make_db_stack(
    stack_id: str = "s1",
    name: str = "My Stack",
    target_type: str = "docker",
    deployments: list | None = None,
) -> MagicMock:
    """Crée un Stack ORM mocké."""
    s = MagicMock()
    s.id = stack_id
    s.name = name
    s.target_type = target_type
    s.deployments = deployments or []
    return s


def _make_target(target_id: str = "t1", name: str = "Target1", target_type: str = "docker") -> MagicMock:
    """Crée un Target ORM mocké."""
    t = MagicMock()
    t.id = target_id
    t.name = name
    t.type = MagicMock()
    t.type.value = target_type
    return t


def _make_stack_schema(
    stack_id: str = "s1",
    name: str = "my-stack",
    target_id: str = "local",
) -> StackWithServices:
    from app.schemas.compute import ServiceWithMetrics
    return StackWithServices(
        id=stack_id, name=name, technology="windflow",
        target_id=target_id, target_name="Local Docker",
        services_total=1, services_running=1, status="running",
        services=[ServiceWithMetrics(
            id="svc1", name="svc", image="nginx",
            status="running", cpu_percent=0.0, memory_usage="0M",
        )],
    )


def _make_discovered_schema(
    item_id: str = "d1",
    name: str = "my-proj",
    target_id: str = "local",
) -> DiscoveredItem:
    return DiscoveredItem(
        id=item_id, name=name, type="composition", technology="docker-compose",
        source_path=None, target_id=target_id, target_name="Local Docker",
        services_total=1, services_running=1, detected_at="2026-01-01T00:00:00Z",
        adoptable=True, services=[],
    )


def _make_standalone_schema(
    container_id: str = "c1",
    name: str = "my-container",
    target_id: str = "local",
) -> StandaloneContainer:
    return StandaloneContainer(
        id=container_id, name=name, image="nginx",
        target_id=target_id, target_name="Local Docker",
        status="running", cpu_percent=0.0, memory_usage="0M",
        uptime="Up 2 hours", ports=[], health_status=None,
    )


# =============================================================================
# Tests get_latest_active_deployment
# =============================================================================


class TestGetLatestActiveDeployment:
    def test_empty_list_returns_none(self) -> None:
        assert get_latest_active_deployment([]) is None

    def test_returns_most_recent_active(self) -> None:
        d1 = _make_deployment("t1", DeploymentStatus.RUNNING, datetime(2026, 1, 1, tzinfo=timezone.utc))
        d2 = _make_deployment("t2", DeploymentStatus.RUNNING, datetime(2026, 1, 10, tzinfo=timezone.utc))
        result = get_latest_active_deployment([d1, d2])
        assert result.target_id == "t2"

    def test_skips_stopped_and_failed(self) -> None:
        d1 = _make_deployment("t1", DeploymentStatus.STOPPED, datetime(2026, 1, 10, tzinfo=timezone.utc))
        d2 = _make_deployment("t2", DeploymentStatus.FAILED, datetime(2026, 1, 5, tzinfo=timezone.utc))
        d3 = _make_deployment("t3", DeploymentStatus.RUNNING, datetime(2026, 1, 1, tzinfo=timezone.utc))
        result = get_latest_active_deployment([d1, d2, d3])
        assert result.target_id == "t3"

    def test_fallback_to_most_recent_if_all_stopped(self) -> None:
        d1 = _make_deployment("t1", DeploymentStatus.STOPPED, datetime(2026, 1, 1, tzinfo=timezone.utc))
        d2 = _make_deployment("t2", DeploymentStatus.STOPPED, datetime(2026, 1, 15, tzinfo=timezone.utc))
        result = get_latest_active_deployment([d1, d2])
        assert result.target_id == "t2"


# =============================================================================
# Tests build_managed_stacks
# =============================================================================


class TestBuildManagedStacks:
    @pytest.mark.asyncio
    async def test_empty_stacks(self) -> None:
        result = await build_managed_stacks([], {}, {}, "local", "Local Docker")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_stack_with_containers(self) -> None:
        stack = _make_db_stack("s1", "My Stack", deployments=[
            _make_deployment("t1", DeploymentStatus.RUNNING),
        ])
        target = _make_target("t1", "My Target")
        c1 = _make_container_info("c1", "svc1", state="running")
        c2 = _make_container_info("c2", "svc2", state="running")

        result = await build_managed_stacks(
            [stack], {"s1": [c1, c2]}, {"t1": target}, "local", "Local Docker",
        )

        assert len(result) == 1
        s = result[0]
        assert s.name == "My Stack"
        assert s.target_id == "t1"
        assert s.target_name == "My Target"
        assert s.services_total == 2
        assert s.services_running == 2
        assert s.status == "running"

    @pytest.mark.asyncio
    async def test_partial_status(self) -> None:
        stack = _make_db_stack("s1", deployments=[_make_deployment("t1")])
        c1 = _make_container_info("c1", state="running")
        c2 = _make_container_info("c2", state="exited")

        result = await build_managed_stacks([stack], {"s1": [c1, c2]}, {"t1": _make_target()}, "local", "Local")

        assert result[0].status == "partial"
        assert result[0].services_running == 1

    @pytest.mark.asyncio
    async def test_stopped_when_no_containers(self) -> None:
        stack = _make_db_stack("s1", deployments=[_make_deployment("t1")])
        result = await build_managed_stacks([stack], {}, {"t1": _make_target()}, "local", "Local")
        assert result[0].status == "stopped"
        assert result[0].services_total == 0

    @pytest.mark.asyncio
    async def test_fallback_to_local_target_when_no_deployment(self) -> None:
        stack = _make_db_stack("s1", deployments=[])
        result = await build_managed_stacks([stack], {}, {}, "local", "Local Docker")
        assert result[0].target_id == "local"
        assert result[0].target_name == "Local Docker"

    @pytest.mark.asyncio
    async def test_technology_normalization(self) -> None:
        stack = _make_db_stack("s1", target_type="docker_compose")
        result = await build_managed_stacks([stack], {}, {}, "local", "Local")
        assert result[0].technology == "docker-compose"

    @pytest.mark.asyncio
    async def test_technology_windflow_unchanged(self) -> None:
        stack = _make_db_stack("s1", target_type="windflow")
        result = await build_managed_stacks([stack], {}, {}, "local", "Local")
        assert result[0].technology == "windflow"

    @pytest.mark.asyncio
    async def test_service_uptime_and_ports_populated(self) -> None:
        """Les champs uptime et ports sont extraits depuis ContainerInfo."""
        stack = _make_db_stack("s1", deployments=[_make_deployment("t1")])
        c1 = _make_container_info(
            "c1", state="running", status="Up 5 minutes",
            ports=[{"IP": "0.0.0.0", "PublicPort": 80, "PrivatePort": 80, "Type": "tcp"}],
        )

        result = await build_managed_stacks(
            [stack], {"s1": [c1]}, {"t1": _make_target()}, "local", "Local",
        )

        svc = result[0].services[0]
        assert svc.uptime == "Up 5 minutes"
        assert len(svc.ports) == 1
        assert svc.ports[0].host_port == 80


# =============================================================================
# Tests build_discovered_items
# =============================================================================


class TestBuildDiscoveredItems:
    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        result = await build_discovered_items({}, "local", "Local Docker", "2026-01-01T00:00:00Z")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_project(self) -> None:
        c1 = _make_container_info("c1", "app-web", state="running")
        c1.labels = {"com.docker.compose.project.config_files": "/opt/app/docker-compose.yml"}
        c2 = _make_container_info("c2", "app-db", state="running")

        result = await build_discovered_items(
            {"myapp": [c1, c2]}, "local", "Local Docker", "2026-03-28T00:00:00Z",
        )

        assert len(result) == 1
        item = result[0]
        assert item.name == "myapp"
        assert item.id == "compose:myapp@local"
        assert item.technology == "docker-compose"
        assert item.type == "composition"
        assert item.target_id == "local"
        assert item.services_total == 2
        assert item.services_running == 2
        assert item.adoptable is True
        assert item.source_path == "/opt/app/docker-compose.yml"
        assert len(item.services) == 2

    @pytest.mark.asyncio
    async def test_multiple_projects(self) -> None:
        c1 = _make_container_info("c1")
        c2 = _make_container_info("c2")

        result = await build_discovered_items(
            {"proj-a": [c1], "proj-b": [c2]}, "local", "Local", "2026-01-01T00:00:00Z",
        )

        assert len(result) == 2
        names = {item.name for item in result}
        assert names == {"proj-a", "proj-b"}

    @pytest.mark.asyncio
    async def test_no_source_path(self) -> None:
        c1 = _make_container_info("c1")
        c1.labels = {}  # Pas de config_files label

        result = await build_discovered_items({"proj": [c1]}, "local", "Local", "2026-01-01T00:00:00Z")
        assert result[0].source_path is None

    @pytest.mark.asyncio
    async def test_service_uptime_and_ports_populated(self) -> None:
        """Les champs uptime et ports sont extraits depuis ContainerInfo."""
        c1 = _make_container_info(
            "c1", state="running", status="Up 3 hours",
            ports=[{"IP": "0.0.0.0", "PublicPort": 443, "PrivatePort": 443, "Type": "tcp"}],
        )

        result = await build_discovered_items(
            {"myproj": [c1]}, "local", "Local", "2026-01-01T00:00:00Z",
        )

        svc = result[0].services[0]
        assert svc.uptime == "Up 3 hours"
        assert len(svc.ports) == 1
        assert svc.ports[0].host_port == 443


# =============================================================================
# Tests build_standalone_containers
# =============================================================================


class TestBuildStandaloneContainers:
    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        result = await build_standalone_containers([], "local", "Local", False)
        assert result == []

    @pytest.mark.asyncio
    async def test_docker_not_available(self) -> None:
        """Docker indisponible → pas d'inspection health."""
        c1 = _make_container_info("c1", "my-app", state="running", status="Up 2 hours")
        c1.ports = [{"IP": "0.0.0.0", "PublicPort": 8080, "PrivatePort": 80, "Type": "tcp"}]

        result = await build_standalone_containers([c1], "local", "Local Docker", False)

        assert len(result) == 1
        container = result[0]
        assert container.name == "my-app"
        assert container.target_id == "local"
        assert container.uptime == "Up 2 hours"
        assert len(container.ports) == 1
        assert container.health_status is None  # Docker pas dispo

    @pytest.mark.asyncio
    async def test_exited_container_no_uptime(self) -> None:
        c1 = _make_container_info("c1", state="exited", status="Exited (0) 3 minutes ago")

        result = await build_standalone_containers([c1], "local", "Local", False)

        assert result[0].uptime is None
        assert result[0].status == "exited"

    @pytest.mark.asyncio
    async def test_with_health_status(self) -> None:
        """Docker disponible → inspection du health status."""
        c1 = _make_container_info("c1", state="running", status="Up 2 hours")

        with patch("app.services.container_builder.DockerClientService") as mock_cls:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.inspect_container.return_value = {
                "State": {"Health": {"Status": "healthy"}},
            }
            mock_cls.return_value = mock_docker

            result = await build_standalone_containers([c1], "local", "Local", True)

        assert len(result) == 1
        assert result[0].health_status == "healthy"
        mock_docker.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_inspection_failure_graceful(self) -> None:
        """Échec d'inspection → health_status=None, pas d'exception."""
        c1 = _make_container_info("c1", state="running", status="Up 2 hours")

        with patch("app.services.container_builder.DockerClientService") as mock_cls:
            mock_docker = AsyncMock()
            mock_docker.ping.return_value = True
            mock_docker.inspect_container.side_effect = Exception("inspect failed")
            mock_cls.return_value = mock_docker

            result = await build_standalone_containers([c1], "local", "Local", True)

        assert result[0].health_status is None
        mock_docker.close.assert_awaited_once()


# =============================================================================
# Tests build_target_groups
# =============================================================================


class TestBuildTargetGroups:
    def test_empty_all(self) -> None:
        result = build_target_groups([], [], [], {})
        assert result == []

    def test_single_target_with_all_types(self) -> None:
        stack = _make_stack_schema(target_id="local")
        discovered = _make_discovered_schema(target_id="local")
        standalone = _make_standalone_schema(target_id="local")

        result = build_target_groups([stack], [discovered], [standalone], {})

        assert len(result) == 1
        group = result[0]
        assert group.target_id == "local"
        assert len(group.stacks) == 1
        assert len(group.discovered) == 1
        assert len(group.standalone) == 1

    def test_multiple_targets(self) -> None:
        s1 = _make_stack_schema(stack_id="s1", target_id="local")
        s2 = _make_stack_schema(stack_id="s2", target_id="remote")

        result = build_target_groups([s1, s2], [], [], {})

        assert len(result) == 2
        target_ids = {g.target_id for g in result}
        assert target_ids == {"local", "remote"}

    def test_technology_from_db_target(self) -> None:
        stack = _make_stack_schema(target_id="t1")
        target = _make_target(target_id="t1", target_type="kubernetes")

        result = build_target_groups([stack], [], [], {"t1": target})

        assert result[0].technology == "kubernetes"

    def test_default_technology_docker(self) -> None:
        stack = _make_stack_schema(target_id="local")
        result = build_target_groups([stack], [], [], {})
        assert result[0].technology == "docker"
