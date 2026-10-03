"""Tests unitaires du login avec hash bcrypt legacy — re-hash Argon2id (STORY-130.1).

Couvre le cœur de l'AC 1 au niveau API (story tâche 3, rules 35/40) :

- utilisateur seedé avec un hash **bcrypt legacy** (écriture directe en
  base) → ``POST /auth/login`` 200 → relecture DB : ``hashed_password``
  désormais préfixé ``$argon2id$`` (upgrade transparent, aucun reset
  requis — arbitrage F2) ;
- deuxième login (hash désormais argon2) → 200 : la boucle est stable ;
- mot de passe faux → **401 générique** — aucune fuite du schème du hash
  (anti-énumération, rules 40) ;
- réponse login sans hash ni mot de passe (champs sensibles absents).

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4) — le ``.env``
racine porte ``DISABLE_AUTH=true``.
"""

import pytest
from httpx import AsyncClient
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.models.user import User

USER_PASSWORD = "testpassword123"

LOGIN_URL = "/api/v1/auth/login"

# Contexte local dédié à la génération du hash bcrypt legacy de fixture
# (la production écrit exclusivement en Argon2id — STORY-130.1).
_BCRYPT_FIXTURE_CTX = CryptContext(schemes=["bcrypt"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4."""
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


async def _seed_bcrypt_user(db_session: AsyncSession) -> User:
    """Crée un utilisateur dont le hash est bcrypt legacy ($2b$...).

    Écriture directe en base (pattern seed) : simule un compte créé avant
    la migration Argon2id.
    """
    user = User(
        email="legacy-bcrypt@example.com",
        username="legacy-bcrypt",
        full_name="Legacy Bcrypt",
        hashed_password=_BCRYPT_FIXTURE_CTX.hash(USER_PASSWORD),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.hashed_password.startswith("$2b$")
    return user


async def _reload_user(db_session: AsyncSession, user_id: str) -> User:
    """Recharge l'utilisateur depuis la base (post-login)."""
    result = await db_session.execute(select(User).where(User.id == user_id))
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Migration bcrypt → Argon2id au login (AC 1)
# ---------------------------------------------------------------------------


class TestLoginHashUpgrade:
    """Login d'un compte bcrypt legacy → re-hash Argon2id transparent."""

    async def test_login_bcrypt_user_returns_200_and_rehashes_to_argon2id(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """AC 1 : login 200 → hash DB re-haché $argon2id$ (aucun reset requis)."""
        user = await _seed_bcrypt_user(db_session)

        response = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": USER_PASSWORD},
        )

        assert response.status_code == 200
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password.startswith("$argon2id$")

    async def test_second_login_with_rehashed_password_still_succeeds(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """La boucle est stable : 2e login (hash désormais argon2) → 200."""
        user = await _seed_bcrypt_user(db_session)

        first = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": USER_PASSWORD},
        )
        assert first.status_code == 200

        second = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": USER_PASSWORD},
        )
        assert second.status_code == 200
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password.startswith("$argon2id$")

    async def test_wrong_password_returns_generic_401_no_scheme_leak(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """rules 40 : mot de passe faux → 401 générique, aucune fuite du schème."""
        user = await _seed_bcrypt_user(db_session)

        response = await client.post(
            LOGIN_URL,
            data={"username": user.username, "password": "totally-wrong"},
        )

        assert response.status_code == 401
        body = response.json()
        message = str(body).lower()
        assert "bcrypt" not in message
        assert "argon2" not in message
        # Le hash n'a pas été modifié par une tentative échouée
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password.startswith("$2b$")

    async def test_login_response_has_no_sensitive_fields(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """rules 40 : réponse login sans hash ni mot de passe."""
        user = await _seed_bcrypt_user(db_session)

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

    async def test_login_bcrypt_user_by_email_also_rehashes(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Login par email (non-régression flux) : même upgrade transparent."""
        user = await _seed_bcrypt_user(db_session)

        response = await client.post(
            LOGIN_URL,
            data={"username": user.email, "password": USER_PASSWORD},
        )

        assert response.status_code == 200
        reloaded = await _reload_user(db_session, user.id)
        assert reloaded.hashed_password.startswith("$argon2id$")
