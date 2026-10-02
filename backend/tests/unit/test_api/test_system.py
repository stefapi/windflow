"""Tests unitaires des endpoints système sans authentification (STORY-129).

Couvre (story Tâche 6, spec 09 exemptions, rules 35/40) :
- ``GET /api/v1/system/ready`` **sans header Authorization** → 200,
  body enveloppé ``{"data": ..., "message": null}`` (AC 1 / AC 4) ;
- 503 → corps **nu** ``{status, checks}`` avec causes (arbitrage n°3 :
  pas d'enveloppe sur les 503 système, symétrique du /health racine) ;
- ``GET /api/v1/system/health`` sans auth → 200/503 (contrat historique
  sous le chemin canonique spec 09) ;
- ``GET /health`` racine non régressé : format historique
  ``status/services``, jamais enveloppé.

Le service est mocké (``SystemService.get_readiness``/``get_health``) :
l'objectif est le contrat HTTP (auth, enveloppe, codes), pas les checks
métier (couverts par ``test_system_service.py``). ``patch.object`` sur la
classe couvre les deux références (router et /health racine).
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.services.system_service import SystemService

READY_URL = "/api/v1/system/ready"
SYSTEM_HEALTH_URL = "/api/v1/system/health"

_READY_PAYLOAD = {
    "status": "ready",
    "checks": {
        "database": {"status": "healthy"},
        "migrations": {"status": "ok", "current": "rev1", "head": "rev1"},
    },
}

_UNREADY_PAYLOAD = {
    "status": "unready",
    "checks": {
        "database": {"status": "unhealthy"},
        "migrations": {"status": "pending", "current": None, "head": "rev1"},
    },
}

_HEALTHY_PAYLOAD = {
    "status": "healthy",
    "version": "0.1.0",
    "environment": "development",
    "services": {"database": {"status": "healthy", "type": "sqlite"}},
}


def _unhealthy_payload() -> dict:
    """Payload santé historique avec DB down."""
    return {
        "status": "unhealthy",
        "version": "0.1.0",
        "environment": "development",
        "services": {"database": {"status": "unhealthy", "type": "sqlite"}},
    }


class TestSystemReady:
    """GET /api/v1/system/ready — sonde orchestrateur sans auth."""

    async def test_ready_200_without_authorization_header(self, client: AsyncClient):
        """AC 1/AC 4 : accessible sans token → 200 enveloppé."""
        with patch.object(
            SystemService,
            "get_readiness",
            new=AsyncMock(return_value=(_READY_PAYLOAD, 200)),
        ):
            response = await client.get(READY_URL)  # aucun header d'auth

        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert body["message"] is None
        assert body["data"]["status"] == "ready"
        assert body["data"]["checks"]["migrations"]["status"] == "ok"

    async def test_unready_503_bare_body_with_causes(self, client: AsyncClient):
        """503 → corps NU {status, checks} (pas d'enveloppe) avec causes."""
        with patch.object(
            SystemService,
            "get_readiness",
            new=AsyncMock(return_value=(_UNREADY_PAYLOAD, 503)),
        ):
            response = await client.get(READY_URL)

        assert response.status_code == 503
        body = response.json()
        assert "data" not in body  # arbitrage n°3 : pas d'enveloppe
        assert "error" not in body
        assert body["status"] == "unready"
        assert body["checks"]["database"]["status"] == "unhealthy"
        assert body["checks"]["migrations"]["current"] is None


class TestSystemHealth:
    """GET /api/v1/system/health — chemin canonique spec 09 sans auth."""

    async def test_healthy_200_enveloped_without_auth(self, client: AsyncClient):
        """200 sans token → enveloppe standard + payload historique."""
        with patch.object(
            SystemService,
            "get_health",
            new=AsyncMock(return_value=_HEALTHY_PAYLOAD),
        ):
            response = await client.get(SYSTEM_HEALTH_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "healthy"
        assert body["message"] is None

    async def test_unhealthy_503_bare_body(self, client: AsyncClient):
        """DB down → 503 nu (symétrique du /health racine)."""
        with patch.object(
            SystemService,
            "get_health",
            new=AsyncMock(return_value=_unhealthy_payload()),
        ):
            response = await client.get(SYSTEM_HEALTH_URL)

        assert response.status_code == 503
        body = response.json()
        assert "data" not in body
        assert body["status"] == "unhealthy"


class TestRootHealthNotRegressed:
    """GET /health racine — format historique préservé (non-régression)."""

    async def test_root_health_200_historical_format(self, client: AsyncClient):
        """/health racine : status/services, jamais enveloppé."""
        with patch.object(
            SystemService,
            "get_health",
            new=AsyncMock(return_value=_HEALTHY_PAYLOAD),
        ):
            response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert "data" not in body
        assert "error" not in body
        assert body["status"] == "healthy"
        assert "database" in body["services"]

    async def test_root_health_503_when_db_down(self, client: AsyncClient):
        """DB down → 503 nu (contrat compose/traefik préservé)."""
        with patch.object(
            SystemService,
            "get_health",
            new=AsyncMock(return_value=_unhealthy_payload()),
        ):
            response = await client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert "data" not in body
        assert body["status"] == "unhealthy"
