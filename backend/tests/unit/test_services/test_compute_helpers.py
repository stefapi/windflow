"""
Tests unitaires pour compute_helpers.py.

Fonctions pures : formatage mémoire, parsing de ports,
extraction d'uptime et filtrage des vues compute.
Aucun mock nécessaire — tests déterministes et rapides.
"""

from __future__ import annotations

import pytest

from app.helper.compute_helpers import (
    apply_filters,
    extract_uptime,
    format_memory,
    parse_ports,
)
from app.schemas.compute import (
    ContainerPortMapping,
    DiscoveredItem,
    StandaloneContainer,
    StackWithServices,
    ServiceWithMetrics,
)


# =============================================================================
# Helpers — construction d'objets domaine pour les tests de filtrage
# =============================================================================


def _make_stack(
    stack_id: str = "s1",
    name: str = "my-stack",
    status: str = "running",
    target_id: str = "local",
    technology: str = "windflow",
) -> StackWithServices:
    return StackWithServices(
        id=stack_id,
        name=name,
        technology=technology,
        target_id=target_id,
        target_name="Local Docker",
        services_total=1,
        services_running=1 if status == "running" else 0,
        status=status,  # type: ignore[arg-type]
        services=[
            ServiceWithMetrics(
                id="svc1", name="svc", image="nginx",
                status="running", cpu_percent=0.0, memory_usage="0M",
            )
        ],
    )


def _make_discovered(
    item_id: str = "d1",
    name: str = "my-proj",
    target_id: str = "local",
    technology: str = "docker-compose",
    detected_at: str = "2026-01-01T00:00:00Z",
) -> DiscoveredItem:
    return DiscoveredItem(
        id=item_id,
        name=name,
        type="composition",
        technology=technology,
        source_path=None,
        target_id=target_id,
        target_name="Local Docker",
        services_total=1,
        services_running=1,
        detected_at=detected_at,
        adoptable=True,
        services=[],
    )


def _make_standalone(
    container_id: str = "c1",
    name: str = "my-container",
    status: str = "running",
    target_id: str = "local",
) -> StandaloneContainer:
    return StandaloneContainer(
        id=container_id,
        name=name,
        image="nginx",
        target_id=target_id,
        target_name="Local Docker",
        status=status,  # type: ignore[arg-type]
        cpu_percent=0.0,
        memory_usage="0M",
        uptime="Up 2 hours" if status == "running" else None,
        ports=[],
        health_status=None,
    )


# =============================================================================
# Tests format_memory
# =============================================================================


class TestFormatMemory:
    def test_zero(self) -> None:
        assert format_memory(0) == "0M"

    def test_negative(self) -> None:
        assert format_memory(-100) == "0M"

    def test_kilobytes(self) -> None:
        result = format_memory(512 * 1024)
        assert result == "512K"

    def test_megabytes(self) -> None:
        result = format_memory(100 * 1024 * 1024)
        assert result == "100M"

    def test_gigabytes(self) -> None:
        result = format_memory(2 * 1024 * 1024 * 1024)
        assert result == "2.0G"

    def test_exactly_one_gb(self) -> None:
        result = format_memory(1024 * 1024 * 1024)
        assert result == "1.0G"

    def test_small_bytes(self) -> None:
        """Quelques bytes sont arrondis en K."""
        result = format_memory(1024)
        assert result == "1K"


# =============================================================================
# Tests parse_ports
# =============================================================================


class TestParsePorts:
    def test_empty_list(self) -> None:
        assert parse_ports([]) == []

    def test_full_port_mapping(self) -> None:
        data = [{"IP": "0.0.0.0", "PublicPort": 8080, "PrivatePort": 80, "Type": "tcp"}]
        result = parse_ports(data)
        assert len(result) == 1
        assert result[0] == ContainerPortMapping(
            host_ip="0.0.0.0", host_port=8080, container_port=80, protocol="tcp",
        )

    def test_filters_incomplete_ports(self) -> None:
        """Ports sans PublicPort ou PrivatePort sont ignorés."""
        data = [
            {"PrivatePort": 80, "Type": "tcp"},  # pas de PublicPort
            {"PublicPort": 8080, "Type": "tcp"},  # pas de PrivatePort
            {"PublicPort": 0, "PrivatePort": 80, "Type": "tcp"},  # PublicPort=0 = falsy
        ]
        assert parse_ports(data) == []

    def test_multiple_ports(self) -> None:
        data = [
            {"IP": "0.0.0.0", "PublicPort": 8080, "PrivatePort": 80, "Type": "tcp"},
            {"IP": "::", "PublicPort": 443, "PrivatePort": 443, "Type": "tcp"},
        ]
        result = parse_ports(data)
        assert len(result) == 2
        assert result[1].host_ip == "::"

    def test_default_ip_and_protocol(self) -> None:
        """IP et Type manquants → valeurs par défaut."""
        data = [{"PublicPort": 3000, "PrivatePort": 3000}]
        result = parse_ports(data)
        assert result[0].host_ip == "0.0.0.0"
        assert result[0].protocol == "tcp"


# =============================================================================
# Tests extract_uptime
# =============================================================================


class TestExtractUptime:
    def test_up_status(self) -> None:
        assert extract_uptime("Up 2 hours") == "Up 2 hours"

    def test_up_seconds(self) -> None:
        assert extract_uptime("Up 30 seconds") == "Up 30 seconds"

    def test_exited_returns_none(self) -> None:
        assert extract_uptime("Exited (0) 3 minutes ago") is None

    def test_empty_string(self) -> None:
        assert extract_uptime("") is None

    def test_created_returns_none(self) -> None:
        assert extract_uptime("Created") is None


# =============================================================================
# Tests apply_filters
# =============================================================================


class TestApplyFilters:
    def test_no_filters_returns_all(self) -> None:
        stacks = [_make_stack()]
        discovered = [_make_discovered()]
        standalone = [_make_standalone()]

        rs, rd, rc = apply_filters(stacks, discovered, standalone)

        assert rs == stacks
        assert rd == discovered
        assert rc == standalone

    def test_type_filter_managed(self) -> None:
        stacks = [_make_stack()]
        discovered = [_make_discovered()]
        standalone = [_make_standalone()]

        rs, rd, rc = apply_filters(stacks, discovered, standalone, type_filter="managed")

        assert rs == stacks
        assert rd == []
        assert rc == []

    def test_type_filter_discovered(self) -> None:
        stacks = [_make_stack()]
        discovered = [_make_discovered()]
        standalone = [_make_standalone()]

        rs, rd, rc = apply_filters(stacks, discovered, standalone, type_filter="discovered")

        assert rs == []
        assert rd == discovered
        assert rc == []

    def test_type_filter_standalone(self) -> None:
        stacks = [_make_stack()]
        discovered = [_make_discovered()]
        standalone = [_make_standalone()]

        rs, rd, rc = apply_filters(stacks, discovered, standalone, type_filter="standalone")

        assert rs == []
        assert rd == []
        assert rc == standalone

    def test_search_filter_case_insensitive(self) -> None:
        stacks = [_make_stack(name="Nginx-Stack"), _make_stack(stack_id="s2", name="Redis")]
        discovered = [_make_discovered(name="nginx-proj")]
        standalone = [_make_standalone(name="Redis-standalone")]

        rs, rd, rc = apply_filters(stacks, discovered, standalone, search="nginx")

        assert len(rs) == 1
        assert rs[0].name == "Nginx-Stack"
        assert len(rd) == 1
        assert rd[0].name == "nginx-proj"
        assert len(rc) == 0

    def test_status_filter(self) -> None:
        stacks = [
            _make_stack(stack_id="s1", status="running"),
            _make_stack(stack_id="s2", status="stopped"),
        ]
        standalone = [
            _make_standalone(container_id="c1", status="running"),
            _make_standalone(container_id="c2", status="stopped"),
        ]

        rs, _, rc = apply_filters(stacks, [], standalone, status_filter="running")

        assert len(rs) == 1
        assert rs[0].id == "s1"
        assert len(rc) == 1
        assert rc[0].id == "c1"

    def test_target_id_filter(self) -> None:
        stacks = [
            _make_stack(stack_id="s1", target_id="local"),
            _make_stack(stack_id="s2", target_id="remote"),
        ]
        discovered = [_make_discovered(target_id="local")]

        rs, rd, _ = apply_filters(stacks, discovered, [], target_id_filter="local")

        assert len(rs) == 1
        assert rs[0].id == "s1"
        assert len(rd) == 1

    def test_technology_filter(self) -> None:
        stacks = [
            _make_stack(stack_id="s1", technology="windflow"),
            _make_stack(stack_id="s2", technology="docker-compose"),
        ]
        discovered = [_make_discovered(technology="docker-compose")]

        rs, rd, _ = apply_filters(stacks, discovered, [], technology="docker-compose")

        assert len(rs) == 1
        assert rs[0].id == "s2"
        assert len(rd) == 1

    def test_combined_filters(self) -> None:
        """Filtres combinés : type + status + target."""
        stacks = [
            _make_stack(stack_id="s1", status="running", target_id="local"),
            _make_stack(stack_id="s2", status="stopped", target_id="local"),
        ]
        standalone = [_make_standalone(status="running", target_id="local")]

        rs, _, rc = apply_filters(
            stacks, [], standalone,
            type_filter="managed",
            status_filter="running",
            target_id_filter="local",
        )

        assert len(rs) == 1
        assert rs[0].id == "s1"
        assert rc == []  # type=managed → standalone vidé
