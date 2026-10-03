"""Tests d'intégration de la migration bcrypt → Argon2id (STORY-130.1).

Valide le parcours complet en conditions réelles (base de test, login réel
par form-data — patterns ``test_auth_password_flow.py``) :

- **flux complet** : seed utilisateur bcrypt (écriture directe en base) →
  ``POST /auth/login`` 200 → hash DB devenu ``$argon2id$`` → ``PUT
  /auth/password`` avec l'ancien mot de passe d'origine (200 — preuve que
  la vérification double lecture fonctionne aussi sur ce chemin) → login
  avec le nouveau mot de passe 200 ;
- **non-régression argon2** : utilisateur créé via ``POST /auth/register``
  → hash ``$argon2id$`` dès la création (AC 1) → login 200 → hash
  **inchangé** en base (pas de re-hash superflu — arbitrage n°2).

La non-régression des flux auth existants (login username/email, register,
refresh, disable_auth) est couverte par les suites existantes
(``test_auth_password_flow.py``, ``test_auth_api.py``,
``test_auth_refresh_security.py``) rejouées dans la validation de la story
(AC 3).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4).
"""

import pytest
from httpx import AsyncClient
from passlib.context import CryptContext
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

# Contexte local dédié à la génération du hash bcrypt legacy de fixture
# (la production écrit exclusivement en Argon2id — STORY-130.1).
_BCRYPT_FIXTURE_CTX = CryptContext(schemes=["bcrypt"])


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


async def _seed_bcrypt_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur au hash bcrypt legacy ($2b$...) — compte pré-migration."""
    user = User(
        email="it-legacy-bcrypt@example.com",
        username="it-legacy-bcrypt",
        full_name="IT Legacy Bcrypt",
        hashed_password=_BCRYPT_FIXTURE_CTX.hash(OLD_PASSWORD),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _reload_user(db_session: AsyncSession, user_id: str) -> User:
    """Recharge l'utilisateur depuis la base (après login/upgrade)."""
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


class TestPasswordHashMigrationFullFlow:
    """Flux complet de migration : bcrypt → login (re-hash) → PUT password → login."""

    async def test_bcrypt_login_rehash_then_password_change_and_new_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """AC 1 : bcrypt → login 200 (re-hash $argon2id$) → PUT /auth/password
        avec l'ancien mot de passe d'origine → login nouveau mot de passe 200."""
        user = await _seed_bcrypt_user(db_session)

        # 1. Login avec le hash bcrypt legacy → 200 + re-hash transparent
        status, login_data = await _login(client, user.username, OLD_PASSWORD)
        assert (
            status == 200
        ), "le compte bcrypt doit pouvoir se connecter (aucun reset requis)"
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password.startswith("$argon2id$")

        # 2. Changement de mot de passe avec l'ANCIEN mot de passe d'origine —
        #    preuve que la double lecture bcrypt fonctionne aussi sur PUT /auth/password
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


class TestArgon2NoRegression:
    """Non-régression : les comptes créés aujourd'hui sont Argon2id et stables."""

    async def test_register_hashes_argon2id_and_login_keeps_hash_stable(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """AC 1 : register → $argon2id$ dès la création → login 200 → hash inchangé."""
        await _ensure_default_org(db_session)
        register = await client.post(
            REGISTER_URL,
            json={
                "email": "it-argon2-register@example.com",
                "username": "it-argon2-register",
                "full_name": "IT Argon2 Register",
                "password": OLD_PASSWORD,
            },
        )
        assert register.status_code == 201, register.text
        created = unwrap(register)

        # Hash Argon2id dès la création
        user = await _reload_user(db_session, created["user"]["id"])
        assert user.hashed_password.startswith("$argon2id$")
        hash_after_creation = user.hashed_password

        # Login → 200, sans re-hash superflu (arbitrage n°2)
        status, _ = await _login(client, user.username, OLD_PASSWORD)
        assert status == 200
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password == hash_after_creation
