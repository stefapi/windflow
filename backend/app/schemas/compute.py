"""
Schémas Pydantic pour l'API Compute.

Ces schémas représentent la vue agrégée des ressources compute :
- Stacks managées par WindFlow (label windflow.managed=true)
- Objets découverts (containers compose externes sans label WindFlow)
- Containers standalone (sans label compose ni WindFlow)
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Primitives — Services et containers
# =============================================================================


class ServiceWithMetrics(BaseModel):
    """Un service (container) appartenant à une stack managée."""

    id: str = Field(..., description="Container ID (12 premiers caractères)")
    name: str = Field(..., description="Nom du container/service")
    image: str = Field(..., description="Image Docker utilisée")
    status: str = Field(..., description="État du container (running, exited, etc.)")
    cpu_percent: float = Field(0.0, description="Utilisation CPU en %")
    memory_usage: str = Field("0M", description="Utilisation mémoire formatée (ex: 540M)")
    memory_limit: Optional[str] = Field(None, description="Limite mémoire formatée (ex: 2G)")


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


class DiscoveredItem(BaseModel):
    """
    Objet découvert — projet Docker Compose externe (sans label WindFlow).

    Détecté via le label com.docker.compose.project sur les containers.
    Non managé par WindFlow mais visible dans la vue Compute.
    """

    id: str = Field(..., description="Identifiant unique (ex: compose:<project>@<target>)")
    name: str = Field(..., description="Nom du projet (valeur de com.docker.compose.project)")
    type: Literal["container", "composition", "helm_release"] = Field(
        ..., description="Type d'objet découvert"
    )
    technology: str = Field(..., description="Technologie (docker-compose, helm, etc.)")
    source_path: Optional[str] = Field(
        None, description="Chemin du fichier de définition (com.docker.compose.project.config_files)"
    )
    target_id: str = Field(..., description="ID de la target hébergeant cet objet")
    target_name: str = Field(..., description="Nom de la target")
    services_total: int = Field(0, description="Nombre total de services dans le projet")
    services_running: int = Field(0, description="Nombre de services en état running")
    detected_at: str = Field(..., description="Timestamp ISO de détection")
    adoptable: bool = Field(True, description="Peut être adopté dans WindFlow")


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
    services_running: int = Field(..., description="Nombre de services actuellement running")
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
        default_factory=list, description="Projets Compose et autres objets découverts (non-WindFlow)"
    )
    standalone_containers: list[StandaloneContainer] = Field(
        default_factory=list, description="Containers individuels sans appartenance à un projet"
    )


class TargetMetrics(BaseModel):
    """Métriques agrégées d'une target."""

    cpu_total_percent: float = Field(0.0, description="CPU total utilisé sur la target (%)")
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
        default_factory=TargetMetrics, description="Métriques agrégées de cette target"
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

    total_containers: int = Field(..., description="Nombre total de containers Docker (tous états)")
    running_containers: int = Field(..., description="Nombre de containers en état running")
    stacks_count: int = Field(..., description="Nombre de stacks managées par WindFlow (DB)")
    stacks_services_count: int = Field(
        ..., description="Nombre total de services dans les stacks WindFlow actifs"
    )
    discovered_count: int = Field(
        ..., description="Nombre de projets Compose découverts (hors WindFlow)"
    )
    standalone_count: int = Field(
        ..., description="Nombre de containers standalone (ni compose ni WindFlow)"
    )
    targets_count: int = Field(..., description="Nombre de targets enregistrées dans WindFlow")
