"""
Schémas Pydantic pour l'adoption d'objets découverts.

Utilisés par les endpoints GET /discovery/{type}/{id}/adoption-data
et POST /discovery/adopt pour le wizard d'adoption en 3 étapes.
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Primitives — Données détectées d'un container
# =============================================================================


class AdoptionEnvVar(BaseModel):
    """Variable d'environnement détectée dans un container."""

    key: str = Field(..., description="Nom de la variable d'environnement")
    value: str = Field(..., description="Valeur de la variable")
    is_secret: bool = Field(
        False,
        description="True si la valeur semble être un secret (PASSWORD, TOKEN, KEY…)",
    )


class AdoptionVolume(BaseModel):
    """Volume monté détecté dans un container."""

    source: Optional[str] = Field(
        None, description="Chemin hôte ou nom de volume Docker"
    )
    destination: str = Field(..., description="Chemin de montage dans le container")
    mode: str = Field("rw", description="Mode d'accès (rw ou ro)")
    type: str = Field("bind", description="Type de montage (bind ou volume)")


class AdoptionNetwork(BaseModel):
    """Réseau auquel le container est connecté."""

    name: str = Field(..., description="Nom du réseau Docker")
    driver: str = Field("bridge", description="Driver du réseau (bridge, overlay…)")
    is_default: bool = Field(False, description="True si c'est le réseau par défaut")


class AdoptionPortMapping(BaseModel):
    """Mapping de port détecté."""

    host_ip: str = Field("0.0.0.0", description="IP hôte")
    host_port: int = Field(..., description="Port hôte")
    container_port: int = Field(..., description="Port container")
    protocol: str = Field("tcp", description="Protocole (tcp/udp)")


# =============================================================================
# Données d'un service (container) pour le wizard
# =============================================================================


class AdoptionServiceData(BaseModel):
    """Données détaillées d'un service pour le wizard d'adoption."""

    name: str = Field(..., description="Nom du container/service")
    image: str = Field(..., description="Image Docker utilisée")
    status: str = Field(..., description="État du container (running, exited…)")
    env_vars: list[AdoptionEnvVar] = Field(
        default_factory=list, description="Variables d'environnement détectées"
    )
    volumes: list[AdoptionVolume] = Field(
        default_factory=list, description="Volumes montés détectés"
    )
    networks: list[AdoptionNetwork] = Field(
        default_factory=list, description="Réseaux connectés"
    )
    ports: list[AdoptionPortMapping] = Field(
        default_factory=list, description="Ports mappés"
    )
    cpu_percent: float = Field(0.0, description="Utilisation CPU en %")
    memory_usage: str = Field("0M", description="Utilisation mémoire formatée")


# =============================================================================
# Réponse du wizard — GET adoption-data
# =============================================================================


class AdoptionWizardData(BaseModel):
    """
    Données complètes pour le wizard d'adoption.

    Retournée par GET /discovery/{type}/{id}/adoption-data.
    Contient l'inventaire des services, un aperçu Compose généré,
    et les options de stratégie disponibles.
    """

    discovered_id: str = Field(
        ..., description="ID de l'objet découvert (ex: compose:myproject@local)"
    )
    name: str = Field(..., description="Nom du projet ou du container")
    type: Literal["container", "composition", "helm_release"] = Field(
        ..., description="Type d'objet découvert"
    )
    technology: str = Field(..., description="Technologie (docker-compose, helm…)")
    target_id: str = Field(..., description="ID de la target hébergeant l'objet")
    target_name: str = Field(..., description="Nom de la target")
    services: list[AdoptionServiceData] = Field(
        default_factory=list, description="Liste des services détectés"
    )
    generated_compose: Optional[str] = Field(
        None, description="Aperçu docker-compose.yml généré automatiquement"
    )
    volumes_strategy_options: list[str] = Field(
        default_factory=lambda: ["keep_existing", "create_named", "bind_mount"],
        description="Options de stratégie pour les volumes",
    )
    networks_strategy_options: list[str] = Field(
        default_factory=lambda: ["keep_existing", "create_new"],
        description="Options de stratégie pour les réseaux",
    )


# =============================================================================
# Stratégies d'adoption
# =============================================================================


class VolumeStrategy(str, Enum):
    """Stratégie de gestion des volumes lors de l'adoption."""

    KEEP_EXISTING = "keep_existing"
    CREATE_NAMED = "create_named"
    BIND_MOUNT = "bind_mount"


class NetworkStrategy(str, Enum):
    """Stratégie de gestion des réseaux lors de l'adoption."""

    KEEP_EXISTING = "keep_existing"
    CREATE_NEW = "create_new"


# =============================================================================
# Options Helm (uniquement si type=helm_release)
# =============================================================================


class HelmOptions(BaseModel):
    """Options spécifiques à Helm (uniquement si type=helm_release)."""

    namespace: str = Field("default", description="Namespace Kubernetes cible")
    release_name: str = Field("", description="Nom de la release Helm")
    values_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Surcharge des values Helm (clé=valeur)",
    )


# =============================================================================
# Requête d'adoption — POST /discovery/adopt
# =============================================================================


class AdoptionRequest(BaseModel):
    """
    Requête d'adoption d'un objet découvert.

    Envoyée par le wizard à l'étape 3 (confirmation).
    """

    discovered_id: str = Field(
        ...,
        description="ID de l'objet découvert (ex: compose:myproject@local)",
    )
    item_type: Literal["container", "composition", "helm_release"] = Field(
        ..., alias="type", description="Type de l'objet à adopter"
    )
    stack_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom de la future stack WindFlow",
    )
    volume_strategy: VolumeStrategy = Field(
        VolumeStrategy.KEEP_EXISTING,
        description="Stratégie de gestion des volumes",
    )
    network_strategy: NetworkStrategy = Field(
        NetworkStrategy.KEEP_EXISTING,
        description="Stratégie de gestion des réseaux",
    )
    target_id: Optional[str] = Field(
        None, description="Target ID (si différent de la target détectée)"
    )
    helm_options: Optional[HelmOptions] = Field(
        None, description="Options Helm (si type=helm_release)"
    )
    compose_content: Optional[str] = Field(
        None,
        description="Contenu docker-compose.yml généré/modifié par l'utilisateur",
    )

    model_config = {"populate_by_name": True}


# =============================================================================
# Réponse d'adoption — POST /discovery/adopt
# =============================================================================


class AdoptionResponse(BaseModel):
    """
    Réponse après une adoption réussie ou échouée.

    Retournée par POST /discovery/adopt.
    """

    success: bool = Field(..., description="True si l'adoption a réussi")
    stack_id: Optional[str] = Field(
        None, description="ID de la stack créée (si succès)"
    )
    stack_name: Optional[str] = Field(
        None, description="Nom de la stack créée (si succès)"
    )
    deployment_id: Optional[str] = Field(
        None, description="ID du déploiement créé (si succès)"
    )
    message: str = Field(..., description="Message de confirmation ou d'erreur")
