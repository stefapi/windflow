"""
Schémas Pydantic pour les manifests de plugins WindFlow.

Validation stricte de la structure des fichiers windflow-plugin.yml.
Chaque plugin déclare ses métadonnées, dépendances, ressources et configuration
via ce manifest standardisé.
"""

import os
import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

# ── Regex patterns ──────────────────────────────────────────────────────────

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_VERSION_CONSTRAINT_PATTERN = re.compile(r"^(>=|<=|>|<|==|!=|~=)\s*\d+(\.\d+){0,2}.*$")


# ── Enums ───────────────────────────────────────────────────────────────────


class PluginType(str, Enum):
    """Types de plugins supportés."""

    SERVICE = "service"
    EXTENSION = "extension"
    HYBRID = "hybrid"


class PluginCategory(str, Enum):
    """Catégories de plugins pour la marketplace."""

    ACCESS = "access"
    DNS = "dns"
    DATABASE = "database"
    MONITORING = "monitoring"
    SECURITY = "security"
    BACKUP = "backup"
    MAIL = "mail"
    MESSAGING = "messaging"
    STORAGE = "storage"
    GIT = "git"
    WORKFLOW = "workflow"
    AI = "ai"
    WEB = "web"
    COLLABORATION = "collaboration"
    ANALYTICS = "analytics"
    OTHER = "other"


class ConfigFieldType(str, Enum):
    """Types de champs de configuration pour formulaires dynamiques."""

    STRING = "string"
    PASSWORD = "password"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    SELECT = "select"
    MULTILINE = "multiline"


class PortProtocol(str, Enum):
    """Protocoles réseau supportés pour les ports."""

    TCP = "tcp"
    UDP = "udp"


class Architecture(str, Enum):
    """Architectures matérielles supportées."""

    LINUX_AMD64 = "linux/amd64"
    LINUX_ARM64 = "linux/arm64"


# ── Sous-modèles ────────────────────────────────────────────────────────────


class PluginResourceRequirements(BaseModel):
    """Exigences de ressources matérielles pour un plugin."""

    ram_min_mb: int = Field(..., ge=0, description="RAM minimum en Mo")
    cpu_min_cores: float = Field(..., ge=0, description="CPU minimum en cœurs")
    disk_min_mb: int = Field(..., ge=0, description="Espace disque minimum en Mo")


class PluginPort(BaseModel):
    """Définition d'un port exposé par un plugin."""

    port: int = Field(..., ge=1, le=65535, description="Numéro de port")
    protocol: PortProtocol = Field(..., description="Protocole réseau")
    description: str = Field(..., description="Description du port")
    optional: bool = Field(False, description="Port optionnel")


class PluginConfigField(BaseModel):
    """Définition d'un champ de configuration pour formulaires dynamiques."""

    key: str = Field(..., description="Identifiant unique du champ")
    label: str = Field(..., description="Label affiché dans l'interface")
    description: Optional[str] = Field(None, description="Description détaillée")
    type: ConfigFieldType = Field(..., description="Type du champ")
    required: bool = Field(False, description="Champ obligatoire")
    default: Optional[Any] = Field(None, description="Valeur par défaut")
    validation: Optional[str] = Field(None, description="Regex de validation")
    options: Optional[List[Dict[str, str]]] = Field(
        None, description="Options pour le type select (liste de {value, label})"
    )
    generate: bool = Field(False, description="Propose un bouton Générer")
    visible_if: Optional[str] = Field(
        None, description="Condition d'affichage (capability ou plugin)"
    )

    @model_validator(mode="after")
    def validate_options_for_select(self) -> "PluginConfigField":
        """Les options ne sont autorisées que pour le type select."""
        if self.options is not None and self.type != ConfigFieldType.SELECT:
            raise ValueError(
                "Le champ 'options' n'est autorisé que pour le type 'select'"
            )
        if self.type == ConfigFieldType.SELECT and self.options is None:
            raise ValueError("Le champ 'options' est obligatoire pour le type 'select'")
        return self


class PluginDependencyRef(BaseModel):
    """Référence de dépendance avec nom + contrainte de version optionnelle."""

    name: str = Field(..., description="Nom du plugin dépendance (kebab-case)")
    version_constraint: Optional[str] = Field(
        None, description="Contrainte de version (ex: >=1.0.0)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Valide que le nom est en kebab-case (sécurité : anti path traversal)."""
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Le nom de dépendance doit être en kebab-case : "
                "lettres minuscules, chiffres et tirets, "
                "commençant par une lettre minuscule ou un chiffre"
            )
        return v

    @field_validator("version_constraint")
    @classmethod
    def validate_version_constraint(cls, v: Optional[str]) -> Optional[str]:
        """Valide le format de contrainte de version."""
        if v is None:
            return v
        if not _VERSION_CONSTRAINT_PATTERN.match(v):
            raise ValueError(
                "La contrainte de version doit être valide "
                "(ex: >=1.0.0, ==2.0.0, ~=1.1.0)"
            )
        return v


def parse_dependency_string(dep: str) -> PluginDependencyRef:
    """Parse une chaîne de dépendance en PluginDependencyRef.

    Supporte les formats :
    - ``"plugin-name"`` → PluginDependencyRef(name="plugin-name", version_constraint=None)
    - ``"plugin-name>=1.0.0"`` → PluginDependencyRef(name="plugin-name", version_constraint=">=1.0.0")

    Args:
        dep: Chaîne de dépendance à parser.

    Returns:
        PluginDependencyRef parsé et validé.

    Raises:
        ValueError: Si le nom ou la contrainte de version est invalide.
    """
    # Séparer le nom de la contrainte de version
    # Les opérateurs possibles : >=, <=, >, <, ==, !=, ~=
    match = re.match(
        r"^([a-z0-9][a-z0-9-]*)(?:(>=|<=|>|<|==|!=|~=)\s*(\d+(?:\.\d+){0,2}.*))?$",
        dep,
    )
    if not match:
        raise ValueError(
            f"Format de dépendance invalide : '{dep}'. "
            "Attendu : 'plugin-name' ou 'plugin-name>=1.0.0'"
        )

    name = match.group(1)
    operator = match.group(2)
    version_part = match.group(3)

    version_constraint: Optional[str] = None
    if operator and version_part:
        version_constraint = f"{operator}{version_part}"

    return PluginDependencyRef(name=name, version_constraint=version_constraint)


class PluginDependency(BaseModel):
    """Dépendances entre plugins."""

    requires: List[str] = Field(default_factory=list, description="Plugins requis")
    optional: List[str] = Field(default_factory=list, description="Plugins optionnels")
    conflicts: List[str] = Field(
        default_factory=list, description="Plugins incompatibles"
    )

    def get_resolved_requires(self) -> List[PluginDependencyRef]:
        """Parse chaque élément de requires en PluginDependencyRef."""
        return [parse_dependency_string(dep) for dep in self.requires]

    def get_resolved_optional(self) -> List[PluginDependencyRef]:
        """Parse chaque élément de optional en PluginDependencyRef."""
        return [parse_dependency_string(dep) for dep in self.optional]

    def get_resolved_conflicts(self) -> List[PluginDependencyRef]:
        """Parse chaque élément de conflicts en PluginDependencyRef."""
        return [parse_dependency_string(dep) for dep in self.conflicts]


class PluginExtension(BaseModel):
    """Points d'extension pour les plugins de type extension/hybrid."""

    api_module: Optional[str] = Field(None, description="Module API FastAPI")
    hooks_module: Optional[str] = Field(None, description="Module de hooks")
    ui_routes: Optional[str] = Field(None, description="Fichier de routes UI")
    ui_components: Optional[str] = Field(None, description="Répertoire composants UI")


class PluginHook(BaseModel):
    """Hooks du cycle de vie d'un plugin."""

    on_install: Optional[str] = Field(None, description="Script post-installation")
    on_configure: Optional[str] = Field(None, description="Script post-configuration")
    on_start: Optional[str] = Field(None, description="Script au démarrage")
    on_stop: Optional[str] = Field(None, description="Script à l'arrêt")
    on_update: Optional[str] = Field(None, description="Script pré-mise à jour")
    on_uninstall: Optional[str] = Field(None, description="Script pré-désinstallation")


# ── Deploy hooks / gates pre-deploy (STORY-170.2, spec 11) ──────────────────

#: Nom de fonction python seul (partie après ``:``).
_FUNCTION_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class PluginDeployHookGate(BaseModel):
    """Gate pre-deploy déclarée dans un manifest (STORY-170.2, spec 11).

    Une gate est un hook **synchrone bloquant** exécuté après résolution
    d'images, avant création des containers : elle retourne une décision
    ``approve``/``deny`` (SDK :class:`~app.plugins.gates.GateDecision`).
    Contrat distinct des hooks ``@on_event`` (asynchrones, non bloquants).

    Comportements par défaut (spec 11 § Hooks de déploiement) :

    - timeout → refus prudent ``GATE_TIMEOUT`` sauf ``on_timeout: approve`` ;
    - handler en erreur → refus prudent (``gate_error``) ;
    - aucune gate enregistrée → le déploiement suit son cours.
    """

    handler: str = Field(
        ...,
        description=(
            "Handler de la gate au format 'module:fonction' — chemin "
            "relatif .py sous le répertoire du plugin + fonction python "
            "async (ex. 'gates.py:pre_deploy')"
        ),
    )
    timeout: Optional[int] = Field(
        None,
        ge=1,
        le=3600,
        description=(
            "Timeout d'exécution de la gate en secondes (1-3600) — "
            "surcharge le défaut settings plugin_gate_timeout_seconds "
            "(spec 11 : 300 s)"
        ),
    )
    on_timeout: Literal["deny", "approve"] = Field(
        default="deny",
        description=(
            "Comportement au timeout — 'deny' (défaut, refus prudent : on "
            "ne déploie pas ce qu'on n'a pas pu évaluer) ou 'approve' "
            "(déploiement autorisé malgré le timeout)"
        ),
    )

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        """Valide le format ``module:fonction`` du handler de gate.

        Refus (anti path-traversal, cohérent
        ``_resolve_hooks_module_path``) : chemins absolus, segments ``..``,
        absence de séparateur ``:``, nom de fonction python invalide.
        """
        v = v.strip()
        if not v or ":" not in v:
            raise ValueError(
                "Le handler de gate doit être au format 'module:fonction' "
                "(ex. 'gates.py:pre_deploy')"
            )
        module_part, _, function_part = v.rpartition(":")
        if os.path.isabs(module_part) or module_part.startswith("/"):
            raise ValueError(
                "Chemin de module absolu interdit dans le handler de gate " f": {v}"
            )
        if ".." in module_part.split("/") or ".." in module_part.split(os.sep):
            raise ValueError(f"Path traversal détecté dans le handler de gate : {v}")
        if not module_part.endswith(".py"):
            raise ValueError(
                "Le module du handler de gate doit être un chemin relatif "
                f"finissant par .py : {v}"
            )
        if not _FUNCTION_NAME_PATTERN.match(function_part):
            raise ValueError(
                f"Nom de fonction python invalide dans le handler de gate : {v}"
            )
        return v


class PluginDeployHooks(BaseModel):
    """Hooks de déploiement d'un plugin (gates pre-deploy, STORY-170.2)."""

    model_config = {"extra": "ignore"}

    pre_deploy: Optional[PluginDeployHookGate] = Field(
        None,
        description="Gate pre-deploy exécutée avant création des containers",
    )


class PluginAutoDetect(BaseModel):
    """Configuration de détection automatique de services existants."""

    docker_images: List[str] = Field(
        default_factory=list,
        description="Images Docker qui activent le plugin",
    )


# ── Modèle principal ────────────────────────────────────────────────────────


class PluginManifest(BaseModel):
    """Manifest complet d'un plugin WindFlow.

    Représente la totalité d'un fichier windflow-plugin.yml.
    La validation est stricte : tous les champs requis doivent être présents
    et les contraintes de type sont vérifiées.
    """

    # Identité
    name: str = Field(..., description="Identifiant unique (kebab-case)")
    version: str = Field(..., description="Version (format semver)")
    display_name: str = Field(..., description="Nom affiché dans l'UI")
    description: str = Field(..., description="Description courte")
    long_description: Optional[str] = Field(None, description="Description longue")
    category: PluginCategory = Field(..., description="Catégorie marketplace")
    tags: List[str] = Field(default_factory=list, description="Tags de recherche")
    icon: Optional[str] = Field(None, description="Icône (SVG ou PNG)")
    author: str = Field(..., description="Auteur du plugin")
    license: str = Field(..., description="Licence du plugin")
    homepage: Optional[str] = Field(None, description="URL du site principal")

    # Type
    type: PluginType = Field(..., description="Type de plugin")

    # Compatibilité
    architectures: List[Architecture] = Field(
        ..., min_length=1, description="Architectures supportées"
    )
    windflow_version: Optional[str] = Field(
        None, description="Version minimum de WindFlow (ex: >=1.1.0)"
    )

    # Ressources
    resources: Optional[PluginResourceRequirements] = Field(
        None, description="Exigences de ressources"
    )

    # Dépendances
    dependencies: Optional[PluginDependency] = Field(
        None, description="Dépendances entre plugins"
    )

    # Capabilities
    provides: List[str] = Field(
        default_factory=list, description="Capabilities fournies"
    )

    # Ports
    ports: List[PluginPort] = Field(default_factory=list, description="Ports exposés")

    # Configuration
    config: List[PluginConfigField] = Field(
        default_factory=list, description="Champs de configuration"
    )

    # Fichiers
    compose_file: Optional[str] = Field(
        None, description="Fichier docker-compose (service/hybrid)"
    )
    config_schema: Optional[str] = Field(
        None, description="Fichier schéma de configuration"
    )

    # Extensions
    extensions: Optional[PluginExtension] = Field(
        None, description="Points d'extension (extension/hybrid)"
    )

    # Hooks
    hooks: Optional[PluginHook] = Field(None, description="Hooks du cycle de vie")

    # Deploy hooks — gates pre-deploy (STORY-170.2, spec 11 § Hooks de
    # déploiement). Les gates ne concernent que les types extension/hybrid ;
    # pour un plugin service la déclaration est ignorée (warning au
    # chargement — le manifest peut être partagé, pas un rejet).
    deploy_hooks: Optional[PluginDeployHooks] = Field(
        None, description="Hooks de déploiement (gates pre-deploy)"
    )

    # Auto-détection
    auto_detect: Optional[PluginAutoDetect] = Field(
        None, description="Détection automatique de services"
    )

    model_config = {"extra": "ignore"}

    # ── Field validators ────────────────────────────────────────────────

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Valide que le name est en kebab-case (sécurité : anti path traversal)."""
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Le nom doit être en kebab-case : "
                "lettres minuscules, chiffres et tirets, "
                "commençant par une lettre minuscule ou un chiffre"
            )
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Valide que la version est au format semver."""
        if not _SEMVER_PATTERN.match(v):
            raise ValueError(
                "La version doit être au format semver (ex: 1.2.3, 1.0.0-alpha.1)"
            )
        return v

    @field_validator("windflow_version")
    @classmethod
    def validate_windflow_version(cls, v: Optional[str]) -> Optional[str]:
        """Valide le format de contrainte de version WindFlow."""
        if v is None:
            return v
        if not _VERSION_CONSTRAINT_PATTERN.match(v):
            raise ValueError(
                "windflow_version doit être une contrainte de version valide "
                "(ex: >=1.1.0, ==2.0.0, ~=1.1.0)"
            )
        return v

    # ── Model validators ────────────────────────────────────────────────

    @model_validator(mode="after")
    def validate_type_consistency(self) -> "PluginManifest":
        """Vérifie la cohérence entre le type de plugin et les champs requis."""
        if self.type in (PluginType.SERVICE, PluginType.HYBRID):
            if not self.compose_file:
                raise ValueError(
                    f"Le champ 'compose_file' est obligatoire pour le type "
                    f"'{self.type.value}'"
                )

        if self.type in (PluginType.EXTENSION, PluginType.HYBRID):
            if not self.extensions:
                raise ValueError(
                    f"Le champ 'extensions' est obligatoire pour le type "
                    f"'{self.type.value}'"
                )

        return self

    # ── Méthodes utilitaires ────────────────────────────────────────────

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "PluginManifest":
        """Parse un contenu YAML et retourne un PluginManifest validé.

        Utilise yaml.safe_load() exclusivement pour des raisons de sécurité.

        Args:
            yaml_content: Contenu YAML du manifest.

        Returns:
            PluginManifest validé.

        Raises:
            ValueError: Si le contenu YAML est vide.
            yaml.YAMLError: Si le YAML est malformé.
            ValidationError: Si la validation Pydantic échoue.
        """
        raw_data = yaml.safe_load(yaml_content)

        if not raw_data:
            raise ValueError("Le contenu YAML est vide ou invalide")

        return cls(**raw_data)
