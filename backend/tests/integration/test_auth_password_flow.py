"""Tests d'intégration du flux complet de changement de mot de passe (STORY-129).

Flux réel de bout en bout sur la base de test (login réel par form-data,
refresh tokens persistés, clés API en base) :

1. ``POST /auth/login`` (mint réel via form) → paire de tokens ;
2. ``PUT /auth/password`` (token bearer) → 200 ;
3. ``POST /auth/refresh`` avec l'ANCIEN refresh → **401** (révocation
   globale, AC 3) ;
4. re-``login`` avec le NOUVEAU mot de passe → 200 ;
5. le nouveau refresh émis est utilisable (rotation OK) ;
6. une clé API créée avant le changement reste fonctionnelle après
   (AC 3 — clés API non affectées).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4).
"""

import pytest
from httpx import AsyncClient
from tests.conftest import unwrap

from app.models.user import User

OLD_PASSWORD = "testpassword123"
NEW_PASSWORD = "NewSecureP@ss456"

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
PASSWORD_URL = "/api/v1/auth/password"
ME_URL = "/api/v1/auth/me"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


async def _login(
    client: AsyncClient, username: str, password: str
) -> tuple[int, dict | None]:
    """Login réel par form-data → (status, payload unwrapped | None)."""
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": password}
    )
    if response.status_code != 200:
        return response.status_code, None
    return 200, unwrap(response)


class TestPasswordChangeFullFlow:
    """Flux complet : login → change → refresh ancien 401 → re-login."""

    async def test_full_flow(self, client: AsyncClient, test_user: User):
        """Parcours nominal complet sur base réelle (AC 2 + AC 3)."""
        # 1. Login réel avec l'ancien mot de passe
        status, login_data = await _login(client, test_user.username, OLD_PASSWORD)
        assert status == 200
        old_access = login_data["access_token"]
        old_refresh = login_data["refresh_token"]

        # 2. Changement de mot de passe avec le token bearer du login
        change = await client.put(
            PASSWORD_URL,
            json={
                "current_password": OLD_PASSWORD,
                "new_password": NEW_PASSWORD,
            },
            headers={"Authorization": f"Bearer {old_access}"},
        )
        assert change.status_code == 200, change.text
        data = unwrap(change)
        assert data["message"] == "Password updated successfully"
        # Le refresh du login (persisté) a été révoqué
        assert data["refresh_tokens_revoked"] >= 1

        # 3. L'ancien refresh est révoqué → 401
        refresh_response = await client.post(
            REFRESH_URL, json={"refresh_token": old_refresh}
        )
        assert refresh_response.status_code == 401
        assert refresh_response.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

        # 4. Re-login avec le NOUVEAU mot de passe → 200
        status, new_login = await _login(client, test_user.username, NEW_PASSWORD)
        assert status == 200

        # 5. Le nouveau refresh est utilisable (rotation)
        new_refresh_response = await client.post(
            REFRESH_URL,
            json={"refresh_token": new_login["refresh_token"]},
        )
        assert new_refresh_response.status_code == 200, new_refresh_response.text

        # 6. L'ancien mot de passe ne fonctionne plus
        old_status, _ = await _login(client, test_user.username, OLD_PASSWORD)
        assert old_status == 401

    async def test_api_key_created_before_change_survives(
        self, client: AsyncClient, test_user: User
    ):
        """AC 3 : clé API créée avant le changement toujours fonctionnelle."""
        # Login + création de clé API AVANT le changement
        status, login_data = await _login(client, test_user.username, OLD_PASSWORD)
        assert status == 200
        client.headers.update({"Authorization": f"Bearer {login_data['access_token']}"})
        create = await client.post(
            "/api/v1/auth/api-keys", json={"name": "survives-password-change"}
        )
        assert create.status_code == 201, create.text
        raw_key = unwrap(create)["key"]

        # Changement de mot de passe
        change = await client.put(
            PASSWORD_URL,
            json={
                "current_password": OLD_PASSWORD,
                "new_password": NEW_PASSWORD,
            },
        )
        assert change.status_code == 200

        # La clé API fonctionne toujours (authentification par clé)
        me = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert me.status_code == 200
        assert unwrap(me)["username"] == test_user.username
