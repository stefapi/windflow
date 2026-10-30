"""Tests unitaires — rendu/déploiement avec snapshots chiffrés (STORY-103.3).

Tâche 3 : vérifie que le pipeline de rendu/déploiement fonctionne à
l'identique avec des snapshots chiffrés au repos :
- ``DeploymentService.create`` chiffre bien les snapshots à la
  persistance (colonne = tokens Fernet) ;
- le rendu (substitution Jinja) reçoit les valeurs **déchiffrées en
  mémoire** : les macros ``{{ db_password }}`` produisent la valeur en
  clair attendue dans le config rendu, jamais un token ``gAAAA`` ;
- la relance (retry) repart des valeurs déchiffrées du snapshot.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secret_manager import SecretManager, reset_secret_manager
from app.models.deployment import DeploymentStatus
from app.models.organization import Organization
from app.models.stack import Stack
from app.models.host import Host
from app.schemas.deployment import DeploymentCreate
from app.services.deployment_service import DeploymentService

PLAIN_PASSWORD = "pg-S3cr3t-103-3"

STACK_VARIABLES: dict = {
    "db_password": {"type": "password", "label": "DB password", "required": True},
    "domain": {"type": "string", "default": "app.example.com"},
}


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé déterministe)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


async def _seed_stack(
    db_session: AsyncSession, organization: Organization
) -> tuple[Stack, Host]:
    """Crée le stack (template + variables) et la cible de déploiement."""
    stack = Stack(
        name="render-sec-stack",
        template={
            "image": "postgres:16",
            "environment": {"POSTGRES_PASSWORD": "{{ db_password }}"},
            "labels": {"app.domain": "{{ domain }}"},
        },
        variables=dict(STACK_VARIABLES),
        organization_id=organization.id,
        version="1.0.0",
    )
    target = Host(
        name="render-sec-target",
        host="127.0.0.1",
        credentials={},
        organization_id=organization.id,
    )
    db_session.add_all([stack, target])
    await db_session.commit()
    await db_session.refresh(stack)
    await db_session.refresh(target)
    return stack, target


def _orchestrator_stub() -> AsyncMock:
    """Stub de DeploymentOrchestrator.start_deployment (aucune tâche réelle)."""
    stub = AsyncMock(return_value=None)
    # AsyncMock se comporte comme un awaitable nul — suffisant pour create().
    return stub


class TestRenderReceivesDecryptedValues:
    """AC 3 — le rendu consomme les valeurs déchiffrées en mémoire."""

    async def test_render_receives_decrypted_values(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """create() : colonnes chiffrées + config rendu avec valeurs en clair."""
        stack, target = await _seed_stack(db_session, test_organization)

        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            new=_orchestrator_stub(),
        ):
            deployment = await DeploymentService.create(
                db_session,
                DeploymentCreate(
                    stack_id=stack.id,
                    target_id=target.id,
                    variables={"db_password": PLAIN_PASSWORD},
                ),
                organization_id=test_organization.id,
                user_id="user-1",
            )

        # 1. Snapshots chiffrés au repos : valeurs sensibles en gAAAA.
        stored_vars = deployment.variables
        assert SecretManager.is_encrypted(stored_vars["db_password"])
        assert stored_vars["domain"] == "app.example.com"

        # 2. Le rendu (config) contient la valeur DÉCHIFFRÉE en mémoire :
        #    la macro Jinja a bien reçu le mot de passe en clair.
        rendered_config = deployment.config
        assert (
            rendered_config["environment"]["POSTGRES_PASSWORD"] == PLAIN_PASSWORD
        ), "le rendu doit recevoir la valeur déchiffrée, pas le token gAAAA"
        assert rendered_config["labels"]["app.domain"] == "app.example.com"
        # Le token ne fuit pas dans le rendu.
        assert "gAAAA" not in str(rendered_config)

        # 3. Accès déchiffré : round-trip depuis la colonne chiffrée.
        assert deployment.decrypted_variables["db_password"] == PLAIN_PASSWORD

    async def test_snapshot_columns_encrypted_after_create(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """La colonne variables persistée ne contient aucun clair sensible."""
        stack, target = await _seed_stack(db_session, test_organization)

        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            new=_orchestrator_stub(),
        ):
            deployment = await DeploymentService.create(
                db_session,
                DeploymentCreate(
                    stack_id=stack.id,
                    target_id=target.id,
                    variables={"db_password": PLAIN_PASSWORD},
                ),
                organization_id=test_organization.id,
                user_id="user-1",
            )

        # Recharger depuis la base pour lire la colonne réellement persistée.
        deployment_id = deployment.id
        db_session.expire_all()
        from sqlalchemy import select

        from app.models.deployment import Deployment

        result = await db_session.execute(
            select(Deployment).where(Deployment.id == deployment_id)
        )
        persisted = result.scalar_one()
        assert SecretManager.is_encrypted(persisted.variables["db_password"])
        assert PLAIN_PASSWORD not in str(persisted.variables)

    async def test_retry_uses_decrypted_snapshot(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
    ):
        """Tâche 3 — retry : l'orchestrateur reçoit les valeurs déchiffrées."""
        stack, target = await _seed_stack(db_session, test_organization)

        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            new=_orchestrator_stub(),
        ) as create_stub:
            deployment = await DeploymentService.create(
                db_session,
                DeploymentCreate(
                    stack_id=stack.id,
                    target_id=target.id,
                    variables={"db_password": PLAIN_PASSWORD},
                ),
                organization_id=test_organization.id,
                user_id="user-1",
            )
            assert create_stub.await_count == 1
            # create() passe la configuration en clair au premier lancement.
            first_call: Any = create_stub.await_args
            assert first_call.kwargs["configuration"]["db_password"] == PLAIN_PASSWORD

        # Simuler un échec puis relancer : le retry relit la colonne
        # chiffrée et doit repasser les valeurs déchiffrées en mémoire.
        deployment.status = DeploymentStatus.FAILED
        await db_session.commit()

        with patch(
            "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment",
            new=_orchestrator_stub(),
        ) as retry_stub:
            ok = await DeploymentService.retry_deployment(
                db_session, deployment.id, "user-1"
            )
            assert ok is True
            assert retry_stub.await_count == 1
            retry_call: Any = retry_stub.await_args
            assert (
                retry_call.kwargs["configuration"]["db_password"] == PLAIN_PASSWORD
            ), "le retry doit déchiffrer le snapshot avant relance"
