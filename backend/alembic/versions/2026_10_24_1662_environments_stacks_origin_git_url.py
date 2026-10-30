"""Environnements + axe origine stacks + git_url + rattachements (STORY-166.4)

Migration du volet « entités pilotées » de STORY-166 (P2-4) :

1. **table ``environments``** (item plan A14 — n'existait pas en base) :
   schéma canonique spec 06 (``id``, ``name``, ``type``, ``organization_id``
   FK CASCADE, ``configuration``, ``is_active``, timestamps,
   ``UNIQUE(organization_id, name)`` — contrainte ``uq_environment_org_name``) ;
2. **``stacks.origin``** (axe origine de la matrice « profil × origine »,
   spec 03/06) : ``VARCHAR(10) NOT NULL DEFAULT 'managed'`` + **backfill** :

   ==========================  ===========================
   Ligne préexistante          ``origin`` après migration
   ==========================  ===========================
   ``category = 'adopted'``    ``adopted``
   ``tags`` contient           ``adopted``
   ``"adopted"`` (JSON)
   autres (créations manuelles) ``managed`` (défaut)
   ==========================  ===========================

   La colonne réellement posée par l'adoption historique est bien
   ``stacks.category = 'adopted'`` (+ ``tags = ["adopted", ...]`` —
   [`adoption_service.adopt_discovered_item`]) : le backfill cible les
   deux signaux pour ne manquer aucune ligne.

3. **``stacks.git_url``** (item plan D2) : ``VARCHAR(500) NULL`` — URL du
   dépôt Git source persistée pour le GitOps futur. **Aucun clone ni
   exécution à ce stade** (validation URL côté schémas Pydantic, pas de
   fetch — pas de surface SSRF) ;
4. **``stacks.environment_id``** / **``hosts.environment_id``** :
   ``VARCHAR(36) NULL`` + FK ``environments.id`` ``ON DELETE SET NULL``
   (la suppression d'un environnement déréférence, l'entité rattachée
   est conservée) + index.

⚠️ **Arbitrage « host local » tracé** (Tâche 5 de la story) : l'adoption
pose ``origin='adopted'`` sur la **stack** uniquement — ``hosts.origin``
n'est **pas** modifié à l'adoption (l'axe origin décrit le *workload*,
pas le substrat ; le host local reste ``managed`` — il est piloté par
WindFlow).

⚠️ **Renvoi explicite STORY-160** : la surcharge timezone par Host est
**renvoyée** à STORY-160 (arbitrage « Décisions de découpe » de la
story) — **aucune colonne timezone ici**.

Downgrade : **réversible et documenté** — les colonnes sont nouvelles
(zéro donnée préexistante), seule la valeur backfillée ``origin`` est
perdable au retour arrière (les signaux ``category``/``tags`` restent
en base pour re-backfiller) ; la table ``environments`` est droppée
(les rattachements sont SET NULL par construction).

Défensive (pattern 1661/1311) : sur une base ``create_all`` avec les
modèles courants (simulations de tests), colonnes/table déjà présentes
→ no-op journalisé, jamais d'erreur « duplicate column ».

Revision ID: 1662_environments_stacks_origin_git_url
Revises: 1661_targets_to_hosts
Create Date: 2026-10-24 23:30:00.000000+00:00

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context as alembic_context
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "1662_environments_stacks_origin_git_url"
down_revision: Union[str, None] = "1661_targets_to_hosts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns(table: str) -> set[str]:
    """Colonnes existantes de ``table`` (inspection défensive)."""
    bind = op.get_bind()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _create_environments() -> None:
    """Étape 1 — table ``environments`` (schéma canonique spec 06)."""
    op.create_table(
        "environments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "type",
            sa.String(length=30),
            nullable=False,
            server_default="development",
            comment="Type d'environnement (dev, staging, prod — valeur libre à ce stade)",
        ),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column(
            "configuration",
            sa.JSON(),
            nullable=False,
            server_default="{}",
            comment="Paramètres réseau, variables partagées (JSON)",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_environment_org_name"),
    )
    with op.batch_alter_table("environments", schema=None) as batch_op:
        batch_op.create_index("ix_environments_name", ["name"], unique=False)
        batch_op.create_index(
            "ix_environments_organization_id", ["organization_id"], unique=False
        )


def _add_stacks_columns() -> None:
    """Étape 2 — ``stacks`` : origin + git_url + environment_id (FK)."""
    with op.batch_alter_table("stacks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "origin",
                sa.String(length=10),
                nullable=False,
                server_default="managed",
                comment="Origine du workload (managed, adopted, external)",
            )
        )
        batch_op.add_column(
            sa.Column(
                "git_url",
                sa.String(length=500),
                nullable=True,
                comment=(
                    "URL du dépôt Git source — GitOps futur "
                    "(pas de clone à ce stade)"
                ),
            )
        )
        batch_op.add_column(
            sa.Column(
                "environment_id",
                sa.String(length=36),
                nullable=True,
                comment="Environnement de rattachement (FK environments.id — SET NULL)",
            )
        )
        batch_op.create_foreign_key(
            "fk_stacks_environment_id",
            "environments",
            ["environment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_stacks_environment_id", ["environment_id"], unique=False
        )


def _add_hosts_environment() -> None:
    """Étape 3 — ``hosts`` : environment_id (FK SET NULL)."""
    with op.batch_alter_table("hosts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "environment_id",
                sa.String(length=36),
                nullable=True,
                comment="Environnement de rattachement (FK environments.id — SET NULL)",
            )
        )
        batch_op.create_foreign_key(
            "fk_hosts_environment_id",
            "environments",
            ["environment_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_hosts_environment_id", ["environment_id"], unique=False
        )


def _backfill_adopted_origin() -> None:
    """Étape 4 — backfill ``origin='adopted'`` (arbitrage story T3).

    Signaux réels laissés par l'adoption historique :
    ``category='adopted'`` et/ou ``tags`` JSON contenant ``"adopted"``.
    Idempotent (UPDATE pur, sans donnée sensible loggée).
    """
    result = op.get_bind().execute(
        sa.text(
            "UPDATE stacks SET origin = 'adopted' "
            "WHERE category = 'adopted' OR tags LIKE '%\"adopted\"%'"
        )
    )
    logger.info(
        "Migration 1662 backfill: %s stack(s) marquée(s) origin='adopted'",
        getattr(result, "rowcount", 0),
    )


def upgrade() -> None:
    if alembic_context.is_offline_mode():
        # Génération SQL hors ligne : DDL seul, aucune inspection de
        # données (pattern 1311/1661 — pas de bind réel inspectable).
        _create_environments()
        _add_stacks_columns()
        _add_hosts_environment()
        return

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    # Étape 1 : table environments (défensive — base create_all déjà
    # canonique : no-op journalisé).
    if "environments" not in tables:
        _create_environments()
    else:
        logger.info("Migration 1662 : table environments déjà présente — no-op")

    # Étapes 2-3 : colonnes additives (défensives, jamais « duplicate
    # column » sur une base create_all avec les modèles courants).
    stacks_columns = _existing_columns("stacks")
    missing_stacks = {
        "origin",
        "git_url",
        "environment_id",
    } - stacks_columns
    if missing_stacks == {"origin", "git_url", "environment_id"}:
        _add_stacks_columns()
    elif not missing_stacks:
        logger.info("Migration 1662 : colonnes stacks déjà présentes — no-op")
    else:
        raise RuntimeError(
            "Migration 1662 : état partiel incohérent de stacks "
            f"(colonnes manquantes : {sorted(missing_stacks)}) — restaurer "
            "le backup (procédure en docstring de la révision 1661)"
        )

    hosts_columns = _existing_columns("hosts")
    if "environment_id" not in hosts_columns:
        _add_hosts_environment()
    else:
        logger.info("Migration 1662 : colonne hosts.environment_id déjà présente")

    # Étape 4 : backfill (idempotent, exécuté dans tous les cas).
    _backfill_adopted_origin()


def downgrade() -> None:
    """Downgrade **réversible** : drop des colonnes nouvelles + table.

    Sans perte : les colonnes sont nouvelles (aucune donnée
    préexistante) ; seule la valeur backfillée ``origin='adopted'`` est
    perdue — les signaux d'origine (``category``/``tags``) restent en
    base, un re-upgrade re-backfille. Défensif : colonnes déjà absentes
    → no-op (round-trips tests).
    """
    stacks_columns = _existing_columns("stacks")
    with op.batch_alter_table("stacks", schema=None) as batch_op:
        if "environment_id" in stacks_columns:
            batch_op.drop_index("ix_stacks_environment_id")
            batch_op.drop_constraint("fk_stacks_environment_id", type_="foreignkey")
            batch_op.drop_column("environment_id")
        if "git_url" in stacks_columns:
            batch_op.drop_column("git_url")
        if "origin" in stacks_columns:
            batch_op.drop_column("origin")

    if "environment_id" in _existing_columns("hosts"):
        with op.batch_alter_table("hosts", schema=None) as batch_op:
            batch_op.drop_index("ix_hosts_environment_id")
            batch_op.drop_constraint("fk_hosts_environment_id", type_="foreignkey")
            batch_op.drop_column("environment_id")

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "environments" in tables:
        op.drop_table("environments")
