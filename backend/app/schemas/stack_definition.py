"""
Schémas Pydantic pour les définitions de stacks depuis fichiers YAML.

Validation stricte de la structure des fichiers stacks_definitions/*.yaml
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator


class VariableType(str, Enum):
    """Types de variables configurables."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    PASSWORD = "password"
    TEXTAREA = "textarea"


class StackDefinitionVariable(BaseModel):
    """Définition d'une variable configurable."""

    type: VariableType = Field(..., description="Type de la variable")
    label: str = Field(..., description="Label affiché dans l'interface")
    description: Optional[str] = Field(None, description="Description détaillée")
    default: Any = Field(None, description="Valeur par défaut")
    required: bool = Field(False, description="Variable obligatoire ?")
    group: Optional[str] = Field(None, description="Groupe dans l'interface")
    help: Optional[str] = Field(None, description="Aide contextuelle (tooltip)")

    # Contraintes spécifiques selon le type
    pattern: Optional[str] = Field(None, description="Regex de validation (string)")
    enum: Optional[List[Any]] = Field(None, description="Liste de choix possibles")
    enum_labels: Optional[Dict[str, str]] = Field(
        None,
        description="Libellés explicatifs pour les valeurs enum (optionnel)"
    )
    minimum: Optional[int] = Field(None, description="Valeur minimale (number)")
    maximum: Optional[int] = Field(None, description="Valeur maximale (number)")
    min_length: Optional[int] = Field(None, description="Longueur minimale (string/password)")
    max_length: Optional[int] = Field(None, description="Longueur maximale (string/password)")

    # Métadonnées pour les macros
    has_macro: bool = Field(False, description="Indique si la valeur par défaut contient une macro Jinja")
    macro_template: Optional[str] = Field(None, description="Template Jinja original avant rendu")

    # Dépendances conditionnelles
    depends_on: Optional[Dict[str, Any]] = Field(
        None,
        description="Conditions d'affichage basées sur d'autres variables"
    )

    @validator('enum_labels')
    def validate_enum_labels(cls, v, values):
        """Valide que les clés de enum_labels correspondent aux valeurs de enum."""
        if v is None:
            return v

        enum_values = values.get('enum')
        if enum_values is None:
            raise ValueError(
                "enum_labels ne peut être défini que si enum est également défini"
            )

        # Convertir les valeurs enum en strings pour la comparaison
        enum_str_values = {str(val) for val in enum_values}
        enum_labels_keys = set(v.keys())

        # Vérifier que toutes les clés de enum_labels existent dans enum
        invalid_keys = enum_labels_keys - enum_str_values
        if invalid_keys:
            raise ValueError(
                f"Les clés suivantes dans enum_labels n'existent pas dans enum: {invalid_keys}"
            )

        return v


class StackDefinitionMetadata(BaseModel):
    """Métadonnées du stack."""

    name: str = Field(..., description="Nom du stack")
    version: str = Field(..., description="Version (format semver)")
    category: str = Field(..., description="Catégorie du stack")
    author: str = Field(..., description="Auteur du stack")
    license: str = Field(..., description="Licence")
    description: str = Field(..., description="Description détaillée")

    # Champs optionnels
    icon_url: Optional[str] = Field(None, description="URL de l'icône")
    documentation_url: Optional[str] = Field(None, description="URL de la documentation")
    screenshots: List[str] = Field(default_factory=list, description="URLs des screenshots")
    tags: List[str] = Field(default_factory=list, description="Tags de recherche")
    is_public: bool = Field(True, description="Stack public dans le marketplace ?")

    # Type de déploiement supporté (obligatoire)
    target_type: str = Field(..., description="Type de déploiement (docker, docker_compose, etc.)")

    # Nom par défaut du déploiement (template)
    deployment_name: Optional[str] = Field(None, description="Nom par défaut du déploiement (template)")

    @validator('version')
    def validate_version(cls, v):
        """Valide le format de la version."""
        # Simple validation - devrait idéalement utiliser semver
        if not v or len(v.strip()) == 0:
            raise ValueError("Version ne peut pas être vide")
        return v

    @validator('target_type')
    def validate_target_type(cls, v):
        """Valide que le target_type est valide."""
        valid_types = {
            'docker', 'docker_compose', 'docker_swarm',
            'kubernetes', 'vm', 'physical'
        }
        if v not in valid_types:
            raise ValueError(
                f"target_type invalide: {v}. "
                f"Valeurs valides: {', '.join(valid_types)}"
            )
        return v


class StackDefinition(BaseModel):
    """Définition complète d'un stack depuis YAML."""

    metadata: StackDefinitionMetadata = Field(..., description="Métadonnées du stack")
    template: Dict[str, Any] = Field(..., description="Template Docker/Compose/K8s")
    variables: Dict[str, StackDefinitionVariable] = Field(
        default_factory=dict,
        description="Variables configurables"
    )
    target_parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Paramètres spécifiques à la target (ex: volumes à supprimer)"
    )
    deployment_notes: Optional[str] = Field(
        None,
        description="Notes de déploiement (markdown)"
    )

    @validator('template')
    def validate_template(cls, v):
        """Valide que le template n'est pas vide."""
        if not v or len(v) == 0:
            raise ValueError("Template ne peut pas être vide")
        return v
