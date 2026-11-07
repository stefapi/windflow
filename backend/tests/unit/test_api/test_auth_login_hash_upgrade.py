"""Tests unitaires du login vis-à-vis des hashes legacy — contrat post BUG-012.

La double lecture bcrypt (transition STORY-130.1) a été retirée : migration
achevée (0 hash bcrypt en base), dépendance ``bcrypt`` purgée. Contrat actuel :

- un compte Argon2id standard → login 200 (non-régression du flux nominal) ;
- un éventuel résidu de hash **bcrypt legacy** ($2b$...) → **401 générique**
  sans fuite du schème (schème inconnu → échec silencieux, arbitrage n°9 —
  anti-énumération rules 40) et **hash inchangé en base** (jamais re-haché ;
- réponse login sans hash ni mot de passe (champs sensibles absents).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4) — le ``.env``
racine porte ``DISABLE_AUTH=true``.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.models.user import User
from app.services.user_service import UserService

USER_PASSWORD = "testpassword123"

LOGIN_URL = "/api/v1/auth/login"

# Hash bcrypt legacy CONSTANT (généré historiquement via passlib/bcrypt,
# préfixe $2b$) — fixture sans dépendance : la purge BUG-012 retire le
# package ``bcrypt``, le hash n'est plus jamais vérifiable (schème inconnu).
LEGACY_BCRYPT_HASH = "$2b$12$KIXQeJxYRqEOeBzKzGzLxOjQk8Y0eQqZSsr6NUeG7Wc7kQqCqfQqC"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


async def _seed_user_with_hash(
    db_session: AsyncSession, hashed_password: str, username: str = "std-user"
) -> User:
    """Crée un utilisateur portant le hash donné (écriture directe en base)."""
    user = User(
        email=f"{username}@example.com",
        username=username,
        full_name=username.title(),
        hashed_password=hashed_password,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _reload_user(db_session: AsyncSession, user_id: str) -> User:
    """Recharge l'utilisateur depuis la base (post-login)."""
    result = await db_session.execute(select(User).where(User.id == user_id))
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Login nominal Argon2id (non-régression)
# ---------------------------------------------------------------------------


class TestLoginArgon2Nominal:
    """Compte Argon2id standard → login nominal (non-régression)."""

    async def test_login_argon2_user_returns_200_and_hash_stable(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Login nominal : 200, hash $argon2id$ inchangé (pas de re-hash superflu)."""
        user = await _seed_user_with_hash(
            db_session, UserService.hash_password(USER_PASSWORD), "argon2-user"
        )
        hash_before = user.hashed_password

        response = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": USER_PASSWORD},
        )

        assert response.status_code == 200
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password == hash_before
        assert reloaded.hashed_password.startswith("$argon2id$")

    async def test_login_by_email_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Login par email (non-régression flux) : 200."""
        user = await _seed_user_with_hash(
            db_session, UserService.hash_password(USER_PASSWORD), "argon2-email"
        )

        response = await client.post(
            LOGIN_URL,
            data={"username": user.email, "password": USER_PASSWORD},
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Résidu bcrypt legacy → 401 générique, hash inchangé (contrat post BUG-012)
# ---------------------------------------------------------------------------


class TestLoginLegacyBcryptRejected:
    """Hash bcrypt legacy ($2b$) → 401 générique, aucun re-hash (post BUG-012)."""

    async def test_login_bcrypt_user_returns_generic_401_no_scheme_leak(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """rules 40 : résidu bcrypt → 401 générique, aucune fuite du schème."""
        user = await _seed_user_with_hash(
            db_session, LEGACY_BCRYPT_HASH, "legacy-bcrypt"
        )

        response = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": USER_PASSWORD},
        )

        assert response.status_code == 401
        body = response.json()
        message = str(body).lower()
        assert "bcrypt" not in message
        assert "argon2" not in message
        # Hash inchangé : plus aucun chemin de re-hash (double lecture retirée)
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password == LEGACY_BCRYPT_HASH

    async def test_login_response_has_no_sensitive_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """rules 40 : réponse login (cas nominal) sans hash ni mot de passe."""
        user = await _seed_user_with_hash(
            db_session, UserService.hash_password(USER_PASSWORD), "sensitive-check"
        )

        response = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": USER_PASSWORD},
        )

        assert response.status_code == 200
        payload = unwrap(response)
        flattened = str(payload).lower()
        assert "hashed_password" not in flattened
        assert "password" not in flattened
        assert USER_PASSWORD.lower() not in flattened
        assert "$2b$" not in flattened
        assert "$argon2" not in flattened
