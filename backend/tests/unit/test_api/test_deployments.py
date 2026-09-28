"""Tests unitaires API deployments — non-exposition des valeurs sensibles (STORY-103.3).

Vérifie que l'API REST ne renvoie JAMAIS les valeurs des variables
sensibles en clair, que le snapshot en base soit chiffré (token Fernet)
ou legacy en clair. Les déploiements sont insérés directement en session
de test (pas de POST : le déploiement asynchrone n'est pas lancé), puis
lus via GET — le chemin réel de lecture de l'API.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secret_manager import SecretManager, reset_secret_manager
from app.models.deployment import (
    Deployment,
    DeploymentStatus,
    encrypt_variables_for_storage,
)
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.target import Target
from app.models.user import User
from tests.conftest import unwrap

PLAIN_SECRET = "S3cr3t!Pass-103-3"
PLAIN_TOKEN = "tok_api_103-3"

PLAIN_VARIABLES: dict = {
    "db_password": PLAIN_SECRET,
    "api_token": PLAIN_TOKEN,
    "domain": "app.example.com",
}


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé déterministe)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


async def _seed_deployment(
    db_session: AsyncSession,
    organization: Organization,
    stack: Stack,
    target: Target,
    variables: dict,
) -> Deployment:
    """Insère un déploiement avec le snapshot donné (sans lancer la tâche)."""
    deployment = Deployment(
        stack_id=stack.id,
        target_id=target.id,
        organization_id=organization.id,
        name="sec-test-deployment",
        config={},
        variables=variables,
        status=DeploymentStatus.RUNNING,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)
    return deployment


class TestDeploymentsApiNeverReturnsPlainValues:
    """AC 3 — aucune valeur sensible en clair dans les payloads JSON."""

    async def test_deployments_api_never_returns_plain_values(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """GET déploiement (snapshot chiffré) : valeurs masquées ``***``."""
        stack = Stack(
            name="sec-stack",
            template={"image": "nginx"},
            variables={},
            organization_id=test_organization.id,
            version="1.0.0",
        )
        target = Target(
            name="sec-target",
            host="127.0.0.1",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add_all([stack, target])
        await db_session.commit()

        deployment = await _seed_deployment(
            db_session,
            test_organization,
            stack,
            target,
            encrypt_variables_for_storage(dict(PLAIN_VARIABLES)),
        )

        # Détail
        response = await admin_client.get(f"/api/v1/deployments/{deployment.id}")
        assert response.status_code == 200
        payload = unwrap(response)
        assert payload["variables"]["db_password"] == "***"
        assert payload["variables"]["api_token"] == "***"
        assert payload["variables"]["domain"] == "app.example.com"
        # Aucun secret en clair dans le payload complet.
        assert PLAIN_SECRET not in response.text
        assert PLAIN_TOKEN not in response.text
        # Ni ciphertext exposé (la clé resterait deviner-able côté client).
        assert "gAAAA" not in response.text

        # Liste — même exigence
        list_response = await admin_client.get("/api/v1/deployments")
        assert list_response.status_code == 200
        assert PLAIN_SECRET not in list_response.text
        assert PLAIN_TOKEN not in list_response.text
        assert "gAAAA" not in list_response.text

    async def test_deployments_api_masks_legacy_clear_snapshot(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_superuser: User,
        test_organization: Organization,
    ):
        """GET déploiement (snapshot legacy en clair) : aussi masqué."""
        stack = Stack(
            name="sec-stack-legacy",
            template={"image": "nginx"},
            variables={},
            organization_id=test_organization.id,
            version="1.0.0",
        )
        target = Target(
            name="sec-target-legacy",
            host="127.0.0.1",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add_all([stack, target])
        await db_session.commit()

        deployment = await _seed_deployment(
            db_session,
            test_organization,
            stack,
            target,
            dict(PLAIN_VARIABLES),  # legacy : clair en base
        )

        response = await admin_client.get(f"/api/v1/deployments/{deployment.id}")
        assert response.status_code == 200
        assert unwrap(response)["variables"]["db_password"] == "***"
        assert PLAIN_SECRET not in response.text

    async def test_deployments_api_encrypted_at_rest(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """Oracle complémentaire : la valeur en base est bien un ciphertext."""
        stack = Stack(
            name="sec-stack-atrest",
            template={},
            variables={},
            organization_id=test_organization.id,
            version="1.0.0",
        )
        target = Target(
            name="sec-target-atrest",
            host="127.0.0.1",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add_all([stack, target])
        await db_session.commit()

        deployment = await _seed_deployment(
            db_session,
            test_organization,
            stack,
            target,
            encrypt_variables_for_storage(dict(PLAIN_VARIABLES)),
        )

        stored = deployment.variables
        assert SecretManager.is_encrypted(stored["db_password"])
        assert SecretManager.is_encrypted(stored["api_token"])
        assert stored["domain"] == "app.example.com"
