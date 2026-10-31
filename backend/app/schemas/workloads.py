"""Schémas Pydantic du contrat WorkloadAdapter (spec 02 — STORY-174.1).

Types de retour du contrat commun (chapitre 02 § Interface WorkloadAdapter
et § Hiérarchie des adapters App) : métriques unifiées, santé, actions
contextuelles, configuration native (Mode Infra), composants techniques
et composants applicatifs. Les adapters Docker (STORY-174.1) produisent
ces types en enveloppant les exécuteurs existants ; les adapters
K8s/Helm/VM suivront (Roadmap — arbitrage F7).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Métriques et santé (universel — spec 02 § Interface WorkloadAdapter)
# =============================================================================


class WorkloadMetrics(BaseModel):
    """Métriques ressources unifiées d'un workload (CPU, RAM, réseau)."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "cpu_percent": 12.5,
                "memory_used": 540000000,
                "memory_limit": 1073741824,
                "network_rx": 1024000,
                "network_tx": 512000,
            }
        }
    }

    cpu_percent: float = Field(..., ge=0, description="Utilisation CPU en %")
    memory_used: int = Field(..., ge=0, description="Mémoire utilisée (octets)")
    memory_limit: int = Field(..., ge=0, description="Limite mémoire (octets)")
    network_rx: int = Field(0, ge=0, description="Réseau reçu (octets, cumul)")
    network_tx: int = Field(0, ge=0, description="Réseau émis (octets, cumul)")


class HealthStatus(BaseModel):
    """État de santé d'un workload (dérivé du healthcheck / statut runtime)."""

    model_config = {
        "json_schema_extra": {"example": {"status": "healthy", "detail": "Up 2 hours"}}
    }

    status: Literal["healthy", "unhealthy", "starting", "unknown"] = Field(
        ..., description="État de santé agrégé"
    )
    detail: Optional[str] = Field(
        None, description="Détail lisible (uptime, dernière erreur…)"
    )


# =============================================================================
# ContextualActions (spec 02 § Catalogue par profil)
# =============================================================================


class ContextualAction(BaseModel):
    """Action contextuelle offerte par l'action bar / menu d'un workload.

    Déclarative dans cette story (catalogues statiques par profil — la
    surface REST d'exécution ``POST /apps/{id}/actions/…`` est Roadmap).
    """

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "force_restart",
                "label": "Force restart",
                "section": "lifecycle",
                "danger": False,
            }
        }
    }

    id: str = Field(..., description="Identifiant machine de l'action")
    label: str = Field(..., description="Libellé affiché")
    section: str = Field(
        ...,
        description=(
            "Section du menu (lifecycle, configuration, data, advanced, " "danger)"
        ),
    )
    danger: bool = Field(
        default=False, description="Action destructive (confirmation requise côté UI)"
    )


# =============================================================================
# Mode Infra (spec 02 § Mode Infra ciblé)
# =============================================================================


class NativeConfig(BaseModel):
    """Configuration native d'un workload telle que vue par le moteur.

    Mode Infra : compose YAML pour une stack, inspection JSON pour un
    container, XML libvirt pour une VM (Roadmap)…
    """

    model_config = {
        "json_schema_extra": {
            "example": {
                "format": "json",
                "content": '{"Id": "abc123", "State": {"Running": true}}',
            }
        }
    }

    format: Literal["compose", "json", "xml", "yaml"] = Field(
        ..., description="Format de la configuration native"
    )
    content: str = Field(..., description="Contenu brut (masqué si secrets)")


class TechnicalComponent(BaseModel):
    """Composant technique d'un workload révélé en Mode Infra."""

    model_config = {
        "json_schema_extra": {
            "example": {"kind": "container", "name": "app-web-1", "status": "running"}
        }
    }

    kind: str = Field(..., description="Type de composant (container, service, pod…)")
    name: str = Field(..., description="Nom du composant")
    status: Optional[str] = Field(None, description="État du composant")


# =============================================================================
# Famille Apps — spécialisation AppAdapter (spec 02 § Hiérarchie adapters App)
# =============================================================================


class AppComponent(BaseModel):
    """Composant applicatif interne d'une App (service Compose, pod…)."""

    model_config = {
        "json_schema_extra": {
            "example": {"name": "web", "status": "running", "image": "nginx:1.27"}
        }
    }

    name: str = Field(..., description="Nom du service/pod/container")
    status: str = Field(..., description="État (running, exited…)")
    image: Optional[str] = Field(None, description="Image du composant")


class AppOpenUrl(BaseModel):
    """URL d'ouverture d'une App (port exposé mappé, le cas échéant)."""

    model_config = {"json_schema_extra": {"example": {"url": "http://localhost:8080"}}}

    url: Optional[str] = Field(
        None, description="URL d'accès public (null si aucun port exposé)"
    )
