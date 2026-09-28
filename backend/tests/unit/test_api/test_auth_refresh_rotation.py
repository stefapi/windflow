"""Tests endpoints refresh tokens révocables (STORY-123.3).

Couvre les 4 endpoints modifiés : persistance au login/register (hash en
base, jamais la valeur claire), rotation HTTP complète de ``/refresh``
(usage unique, 401 sur consommé/révoqué/inconnu/expiré, révocation
défensive de la famille, utilisateur actif), logout révocant (Option A —
révocation globale) et non-régression des contrats de réponse
(``LoginResponse``/``RefreshResponse`` inchangés).

Sécurité (rules 40) : les 401 génériques ``INVALID_OR_EXPIRED_TOKEN`` ne
divulguent pas l'existence du token ; le refresh token ne doit JAMAIS
apparaître en clair dans une réponse autre que sa création.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.conftest import unwrap

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
REGISTER_URL = "/api/v1/auth/register"

USER_PASSWORD = "testpassword123"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2/122.7.

    Divergence STORY-123.4 (correction de non-régression) : sans cette
    garde, la suite dépend du CWD d'exécution (pydantic-settings charge
    le ``.env`` relatif au répertoire courant ; le ``.env`` racine porte
    ``DISABLE_AUTH=true``) — ``get_current_user`` résout alors le premier
    superadmin en ignorant le Bearer, et les tests logout (qui authentifient
    ``test_user`` non-superuser) échouent ou révoquent le mauvais
    propriétaire. Lancée depuis ``backend/`` la suite passait déjà ; la
    garde la rend indépendante du répertoire d'invocation (Makefile/CI).
    """
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


async def _login(client: AsyncClient, user: User) -> dict:
    """Login par username → 200 ; retourne le body JSON de la réponse."""
    response = await client.post(
        LOGIN_URL, data={"username": user.username, "password": USER_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return unwrap(response)


async def _active_tokens(db_session: AsyncSession, user_id: str) -> list:
    """Lignes refresh_tokens actives (non révoquées) d'un utilisateur."""
    return list(
        (
            await db_session.execute(
                select(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )


class TestLoginPersistance:
    """STORY-123.3 Tâche 1 : /login (+ auto-login dev) persiste le hash."""

    async def test_login_persists_refresh_token_hash(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Après /login : une ligne ``refresh_tokens`` existe, contient le
        **hash Argon2** — jamais la valeur claire (AC 1 démo)."""
        body = await _login(client, test_user)
        plain_token = body["refresh_token"]

        rows = (
            (
                await db_session.execute(
                    select(RefreshToken).where(RefreshToken.user_id == test_user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        row = rows[0]

        # Hash, pas la valeur claire : ni égal ni contenu
        assert row.token_hash != plain_token
        assert plain_token not in row.token_hash
        # Argon2 (arbitrage n°1 — STORY-123.1)
        assert row.token_hash.startswith("$argon2")
        # Ligne active, expiration = durée configurable (7 j défaut)
        assert row.revoked_at is None
        delta = row.expires_at - datetime.now(timezone.utc).replace(tzinfo=None)
        assert timedelta(days=6) < delta <= timedelta(days=7, minutes=5)

    async def test_login_response_contract_unchanged(
        self, client: AsyncClient, test_user: User
    ):
        """Non-régression : forme ``LoginResponse`` inchangée — le refresh
        est une string opaque (préfixe ``wf_rt_``), pas un JWT (AC 4)."""
        body = await _login(client, test_user)

        assert set(body.keys()) == {
            "access_token",
            "refresh_token",
            "token_type",
            "expires_in",
            "user",
        }
        assert body["token_type"] == "bearer"
        assert body["user"]["id"] == test_user.id
        # Access : JWT 3 segments ; refresh : opaque préfixé sans structure JWT
        assert len(body["access_token"].split(".")) == 3
        assert body["refresh_token"].startswith("wf_rt_")
        assert len(body["refresh_token"].split(".")) != 3

    async def test_register_persists_refresh_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """/register (auto-login) émet et persiste aussi la ligne hashée."""
        # Provisionner l'org par défaut (pattern test_auth_isolation)
        from app.config import settings

        default_org = (
            await db_session.execute(
                select(Organization).where(
                    Organization.slug == settings.default_org_slug
                )
            )
        ).scalar_one_or_none()
        if default_org is None:
            db_session.add(
                Organization(
                    name="Default Org",
                    slug=settings.default_org_slug,
                    description="",
                )
            )
            await db_session.commit()

        response = await client.post(
            REGISTER_URL,
            json={
                "email": "rot-newuser@example.com",
                "username": "rot-newuser",
                "password": "SecurePass123!",
            },
        )
        assert response.status_code == 201, response.text
        body = unwrap(response)
        user_id = body["user"]["id"]

        rows = (
            (
                await db_session.execute(
                    select(RefreshToken).where(RefreshToken.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].token_hash != body["refresh_token"]
        assert rows[0].token_hash.startswith("$argon2")


class TestRefreshRotation:
    """STORY-123.3 Tâche 2 : /refresh rotatif — usage unique strict."""

    async def test_refresh_rotates_token(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Refresh → nouveau couple émis ; l'ANCIEN re-soumis → 401
        ``INVALID_OR_EXPIRED_TOKEN`` (AC 2 démo HTTP)."""
        body = await _login(client, test_user)
        old_refresh = body["refresh_token"]

        response = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert response.status_code == 200, response.text
        rotated = unwrap(response)

        # Nouveau couple complet, refresh nouveau distinct de l'ancien
        assert rotated["access_token"]
        assert rotated["refresh_token"].startswith("wf_rt_")
        assert rotated["refresh_token"] != old_refresh
        assert rotated["token_type"] == "bearer"

        # L'ancien est consommé : re-soumission → 401 générique
        replay = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert replay.status_code == 401
        assert replay.json()["error"]["message"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_refresh_unknown_token_returns_401(
        self, client: AsyncClient, test_user: User
    ):
        """Token inconnu → 401 générique (pas d'oracle d'existence)."""
        response = await client.post(
            REFRESH_URL, json={"refresh_token": "wf_rt_totally-unknown-token"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_refresh_expired_token_returns_401(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Ligne expirée en base → 401."""
        body = await _login(client, test_user)

        # Expire la ligne en base (sans passer par le service)
        await db_session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == test_user.id)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        )
        await db_session.commit()

        response = await client.post(
            REFRESH_URL, json={"refresh_token": body["refresh_token"]}
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "INVALID_OR_EXPIRED_TOKEN"

    async def test_refresh_reuse_revokes_family(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Réutilisation de l'ancien token après rotation → 401 ET tous
        les tokens de l'utilisateur révoqués (nouveau inclus) — défense
        anti-vol (révocation défensive de la famille)."""
        body = await _login(client, test_user)
        old_refresh = body["refresh_token"]

        rotated = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert rotated.status_code == 200
        new_refresh = unwrap(rotated)["refresh_token"]
        assert await _active_tokens(db_session, test_user.id)  # nouveau actif

        # Réutilisation de l'ancien → 401 + famille révoquée
        replay = await client.post(REFRESH_URL, json={"refresh_token": old_refresh})
        assert replay.status_code == 401

        actives = await _active_tokens(db_session, test_user.id)
        assert not actives, "la famille doit être intégralement révoquée"

        # Le nouveau token est mort lui aussi
        with_new = await client.post(REFRESH_URL, json={"refresh_token": new_refresh})
        assert with_new.status_code == 401

    async def test_refresh_inactive_user_returns_401(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Utilisateur désactivé → 401 (cohérence vérifications actuelles,
        AC 2) — et le token fraîchement roté est révoqué (défense)."""
        body = await _login(client, test_user)

        test_user.is_active = False
        db_session.add(test_user)
        await db_session.commit()

        response = await client.post(
            REFRESH_URL, json={"refresh_token": body["refresh_token"]}
        )
        assert response.status_code == 401
        assert response.json()["error"]["message"] == "INVALID_OR_EXPIRED_TOKEN"

        # Défense : aucune ligne active ne survit pour un compte désactivé
        actives = await _active_tokens(db_session, test_user.id)
        assert not actives

    async def test_refresh_empty_or_oversized_body_returns_422(
        self, client: AsyncClient, test_user: User
    ):
        """Body invalide → 422 (validation Pydantic : non vide, ≤ 512)."""
        empty = await client.post(REFRESH_URL, json={"refresh_token": ""})
        assert empty.status_code == 422

        missing = await client.post(REFRESH_URL, json={})
        assert missing.status_code == 422

        oversized = await client.post(REFRESH_URL, json={"refresh_token": "x" * 513})
        assert oversized.status_code == 422


class TestLogoutRevocation:
    """STORY-123.3 Tâche 3 : /logout révocant (arbitrage n°2, Option A)."""

    async def _auth_header(self, client: AsyncClient, user: User) -> dict:
        body = await _login(client, user)
        return {"Authorization": f"Bearer {body['access_token']}"}

    async def test_logout_revokes_refresh_tokens(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Login → logout → refresh avec le token → 401 (AC 3 démo)."""
        body = await _login(client, test_user)
        headers = {"Authorization": f"Bearer {body['access_token']}"}

        logout = await client.post(LOGOUT_URL, headers=headers)
        assert logout.status_code == 200, logout.text
        assert unwrap(logout)["message"] == "Successfully logged out"

        # Tous les refresh tokens de l'utilisateur sont révoqués en base
        actives = await _active_tokens(db_session, test_user.id)
        assert not actives

        # Le refresh suivant avec ce token → 401
        response = await client.post(
            REFRESH_URL, json={"refresh_token": body["refresh_token"]}
        )
        assert response.status_code == 401

    async def test_logout_idempotent_returns_200(
        self, client: AsyncClient, test_user: User
    ):
        """Double logout → 200 (idempotence — le second révoque 0 token)."""
        headers = await self._auth_header(client, test_user)

        first = await client.post(LOGOUT_URL, headers=headers)
        assert first.status_code == 200

        second = await client.post(LOGOUT_URL, headers=headers)
        assert second.status_code == 200

    async def test_logout_does_not_revoke_other_users(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
    ):
        """Isolation : logout de A n'invalide pas les tokens de B."""
        # B (superuser) se connecte — sa réponse porte son refresh en clair
        # (seule source : la base ne stocke que le hash)
        login_b = await client.post(
            LOGIN_URL,
            data={
                "username": test_superuser.username,
                "password": "adminpassword123",
            },
        )
        assert login_b.status_code == 200, login_b.text
        body_b = unwrap(login_b)

        # A se connecte à son tour
        body_a = await _login(client, test_user)
        headers_a = {"Authorization": f"Bearer {body_a['access_token']}"}

        # Les deux utilisateurs ont une ligne active
        assert await _active_tokens(db_session, test_user.id)
        assert await _active_tokens(db_session, test_superuser.id)

        # Logout de A uniquement
        logout_a = await client.post(LOGOUT_URL, headers=headers_a)
        assert logout_a.status_code == 200

        # A : tout révoqué ; B : rien de changé
        assert not await _active_tokens(db_session, test_user.id)
        assert await _active_tokens(db_session, test_superuser.id)

        # B peut toujours rafraîchir sa session (son token est intact)
        refresh_b = await client.post(
            REFRESH_URL, json={"refresh_token": body_b["refresh_token"]}
        )
        assert refresh_b.status_code == 200, refresh_b.text
