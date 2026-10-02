"""Tests unitaires de l'endpoint PUT /auth/password (STORY-129).

Couvre (story Tâche 6, rules 35/40) :

- **Sécurité obligatoire (rules 40)** : 401 sans token ; 400 ancien mot
  de passe faux (arbitrage n°4 — pas 401) ; 422 body invalide (champ
  manquant, nouveau mot de passe < 8) ;
- nominal : 200 → ``message`` + ``refresh_tokens_revoked`` ; le login
  suivant fonctionne avec le NOUVEAU mot de passe (AC 2) ; l'ancien ne
  fonctionne plus ;
- **AC 3** : refresh tokens révoqués — ``POST /auth/refresh`` avec
  l'ancien refresh → 401 ``INVALID_OR_EXPIRED_TOKEN`` ; les **clés API
  restent valides** (requête authentifiée ``X-API-Key`` après le
  changement → 200) ;
- isolation structurelle : le schéma n'expose **aucun identifiant
  utilisateur** (impossible de cibler un autre compte) ;
- réponse sans champ sensible (pas de hash/mot de passe/token) ;
- audit ``user.password_changed`` émis (pattern tests audit 125.2 via
  redirection ``AsyncSessionLocal``).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4) — le
``.env`` racine porte ``DISABLE_AUTH=true``.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.conftest import unwrap

from app.models.audit_log import AuditLog
from app.models.user import User

USER_PASSWORD = "testpassword123"
NEW_PASSWORD = "NewSecureP@ss456"

PASSWORD_URL = "/api/v1/auth/password"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture(autouse=True)
async def _audit_db(monkeypatch, test_session_factory: async_sessionmaker) -> None:
    """Redirige les sessions courtes d'audit vers la base de test.

    Pattern ``test_audit_emission.py`` : ``AuditService.log`` sans ``db``
    ouvre ``AsyncSessionLocal()`` — jamais initialisée hors lifespan ;
    on redirige vers la factory du test pour rendre les lignes visibles.
    """
    import app.services.audit_service as audit_service_module

    monkeypatch.setattr(audit_service_module, "AsyncSessionLocal", test_session_factory)


def _bearer(user: User) -> dict:
    """Headers Authorization — mint direct (pattern test_api_envelope)."""
    from app.auth.jwt import create_access_token

    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _login(
    client: AsyncClient, username: str, password: str
) -> tuple[int, dict | None]:
    """Login par form-data ; retourne (status, payload unwrapped ou None)."""
    response = await client.post(
        LOGIN_URL, data={"username": username, "password": password}
    )
    if response.status_code != 200:
        return response.status_code, None
    return 200, unwrap(response)


# ---------------------------------------------------------------------------
# Sécurité obligatoire (rules 40)
# ---------------------------------------------------------------------------


class TestPasswordSecurity:
    """Cas d'erreur et de sécurité de PUT /auth/password."""

    async def test_password_returns_401_without_token(self, client: AsyncClient):
        """Sécurité : 401 sans Authorization."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": "x", "new_password": "y" * 12},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_password_returns_400_on_wrong_current(
        self, client: AsyncClient, test_user: User
    ):
        """AC 2 : ancien mot de passe faux → 400 INVALID_INPUT (arbitrage n°4)."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": "totally-wrong", "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "INVALID_INPUT"
        assert "incorrect" in body["error"]["message"].lower()

    async def test_password_returns_422_on_missing_fields(
        self, client: AsyncClient, test_user: User
    ):
        """AC 2 : champ manquant → 422 VALIDATION_ERROR."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD},  # new_password absent
            headers=_bearer(test_user),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_password_returns_422_on_weak_new_password(
        self, client: AsyncClient, test_user: User
    ):
        """AC 2 : nouveau mot de passe < 8 caractères → 422 (politique)."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": "short"},
            headers=_bearer(test_user),
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Nominal (AC 2)
# ---------------------------------------------------------------------------


class TestPasswordChangeNominal:
    """Changement réussi — hash mis à jour, login suivant OK."""

    async def test_change_password_200(self, client: AsyncClient, test_user: User):
        """200 nominal → message + refresh_tokens_revoked (0 ici : bearer
        minté directement, aucun login réel n'a persisté de refresh)."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert response.status_code == 200
        data = unwrap(response)
        assert data["message"] == "Password updated successfully"
        assert isinstance(data["refresh_tokens_revoked"], int)
        assert data["refresh_tokens_revoked"] >= 0

    async def test_next_login_works_with_new_password(
        self, client: AsyncClient, test_user: User
    ):
        """AC 2 : login suivant avec le NOUVEAU mot de passe → 200."""
        change = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert change.status_code == 200

        status, _payload = await _login(client, test_user.username, NEW_PASSWORD)
        assert status == 200

    async def test_old_password_rejected_after_change(
        self, client: AsyncClient, test_user: User
    ):
        """AC 2 : login avec l'ANCIEN mot de passe → 401."""
        change = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert change.status_code == 200

        response = await client.post(
            LOGIN_URL,
            data={"username": test_user.username, "password": USER_PASSWORD},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC 3 — révocation refresh tokens, clés API conservées
# ---------------------------------------------------------------------------


class TestRefreshRevocationAndApiKeys:
    """Après changement : anciens refresh révoqués, clés API intactes."""

    async def test_old_refresh_token_rejected_after_change(
        self, client: AsyncClient, test_user: User
    ):
        """AC 3 : refresh avec un ancien token → 401 INVALID_OR_EXPIRED_TOKEN."""
        # Login réel → refresh token persisté
        status, login_data = await _login(client, test_user.username, USER_PASSWORD)
        assert status == 200
        old_refresh = login_data["refresh_token"]

        # Changement de mot de passe (bearer minté, pas le login token)
        change = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert change.status_code == 200

        # L'ancien refresh est révoqué → 401
        response = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_api_key_still_valid_after_change(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """AC 3 : clé API créée avant le changement reste valide (200)."""
        # Créer une clé API avant le changement (login réel requis)
        status, login_data = await _login(client, test_user.username, USER_PASSWORD)
        assert status == 200
        client.headers.update({"Authorization": f"Bearer {login_data['access_token']}"})
        create = await client.post("/api/v1/auth/api-keys", json={"name": "cli-laptop"})
        assert create.status_code == 201, create.text
        raw_key = unwrap(create)["key"]

        # Changement de mot de passe via la clé API (self-service accepté)
        change = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers={"X-API-Key": raw_key},
        )
        assert change.status_code == 200

        # La clé API fonctionne toujours après le changement
        me = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert me.status_code == 200


# ---------------------------------------------------------------------------
# Isolation structurelle & absence de champ sensible
# ---------------------------------------------------------------------------


class TestStructuralIsolation:
    """Le body ne permet pas de cibler un autre compte (rules 40)."""

    def test_request_schema_has_no_user_identifier(self):
        """Contrat du schéma : seuls current_password/new_password."""
        from app.schemas.user import PasswordChangeRequest

        fields = set(PasswordChangeRequest.model_fields.keys())
        assert fields == {"current_password", "new_password"}

    async def test_response_has_no_sensitive_field(
        self, client: AsyncClient, test_user: User
    ):
        """Réponse sans hash, mot de passe ni token."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert response.status_code == 200
        body = response.text.lower()
        assert "hashed_password" not in body
        assert NEW_PASSWORD.lower() not in body
        assert USER_PASSWORD.lower() not in body
        assert "wf_rt_" not in body
        assert "$argon2" not in body


# ---------------------------------------------------------------------------
# Audit (STORY-125.2)
# ---------------------------------------------------------------------------


class TestPasswordAudit:
    """Action critique credentials → ligne user.password_changed émise."""

    async def test_audit_line_emitted(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Ligne ``user.password_changed`` avec acteur et cible."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": USER_PASSWORD, "new_password": NEW_PASSWORD},
            headers={**_bearer(test_user), "X-Correlation-ID": "pwd-corr-42"},
        )
        assert response.status_code == 200

        entries = (
            (
                await db_session.execute(
                    select(AuditLog).where(AuditLog.action == "user.password_changed")
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 1
        entry = entries[0]
        assert entry.user_id == test_user.id
        assert entry.resource_type == "user"
        assert entry.resource_id == str(test_user.id)
        # details : la clé refresh_tokens_revoked est masquée "***" par le
        # sanitizer structurel STORY-125 (marqueur "token") — comportement
        # conservateur attendu ; aucun mot de passe dans les details.
        assert entry.details["refresh_tokens_revoked"] == "***"
        assert not any("password" in k for k in (entry.details or {}).keys())

    async def test_no_audit_on_wrong_current_password(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Échec 400 : le changement n'a pas eu lieu → pas de ligne succès."""
        response = await client.put(
            PASSWORD_URL,
            json={"current_password": "wrong", "new_password": NEW_PASSWORD},
            headers=_bearer(test_user),
        )
        assert response.status_code == 400

        entries = (
            (
                await db_session.execute(
                    select(AuditLog).where(AuditLog.action == "user.password_changed")
                )
            )
            .scalars()
            .all()
        )
        assert entries == []
