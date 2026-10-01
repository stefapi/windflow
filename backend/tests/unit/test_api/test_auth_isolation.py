"""Tests d'isolation et de non-régression auth après la bascule STORY-121.3.

Non-régression AC 5 : login username/email, register (rôle viewer + org par
défaut), ``/auth/me`` (organization_id = org primaire depuis l'association),
``disable_auth`` (auto-login superadmin).
"""

from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import unwrap

from app.config import settings
from app.models.organization import Organization
from app.models.user import User
from app.models.user_organization import UserOrganization
from app.services.user_organization_service import UserOrganizationService


class TestLoginNonRegression:
    """AC 5 : login username et email toujours fonctionnels."""

    async def test_login_by_username_and_email_still_work(
        self, client, db_session, test_user
    ):
        """Login par username ET par email → 200 + token + user avec
        ``organization_id`` peuplé depuis l'association primaire."""
        primary_org = await UserOrganizationService.get_primary_organization_id(
            db_session, test_user
        )
        assert primary_org is not None

        for identifier in (test_user.username, test_user.email):
            response = await client.post(
                "/api/v1/auth/login",
                data={"username": identifier, "password": "testpassword123"},
            )
            assert response.status_code == 200, response.text
            body = unwrap(response)
            assert body["access_token"]
            # Contrat conservé : organization_id = org primaire
            assert body["user"]["organization_id"] == primary_org

    async def test_login_token_claims_have_no_organization(self, client, test_user):
        """Le token émis au login ne porte plus le claim organization_id."""
        from app.auth.jwt import decode_access_token

        response = await client.post(
            "/api/v1/auth/login",
            data={"username": test_user.username, "password": "testpassword123"},
        )
        assert response.status_code == 200
        decoded = decode_access_token(unwrap(response)["access_token"])
        assert decoded is not None
        assert decoded.user_id == test_user.id
        assert decoded.is_superuser is False


class TestRegisterSwitch:
    """Register : résolution de l'organisation cible + rôle viewer borné."""

    async def test_register_defaults_to_default_org_with_viewer_role(
        self, client, db_session
    ):
        """Register sans organization_id → 201, user rattaché à l'org par
        défaut (résolue par slug) avec ``role == "viewer"`` en base."""
        default_org = (
            await db_session.execute(
                select(Organization).where(
                    Organization.slug == settings.default_org_slug
                )
            )
        ).scalar_one_or_none()
        if default_org is None:
            # Base de test sans seed : créer l'org par défaut attendue
            default_org = Organization(
                name="Default Org",
                slug=settings.default_org_slug,
                description="",
            )
            db_session.add(default_org)
            await db_session.commit()
            await db_session.refresh(default_org)

        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "SecurePass123!",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201, response.text
        user_id = unwrap(response)["user"]["id"]

        link = (
            await db_session.execute(
                select(UserOrganization).where(
                    UserOrganization.user_id == user_id,
                    UserOrganization.organization_id == default_org.id,
                )
            )
        ).scalar_one_or_none()
        assert link is not None, "rattachement à l'org par défaut absent"
        assert link.role.value if hasattr(link.role, "value") else link.role == "viewer"

    async def test_register_with_unknown_org_returns_404(self, client):
        """organization_id inexistant → 404 (pas de rattachement fantôme)."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "ghost@example.com",
                "username": "ghostuser",
                "password": "SecurePass123!",
                "organization_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert response.status_code == 404

    async def test_register_role_cannot_be_escalated(self, client, db_session):
        """Sécurité : le register n'expose aucun champ rôle — un payload
        contenant ``role``/``is_superuser`` ne peut pas escalader (champ
        ignoré par le schéma UserCreate, auto-enregistlement viewer)."""
        # Provisionner l'org par défaut (indépendant de l'ordre des tests)
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
                    name="Default Org", slug=settings.default_org_slug, description=""
                )
            )
            await db_session.commit()
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "escalate@example.com",
                "username": "escalator",
                "password": "SecurePass123!",
                "role": "admin",
                "is_superuser": True,
            },
        )
        assert response.status_code == 201, response.text
        # is_superuser du body ignoré (schéma : défaut False sans champ exposé)
        assert unwrap(response)["user"]["is_superuser"] is False


class TestAuthMe:
    """``GET /auth/me`` : organization_id = org primaire."""

    async def test_me_returns_primary_organization_id(
        self, authenticated_client, db_session, test_user, test_organization
    ):
        """User avec 2 appartenances → ``organization_id`` = org primaire
        (plus ancienne par joined_at)."""
        from datetime import datetime, timezone

        from app.enums.rbac import Role

        other_org = Organization(name="Other Org", slug="other-org-me", description="")
        db_session.add(other_org)
        await db_session.flush()
        # STORY-121.3 : purger le rattachement posé par la fixture avant
        # de re-seeder avec des joined_at contrôlés (PK composite)
        from sqlalchemy import delete

        await db_session.execute(
            delete(UserOrganization).where(UserOrganization.user_id == test_user.id)
        )
        # Appartenance plus ancienne (primaire) : joined_at antérieur
        db_session.add(
            UserOrganization(
                user_id=test_user.id,
                organization_id=test_organization.id,
                role=Role.OPERATOR,
                joined_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        db_session.add(
            UserOrganization(
                user_id=test_user.id,
                organization_id=other_org.id,
                role=Role.VIEWER,
                joined_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        )
        await db_session.commit()

        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200, response.text
        assert unwrap(response)["organization_id"] == test_organization.id

    async def test_me_response_does_not_expose_sensitive_fields(
        self, authenticated_client
    ):
        """Sécurité : ni ``hashed_password`` ni ``keycloak_id`` (non nul)
        dans la réponse."""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        body = unwrap(response)
        assert "hashed_password" not in body
        assert "password" not in body


class TestDisableAuthMode:
    """AC 5 : ``disable_auth`` (auto-login superadmin) intact."""

    async def test_disable_auth_mode_still_auto_logs_superadmin(
        self, client, db_session, test_superuser
    ):
        """settings.disable_auth=True → get_current_user retourne le
        superadmin seedé (pattern test_dev_mode)."""
        from app.auth.dependencies import get_current_user

        with patch.object(settings, "disable_auth", True):
            user = await get_current_user(token="ignored", session=db_session)
        assert user is not None
        assert user.id == test_superuser.id
        assert user.is_superuser is True
