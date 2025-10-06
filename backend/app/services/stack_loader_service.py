"""
Service de chargement de stacks depuis des fichiers YAML.

Permet de charger et parser des définitions de stacks depuis des fichiers
YAML pour les importer dans le marketplace WindFlow.
"""

import yaml
import secrets
import string
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from jinja2 import Template

from ..schemas.stack import StackCreate


class StackLoaderService:
    """Service de chargement et parsing de stacks YAML."""

    @staticmethod
    def generate_password(length: int = 20) -> str:
        """
        Génère un mot de passe aléatoire sécurisé.

        Args:
            length: Longueur du mot de passe

        Returns:
            str: Mot de passe généré
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password

    @staticmethod
    def generate_secret(length: int = 50) -> str:
        """
        Génère une clé secrète aléatoire.

        Args:
            length: Longueur de la clé

        Returns:
            str: Clé secrète générée
        """
        alphabet = string.ascii_letters + string.digits
        secret = ''.join(secrets.choice(alphabet) for _ in range(length))
        return secret

    @staticmethod
    def process_variable_default(default_value: Any) -> Any:
        """
        Traite les valeurs par défaut des variables avec templates Jinja2.

        Supporte les fonctions:
        - {{ generate_password(N) }}: Génère un mot de passe de N caractères
        - {{ generate_secret(N) }}: Génère une clé secrète de N caractères
        - {{ domain }}: Référence à une autre variable

        Args:
            default_value: Valeur par défaut à traiter

        Returns:
            Any: Valeur traitée
        """
        if not isinstance(default_value, str):
            return default_value

        # Détection des templates Jinja2
        if "{{" not in default_value:
            return default_value

        # Traitement des fonctions de génération
        if "generate_password" in default_value:
            match = re.search(r'generate_password\((\d+)\)', default_value)
            if match:
                length = int(match.group(1))
                return StackLoaderService.generate_password(length)

        if "generate_secret" in default_value:
            match = re.search(r'generate_secret\((\d+)\)', default_value)
            if match:
                length = int(match.group(1))
                return StackLoaderService.generate_secret(length)

        # Pour les autres cas, on retourne la valeur brute
        # (sera traité lors du déploiement avec les vraies valeurs)
        return default_value

    @staticmethod
    def normalize_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalise les variables au format simple pour JSONForms.

        Convertit le format YAML détaillé en format simple attendu par WindFlow.

        Args:
            variables: Variables au format YAML détaillé

        Returns:
            Dict: Variables au format simple
        """
        normalized = {}

        for var_name, var_config in variables.items():
            # Traiter la valeur par défaut
            default = var_config.get("default", "")
            processed_default = StackLoaderService.process_variable_default(default)

            # Format simple pour WindFlow
            normalized[var_name] = {
                "type": var_config.get("type", "string"),
                "label": var_config.get("label", var_name),
                "description": var_config.get("description", ""),
                "default": processed_default,
                "required": var_config.get("required", False)
            }

            # Ajouter les contraintes optionnelles
            if "enum" in var_config:
                normalized[var_name]["enum"] = var_config["enum"]

            if "pattern" in var_config:
                normalized[var_name]["pattern"] = var_config["pattern"]

            if "minimum" in var_config:
                normalized[var_name]["minimum"] = var_config["minimum"]

            if "maximum" in var_config:
                normalized[var_name]["maximum"] = var_config["maximum"]

            if "min_length" in var_config:
                normalized[var_name]["min_length"] = var_config["min_length"]

            if "max_length" in var_config:
                normalized[var_name]["max_length"] = var_config["max_length"]

            if "help" in var_config:
                normalized[var_name]["help"] = var_config["help"]

            if "group" in var_config:
                normalized[var_name]["group"] = var_config["group"]

            if "depends_on" in var_config:
                normalized[var_name]["depends_on"] = var_config["depends_on"]

        return normalized

    @staticmethod
    def load_from_yaml(yaml_path: Path) -> Dict[str, Any]:
        """
        Charge une définition de stack depuis un fichier YAML.

        Args:
            yaml_path: Chemin vers le fichier YAML

        Returns:
            Dict: Définition du stack parsée

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            yaml.YAMLError: Si le YAML est invalide
            ValueError: Si la structure est invalide
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Stack definition not found: {yaml_path}")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Validation de la structure
        if not data:
            raise ValueError(f"Empty YAML file: {yaml_path}")

        if "metadata" not in data:
            raise ValueError(f"Missing 'metadata' section in {yaml_path}")

        if "template" not in data:
            raise ValueError(f"Missing 'template' section in {yaml_path}")

        if "variables" not in data:
            raise ValueError(f"Missing 'variables' section in {yaml_path}")

        return data

    @staticmethod
    def validate_stack_definition(data: Dict[str, Any]) -> None:
        """
        Valide une définition de stack.

        Args:
            data: Définition du stack à valider

        Raises:
            ValueError: Si la définition est invalide
        """
        metadata = data.get("metadata", {})

        # Validation des métadonnées requises
        required_metadata = ["name", "version", "description"]
        for field in required_metadata:
            if not metadata.get(field):
                raise ValueError(f"Missing required metadata field: {field}")

        # Validation du template
        template = data.get("template", {})
        if not template.get("services"):
            raise ValueError("Template must contain at least one service")

        # Validation des variables
        variables = data.get("variables", {})
        for var_name, var_config in variables.items():
            if not isinstance(var_config, dict):
                raise ValueError(f"Invalid variable configuration for {var_name}")

            if "type" not in var_config:
                raise ValueError(f"Missing type for variable {var_name}")

            valid_types = ["string", "number", "boolean", "password", "enum", "textarea"]
            if var_config["type"] not in valid_types:
                raise ValueError(
                    f"Invalid type '{var_config['type']}' for variable {var_name}. "
                    f"Must be one of: {', '.join(valid_types)}"
                )

    @staticmethod
    def to_stack_create(
        data: Dict[str, Any],
        organization_id: str
    ) -> StackCreate:
        """
        Convertit une définition YAML en schéma StackCreate.

        Args:
            data: Définition du stack parsée
            organization_id: ID de l'organisation propriétaire

        Returns:
            StackCreate: Schéma pour créer le stack
        """
        # Validation
        StackLoaderService.validate_stack_definition(data)

        metadata = data["metadata"]
        template = data["template"]
        variables = data["variables"]

        # Normaliser les variables
        normalized_variables = StackLoaderService.normalize_variables(variables)

        # Créer le schéma
        stack_create = StackCreate(
            name=metadata["name"],
            description=metadata["description"],
            version=metadata.get("version", "1.0.0"),
            category=metadata.get("category"),
            author=metadata.get("author"),
            license=metadata.get("license", "MIT"),
            icon_url=metadata.get("icon_url"),
            documentation_url=metadata.get("documentation_url"),
            template=template,
            variables=normalized_variables,
            tags=metadata.get("tags", []),
            is_public=metadata.get("is_public", False),
            screenshots=metadata.get("screenshots", []),
            organization_id=organization_id
        )

        return stack_create

    @staticmethod
    def load_all_from_directory(
        directory: Path,
        organization_id: str
    ) -> List[StackCreate]:
        """
        Charge tous les stacks d'un répertoire.

        Args:
            directory: Répertoire contenant les fichiers YAML
            organization_id: ID de l'organisation

        Returns:
            List[StackCreate]: Liste des schémas de création
        """
        stacks = []

        if not directory.exists():
            return stacks

        # Parcourir tous les fichiers YAML
        for yaml_file in directory.glob("*.yaml"):
            if yaml_file.name.startswith("_"):
                # Ignorer les fichiers commençant par _
                continue

            try:
                data = StackLoaderService.load_from_yaml(yaml_file)
                stack_create = StackLoaderService.to_stack_create(
                    data,
                    organization_id
                )
                stacks.append(stack_create)
                print(f"✓ Chargé: {yaml_file.name} - {stack_create.name}")
            except Exception as e:
                print(f"✗ Erreur lors du chargement de {yaml_file.name}: {e}")
                # On continue avec les autres fichiers

        return stacks

    @staticmethod
    def get_stack_filename(stack_create: StackCreate) -> str:
        """
        Génère un nom de fichier à partir d'un nom de stack.

        Args:
            stack_create: Schéma du stack

        Returns:
            str: Nom de fichier suggéré
        """
        # Convertir le nom en slug
        name = stack_create.name.lower()
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[-\s]+', '-', name)
        return f"{name}.yaml"
