"""Tests transverses de sécurité du dispositif refresh tokens (STORY-123.4).

Vérification bout en bout des propriétés exigées par l'AC 4 de STORY-123 :
- **401 systématiques** sur refresh avec token inconnu / malformé /
  révoqué / consommé (message générique, pas d'oracle d'existence) ;
- **hash jamais en clair en base** — propriété vérifiée sur l'ensemble
  de la table après login ET après rotation ;
- **isolation multi-utilisateurs** de bout en bout (logout de A ne tue
  pas les tokens de B) ;
- **non-régression** des flux auth existants (disable_auth, login
  username ET email, register, logout) ;
- **purge des entrées expirées** — appel direct de la fonction que le
  job du lifespan (STORY-123.4 Tâche 1) exécute périodiquement.

Sécurité (rules 40) : cette suite EST la concrétisation de l'AC 4 —
les démonstrations unitaires des AC 1/2/3 (posées par 123.1/123.2/123.3)
sont revalidées ici dans une perspective transverse.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.refresh_token_service import RefreshTokenService

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
REGISTER_URL = "/api/v1/auth/register"

USER_PASSWORD = "testpassword123"
SUPERUSER_PASSWORD = "adminpassword123"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2/122.7.

    Sans cette garde, la suite dépend du CWD d'exécution : pydantic-settings
    charge le ``.env`` relatif au répertoire courant, et le ``.env`` racine
    du dépôt porte ``DISABLE_AUTH=true`` — ``get_current_user`` résoudrait
    alors le premier superadmin en ignorant le Bearer (logout/refresh d'un
    utilisateur non-superuser_testé deviendraient incohérents). La
    non-régression ``disable_auth`` est couverte explicitement par
    ``test_existing_auth_suites_unaffected``.
    """
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


SUPERUSER_PASSWORD = "adminpassword123"


async def _login(
    client: AsyncClient, user: User, password: str = USER_PASSWORD
) -> dict:
    """Login par username → 200 ; retourne le body JSON de la réponse."""
    response = await client.post(
        LOGIN_URL, data={"username": user.username, "password": password}
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


class TestRefreshSecurity401:
    """AC 4 : 401 sur tout token inconnu/malformé/révoqué/consommé."""

    async def _prepare_token(
        self,
        case: str,
        client: AsyncClient,
        db_session: AsyncSession,
        user: User,
    ) -> str:
        """Construit le refresh token soumis selon le cas paramétré."""
        if case == "unknown":
            # Format plausible mais jamais émis par le serveur
            return "wf_rt_" + "A" * 86
        if case == "malformed":
            # Chaîne arbitraire non résolue par le lookup de hash
            return "%%not-a-valid-refresh-token%%"

        body = await _login(client, user)
        token = body["refresh_token"]

        if case == "revoked":
            # Révocation directe en base (simule logout / compromission)
            await db_session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user.id)
                .values(revoked_at=datetime.now(timezone.utc) - timedelta(minutes=5))
            )
            await db_session.commit()
        elif case == "consumed":
            # Rotation : l'ancien token devient consommé (usage unique)
            rotated = await client.post(REFRESH_URL, json={"refresh_token": token})
            assert rotated.status_code == 200, rotated.text
        return token

    @pytest.mark.parametrize(
        "case",
        ["unknown", "malformed", "revoked", "consumed"],
        ids=["unknown", "malformed", "revoked", "consumed"],
    )
    async def test_refresh_unknown_invalid_revoked_consume_all_return_401(
        self,
        case: str,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Paramétré : token inconnu / malformé / révoqué / consommé →
        401 générique ``INVALID_OR_EXPIRED_TOKEN`` (AC 4)."""
        token = await self._prepare_token(case, client, db_session, test_user)

        response = await client.post(REFRESH_URL, json={"refresh_token": token})
        assert response.status_code == 401, response.text
        assert response.json()["error"]["message"] == "INVALID_OR_EXPIRED_TOKEN"


class TestNoPlaintextToken:
    """AC 4 : le hash en base ne contient jamais la valeur claire."""

    async def test_no_plaintext_token_in_database(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Après login ET après rotation : aucune ligne de la table ne
        contient la valeur claire d'un token émis (balayage complet du
        ``token_hash`` — propriété de bout en bout)."""
        login_body = await _login(client, test_user)
        plain_login = login_body["refresh_token"]

        rotated = await client.post(REFRESH_URL, json={"refresh_token": plain_login})
        assert rotated.status_code == 200, rotated.text
        plain_rotated = unwrap(rotated)["refresh_token"]
        assert plain_rotated != plain_login

        # Balayage de TOUTES les lignes (base isolée par test)
        rows = (await db_session.execute(select(RefreshToken))).scalars().all()
        assert rows, "login + rotation doivent avoir persisté des lignes"

        for row in rows:
            assert row.token_hash != plain_login
            assert row.token_hash != plain_rotated
            assert plain_login not in row.token_hash
            assert plain_rotated not in row.token_hash
            # Hash fort Argon2 (arbitrage n°1 tranché en STORY-123.1 —
            # divergence « bcrypt » du libellé AC consignée pour STORY-252)
            assert row.token_hash.startswith("$argon2")


class TestUserIsolation:
    """AC 4 : isolation de bout en bout entre utilisateurs."""

    async def test_user_isolation_full_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
    ):
        """Deux utilisateurs A/B : logout de A, rotation de B ; tokens de
        A morts, tokens de B vivants (isolation stricte par propriétaire)."""
        body_a = await _login(client, test_user)
        body_b = await _login(client, test_superuser, SUPERUSER_PASSWORD)

        assert await _active_tokens(db_session, test_user.id)
        assert await _active_tokens(db_session, test_superuser.id)

        # Logout de A uniquement (révocation globale de A)
        logout_a = await client.post(
            LOGOUT_URL,
            headers={"Authorization": f"Bearer {body_a['access_token']}"},
        )
        assert logout_a.status_code == 200, logout_a.text

        # Tokens de A morts — refresh rejeté, plus aucune ligne active
        refresh_a = await client.post(
            REFRESH_URL, json={"refresh_token": body_a["refresh_token"]}
        )
        assert refresh_a.status_code == 401
        assert not await _active_tokens(db_session, test_user.id)

        # Tokens de B vivants — rotation de B fonctionne, lignes actives
        refresh_b = await client.post(
            REFRESH_URL, json={"refresh_token": body_b["refresh_token"]}
        )
        assert refresh_b.status_code == 200, refresh_b.text
        assert unwrap(refresh_b)["refresh_token"] != body_b["refresh_token"]
        assert await _active_tokens(db_session, test_superuser.id)


class TestExistingAuthFlows:
    """AC 4 : non-régression des flux auth existants (conftest matrice)."""

    async def test_existing_auth_suites_unaffected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
        monkeypatch,
    ):
        """disable_auth → 200 sans header ; login username ET email → 200 ;
        register → 201 ; logout → 200 (revalidation non-régression)."""
        from app.auth import dependencies as auth_deps

        # 1. disable_auth : auto-login superadmin, 200 sans header
        monkeypatch.setattr(auth_deps.settings, "disable_auth", True)
        try:
            no_auth = await client.get("/api/v1/users/")
            assert no_auth.status_code == 200, no_auth.text
        finally:
            monkeypatch.setattr(auth_deps.settings, "disable_auth", False)

        # 2. Login username ET email → 200
        by_username = await client.post(
            LOGIN_URL,
            data={"username": test_user.username, "password": USER_PASSWORD},
        )
        assert by_username.status_code == 200, by_username.text

        by_email = await client.post(
            LOGIN_URL,
            data={"username": test_user.email, "password": USER_PASSWORD},
        )
        assert by_email.status_code == 200, by_email.text

        # 3. Register → 201 (org par défaut provisionnée si absente)
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

        register = await client.post(
            REGISTER_URL,
            json={
                "email": "sec-newuser@example.com",
                "username": "sec-newuser",
                "password": "SecurePass123!",
            },
        )
        assert register.status_code == 201, register.text

        # 4. Logout authentifié → 200
        logout = await client.post(
            LOGOUT_URL,
            headers={"Authorization": f"Bearer {unwrap(by_username)['access_token']}"},
        )
        assert logout.status_code == 200, logout.text


class TestPurgeExpiredEntries:
    """AC 3 (part purge) : le job supprime les entrées expirées/révoquées."""

    async def test_purge_job_removes_expired_entries(
        self, db_session: AsyncSession, test_user: User
    ):
        """Lignes expirées insérées → exécution de la fonction de purge
        (appel direct — celle que la boucle lifespan exécute) → lignes
        supprimées ; lignes actives et révoquées récentes conservées."""
        now = datetime.now(timezone.utc)

        def _row(
            hash_label: str,
            *,
            expires_at: datetime,
            revoked_at: datetime | None,
        ) -> RefreshToken:
            return RefreshToken(
                user_id=test_user.id,
                token_hash=f"purge-fixture-{hash_label}",
                expires_at=expires_at,
                revoked_at=revoked_at,
            )

        db_session.add_all(
            [
                # Expirée depuis 1 h, jamais révoquée → purgée
                _row(
                    "expired",
                    expires_at=now - timedelta(hours=1),
                    revoked_at=None,
                ),
                # Révoquée depuis 8 jours (au-delà de la rétention 7 j) → purgée
                _row(
                    "revoked-old",
                    expires_at=now + timedelta(days=1),
                    revoked_at=now - timedelta(days=8),
                ),
                # Active → JAMAIS purgée
                _row(
                    "active",
                    expires_at=now + timedelta(days=1),
                    revoked_at=None,
                ),
                # Révoquée depuis 1 jour (fenêtre d'audit) → conservée
                _row(
                    "revoked-recent",
                    expires_at=now + timedelta(days=1),
                    revoked_at=now - timedelta(days=1),
                ),
            ]
        )
        await db_session.commit()

        removed = await RefreshTokenService.purge_expired(db_session)

        assert removed == 2, "seules les lignes expirée et révoquée-vieille partent"
        remaining = {
            row.token_hash
            for row in (
                await db_session.execute(
                    select(RefreshToken).execution_options(populate_existing=True)
                )
            )
            .scalars()
            .all()
        }
        assert remaining == {
            "purge-fixture-active",
            "purge-fixture-revoked-recent",
        }
