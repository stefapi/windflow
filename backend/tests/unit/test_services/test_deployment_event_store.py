"""Tests unitaires du store DeploymentEventStore (STORY-167 — Tâche 3).

Couvre : ``append_event`` (validation domaines fermés + sanitisation
``data``), ``list_for_deployment`` (filtres combinés, pagination, tri
``created_at ASC, id ASC``, isolation stricte, COUNT aux mêmes filtres)
et ``purge_expired`` (horloge figée injectable — time travel AC 4).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_event import DeploymentEvent
from app.models.host import Host
from app.models.organization import Organization
from app.models.stack import Stack
from app.services.deployment_event_store import DeploymentEventStore

# Horloge figée : les horodatages sont déterministes (time travel AC 4).
_FROZEN_NOW = datetime(2026, 1, 15, 12, 0, 0)


async def _seed_deployment(
    db_session: AsyncSession, *, name: str, slug: str
) -> Deployment:
    """Insère un déploiement minimal (sans lancer de pipeline)."""
    org = Organization(name=f"Org {name}", slug=f"org-{slug}")
    db_session.add(org)
    await db_session.flush()
    stack = Stack(
        name=f"stack-{slug}",
        template={"image": "nginx"},
        variables={},
        organization_id=org.id,
        version="1.0.0",
    )
    host = Host(
        name=f"host-{slug}",
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
        name=f"deployment-{slug}",
        config={},
        variables={},
        status=DeploymentStatus.RUNNING,
    )
    db_session.add(deployment)
    await db_session.commit()
    await db_session.refresh(deployment)
    return deployment


class TestAppendEvent:
    """Écriture : insertion + validation + sanitisation."""

    @pytest.mark.asyncio
    async def test_append_event_inserts_row_with_fields(self, db_session):
        deployment = await _seed_deployment(db_session, name="A", slug="a")
        store = DeploymentEventStore(clock=lambda: _FROZEN_NOW)

        event = await store.append_event(
            db_session,
            deployment_id=deployment.id,
            event_type="deploying",
            level="info",
            message="[INFO] step",
            data={"old_status": "pending", "new_status": "deploying"},
        )
        await db_session.commit()

        stored = await db_session.get(DeploymentEvent, event.id)
        assert stored is not None
        assert stored.deployment_id == deployment.id
        assert stored.event_type == "deploying"
        assert stored.level == "info"
        assert stored.message == "[INFO] step"
        assert stored.data == {"old_status": "pending", "new_status": "deploying"}
        assert stored.created_at == _FROZEN_NOW

    @pytest.mark.asyncio
    async def test_append_event_sanitizes_data_whitelist(self, db_session):
        """Clés hors liste blanche exclues (rules 40 — jamais de secret)."""
        deployment = await _seed_deployment(db_session, name="B", slug="b")
        store = DeploymentEventStore()

        event = await store.append_event(
            db_session,
            deployment_id=deployment.id,
            event_type="error",
            level="error",
            data={
                "old_status": "deploying",
                "variables": {"DB_PASSWORD": "h4x0r"},
                "configuration": {"secret": "leak"},
                "token": "wf_tok",
            },
        )
        await db_session.commit()

        stored = await db_session.get(DeploymentEvent, event.id)
        assert stored is not None
        assert stored.data == {"old_status": "deploying"}

    @pytest.mark.asyncio
    async def test_append_event_rejects_invalid_event_type(self, db_session):
        deployment = await _seed_deployment(db_session, name="C", slug="c")
        store = DeploymentEventStore()
        with pytest.raises(ValueError, match="event_type"):
            await store.append_event(
                db_session,
                deployment_id=deployment.id,
                event_type="stopped",
                level="info",
            )

    @pytest.mark.asyncio
    async def test_append_event_rejects_invalid_level(self, db_session):
        deployment = await _seed_deployment(db_session, name="D", slug="d")
        store = DeploymentEventStore()
        with pytest.raises(ValueError, match="level"):
            await store.append_event(
                db_session,
                deployment_id=deployment.id,
                event_type="deploying",
                level="critical",
            )


class TestListForDeployment:
    """Lecture : filtres, tri ASC, pagination, isolation, COUNT."""

    @pytest.fixture(autouse=True)
    async def _seeded_events(self, db_session):
        """Deux déploiements : le premier porte 5 events datés, le second 1."""
        self.deployment = await _seed_deployment(db_session, name="L", slug="list")
        self.other = await _seed_deployment(db_session, name="O", slug="other")

        base = datetime(2026, 1, 10, 10, 0, 0)
        events = [
            DeploymentEvent(
                deployment_id=self.deployment.id,
                event_type="deploying",
                level="info",
                message=f"[INFO] step {i}",
                data={"step": i},
                created_at=base + timedelta(minutes=i),
            )
            for i in range(4)
        ]
        events.append(
            DeploymentEvent(
                deployment_id=self.deployment.id,
                event_type="error",
                level="error",
                message="[ERROR] boom",
                data={"step": 4},
                created_at=base + timedelta(minutes=4),
            )
        )
        # Event d'un autre déploiement : ne doit JAMAIS apparaître.
        events.append(
            DeploymentEvent(
                deployment_id=self.other.id,
                event_type="success",
                level="info",
                message="[SUCCESS] intruder",
                created_at=base,
            )
        )
        db_session.add_all(events)
        await db_session.commit()
        self.base = base
        yield

    @pytest.mark.asyncio
    async def test_list_returns_all_events_ordered_asc(self, db_session):
        items, total = await DeploymentEventStore().list_for_deployment(
            db_session, self.deployment.id
        )
        assert total == 5
        assert [item.message for item in items] == [
            "[INFO] step 0",
            "[INFO] step 1",
            "[INFO] step 2",
            "[INFO] step 3",
            "[ERROR] boom",
        ]
        created = [item.created_at for item in items]
        assert created == sorted(created)

    @pytest.mark.asyncio
    async def test_filter_event_type_and_level_combined(self, db_session):
        items, total = await DeploymentEventStore().list_for_deployment(
            db_session,
            self.deployment.id,
            event_type="error",
            level="error",
        )
        assert total == 1
        assert items[0].message == "[ERROR] boom"

    @pytest.mark.asyncio
    async def test_filter_after_before_bounds_inclusive(self, db_session):
        after = self.base + timedelta(minutes=1)
        before = self.base + timedelta(minutes=3)
        items, total = await DeploymentEventStore().list_for_deployment(
            db_session, self.deployment.id, after=after, before=before
        )
        # Bornes inclusives : steps 1, 2, 3.
        assert total == 3
        assert [item.data["step"] for item in items] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_pagination_page2_and_beyond(self, db_session):
        store = DeploymentEventStore()
        # Page 2 avec per_page=2 : events 3-4.
        items, total = await store.list_for_deployment(
            db_session, self.deployment.id, page=2, per_page=2
        )
        assert total == 5  # COUNT au même scoping (pas d'oracle)
        assert [item.data["step"] for item in items] == [2, 3]

        # Page au-delà de la dernière : [] + total exact.
        items, total = await store.list_for_deployment(
            db_session, self.deployment.id, page=10, per_page=2
        )
        assert items == []
        assert total == 5

    @pytest.mark.asyncio
    async def test_isolation_other_deployment_events_never_leak(self, db_session):
        """Les events d'un autre déploiement n'apparaissent jamais."""
        items, total = await DeploymentEventStore().list_for_deployment(
            db_session, self.deployment.id, event_type="success"
        )
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_count_matches_filters_not_global(self, db_session):
        """Le COUNT porte les mêmes filtres que la liste (pas d'oracle)."""
        items, total = await DeploymentEventStore().list_for_deployment(
            db_session, self.deployment.id, event_type="deploying"
        )
        assert total == 4
        assert len(items) == 4
        assert all(item.event_type == "deploying" for item in items)


class TestPurgeExpired:
    """Rétention : cutoff created_at, horloge injectable (AC 4)."""

    @pytest.mark.asyncio
    async def test_purge_removes_old_keeps_recent_returns_count(
        self, db_session, test_session_factory
    ):
        deployment = await _seed_deployment(db_session, name="P", slug="purge")
        old_event = DeploymentEvent(
            deployment_id=deployment.id,
            event_type="deploying",
            level="info",
            message="[INFO] old",
            created_at=_FROZEN_NOW - timedelta(days=10),
        )
        recent_event = DeploymentEvent(
            deployment_id=deployment.id,
            event_type="success",
            level="info",
            message="[SUCCESS] recent",
            created_at=_FROZEN_NOW - timedelta(days=2),
        )
        db_session.add_all([old_event, recent_event])
        await db_session.commit()

        # IDs capturés avant toute expiration (lazy-load async interdit
        # sur attribut expiré).
        old_event_id = old_event.id
        recent_event_id = recent_event.id

        # Rétention 5 jours, horloge figée : seul l'event à -10j est purge.
        store = DeploymentEventStore(
            session_factory=test_session_factory, clock=lambda: _FROZEN_NOW
        )
        removed = await store.purge_expired(5)

        assert removed == 1
        # La purge passe par une session dédiée : invalider l'identity
        # map de db_session avant relecture.
        db_session.expire_all()
        remaining = await db_session.get(DeploymentEvent, old_event_id)
        assert remaining is None
        kept = await db_session.get(DeploymentEvent, recent_event_id)
        assert kept is not None

    @pytest.mark.asyncio
    async def test_purge_noop_under_threshold(self, test_session_factory):
        """Tous les events plus récents que la rétention → no-op 0."""
        store = DeploymentEventStore(
            session_factory=test_session_factory, clock=lambda: _FROZEN_NOW
        )
        removed = await store.purge_expired(365)
        assert removed == 0

    @pytest.mark.asyncio
    async def test_purge_idempotent_second_run_noop(
        self, db_session, test_session_factory
    ):
        """Deuxième passe (exécution simultanée lifespan+cron) : no-op."""
        deployment = await _seed_deployment(db_session, name="I", slug="idem")
        db_session.add(
            DeploymentEvent(
                deployment_id=deployment.id,
                event_type="deploying",
                level="info",
                message="[INFO] old",
                created_at=_FROZEN_NOW - timedelta(days=30),
            )
        )
        await db_session.commit()

        store = DeploymentEventStore(
            session_factory=test_session_factory, clock=lambda: _FROZEN_NOW
        )
        assert await store.purge_expired(7) == 1
        assert await store.purge_expired(7) == 0
