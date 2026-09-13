"""Création de la table refresh_tokens (STORY-123.1)

Migration **strictement additive** : création de la table
``refresh_tokens`` (spec 06 — modèle de données, spec 07 —
authentification) stockant le **hash** des refresh tokens opaques
— jamais la valeur en clair (garantie structurelle : aucune colonne
n'existe pour la valeur brute).

Schéma :
- ``id VARCHAR(36)`` PK (convention maison UUID String(36)) ;
- ``user_id VARCHAR(36)`` FK ``users.id`` ``ON DELETE CASCADE``
  (la suppression d'un utilisateur purge ses refresh tokens) ;
- ``token_hash VARCHAR(255) NOT NULL`` ;
- ``expires_at DATETIME NOT NULL`` (durée configurable
  ``REFRESH_TOKEN_EXPIRE_DAYS``, 7 jours par défaut) ;
- ``revoked_at DATETIME NULL`` (NULL = token actif — permet de
  distinguer un token inconnu d'un token consommé réutilisé et de
  tracer les révocations) ;
- ``created_at`` / ``updated_at DATETIME NOT NULL`` ;
- index ``ix_refresh_tokens_user_id`` et ``ix_refresh_tokens_expires_at``
  (recherche par utilisateur et purge des entrées expirées — spec 06).

Aucune donnée existante n'est lue ni modifiée : l'émission des tokens
opaques est portée par STORY-123.2/123.3.

Revision ID: 1231_refresh_tokens
Revises: 1213_users_org_migration
Create Date: 2026-09-12 22:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1231_refresh_tokens"
down_revision: Union[str, None] = "1213_users_org_migration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=False,
            comment="Propriétaire du token (index requis spec 06)",
        ),
        sa.Column(
            "token_hash",
            sa.String(length=255),
            nullable=False,
            comment="Hash du token opaque — jamais la valeur en clair",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=False,
            comment="Date d'expiration (index requis spec 06 — purge)",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(),
            nullable=True,
            comment="Date de révocation (NULL = token actif)",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_refresh_tokens_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_refresh_tokens_expires_at"),
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_expires_at"))
        batch_op.drop_index(batch_op.f("ix_refresh_tokens_user_id"))

    op.drop_table("refresh_tokens")
