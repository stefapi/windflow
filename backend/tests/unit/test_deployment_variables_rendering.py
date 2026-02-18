"""Test pour valider que les variables avec macros sont rendues avant stockage."""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.deployment_service import DeploymentService
from app.schemas.deployment import DeploymentCreate
from app.models.stack import Stack
from app.models.target import Target


@pytest.mark.asyncio
class TestDeploymentVariablesRendering:
    """Tests pour le rendu des variables avant stockage."""

    @patch('app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment', new_callable=AsyncMock)
    async def test_variables_with_macros_are_rendered_before_storage(
        self,
        mock_start_deployment: AsyncMock,
        db_session: AsyncSession
    ):
        """
        Test que les variables contenant des macros Jinja2 sont rendues
        AVANT d'être stockées dans le déploiement.

        Cela garantit que le frontend reçoit les valeurs générées,
        pas les macros brutes comme {{ generate_password(24) }}.
        """
        # Créer une target de test
        from app.models.target import TargetType, TargetStatus
        target = Target(
            name="Test Target",
            description="Target de test",
            host="localhost",
            port=2375,
            type=TargetType.DOCKER,
            status=TargetStatus.ONLINE,
            credentials={},
            organization_id="test-org"
        )
        db_session.add(target)
        await db_session.commit()
        await db_session.refresh(target)

        # Créer un stack avec des variables contenant des macros
        stack = Stack(
            name="PostgreSQL Test",
            description="Stack de test avec macros",
            template={
                "services": {
                    "postgres": {
                        "image": "postgres:15",
                        "environment": {
                            "POSTGRES_PASSWORD": "{{ db_password }}",
                            "POSTGRES_USER": "{{ db_user }}"
                        }
                    }
                }
            },
            variables={
                "db_password": {
                    "default": "{{ generate_password(24) }}",
                    "description": "Mot de passe PostgreSQL"
                },
                "db_user": {
                    "default": "postgres",
                    "description": "Utilisateur PostgreSQL"
                }
            },
            organization_id="test-org"
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        # Créer un déploiement SANS fournir de variables
        # (doit utiliser les defaults du stack)
        deployment_data = DeploymentCreate(
            stack_id=str(stack.id),
            target_id=str(target.id),
            variables={}  # Pas de variables utilisateur
        )

        deployment = await DeploymentService.create(
            db_session,
            deployment_data,
            organization_id="test-org",
            user_id="test-user"
        )

        # Vérifier que les variables stockées ont les macros RENDUES
        assert "db_password" in deployment.variables
        assert "db_user" in deployment.variables

        # Le mot de passe NE DOIT PAS être la macro brute
        assert deployment.variables["db_password"] != "{{ generate_password(24) }}"

        # Le mot de passe doit avoir la bonne longueur
        assert len(deployment.variables["db_password"]) == 24

        # Le mot de passe doit être une chaîne non vide
        assert isinstance(deployment.variables["db_password"], str)
        assert len(deployment.variables["db_password"]) > 0

        # L'utilisateur doit être la valeur par défaut
        assert deployment.variables["db_user"] == "postgres"

    @patch('app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment', new_callable=AsyncMock)
    async def test_user_provided_variables_override_defaults(
        self,
        mock_start_deployment: AsyncMock,
        db_session: AsyncSession
    ):
        """
        Test que les variables fournies par l'utilisateur
        overrident les defaults du stack.
        """
        # Créer une target de test
        from app.models.target import TargetType, TargetStatus
        target = Target(
            name="Test Target 2",
            description="Target de test",
            host="localhost",
            port=2375,
            type=TargetType.DOCKER,
            status=TargetStatus.ONLINE,
            credentials={},
            organization_id="test-org"
        )
        db_session.add(target)
        await db_session.commit()
        await db_session.refresh(target)

        # Créer un stack avec des variables contenant des macros
        stack = Stack(
            name="App Test",
            description="Stack de test",
            template={
                "app": {
                    "secret": "{{ app_secret }}"
                }
            },
            variables={
                "app_secret": {
                    "default": "{{ generate_secret(32) }}",
                    "description": "Secret de l'application"
                }
            },
            organization_id="test-org"
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        # Créer un déploiement avec une variable utilisateur
        user_secret = "my-custom-secret-123"
        deployment_data = DeploymentCreate(
            stack_id=str(stack.id),
            target_id=str(target.id),
            variables={"app_secret": user_secret}
        )

        deployment = await DeploymentService.create(
            db_session,
            deployment_data,
            organization_id="test-org",
            user_id="test-user"
        )

        # Vérifier que la variable utilisateur a été utilisée
        assert deployment.variables["app_secret"] == user_secret
        # Et PAS le default généré
        assert deployment.variables["app_secret"] != "{{ generate_secret(32) }}"

    @patch('app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment', new_callable=AsyncMock)
    async def test_multiple_macros_generate_different_values(
        self,
        mock_start_deployment: AsyncMock,
        db_session: AsyncSession
    ):
        """
        Test que plusieurs macros generate_password() génèrent
        des valeurs différentes.
        """
        # Créer une target de test
        from app.models.target import TargetType, TargetStatus
        target = Target(
            name="Test Target 3",
            description="Target de test",
            host="localhost",
            port=2375,
            type=TargetType.DOCKER,
            status=TargetStatus.ONLINE,
            credentials={},
            organization_id="test-org"
        )
        db_session.add(target)
        await db_session.commit()
        await db_session.refresh(target)

        # Créer un stack avec plusieurs variables contenant des macros
        stack = Stack(
            name="Multi-Password Test",
            description="Stack avec plusieurs mots de passe",
            template={},
            variables={
                "admin_password": {
                    "default": "{{ generate_password(16) }}"
                },
                "user_password": {
                    "default": "{{ generate_password(16) }}"
                },
                "api_key": {
                    "default": "{{ generate_secret(32) }}"
                }
            },
            organization_id="test-org"
        )
        db_session.add(stack)
        await db_session.commit()
        await db_session.refresh(stack)

        # Créer un déploiement
        deployment_data = DeploymentCreate(
            stack_id=str(stack.id),
            target_id=str(target.id),
            variables={}
        )

        deployment = await DeploymentService.create(
            db_session,
            deployment_data,
            organization_id="test-org",
            user_id="test-user"
        )

        # Vérifier que tous les mots de passe ont été générés
        admin_pwd = deployment.variables["admin_password"]
        user_pwd = deployment.variables["user_password"]
        api_key = deployment.variables["api_key"]

        # Aucun ne doit être une macro brute
        assert admin_pwd != "{{ generate_password(16) }}"
        assert user_pwd != "{{ generate_password(16) }}"
        assert api_key != "{{ generate_secret(32) }}"

        # Tous doivent avoir la bonne longueur
        assert len(admin_pwd) == 16
        assert len(user_pwd) == 16
        assert len(api_key) == 32

        # Les deux mots de passe doivent être DIFFÉRENTS
        assert admin_pwd != user_pwd

        # L'API key doit être différente des mots de passe
        assert api_key != admin_pwd
        assert api_key != user_pwd
