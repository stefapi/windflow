"""Création de la table user_organizations (STORY-121.1)

Migration **strictement additive** : création de la table d'association
``user_organizations`` (PK composite ``(user_id, organization_id)``,
``role VARCHAR(20) NOT NULL DEFAULT 'viewer'``, ``joined_at``, index
``ix_user_organizations_organization_id``) conformément aux specs 06
(modèle de données) et 08 (RBAC & permissions).

Aucune donnée existante n'est lue ni modifiée : la colonne héritée
``users.organization_id`` reste **intacte** — la copie des données et la
bascule des lectures sont portées par STORY-121.3.

Revision ID: 1211_user_organizations
Revises: baseline
Create Date: 2026-09-08 21:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1211_user_organizations"
down_revision: Union[str, None] = "baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_organizations",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="viewer",
            comment="Rôle de l'utilisateur dans l'organisation "
            "(viewer | operator | admin)",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(),
            nullable=False,
            comment="Date d'adhésion de l'utilisateur à l'organisation",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "organization_id"),
    )
    with op.batch_alter_table("user_organizations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_user_organizations_organization_id"),
            ["organization_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("user_organizations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_organizations_organization_id"))

    op.drop_table("user_organizations")
