"""Tests pour les endpoints d'archivage/désarchivage de stack."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import error_message, unwrap

from app.models.organization import Organization
from app.models.stack import Stack
from app.schemas.stack import StackCreate
from app.services.stack_service import StackService


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 122.2.

    Le fichier ``.env`` local (git-ignored) peut contenir ``DISABLE_AUTH=true``
    (valeur recommandée par ``env.example`` pour le dev). Sans ce forçage,
    ``get_current_user`` court-circuite le JWT pour chercher un superadmin
    en base → 500 ``INTERNAL_ERROR`` sur tous les endpoints authentifiés.
    """

    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


@pytest.fixture
async def test_stack(
    db_session: AsyncSession, test_organization: Organization
) -> Stack:
    """Crée un stack de test."""
    stack_data = StackCreate(
        name="Archive Test Stack",
        description="A stack for archive tests",
        template={"version": "3.8", "services": {"web": {"image": "nginx:latest"}}},
        variables={"port": {"type": "integer", "default": 80}},
        version="1.0.0",
        category="web",
        tags=["web"],
        is_public=True,
        organization_id=test_organization.id,
    )
    stack = await StackService.create(db_session, stack_data)
    return stack


@pytest.fixture
async def archived_stack(db_session: AsyncSession, test_stack: Stack) -> Stack:
    """Archive le stack de test."""
    return await StackService.archive(db_session, test_stack.id)


@pytest.fixture
async def second_organization(db_session: AsyncSession) -> Organization:
    """Crée une seconde organisation pour les tests cross-org."""
    org = Organization(
        name="Second Organization",
        slug="second-org",
        description="Second org for archive tests",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


class TestArchiveStack:
    """Tests pour POST /api/v1/stacks/{stack_id}/archive."""

    @pytest.mark.asyncio
    async def test_archive_stack_success(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Archiver un stack existant dans sa propre org → 200."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{test_stack.id}/archive",
        )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["action"] == "archive"
        assert data["stack_id"] == test_stack.id
        assert "archivée" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_archive_stack_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Archiver un stack inexistant → 404."""
        response = await authenticated_client.post(
            "/api/v1/stacks/nonexistent-id/archive",
        )

        assert response.status_code == 404
        assert "non trouvé" in error_message(response).lower()

    @pytest.mark.asyncio
    async def test_archive_stack_already_archived(
        self,
        authenticated_client: AsyncClient,
        archived_stack: Stack,
    ):
        """Archiver un stack déjà archivé → 200 (idempotent)."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{archived_stack.id}/archive",
        )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_archive_stack_unauthenticated(
        self,
        client: AsyncClient,
        test_stack: Stack,
    ):
        """Appel sans token → 401."""
        response = await client.post(
            f"/api/v1/stacks/{test_stack.id}/archive",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_archive_stack_forbidden_org(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        second_organization: Organization,
    ):
        """Archiver un stack d'une autre organisation → 403."""
        # Créer un stack dans la seconde organisation
        stack = Stack(
            name="Other Org Stack",
            description="Stack in another org",
            template={"version": "3.8", "services": {}},
            variables={},
            organization_id=second_organization.id,
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        response = await authenticated_client.post(
            f"/api/v1/stacks/{stack.id}/archive",
        )

        assert response.status_code == 403


class TestUnarchiveStack:
    """Tests pour POST /api/v1/stacks/{stack_id}/unarchive."""

    @pytest.mark.asyncio
    async def test_unarchive_stack_success(
        self,
        authenticated_client: AsyncClient,
        archived_stack: Stack,
    ):
        """Désarchiver un stack archivé → 200."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{archived_stack.id}/unarchive",
        )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True
        assert data["action"] == "unarchive"
        assert "désarchivée" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_unarchive_stack_not_archived(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Désarchiver un stack non archivé → 200 (idempotent)."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{test_stack.id}/unarchive",
        )

        assert response.status_code == 200
        data = unwrap(response)
        assert data["success"] is True


class TestListStacksArchiveFilter:
    """Tests pour le filtre include_archived sur list_stacks."""

    @pytest.mark.asyncio
    async def test_list_stacks_excludes_archived(
        self,
        authenticated_client: AsyncClient,
        archived_stack: Stack,
    ):
        """Lister les stacks exclut les archivées par défaut (STORY-128 :
        liste paginée sous ``data`` — unwrap déplie l'enveloppe)."""
        response = await authenticated_client.get("/api/v1/stacks/")

        assert response.status_code == 200
        body = response.json()
        assert "pagination" in body, f"contrat paginé STORY-128 : {list(body)}"
        stack_ids = [s["id"] for s in body["data"]]
        assert archived_stack.id not in stack_ids

    @pytest.mark.asyncio
    async def test_list_stacks_includes_archived(
        self,
        authenticated_client: AsyncClient,
        archived_stack: Stack,
    ):
        """Lister avec include_archived=true → toutes les stacks (total
        filtré exact — AC 3)."""
        response = await authenticated_client.get(
            "/api/v1/stacks/",
            params={"include_archived": "true"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "pagination" in body
        stack_ids = [s["id"] for s in body["data"]]
        assert archived_stack.id in stack_ids
