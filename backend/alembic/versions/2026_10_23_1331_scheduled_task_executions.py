"""scheduled_task_executions : historique des exécutions scheduler (STORY-161)

Migration additive créant la table ``scheduled_task_executions`` (spec 06
§ Entités d'automatisation — P2-1 partie traçabilité) : chaque exécution
d'une tâche planifiée — par cron, par événement ou manuelle — est
matérialisée avec son cycle de vie complet, consultable via les endpoints
paginés ``/schedules/executions`` (spec 17 § Exécutions / § Gestion des
tâches, écran Activité).

Colonnes (spec 06) :

- ``id`` ``String(36)`` PK (uuid4 applicatif) ;
- ``task_id`` ``String(36)`` NOT NULL — FK ``scheduled_tasks.id``
  ``ON DELETE CASCADE`` (la suppression d'une définition emporte son
  historique d'exécutions) ;
- ``status`` ``String(10)`` NOT NULL ``'queued'`` —
  ``queued``|``running``|``success``|``failed``|``skipped``
  (sémantique : ``queued → running → success|failed`` ; ``skipped`` =
  saut par verrou anti-chevauchement / annulation défensive ; au
  redémarrage du scheduler, les orphelins ``queued``/``running`` sont
  marqués ``failed`` avec la raison contractualisée
  ``interrompue — le scheduler a été redémarré pendant l'exécution``) ;
- ``triggered_by`` ``String(10)`` NOT NULL — ``cron``|``event``|``manual``
  (nomenclature spec 06 ; le contrat moteur utilise ``schedule``, traduit
  au point unique ``DatabaseExecutionStore.mark_queued``) ;
- ``started_at``/``finished_at`` ``DateTime`` nullable (UTC aware) ;
- ``duration_seconds`` ``Float`` nullable — calculée à la clôture en
  secondes fractionnaires (divergence mineure vs spec 06 ``INTEGER``,
  assumée : le moteur produit ``total_seconds()`` — reporté à STORY-252) ;
- ``error`` ``Text`` nullable — message assaini/tronqué (rules 40, jamais
  de stack brute) ;
- ``logs`` ``Text`` nullable — journal ligne à ligne sérialisé JSON
  ``[{"timestamp": "<ISO 8601 UTC>", "message": str}]`` (spec 06 :
  horodatages ISO 8601, stockage UTC) ;
- ``created_at`` ``DateTime`` NOT NULL.

Index (spec 06 — requêtes de rétention/historique) :
``idx_scheduled_exec_task`` (``task_id``), ``idx_scheduled_exec_status``
(``status``), ``idx_scheduled_exec_started`` (``started_at``).

Compatibilité SQLite + PostgreSQL (types portables ``sa.String`` /
``sa.Text`` / ``sa.DateTime`` / ``sa.Float`` — aucun JSON natif : les
journaux vivent en ``Text`` JSON, identiques sur les deux moteurs).

Downgrade : drop des index puis de la table (perte de l'historique —
irréversible, assumé : un downgrade retire volontairement la traçabilité
posée par cette migration).

Revision ID: 1331_scheduled_task_executions
Revises: 1321_scheduled_tasks_spec17
Create Date: 2026-10-23 12:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1331_scheduled_task_executions"
down_revision: Union[str, None] = "1321_scheduled_tasks_spec17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_task_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "task_id",
            sa.String(length=36),
            sa.ForeignKey("scheduled_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("triggered_by", sa.String(length=10), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_scheduled_exec_task", "scheduled_task_executions", ["task_id"])
    op.create_index(
        "idx_scheduled_exec_status", "scheduled_task_executions", ["status"]
    )
    op.create_index(
        "idx_scheduled_exec_started", "scheduled_task_executions", ["started_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_scheduled_exec_started", table_name="scheduled_task_executions")
    op.drop_index("idx_scheduled_exec_status", table_name="scheduled_task_executions")
    op.drop_index("idx_scheduled_exec_task", table_name="scheduled_task_executions")
    op.drop_table("scheduled_task_executions")
