"""Tests unitaires du service `get_compute_browse` (STORY-173, AC 1).

Aplatissement paginé/filtrable de l'inventaire — réutilise le chemin de
`get_compute_global` (classification, builders, `apply_filters`), Docker
systématiquement mocké (pattern `test_compute_service.py`).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import compute_service
from app.services.compute_service import get_compute_browse


def _svc(docker_available: bool = True, containers: list | None = None):
    """Client Docker factice (pattern test_compute_service)."""
    client = AsyncMock()
    client.ping.return_value = docker_available
    client.list_containers.return_value = containers or []
    client.close = AsyncMock()
    client.inspect_container = AsyncMock(return_value={})
    return client


def _managed_container(name: str, stack_id: str, state: str = "running"):
    """ContainerInfo managé WindFlow (labels windflow.*)."""
    return SimpleNamespace(
        id=f"cid-{name}",
        name=name,
        image="nginx:latest",
        image_id="sha256:abc",
        command="nginx",
        created=0,
        state=state,
        status="Up 2 hours" if state == "running" else "Exited (0)",
        ports=[],
        labels={
            "windflow.managed": "true",
            "windflow.stack_id": stack_id,
        },
        networks=[],
        mounts=[],
        restart_count=0,
    )


def _discovered_container(name: str, project: str, state: str = "running"):
    """ContainerInfo découvert (label compose, sans label WindFlow)."""
    return SimpleNamespace(
        id=f"cid-{name}",
        name=name,
        image="redis:7",
        image_id="sha256:def",
        command="redis",
        created=0,
        state=state,
        status="Up 1 hour",
        ports=[],
        labels={"com.docker.compose.project": project},
        networks=[],
        mounts=[],
        restart_count=0,
    )


def _standalone_container(name: str, state: str = "running"):
    """ContainerInfo standalone (aucun label)."""
    return SimpleNamespace(
        id=f"cid-{name}",
        name=name,
        image="busybox:1.37",
        image_id="sha256:123",
        command="sleep",
        created=0,
        state=state,
        status="Up 5 minutes",
        ports=[],
        labels={},
        networks=[],
        mounts=[],
        restart_count=0,
    )


@pytest.fixture
async def seeded_stack(db_session, test_organization):
    """Stack DB managée sans deployment (target locale par défaut)."""
    from app.models.stack import Stack

    stack = Stack(
        name="managed-app",
        description="stack de test browse",
        template={"version": "3.8", "services": {"web": {"image": "nginx"}}},
        variables={},
        organization_id=test_organization.id,
    )
    db_session.add(stack)
    await db_session.commit()
    await db_session.refresh(stack)
    return stack


async def test_browse_flattens_all_kinds(db_session, seeded_stack):
    """Inventaire managé + découvert + standalone → items aplatis kind correct."""
    containers = [
        _managed_container("web-1", seeded_stack.id),
        _discovered_container("ext-redis", "ext-project"),
        _standalone_container("loose-tool"),
    ]
    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(True, containers)
    ):
        result = await get_compute_browse(db_session, [seeded_stack.organization_id])

    kinds = {(item.kind, item.name) for item in result.data}
    assert ("managed_service", "web-1") in kinds
    assert ("discovered", "ext-project") in kinds
    assert ("standalone", "loose-tool") in kinds


async def test_browse_applies_filters_type_status_search(db_session, seeded_stack):
    """Chaque filtre réduit la liste aplatie (réutilise apply_filters)."""
    containers = [
        _managed_container("web-1", seeded_stack.id),
        _standalone_container("loose-tool"),
        _standalone_container("dead-tool", state="exited"),
    ]
    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(True, containers)
    ):
        # Filtre type : standalone uniquement
        result = await get_compute_browse(
            db_session, [seeded_stack.organization_id], type_filter="standalone"
        )
    names = [item.name for item in result.data]
    assert "web-1" not in names
    assert set(names) == {"loose-tool", "dead-tool"}

    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(True, containers)
    ):
        # Filtre statut (containers standalone : stateExited → exited)
        result = await get_compute_browse(
            db_session, [seeded_stack.organization_id], status_filter="exited"
        )
    assert [item.name for item in result.data] == ["dead-tool"]

    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(True, containers)
    ):
        # Recherche libre
        result = await get_compute_browse(
            db_session, [seeded_stack.organization_id], search="loose"
        )
    assert [item.name for item in result.data] == ["loose-tool"]


async def test_browse_pagination_slicing(db_session, seeded_stack):
    """Slicing paginate_sequence exact ; page au-delà → data: [] + métadonnées.

    L'inventaire contient l'item stack managée (aucun container actif →
    item au niveau stack, en tête) + 5 standalone = 6 items.
    """
    containers = [_standalone_container(f"tool-{i}") for i in range(5)]
    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(True, containers)
    ):
        result = await get_compute_browse(
            db_session, [seeded_stack.organization_id], page=2, per_page=2
        )
    assert [item.name for item in result.data] == ["tool-1", "tool-2"]
    assert result.pagination.total == 6
    assert result.pagination.pages == 3

    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(True, containers)
    ):
        result = await get_compute_browse(
            db_session, [seeded_stack.organization_id], page=9, per_page=2
        )
    assert result.data == []
    assert result.pagination.total == 6


async def test_browse_graceful_degradation_docker_down(db_session, seeded_stack):
    """Docker indisponible → stacks DB seules, pas d'exception."""
    with patch.object(
        compute_service, "DockerClientService", return_value=_svc(False, [])
    ):
        result = await get_compute_browse(db_session, [seeded_stack.organization_id])

    # La stack managée sans container apparaît comme item managed_service
    kinds = [item.kind for item in result.data]
    assert "managed_service" in kinds
    assert "discovered" not in kinds
    assert "standalone" not in kinds
