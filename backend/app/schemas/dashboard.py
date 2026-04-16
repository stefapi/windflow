"""
Schemas Pydantic V2 pour les statistiques du Dashboard.

Fournit les structures de données pour l'endpoint consolidé du dashboard.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TargetHealthItem(BaseModel):
    """Élément de santé d'une target."""

    id: str = Field(..., description="ID de la target")
    name: str = Field(..., description="Nom de la target")
    status: str = Field(..., description="Statut (online, offline, error, maintenance)")
    host: str = Field(..., description="Hôte de la target")
    last_check: Optional[datetime] = Field(None, description="Dernière vérification")

    model_config = ConfigDict(from_attributes=True)


class AlertItem(BaseModel):
    """Alerte ou notification du dashboard."""

    id: str = Field(..., description="ID de l'alerte")
    severity: Literal["critical", "warning", "info"] = Field(
        ..., description="Sévérité"
    )
    title: str = Field(..., description="Titre de l'alerte")
    message: str = Field(..., description="Message détaillé")
    source: str = Field(
        ..., description="Source de l'alerte (target, deployment, system)"
    )
    timestamp: datetime = Field(..., description="Date de l'alerte")
    acknowledged: bool = Field(False, description="Alerte acquittée")


class ActivityFeedItem(BaseModel):
    """Élément du flux d'activité récente."""

    id: str = Field(..., description="ID de l'événement source")
    type: str = Field(..., description="Type d'événement (deployment, scan, error)")
    title: str = Field(..., description="Titre de l'événement")
    status: str = Field(..., description="Statut de l'événement")
    timestamp: datetime = Field(..., description="Date de l'événement")
    details: Optional[str] = Field(None, description="Détails supplémentaires")


class ResourceCounter(BaseModel):
    """Compteur de ressources avec statut running/stopped."""

    total: int = Field(0, description="Nombre total de ressources")
    running: int = Field(0, description="Ressources en cours d'exécution")
    stopped: int = Field(0, description="Ressources arrêtées")


class DeploymentMetrics(BaseModel):
    """Métriques de performance des déploiements."""

    total: int = Field(0, description="Total des déploiements")
    success: int = Field(0, description="Déploiements réussis")
    failed: int = Field(0, description="Déploiements échoués")
    running: int = Field(0, description="Déploiements en cours")
    success_rate: float = Field(0.0, description="Taux de succès en pourcentage")


class ResourceMetricPoint(BaseModel):
    """Point de données pour les métriques de ressources."""

    timestamp: str = Field(..., description="Horodatage ISO")
    cpu: float = Field(0.0, description="Utilisation CPU en pourcentage")
    memory: float = Field(0.0, description="Utilisation mémoire en pourcentage")


class ResourceMetrics(BaseModel):
    """Métriques de ressources système (CPU/RAM/Disque/Uptime)."""

    current_cpu: float = Field(0.0, description="CPU actuel en pourcentage")
    current_memory: float = Field(0.0, description="Mémoire actuelle en pourcentage")
    total_memory_mb: float = Field(0.0, description="Mémoire totale en Mo")
    used_memory_mb: float = Field(0.0, description="Mémoire utilisée en Mo")
    current_disk: float = Field(0.0, description="Disque actuel en pourcentage")
    total_disk_gb: float = Field(0.0, description="Disque total en Go")
    used_disk_gb: float = Field(0.0, description="Disque utilisé en Go")
    uptime_seconds: int = Field(0, description="Uptime en secondes")
    history: List[ResourceMetricPoint] = Field(
        default_factory=list,
        description="Historique des métriques (dernières 60 minutes)",
    )


class DashboardStats(BaseModel):
    """Réponse consolidée pour le dashboard."""

    # Compteurs globaux (legacy - conservés pour compatibilité)
    total_targets: int = Field(0, description="Nombre total de targets")
    online_targets: int = Field(0, description="Targets en ligne")
    total_stacks: int = Field(0, description="Nombre total de stacks")
    active_deployments: int = Field(0, description="Déploiements actifs")
    total_workflows: int = Field(0, description="Nombre total de workflows")

    # Compteurs ressources par statut (STORY-432)
    containers: ResourceCounter = Field(
        default_factory=ResourceCounter,  # type: ignore[arg-type]
        description="Compteur de containers (running/stopped/total)",
    )
    vms: ResourceCounter = Field(
        default_factory=ResourceCounter,  # type: ignore[arg-type]
        description="Compteur de VMs (running/stopped/total)",
    )
    stacks: ResourceCounter = Field(
        default_factory=ResourceCounter,  # type: ignore[arg-type]
        description="Compteur de stacks (active/inactive/total)",
    )

    # Indicateur de disponibilité VMs
    vms_available: bool = Field(
        False, description="True si EPIC-002 livrée, False affiche 'Bientôt disponible'"
    )

    # Santé des targets
    target_health: Dict[str, int] = Field(
        default_factory=dict,
        description="Répartition des statuts targets (online, offline, error, maintenance)",
    )
    targets_detail: List[TargetHealthItem] = Field(
        default_factory=list, description="Détail de santé par target"
    )

    # Métriques déploiements
    deployment_metrics: DeploymentMetrics = Field(
        default_factory=DeploymentMetrics,  # type: ignore[arg-type]
        description="Métriques de performance des déploiements",
    )

    # Métriques ressources système
    resource_metrics: ResourceMetrics = Field(
        default_factory=ResourceMetrics,  # type: ignore[arg-type]
        description="Métriques CPU/RAM du système"
    )

    # Activité récente
    recent_activity: List[ActivityFeedItem] = Field(
        default_factory=list, description="Flux d'activité récente"
    )

    # Alertes et notifications
    alerts: List[AlertItem] = Field(
        default_factory=list, description="Alertes et notifications actives"
    )


class StackStatsResponse(BaseModel):
    """Statistiques détaillées d'une stack."""

    deployments_by_status: dict[str, int] = Field(
        ..., description="Nombre de déploiements par statut"
    )
    deployments_last_30_days: int = Field(
        ..., description="Nombre de déploiements sur les 30 derniers jours"
    )
