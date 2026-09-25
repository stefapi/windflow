"""Création de la table api_keys (STORY-124.1)

Migration **strictement additive** : création de la table
``api_keys`` (spec 06 — modèle de données, spec 07 —
authentification) stockant le **hash** des clés API ``wf_ak_``
— jamais la valeur en clair (garantie structurelle : aucune colonne
n'existe pour la valeur brute).

Schéma :
- ``id VARCHAR(36)`` PK (convention maison UUID String(36)) ;
- ``user_id VARCHAR(36)`` FK ``users.id`` ``ON DELETE CASCADE``
  (la suppression d'un utilisateur purge ses clés API) ;
- ``name VARCHAR(100) NOT NULL`` (libellé choisi par l'utilisateur) ;
- ``key_hash VARCHAR(255) NOT NULL`` ;
- ``expires_at DATETIME NULL`` (NULL = n'expire jamais) ;
- ``last_used_at DATETIME NULL`` (alimenté de façon throttlée par
  la voie d'authentification par clé — STORY-124.2/124.3) ;
- ``revoked BOOLEAN NOT NULL DEFAULT FALSE`` (révocation
  administrative, distincte de l'expiration) ;
- ``created_at DATETIME NOT NULL`` ;
- index ``ix_api_keys_user_id`` (recherche par propriétaire — spec 06).

Aucune donnée existante n'est lue ni modifiée : l'émission des clés
API est portée par STORY-124.2/124.3.

Revision ID: 1241_api_keys
Revises: 1231_refresh_tokens
Create Date: 2026-09-13 22:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1241_api_keys"
down_revision: Union[str, None] = "1231_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=36),
            nullable=False,
            comment="Propriétaire de la clé (index requis spec 06)",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Libellé de la clé choisi par l'utilisateur",
        ),
        sa.Column(
            "key_hash",
            sa.String(length=255),
            nullable=False,
            comment="Hash de la clé wf_ak_ — jamais la valeur en clair",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=True,
            comment="Date d'expiration (NULL = n'expire jamais)",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(),
            nullable=True,
            comment="Dernière utilisation réussie (mise à jour throttlée)",
        ),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            comment="Révocation administrative (distincte de l'expiration)",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("api_keys", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_api_keys_user_id"), ["user_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("api_keys", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_api_keys_user_id"))

    op.drop_table("api_keys")
