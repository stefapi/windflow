"""Tests du socle WorkloadAdapter — contrat ABC + types (STORY-174.1, AC 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.enums.workload import WorkloadFamily
from app.schemas.workloads import (
    AppComponent,
    ContextualAction,
    HealthStatus,
    NativeConfig,
    TechnicalComponent,
    WorkloadMetrics,
)
from app.services.workloads.base import AppAdapter, WorkloadAdapter


class TestWorkloadFamily:
    def test_workload_family_values(self):
        """Enum canonique spec 02 : app/machine/host/cluster."""
        assert WorkloadFamily.APP.value == "app"
        assert WorkloadFamily.MACHINE.value == "machine"
        assert WorkloadFamily.HOST.value == "host"
        assert WorkloadFamily.CLUSTER.value == "cluster"


class TestWorkloadAdapterABC:
    def test_workload_adapter_cannot_instantiate(self):
        """ABC : instanciation directe impossible."""
        with pytest.raises(TypeError):
            WorkloadAdapter()  # type: ignore[abstract]

    def test_app_adapter_missing_method_rejected(self):
        """Sous-classe incomplète (méthode manquante) → TypeError."""

        class _Incomplete(AppAdapter):
            def family(self):
                return WorkloadFamily.APP

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]


class TestSchemas:
    def test_workload_metrics_schema_roundtrip(self):
        """Schéma valide avec les champs spec 02."""
        m = WorkloadMetrics(
            cpu_percent=12.5,
            memory_used=540,
            memory_limit=1073,
            network_rx=10,
            network_tx=5,
        )
        assert m.cpu_percent == 12.5
        dumped = m.model_dump()
        assert dumped["memory_limit"] == 1073

    def test_workload_metrics_rejects_negative(self):
        """Validation : bornes ge=0."""
        with pytest.raises(ValidationError):
            WorkloadMetrics(cpu_percent=-1, memory_used=0, memory_limit=0)

    def test_health_status_literal(self):
        """Statut de santé borné (healthy/unhealthy/starting/unknown)."""
        assert HealthStatus(status="healthy").status == "healthy"
        with pytest.raises(ValidationError):
            HealthStatus(status="boom")

    def test_contextual_action_danger_flag_default_false(self):
        """Danger=False par défaut (confirmation UI seulement si explicite)."""
        a = ContextualAction(id="x", label="X", section="lifecycle")
        assert a.danger is False

    def test_native_config_formats(self):
        """Formats bornés compose/json/xml/yaml."""
        assert NativeConfig(format="json", content="{}").format == "json"
        with pytest.raises(ValidationError):
            NativeConfig(format="toml", content="")

    def test_app_component_and_technical_component(self):
        """Composants applicatifs et techniques."""
        assert AppComponent(name="web", status="running").image is None
        assert TechnicalComponent(kind="container", name="c", status="running").status

    def test_app_open_url_nullable(self):
        from app.schemas.workloads import AppOpenUrl

        assert AppOpenUrl(url=None).url is None
        assert AppOpenUrl(url="http://localhost:8080").url.endswith("8080")
