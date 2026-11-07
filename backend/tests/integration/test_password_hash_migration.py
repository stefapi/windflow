"""Tests d'intégration du hachage de mots de passe — contrat post BUG-012.

La double lecture bcrypt (transition STORY-130.1) a été retirée : migration
achevée (0 hash bcrypt en base), dépendance ``bcrypt`` purgée. Valide en
conditions réelles (base de test, login réel par form-data — patterns
``test_auth_password_flow.py``) :

- **flux complet Argon2id** : register → login 200 → ``PUT /auth/password``
  (ancien mot de passe vérifié en Argon2id) → login nouveau mot de passe 200 ;
- **résidu bcrypt legacy** : un éventuel hash ``$2b$...`` resté en base →
  login **401 générique** (schème inconnu → échec silencieux) et hash
  **inchangé** (aucun re-hash — le compte doit être réinitialisé).

La non-régression des flux auth existants (login username/email, register,
refresh, disable_auth) est couverte par les suites existantes
(``test_auth_password_flow.py``, ``test_auth_api.py``,
``test_auth_refresh_security.py``).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.config import settings
from app.models.organization import Organization
from app.models.user import User

OLD_PASSWORD = "testpassword123"
NEW_PASSWORD = "NewSecureP@ss456"

LOGIN_URL = "/api/v1/auth/login"
REGISTER_URL = "/api/v1/auth/register"
PASSWORD_URL = "/api/v1/auth/password"

# Hash bcrypt legacy CONSTANT (généré historiquement via passlib/bcrypt,
# préfixe $2b$) — fixture sans dépendance : la purge BUG-012 retire le
# package ``bcrypt``, le hash n'est plus jamais vérifiable (schème inconnu).
LEGACY_BCRYPT_HASH = "$2b$12$KIXQeJxYRqEOeBzKzGzLxOjQk8Y0eQqZSsr6NUeG7Wc7kQqCqfQqC"


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


async def _seed_legacy_bcrypt_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur au hash bcrypt legacy ($2b$...) — résidu pré-migration."""
    user = User(
        email="it-legacy-bcrypt@example.com",
        username="it-legacy-bcrypt",
        full_name="IT Legacy Bcrypt",
        hashed_password=LEGACY_BCRYPT_HASH,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _reload_user(db_session: AsyncSession, user_id: str) -> User:
    """Recharge l'utilisateur depuis la base."""
    result = await db_session.execute(select(User).where(User.id == user_id))
    return result.scalar_one()


async def _ensure_default_org(db_session: AsyncSession) -> None:
    """Provisionne l'organisation par défaut si absente (pattern test_auth_isolation).

    ``POST /auth/register`` rattache l'utilisateur à l'org résolue par
    ``settings.default_org_slug`` — la base de test n'exécute pas le seed.
    """
    default_org = (
        await db_session.execute(
            select(Organization).where(Organization.slug == settings.default_org_slug)
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


class TestArgon2FullFlow:
    """Flux complet Argon2id : register → login → PUT password → login."""

    async def test_register_login_password_change_and_new_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Register → login 200 → PUT /auth/password (ancien mdp vérifié
        Argon2id) → login nouveau mot de passe 200, ancien 401."""
        await _ensure_default_org(db_session)
        register = await client.post(
            REGISTER_URL,
            json={
                "email": "it-argon2-flow@example.com",
                "username": "it-argon2-flow",
                "full_name": "IT Argon2 Flow",
                "password": OLD_PASSWORD,
            },
        )
        assert register.status_code == 201, register.text
        created = unwrap(register)

        # 1. Login avec le mot de passe d'origine → 200
        user_id = created["user"]["id"]
        user = await _reload_user(db_session, user_id)
        assert user.hashed_password.startswith("$argon2id$")
        status, login_data = await _login(client, user.username, OLD_PASSWORD)
        assert status == 200

        # 2. Changement de mot de passe — l'ancien mot de passe est vérifié
        #    en Argon2id (lecture unique post BUG-012)
        change = await client.put(
            PASSWORD_URL,
            json={
                "current_password": OLD_PASSWORD,
                "new_password": NEW_PASSWORD,
            },
            headers={"Authorization": f"Bearer {login_data['access_token']}"},
        )
        assert change.status_code == 200, change.text
        assert unwrap(change)["message"] == "Password updated successfully"

        # 3. Login avec le NOUVEAU mot de passe → 200
        status, _ = await _login(client, user.username, NEW_PASSWORD)
        assert status == 200

        # 4. L'ancien mot de passe ne fonctionne plus
        old_status, _ = await _login(client, user.username, OLD_PASSWORD)
        assert old_status == 401


class TestLegacyBcryptResidue:
    """Résidu bcrypt legacy : rejet générique, aucun re-hash (post BUG-012)."""

    async def test_legacy_bcrypt_login_rejected_and_hash_unchanged(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Hash $2b$ resté en base → 401 générique (aucune fuite de schème,
        aucune info sur le hash) et hash inchangé — plus aucun chemin de
        re-hash (double lecture retirée, migration achevée)."""
        user = await _seed_legacy_bcrypt_user(db_session)

        status, payload = await _login(client, user.username, OLD_PASSWORD)

        assert status == 401
        assert payload is None
        body_text = str(payload).lower()
        assert "bcrypt" not in body_text
        assert "argon2" not in body_text
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password == LEGACY_BCRYPT_HASH
