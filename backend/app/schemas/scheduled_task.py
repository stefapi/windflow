"""Schemas Pydantic V2 pour les tâches planifiées (spec 17 — STORY-160.1).

Contrats I/O ``/schedules`` v2 : ``action`` du registre canonique,
``trigger_type`` ``cron``|``event``, ``event_name`` (∈ liste canonique
``EventType``), ``timezone`` IANA, ``error_policy`` — validation de bout
en bout (checklist sécurité rules 40) :

- expression cron validée via croniter vendored (invalide → 422) ;
- fuseau via ``zoneinfo.ZoneInfo`` (inconnu → 422) ;
- ``action`` ∈ registre (via ``action_registry``, 422) ;
- ``event_name`` ∈ ``EventType`` (spec 11) et **requis** si
  ``trigger_type='event'`` (422) ;
- ``parameters`` validés par le schéma Pydantic de l'action (422,
  ``model_validator(mode='before')`` — accès au payload brut complet) ;
- ``extra='forbid'`` : le champ legacy ``task_type`` (retiré par la
  migration 1321) est explicitement rejeté en entrée.

La ``Response`` n'expose aucun champ sensible : ``parameters`` est
retourné tel que validé (structure bornée par le schéma d'action —
``extra='forbid'`` interdit les champs libres), jamais loggé brut
(audit ``_sanitize_details``).
"""

from datetime import datetime
from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.events import EventType
from ..helper.croniter import CroniterBadCronError, croniter
from ..services.action_registry import is_valid as action_is_valid
from ..services.action_registry import validate_params as validate_action_params

# Liste canonique des événements (spec 11 — valeurs machine EventType).
_CANONICAL_EVENT_NAMES: frozenset[str] = frozenset(member.value for member in EventType)

TRIGGER_TYPES: tuple[str, ...] = ("cron", "event")
ERROR_POLICIES: tuple[str, ...] = ("ignore", "retry", "disable")


def _validate_cron_expression(expr: str) -> str:
    """Valide une expression cron via croniter (422 si invalide).

    Args:
        expr: Expression cron (5-7 champs).

    Returns:
        L'expression validée (inchangée).

    Raises:
        ValueError: Expression rejetée par croniter — Pydantic la
            convertit en 422 ``VALIDATION_ERROR``.
    """
    try:
        croniter(expr)
    except (CroniterBadCronError, ValueError) as exc:
        raise ValueError(f"Invalid cron expression: {expr!r} ({exc})") from exc
    return expr


def _validate_timezone(name: Optional[str]) -> Optional[str]:
    """Valide un fuseau IANA via zoneinfo (422 si inconnu). None accepté.

    Args:
        name: Nom de fuseau (ex. ``Europe/Paris``).

    Returns:
        Le fuseau validé (inchangé).

    Raises:
        ValueError: Fuseau inconnu du contexte IANA.
    """
    if name is None:
        return name
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {name!r}") from exc
    return name


def _validate_event_name(name: Optional[str]) -> Optional[str]:
    """Valide un event_name contre la liste canonique EventType (422).

    Args:
        name: Nom d'événement candidat (None accepté pour les crons).

    Returns:
        Le nom validé (inchangé).

    Raises:
        ValueError: Événement hors liste canonique spec 11.
    """
    if name is not None and name not in _CANONICAL_EVENT_NAMES:
        raise ValueError(
            f"Unknown event_name: {name!r} (must be a canonical EventType, " "spec 11)"
        )
    return name


def _validate_action(name: str) -> str:
    """Valide qu'une action appartient au registre canonique (422 sinon).

    Args:
        name: Clé candidate.

    Returns:
        La clé validée (inchangée).

    Raises:
        ValueError: Action inconnue du registre.
    """
    if not action_is_valid(name):
        raise ValueError(f"Unknown scheduler action: {name!r}")
    return name


def _validate_parameters_raw(data: dict) -> dict:
    """Valide ``parameters`` contre le schéma de l'action (payload brut).

    ``model_validator(mode='before')`` : accès simultané à ``action`` et
    ``parameters`` du payload — les paramètres sont validés par le
    schéma Pydantic strict de l'action visée (422 si invalides).

    Args:
        data: Payload brut (clés ``action``/``parameters``).

    Returns:
        Le payload, ``parameters`` remplacés par les valeurs validées.

    Raises:
        ValueError: Paramètres invalides au regard du schéma de l'action.
    """
    action = data.get("action")
    parameters = data.get("parameters")
    if (
        isinstance(action, str)
        and action_is_valid(action)
        and isinstance(parameters, dict)
    ):
        data["parameters"] = validate_action_params(action, parameters)
    return data


class _ScheduledTaskValidators(BaseModel):
    """Validators sémantiques spec 17 partagés Create/Update (mixin).

    Les ``field_validator`` s'appliquent aux champs déclarés par les
    sous-classes ; ``_validate_parameters_raw`` (mode before) couple
    ``action``↔``parameters`` sur le payload brut.
    """

    @model_validator(mode="before")
    @classmethod
    def _params_against_action(cls, data: dict) -> dict:
        if isinstance(data, dict):
            return _validate_parameters_raw(data)
        return data

    @field_validator("cron_expression", check_fields=False)
    @classmethod
    def _v_cron(cls, value: Optional[str]) -> Optional[str]:
        return _validate_cron_expression(value) if value is not None else value

    @field_validator("timezone", check_fields=False)
    @classmethod
    def _v_timezone(cls, value: Optional[str]) -> Optional[str]:
        return _validate_timezone(value)

    @field_validator("event_name", check_fields=False)
    @classmethod
    def _v_event_name(cls, value: Optional[str]) -> Optional[str]:
        return _validate_event_name(value)

    @field_validator("action", check_fields=False)
    @classmethod
    def _v_action(cls, value: Optional[str]) -> Optional[str]:
        return _validate_action(value) if value is not None else value


class ScheduledTaskCreate(_ScheduledTaskValidators):
    """Création d'une tâche planifiée (v2 — spec 17)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    action: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Clé canonique de l'action scheduler (registre — ex. "
        "'host.scan', 'compute.docker.prune')",
    )
    trigger_type: Literal["cron", "event"] = Field(
        default="cron",
        description="Type de déclencheur : planification cron ou événement",
    )
    event_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Événement canonique (spec 11) déclenchant la tâche — "
        "requis si trigger_type='event'",
    )
    timezone: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Fuseau IANA de planification (ex. 'Europe/Paris') — "
        "défaut settings sinon",
    )
    error_policy: Literal["ignore", "retry", "disable"] = Field(
        default="ignore",
        description="Politique d'erreur : ignore | retry | disable",
    )
    cron_expression: str = Field(
        default="0 * * * *",
        min_length=1,
        max_length=100,
        description="Expression cron (ex: '0 3 * * *')",
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Paramètres de l'action — validés par le schéma de "
        "l'action (registre)",
    )
    enabled: bool = True
    organization_id: str

    @model_validator(mode="after")
    def _validate_trigger(self) -> "ScheduledTaskCreate":
        """``event`` sans ``event_name`` → 422 (validation croisée)."""
        if self.trigger_type == "event" and not self.event_name:
            raise ValueError("event_name is required when trigger_type='event'")
        return self


class ScheduledTaskUpdate(_ScheduledTaskValidators):
    """Mise à jour d'une tâche planifiée (v2 — spec 17).

    Tous les champs sont optionnels (PATCH sémantique sur PUT) ; les
    champs fournis subissent la **même validation** que la création.
    La validation croisée ``event`` sans ``event_name`` s'applique aux
    seules valeurs fournies ; la cohérence de l'état fusionné (ex.
    trigger event conservé avec event_name retiré) est garantie par le
    service (défense en profondeur, Tâche 5).
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    action: Optional[str] = Field(None, min_length=1, max_length=100)
    trigger_type: Optional[Literal["cron", "event"]] = None
    event_name: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=64)
    error_policy: Optional[Literal["ignore", "retry", "disable"]] = None
    cron_expression: Optional[str] = Field(None, min_length=1, max_length=100)
    parameters: Optional[dict] = None
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def _validate_trigger(self) -> "ScheduledTaskUpdate":
        """``event`` fourni sans ``event_name`` → 422."""
        if self.trigger_type == "event" and self.event_name is None:
            raise ValueError("event_name is required when trigger_type='event'")
        return self


class ScheduledTaskResponse(BaseModel):
    """Réponse pour une tâche planifiée — sans champ sensible.

    ``parameters`` est retourné tel que validé (structure bornée par le
    schéma de l'action — ``extra='forbid'``) ; aucun secret ne peut y
    vivre car les schémas d'action n'en définissent aucun.
    """

    id: str
    name: str
    description: Optional[str] = None
    action: str
    trigger_type: str
    event_name: Optional[str] = None
    timezone: Optional[str] = None
    error_policy: str
    cron_expression: str
    parameters: dict
    enabled: bool
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    run_count: int
    organization_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "TRIGGER_TYPES",
    "ERROR_POLICIES",
    "ScheduledTaskCreate",
    "ScheduledTaskUpdate",
    "ScheduledTaskResponse",
]
