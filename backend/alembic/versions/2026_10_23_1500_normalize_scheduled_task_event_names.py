"""Normalize scheduled_tasks.event_name : alias legacy -> canonique (STORY-162)

Data migration **data-only** (P2-2 partie bus - nomenclature canonique
spec 11) : les ``event_name`` stockés sous une valeur alias historique
sont traduits vers leur forme canonique, miroir exact de
``LEGACY_EVENT_ALIASES`` (``backend/app/core/events.py``).

Sans cette migration, les triggers événement du scheduler seraient muets
après le renommage de la nomenclature : le match DB
``ScheduledTask.event_name == event.event_type.value`` comparerait des
alias (ex. ``deployment.completed``) à des valeurs canoniques (ex.
``deployment.succeeded``) sans jamais correspondre.

Mapping appliqué (couvre **tous** les alias, y compris les valeurs
jamais émises - robustesse) :

===========================  =========================
Alias legacy                 Canonique spec 11
===========================  =========================
deployment.completed         deployment.succeeded
target.created               host.added
target.updated               host.offline
target.deleted               host.removed
target.health_check          host.offline
stack.deleted                stack.removed
plugin.uninstalled           plugin.removed
===========================  =========================

Note ``target.updated`` : membre **supprimé** du référentiel (jamais
émis, aucun équivalent ``host.*`` - décision d'analyse STORY-162) ; les
lignes éventuelles sont traduites vers ``host.offline`` (valeur la plus
proche sémantiquement) plutôt que laissées orphelines - la clé d'alias
reste dans ``LEGACY_EVENT_ALIASES`` pour cette traduction déterministe.

Downgrade : **non réversible** de façon fiable (plusieurs alias mappent
vers ``host.offline`` - information de provenance perdue) ; le downgrade
est un no-op documenté (les valeurs canoniques restent valides pour
toutes les versions >= cette révision).

Compatible SQLite + PostgreSQL (UPDATE par alias, aucune construction
spécifique au moteur).

Revision ID: 1341_normalize_event_names
Revises: 1331_scheduled_task_executions
Create Date: 2026-10-23 15:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1341_normalize_event_names"
down_revision: Union[str, None] = "1331_scheduled_task_executions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Miroir exact de LEGACY_EVENT_ALIASES (backend/app/core/events.py) -
# redéfini localement : une migration ne doit pas importer le code
# applicatif courant (la constante évoluera après cette révision).
_EVENT_NAME_ALIASES: dict[str, str] = {
    "deployment.completed": "deployment.succeeded",
    "target.created": "host.added",
    "target.updated": "host.offline",
    "target.deleted": "host.removed",
    "target.health_check": "host.offline",
    "stack.deleted": "stack.removed",
    "plugin.uninstalled": "plugin.removed",
}


def upgrade() -> None:
    """Traduit chaque alias legacy stocké vers sa forme canonique."""
    table = sa.table("scheduled_tasks", sa.column("event_name", sa.String))
    for legacy, canonical in _EVENT_NAME_ALIASES.items():
        op.execute(
            table.update()
            .where(table.c.event_name == legacy)
            .values(event_name=canonical)
        )


def downgrade() -> None:
    """No-op documenté (non réversible - voir docstring du module)."""
