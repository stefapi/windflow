"""
Schemas Pydantic V2 pour les statistiques du Dashboard.

Fournit les structures de données pour l'endpoint consolidé du dashboard.
"""

from datetime import datetime
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


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
    severity: Literal["critical", "warning", "info"] = Field(..., description="Sévérité")
    title: str = Field(..., description="Titre de l'alerte")
    message: str = Field(..., description="Message détaillé")
    source: str = Field(..., description="Source de l'alerte (target, deployment, system)")
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
        description="Historique des métriques (dernières 60 minutes)"
    )


class DashboardStats(BaseModel):
    """Réponse consolidée pour le dashboard."""

    # Compteurs globaux
    total_targets: int = Field(0, description="Nombre total de targets")
    online_targets: int = Field(0, description="Targets en ligne")
    total_stacks: int = Field(0, description="Nombre total de stacks")
    active_deployments: int = Field(0, description="Déploiements actifs")
    total_workflows: int = Field(0, description="Nombre total de workflows")

    # Santé des targets
    target_health: Dict[str, int] = Field(
        default_factory=dict,
        description="Répartition des statuts targets (online, offline, error, maintenance)"
    )
    targets_detail: List[TargetHealthItem] = Field(
        default_factory=list,
        description="Détail de santé par target"
    )

    # Métriques déploiements
    deployment_metrics: DeploymentMetrics = Field(
        default_factory=DeploymentMetrics,
        description="Métriques de performance des déploiements"
    )

    # Métriques ressources système
    resource_metrics: ResourceMetrics = Field(
        default_factory=ResourceMetrics,
        description="Métriques CPU/RAM du système"
    )

    # Activité récente
    recent_activity: List[ActivityFeedItem] = Field(
        default_factory=list,
        description="Flux d'activité récente"
    )

    # Alertes et notifications
    alerts: List[AlertItem] = Field(
        default_factory=list,
        description="Alertes et notifications actives"
    )
