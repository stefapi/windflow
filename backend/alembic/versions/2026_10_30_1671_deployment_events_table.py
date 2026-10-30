"""deployment_events : table dédiée des événements de déploiement (STORY-167)

Migration additive du plan P2-7 (axe A15) :

1. **DDL (spec 06 § DeploymentEvent)** : création de ``deployment_events``
   — ``id`` ``String(36)`` PK (uuid4 applicatif), ``deployment_id``
   ``String(36)`` NOT NULL FK ``deployments.id`` ``ON DELETE CASCADE`` (la
   suppression d'un déploiement emporte ses événements), ``event_type``
   ``String(50)`` NOT NULL (``pulling|deploying|health_check|success|
   error|rollback``), ``level`` ``String(10)`` NOT NULL DEFAULT ``'info'``
   (``debug|info|warning|error``), ``message`` ``Text`` nullable, ``data``
   ``JSON`` nullable (divergence mineure vs spec 06 ``TEXT DEFAULT '{}'``
   : le type ``sa.JSON`` est le pattern des colonnes ``config``/
   ``variables`` de ``deployments`` — même stockage TEXT sous SQLite,
   sérialisation pilotée par SQLAlchemy), ``created_at`` ``DateTime`` NOT
   NULL. Index nommés spec 06 : ``idx_deploy_events_deployment``
   (``deployment_id``) et ``idx_deploy_events_created`` (``created_at``).

2. **Data migration « sans perte » (AC 1)** : la colonne texte
   ``deployments.logs`` existante est découpée en lignes d'events — une
   ligne de texte = un event requêtable (``message`` = ligne brute, la
   concaténation des messages reconstitue le texte original). Mapping :

   - ``level`` par préfixe de ligne : ``[ERROR]`` → ``error``,
     ``[SYSTEM]`` → ``warning``, sinon ``info`` (convention des préfixes
     du pipeline — décision d'analyse 1) ;
   - ``event_type`` par statut du déploiement : ``failed`` → ``error``,
     ``running`` → ``success``, sinon ``deploying`` (décision 1) ;
   - ``created_at`` : **interpolation linéaire** entre
     ``deployments.created_at`` et
     ``COALESCE(stopped_at, deployed_at, updated_at)`` (décision 3). Le
     texte ne porte pas d'horodatage fin ; un timestamp unique ferait
     perdre l'ordre chronologique au tri de l'endpoint
     (``created_at ASC, id ASC``). Limite assumée : si les deux bornes
     sont égales (durée nulle), toutes les lignes reçoivent le même
     horodatage et l'ordre original n'est plus garanti par le tri.

   Tolérance (pattern 1311) : tout échec par déploiement laisse ses
   lignes non migrées avec un ``logger.warning`` sans donnée sensible
   (identifiant de ligne uniquement) — ``upgrade head`` ne doit
   **jamais** échouer. L'import applicatif est inutile ici (aucun
   chiffrement), seul le mode offline est court-circuité.

   **La colonne ``deployments.logs`` n'est jamais modifiée** (critère
   P2-7 : elle reste pour le payload brut — double écriture ensuite).
   Limite assumée : un downgrade puis re-upgrade re-migrerait les lignes
   avec de nouvelles PK uuid4 (les events post-downgrade sont perdus).

3. **Downgrade non destructif** : drop des index puis de la table —
   ``deployments.logs`` intacte.

Revision ID: 1671_deployment_events_table
Revises: 1662_environments_stacks_origin_git_url
Create Date: 2026-10-30 14:00:00.000000+00:00

"""

import logging
from datetime import datetime, timedelta
from typing import List, Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import context as alembic_context
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = "1671_deployment_events_table"
down_revision: Union[str, None] = "1662_environments_stacks_origin_git_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mapping préfixe de ligne → level (convention des préfixes du pipeline,
# décision d'analyse 1) ; [INFO]/[SUCCESS] et le reste → info.
_LEVEL_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("[ERROR]", "error"),
    ("[SYSTEM]", "warning"),
)
_DEFAULT_LEVEL: str = "info"

# Mapping statut du déploiement → event_type des lignes migrées
# (décision 1 : divergence success ↔ running documentée STORY-162).
_EVENT_TYPE_BY_STATUS: dict[str, str] = {
    "failed": "error",
    "running": "success",
}
_DEFAULT_EVENT_TYPE: str = "deploying"


def _level_for_line(line: str) -> str:
    """Retourne le level spec 06 d'une ligne de log (par préfixe)."""
    for prefix, level in _LEVEL_BY_PREFIX:
        if line.startswith(prefix):
            return level
    return _DEFAULT_LEVEL


def _status_value(raw: object) -> str:
    """Normalise le statut stocké (name SQLEnum ou valeur) en lowercase."""
    return str(getattr(raw, "value", raw)).lower()


def _interpolate_timestamps(
    start: datetime | None, end: datetime | None, count: int
) -> List[datetime]:
    """Interpole linéairement ``count`` horodatages entre start et end.

    Décision d'analyse 3 : le texte des logs ne porte pas d'horodatage
    fin — les lignes migrées sont réparties uniformément entre la création
    du déploiement et sa clôture (``COALESCE(stopped_at, deployed_at,
    updated_at)``). Bornes dégénérées (absentes ou inversées) : clamp sur
    ``start`` (utcnow si inconnu) — toutes les lignes reçoivent alors le
    même horodatage, l'ordre original n'est plus garanti par le tri
    (limite documentée).

    Args:
        start: Horodatage de début (création du déploiement).
        end: Horodatage de fin (clôture, éventuellement absente).
        count: Nombre de lignes à dater.

    Returns:
        Liste de ``count`` horodatages naïfs croissants.
    """
    if count <= 0:
        return []
    if start is None:
        start = datetime.utcnow()
    if end is None or end < start:
        end = start
    if count == 1:
        return [start]
    step: timedelta = (end - start) / (count - 1)
    return [start + step * i for i in range(count)]


def _migrate_logs_to_events() -> None:
    """Data migration tolérante : lignes de ``deployments.logs`` → events.

    Best-effort par déploiement (pattern 1311) : un échec laisse les
    lignes du déploiement non migrées avec un warning sans donnée
    sensible — l'upgrade ne doit jamais échouer.
    """
    if alembic_context.is_offline_mode():
        # Génération SQL hors ligne : aucune base connectée, aucune
        # donnée à migrer (DDL seul).
        return

    bind = op.get_bind()
    metadata = sa.MetaData()
    deployments_table = sa.Table("deployments", metadata, autoload_with=bind)
    events_table = sa.Table("deployment_events", metadata, autoload_with=bind)

    rows = bind.execute(
        sa.select(
            deployments_table.c.id,
            deployments_table.c.logs,
            deployments_table.c.status,
            deployments_table.c.created_at,
            deployments_table.c.stopped_at,
            deployments_table.c.deployed_at,
            deployments_table.c.updated_at,
        )
    ).fetchall()

    migrated_lines = 0
    for row in rows:
        if not row.logs:
            # Logs vides/NULL : aucune ligne à migrer (cas nominal).
            continue
        try:
            lines = [line for line in str(row.logs).split("\n") if line.strip()]
            if not lines:
                continue

            event_type = _EVENT_TYPE_BY_STATUS.get(
                _status_value(row.status), _DEFAULT_EVENT_TYPE
            )
            # COALESCE(stopped_at, deployed_at, updated_at) — décision 3.
            end = row.stopped_at or row.deployed_at or row.updated_at
            timestamps = _interpolate_timestamps(row.created_at, end, len(lines))

            bind.execute(
                events_table.insert(),
                [
                    {
                        "id": str(uuid4()),
                        "deployment_id": row.id,
                        "event_type": event_type,
                        "level": _level_for_line(line),
                        "message": line,
                        "data": None,
                        "created_at": ts,
                    }
                    for line, ts in zip(lines, timestamps)
                ],
            )
            migrated_lines += len(lines)
        except Exception:
            # Tolérance : lignes de ce déploiement laissées non migrées
            # (deployments.logs intacte — aucune perte), warning sans
            # donnée sensible (identifiant uniquement).
            logger.warning(
                "1671: déploiement %s laissé sans events — lignes de "
                "logs illisibles (best-effort, upgrade jamais en échec)",
                row.id,
            )

    if migrated_lines:
        logger.info(
            "1671: %d ligne(s) de logs migrée(s) vers deployment_events",
            migrated_lines,
        )


def upgrade() -> None:
    op.create_table(
        "deployment_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "deployment_id",
            sa.String(length=36),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_deploy_events_deployment", "deployment_events", ["deployment_id"]
    )
    op.create_index("idx_deploy_events_created", "deployment_events", ["created_at"])

    _migrate_logs_to_events()


def downgrade() -> None:
    op.drop_index("idx_deploy_events_created", table_name="deployment_events")
    op.drop_index("idx_deploy_events_deployment", table_name="deployment_events")
    op.drop_table("deployment_events")
