"""Tests de la dépréciation `/auth/me` (STORY-250.2 — P3-3/E9, AC 3).

`/auth/me` conserve 200 (compatibilité) mais porte les headers
`Deprecation: true` + `Sunset` (constante ``AUTH_ME_SUNSET``) et est
marqué `deprecated` dans l'OpenAPI avec renvoi vers `/users/me`
(endpoint contractuel, sans dépréciation).
"""

from __future__ import annotations

import pytest
from tests.conftest import unwrap

from app.api.v1.auth import AUTH_ME_SUNSET
from app.main import app


@pytest.fixture(autouse=True)
def force_real_auth(monkeypatch) -> None:
    """Force disable_auth=False — pattern test_compute_api."""
    from app.config import settings

    monkeypatch.setattr(settings, "disable_auth", False)


class TestAuthMeDeprecation:
    async def test_auth_me_still_200_with_deprecation_headers(
        self, authenticated_client
    ):
        """AC 3 : 200 conservé + headers Deprecation et Sunset présents."""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200, response.text
        assert response.headers.get("Deprecation") == "true"
        sunset = response.headers.get("Sunset")
        assert sunset == AUTH_ME_SUNSET
        # format ISO YYYY-MM-DD (RFC 8594)
        assert len(sunset) == 10 and sunset[4] == "-" and sunset[7] == "-"
        # le profil répond toujours (contrat inchangé)
        body = unwrap(response)
        assert body["username"]

    async def test_users_me_no_deprecation_headers(self, authenticated_client):
        """AC 3 : endpoint contractuel — pas de headers de dépréciation."""
        response = await authenticated_client.get("/api/v1/users/me")
        assert response.status_code == 200, response.text
        assert response.headers.get("Deprecation") is None
        assert response.headers.get("Sunset") is None
        assert unwrap(response)["username"]

    async def test_auth_me_401_without_token(self, client):
        """Sécurité (règle 40) : pas d'accès sans token — dépréciation ≠ ouverture."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_openapi_marks_auth_me_deprecated(self):
        """AC 3 : OpenAPI `deprecated: true` + description mentionne /users/me."""
        spec = app.openapi()
        me = spec["paths"]["/api/v1/auth/me"]["get"]
        assert me.get("deprecated") is True
        assert "/users/me" in me.get("description", "")

    def test_openapi_users_me_not_deprecated(self):
        spec = app.openapi()
        me = spec["paths"]["/api/v1/users/me"]["get"]
        assert me.get("deprecated") is not True
