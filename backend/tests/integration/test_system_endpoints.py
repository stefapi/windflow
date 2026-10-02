"""Tests d'intégration des endpoints système (STORY-129).

Contrat de bout en bout sans auth via ``client`` (ASGITransport), base
de test réelle (schéma appliqué par les migrations Alembic — la table
``alembic_version`` existe donc, avec ``current == head``) :

- ``GET /api/v1/system/ready`` sans auth → 200 **enveloppé** (helper
  ``unwrap`` du conftest) avec DB réelle saine ;
- header ``X-Correlation-ID`` propagé ;
- ``GET /health`` racine toujours **non enveloppé** (garde-fou
  STORY-126 étendu aux nouveaux chemins système — le ``/health`` racine
  et le 503 système restent nus) ;
- ``GET /api/v1/system/health`` sans auth → 200 enveloppé.

Note anti-fingerprinting (AC 4) : contrairement au ``/health`` racine
historique (qui expose ``version``/``environment`` — contrat préservé),
le payload de readiness ne contient ni l'un ni l'autre.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.conftest import unwrap

from app.services import system_service as system_service_module

READY_URL = "/api/v1/system/ready"
SYSTEM_HEALTH_URL = "/api/v1/system/health"


@pytest.fixture(autouse=True)
def _real_test_db(monkeypatch, test_db_engine: AsyncEngine) -> None:
    """Branche le service système sur l'engine de test (DB « réelle »).

    Hors lifespan (client ASGI sans startup), la ``Database`` globale
    n'est jamais connectée (``db.engine is None``) — tous les checks DB
    répondraient unhealthy/503. On pointe le ``db`` du module service
    vers l'engine de la base de test (schéma appliqué par les migrations,
    ``alembic_version`` à ``head``) : les checks métier s'exécutent
    réellement, y compris la comparaison migrations current == head.
    """
    from app.database import Database

    wired = Database()
    wired.engine = test_db_engine
    monkeypatch.setattr(system_service_module, "db", wired)


class TestSystemReadyIntegration:
    """Readiness bout en bout — DB réelle migrée, sans auth."""

    async def test_ready_200_enveloped_on_migrated_db(self, client: AsyncClient):
        """Base de test migrée (current == head) → 200 prêt, enveloppé."""
        response = await client.get(READY_URL)  # aucun header d'auth
        assert response.status_code == 200

        data = unwrap(response)
        assert data["status"] == "ready"
        assert data["checks"]["database"]["status"] == "healthy"
        # Migrations : la base de test provient du template migré par
        # `alembic upgrade head` → current == head
        assert data["checks"]["migrations"]["status"] == "ok"
        assert data["checks"]["migrations"]["current"] is not None
        assert (
            data["checks"]["migrations"]["current"]
            == data["checks"]["migrations"]["head"]
        )
        # Redis non configuré en test → check absent
        assert "redis" not in data["checks"]

    async def test_ready_payload_no_fingerprint(self, client: AsyncClient):
        """AC 4 : pas de version ni environnement dans /ready."""
        response = await client.get(READY_URL)
        assert response.status_code == 200
        data = unwrap(response)
        assert "version" not in data
        assert "environment" not in data

    async def test_ready_correlation_id_propagated(self, client: AsyncClient):
        """X-Correlation-ID envoyé → même valeur en réponse (rules 45)."""
        response = await client.get(
            READY_URL, headers={"X-Correlation-ID": "ready-corr-129"}
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == "ready-corr-129"


class TestSystemHealthIntegration:
    """Santé bout en bout sous le chemin canonique spec 09."""

    async def test_system_health_200_enveloped(self, client: AsyncClient):
        """/api/v1/system/health sans auth → 200 enveloppé, DB saine."""
        response = await client.get(SYSTEM_HEALTH_URL)
        assert response.status_code == 200

        data = unwrap(response)
        assert data["status"] == "healthy"
        assert data["services"]["database"]["status"] == "healthy"

    async def test_root_health_not_enveloped(self, client: AsyncClient):
        """Garde-fou : /health racine reste nu (compose/traefik/tests)."""
        response = await client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert "data" not in body
        assert "error" not in body
        assert body["status"] == "healthy"
        assert "database" in body["services"]
        # Contrat historique : version/environnement exposés (préservé)
        assert "version" in body
        assert "environment" in body


class TestSystemOpenApiContract:
    """OpenAPI : les nouveaux chemins et tag sont documentés (rules 20)."""

    async def test_openapi_declares_system_paths_and_tag(self, client: AsyncClient):
        """Paths /system/health + /system/ready et tag system présents."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        assert "/api/v1/system/health" in schema["paths"]
        assert "/api/v1/system/ready" in schema["paths"]
        assert "/api/v1/auth/password" in schema["paths"]

        tags = {tag["name"] for tag in schema.get("tags", [])}
        assert "system" in tags

    async def test_openapi_password_examples_documented(self, client: AsyncClient):
        """PUT /auth/password : responses 200/400/401/422 documentées."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        operation = schema["paths"]["/api/v1/auth/password"]["put"]
        documented = set(operation.get("responses", {}).keys())
        assert {"200", "400", "401", "422"}.issubset(documented)
        # Body d'exemple présent (rules 20 : documentation maximale)
        request_examples = operation["requestBody"]["content"]["application/json"]
        assert "schema" in request_examples

    async def test_openapi_ready_examples_documented(self, client: AsyncClient):
        """GET /system/ready : responses 200/503 avec examples."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        operation = schema["paths"]["/api/v1/system/ready"]["get"]
        documented = set(operation.get("responses", {}).keys())
        assert {"200", "503"}.issubset(documented)
