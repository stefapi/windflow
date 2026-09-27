"""Tests unitaires d'AuditService (STORY-125.1).

Vérifie :
- la persistance complète d'une ligne (``test_log_persists_full_line``) ;
- le masquage systématique : clés sensibles → ``***`` (paramétré),
  récursion sur dicts/lists, troncature > 512 chars (AC 5) ;
- le best-effort structurel : échec DB → aucune exception propagée,
  ``audit.write_failed`` loggé sans ``details`` (AC 4) ;
- l'ouverture d'une session courte quand ``db`` n'est pas fourni ;
- l'extraction du contexte requête par ``log_from_request`` (ip,
  correlation_id, acteur) ;
- la consultation ``list_entries`` : filtres combinés, ordre
  ``created_at desc``, pagination, total exact ;
- la purge : no-op quand ``audit_retention_days`` est None (aucune
  requête delete), seules les lignes au-delà du seuil sont purgées ;
- la sécurité des logs : jamais le contenu de ``details`` (caplog).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.audit_log import AuditLog
from app.services.audit_service import AuditService

SECRET_VALUE = "hunter2-super-secret"
LONG_VALUE = "x" * 600


def _make_log(**kwargs) -> AuditLog:
    """Construit une AuditLog datée pour les tests de liste/purge."""
    defaults: dict = {
        "action": "user.login",
    }
    defaults.update(kwargs)
    return AuditLog(**defaults)


class _FakeClient:
    """Simule request.client (host)."""

    host = "198.51.100.7"


def _fake_request() -> SimpleNamespace:
    """Requête factice : correlation_id posé sur state (middleware)."""
    request = SimpleNamespace()
    request.client = _FakeClient()
    request.state = SimpleNamespace(correlation_id="corr-abc-123")
    return request


class TestLogPersists:
    """test_log_persists_full_line."""

    async def test_log_persists_full_line(
        self, db_session, test_user, test_organization
    ) -> None:
        """Acteur, org, action, cible, ip, correlation_id et details
        (non sensibles) sont persistés tels quels."""
        await AuditService.log(
            "stack.deleted",
            user_id=test_user.id,
            organization_id=test_organization.id,
            resource_type="stack",
            resource_id="stk-42",
            details={"stack_name": "production-nginx"},
            ip_address="203.0.113.10",
            correlation_id="corr-xyz",
            db=db_session,
        )

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        assert entry.action == "stack.deleted"
        assert entry.user_id == test_user.id
        assert entry.organization_id == test_organization.id
        assert entry.resource_type == "stack"
        assert entry.resource_id == "stk-42"
        assert entry.details == {"stack_name": "production-nginx"}
        assert entry.ip_address == "203.0.113.10"
        assert entry.correlation_id == "corr-xyz"
        assert entry.created_at is not None

    async def test_log_minimal_line(self, db_session) -> None:
        """Ligne minimale : action seule (acteur système, sans cible)."""
        await AuditService.log("deployment.succeeded", db=db_session)

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        assert entry.action == "deployment.succeeded"
        assert entry.user_id is None
        assert entry.details is None


class TestSanitizeDetails:
    """test_log_sanitizes_sensitive_details + troncature."""

    @pytest.mark.parametrize(
        "sensitive_key",
        [
            "password",
            "user_token",
            "client_secret",
            "api_key",
            "credentials",
            "authorization_header",
            "session_cookie",
            "PASSWORD",
            "ApiKey",
        ],
    )
    async def test_log_sanitizes_sensitive_details(
        self, db_session, sensitive_key
    ) -> None:
        """Toute clé contenant un marqueur sensible (insensible à la
        casse) → valeur ``***`` ; clés non sensibles intactes."""
        details = {
            sensitive_key: SECRET_VALUE,
            "reason": "nominal",
        }
        await AuditService.log("user.login", details=details, db=db_session)

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        assert entry.details is not None
        assert entry.details[sensitive_key] == "***"
        assert entry.details["reason"] == "nominal"
        assert SECRET_VALUE not in str(entry.details)

    async def test_log_sanitizes_recursively(self, db_session) -> None:
        """Récursion : nested dicts et listes sont parcourus."""
        details = {
            "config": {
                "database_password": SECRET_VALUE,
                "host": "db.internal",
            },
            "items": [
                {"name": "ok", "token": SECRET_VALUE},
                {"plain": "kept"},
            ],
        }
        await AuditService.log("stack.deployed", details=details, db=db_session)

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        stored = entry.details
        assert stored is not None
        assert stored["config"]["database_password"] == "***"
        assert stored["config"]["host"] == "db.internal"
        assert stored["items"][0]["token"] == "***"
        assert stored["items"][0]["name"] == "ok"
        assert stored["items"][1]["plain"] == "kept"

    async def test_log_truncates_long_values(self, db_session) -> None:
        """Valeur string > 512 chars → tronquée à 512 (borne anti-abus)."""
        await AuditService.log(
            "user.login", details={"long_field": LONG_VALUE}, db=db_session
        )

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        assert entry.details is not None
        assert entry.details["long_field"] == "x" * 512

    def test_sanitize_details_does_not_mutate_input(self) -> None:
        """Copie défensive : le dict appelant n'est jamais modifié."""
        original = {"password": SECRET_VALUE, "keep": "value"}
        sanitized = AuditService._sanitize_details(original)

        assert original == {"password": SECRET_VALUE, "keep": "value"}
        assert sanitized is not original
        assert sanitized["password"] == "***"

    def test_sanitize_details_none(self) -> None:
        """details=None → None (pas de dict vide inventé)."""
        assert AuditService._sanitize_details(None) is None


class TestLogBestEffort:
    """test_log_never_raises_on_db_failure + session courte."""

    async def test_log_never_raises_on_db_failure(self, db_session, caplog) -> None:
        """Commit en échec → aucune exception propagée et
        ``audit.write_failed`` loggé (jamais le contenu de details)."""
        failing_session = AsyncMock(spec=db_session.__class__)
        failing_session.commit = AsyncMock(side_effect=RuntimeError("db down"))
        failing_session.rollback = AsyncMock()
        failing_session.add = MagicMock()

        with caplog.at_level(logging.ERROR, logger="app.services.audit_service"):
            # Ne doit pas lever malgré l'échec DB.
            await AuditService.log(
                "stack.deleted",
                resource_type="stack",
                details={"password": SECRET_VALUE},
                db=failing_session,
            )

        assert failing_session.commit.await_count == 1
        assert failing_session.rollback.await_count == 1
        assert any(
            "audit.write_failed" in record.message for record in caplog.records
        ), "L'échec d'écriture doit être loggé (audit.write_failed)"
        assert not any(
            SECRET_VALUE in record.message for record in caplog.records
        ), "Le contenu de details ne doit jamais apparaître dans les logs"
        assert not any("stack-42" in record.message for record in caplog.records)

    async def test_log_opens_own_session_when_db_none(self) -> None:
        """Appel sans ``db`` → session courte via AsyncSessionLocal."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        class _SessionCtx:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, *args):
                return False

        with patch(
            "app.services.audit_service.AsyncSessionLocal",
            return_value=_SessionCtx(),
        ) as factory:
            await AuditService.log("user.logout")

        factory.assert_called_once()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    async def test_log_own_session_failure_also_swallowed(self, caplog) -> None:
        """L'échec de la session courte est aussi avalé (best-effort)."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock(side_effect=RuntimeError("conn refused"))

        class _SessionCtx:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, *args):
                return False

        with patch(
            "app.services.audit_service.AsyncSessionLocal",
            return_value=_SessionCtx(),
        ):
            with caplog.at_level(logging.ERROR, logger="app.services.audit_service"):
                # Ne doit pas lever.
                await AuditService.log("user.login")

        assert any("audit.write_failed" in record.message for record in caplog.records)


class TestLogFromRequest:
    """test_log_from_request_extracts_context."""

    async def test_log_from_request_extracts_context(
        self, db_session, test_user
    ) -> None:
        """ip_address et correlation_id extraits de la requête factice ;
        user_id résolu depuis l'utilisateur courant."""
        request = _fake_request()
        await AuditService.log_from_request(
            request,
            "user.login",
            user=test_user,
            details={"username": test_user.username},
            db=db_session,
        )

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        assert entry.action == "user.login"
        assert entry.user_id == test_user.id
        assert entry.ip_address == "198.51.100.7"
        assert entry.correlation_id == "corr-abc-123"

    async def test_log_from_request_without_user_and_client(self, db_session) -> None:
        """Sans user ni client : acteur None, ip ``unknown``,
        correlation_id absent (state vierge)."""
        request = SimpleNamespace()
        request.client = None
        request.state = SimpleNamespace()

        await AuditService.log_from_request(request, "user.login_failed", db=db_session)

        entry = (await db_session.execute(select(AuditLog))).scalar_one()
        assert entry.user_id is None
        assert entry.ip_address == "unknown"
        assert entry.correlation_id is None


class TestListEntries:
    """test_list_entries_filters_and_pagination."""

    async def _seed(self, db_session, test_user, test_organization) -> None:
        """Trois lignes datées : ancienne / récente / très récente."""
        now = datetime.now(timezone.utc)
        rows = [
            AuditLog(
                user_id=test_user.id,
                organization_id=test_organization.id,
                action="stack.deleted",
                resource_type="stack",
                resource_id="stk-1",
                created_at=now - timedelta(days=2),
            ),
            AuditLog(
                user_id=test_user.id,
                action="user.login",
                created_at=now - timedelta(days=1),
            ),
            AuditLog(
                user_id=None,
                action="stack.deleted",
                resource_type="stack",
                resource_id="stk-2",
                created_at=now,
            ),
        ]
        db_session.add_all(rows)
        await db_session.flush()

    async def test_list_entries_filters_and_pagination(
        self, db_session, test_user, test_organization
    ) -> None:
        """Filtres user_id/action/resource_type/since combinés ; ordre
        ``created_at desc`` ; skip/limit respectés ; total exact."""
        await self._seed(db_session, test_user, test_organization)

        # Sans filtre : 3 lignes, ordre décroissant.
        rows, total = await AuditService.list_entries(db_session)
        assert total == 3
        assert [r.action for r in rows] == [
            "stack.deleted",
            "user.login",
            "stack.deleted",
        ]

        # Filtre action seul.
        rows, total = await AuditService.list_entries(
            db_session, action="stack.deleted"
        )
        assert total == 2
        assert all(r.action == "stack.deleted" for r in rows)

        # Filtres combinés user + action.
        rows, total = await AuditService.list_entries(
            db_session,
            user_id=test_user.id,
            action="stack.deleted",
        )
        assert total == 1
        assert rows[0].resource_id == "stk-1"

        # Filtre resource_type.
        _, total = await AuditService.list_entries(db_session, resource_type="stack")
        assert total == 2

        # Filtre since : seulement les dernières 24h (2 lignes).
        since = datetime.now(timezone.utc) - timedelta(hours=36)
        _, total = await AuditService.list_entries(db_session, since=since)
        assert total == 2

        # Pagination : page 1 élément.
        rows, total = await AuditService.list_entries(db_session, skip=0, limit=1)
        assert len(rows) == 1
        assert total == 3
        rows, total = await AuditService.list_entries(db_session, skip=2, limit=1)
        assert len(rows) == 1
        assert rows[0].action == "stack.deleted"
        assert rows[0].resource_id == "stk-1"

    async def test_list_entries_empty(self, db_session, test_user) -> None:
        """Base vide : liste vide, total 0."""
        rows, total = await AuditService.list_entries(db_session, user_id=test_user.id)
        assert rows == []
        assert total == 0


class TestPurgeExpired:
    """test_purge_expired_noop_when_retention_none +
    test_purge_expired_removes_only_old_entries."""

    async def test_purge_expired_noop_when_retention_none(
        self, db_session, test_user
    ) -> None:
        """audit_retention_days=None (défaut) → 0 suppression, aucune
        requête delete émise."""
        db_session.add(_make_log(user_id=test_user.id))
        await db_session.flush()

        original = settings.audit_retention_days
        settings.audit_retention_days = None
        try:
            with patch.object(db_session, "execute", wraps=db_session.execute) as spy:
                removed = await AuditService.purge_expired(db_session)
        finally:
            settings.audit_retention_days = original

        assert removed == 0
        delete_calls = [
            call
            for call in spy.call_args_list
            if "DELETE" in str(call).upper() or "delete" in str(call).lower()
        ]
        assert not delete_calls, "Aucune requête delete ne doit être émise"

        count = len((await db_session.execute(select(AuditLog))).scalars().all())
        assert count == 1, "La ligne ne doit pas être supprimée"

    async def test_purge_expired_removes_only_old_entries(
        self, db_session, test_user
    ) -> None:
        """Lignes au-delà du seuil purgées ; récentes conservées."""
        now = datetime.now(timezone.utc)
        db_session.add(
            _make_log(user_id=test_user.id, created_at=now - timedelta(days=10))
        )
        db_session.add(
            _make_log(user_id=test_user.id, created_at=now - timedelta(days=30))
        )
        db_session.add(
            _make_log(user_id=test_user.id, created_at=now - timedelta(hours=1))
        )
        await db_session.flush()

        original = settings.audit_retention_days
        settings.audit_retention_days = 7
        try:
            removed = await AuditService.purge_expired(db_session)
        finally:
            settings.audit_retention_days = original

        assert removed == 2
        remaining = (await db_session.execute(select(AuditLog))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].created_at is not None
        # La ligne restante est la récente (âgée d'1h).
        assert datetime.now(timezone.utc) - remaining[0].created_at.replace(
            tzinfo=timezone.utc
        ) < timedelta(hours=2)

    async def test_purge_applied_with_short_retention(
        self, db_session, test_user
    ) -> None:
        """STORY-125.3 AC 4 — « test avec valeur courte » : rétention
        ``AUDIT_RETENTION_DAYS=1`` → les lignes de plus d'1 jour sont
        purgées, celles de moins d'1 jour conservées (application
        configurable effectivement branchée, consommée par la boucle
        lifespan ``_periodic_audit_purge``)."""
        now = datetime.now(timezone.utc)
        db_session.add(
            _make_log(user_id=test_user.id, created_at=now - timedelta(days=3))
        )
        db_session.add(
            _make_log(user_id=test_user.id, created_at=now - timedelta(hours=2))
        )
        await db_session.flush()

        original = settings.audit_retention_days
        settings.audit_retention_days = 1
        try:
            removed = await AuditService.purge_expired(db_session)
        finally:
            settings.audit_retention_days = original

        assert removed == 1
        remaining = (await db_session.execute(select(AuditLog))).scalars().all()
        assert len(remaining) == 1
        assert datetime.now(timezone.utc) - remaining[0].created_at.replace(
            tzinfo=timezone.utc
        ) < timedelta(hours=3)


class TestNoSecretsInLogs:
    """test_no_details_in_logs — caplog sur l'ensemble des logs."""

    async def test_no_details_in_logs(self, db_session, test_user, caplog) -> None:
        """Jamais le contenu de details dans les logs du service — y
        compris en succès (event d'écriture sans valeurs)."""
        with caplog.at_level(
            logging.DEBUG,
            logger="app.services.audit_service",
        ):
            await AuditService.log(
                "api_key.created",
                user_id=test_user.id,
                details={"api_key": "wf_ak_supersecret", "name": "CI"},
                db=db_session,
            )

        assert not any(
            "wf_ak_supersecret" in record.message for record in caplog.records
        ), "Le secret ne doit jamais fuir dans les logs"
