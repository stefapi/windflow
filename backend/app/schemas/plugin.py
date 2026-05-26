"""
Schemas Pydantic V2 pour l'entité Plugin — CRUD complet.

Validation stricte avec type hints obligatoires.
Séparation Request/Response pour chaque opération.
Masquage des champs password dans les réponses.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .plugin_manifest import ConfigFieldType

# ── Regex patterns ──────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(
    r"^https?://[^\s<>\"']+$",
    re.IGNORECASE,
)


# ── Request schemas ─────────────────────────────────────────────────────────


class PluginInstallRequest(BaseModel):
    """Schema pour l'installation d'un plugin.

    Au moins un de ``source`` ou ``manifest_yaml`` doit être fourni.
    """

    source: Optional[str] = Field(
        None,
        description="URL ou identifiant registre du plugin",
        json_schema_extra={"example": "https://registry.windflow.io/plugins/traefik/1.0.0"},
    )
    manifest_yaml: Optional[str] = Field(
        None,
        description="Contenu YAML direct du manifest pour installation locale",
        json_schema_extra={"example": "name: my-plugin\nversion: 1.0.0\n..."},
    )
    config_values: Dict[str, Any] = Field(
        default_factory=dict,
        description="Valeurs de configuration initiales",
        json_schema_extra={"example": {"port": 8080, "host": "localhost"}},
    )

    @model_validator(mode="after")
    def validate_source_or_manifest(self) -> "PluginInstallRequest":
        """Au moins un de source ou manifest_yaml doit être fourni."""
        if not self.source and not self.manifest_yaml:
            raise ValueError(
                "Au moins un de 'source' ou 'manifest_yaml' doit être fourni"
            )
        return self

    @model_validator(mode="after")
    def validate_source_url_format(self) -> "PluginInstallRequest":
        """Valide le format URL si source est fourni."""
        if self.source and self.source.startswith(("http://", "https://")):
            if not _URL_PATTERN.match(self.source):
                raise ValueError(f"URL source invalide : {self.source}")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "source": "https://registry.windflow.io/plugins/traefik/1.0.0",
                    "config_values": {"domain": "example.com"},
                }
            ]
        }
    )


class PluginUpdateRequest(BaseModel):
    """Schema pour la mise à jour d'un plugin."""

    version: Optional[str] = Field(
        None,
        max_length=50,
        description="Version cible (si None = dernière version disponible)",
        json_schema_extra={"example": "1.1.0"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"version": "1.1.0"},
                {},
            ]
        }
    )


class PluginConfigureRequest(BaseModel):
    """Schema pour la configuration d'un plugin."""

    config_values: Dict[str, Any] = Field(
        ...,
        description="Valeurs de configuration à appliquer",
        json_schema_extra={"example": {"port": 9090, "api_key": "secret"}},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"config_values": {"port": 9090, "host": "0.0.0.0"}},
            ]
        }
    )


# ── Response schemas ────────────────────────────────────────────────────────


class PluginSummaryResponse(BaseModel):
    """Schema de réponse allégé pour le listing des plugins."""

    id: str = Field(..., description="Identifiant unique du plugin")
    name: str = Field(..., description="Nom technique (kebab-case)")
    version: str = Field(..., description="Version du plugin (semver)")
    display_name: str = Field(..., description="Nom affiché dans l'UI")
    description: Optional[str] = Field(None, description="Description du plugin")
    category: str = Field(..., description="Catégorie du plugin")
    type: str = Field(..., description="Type de plugin")
    status: str = Field(..., description="Statut actuel du plugin")
    installed_at: datetime = Field(..., description="Date d'installation")
    updated_at: datetime = Field(..., description="Date de dernière mise à jour")

    model_config = ConfigDict(from_attributes=True)


class PluginResponse(PluginSummaryResponse):
    """Schema de réponse complet pour le détail d'un plugin.

    Inclut les données du manifest et la configuration utilisateur.
    Les champs de type password sont masqués dans config_values.
    """

    manifest_data: Dict[str, Any] = Field(
        ..., description="Manifest validé complet"
    )
    config_values: Dict[str, Any] = Field(
        default_factory=dict,
        description="Valeurs de configuration (champs password masqués)",
    )
    installed_by: Optional[str] = Field(
        None, description="ID de l'utilisateur ayant installé le plugin"
    )
    organization_id: str = Field(
        ..., description="ID de l'organisation propriétaire"
    )

    @model_validator(mode="after")
    def mask_password_fields(self) -> "PluginResponse":
        """Masque les valeurs des champs de type password dans config_values."""
        if not self.config_values or not self.manifest_data:
            return self

        config_fields = self.manifest_data.get("config", [])
        password_keys: set[str] = set()

        for field_def in config_fields:
            if isinstance(field_def, dict) and field_def.get("type") == ConfigFieldType.PASSWORD.value:
                key = field_def.get("key")
                if key:
                    password_keys.add(key)

        if password_keys:
            masked = dict(self.config_values)
            for key in password_keys:
                if key in masked:
                    masked[key] = "********"
            self.config_values = masked

        return self

    model_config = ConfigDict(from_attributes=True)


class PluginActionResponse(BaseModel):
    """Schema de réponse pour les actions asynchrones (install, update, uninstall)."""

    id: str = Field(..., description="Identifiant unique du plugin")
    status: str = Field(..., description="Statut actuel du plugin")
    message: str = Field(..., description="Message décrivant l'action en cours")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "status": "installing",
                    "message": "Plugin installation started",
                }
            ]
        },
    )
