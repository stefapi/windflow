"""Tests des helpers Prometheus du module WebSocket (STORY-165 — Tâche 9, AC 3).

Couvre ``app/websocket/metrics.py`` (0 % → ≥ 90 %) — tous les helpers
``record_*`` et les context managers de mesure :

- chaque helper incrémente/observe les séries correspondantes dans le
  ``REGISTRY`` global de ``prometheus_client`` ;
- ⚠️ les compteurs sont **cumulatifs globaux** : les assertions portent sur
  des **deltas** (valeur après − valeur avant) pour rester robustes à
  l'exécution des autres tests de la session ;
- les Gauges (connexions/abonnements actifs) vérifient les inc/dec ;
- les Histograms vérifient l'observation des valeurs via les samples
  ``_sum``/``_count`` (delta) ;
- ``MetricsTimer``/``broadcast_timer``/``auth_timer`` appellent la fonction
  recorder avec une durée ≥ 0 (spy).

Le **branchement applicatif** réel de ces helpers reste STORY-172 — ces
tests valident le contrat des helpers eux-mêmes.
"""

from __future__ import annotations

import pytest

# ⚠️ Bug de packaging documenté (STORY-165 Tâche 9, non corrigé — story
# tests-only) : backend/app/websocket/metrics.py importe prometheus_client
# mais la dépendance n'est PAS déclarée dans pyproject.toml (seul un
# override mypy la mentionne). Le module n'est importé nulle part dans le
# code applicatif (couverture 0 % — branchement prévu par STORY-172).
# Si la lib est absente : skip propre plutôt qu'une erreur de collection ;
# l'ajout officiel de la dépendance est à traiter avec STORY-172.
pytest.importorskip(
    "prometheus_client",
    reason="prometheus_client absent des dépendances (voir STORY-172)",
)

from unittest.mock import patch  # noqa: E402

from prometheus_client import REGISTRY  # noqa: E402

from app.websocket import metrics  # noqa: E402


def _counter_value(name: str, labels: dict | None = None) -> float:
    """Valeur actuelle d'un Counter (ou 0 si la série n'existe pas encore)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


def _delta(name: str, labels: dict | None, before: float) -> float:
    """Delta après − avant pour une série Counter."""
    return _counter_value(name, labels) - before


class TestRecordConnection:
    """record_connection : Counter total + Gauge active (inc/dec)."""

    def test_connected_increments_total_and_active(self):
        before_total = _counter_value(
            "windflow_websocket_connections_total",
            {"connection_type": "general", "status": "connected"},
        )
        before_active = _counter_value(
            "windflow_websocket_connections_active",
            {"connection_type": "general"},
        )

        metrics.record_connection("general", "connected")

        assert (
            _delta(
                "windflow_websocket_connections_total",
                {"connection_type": "general", "status": "connected"},
                before_total,
            )
            == 1.0
        )
        assert (
            _counter_value(
                "windflow_websocket_connections_active",
                {"connection_type": "general"},
            )
            - before_active
            == 1.0
        )

    def test_disconnected_increments_total_and_decrements_active(self):
        metrics.record_connection("deployment", "connected")

        before_total = _counter_value(
            "windflow_websocket_connections_total",
            {"connection_type": "deployment", "status": "disconnected"},
        )
        before_active = _counter_value(
            "windflow_websocket_connections_active",
            {"connection_type": "deployment"},
        )

        metrics.record_connection("deployment", "disconnected")

        assert (
            _delta(
                "windflow_websocket_connections_total",
                {"connection_type": "deployment", "status": "disconnected"},
                before_total,
            )
            == 1.0
        )
        assert (
            before_active
            - _counter_value(
                "windflow_websocket_connections_active",
                {"connection_type": "deployment"},
            )
            == 1.0
        )

    def test_other_status_only_increments_total(self):
        """Statut inconnu de la Gauge → seul le Counter total bouge."""
        before_active = _counter_value(
            "windflow_websocket_connections_active", {"connection_type": "user"}
        )

        metrics.record_connection("user", "reconnected")

        assert (
            _counter_value(
                "windflow_websocket_connections_active",
                {"connection_type": "user"},
            )
            == before_active
        )


class TestRecordMessages:
    """record_message_sent / record_message_received."""

    def test_message_sent_success(self):
        labels = {"message_type": "log", "status": "success"}
        before = _counter_value("windflow_websocket_messages_sent_total", labels)

        metrics.record_message_sent("log", success=True)

        assert _delta("windflow_websocket_messages_sent_total", labels, before) == 1.0

    def test_message_sent_error(self):
        labels = {"message_type": "stats", "status": "error"}
        before = _counter_value("windflow_websocket_messages_sent_total", labels)

        metrics.record_message_sent("stats", success=False)

        assert _delta("windflow_websocket_messages_sent_total", labels, before) == 1.0

    def test_message_received(self):
        labels = {"message_type": "ping"}
        before = _counter_value("windflow_websocket_messages_received_total", labels)

        metrics.record_message_received("ping")

        assert (
            _delta("windflow_websocket_messages_received_total", labels, before) == 1.0
        )


class TestRecordBroadcast:
    """record_broadcast : duration + clients observés (Histograms)."""

    def test_broadcast_observes_duration_and_clients(self):
        type_labels = {"broadcast_type": "deployment"}
        duration_name = "windflow_websocket_broadcast_duration_seconds"
        clients_name = "windflow_websocket_broadcast_clients"

        before_duration = _counter_value(f"{duration_name}_sum", type_labels)
        before_count = _counter_value(f"{duration_name}_count", type_labels)
        before_clients = _counter_value(f"{clients_name}_sum", type_labels)

        metrics.record_broadcast("deployment", duration=0.042, client_count=7)

        # STORY-172 : le câblage applicatif écrit désormais de vraies durées
        # dans le même histogramme global (tests broadcasting précédents) —
        # l'égalité flottante stricte sur le delta ``_sum`` devient fragile
        # (somme accumulée), tolérance ``approx`` sur le delta lui-même.
        assert _counter_value(
            f"{duration_name}_sum", type_labels
        ) - before_duration == pytest.approx(0.042)
        assert _delta(f"{duration_name}_count", type_labels, before_count) == 1.0
        assert _counter_value(f"{clients_name}_sum", type_labels) - before_clients == 7


class TestRecordEventsAndPlugins:
    """record_event_dispatch / record_plugin_execution / record_error."""

    def test_event_dispatch_success_and_error(self):
        ok_labels = {"event_type": "DEPLOYMENT_STATUS_CHANGED", "status": "success"}
        ko_labels = {"event_type": "DEPLOYMENT_STATUS_CHANGED", "status": "error"}

        before_ok = _counter_value(
            "windflow_websocket_events_dispatched_total", ok_labels
        )
        before_ko = _counter_value(
            "windflow_websocket_events_dispatched_total", ko_labels
        )

        metrics.record_event_dispatch("DEPLOYMENT_STATUS_CHANGED", success=True)
        metrics.record_event_dispatch("DEPLOYMENT_STATUS_CHANGED", success=False)

        assert (
            _delta("windflow_websocket_events_dispatched_total", ok_labels, before_ok)
            == 1.0
        )
        assert (
            _delta("windflow_websocket_events_dispatched_total", ko_labels, before_ko)
            == 1.0
        )

    def test_plugin_execution_observes_duration(self):
        labels = {"plugin_name": "audit_logger", "event_type": "NOTIFICATION_USER"}
        name = "windflow_websocket_plugin_duration_seconds"

        before_sum = _counter_value(f"{name}_sum", labels)
        before_count = _counter_value(f"{name}_count", labels)

        metrics.record_plugin_execution(
            "audit_logger", "NOTIFICATION_USER", duration=0.25
        )

        # STORY-172 : même durcissement que le broadcast — le câblage applicatif
        # observe de vraies durées dans ce même histogramme global.
        assert _counter_value(f"{name}_sum", labels) - before_sum == pytest.approx(0.25)
        assert _delta(f"{name}_count", labels, before_count) == 1.0

    def test_record_error(self):
        labels = {"error_type": "auth"}
        before = _counter_value("windflow_websocket_errors_total", labels)

        metrics.record_error("auth")

        assert _delta("windflow_websocket_errors_total", labels, before) == 1.0


class TestRecordAuth:
    """record_auth_attempt (success/failed/timeout) / record_auth_duration."""

    def test_auth_attempt_success(self):
        labels = {"status": "success"}
        before = _counter_value("windflow_websocket_auth_attempts_total", labels)

        metrics.record_auth_attempt(success=True)

        assert _delta("windflow_websocket_auth_attempts_total", labels, before) == 1.0

    def test_auth_attempt_failed(self):
        labels = {"status": "failed"}
        before = _counter_value("windflow_websocket_auth_attempts_total", labels)

        metrics.record_auth_attempt(success=False)

        assert _delta("windflow_websocket_auth_attempts_total", labels, before) == 1.0

    def test_auth_attempt_timeout_takes_precedence(self):
        """timeout=True → status 'timeout', même si success=True passé."""
        labels = {"status": "timeout"}
        before = _counter_value("windflow_websocket_auth_attempts_total", labels)

        metrics.record_auth_attempt(success=True, timeout=True)

        assert _delta("windflow_websocket_auth_attempts_total", labels, before) == 1.0

    def test_auth_duration_observed(self):
        name = "windflow_websocket_auth_duration_seconds"
        before_sum = _counter_value(f"{name}_sum")
        before_count = _counter_value(f"{name}_count")

        metrics.record_auth_duration(duration=1.5)

        assert _counter_value(f"{name}_sum") - before_sum == 1.5
        assert _delta(f"{name}_count", None, before_count) == 1.0


class TestRecordSubscription:
    """record_subscription : Counter total + Gauge active (inc/dec)."""

    def test_subscribe_increments_total_and_active(self):
        total_labels = {"subscription_type": "event", "action": "subscribe"}

        metrics.record_subscription("event", "unsubscribe")  # equilibre la Gauge

        before_total = _counter_value(
            "windflow_websocket_subscriptions_total", total_labels
        )
        before_active = _counter_value(
            "windflow_websocket_subscriptions_active",
            {"subscription_type": "event"},
        )

        metrics.record_subscription("event", "subscribe")

        assert (
            _delta("windflow_websocket_subscriptions_total", total_labels, before_total)
            == 1.0
        )
        assert (
            _counter_value(
                "windflow_websocket_subscriptions_active",
                {"subscription_type": "event"},
            )
            - before_active
            == 1.0
        )

    def test_unsubscribe_decrements_active(self):
        metrics.record_subscription("deployment_logs", "subscribe")

        before_active = _counter_value(
            "windflow_websocket_subscriptions_active",
            {"subscription_type": "deployment_logs"},
        )

        metrics.record_subscription("deployment_logs", "unsubscribe")

        assert (
            before_active
            - _counter_value(
                "windflow_websocket_subscriptions_active",
                {"subscription_type": "deployment_logs"},
            )
            == 1.0
        )

    def test_other_action_only_increments_total(self):
        before_active = _counter_value(
            "windflow_websocket_subscriptions_active", {"subscription_type": "event"}
        )

        metrics.record_subscription("event", "resubscribe")

        assert (
            _counter_value(
                "windflow_websocket_subscriptions_active",
                {"subscription_type": "event"},
            )
            == before_active
        )


class TestMetricsTimer:
    """MetricsTimer / broadcast_timer / auth_timer : mesure de durée."""

    def test_timer_calls_recorder_with_positive_duration(self):
        calls: list = []

        def recorder(value: float):
            calls.append(value)

        with metrics.MetricsTimer(recorder):
            pass

        assert len(calls) == 1
        assert calls[0] >= 0.0

    def test_timer_passes_leading_args(self):
        calls: list = []

        def recorder(prefix: str, value: float):
            calls.append((prefix, value))

        with metrics.MetricsTimer(recorder, "p"):
            pass

        assert calls and calls[0][0] == "p"

    def test_timer_calls_recorder_on_exception(self):
        """Le recorder est appelé même si le bloc lève (durée mesurée)."""
        calls: list = []

        def recorder(value: float):
            calls.append(value)

        try:
            with metrics.MetricsTimer(recorder):
                raise RuntimeError("boom")
        except RuntimeError:
            pass

        assert len(calls) == 1
        assert calls[0] >= 0.0

    def test_broadcast_timer_uses_record_broadcast(self):
        """broadcast_timer(type, clients) → record_broadcast(type, clients, durée)."""
        with patch.object(metrics, "record_broadcast") as mock_recorder:
            with metrics.broadcast_timer("deployment", 5):
                pass

        mock_recorder.assert_called_once()
        args = mock_recorder.call_args.args
        assert args[0] == "deployment"
        assert args[1] == 5
        assert args[2] >= 0.0

    def test_auth_timer_uses_record_auth_duration(self):
        with patch.object(metrics, "record_auth_duration") as mock_recorder:
            with metrics.auth_timer():
                pass

        mock_recorder.assert_called_once()
        assert mock_recorder.call_args.args[0] >= 0.0
