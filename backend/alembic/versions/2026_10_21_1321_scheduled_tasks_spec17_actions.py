"""scheduled_tasks spec 17 : action du registre, trigger cron|event, IANA, error_policy (STORY-160.1)

Migration d'évolution du volet définition de STORY-160 (P2-1, spec 17 §
Scheduler core) — remplace l'enum fermé ``task_type`` par une ``action``
du **registre canonique** (``app/services/action_registry.py``) et pose
le contrat du moteur (STORY-160.2) :

- ``action`` ``String(100)`` NOT NULL — clé du registre ;
- ``trigger_type`` ``String(20)`` NOT NULL ``'cron'`` (``cron``|``event``) ;
- ``event_name`` ``String(100)`` nullable (requis si ``event`` — validé API) ;
- ``timezone`` ``String(64)`` nullable — fuseau IANA, défaut résolu au
  runtime depuis les settings (arbitrage : ``Target`` n'a pas de colonne
  timezone, alignement STORY-166) ;
- ``error_policy`` ``String(20)`` NOT NULL ``'ignore'``
  (``ignore``|``retry``|``disable``).

**Mapping défensif des 5 ``task_type`` legacy** (``CLEANUP_LOGS`` /
``HEALTH_CHECK`` / ``GIT_SYNC`` / ``RETRY_DEPLOYMENTS`` / ``CUSTOM``) :
aucune valeur n'a d'équivalent évident et sûr dans le registre core
(sémantiques distinctes — cleanup_logs purge des logs applicatifs ≠
``compute.docker.prune`` ; health_check ≠ ``host.scan``…). Chaque ligne
legacy reçoit donc une **clé gelée** ``legacy.<task_type>`` hors registre
et est **désactivée** (``enabled=false``) avec journalisation — aucune
perte silencieuse, aucune exécution d'une action non validée. La table
n'est pas seedée (``database_seed.py`` ne la touche pas) : le mapping
est en pratique un no-op, vérifié en test d'intégration.

Downgrade inverse : recréation de ``task_type`` (enum legacy) avec
reverse-mapping ``legacy.*`` → enum d'origine, ``CUSTOM`` sinon ; les
définitions créées avec les actions du registre tombent en ``CUSTOM``
(repli documenté). L'état ``enabled`` n'est pas restauré (limite assumée :
la migration d'upgrade désactive pour cause de sécurité, le downgrade ne
réactive pas automatiquement).

Revision ID: 1321_scheduled_tasks_spec17
Revises: 1311_ssh_keys
Create Date: 2026-10-21 22:00:00.000000+00:00

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context as alembic_context
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "1321_scheduled_tasks_spec17"
down_revision: Union[str, None] = "1311_ssh_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Valeurs legacy stockées en base (SQLEnum persiste les NOMS des membres,
# cf. baseline : sa.Enum("CLEANUP_LOGS", ..., name="tasktype")).
_LEGACY_TASK_TYPES: frozenset[str] = frozenset(
    {
        "CLEANUP_LOGS",
        "HEALTH_CHECK",
        "GIT_SYNC",
        "RETRY_DEPLOYMENTS",
        "CUSTOM",
    }
)

_LEGACY_ENUM = sa.Enum(
    "CLEANUP_LOGS",
    "HEALTH_CHECK",
    "GIT_SYNC",
    "RETRY_DEPLOYMENTS",
    "CUSTOM",
    name="tasktype",
)


def _map_legacy_task_types(bind: sa.engine.Connection) -> None:
    """Mapping défensif des ``task_type`` legacy vers des clés gelées.

    Aucun équivalent registre évident (sémantiques distinctes) : chaque
    ligne reçoit ``legacy.<task_type_lower>`` et ``enabled=false``,
    journalisée — jamais de suppression muette ni d'exécution non
    validée (AC 3 : « sans perte silencieuse »).

    Args:
        bind: Connexion Alembic courante (mode online uniquement).
    """
    rows = bind.execute(
        sa.text("SELECT id, name, task_type FROM scheduled_tasks")
    ).fetchall()
    for row in rows:
        raw = row.task_type if isinstance(row.task_type, str) else str(row.task_type)
        key = raw.strip()
        action = f"legacy.{key.lower()}"
        bind.execute(
            sa.text(
                "UPDATE scheduled_tasks SET action = :action, enabled = :enabled "
                "WHERE id = :id"
            ),
            {"action": action, "enabled": False, "id": row.id},
        )
        # Journalisation sans donnée sensible (id/nom de tâche uniquement).
        logger.warning(
            "1321: tâche planifiée legacy %s (%s) sans action registre "
            "équivalente — action gelée %r, enabled=False",
            row.id,
            row.name,
            action,
        )
    if rows:
        logger.warning(
            "1321: %d tâche(s) legacy migrée(s) en action gelée legacy.* "
            "(désactivées, à requalifier via l'API /schedules)",
            len(rows),
        )


def _reverse_map_task_types(bind: sa.engine.Connection) -> None:
    """Reverse-mapping downgrade : ``legacy.*`` → enum legacy, CUSTOM sinon."""
    rows = bind.execute(sa.text("SELECT id, action FROM scheduled_tasks")).fetchall()
    for row in rows:
        action = row.action if isinstance(row.action, str) else ""
        task_type = "CUSTOM"
        if action.startswith("legacy."):
            candidate = action[len("legacy.") :].upper()
            if candidate in _LEGACY_TASK_TYPES:
                task_type = candidate
        bind.execute(
            sa.text("UPDATE scheduled_tasks SET task_type = :tt WHERE id = :id"),
            {"tt": task_type, "id": row.id},
        )


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Colonnes additives (batch — SQLite portable, pattern 1211) ──
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("action", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "trigger_type",
                sa.String(length=20),
                nullable=False,
                server_default="cron",
            )
        )
        batch_op.add_column(
            sa.Column("event_name", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "error_policy",
                sa.String(length=20),
                nullable=False,
                server_default="ignore",
            )
        )

    # ── 2. Mapping défensif des task_type legacy (online uniquement) ──
    if not alembic_context.is_offline_mode():
        _map_legacy_task_types(bind)

    # ── 3. action NOT NULL + retrait de task_type (rebuild unique) ──
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.alter_column(
            "action", existing_type=sa.String(length=100), nullable=False
        )
        batch_op.drop_column("task_type")

    # ── 4. PostgreSQL : drop du type ENUM tasktype orphelin ──
    if bind.dialect.name == "postgresql":
        _LEGACY_ENUM.drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()

    # ── 1. Recréer l'enum + la colonne task_type (nullable d'abord) ──
    if bind.dialect.name == "postgresql":
        _LEGACY_ENUM.create(bind, checkfirst=True)
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_type",
                _LEGACY_ENUM,
                nullable=True,
                server_default="CUSTOM",
            )
        )

    # ── 2. Reverse-mapping legacy.* → enum, CUSTOM sinon (online) ──
    if not alembic_context.is_offline_mode():
        _reverse_map_task_types(bind)

    # ── 3. task_type NOT NULL + retrait des colonnes spec 17 ──
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.alter_column("task_type", existing_type=_LEGACY_ENUM, nullable=False)
        batch_op.drop_column("action")
        batch_op.drop_column("trigger_type")
        batch_op.drop_column("event_name")
        batch_op.drop_column("timezone")
        batch_op.drop_column("error_policy")
