"""
Schemas Pydantic V2 pour l'entité Stack.

Validation stricte avec type hints obligatoires selon backend.md.
Chaque modèle inclut model_config avec exemples et json_schema_extra
pour une documentation OpenAPI complète.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class StackBase(BaseModel):
    """Schema de base pour Stack."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nom du stack",
        json_schema_extra={"example": "Baserow"}
    )
    description: Optional[str] = Field(
        None,
        description="Description du stack",
        json_schema_extra={"example": "Open source no-code database platform"}
    )
    version: str = Field(
        default="1.0.0",
        max_length=50,
        description="Version du stack",
        json_schema_extra={"example": "1.0.0"}
    )
    category: Optional[str] = Field(
        None,
        max_length=100,
        description="Catégorie",
        json_schema_extra={"example": "database"}
    )
    icon_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL de l'icône",
        json_schema_extra={"example": "https://cdn.windflow.io/icons/baserow.svg"}
    )
    author: Optional[str] = Field(
        None,
        max_length=255,
        description="Auteur du stack",
        json_schema_extra={"example": "WindFlow Team"}
    )
    license: Optional[str] = Field(
        default="MIT",
        max_length=100,
        description="Licence",
        json_schema_extra={"example": "MIT"}
    )
    deployment_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Nom par défaut du déploiement (template)",
        json_schema_extra={"example": "baserow-{{timestamp}}"}
    )


class StackCreate(StackBase):
    """
    Schema pour création de stack.

    Définit les paramètres pour créer un nouveau stack Docker Compose.
    Le template doit être un objet JSON valide représentant
    la configuration Docker Compose.

    **Règles de validation:**
    - name: 1-255 caractères, obligatoire
    - template: Format Docker Compose valide en JSON
    - organization_id: Doit référencer une organisation existante
    - variables: Format clé/valeur simple
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Nginx Reverse Proxy",
                    "description": "Nginx reverse proxy with SSL termination",
                    "version": "1.0.0",
                    "category": "web",
                    "template": {
                        "version": "3.8",
                        "services": {
                            "nginx": {
                                "image": "nginx:latest",
                                "ports": ["80:80", "443:443"]
                            }
                        }
                    },
                    "variables": {
                        "port": {"type": "integer", "default": 80},
                        "domain": {"type": "string", "default": "localhost"}
                    },
                    "tags": ["web", "proxy", "nginx"],
                    "is_public": True,
                    "organization_id": "org-001"
                },
                {
                    "name": "PostgreSQL + pgAdmin",
                    "description": "PostgreSQL database with pgAdmin web interface",
                    "version": "16.0",
                    "category": "database",
                    "template": {
                        "version": "3.8",
                        "services": {
                            "postgres": {
                                "image": "postgres:16",
                                "environment": {
                                    "POSTGRES_PASSWORD": "${db_password}"
                                }
                            },
                            "pgadmin": {
                                "image": "dpage/pgadmin4",
                                "ports": ["5050:80"]
                            }
                        }
                    },
                    "variables": {
                        "db_password": {"type": "string", "required": True},
                        "pgadmin_port": {"type": "integer", "default": 5050}
                    },
                    "tags": ["database", "postgresql", "admin"],
                    "is_public": False,
                    "organization_id": "org-001"
                },
                {
                    "name": "Monitoring Stack",
                    "description": "Prometheus + Grafana monitoring",
                    "category": "monitoring",
                    "template": {
                        "version": "3.8",
                        "services": {
                            "prometheus": {"image": "prom/prometheus:latest"},
                            "grafana": {"image": "grafana/grafana:latest", "ports": ["3000:3000"]}
                        }
                    },
                    "tags": ["monitoring", "prometheus", "grafana"],
                    "organization_id": "org-001"
                }
            ]
        }
    )

    template: Dict[str, Any] = Field(
        ...,
        description="Template Docker Compose (format JSON)",
        json_schema_extra={"example": {"version": "3.8", "services": {"web": {"image": "nginx:latest"}}}}
    )
    variables: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Variables configurables (format simple)",
        json_schema_extra={"example": {"port": {"type": "integer", "default": 80}}}
    )
    tags: Optional[List[str]] = Field(
        default_factory=list,
        description="Tags de recherche",
        json_schema_extra={"example": ["web", "proxy"]}
    )
    is_public: bool = Field(
        default=False,
        description="Stack public dans marketplace",
        json_schema_extra={"example": False}
    )
    screenshots: Optional[List[str]] = Field(
        default_factory=list,
        description="URLs des screenshots",
        json_schema_extra={"example": ["https://cdn.windflow.io/screenshots/stack-1.png"]}
    )
    documentation_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL de la documentation",
        json_schema_extra={"example": "https://docs.windflow.io/stacks/nginx"}
    )
    organization_id: str = Field(
        ...,
        description="ID de l'organisation",
        json_schema_extra={"example": "org-001"}
    )


class StackUpdate(BaseModel):
    """
    Schema pour mise à jour de stack.

    Tous les champs sont optionnels. Seuls les champs fournis
    seront mis à jour.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Nginx Reverse Proxy v2",
                    "version": "2.0.0",
                    "tags": ["web", "proxy", "nginx", "ssl"]
                },
                {
                    "is_public": True,
                    "description": "Updated description with more details"
                },
                {
                    "template": {
                        "version": "3.8",
                        "services": {
                            "nginx": {"image": "nginx:1.25", "ports": ["80:80"]}
                        }
                    },
                    "variables": {"port": {"type": "integer", "default": 8080}}
                }
            ]
        }
    )

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Nouveau nom",
        json_schema_extra={"example": "Nginx Reverse Proxy v2"}
    )
    description: Optional[str] = Field(
        None,
        description="Nouvelle description",
        json_schema_extra={"example": "Updated stack with SSL support"}
    )
    template: Optional[Dict[str, Any]] = Field(
        None,
        description="Nouveau template",
        json_schema_extra={"example": {"version": "3.8", "services": {}}}
    )
    variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Nouvelles variables",
        json_schema_extra={"example": {"port": {"type": "integer", "default": 8080}}}
    )
    version: Optional[str] = Field(
        None,
        max_length=50,
        description="Nouvelle version",
        json_schema_extra={"example": "2.0.0"}
    )
    category: Optional[str] = Field(
        None,
        max_length=100,
        description="Nouvelle catégorie",
        json_schema_extra={"example": "web"}
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Nouveaux tags",
        json_schema_extra={"example": ["web", "proxy"]}
    )
    is_public: Optional[bool] = Field(
        None,
        description="Statut public",
        json_schema_extra={"example": True}
    )
    deployment_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Nouveau nom par défaut du déploiement",
        json_schema_extra={"example": "nginx-{{timestamp}}"}
    )


class StackResponse(StackBase):
    """
    Schema pour réponse Stack.

    Retourné après création réussie ou lors de la consultation
    d'un stack. Inclut toutes les métadonnées, les statistiques
    de téléchargement et la note moyenne.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "stack-550e8400",
                "name": "Nginx Reverse Proxy",
                "description": "Nginx reverse proxy with SSL termination",
                "version": "1.0.0",
                "category": "web",
                "template": {"version": "3.8", "services": {"nginx": {"image": "nginx:latest"}}},
                "variables": {"port": {"type": "integer", "default": 80}},
                "tags": ["web", "proxy", "nginx"],
                "is_public": True,
                "downloads": 1250,
                "rating": 4.5,
                "screenshots": ["https://cdn.windflow.io/screenshots/nginx-1.png"],
                "documentation_url": "https://docs.windflow.io/stacks/nginx",
                "organization_id": "org-001",
                "created_at": "2026-01-02T10:00:00Z",
                "updated_at": "2026-01-02T12:00:00Z",
                "default_name": "nginx-proxy-20260102"
            }
        }
    )

    id: str = Field(
        ...,
        description="ID unique du stack",
        json_schema_extra={"example": "stack-550e8400"}
    )
    template: Dict[str, Any] = Field(
        ...,
        description="Template Docker Compose",
        json_schema_extra={"example": {"version": "3.8", "services": {}}}
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Variables configurables",
        json_schema_extra={"example": {"port": {"type": "integer", "default": 80}}}
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags",
        json_schema_extra={"example": ["web", "proxy"]}
    )
    is_public: bool = Field(
        ...,
        description="Stack public",
        json_schema_extra={"example": True}
    )
    downloads: int = Field(
        default=0,
        description="Nombre de téléchargements",
        json_schema_extra={"example": 1250}
    )
    rating: float = Field(
        default=0.0,
        description="Note moyenne",
        json_schema_extra={"example": 4.5}
    )
    screenshots: List[str] = Field(
        default_factory=list,
        description="Screenshots",
        json_schema_extra={"example": []}
    )
    documentation_url: Optional[str] = Field(
        None,
        description="URL documentation",
        json_schema_extra={"example": "https://docs.windflow.io/stacks/nginx"}
    )
    organization_id: str = Field(
        ...,
        description="ID de l'organisation",
        json_schema_extra={"example": "org-001"}
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-01-02T10:00:00Z"}
    )
    updated_at: datetime = Field(
        ...,
        description="Date de mise à jour",
        json_schema_extra={"example": "2026-01-02T12:00:00Z"}
    )
    default_name: Optional[str] = Field(
        None,
        description="Nom par défaut généré pour le déploiement",
        json_schema_extra={"example": "nginx-proxy-20260102"}
    )


class MarketplaceStackResponse(BaseModel):
    """
    Schema pour réponse Stack marketplace (sans template complet).

    Version allégée de StackResponse pour les listings du marketplace,
    ne contient pas le template complet pour des raisons de performance.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "stack-550e8400",
                "name": "Nginx Reverse Proxy",
                "description": "Nginx reverse proxy with SSL termination",
                "version": "1.0.0",
                "category": "web",
                "tags": ["web", "proxy", "nginx"],
                "icon_url": "https://cdn.windflow.io/icons/nginx.svg",
                "screenshots": [],
                "author": "WindFlow Team",
                "license": "MIT",
                "downloads": 1250,
                "rating": 4.5,
                "created_at": "2026-01-02T10:00:00Z",
                "updated_at": "2026-01-02T12:00:00Z"
            }
        }
    )

    id: str = Field(
        ...,
        description="ID unique du stack",
        json_schema_extra={"example": "stack-550e8400"}
    )
    name: str = Field(
        ...,
        description="Nom du stack",
        json_schema_extra={"example": "Nginx Reverse Proxy"}
    )
    description: Optional[str] = Field(
        None,
        description="Description",
        json_schema_extra={"example": "Nginx reverse proxy with SSL termination"}
    )
    version: str = Field(
        ...,
        description="Version",
        json_schema_extra={"example": "1.0.0"}
    )
    category: Optional[str] = Field(
        None,
        description="Catégorie",
        json_schema_extra={"example": "web"}
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags",
        json_schema_extra={"example": ["web", "proxy"]}
    )
    icon_url: Optional[str] = Field(
        None,
        description="URL icône",
        json_schema_extra={"example": "https://cdn.windflow.io/icons/nginx.svg"}
    )
    screenshots: List[str] = Field(
        default_factory=list,
        description="Screenshots",
        json_schema_extra={"example": []}
    )
    author: Optional[str] = Field(
        None,
        description="Auteur",
        json_schema_extra={"example": "WindFlow Team"}
    )
    license: Optional[str] = Field(
        None,
        description="Licence",
        json_schema_extra={"example": "MIT"}
    )
    downloads: int = Field(
        default=0,
        description="Téléchargements",
        json_schema_extra={"example": 1250}
    )
    rating: float = Field(
        default=0.0,
        description="Note",
        json_schema_extra={"example": 4.5}
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-01-02T10:00:00Z"}
    )
    updated_at: datetime = Field(
        ...,
        description="Date de mise à jour",
        json_schema_extra={"example": "2026-01-02T12:00:00Z"}
    )


class DeploymentConfigRequest(BaseModel):
    """Schema pour configuration de déploiement."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stack_id": "uuid-baserow",
            "target_id": "target-docker-local",
            "configuration": {
                "baserow_version": "1.26.1",
                "db_password": "secure_password_123",
                "domain": "baserow.localhost",
                "workers": 2
            }
        }
    })

    stack_id: str = Field(
        ...,
        description="ID du stack à déployer",
        json_schema_extra={"example": "uuid-baserow"}
    )
    target_id: str = Field(
        ...,
        description="ID de la cible de déploiement",
        json_schema_extra={"example": "target-docker-local"}
    )
    configuration: Dict[str, Any] = Field(
        ...,
        description="Configuration des variables",
        json_schema_extra={"example": {"baserow_version": "1.26.1", "db_password": "secure_password_123"}}
    )
    name: Optional[str] = Field(
        None,
        description="Nom du déploiement (optionnel)",
        json_schema_extra={"example": "baserow-production"}
    )
