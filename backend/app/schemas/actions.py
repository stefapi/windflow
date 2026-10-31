"""Schémas Pydantic des paramètres des actions scheduler core (STORY-160.1).

Chaque action du registre ([`services/action_registry.py`](../services/action_registry.py))
est définie par un **schéma de paramètres strict** (spec 17 § Scheduler core) :
borné, typé, `extra="forbid"` — jamais de paramètre libre non validé
(checklist sécurité rules 40 : aucune exécution avec des paramètres non
validés).

Arbitrage de nomenclature (décision d'entrée STORY-160.1, tracée en note
d'implémentation de la story — alerte STORY-252 si la spec doit être
corrigée) :

- ``host.scan`` — paramètre ``target_id`` : l'entité « Host » des specs
  n'existe pas en base (arbitrage F3, renommage porté par STORY-166),
  la clé étrangère réelle est ``targets.id`` ;
- ``compute.docker.prune`` — clé unique du plan P2-1 (vs
  ``compute.images.prune``/``compute.volumes.prune`` de la spec 17) avec
  paramètre borné ``resource: "images" | "volumes"``, sémantique prune
  protégé STORY-173 (liste ``windflow-plugin-*`` épargnée, ``dry_run``
  par défaut) ;
- ``stack.backup`` / ``admin.backup`` — clés du plan P2-1 (vs
  ``app.backup`` / ``admin.backup.create`` de la spec 17), stubs
  explicites (renvoi F8 — initiative backup) ;
- ``notification.send`` — contrat spec 17 § Notifications
  (``channel``/``title``/``message``/``severity``/``event_type``/
  ``routing``), stub explicite (renvoi P2-15).
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ActionParams(BaseModel):
    """Base commune des schémas de paramètres d'action.

    ``extra="forbid"`` : tout paramètre non prévu par le schéma de
    l'action est rejeté (422) — surface d'attaque minimale, pas de
    paramètre « passe-partout » persisté puis exécuté.
    """

    model_config = ConfigDict(extra="forbid")


class HostScanParams(ActionParams):
    """Paramètres de l'action ``host.scan`` — rescan des moteurs et objets
    discovered d'une cible (implémentation réelle portée par STORY-160.3)."""

    target_id: str = Field(
        ...,
        min_length=1,
        max_length=36,
        description="Identifiant de la cible à rescaner (targets.id — "
        "arbitrage F3, renommage Host STORY-166)",
    )


class DockerPruneParams(ActionParams):
    """Paramètres de l'action ``compute.docker.prune``.

    Sémantique prune protégé (STORY-173) : la liste ``windflow-plugin-*``
    est épargnée par construction et ``dry_run`` vaut ``True`` par
    défaut — un prune planifié ne détruit rien sans action explicite.
    """

    resource: Literal["images", "volumes", "containers"] = Field(
        ...,
        description="Ressource Docker à nettoyer (images non utilisées / "
        "volumes orphelins / containers stoppés non managés — STORY-173)",
    )
    dry_run: bool = Field(
        default=True,
        description="Simulation sans suppression (défaut True — sécurité " "STORY-173)",
    )
    force: bool = Field(
        default=False,
        description="Contourner les confirmations de l'API Docker "
        "(n'affecte pas la liste protégée windflow-plugin-*)",
    )


class DeploymentEventsPurgeParams(ActionParams):
    """Paramètres de l'action ``deployment_events.purge`` (STORY-167).

    Rétention des événements de déploiement exécutée comme tâche
    ordinaire du scheduler (spec 17 — maintenance planifiée, coordonnée
    avec la boucle lifespan : les deux délèguent au même
    ``purge_expired`` idempotent).
    """

    retention_days: int = Field(
        default=30,
        ge=1,
        le=3650,
        description="Rétention des événements en jours (cutoff created_at)",
    )


class StackBackupParams(ActionParams):
    """Paramètres de l'action ``stack.backup`` (stub explicite — renvoi
    F8 / initiative backup)."""

    stack_id: str = Field(
        ...,
        min_length=1,
        max_length=36,
        description="Identifiant de la stack à sauvegarder",
    )
    keep: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Nombre de sauvegardes à conserver (rétention)",
    )


class AdminBackupParams(ActionParams):
    """Paramètres de l'action ``admin.backup`` (stub explicite — renvoi
    F8 / initiative backup, spec 16)."""

    output: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Répertoire de sortie du backup core (défaut : "
        "configuration serveur)",
    )


class NotificationSendParams(ActionParams):
    """Paramètres de l'action ``notification.send`` (stub explicite —
    renvoi P2-15) — contrat spec 17 § Notifications."""

    channel: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Canal de notification (contrat de canal, P2-15)",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Corps du message",
    )
    title: Optional[str] = Field(
        default=None, max_length=200, description="Titre de la notification"
    )
    severity: Literal["info", "warning", "error"] = Field(
        default="info", description="Sévérité affichée"
    )
    event_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Type d'événement à l'origine de la notification "
        "(ex. deployment.failed)",
    )
    routing: Optional[List[str]] = Field(
        default=None,
        description="Canaux explicites visés (court-circuit de la matrice "
        "de routage)",
    )


__all__ = [
    "ActionParams",
    "HostScanParams",
    "DockerPruneParams",
    "StackBackupParams",
    "AdminBackupParams",
    "NotificationSendParams",
]
