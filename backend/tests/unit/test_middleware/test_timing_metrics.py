"""Tests de l'instrumentation HTTP du middleware Timing (STORY-172 — Tâche 3, AC 1/AC 5).

Vérifie les deltas de séries ``windflow_http_*`` via le ``REGISTRY`` global
après des requêtes réelles (client ``ASGITransport``) : compteur par
method/path normalisé/status, histogramme de latence, capture des 500 via
le wrap try/except (re-raise inchangé), exclusion du scrape, non-régression
du header ``X-Process-Time`` et flag-gating ``prometheus_enabled``.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from prometheus_client import REGISTRY

from app.config import settings


def _value(name: str, labels: dict | None = None) -> float:
    """Valeur actuelle d'un sample (0 si la série n'existe pas encore)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


@pytest.fixture
def prometheus_enabled():
    original = settings.prometheus_enabled
    settings.prometheus_enabled = True
    yield
    settings.prometheus_enabled = original


@pytest.fixture
def prometheus_disabled():
    original = settings.prometheus_enabled
    settings.prometheus_enabled = False
    yield
    settings.prometheus_enabled = original


async def test_http_request_records_latency_and_status(
    client: AsyncClient, prometheus_enabled
):
    """Une requête via le client → delta +1 compteur et +1 _count histogramme.

    Le statut réel observé est utilisé pour le label (le health check peut
    légitimement répondre 503 sur une base vide — seul le comptage importe).
    """
    probe = await client.get("/api/v1/system/health")
    status_label = str(probe.status_code)

    labels = {
        "method": "GET",
        "path": "/api/v1/system/health",
        "status": status_label,
    }
    before = _value("windflow_http_requests_total", labels)
    before_count = _value(
        "windflow_http_request_duration_seconds_count",
        {"method": "GET", "path": "/api/v1/system/health"},
    )

    response = await client.get("/api/v1/system/health")
    assert response.status_code == probe.status_code

    assert _value("windflow_http_requests_total", labels) - before == 1.0
    assert (
        _value(
            "windflow_http_request_duration_seconds_count",
            {"method": "GET", "path": "/api/v1/system/health"},
        )
        - before_count
        == 1.0
    )


async def test_http_request_path_normalization(client: AsyncClient, prometheus_enabled):
    """Un chemin à UUID → label ``{id}`` (cardinalité bornée — deux UUIDs = une série).

    Le statut réel (404 ou 500 selon le mode auth dev) est capturé au probe
    pour construire le label — seule la normalisation du chemin est assertée.
    """
    probe = await client.get(f"/api/v1/stacks/{uuid.uuid4()}")
    normalized_labels = {
        "method": "GET",
        "path": "/api/v1/stacks/{id}",
        "status": str(probe.status_code),
    }
    before = _value("windflow_http_requests_total", normalized_labels)

    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    await client.get(f"/api/v1/stacks/{first}")
    await client.get(f"/api/v1/stacks/{second}")

    # Les deux requêtes tombent sur UNE série normalisée.
    assert _value("windflow_http_requests_total", normalized_labels) - before == 2.0


async def test_http_request_500_recorded(client: AsyncClient, prometheus_enabled):
    """Une requête qui lève → compté ``status="500"`` avant l'error handler.

    Route de test : un stack_id mal formé fait lever la validation Pydantic
    côté endpoint ; le middleware compte l'exception puis la re-lève
    (l'error handler central produit la réponse finale — jamais 200).
    """
    from unittest.mock import patch

    labels_500 = {"method": "GET", "path": "/api/v1/system/health", "status": "500"}
    before = _value("windflow_http_requests_total", labels_500)

    with patch(
        "app.services.system_service.SystemService.get_health",
        side_effect=RuntimeError("boom instrumentation test"),
    ):
        response = await client.get("/api/v1/system/health")

    # Le error handler central convertit en 500 — et le middleware a compté.
    assert response.status_code == 500
    assert _value("windflow_http_requests_total", labels_500) - before == 1.0


async def test_http_metrics_skip_metrics_endpoint(
    client: AsyncClient, prometheus_enabled
):
    """Le scrape ``/api/v1/metrics`` ne s'incrémente pas lui-même."""
    labels = {
        "method": "GET",
        "path": "/api/v1/metrics",
        "status": "200",
    }
    before = _value("windflow_http_requests_total", labels)

    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200

    assert _value("windflow_http_requests_total", labels) == before


async def test_http_metrics_disabled_when_flag_off(
    client: AsyncClient, prometheus_disabled
):
    """``prometheus_enabled=False`` → middleware no-op métrique (delta 0)."""
    probe = await client.get("/api/v1/system/health")
    labels = {
        "method": "GET",
        "path": "/api/v1/system/health",
        "status": str(probe.status_code),
    }
    before = _value("windflow_http_requests_total", labels)
    before_count = _value(
        "windflow_http_request_duration_seconds_count",
        {"method": "GET", "path": "/api/v1/system/health"},
    )

    response = await client.get("/api/v1/system/health")
    assert response.status_code == probe.status_code

    assert _value("windflow_http_requests_total", labels) == before
    assert (
        _value(
            "windflow_http_request_duration_seconds_count",
            {"method": "GET", "path": "/api/v1/system/health"},
        )
        == before_count
    )


async def test_timing_header_still_present(client: AsyncClient, prometheus_enabled):
    """AC 5 : ``X-Process-Time`` présent sur toutes les réponses (non-régression).

    Comportement préexistant conservé : le logging middleware (monté après
    timing dans la pile) réécrit le header en secondes brutes — seul le
    contrat de présence importe ici (aucune régression d'header).
    """
    response = await client.get("/api/v1/system/health")
    assert response.status_code in (200, 503)  # healthy ou unhealthy — header partout
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"].removesuffix("ms")) >= 0.0
