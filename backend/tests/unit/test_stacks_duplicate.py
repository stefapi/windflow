"""Tests pour l'endpoint de duplication de stack."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.stack import Stack
from app.models.user import User
from app.schemas.stack import StackCreate
from app.services.stack_service import StackService


@pytest.fixture
async def test_stack(db_session: AsyncSession, test_organization: Organization) -> Stack:
    """Crée un stack de test."""
    stack_data = StackCreate(
        name="Original Stack",
        description="A stack to duplicate",
        template={"version": "3.8", "services": {"web": {"image": "nginx:latest"}}},
        variables={"port": {"type": "integer", "default": 80}},
        version="1.0.0",
        category="web",
        tags=["web", "nginx"],
        is_public=True,
        organization_id=test_organization.id,
    )
    stack = await StackService.create(db_session, stack_data)
    return stack


@pytest.fixture
async def second_organization(db_session: AsyncSession) -> Organization:
    """Crée une seconde organisation pour les tests cross-org."""
    org = Organization(
        name="Second Organization",
        slug="second-org",
        description="Second org for duplication tests",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


class TestDuplicateStack:
    """Tests pour POST /api/v1/stacks/{stack_id}/duplicate."""

    @pytest.mark.asyncio
    async def test_duplicate_stack_success(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Dupliquer un stack existant avec un nouveau nom → 200."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{test_stack.id}/duplicate",
            json={"new_name": "Duplicated Stack"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Duplicated Stack"
        assert data["template"] == test_stack.template
        assert "duplicate" in data["tags"]
        assert data["is_public"] is False
        assert data["organization_id"] == test_stack.organization_id
        assert data["id"] != test_stack.id

    @pytest.mark.asyncio
    async def test_duplicate_stack_not_found(
        self,
        authenticated_client: AsyncClient,
    ):
        """Dupliquer un stack inexistant → 404."""
        response = await authenticated_client.post(
            "/api/v1/stacks/nonexistent-id/duplicate",
            json={"new_name": "New Stack"},
        )

        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_duplicate_stack_name_conflict(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Dupliquer avec un nom déjà existant dans la même org → 409."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{test_stack.id}/duplicate",
            json={"new_name": test_stack.name},
        )

        assert response.status_code == 409
        assert "existe déjà" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_duplicate_stack_different_org(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
        second_organization: Organization,
    ):
        """Dupliquer vers une autre organisation → 200."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{test_stack.id}/duplicate",
            json={
                "new_name": "Duplicated in Other Org",
                "organization_id": second_organization.id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["organization_id"] == second_organization.id
        assert data["name"] == "Duplicated in Other Org"

    @pytest.mark.asyncio
    async def test_duplicate_stack_empty_name(
        self,
        authenticated_client: AsyncClient,
        test_stack: Stack,
    ):
        """Body avec new_name vide → 422 (validation Pydantic)."""
        response = await authenticated_client.post(
            f"/api/v1/stacks/{test_stack.id}/duplicate",
            json={"new_name": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicate_stack_unauthenticated(
        self,
        client: AsyncClient,
        test_stack: Stack,
    ):
        """Appel sans token → 401."""
        response = await client.post(
            f"/api/v1/stacks/{test_stack.id}/duplicate",
            json={"new_name": "Unauthorized Copy"},
        )

        assert response.status_code == 401
