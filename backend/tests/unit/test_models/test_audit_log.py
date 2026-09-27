"""Tests unitaires du modèle AuditLog (STORY-125.1).

Vérifie :
- les défauts du modèle : ``id`` UUID String(36), ``created_at`` non
  nul, toutes les colonnes de contexte nullable ;
- le bornage ``action`` ``String(50)`` (spec 06) ;
- le **SET NULL** (inverse volontaire du test CASCADE 123/124) :
  suppression de l'acteur → ligne **conservée** avec ``user_id=None``
  (conservation documentaire spec 06) ; idem côté organisation ;
- la sécurité : ``__repr__`` n'expose jamais ``details`` ni
  ``ip_address``.
"""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.user import User


def _make_log(**kwargs) -> AuditLog:
    """Construit une AuditLog valide (champs de contexte par défaut)."""
    defaults: dict = {
        "action": "user.login",
        "resource_type": "stack",
        "resource_id": "stk-1",
    }
    defaults.update(kwargs)
    return AuditLog(**defaults)


def select_user_with_audit_logs(user_id: str):
    """Select User avec la relation audit_logs chargée (async-safe)."""
    return select(User).options(selectinload(User.audit_logs)).where(User.id == user_id)


class TestAuditLogDefaults:
    """Cas nominaux : défauts et timestamps."""

    async def test_create_audit_log_defaults(
        self, db_session, test_user, test_organization
    ) -> None:
        """Ligne complète : id UUID, created_at défini, valeurs fidèles."""
        log = AuditLog(
            user_id=test_user.id,
            organization_id=test_organization.id,
            action="stack.deleted",
            resource_type="stack",
            resource_id="stk-1",
            details={"reason": "cleanup"},
            ip_address="203.0.113.10",
            correlation_id="corr-1234",
        )
        db_session.add(log)
        await db_session.flush()

        assert log.id is not None
        assert len(log.id) == 36, "id doit être un UUID String(36)"
        assert log.created_at is not None
        assert log.user_id == test_user.id
        assert log.organization_id == test_organization.id
        assert log.action == "stack.deleted"
        assert log.details == {"reason": "cleanup"}
        assert log.ip_address == "203.0.113.10"
        assert log.correlation_id == "corr-1234"

    async def test_context_columns_all_nullable(self, db_session) -> None:
        """Ligne minimale : toutes les colonnes de contexte sont nullable
        (acteur système, action hors ressource)."""
        minimal = AuditLog(action="user.logout")
        db_session.add(minimal)
        await db_session.flush()

        assert minimal.user_id is None
        assert minimal.organization_id is None
        assert minimal.resource_type is None
        assert minimal.resource_id is None
        assert minimal.details is None
        assert minimal.ip_address is None
        assert minimal.correlation_id is None


class TestColumnBounds:
    """Bornes structurelles spec 06 + story."""

    def test_action_max_length(self) -> None:
        """La colonne action est bornée à String(50), NOT NULL."""
        column = AuditLog.__table__.columns["action"]
        assert column.type.length == 50
        assert not column.nullable

    def test_column_lengths(self) -> None:
        """Longueurs spec 06 + story : user/org 36, resource_type 30,
        ip_address 45 (IPv6), correlation_id 64."""
        columns = AuditLog.__table__.columns
        assert columns["user_id"].type.length == 36
        assert columns["organization_id"].type.length == 36
        assert columns["resource_type"].type.length == 30
        assert columns["ip_address"].type.length == 45
        assert columns["correlation_id"].type.length == 64

    def test_fk_ondelete_is_set_null(self) -> None:
        """Sécurité (conservation documentaire) : les deux FK sont
        ``ON DELETE SET NULL`` — la trace survit à la suppression de
        son acteur et de son organisation (≠ CASCADE 123/124)."""
        user_fk = list(AuditLog.__table__.columns["user_id"].foreign_keys)[0]
        org_fk = list(AuditLog.__table__.columns["organization_id"].foreign_keys)[0]
        assert user_fk.ondelete == "SET NULL"
        assert org_fk.ondelete == "SET NULL"

    async def test_action_50_chars_accepted(self, db_session, test_user) -> None:
        """Une action de 50 caractères (borne max) est acceptée."""
        log = _make_log(user_id=test_user.id, action="a" * 50)
        db_session.add(log)
        await db_session.flush()

        stored = (
            await db_session.execute(
                text("SELECT LENGTH(action) FROM audit_logs WHERE id = :lid"),
                {"lid": log.id},
            )
        ).scalar_one()
        assert stored == 50


class TestFkSetNull:
    """SET NULL : suppression de l'acteur/org → ligne conservée,
    FK nullifiée (inverse volontaire du CASCADE 123/124)."""

    async def test_user_deletion_sets_null_not_cascade(
        self, db_session, test_user, test_organization
    ) -> None:
        """Suppression ORM de l'acteur (lignes chargées → NULLification
        de ``user_id``) → ligne d'audit **conservée** avec user_id=None."""
        db_session.add(
            _make_log(user_id=test_user.id, organization_id=test_organization.id)
        )
        await db_session.flush()

        # Recharge l'acteur avec sa relation audit_logs chargée : sans
        # cascade, l'ORM nullifie user_id des lignes chargées au delete.
        user = (
            await db_session.execute(select_user_with_audit_logs(test_user.id))
        ).scalar_one()
        assert len(user.audit_logs) == 1

        await db_session.delete(user)
        await db_session.flush()

        row = (
            await db_session.execute(text("SELECT user_id, action FROM audit_logs"))
        ).fetchone()
        assert row is not None, "La ligne d'audit doit être conservée (SET NULL)"
        assert row[0] is None, "user_id doit être nullifié, pas la ligne supprimée"
        assert row[1] == "user.login"

    async def test_user_sql_deletion_sets_null(self, db_session, test_user) -> None:
        """Suppressions SQL directes : le ``ON DELETE SET NULL`` couvre
        le DELETE hors ORM (FK SQLite activées pour le test)."""
        # PRAGMA hors transaction DML → s'applique à la connexion.
        await db_session.execute(text("PRAGMA foreign_keys=ON"))
        db_session.add(_make_log(user_id=test_user.id))
        await db_session.flush()

        await db_session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": test_user.id}
        )

        row = (
            await db_session.execute(text("SELECT user_id FROM audit_logs"))
        ).fetchone()
        assert row is not None
        assert row[0] is None

    async def test_organization_deletion_sets_null(
        self, db_session, test_user, test_organization
    ) -> None:
        """Suppression SQL de l'organisation → ligne conservée avec
        organization_id=None (aucune relation ORM côté Organization —
        le SET NULL est purement base de données)."""
        await db_session.execute(text("PRAGMA foreign_keys=ON"))
        db_session.add(
            _make_log(user_id=test_user.id, organization_id=test_organization.id)
        )
        await db_session.flush()

        await db_session.execute(
            text("DELETE FROM organizations WHERE id = :oid"),
            {"oid": test_organization.id},
        )

        row = (
            await db_session.execute(
                text("SELECT user_id, organization_id FROM audit_logs")
            )
        ).fetchone()
        assert row is not None, "La ligne d'audit doit être conservée"
        assert row[1] is None, "organization_id doit être nullifié"


class TestReprSecurity:
    """Sécurité : __repr__ sans exposition de details ni ip_address."""

    def test_repr_does_not_expose_details(self) -> None:
        """__repr__ ne contient jamais la valeur de details ni le nom de
        colonne, ni l'ip_address."""
        log = AuditLog(
            id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            action="user.login",
            resource_type="stack",
            resource_id="stk-1",
            details={"password": "hunter2-secret"},
            ip_address="203.0.113.10",
        )
        representation = repr(log)

        assert "hunter2-secret" not in representation
        assert "details" not in representation
        assert "ip_address" not in representation
        assert "203.0.113.10" not in representation
        assert "action=user.login" in representation
        assert "resource_type=stack" in representation

    def test_tablename(self) -> None:
        """__tablename__ == 'audit_logs' (convention spec 06)."""
        assert AuditLog.__tablename__ == "audit_logs"

    def test_user_relation_has_no_cascade(self) -> None:
        """La relation user ne porte aucune cascade (la trace survit à
        la suppression de l'acteur — conservation documentaire)."""
        relationship = AuditLog.__mapper__.relationships["user"]
        assert "all" not in (relationship.cascade or ())
        assert "delete" not in (relationship.cascade or ())
        assert relationship.passive_deletes is True
