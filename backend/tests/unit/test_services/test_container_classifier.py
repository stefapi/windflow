"""
Tests unitaires pour container_classifier.py.

Logique pure de classification par labels — aucun mock, aucun async.
Les ContainerInfo sont simulés via des MagicMock légers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.container_classifier import (
    LABEL_COMPOSE_PROJECT,
    LABEL_WINDFLOW_MANAGED,
    LABEL_WINDFLOW_STACK_ID,
    classify_containers,
    is_compose_project,
    is_windflow_managed,
)

# =============================================================================
# Helpers
# =============================================================================


def _make_container(labels: dict | None = None) -> MagicMock:
    """Crée un ContainerInfo mocké avec les labels donnés."""
    c = MagicMock()
    c.labels = labels or {}
    return c


# =============================================================================
# Tests is_windflow_managed
# =============================================================================


class TestIsWindflowManaged:
    def test_true_lowercase(self) -> None:
        assert is_windflow_managed({"windflow.managed": "true"}) is True

    def test_true_mixed_case(self) -> None:
        assert is_windflow_managed({"windflow.managed": "True"}) is True
        assert is_windflow_managed({"windflow.managed": "TRUE"}) is True

    def test_false_value(self) -> None:
        assert is_windflow_managed({"windflow.managed": "false"}) is False

    def test_missing_label(self) -> None:
        assert is_windflow_managed({}) is False

    def test_unrelated_labels(self) -> None:
        assert is_windflow_managed({"com.docker.compose.project": "myapp"}) is False


# =============================================================================
# Tests is_compose_project
# =============================================================================


class TestIsComposeProject:
    def test_present(self) -> None:
        assert is_compose_project({"com.docker.compose.project": "myapp"}) is True

    def test_missing(self) -> None:
        assert is_compose_project({}) is False

    def test_empty_string_is_still_present(self) -> None:
        """Le label existe mais est vide — toujours détecté comme Compose."""
        assert is_compose_project({"com.docker.compose.project": ""}) is True


# =============================================================================
# Tests classify_containers
# =============================================================================


class TestClassifyContainers:
    def test_empty_list(self) -> None:
        managed, discovered, standalone = classify_containers([])
        assert managed == {}
        assert discovered == {}
        assert standalone == []

    def test_single_windflow_managed(self) -> None:
        c = _make_container(
            {LABEL_WINDFLOW_MANAGED: "true", LABEL_WINDFLOW_STACK_ID: "stack-1"}
        )
        managed, discovered, standalone = classify_containers([c])
        assert "stack-1" in managed
        assert len(managed["stack-1"]) == 1
        assert discovered == {}
        assert standalone == []

    def test_single_compose(self) -> None:
        c = _make_container({LABEL_COMPOSE_PROJECT: "myapp"})
        managed, discovered, standalone = classify_containers([c])
        assert managed == {}
        assert "myapp" in discovered
        assert len(discovered["myapp"]) == 1
        assert standalone == []

    def test_single_standalone(self) -> None:
        c = _make_container({})
        managed, discovered, standalone = classify_containers([c])
        assert managed == {}
        assert discovered == {}
        assert len(standalone) == 1

    def test_windflow_priority_over_compose(self) -> None:
        """Un container avec les deux labels est classé WindFlow."""
        labels = {
            LABEL_WINDFLOW_MANAGED: "true",
            LABEL_WINDFLOW_STACK_ID: "stack-x",
            LABEL_COMPOSE_PROJECT: "myproject",
        }
        c = _make_container(labels)
        managed, discovered, standalone = classify_containers([c])
        assert "stack-x" in managed
        assert discovered == {}
        assert standalone == []

    def test_multiple_stacks(self) -> None:
        c1 = _make_container(
            {LABEL_WINDFLOW_MANAGED: "true", LABEL_WINDFLOW_STACK_ID: "s1"}
        )
        c2 = _make_container(
            {LABEL_WINDFLOW_MANAGED: "true", LABEL_WINDFLOW_STACK_ID: "s2"}
        )
        c3 = _make_container(
            {LABEL_WINDFLOW_MANAGED: "true", LABEL_WINDFLOW_STACK_ID: "s1"}
        )
        managed, _, _ = classify_containers([c1, c2, c3])
        assert len(managed["s1"]) == 2
        assert len(managed["s2"]) == 1

    def test_multiple_compose_projects(self) -> None:
        c1 = _make_container({LABEL_COMPOSE_PROJECT: "proj-a"})
        c2 = _make_container({LABEL_COMPOSE_PROJECT: "proj-b"})
        c3 = _make_container({LABEL_COMPOSE_PROJECT: "proj-a"})
        _, discovered, _ = classify_containers([c1, c2, c3])
        assert len(discovered["proj-a"]) == 2
        assert len(discovered["proj-b"]) == 1

    def test_mixed_classification(self) -> None:
        """Containers répartis dans les 3 catégories."""
        containers = [
            _make_container(
                {LABEL_WINDFLOW_MANAGED: "true", LABEL_WINDFLOW_STACK_ID: "s1"}
            ),
            _make_container({LABEL_COMPOSE_PROJECT: "proj"}),
            _make_container({}),
            _make_container(
                {LABEL_WINDFLOW_MANAGED: "true", LABEL_WINDFLOW_STACK_ID: "s1"}
            ),
            _make_container({}),
        ]
        managed, discovered, standalone = classify_containers(containers)
        assert len(managed["s1"]) == 2
        assert len(discovered["proj"]) == 1
        assert len(standalone) == 2

    def test_unknown_stack_id_for_managed_without_label(self) -> None:
        """Un container managé sans stack_id → groupé sous 'unknown'."""
        c = _make_container({LABEL_WINDFLOW_MANAGED: "true"})
        managed, _, _ = classify_containers([c])
        assert "unknown" in managed
