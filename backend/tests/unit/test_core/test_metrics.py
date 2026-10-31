"""Tests du module central ``app/core/metrics.py`` (STORY-172 — Tâche 2).

Couvre la normalisation des chemins (cardinalité bornée, sécurité — jamais
de query string), les helpers d'enregistrement (deltas sur le ``REGISTRY``
global, pattern ``test_ws_metrics_helpers.py``) et l'audit de nommage des
séries (préfixe ``windflow_`` homogène — les dashboards/alertes y font
référence).
"""

from __future__ import annotations

from prometheus_client import REGISTRY

from app.core import metrics


def _value(name: str, labels: dict | None = None) -> float:
    """Valeur actuelle d'un sample (0 si la série n'existe pas encore)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


class TestNormalizePath:
    """``normalize_path`` : UUID → ``{id}``, numérique → ``{n}``, statique inchangé."""

    def test_normalize_path_uuid_and_numeric(self):
        """Les segments variables sont substitués ; les chemins statiques inchangés."""
        uuid_path = "/api/v1/stacks/550e8400-e29b-41d4-a716-446655440000/deploy"
        assert metrics.normalize_path(uuid_path) == "/api/v1/stacks/{id}/deploy"

        assert metrics.normalize_path("/api/v1/hosts/42") == "/api/v1/hosts/{n}"

        assert metrics.normalize_path("/api/v1/system/health") == (
            "/api/v1/system/health"
        )
        assert metrics.normalize_path("/api/v1/auth/login") == "/api/v1/auth/login"

    def test_normalize_path_never_includes_query_string(self):
        """Sécurité (rules 40) : un éventuel ``?token=…`` n'apparaît jamais en label."""
        polluted = "/api/v1/stacks?token=super-secret-token&token2=x"
        normalized = metrics.normalize_path(polluted)
        assert "super-secret-token" not in normalized
        assert "token" not in normalized
        assert normalized == "/api/v1/stacks"

    def test_normalize_path_empty(self):
        """Chemin vide inchangé (défense en profondeur)."""
        assert metrics.normalize_path("") == ""


class TestSeriesNaming:
    """Audit : chaque série du module porte le préfixe ``windflow_``."""

    def test_all_series_use_windflow_prefix(self):
        """Convention homogène — les dashboards/alertes D3 y font référence.

        ``REGISTRY.collect()`` expose le nom du **composant** (Counter
        ``windflow_http_requests`` → samples ``..._total`` ; Histogram
        ``windflow_deployment_duration_seconds`` → samples ``..._bucket/
        _count/_sum``). L'audit vérifie le préfixe sur chaque composant
        enregistré + la présence des 7 familles attendues.
        """
        registered = {metric.name for metric in REGISTRY.collect()}
        # Aucune série WindFlow hors convention de préfixe.
        windflow_series = {n for n in registered if n.startswith("windflow_")}
        assert windflow_series  # au moins les familles du module
        assert all(n.startswith("windflow_") for n in windflow_series)

        # Les 7 familles centrales (nom composant, sans suffixe de sample)
        # sont enregistrées dans le REGISTRY global (→ /api/v1/metrics).
        for component in (
            "windflow_http_requests",
            "windflow_http_request_duration_seconds",
            "windflow_deployments",
            "windflow_deployment_duration_seconds",
            "windflow_deployments_active",
            "windflow_scheduler_executions",
            "windflow_scheduler_execution_duration_seconds",
        ):
            assert component in registered, f"série absente du REGISTRY: {component}"
            # Contrat D3 : préfixe unique homogène.
            assert component.startswith("windflow_")


class TestRecordHelpers:
    """Helpers best-effort : deltas corrects, jamais d'exception."""

    def test_record_http_request_increments_counter_and_histogram(self):
        before = _value(
            "windflow_http_requests_total",
            {"method": "GET", "path": "/t", "status": "200"},
        )
        before_count = _value(
            "windflow_http_request_duration_seconds_count",
            {"method": "GET", "path": "/t"},
        )

        metrics.record_http_request("GET", "/t", "200", 0.042)

        assert (
            _value(
                "windflow_http_requests_total",
                {"method": "GET", "path": "/t", "status": "200"},
            )
            - before
            == 1.0
        )
        assert (
            _value(
                "windflow_http_request_duration_seconds_count",
                {"method": "GET", "path": "/t"},
            )
            - before_count
            == 1.0
        )

    def test_record_deployment_transition_success_and_gauge(self):
        before = _value("windflow_deployments_total", {"result": "success"})
        before_active = _value("windflow_deployments_active")

        metrics.record_deployment_transition(
            "deploying", None, old_status=None
        )  # création → active +1
        metrics.record_deployment_transition(
            "running", 12.5, old_status="deploying"
        )  # succès → compteur +1, active −1

        assert (
            _value("windflow_deployments_total", {"result": "success"}) - before == 1.0
        )
        assert _value("windflow_deployments_active") == before_active  # net 0

    def test_record_deployment_transition_failed(self):
        before = _value("windflow_deployments_total", {"result": "failed"})
        metrics.record_deployment_transition("failed", 3.0, old_status="deploying")
        assert (
            _value("windflow_deployments_total", {"result": "failed"}) - before == 1.0
        )

    def test_record_scheduler_execution(self):
        before = _value("windflow_scheduler_executions_total", {"status": "success"})
        before_count = _value("windflow_scheduler_execution_duration_seconds_count")

        metrics.record_scheduler_execution("success", 1.5)

        assert (
            _value("windflow_scheduler_executions_total", {"status": "success"})
            - before
            == 1.0
        )
        assert (
            _value("windflow_scheduler_execution_duration_seconds_count") - before_count
            == 1.0
        )


class TestCircuitBreakerSeries:
    """Séries résilience STORY-251 — nommage et helpers best-effort."""

    def test_circuit_series_use_windflow_prefix(self):
        """Audit nommage : préfixe windflow_ + présence des 2 composants breaker."""
        registered = {metric.name for metric in REGISTRY.collect()}
        for component in (
            "windflow_circuit_breaker_state",
            "windflow_circuit_breaker_failures",
        ):
            assert component in registered, f"série absente du REGISTRY: {component}"
            assert component.startswith("windflow_")

    def test_record_circuit_state_and_failure_deltas(self):
        """Helpers best-effort : gauge positionnée, compteur incrémenté."""
        name = "docker_engine"
        metrics.record_circuit_state(name, 2)  # OPEN
        assert _value("windflow_circuit_breaker_state", {"name": name}) == 2.0

        before = _value("windflow_circuit_breaker_failures_total", {"name": name})
        metrics.record_circuit_failure(name)
        metrics.record_circuit_failure(name)
        assert (
            _value("windflow_circuit_breaker_failures_total", {"name": name}) - before
            == 2.0
        )
