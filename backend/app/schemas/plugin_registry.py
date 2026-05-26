"""
Schémas Pydantic pour le registre officiel de plugins WindFlow.

Validation stricte de l'index JSON du registre et des réponses API.
Chaque entrée du registre décrit un plugin officiel avec ses métadonnées,
son URL de téléchargement et son checksum SHA-256.
"""

import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .plugin_manifest import Architecture, PluginCategory, PluginType

# ── Regex patterns ──────────────────────────────────────────────────────────

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_CHECKSUM_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_HTTPS_URL_PATTERN = re.compile(r"^https://[^\s<>\"']+$")


# ── Modèles de l'index JSON ─────────────────────────────────────────────────


class RegistryPluginEntry(BaseModel):
    """Entrée individuelle du registre officiel.

    Représente un plugin disponible dans l'index JSON du registre.
    La validation est stricte sur tous les champs.
    """

    name: str = Field(..., description="Identifiant unique (kebab-case)")
    version: str = Field(..., description="Version (format semver)")
    display_name: str = Field(..., description="Nom affiché dans l'UI")
    description: str = Field(..., description="Description courte du plugin")
    category: PluginCategory = Field(..., description="Catégorie marketplace")
    type: PluginType = Field(..., description="Type de plugin")
    author: str = Field(..., description="Auteur du plugin")
    license: str = Field(..., description="Licence du plugin")
    architectures: List[Architecture] = Field(
        ..., min_length=1, description="Architectures supportées"
    )
    download_url: str = Field(..., description="URL de téléchargement (HTTPS uniquement)")
    checksum_sha256: str = Field(
        ..., description="Checksum SHA-256 du package (hex 64 caractères)"
    )
    homepage: Optional[str] = Field(None, description="URL du site principal")
    tags: List[str] = Field(default_factory=list, description="Tags de recherche")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Valide que le nom est en kebab-case (sécurité : anti path traversal)."""
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Le nom du plugin doit être en kebab-case : "
                "lettres minuscules, chiffres et tirets, "
                "commençant par une lettre minuscule ou un chiffre"
            )
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Valide le format semver de la version."""
        if not _SEMVER_PATTERN.match(v):
            raise ValueError(
                "La version doit être au format semver (ex: 1.0.0, 1.2.3-alpha.1)"
            )
        return v

    @field_validator("download_url")
    @classmethod
    def validate_download_url(cls, v: str) -> str:
        """Valide que l'URL de téléchargement est en HTTPS."""
        if not _HTTPS_URL_PATTERN.match(v):
            raise ValueError(
                "L'URL de téléchargement doit être une URL HTTPS valide"
            )
        return v

    @field_validator("checksum_sha256")
    @classmethod
    def validate_checksum(cls, v: str) -> str:
        """Valide le format du checksum SHA-256 (hex 64 caractères)."""
        if not _CHECKSUM_SHA256_PATTERN.match(v):
            raise ValueError(
                "Le checksum SHA-256 doit être une chaîne hexadécimale de 64 caractères"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "traefik",
                    "version": "1.2.0",
                    "display_name": "Traefik",
                    "description": "Reverse proxy avec TLS automatique",
                    "category": "access",
                    "type": "hybrid",
                    "author": "WindFlow Team",
                    "license": "MIT",
                    "architectures": ["linux/amd64", "linux/arm64"],
                    "download_url": "https://registry.windflow.io/plugins/traefik/1.2.0/package.tar.gz",
                    "checksum_sha256": "a" * 64,
                    "homepage": "https://github.com/windflow/plugin-traefik",
                    "tags": ["reverse-proxy", "tls", "proxy"],
                }
            ]
        }
    )


class RegistryIndex(BaseModel):
    """Index complet du registre officiel.

    Représente le fichier index.json servi par le registre officiel.
    Contient la liste de tous les plugins officiels disponibles.
    """

    version: str = Field(..., description="Version du format d'index")
    updated_at: str = Field(..., description="Date de dernière mise à jour (ISO 8601)")
    registry_url: str = Field(..., description="URL du registre officiel")
    plugins: List[RegistryPluginEntry] = Field(
        default_factory=list, description="Liste des plugins disponibles"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "version": "1.0",
                    "updated_at": "2026-05-26T00:00:00Z",
                    "registry_url": "https://registry.windflow.io",
                    "plugins": [],
                }
            ]
        }
    )


# ── Schémas de réponse API ──────────────────────────────────────────────────


class RegistryPluginSummaryResponse(BaseModel):
    """Schéma de réponse allégé pour le listing des plugins du registre."""

    name: str = Field(..., description="Identifiant unique (kebab-case)")
    version: str = Field(..., description="Version du plugin (semver)")
    display_name: str = Field(..., description="Nom affiché dans l'UI")
    description: str = Field(..., description="Description courte du plugin")
    category: str = Field(..., description="Catégorie du plugin")
    tags: List[str] = Field(default_factory=list, description="Tags de recherche")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "traefik",
                    "version": "1.2.0",
                    "display_name": "Traefik",
                    "description": "Reverse proxy avec TLS automatique",
                    "category": "access",
                    "tags": ["reverse-proxy", "tls"],
                }
            ]
        }
    )


class RegistryPluginDetailResponse(BaseModel):
    """Schéma de réponse complet pour le détail d'un plugin du registre.

    Inclut tous les champs de l'entrée du registre, y compris
    le checksum SHA-256 et l'URL de téléchargement.
    """

    name: str = Field(..., description="Identifiant unique (kebab-case)")
    version: str = Field(..., description="Version du plugin (semver)")
    display_name: str = Field(..., description="Nom affiché dans l'UI")
    description: str = Field(..., description="Description courte du plugin")
    category: str = Field(..., description="Catégorie du plugin")
    type: str = Field(..., description="Type de plugin")
    author: str = Field(..., description="Auteur du plugin")
    license: str = Field(..., description="Licence du plugin")
    architectures: List[str] = Field(
        ..., description="Architectures supportées"
    )
    download_url: str = Field(..., description="URL de téléchargement (HTTPS)")
    checksum_sha256: str = Field(
        ..., description="Checksum SHA-256 du package"
    )
    homepage: Optional[str] = Field(None, description="URL du site principal")
    tags: List[str] = Field(default_factory=list, description="Tags de recherche")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "traefik",
                    "version": "1.2.0",
                    "display_name": "Traefik",
                    "description": "Reverse proxy avec TLS automatique",
                    "category": "access",
                    "type": "hybrid",
                    "author": "WindFlow Team",
                    "license": "MIT",
                    "architectures": ["linux/amd64", "linux/arm64"],
                    "download_url": "https://registry.windflow.io/plugins/traefik/1.2.0/package.tar.gz",
                    "checksum_sha256": "a" * 64,
                    "homepage": "https://github.com/windflow/plugin-traefik",
                    "tags": ["reverse-proxy", "tls"],
                }
            ]
        }
    )
