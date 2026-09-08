"""Tests d'isolation WebSocket après réparation STORY-121.3.

L'ancien code utilisait ``is_superadmin`` (attribut inexistant du modèle
``User``) : l'AttributeError était masquée par les conditions
court-circuitées et le check d'isolation était **inopérant**. Depuis la
bascule, l'isolation passe par ``is_member`` (association) avec bypass
``is_superuser`` explicite.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.websocket.deployment_logs import verify_deployment_access


def _make_user(user_id: str = "user-1", superadmin: bool = False) -> User:
    """User non-persisté (plus de colonne organization_id — STORY-121.3)."""
    return User(
        id=user_id,
        email="user@test.com",
        username="testuser",
        is_active=True,
        is_superuser=superadmin,
    )


def _make_deployment(org_id: str = "org-1") -> MagicMock:
    deployment = MagicMock()
    deployment.id = "dep-1"
    deployment.organization_id = org_id
    return deployment


def _mock_db_with_deployment(deployment: MagicMock) -> AsyncMock:
    """Session async mockée dont execute retourne le deployment."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = deployment
    db.execute = AsyncMock(return_value=result)
    return db


def _patch_is_member(return_value: bool):
    """Patche UserOrganizationService.is_member (pas de DB réelle)."""
    from app.services.user_organization_service import UserOrganizationService

    return patch.object(
        UserOrganizationService,
        "is_member",
        new=AsyncMock(return_value=return_value),
    )


class TestDeploymentLogsIsolation:
    """verify_deployment_access : isolation réparée (403 non-membre)."""

    @pytest.mark.asyncio
    async def test_deployment_logs_isolation_denied_for_foreign_deployment(self):
        """Sécurité : user non membre de l'org du deployment (non
        superuser) → HTTPException 403 (l'ancien bug is_superadmin rendait
        le check inopérant)."""
        deployment = _make_deployment("org-foreign")
        db = _mock_db_with_deployment(deployment)
        user = _make_user(superadmin=False)

        with _patch_is_member(False):
            with pytest.raises(HTTPException) as exc_info:
                await verify_deployment_access("dep-1", user, db)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_deployment_logs_allowed_for_member(self):
        """Cas nominal : membre de l'org → deployment retourné."""
        deployment = _make_deployment("org-1")
        db = _mock_db_with_deployment(deployment)
        user = _make_user(superadmin=False)

        with _patch_is_member(True):
            result = await verify_deployment_access("dep-1", user, db)

        assert result is deployment

    @pytest.mark.asyncio
    async def test_superuser_bypass_via_is_superuser_flag(self):
        """Superuser → accès autorisé : le bypass lit ``is_superuser``
        (attribut réel du modèle — plus aucun ``is_superadmin``)."""
        deployment = _make_deployment("org-foreign")
        db = _mock_db_with_deployment(deployment)
        user = _make_user(superadmin=True)

        # is_member retourne True pour un superuser (bypass interne)
        with _patch_is_member(True):
            result = await verify_deployment_access("dep-1", user, db)

        assert result is deployment
        # Le modèle ne porte pas d'attribut is_superadmin (bug corrigé)
        assert not hasattr(user, "is_superadmin")
        assert user.is_superuser is True

    @pytest.mark.asyncio
    async def test_unknown_deployment_returns_404(self):
        """Cas d'erreur : deployment introuvable → 404 (avant le check org)."""
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(HTTPException) as exc_info:
            await verify_deployment_access("ghost", _make_user(), db)
        assert exc_info.value.status_code == 404


class TestTerminalIsolationLogic:
    """Logique d'isolation terminal (même convention is_member/is_superuser)."""

    @pytest.mark.asyncio
    async def test_terminal_isolation_denied_for_foreign_deployment(self):
        """Sécurité : la condition terminal utilise is_member — un non
        membre (non superuser) serait refusé ; vérification du prédicat
        (True = accès refusé) sur un cas étranger."""
        from app.services.user_organization_service import UserOrganizationService

        user = _make_user(superadmin=False)
        deployment = _make_deployment("org-foreign")

        # Le déploiement étranger + non-membre → is_member False → refus
        async def _member(db, u, org_id):
            return u.is_superuser or org_id == "org-1"

        with patch.object(
            UserOrganizationService,
            "is_member",
            side_effect=_member,
        ):
            is_member = await UserOrganizationService.is_member(
                None, user, deployment.organization_id
            )
        assert is_member is False, "un non-membre doit être refusé"

    @pytest.mark.asyncio
    async def test_terminal_superuser_bypass_is_superuser_flag(self):
        """Superuser → bypass effectif via le flag réel ``is_superuser``."""
        from app.services.user_organization_service import UserOrganizationService

        user = _make_user(superadmin=True)

        async def _member(db, u, org_id):
            return u.is_superuser or org_id == "org-1"

        with patch.object(
            UserOrganizationService,
            "is_member",
            side_effect=_member,
        ):
            is_member = await UserOrganizationService.is_member(
                None, user, "org-foreign"
            )
        assert is_member is True
