"""Tests de l'endpoint ``GET /api/v1/metrics`` (STORY-172 — Tâche 4, AC 1/AC 2).

Contrat D5 : sans authentification (exemption sondes spec 09 — scrape interne
Docker), format texte Prometheus, non enveloppé (content-type non JSON,
STORY-126), 404 quand ``prometheus_enabled=False`` (les deux états testés).

Client via ``ASGITransport`` (conftest) ; assertions sur le corps de la
réponse (séries présentes après instrumentation réelle via le middleware).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture
def prometheus_enabled():
    """Garantit le flag actif pendant le test (restauré après)."""
    original = settings.prometheus_enabled
    settings.prometheus_enabled = True
    yield
    settings.prometheus_enabled = original


@pytest.fixture
def prometheus_disabled():
    """Force la désactivation de l'instrumentation (restauré après)."""
    original = settings.prometheus_enabled
    settings.prometheus_enabled = False
    yield
    settings.prometheus_enabled = original


async def test_metrics_endpoint_returns_200_without_auth(
    client: AsyncClient, prometheus_enabled
):
    """AC 1 : GET /api/v1/metrics sans token → 200, content-type Prometheus."""
    # Une requête préalable garantit au moins une série HTTP instrumentée.
    await client.get("/api/v1/system/health")

    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "windflow_http_requests_total" in response.text


async def test_metrics_endpoint_format_prometheus_valide(
    client: AsyncClient, prometheus_enabled
):
    """Format d'exposition : lignes ``# HELP``/``# TYPE`` + samples présents."""
    # Un déploiement fictif garantit l'existence des séries métier (label
    # result initialisé à l'import du module core/metrics — Counter avec
    # labels : au moins une série après instrumentation).
    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    body = response.text
    assert "# HELP" in body
    assert "# TYPE" in body
    # Les séries métier (déploiements) sont présentes même à zéro.
    assert "windflow_deployments_total" in body
    assert "windflow_scheduler_executions_total" in body


async def test_metrics_endpoint_disabled_returns_404(
    client: AsyncClient, prometheus_disabled
):
    """AC 2 : ``prometheus_enabled=False`` → 404 (choix documenté D5)."""
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 404


async def test_metrics_endpoint_enabled_returns_metrics(
    client: AsyncClient, prometheus_enabled
):
    """AC 2 : flag à True → 200 (deuxième état — parité avec le 404)."""
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "windflow_" in response.text


async def test_metrics_endpoint_not_wrapped_in_envelope(
    client: AsyncClient, prometheus_enabled
):
    """La réponse n'est PAS au format enveloppe STORY-126 (pas de JSON)."""
    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert "application/json" not in response.headers["content-type"]
    # Un body Prometheus texte ne peut pas contenir la clé d'enveloppe.
    assert '"data"' not in response.text
    assert '"message"' not in response.text


async def test_metrics_endpoint_excludes_websocket_series_when_unused(
    client: AsyncClient, prometheus_enabled
):
    """Contrat de non-pollution : les compteurs WS non sollicités n'apparaissent pas.

    prometheus_client n'expose un Counter avec labels **qu'une fois une
    combinaison de labels observée**. Dans une session de tests partagée,
    d'autres fichiers peuvent avoir initialisé des labels WS — on vérifie
    donc le contrat sur une combinaison jamais sollicitée (le timeout
    d'authentification WS, réservé au helper ``record_auth_attempt(timeout)``).
    """
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    # Le label "timeout" des tentatives d'auth WS n'est utilisé nulle part :
    # cette combinaison ne peut pas avoir été initialisée par le câblage.
    assert 'windflow_websocket_auth_attempts_total{status="timeout"}' not in (
        response.text
    )
    assert 'windflow_websocket_errors_total{error_type="disconnect"}' not in (
        response.text
    )
