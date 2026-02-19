"""Tests unitaires pour DeploymentService."""

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.deployment_service import DeploymentService
from app.schemas.deployment import DeploymentCreate
from app.models.deployment import Deployment
from app.models.stack import Stack
from app.models.target import Target
from app.models.user import User
from app.models.organization import Organization

ORCH_PATCH = "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment"


@pytest.mark.asyncio
class TestDeploymentService:
    """Tests pour le service de déploiement."""

    async def test_create_deployment(
        self,
        db_session: AsyncSession,
        test_stack: Stack,
        test_target: Target,
        test_user: User,
        test_organization: Organization
    ):
        """Test de création d'un déploiement."""
        deployment_data = DeploymentCreate(
            name="Test Deployment",
            stack_id=test_stack.id,
            target_id=test_target.id,
            config={
                "version": "3.8",
                "services": {
                    "web": {
                        "image": "nginx:latest"
                    }
                }
            },
            variables={"port": 8080}
        )

        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            deployment = await DeploymentService.create(
                db_session,
                deployment_data,
                organization_id=str(test_organization.id),
                user_id=str(test_user.id)
            )

        assert deployment.id is not None
        assert deployment.name == "Test Deployment"
        assert deployment.stack_id == test_stack.id
        assert deployment.target_id == test_target.id

    async def test_get_by_id(
        self,
        db_session: AsyncSession,
        test_stack: Stack,
        test_target: Target,
        test_user: User,
        test_organization: Organization
    ):
        """Test de récupération par ID."""
        deployment_data = DeploymentCreate(
            name="Deployment to Retrieve",
            stack_id=test_stack.id,
            target_id=test_target.id,
            config={"test": "config"},
            variables={}
        )

        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            created = await DeploymentService.create(
                db_session,
                deployment_data,
                organization_id=str(test_organization.id),
                user_id=str(test_user.id)
            )

        deployment = await DeploymentService.get_by_id(db_session, created.id)
        assert deployment is not None
        assert deployment.id == created.id
        assert deployment.name == "Deployment to Retrieve"

    async def test_get_by_id_not_found(self, db_session: AsyncSession):
        """Test de récupération avec ID inexistant."""
        deployment = await DeploymentService.get_by_id(
            db_session,
            "non-existent-id"
        )
        assert deployment is None

    async def test_list_all(
        self,
        db_session: AsyncSession,
        test_stack: Stack,
        test_target: Target,
        test_user: User,
        test_organization: Organization
    ):
        """Test de listage de tous les déploiements."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            for i in range(3):
                deployment_data = DeploymentCreate(
                    name=f"Deployment {i}",
                    stack_id=test_stack.id,
                    target_id=test_target.id,
                    config={"index": i},
                    variables={}
                )
                await DeploymentService.create(
                    db_session,
                    deployment_data,
                    organization_id=str(test_organization.id),
                    user_id=str(test_user.id)
                )

        deployments = await DeploymentService.list_all(db_session)
        assert len(deployments) == 3
        assert all(isinstance(d, Deployment) for d in deployments)

    async def test_list_all_with_pagination(
        self,
        db_session: AsyncSession,
        test_stack: Stack,
        test_target: Target,
        test_user: User,
        test_organization: Organization
    ):
        """Test de listage avec pagination."""
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            for i in range(5):
                deployment_data = DeploymentCreate(
                    name=f"Deployment {i}",
                    stack_id=test_stack.id,
                    target_id=test_target.id,
                    config={"index": i},
                    variables={}
                )
                await DeploymentService.create(
                    db_session,
                    deployment_data,
                    organization_id=str(test_organization.id),
                    user_id=str(test_user.id)
                )

        deployments = await DeploymentService.list_all(
            db_session,
            skip=1,
            limit=2
        )
        assert len(deployments) == 2

    async def test_create_deployment_with_empty_variables(
        self,
        db_session: AsyncSession,
        test_stack: Stack,
        test_target: Target,
        test_user: User,
        test_organization: Organization
    ):
        """Test de création avec variables vides."""
        deployment_data = DeploymentCreate(
            name="Deployment Without Variables",
            stack_id=test_stack.id,
            target_id=test_target.id,
            config={"test": "config"}
        )

        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            deployment = await DeploymentService.create(
                db_session,
                deployment_data,
                organization_id=str(test_organization.id),
                user_id=str(test_user.id)
            )

        assert deployment is not None
        assert deployment.name == "Deployment Without Variables"
