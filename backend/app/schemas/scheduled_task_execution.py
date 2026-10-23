"""Schemas Pydantic V2 pour les exécutions de tâches planifiées (STORY-161).

Contrats I/O des endpoints de consultation ``/schedules/executions``
(spec 06 § Entités d'automatisation, spec 17 § Exécutions) :

- filtres de query typés par ``Literal`` (``status``, ``triggered_by`` —
  valeur hors domaine → 422 ``VALIDATION_ERROR``, jamais de filtre
  silencieusement ignoré) et dates ISO 8601 (``started_after`` /
  ``started_before``) ;
- liste légère **sans** ``logs`` (spec 09 : les listes paginées restent
  compactes) ; le détail expose le journal structuré
  ``ExecutionLogLine{timestamp, message}`` (ISO 8601 UTC, stockage UTC) ;
- ``ManualRunResponse`` : accusé 202 fire-and-forget du déclenchement
  manuel.

Checklist sécurité (rules 40) : **aucun champ sensible** — jamais les
``parameters`` de définition ni de secrets dans ces schémas ;
``error`` est la version assainie/tronquée persistée par
``sanitize_error`` (jamais de stack brute).
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Domaines canoniques (spec 06) — Literal : valeur hors domaine → 422.
EXECUTION_STATUSES: tuple[str, ...] = (
    "queued",
    "running",
    "success",
    "failed",
    "skipped",
)
EXECUTION_ORIGINS: tuple[str, ...] = ("cron", "event", "manual")


class ExecutionLogLine(BaseModel):
    """Ligne de journal horodatée d'une exécution (spec 06/17 — ISO 8601 UTC)."""

    timestamp: datetime = Field(
        ...,
        description="Horodatage de la ligne (ISO 8601, stockage UTC).",
        json_schema_extra={"example": "2026-10-23T03:00:00.123456+00:00"},
    )
    message: str = Field(
        ...,
        description="Contenu de la ligne (assaini — jamais de secret).",
        json_schema_extra={"example": "running"},
    )


class ScheduledTaskExecutionListItem(BaseModel):
    """Item de liste d'exécution — léger, **sans** journal."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Identifiant unique de l'exécution.")
    task_id: str = Field(..., description="Définition ``scheduled_tasks`` exécutée.")
    status: Literal["queued", "running", "success", "failed", "skipped"] = Field(
        ..., description="Cycle de vie : queued → running → success|failed ; skipped."
    )
    triggered_by: Literal["cron", "event", "manual"] = Field(
        ..., description="Origine du déclenchement (nomenclature spec 06)."
    )
    started_at: Optional[datetime] = Field(
        None, description="Passage en running (None = jamais démarrée)."
    )
    finished_at: Optional[datetime] = Field(
        None, description="Clôture success/failed/skipped (None = en cours)."
    )
    duration_seconds: Optional[float] = Field(
        None,
        description="Durée en secondes fractionnaires, calculée à la clôture.",
    )
    error: Optional[str] = Field(
        None,
        description="Message assaini/tronqué (rules 40 — jamais de stack brute).",
    )
    created_at: datetime = Field(..., description="Création de la ligne (queued).")


class ScheduledTaskExecutionResponse(ScheduledTaskExecutionListItem):
    """Détail d'une exécution — item + journal ligne à ligne complet."""

    logs: list[ExecutionLogLine] = Field(
        default_factory=list,
        description="Journal horodaté (ISO 8601 UTC) — vide si aucun.",
    )


class ManualRunResponse(BaseModel):
    """Accusé de déclenchement manuel (202 Accepted — fire-and-forget)."""

    execution_id: str = Field(
        ...,
        description="Identifiant de la ligne d'exécution ``queued`` créée.",
        json_schema_extra={"example": "b4e1c0a2-9f3d-4c5b-8e7a-1d2f3a4b5c6d"},
    )
    status: str = Field(
        default="queued",
        description="Statut au moment de la réponse (``queued``).",
        json_schema_extra={"example": "queued"},
    )
    triggered_by: str = Field(
        default="manual",
        description="Origine du déclenchement (``manual``).",
        json_schema_extra={"example": "manual"},
    )


class ExecutionQueryParams(BaseModel):
    """Filtres de la vue globale des exécutions (validation partagée).

    ``status``/``triggered_by`` sont des ``Literal`` : une valeur hors
    domaine est rejetée en 422 par FastAPI (checklist rules 40 —
    validation & injection). Les dates sont parsées ISO 8601 par Pydantic
    (422 sinon).
    """

    status: Optional[Literal["queued", "running", "success", "failed", "skipped"]] = (
        None
    )
    triggered_by: Optional[Literal["cron", "event", "manual"]] = None
    started_after: Optional[datetime] = None
    started_before: Optional[datetime] = None


__all__ = [
    "ExecutionLogLine",
    "ExecutionQueryParams",
    "ManualRunResponse",
    "ScheduledTaskExecutionListItem",
    "ScheduledTaskExecutionResponse",
]
