"""Tests d'intégration du socle enveloppes API spec 09 (STORY-126.1).

Le flag transitoire ``api_envelope_enabled`` a été retiré par
STORY-126.3 : les enveloppes sont systématiques (plus de mode legacy).

Couvre (AC 2 + garde-fous AC 5) :
- 2xx JSON ``/api/v1/*`` → ``{"data": ..., "message": null}`` ;
- 204 non enveloppé (DELETE sans content) ;
- Erreurs → ``error.code`` mapping spec 09 : 401 ``INVALID_OR_EXPIRED_TOKEN``
  (login : ``INVALID_CREDENTIALS``), 403 ``PERMISSION_DENIED``, 404
  ``NOT_FOUND``, 409 ``CONFLICT`` (org dupliquée — test de référence
  story mère), 422 ``VALIDATION_ERROR`` + ``details`` + ``correlation_id`` ;
- ``/health`` et ``/`` jamais enveloppés ;
- 500 middleware → **une seule** enveloppe ;
- Headers transport (``X-Correlation-ID``) préservés.

Sécurité (rules 40) : ``_jwt_mode`` (pattern 123.4) — le ``.env`` racine
porte ``DISABLE_AUTH=true`` qui court-circuiterait ``get_current_user``
et ferait échouer les 401 attendus.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.models.organization import Organization
from app.models.user import User
from app.services.organization_service import OrganizationService

STACKS_URL = "/api/v1/stacks/"
LOGIN_URL = "/api/v1/auth/login"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


def _bearer(user: User) -> dict:
    """Headers Authorization — mint direct (pattern test_api_keys)."""
    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


class TestSuccessEnvelopes:
    """Réponses 2xx JSON → {"data": ..., "message": ...}."""

    async def test_2xx_json_enveloped(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """GET liste (auth) → data clé présente + message null."""
        response = await client.get(STACKS_URL, headers=_bearer(test_user))
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert "message" in body
        assert body["message"] is None
        assert isinstance(body["data"], list)

    async def test_204_not_enveloped(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """DELETE réussi → 204 corps vide, aucune enveloppe."""
        response = await client.delete(
            f"/api/v1/organizations/{test_organization.id}",
            headers=_bearer(test_superuser),
        )
        assert response.status_code == 204
        assert response.content == b""

    async def test_export_headers_preserved(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_stack,
    ):
        """Export stack (attachment JSON) : l'enveloppe préserve les
        headers transport (Content-Disposition) — le flux d'export reste
        fonctionnellement intact."""
        response = await client.get(
            f"/api/v1/stacks/{test_stack.id}/export", headers=_bearer(test_user)
        )
        assert response.status_code == 200
        assert response.headers.get("content-disposition") is not None
        # Corps enveloppé : l'export vit sous data
        assert "data" in response.json()


class TestErrorEnvelopes:
    """Erreurs 4xx/5xx → {"error": {"code", "message"}, "correlation_id"?}."""

    async def test_401_without_token(self, client: AsyncClient):
        """401 sans token → INVALID_OR_EXPIRED_TOKEN."""
        response = await client.get(STACKS_URL)
        assert response.status_code == 401
        error = response.json()["error"]
        assert error["code"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_401_login_invalid_credentials(self, client: AsyncClient):
        """401 sur login mauvais mot de passe → INVALID_CREDENTIALS."""
        response = await client.post(
            LOGIN_URL, data={"username": "ghost", "password": "wrong"}
        )
        assert response.status_code == 401
        error = response.json()["error"]
        assert error["code"] == "INVALID_CREDENTIALS"

    async def test_403_permission_denied(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        viewer_user: User,
    ):
        """403 viewer sur création d'org → PERMISSION_DENIED."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": "Viewer Corp"},
            headers=_bearer(viewer_user),
        )
        assert response.status_code == 403
        error = response.json()["error"]
        assert error["code"] == "PERMISSION_DENIED"

    async def test_404_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """404 stack inconnue → NOT_FOUND."""
        response = await client.get(
            f"{STACKS_URL}/00000000-0000-0000-0000-000000000000",
            headers=_bearer(test_user),
        )
        assert response.status_code == 404
        error = response.json()["error"]
        assert error["code"] == "NOT_FOUND"

    async def test_409_conflict_duplicate_organization(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """409 nom d'organisation dupliqué → CONFLICT (test de référence
        AC 2 story mère)."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"name": test_organization.name},
            headers=_bearer(test_superuser),
        )
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "CONFLICT"
        assert test_organization.name in error["message"]

    async def test_422_validation_error(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
    ):
        """422 body invalide → VALIDATION_ERROR + details liste +
        correlation_id préservé (AC 2 story mère)."""
        response = await client.post(
            "/api/v1/organizations/",
            json={"description": "name is missing"},
            headers=_bearer(test_superuser),
        )
        assert response.status_code == 422
        body = response.json()
        error = body["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert isinstance(error["details"], list)
        assert error["details"]  # erreurs Pydantic non vides
        assert "correlation_id" in body
        # Correlation ID cohérent avec le header de réponse
        assert body["correlation_id"] == response.headers["X-Correlation-ID"]


class TestGuardRails:
    """/health, / et headers : jamais d'enveloppe hors /api/v1."""

    async def test_health_not_enveloped(self, client: AsyncClient):
        """/health garde son format status/services nu."""
        response = await client.get("/health")
        assert response.status_code in (200, 503)
        body = response.json()
        assert "data" not in body
        assert "error" not in body
        assert "status" in body

    async def test_root_not_enveloped(self, client: AsyncClient):
        """Racine / garde son format documentaire nu."""
        response = await client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert "data" not in body
        assert "name" in body

    async def test_correlation_id_header_preserved(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """X-Correlation-ID exposé sur réponse enveloppée (CORS
        expose_headers inchangé)."""
        response = await client.get(
            STACKS_URL, headers={**_bearer(test_user), "X-Correlation-ID": "corr-42"}
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == "corr-42"
        # Et le corps est bien enveloppé
        assert "data" in response.json()


class TestMiddlewareSingleEnvelope:
    """Anti double-enveloppe : une erreur 500 middleware → UNE enveloppe."""

    async def test_500_single_envelope(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
    ):
        """Une exception non gérée → 500 avec exactement une enveloppe
        ``error`` — pas d'enveloppe dans l'enveloppe (décision 5)."""
        with patch.object(
            OrganizationService,
            "list_all",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            response = await client.get(
                "/api/v1/organizations/", headers=_bearer(test_superuser)
            )
        assert response.status_code == 500
        body = response.json()
        # Une seule enveloppe : error dict au sommet, pas de nesting
        assert "error" in body
        assert "data" not in body
        assert body["error"]["code"] == "INTERNAL_ERROR"
        # Pas de double : error ne porte pas une 2e enveloppe error
        assert "error" not in body["error"]
