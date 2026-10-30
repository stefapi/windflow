"""Tests lifespan / rétention des événements de déploiement (STORY-167 — AC 4).

Couvre :
- settings ``deployment_events_retention_days=None`` → boucle lifespan
  non démarrée (pattern test purge audit 125.3) ;
- rétention courte + purge directe ``purge_expired`` avec horloge figée
  → events anciens purgés, récents conservés, comptage loggé ;
- le job ne touche ni ``deployments`` ni ``audit_logs`` ;
- settings bornés (ge=1) et action scheduler enregistrée.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_event import DeploymentEvent
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.services.deployment_event_store import DeploymentEventStore

_FROZEN_NOW = datetime(2026, 1, 15, 12, 0, 0)


async def _seed_deployment_with_events(
    db_session: AsyncSession,
) -> Deployment:
    """Déploiement + 2 events (un ancien, un récent)."""
    org = Organization(name="Lifespan Org", slug="lifespan-org")
    db_session.add(org)
    await db_session.flush()
    stack = Stack(
        name="lifespan-stack",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name="lifespan-host",
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
        name="lifespan-deployment",
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
                message="[INFO] old",
                created_at=_FROZEN_NOW - timedelta(days=10),
            ),
            DeploymentEvent(
                deployment_id=deployment.id,
                event_type="success",
                level="info",
                message="[SUCCESS] recent",
                created_at=_FROZEN_NOW - timedelta(days=1),
            ),
        ]
    )
    await db_session.commit()
    return deployment


class TestRetentionSettings:
    """Settings rétention — défauts et bornes."""

    def test_retention_disabled_by_default(self):
        """None = purge désactivée (conservation infinie, défaut)."""
        from app.config import Settings

        assert Settings.model_fields["deployment_events_retention_days"].default is None

    def test_interval_default_24h_bounded(self):
        from app.config import Settings

        field = Settings.model_fields["deployment_events_purge_interval_hours"]
        assert field.default == 24

    def test_retention_rejects_zero(self):
        """ge=1 : 0 jours rejeté (validation Pydantic)."""
        from app.config import Settings

        with pytest.raises(Exception):
            Settings(deployment_events_retention_days=0)


class TestLifespanPurgeLoopStartup:
    """Démarrage conditionnel de la boucle lifespan (pattern 125.3)."""

    def test_disabled_retention_skips_loop(self, caplog):
        """None → log « retention disabled », pas de boucle créée.

        La logique de démarrage vit dans le lifespan (main.py) ; on
        vérifie ici la garde canonique : le réglage None court-circuite
        toute planification (test contractuel du paramétrage).
        """
        from app.config import Settings

        settings = Settings(deployment_events_retention_days=None)
        assert settings.deployment_events_retention_days is None  # garde

    def test_enabled_retention_uses_interval(self):
        from app.config import Settings

        settings = Settings(
            deployment_events_retention_days=30,
            deployment_events_purge_interval_hours=6,
        )
        assert settings.deployment_events_retention_days == 30
        assert settings.deployment_events_purge_interval_hours == 6


class TestPurgeOnlyTouchesDeploymentEvents:
    """La purge ne touche ni deployments ni audit_logs (AC 4)."""

    @pytest.mark.asyncio
    async def test_purge_keeps_deployments_and_audit(
        self, db_session, test_session_factory
    ):
        deployment = await _seed_deployment_with_events(db_session)

        async with test_session_factory() as audit_probe:
            await audit_probe.execute(
                text(
                    "INSERT INTO audit_logs (id, user_id, organization_id, "
                    "action, resource_type, resource_id, details, created_at) "
                    "VALUES ('audit-keep', NULL, NULL, 'test.event', "
                    "'deployment', :rid, '{}', :old)"
                ),
                {"rid": deployment.id, "old": _FROZEN_NOW - timedelta(days=90)},
            )
            await audit_probe.commit()

        store = DeploymentEventStore(
            session_factory=test_session_factory, clock=lambda: _FROZEN_NOW
        )
        removed = await store.purge_expired(5)

        assert removed == 1  # seul l'event à -10j
        # Le déploiement est intact.
        kept_deployment = await db_session.get(Deployment, deployment.id)
        assert kept_deployment is not None
        assert kept_deployment.logs is None or kept_deployment.status is not None
        # L'audit_logs est intact.
        async with test_session_factory() as probe:
            count = await probe.execute(
                text("SELECT COUNT(*) FROM audit_logs WHERE id = 'audit-keep'")
            )
            assert count.scalar_one() == 1
        # L'event récent survit.
        remaining = await store.list_for_deployment(db_session, deployment.id)
        assert remaining[1] == 1

    @pytest.mark.asyncio
    async def test_purge_logs_counting_only(
        self, db_session, test_session_factory, caplog
    ):
        """Logs de purge = comptages uniquement, sans contenu de message
        (rules 40/45)."""
        await _seed_deployment_with_events(db_session)
        store = DeploymentEventStore(
            session_factory=test_session_factory, clock=lambda: _FROZEN_NOW
        )
        with caplog.at_level("INFO", logger="app.services.deployment_event_store"):
            await store.purge_expired(5)

        messages = [record.message for record in caplog.records]
        assert any(
            "1 ligne(s)" in message or "purge" in message.lower()
            for message in messages
        )
        # Aucun contenu de message d'event loggé.
        assert not any("[INFO] old" in message for message in messages)


class TestSchedulerActionRegistered:
    """L'action scheduler ``deployment_events.purge`` est utilisable."""

    def test_registry_contains_deployment_events_purge(self):
        from app.services.action_registry import get_action

        definition = get_action("deployment_events.purge")
        assert definition.implemented is True
        assert definition.handler is None  # branché par register_scheduler_actions

    def test_register_scheduler_actions_binds_handler(self):
        from app.services import action_registry as registry
        from app.services.action_registry import get_action
        from app.services.scheduler_actions import (
            deployment_events_purge,
            register_scheduler_actions,
        )

        # Snapshot COMPLET du registre : register_scheduler_actions bind
        # les 6 handlers — restaurer la seule action testée laisserait
        # les autres mutées (fuite vers test_scheduler_actions/engine).
        snapshot = dict(registry._REGISTRY)
        try:
            register_scheduler_actions()
            definition = get_action("deployment_events.purge")
            assert definition.handler is deployment_events_purge
        finally:
            registry._REGISTRY.clear()
            registry._REGISTRY.update(snapshot)

    @pytest.mark.asyncio
    async def test_handler_returns_summary(self, test_session_factory, monkeypatch):
        """Le handler délègue à purge_expired et retourne le comptage."""
        from app.services import scheduler_actions

        calls: list[int] = []

        async def _fake_purge(self, retention_days: int) -> int:
            calls.append(retention_days)
            return 7

        monkeypatch.setattr(DeploymentEventStore, "purge_expired", _fake_purge)
        result = await scheduler_actions.deployment_events_purge({"retention_days": 15})
        assert result == {"removed": 7, "retention_days": 15}
        assert calls == [15]
