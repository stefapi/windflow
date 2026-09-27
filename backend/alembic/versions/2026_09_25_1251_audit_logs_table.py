"""Création de la table audit_logs (STORY-125.1)

Migration **strictement additive** : création de la table
``audit_logs`` (spec 06 — modèle de données, spec 15 — sécurité §
Audit trail) posant le socle de données de l'audit trail — l'émission
sur les actions critiques est portée par STORY-125.2, l'endpoint de
consultation et la purge périodique par STORY-125.3.

Schéma (spec 06 + 3 ajouts STORY-125 : ``organization_id``,
``correlation_id``, index associés) :
- ``id VARCHAR(36)`` PK (convention maison UUID String(36)) ;
- ``user_id VARCHAR(36)`` FK ``users.id`` ``ON DELETE SET NULL``
  nullable — **conservation documentaire** : la trace survit à la
  suppression de son acteur (≠ CASCADE des tables 123/124) ;
- ``organization_id VARCHAR(36)`` FK ``organizations.id``
  ``ON DELETE SET NULL`` nullable (idem) ;
- ``action VARCHAR(50) NOT NULL`` (catalogue spec 15 :
  ``user.login``, ``stack.deleted``…) ;
- ``resource_type VARCHAR(30) NULL`` / ``resource_id TEXT NULL``
  (TEXT : IDs conteneurs Docker longs) ;
- ``details JSON NULL`` — **toujours sanitizé à l'écriture** par
  ``AuditService._sanitize_details`` (secrets masqués ``***``) ;
- ``ip_address VARCHAR(45) NULL`` (IPv6 max) ;
- ``correlation_id VARCHAR(64) NULL`` (middleware X-Correlation-ID —
  recherche d'incident par requête, rules 45) ;
- ``created_at DATETIME NOT NULL`` ;
- index : ``user_id``, ``organization_id``, ``action``,
  ``correlation_id``, ``created_at`` (spec 06 + story) + composite
  ``idx_audit_resource (resource_type, resource_id)`` (nommage spec 06).

Aucune donnée existante n'est lue ni modifiée.

Revision ID: 1251_audit_logs
Revises: 1241_api_keys
Create Date: 2026-09-25 21:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1251_audit_logs"
down_revision: Union[str, None] = "1241_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=True,
            comment="Acteur — NULL si anonymisé après suppression du compte "
            "(FK SET NULL : conservation documentaire, spec 06)",
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            nullable=True,
            comment="Organisation concernée par l'action (recherche par org)",
        ),
        sa.Column(
            "action",
            sa.String(length=50),
            nullable=False,
            comment="Action auditée — catalogue spec 15 "
            "(user.login, stack.deleted…)",
        ),
        sa.Column(
            "resource_type",
            sa.String(length=30),
            nullable=True,
            comment="Type de la cible (stack, container, user…)",
        ),
        sa.Column(
            "resource_id",
            sa.Text(),
            nullable=True,
            comment="Identifiant de la cible (Text : IDs conteneurs Docker longs)",
        ),
        sa.Column(
            "details",
            sa.JSON(),
            nullable=True,
            comment="Contexte JSON — TOUJOURS sanitizé par "
            "AuditService._sanitize_details avant persistance "
            "(secrets masqués)",
        ),
        sa.Column(
            "ip_address",
            sa.String(length=45),
            nullable=True,
            comment="IP source de l'action (IPv6 max 45 chars)",
        ),
        sa.Column(
            "correlation_id",
            sa.String(length=64),
            nullable=True,
            comment="Correlation ID du middleware (X-Correlation-ID — "
            "recherche d'incident par requête, rules 45)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            comment="Horodatage de l'action (index requis spec 06)",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_audit_logs_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_audit_logs_organization_id"),
            ["organization_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_audit_logs_action"), ["action"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_audit_logs_correlation_id"),
            ["correlation_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_audit_logs_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            "idx_audit_resource", ["resource_type", "resource_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_index("idx_audit_resource")
        batch_op.drop_index(batch_op.f("ix_audit_logs_created_at"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_correlation_id"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_action"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_organization_id"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_user_id"))

    op.drop_table("audit_logs")
