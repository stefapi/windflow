"""Tests unitaires du modèle DeploymentEvent (STORY-167 — Tâche 1).

Vérifie le schéma spec 06 § DeploymentEvent : defaults (uuid, created_at,
level ``info``, data), index nommés ``idx_deploy_events_deployment`` /
``idx_deploy_events_created``, domaines fermés des enums
(``DeploymentEventType`` / ``DeploymentEventLevel``), FK ``ON DELETE
CASCADE`` (PRAGMA foreign_keys=ON sous SQLite, pattern tests
ScheduledTaskExecution) et ``__repr__``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_event import (
    DeploymentEvent,
    DeploymentEventLevel,
    DeploymentEventType,
)
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack


class TestDeploymentEventEnums:
    """Domaines fermés spec 06 — valeurs exactes des enums."""

    def test_event_type_domain_spec06(self):
        """Les 6 valeurs spec 06, exactement."""
        values = {member.value for member in DeploymentEventType}
        assert values == {
            "pulling",
            "deploying",
            "health_check",
            "success",
            "error",
            "rollback",
        }

    def test_level_domain_spec06(self):
        """Les 4 niveaux spec 06, exactement."""
        values = {member.value for member in DeploymentEventLevel}
        assert values == {"debug", "info", "warning", "error"}

    def test_enums_are_str_enums(self):
        """str-Enum : stockage des valeurs littérales en base."""
        assert DeploymentEventType.SUCCESS == "success"
        assert DeploymentEventLevel.WARNING == "warning"


class TestDeploymentEventDefaults:
    """Defaults déclarés sur les colonnes (appliqués au flush SQLAlchemy)."""

    def test_column_defaults_declared(self):
        """level défaut 'info' (spec 06), id uuid4, created_at utcnow."""
        cols = DeploymentEvent.__table__.c
        assert cols.level.default.arg == "info"
        assert callable(cols.id.default.arg)  # lambda: str(uuid4())
        # default created_at : callable produisant un datetime naïf UTC
        # (comparaison comportementale — SQLAlchemy wrappe la fonction
        # avec un paramètre de contexte).
        created_default = cols.created_at.default.arg
        assert callable(created_default)
        assert created_default(None).tzinfo is None  # type: ignore[call-arg]
        # Colonnes nullable laissées à None par construction.
        event = DeploymentEvent(
            deployment_id="00000000-0000-0000-0000-000000000001",
            event_type="deploying",
        )
        assert event.data is None
        assert event.message is None
        assert event.created_at is None or event.created_at.tzinfo is None

    def test_created_at_default_is_naive_utc(self):
        """Le default created_at produit un datetime naïf (décision 5)."""
        naive = DeploymentEvent.__table__.c.created_at.default.arg
        assert callable(naive)
        assert naive(None).tzinfo is None  # type: ignore[call-arg]

    def test_repr(self):
        event = DeploymentEvent(
            id="abc-123",
            deployment_id="dep-1",
            event_type="error",
            level="error",
        )
        rendered = repr(event)
        assert "DeploymentEvent" in rendered
        assert "dep-1" in rendered
        assert "error" in rendered


class TestDeploymentEventTableArgs:
    """Index nommés spec 06 (requêtes par déploiement + rétention)."""

    def test_table_args_indexes_named_spec06(self):
        index_names = {idx.name for idx in DeploymentEvent.__table__.indexes}
        assert "idx_deploy_events_deployment" in index_names
        assert "idx_deploy_events_created" in index_names

    def test_index_columns(self):
        by_name = {idx.name: idx for idx in DeploymentEvent.__table__.indexes}
        deployment_idx = by_name["idx_deploy_events_deployment"]
        created_idx = by_name["idx_deploy_events_created"]
        assert [col.name for col in deployment_idx.columns] == ["deployment_id"]
        assert [col.name for col in created_idx.columns] == ["created_at"]

    def test_column_types_and_lengths(self):
        """String(50)/String(10)/Text/JSON/DateTime — spec 06 + analyse."""
        cols = DeploymentEvent.__table__.c
        assert cols.event_type.type.length == 50
        assert cols.level.type.length == 10
        assert cols.data.nullable is True
        assert cols.message.nullable is True
        assert cols.deployment_id.nullable is False
        assert cols.created_at.nullable is False


class TestDeploymentEventForeignKeyCascade:
    """FK ``deployments.id`` ON DELETE CASCADE (PRAGMA SQLite)."""

    @pytest.mark.asyncio
    async def test_delete_deployment_cascades_events(self, db_session):
        """La suppression du déploiement emporte ses events (base = source
        de vérité — pas de cascade ORM)."""
        org = Organization(name="Cascade Org", slug="cascade-org")
        db_session.add(org)
        await db_session.flush()
        stack = Stack(
            name="cascade-stack",
            template={"image": "nginx"},
            variables={},
            organization_id=org.id,
            version="1.0.0",
        )
        host = Host(
            name="cascade-host",
            host="127.0.0.1",
            credentials={},
            organization_id=org.id,
        )
        db_session.add_all([stack, host])
        await db_session.flush()
        deployment = Deployment(
            stack_id=stack.id,
            host_id=host.id,
            organization_id=org.id,
            name="cascade-deployment",
            config={},
            variables={},
            status=DeploymentStatus.RUNNING,
        )
        db_session.add(deployment)
        await db_session.flush()

        db_session.add_all(
            [
                DeploymentEvent(
                    deployment_id=deployment.id,
                    event_type="deploying",
                    level="info",
                    message="[INFO] step 1",
                ),
                DeploymentEvent(
                    deployment_id=deployment.id,
                    event_type="success",
                    level="info",
                    message="[SUCCESS] done",
                ),
            ]
        )
        await db_session.commit()

        # PRAGMA foreign_keys=ON — la cascade SQL s'applique.
        await db_session.execute(text("PRAGMA foreign_keys=ON"))
        await db_session.delete(deployment)
        await db_session.commit()

        remaining = await db_session.execute(
            text("SELECT COUNT(*) FROM deployment_events")
        )
        assert remaining.scalar() == 0
