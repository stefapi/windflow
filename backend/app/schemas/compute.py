"""
Schémas Pydantic pour l'API Compute.

Ces schémas représentent la vue agrégée des ressources compute :
- Stacks managées par WindFlow (label windflow.managed=true)
- Objets découverts (containers compose externes sans label WindFlow)
- Containers standalone (sans label compose ni WindFlow)
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Primitives — Services et containers
# =============================================================================


class ContainerPortMapping(BaseModel):
    """Mapping de port container."""

    host_ip: str = Field("0.0.0.0", description="IP hôte")
    host_port: int = Field(..., description="Port hôte")
    container_port: int = Field(..., description="Port container")
    protocol: str = Field("tcp", description="Protocole (tcp/udp)")


class ServiceWithMetrics(BaseModel):
    """Un service (container) appartenant à une stack managée ou découverte."""

    id: str = Field(..., description="Container ID (12 premiers caractères)")
    name: str = Field(..., description="Nom du container/service")
    image: str = Field(..., description="Image Docker utilisée")
    status: str = Field(..., description="État du container (running, exited, etc.)")
    cpu_percent: float = Field(0.0, description="Utilisation CPU en %")
    memory_usage: str = Field(
        "0M", description="Utilisation mémoire formatée (ex: 540M)"
    )
    memory_limit: Optional[str] = Field(
        None, description="Limite mémoire formatée (ex: 2G)"
    )
    uptime: Optional[str] = Field(None, description="Uptime formaté (ex: 'Up 2 hours')")
    ports: list[ContainerPortMapping] = Field(
        default_factory=list, description="Ports mappés"
    )
    health_status: Optional[str] = Field(
        None,
        description="Statut de santé (healthy, unhealthy, starting) si healthcheck configuré",
    )


class StandaloneContainer(BaseModel):
    """
    Container standalone — sans label compose ni WindFlow.

    Représente un container déployé individuellement, soit par WindFlow,
    soit manuellement hors de tout projet compose.
    """

    id: str = Field(..., description="Container ID")
    name: str = Field(..., description="Nom du container")
    image: str = Field(..., description="Image Docker utilisée")
    target_id: str = Field(..., description="ID de la target hébergeant ce container")
    target_name: str = Field(..., description="Nom de la target")
    status: str = Field(..., description="État du container (running, exited, etc.)")
    cpu_percent: float = Field(0.0, description="Utilisation CPU en %")
    memory_usage: str = Field("0M", description="Utilisation mémoire formatée")
    uptime: Optional[str] = Field(None, description="Uptime formaté (ex: 'Up 2 hours')")
    ports: list[ContainerPortMapping] = Field(
        default_factory=list, description="Ports mappés"
    )
    health_status: Optional[str] = Field(
        None,
        description="Statut de santé (healthy, unhealthy, starting) si healthcheck configuré",
    )


class DiscoveredItem(BaseModel):
    """
    Objet découvert — projet Docker Compose externe (sans label WindFlow).

    Détecté via le label com.docker.compose.project sur les containers.
    Non managé par WindFlow mais visible dans la vue Compute.
    """

    id: str = Field(
        ..., description="Identifiant unique (ex: compose:<project>@<target>)"
    )
    name: str = Field(
        ..., description="Nom du projet (valeur de com.docker.compose.project)"
    )
    type: Literal["container", "composition", "helm_release"] = Field(
        ..., description="Type d'objet découvert"
    )
    technology: str = Field(..., description="Technologie (docker-compose, helm, etc.)")
    source_path: Optional[str] = Field(
        None,
        description="Chemin du fichier de définition (com.docker.compose.project.config_files)",
    )
    target_id: str = Field(..., description="ID de la target hébergeant cet objet")
    target_name: str = Field(..., description="Nom de la target")
    services_total: int = Field(
        0, description="Nombre total de services dans le projet"
    )
    services_running: int = Field(0, description="Nombre de services en état running")
    detected_at: str = Field(..., description="Timestamp ISO de détection")
    adoptable: bool = Field(True, description="Peut être adopté dans WindFlow")
    services: list[ServiceWithMetrics] = Field(
        default_factory=list,
        description="Liste des containers détectés pour cet objet découvert",
    )


# =============================================================================
# Stacks managées
# =============================================================================


class StackWithServices(BaseModel):
    """
    Stack managée par WindFlow avec ses containers actifs.

    Les containers associés sont identifiés par le label windflow.managed=true
    et windflow.stack_id=<id>.
    """

    id: str = Field(..., description="ID de la stack WindFlow (DB)")
    name: str = Field(..., description="Nom de la stack")
    technology: str = Field("compose", description="Technologie de déploiement")
    target_id: str = Field(..., description="ID de la target principale")
    target_name: str = Field(..., description="Nom de la target principale")
    services_total: int = Field(..., description="Nombre total de services attendus")
    services_running: int = Field(
        ..., description="Nombre de services actuellement running"
    )
    status: Literal["running", "partial", "stopped", "archived"] = Field(
        ...,
        description=(
            "running=tous les services tournent, "
            "partial=certains seulement, "
            "stopped=aucun, "
            "archived=stack archivée"
        ),
    )
    services: list[ServiceWithMetrics] = Field(
        default_factory=list, description="Liste des containers actifs de cette stack"
    )


# =============================================================================
# Vues agrégées
# =============================================================================


class ComputeGlobalView(BaseModel):
    """
    Vue globale des ressources compute (groupe par stack/type).

    Retournée par GET /compute/global sans group_by=target.
    """

    managed_stacks: list[StackWithServices] = Field(
        default_factory=list, description="Stacks managées par WindFlow"
    )
    discovered_items: list[DiscoveredItem] = Field(
        default_factory=list,
        description="Projets Compose et autres objets découverts (non-WindFlow)",
    )
    standalone_containers: list[StandaloneContainer] = Field(
        default_factory=list,
        description="Containers individuels sans appartenance à un projet",
    )


class TargetMetrics(BaseModel):
    """Métriques agrégées d'une target."""

    cpu_total_percent: float = Field(
        0.0, description="CPU total utilisé sur la target (%)"
    )
    memory_used: str = Field("0M", description="Mémoire utilisée formatée")
    memory_total: str = Field("0M", description="Mémoire totale formatée")


class TargetGroup(BaseModel):
    """
    Vue groupée par target.

    Retournée par GET /compute/global?group_by=target.
    Regroupe toutes les ressources (stacks, discovered, standalone) par target.
    """

    target_id: str = Field(..., description="ID de la target")
    target_name: str = Field(..., description="Nom de la target")
    technology: str = Field("docker", description="Technologie principale de la target")
    stacks: list[StackWithServices] = Field(
        default_factory=list, description="Stacks managées sur cette target"
    )
    discovered: list[DiscoveredItem] = Field(
        default_factory=list, description="Objets découverts sur cette target"
    )
    standalone: list[StandaloneContainer] = Field(
        default_factory=list, description="Containers standalone sur cette target"
    )
    metrics: TargetMetrics = Field(
        default_factory=TargetMetrics,  # type: ignore[arg-type]
        description="Métriques agrégées de cette target",
    )


# =============================================================================
# Statistiques synthétiques
# =============================================================================


class ComputeStatsResponse(BaseModel):
    """
    Statistiques synthétiques de la vue Compute.

    Retournée par GET /compute/stats.
    Fournit les compteurs pour le bandeau supérieur de la vue globale.
    """

    total_containers: int = Field(
        ..., description="Nombre total de containers Docker (tous états)"
    )
    running_containers: int = Field(
        ..., description="Nombre de containers en état running"
    )
    stacks_count: int = Field(
        ..., description="Nombre de stacks managées par WindFlow (DB)"
    )
    stacks_running_count: int = Field(
        ..., description="Nombre de stacks avec tous leurs services en running"
    )
    stacks_targets_count: int = Field(
        ..., description="Nombre de machines distinctes hébergeant des stacks WindFlow"
    )
    stacks_services_count: int = Field(
        ..., description="Nombre total de services dans les stacks WindFlow actifs"
    )
    discovered_count: int = Field(
        ..., description="Nombre de projets Compose découverts (hors WindFlow)"
    )
    discovered_targets_count: int = Field(
        ...,
        description="Nombre de machines distinctes hébergeant des projets découverts",
    )
    standalone_count: int = Field(
        ..., description="Nombre de containers standalone (ni compose ni WindFlow)"
    )
    standalone_targets_count: int = Field(
        ...,
        description="Nombre de machines distinctes hébergeant des containers standalone",
    )
    targets_count: int = Field(
        ..., description="Nombre de targets enregistrées dans WindFlow"
    )


# =============================================================================
# Browse — inventaire aplati paginé (STORY-173)
# =============================================================================


class ComputeBrowseItem(BaseModel):
    """
    Item aplati de l'inventaire compute (GET /compute/browse — STORY-173).

    Aplatissement uniforme des trois sections de la vue globale : chaque
    service d'une stack managée, chaque objet découvert et chaque container
    standalone devient un item du même type, filtrable et paginé.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "app_nextcloud",
                "name": "nextcloud",
                "kind": "managed_service",
                "status": "running",
                "target_id": "local",
                "target_name": "Local Docker",
                "image": "nextcloud:29",
                "technology": "compose",
                "stack_id": "0e9d5f8a-1b2c-4d3e-9f8a-7c6b5a4f3e2d",
            }
        }
    )

    id: str = Field(..., description="Identifiant de l'item (container/projet)")
    name: str = Field(..., description="Nom lisible de l'item")
    kind: Literal["managed_service", "discovered", "standalone"] = Field(
        ...,
        description=(
            "managed_service = container d'une stack WindFlow, "
            "discovered = projet Compose externe, "
            "standalone = container individuel"
        ),
    )
    status: str = Field(..., description="État (running, exited, partial…)")
    target_id: str = Field(..., description="ID du host hébergeant l'item")
    target_name: str = Field(..., description="Nom du host hébergeant l'item")
    image: Optional[str] = Field(
        None, description="Image Docker (si applicable — absent pour un projet)"
    )
    technology: Optional[str] = Field(None, description="Technologie (compose, helm…)")
    stack_id: Optional[str] = Field(
        None, description="ID de la stack WindFlow (items managés uniquement)"
    )


# =============================================================================
# Volumes — sous-surface compute (STORY-173)
# =============================================================================


class ComputeVolumeResponse(BaseModel):
    """
    Volume Docker vu par la surface compute (GET /compute/volumes).

    Miroir du schéma ``VolumeResponse`` du router docker (mêmes champs) ;
    ``size`` volontairement absente — la taille d'un volume n'est pas
    exposée par le listage de l'API Engine (aucune valeur fabriquée).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "windflow_nextcloud_data",
                "driver": "local",
                "mountpoint": "/var/lib/docker/volumes/windflow_nextcloud_data",
                "created_at": "2026-10-31T12:00:00Z",
                "labels": {"com.docker.compose.project": "nextcloud"},
                "scope": "local",
            }
        }
    )

    name: str = Field(..., description="Nom du volume")
    driver: str = Field("local", description="Driver de stockage")
    mountpoint: str = Field(..., description="Point de montage")
    created_at: str = Field(..., description="Date de création (ISO)")
    labels: dict[str, str] = Field(default_factory=dict, description="Labels du volume")
    scope: str = Field("local", description="Scope (local/centered)")


class VolumeBrowseEntry(BaseModel):
    """
    Entrée du contenu d'un volume (GET /compute/volumes/{name}/browse).

    Produit par un listing ``ls -1p`` en conteneur éphémère read-only
    (STORY-173) : le suffixe ``/`` de la sortie ``ls -1p`` marque les
    dossiers.
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "data", "is_dir": True, "path": "data"}}
    )

    name: str = Field(..., description="Nom de l'entrée (fichier ou dossier)")
    is_dir: bool = Field(
        ..., description="True si l'entrée est un dossier (suffixe / de ls -1p)"
    )
    path: str = Field(
        ...,
        description=(
            "Chemin relatif de l'entrée au sein du volume "
            "(préfixé du sous-chemin demandé le cas échéant)"
        ),
    )


# =============================================================================
# Prune Docker protégé (STORY-173)
# =============================================================================


class ComputePruneRequest(BaseModel):
    """
    Requête de prune Docker protégé (POST /compute/prune — STORY-173).

    Sémantique sécurisée : ``dry_run`` par défaut (aucune suppression), et
    exécution réelle **seulement** si ``confirm=true`` — sans confirmation
    et sans dry-run explicite, l'endpoint répond 400 avec un message
    actionnable. ``extra="forbid"`` : tout champ inconnu est rejeté (422).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"resource": "volumes", "dry_run": True, "confirm": False}
        },
    )

    resource: Literal["images", "volumes", "containers"] = Field(
        ...,
        description=(
            "Ressource à nettoyer : images non utilisées (dangling), "
            "volumes orphelins, containers stoppés non managés WindFlow"
        ),
    )
    dry_run: bool = Field(
        default=False,
        description=(
            "Simulation : liste ce qui serait supprimé sans aucun appel "
            "suppressif (toujours autorisé, même sans confirm)"
        ),
    )
    confirm: bool = Field(
        default=False,
        description=(
            "Confirmation explicite requise pour une exécution réelle "
            "(sans confirm=true ni dry_run=true → 400)"
        ),
    )
    force: bool = Field(
        default=False,
        description=(
            "Contourner les confirmations de l'API Docker (n'affecte "
            "pas la liste protégée windflow-plugin-*)"
        ),
    )


class PruneItemFailure(BaseModel):
    """Échec de suppression d'un item du prune (file non interrompue)."""

    name: str = Field(..., description="Nom/ID de la ressource en échec")
    error: str = Field(..., description="Motif de l'échec (message borné)")


class ComputePruneResponse(BaseModel):
    """
    Rapport de prune protégé (POST /compute/prune — STORY-173).

    Liste explicite des supprimés / épargnés (protégés ``windflow-plugin-*``)
    / échecs — un échec d'item n'interrompt jamais la file.

    ``space_reclaimed_bytes`` : exact pour les images (somme des tailles) ;
    **toujours 0 pour les volumes** — l'API Docker n'expose pas la taille
    d'un volume dans le listage (aucune valeur fabriquée).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource": "volumes",
                "dry_run": True,
                "pruned": ["data-orphan"],
                "spared": ["windflow-plugin-trivy-cache"],
                "failed": [],
                "pruned_count": 1,
                "spared_count": 1,
                "failed_count": 0,
                "space_reclaimed_bytes": 0,
            }
        }
    )

    resource: str = Field(..., description="Ressource prunée")
    dry_run: bool = Field(..., description="True si simulation (rien de supprimé)")
    pruned: list[str] = Field(
        default_factory=list,
        description="Noms des ressources supprimées (ou candidates en dry-run)",
    )
    spared: list[str] = Field(
        default_factory=list,
        description="Noms des ressources protégées windflow-plugin-* épargnées",
    )
    failed: list[PruneItemFailure] = Field(
        default_factory=list,
        description="Échecs unitaires (la file continue après un échec)",
    )
    pruned_count: int = Field(..., description="Nombre d'éléments supprimés")
    spared_count: int = Field(..., description="Nombre d'éléments épargnés")
    failed_count: int = Field(..., description="Nombre d'échecs")
    space_reclaimed_bytes: int = Field(
        ...,
        description=(
            "Espace récupéré en octets — 0 pour les volumes (taille non "
            "exposée par l'API Docker, aucune valeur fabriquée)"
        ),
    )
