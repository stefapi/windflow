"""Registre canonique des actions scheduler core (STORY-160.1, spec 17).

Une définition de tâche planifiée référence une **action du registre**
(clé canonique) — plus d'enum fermé arbitraire ([`models/scheduled_task.py`](../models/scheduled_task.py)
retire ``TaskType``). Le registre porte pour chaque action :

- un ``params_schema`` Pydantic **strict** ([`schemas/actions.py`](../schemas/actions.py)) ;
- un ``implemented`` : ``True`` (action consommable, exécutée par le
  moteur STORY-160.2 et les handlers STORY-160.3) ou ``False``
  (**stub explicite documenté** — jamais de succès silencieux à
  l'exécution, comportement porté par 160.3) ;
- un ``handler`` : optionnel à ce stade (renseigné par 160.3).

Arbitrage de nomenclature (décision d'entrée de STORY-160.1, tracée en
note d'implémentation — à signaler à STORY-252 si la spec 17 doit être
corrigée) — plan P2-1 retenu comme liste de travail, confronté à la
spec 17 § Actions core et à la sémantique prune de STORY-173 :

======================  ============================  ====================
Clé retenue             Origine                      Statut
======================  ============================  ====================
``host.scan``           spec 17 (= plan P2-1)        consommable (160.3)
``compute.docker.prune``  plan P2-1 (clé unique,      consommable (160.3)
                        paramètre ``resource`` borné
                        vs ``compute.images.prune``/
                        ``compute.volumes.prune``
                        spec 17)
``stack.backup``        plan P2-1 (vs ``app.backup``  **stub** (F8 —
                        spec 17 : « App » ≡ stack)     initiative backup)
``admin.backup``        plan P2-1 (vs                 **stub** (F8 —
                        ``admin.backup.create``       initiative backup)
                        spec 17)
``notification.send``   spec 17 (= plan P2-1)        **stub** (P2-15)
======================  ============================  ====================

Raison du choix ``compute.docker.prune`` : le plan P2-1 pose une clé
unique avec la ressource en paramètre — la spec 17 éclate en deux clés.
La clé unique évite la duplication de code handler (un seul handler
prune, la ressource est un paramètre validé) et matche la sémantique du
endpoint Docker API ``POST /prune``. La correction de la spec 17
(renommage ``app.*``→``stack.*``, fusion des clés prune) est un point
d'entrée STORY-252.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel

from ..core.exceptions import InvalidInputError
from ..schemas.actions import (
    AdminBackupParams,
    DeploymentEventsPurgeParams,
    DockerPruneParams,
    HostScanParams,
    NotificationSendParams,
    StackBackupParams,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionDefinition:
    """Définition canonique d'une action scheduler.

    Attributes:
        name: Clé canonique du registre (ex. ``host.scan``).
        description: Description lisible (exposée OpenAPI).
        params_schema: Schéma Pydantic strict des paramètres — toute
            définition référencée est validée à la création/modification
            (422 si paramètres invalides).
        implemented: ``True`` si l'action est réellement exécutable ;
            ``False`` = **stub explicite** (définition posable, mais
            l'exécution échouera proprement — jamais de succès
            silencieux, comportement STORY-160.3).
        handler: Callable d'exécution (None à ce stade — branché par
            STORY-160.3).
    """

    name: str
    description: str
    params_schema: type[BaseModel]
    implemented: bool
    handler: Optional[Callable] = field(default=None)


# Registre canonique — figé à l'import (immutabilité des définitions ;
# les plugins pourront s'y ajouter via STORY-163, hors périmètre 160.1).
_REGISTRY: Dict[str, ActionDefinition] = {
    definition.name: definition
    for definition in (
        ActionDefinition(
            name="host.scan",
            description="Rescan des moteurs et objets discovered d'une "
            "cible (spec 17 § Actions core ; implémentation STORY-160.3)",
            params_schema=HostScanParams,
            implemented=True,
        ),
        ActionDefinition(
            name="compute.docker.prune",
            description="Nettoyage Docker protégé — images non utilisées "
            "ou volumes orphelins ; liste windflow-plugin-* épargnée, "
            "dry_run par défaut (STORY-173)",
            params_schema=DockerPruneParams,
            implemented=True,
        ),
        ActionDefinition(
            name="deployment_events.purge",
            description="Rétention des événements de déploiement — purge "
            "des lignes deployment_events au-delà de la rétention "
            "(spec 17 § Maintenance, STORY-167)",
            params_schema=DeploymentEventsPurgeParams,
            implemented=True,
        ),
        ActionDefinition(
            name="stack.backup",
            description="[STUB — F8/initiative backup] Sauvegarde d'une "
            "stack (volumes, configuration) ; exécution non disponible "
            "à ce stade",
            params_schema=StackBackupParams,
            implemented=False,
        ),
        ActionDefinition(
            name="admin.backup",
            description="[STUB — F8/initiative backup] Backup core "
            "(spec 16) ; exécution non disponible à ce stade",
            params_schema=AdminBackupParams,
            implemented=False,
        ),
        ActionDefinition(
            name="notification.send",
            description="[STUB — P2-15] Notification selon le contrat de "
            "canal (spec 17 § Notifications) ; exécution non disponible "
            "à ce stade",
            params_schema=NotificationSendParams,
            implemented=False,
        ),
    )
}


def get_action(name: str) -> ActionDefinition:
    """Retourne la définition d'une action du registre.

    Args:
        name: Clé canonique (ex. ``host.scan``).

    Returns:
        La définition de l'action.

    Raises:
        InvalidInputError: Action inconnue du registre — erreur
            **explicite** (400 ``INVALID_INPUT``), jamais un ``KeyError``
            brut remontant en 500.
    """
    definition = _REGISTRY.get(name)
    if definition is None:
        raise InvalidInputError(
            f"Unknown scheduler action: {name}",
            details={"action": name, "known_actions": sorted(_REGISTRY)},
        )
    return definition


def list_actions() -> List[ActionDefinition]:
    """Liste toutes les actions du registre (ordre alphabétique).

    Returns:
        Liste des définitions d'actions core.
    """
    return sorted(_REGISTRY.values(), key=lambda d: d.name)


def is_valid(name: str) -> bool:
    """Vérifie qu'une clé d'action appartient au registre.

    Cohérent avec :func:`get_action` : ``is_valid(name)`` est vrai si et
    seulement si ``get_action(name)`` ne lève pas.

    Args:
        name: Clé candidat.

    Returns:
        ``True`` si l'action est enregistrée, ``False`` sinon.
    """
    return name in _REGISTRY


def validate_params(name: str, parameters: dict) -> dict:
    """Valide les paramètres d'une définition contre le schéma de l'action.

    Args:
        name: Clé canonique de l'action.
        parameters: Paramètres bruts de la définition de tâche.

    Returns:
        Les paramètres validés (et normalisés par défauts du schéma).

    Raises:
        InvalidInputError: Action inconnue (via ``get_action``).
        UnprocessableEntityError: Paramètres invalides au regard du
            schéma de l'action (422 ``VALIDATION_ERROR``).
    """
    definition = get_action(name)
    validated = definition.params_schema.model_validate(parameters)
    return validated.model_dump()


__all__ = [
    "ActionDefinition",
    "get_action",
    "list_actions",
    "is_valid",
    "validate_params",
]
