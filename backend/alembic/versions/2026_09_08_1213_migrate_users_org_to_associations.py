"""Migration des données users.organization_id vers user_organizations (STORY-121.3)

Copie **sans perte** de chaque appartenance héritée (colonne
``users.organization_id``) vers la table d'association
``user_organizations`` (créée par ``1211_user_organizations``), puis retrait
de la colonne et de son index.

Mapping non cassant (plan de remédiation §7.1) :
- superuser → rôle ``admin`` (rôle max de l'association — le statut
  Super_Admin reste porté par le flag ``users.is_superuser``, **inchangé**) ;
- les autres utilisateurs → rôle ``operator``.

Aucune ligne n'est créée pour les utilisateurs sans organisation
(``organization_id`` NULL — pas de rattachement inventé). La PK composite
``(user_id, organization_id)`` garantit l'absence de doublon : un utilisateur
ne portait qu'une organisation unique.

Downgrade (best-effort) : la colonne ``organization_id`` est recréée
**nullable** (impossible de reconstituer l'organisation d'origine pour les
utilisateurs multi-appartenance créés après la migration), puis renseignée
avec la **première appartenance** par ``joined_at`` croissant. Les lignes
``user_organizations`` ne sont **pas** supprimées (limite documentée : le
downgrade est réversible en données héritées, pas en associations).

Aucune donnée individuelle n'est loggée (exigence sécurité STORY-121.3) —
l'intégrité de la copie est vérifiée par les tests d'intégration.

Revision ID: 1213_users_org_migration
Revises: 1211_user_organizations
Create Date: 2026-09-08 22:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1213_users_org_migration"
down_revision: Union[str, None] = "1211_user_organizations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Copie des données (SQL set-based portable SQLite/PostgreSQL).
    #    SQLite stocke les booléens en 0/1 → comparaison large IN (1, 'true')
    #    couvre les deux stockages ; CURRENT_TIMESTAMP évite un horodatage
    #    Python figé (même valeur pour joined_at/created_at/updated_at).
    #    Garde NOT EXISTS : la migration est rejouable sur des données déjà
    #    migrées sans dupliquer (le downgrade conserve les associations,
    #    un re-upgrade ne ré-insère pas les lignes existantes — la PK
    #    composite n'est jamais violée).
    op.execute(sa.text("""
            INSERT INTO user_organizations
                (user_id, organization_id, role, joined_at, created_at, updated_at)
            SELECT
                u.id,
                u.organization_id,
                CASE WHEN u.is_superuser IN (1, 'true', 't', 'True')
                     THEN 'admin' ELSE 'operator' END,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM users u
            WHERE u.organization_id IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1
                    FROM user_organizations uo
                    WHERE uo.user_id = u.id
                      AND uo.organization_id = u.organization_id
              )
            """))

    # 2. Retrait de la colonne héritée et de son index (rebuild de table
    #    SQLite via batch — pattern baseline)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_organization_id"))
        batch_op.drop_column("organization_id")


def downgrade() -> None:
    # 1. Recréer la colonne **nullable** (best-effort : l'organisation
    #    d'origine est reconstituée, pas choisie, pour les multi-appartenances)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("organization_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_users_organization_id"), ["organization_id"], unique=False
        )

    # 2. Backfill best-effort : première appartenance par joined_at
    #    (les lignes user_organizations sont conservées — voir docstring)
    op.execute(sa.text("""
            UPDATE users
            SET organization_id = (
                SELECT uo.organization_id
                FROM user_organizations uo
                WHERE uo.user_id = users.id
                ORDER BY uo.joined_at
                LIMIT 1
            )
            """))
