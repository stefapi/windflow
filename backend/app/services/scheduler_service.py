"""
Service de gestion des tâches planifiées.

CRUD des définitions spec 17 (STORY-160.1) : validation métier
centralisée via le **registre d'actions** (action + schéma params) ;
l'exécution récurrente est portée par le moteur scheduler asyncio
(STORY-160.2) et les handlers d'actions par STORY-160.3.

Checklist sécurité (rules 40) : les logs ne portent jamais les
``parameters`` bruts (un paramètre peut référencer une ressource
sensible) — nom/action/trigger uniquement.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import UnprocessableEntityError
from ..helper.croniter import CroniterBadCronError, croniter
from ..models.scheduled_task import ScheduledTask
from .action_registry import is_valid as action_is_valid
from .action_registry import validate_params as validate_action_params

logger = logging.getLogger(__name__)

# Champs de définition mutables via update (task_type legacy retiré par
# la migration 1321 — plus accepté).
_UPDATABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "description",
        "action",
        "trigger_type",
        "event_name",
        "timezone",
        "error_policy",
        "cron_expression",
        "parameters",
        "enabled",
    }
)


def _validate_definition(
    *,
    action: str,
    trigger_type: str,
    event_name: Optional[str],
    timezone: Optional[str],
    cron_expression: Optional[str],
    parameters: dict,
) -> dict:
    """Validation métier d'une définition (hors HTTP — Tâche 5).

    Défense en profondeur derrière la validation Pydantic de l'API :
    toute invocation directe du service (CLI, seed, moteur) passe par
    les mêmes règles (registre, croniter, cohérence trigger/event).

    Args:
        action: Clé du registre canonique.
        trigger_type: ``cron`` | ``event``.
        event_name: Événement canonique (requis si ``event``).
        timezone: Fuseau IANA (None = défaut settings).
        cron_expression: Expression cron (validée croniter).
        parameters: Paramètres bruts (validés par le schéma de l'action).

    Returns:
        Les paramètres validés/normalisés.

    Raises:
        UnprocessableEntityError: 422 — action hors registre, cron
            invalide, ``event`` sans ``event_name``, ``event_name`` non
            canonique, fuseau IANA inconnu, paramètres invalides.
    """
    if not action_is_valid(action):
        raise UnprocessableEntityError(
            f"Unknown scheduler action: {action!r}",
            details={"action": action},
        )
    try:
        validated_params = validate_action_params(action, parameters or {})
    except Exception as exc:
        raise UnprocessableEntityError(
            f"Invalid parameters for action {action!r}",
            details={"action": action},
        ) from exc

    if trigger_type not in ("cron", "event"):
        raise UnprocessableEntityError(
            f"Invalid trigger_type: {trigger_type!r} (cron | event)",
            details={"trigger_type": trigger_type},
        )
    if trigger_type == "event":
        from ..core.events import LEGACY_EVENT_ALIASES, EventType, resolve_event_name

        if not event_name:
            raise UnprocessableEntityError(
                "event_name is required when trigger_type='event'",
                details={"trigger_type": trigger_type},
            )
        resolved = resolve_event_name(event_name)
        if resolved not in {member.value for member in EventType} | set(
            LEGACY_EVENT_ALIASES
        ):
            raise UnprocessableEntityError(
                f"Unknown event_name: {event_name!r} (canonical EventType "
                "required, spec 11)",
                details={"event_name": event_name},
            )
        # NOTE : la valeur canonique est stockée par le schéma Pydantic
        # (résolution à la validation) — ici, simple re-validation défensive.
    if cron_expression is not None:
        try:
            croniter(cron_expression)
        except (CroniterBadCronError, ValueError) as exc:
            raise UnprocessableEntityError(
                f"Invalid cron expression: {cron_expression!r}",
                details={"cron_expression": cron_expression},
            ) from exc
    if timezone is not None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise UnprocessableEntityError(
                f"Unknown IANA timezone: {timezone!r}",
                details={"timezone": timezone},
            ) from exc
    return validated_params


class SchedulerService:
    """Service CRUD pour les tâches planifiées (définitions spec 17)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tasks(
        self,
        organization_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[ScheduledTask]:
        """Liste les tâches planifiées, paginées (STORY-128).

        Tri stable ``ORDER BY name`` (l'ancien ``created_at desc`` sans
        tie-breaker rendait les pages non déterministes) ; le filtre
        ``organization_id`` est combiné dans la même requête que la
        pagination.

        Args:
            organization_id: Filtre optionnel par organisation
            page: Page demandée (1-indexée, bornée par le Query endpoint)
            per_page: Taille de page (1-100, bornée par le Query endpoint)

        Returns:
            Liste des tâches de la page, triée par nom
        """
        query = select(ScheduledTask).order_by(ScheduledTask.name)
        if organization_id:
            query = query.where(ScheduledTask.organization_id == organization_id)
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_tasks(self, organization_id: Optional[str] = None) -> int:
        """Compte les tâches planifiées (STORY-128).

        ``COUNT`` avec le **même filtre** ``organization_id`` que
        :meth:`list_tasks` (rules 40 — pas d'oracle de comptage).

        Args:
            organization_id: Filtre optionnel par organisation

        Returns:
            Nombre total de tâches correspondant au filtre
        """
        query = select(func.count()).select_from(ScheduledTask)
        if organization_id:
            query = query.where(ScheduledTask.organization_id == organization_id)
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Récupère une tâche par son ID."""
        result = await self.db.execute(
            select(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create_task(
        self,
        name: str,
        action: str,
        cron_expression: str,
        organization_id: str,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        enabled: bool = True,
        trigger_type: str = "cron",
        event_name: Optional[str] = None,
        timezone: Optional[str] = None,
        error_policy: str = "ignore",
    ) -> ScheduledTask:
        """Crée une nouvelle tâche planifiée (v2 — spec 17).

        La validation (registre, croniter, zoneinfo, EventType) est
        assurée par les schémas Pydantic à l'API **et** rejouée ici
        (défense en profondeur pour les appelants hors HTTP).

        Raises:
            UnprocessableEntityError: Définition invalide (422).
        """
        validated_params = _validate_definition(
            action=action,
            trigger_type=trigger_type,
            event_name=event_name,
            timezone=timezone,
            cron_expression=cron_expression,
            parameters=parameters or {},
        )
        task = ScheduledTask(
            id=str(uuid4()),
            name=name,
            description=description,
            action=action,
            trigger_type=trigger_type,
            event_name=event_name,
            timezone=timezone,
            error_policy=error_policy,
            cron_expression=cron_expression,
            parameters=validated_params,
            enabled=enabled,
            organization_id=organization_id,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        # Rules 40 : jamais les parameters bruts dans les logs.
        logger.info(
            "Tâche planifiée créée : %s (action=%s, trigger=%s)",
            task.name,
            task.action,
            task.trigger_type,
        )
        return task

    async def update_task(
        self,
        task_id: str,
        **kwargs: Any,
    ) -> Optional[ScheduledTask]:
        """Met à jour une tâche planifiée (v2 — spec 17).

        La définition **fusionnée** (état courant + champs fournis) est
        revalidée intégralement : un update ne peut pas corrompre la
        cohérence trigger/event ni référencer une action/params
        invalides (défense en profondeur — le schéma Update ne voit que
        les champs fournis).

        Raises:
            UnprocessableEntityError: Définition fusionnée invalide (422).
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        updates = {k: v for k, v in kwargs.items() if k in _UPDATABLE_FIELDS}
        merged = {
            "action": updates.get("action", task.action),
            "trigger_type": updates.get("trigger_type", task.trigger_type),
            "event_name": updates.get("event_name", task.event_name),
            "timezone": updates.get("timezone", task.timezone),
            "cron_expression": updates.get("cron_expression", task.cron_expression),
            "parameters": updates.get("parameters", task.parameters),
        }
        validated_params = _validate_definition(**merged)

        for key, value in updates.items():
            if value is not None:
                setattr(task, key, value)
        if "parameters" in updates:
            task.parameters = validated_params

        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        # Rules 40 : jamais les parameters bruts dans les logs.
        logger.info(
            "Tâche planifiée mise à jour : %s (action=%s)",
            task.name,
            task.action,
        )
        return task

    async def delete_task(self, task_id: str) -> bool:
        """Supprime une tâche planifiée."""
        result = await self.db.execute(
            delete(ScheduledTask).where(ScheduledTask.id == task_id)
        )
        await self.db.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]

    async def toggle_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Active/désactive une tâche planifiée."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.enabled = not task.enabled
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        logger.info(f"Tâche {task.name} {'activée' if task.enabled else 'désactivée'}")
        return task

    async def record_run(
        self, task_id: str, status: str, error: Optional[str] = None
    ) -> Optional[ScheduledTask]:
        """Enregistre le résultat d'une exécution."""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.last_run = datetime.utcnow()
        task.last_status = status
        task.last_error = error
        task.run_count += 1
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_enabled_tasks(self) -> list[ScheduledTask]:
        """Récupère toutes les tâches actives pour le moteur scheduler asyncio."""
        result = await self.db.execute(
            select(ScheduledTask).where(ScheduledTask.enabled == True)
        )
        return list(result.scalars().all())
