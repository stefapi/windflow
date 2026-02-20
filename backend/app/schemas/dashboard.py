"""
Schemas Pydantic V2 pour les statistiques du Dashboard.

Fournit les structures de données pour l'endpoint consolidé du dashboard.
"""

from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class TargetHealthItem(BaseModel):
    """Élément de santé d'une target."""

    id: str = Field(..., description="ID de la target")
    name: str = Field(..., description="Nom de la target")
    status: str = Field(..., description="Statut (online, offline, error, maintenance)")
    host: str = Field(..., description="Hôte de la target")
    last_check: Optional[datetime] = Field(None, description="Dernière vérification")

    model_config = ConfigDict(from_attributes=True)


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

    # Activité récente
    recent_activity: List[ActivityFeedItem] = Field(
        default_factory=list,
        description="Flux d'activité récente"
    )
