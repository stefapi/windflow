"""
Service de chargement de stacks depuis des fichiers YAML (STORY-171).

Consommateur du **moteur unique de validation** : le schéma Pydantic strict
``StackDefinition`` (``schemas/stack_definition.py``). Ce service ne porte
**plus aucune règle de validation propre** — il charge le YAML
(``yaml.safe_load``) et délègue toute la validation au moteur, garantissant
que le seed de démarrage (``StackDefinitionsLoader``) et l'import/validate
admin rendent le **même verdict** avec les **mêmes données** en base
(variables au format dump Pydantic : groupes récursifs, ``visible``,
``enum_labels``, macros brutes, bornes ``minimum``/``maximum``).
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import ValidationError

from ..schemas.stack import StackCreate
from ..schemas.stack_definition import (
    StackDefinition,
    convert_variables_to_db_format,
    format_validation_errors,
)

logger = logging.getLogger(__name__)


class StackLoaderService:
    """Service de chargement et parsing de stacks YAML (consommateur du moteur)."""

    @staticmethod
    def load_definition(yaml_path: Path) -> StackDefinition:
        """
        Charge et valide une définition de stack depuis un fichier YAML.

        Le **moteur unique** (schéma Pydantic ``StackDefinition``) fait toute
        la validation : types fermés (dont ``integer``/``group``),
        ``enum_labels ⊆ enum``, ``target_type`` fermé, métadonnées complètes,
        template non vide (sans exiger ``services``).

        Args:
            yaml_path: Chemin vers le fichier YAML

        Returns:
            StackDefinition: Définition validée par le moteur

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si le YAML est vide ou mal formé
            yaml.YAMLError: Si le YAML est syntaxiquement invalide
            ValidationError: Si la définition viole le schéma strict
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Stack definition not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty YAML file: {yaml_path}")

        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a mapping: {yaml_path}")

        # Moteur unique : validation stricte par le schéma Pydantic
        return StackDefinition(**data)

    @staticmethod
    def validate_stack_definition(data: Dict[str, Any]) -> None:
        """
        Valide une définition de stack (dict brut) via le moteur unique.

        Wrapper de compatibilité des appels historiques : aucune règle propre
        — délègue intégralement à ``StackDefinition``.

        Args:
            data: Définition du stack (dict brut parsé du YAML)

        Raises:
            ValidationError: Si la définition viole le schéma strict
        """
        StackDefinition(**data)

    @staticmethod
    def load_from_yaml(yaml_path: Path) -> Dict[str, Any]:
        """
        Charge une définition de stack brute (sans validation) depuis YAML.

        Lecture « inventaire » conservée pour les endpoints qui n'ont besoin
        que des métadonnées brutes (ex. sync status). La validation passe par
        :meth:`load_definition`.

        Args:
            yaml_path: Chemin vers le fichier YAML

        Returns:
            Dict: Définition du stack parsée (données brutes)

        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si le YAML est vide ou mal formé
            yaml.YAMLError: Si le YAML est invalide
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"Stack definition not found: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty YAML file: {yaml_path}")

        return data

    @staticmethod
    def to_stack_create(
        definition: StackDefinition, organization_id: str
    ) -> StackCreate:
        """
        Convertit une définition validée en schéma StackCreate.

        Mapping complet depuis ``StackDefinition`` : ``target_type``,
        ``target_parameters``, ``deployment_name`` et macros **brutes**
        conservées dans les défauts (aligné sur le seed — le rendu des macros
        se fait à la volée à chaque ``GET /stacks/{id}``).

        Args:
            definition: Définition validée par le moteur
            organization_id: ID de l'organisation propriétaire

        Returns:
            StackCreate: Schéma pour créer le stack
        """
        return StackCreate(
            name=definition.metadata.name,
            description=definition.metadata.description,
            version=definition.metadata.version,
            category=definition.metadata.category,
            author=definition.metadata.author,
            license=definition.metadata.license,
            icon_url=definition.metadata.icon_url,
            documentation_url=definition.metadata.documentation_url,
            template=definition.template,
            variables=convert_variables_to_db_format(definition.variables),
            tags=definition.metadata.tags,
            is_public=definition.metadata.is_public,
            screenshots=definition.metadata.screenshots,
            organization_id=organization_id,
            deployment_name=definition.metadata.deployment_name,
            target_type=definition.metadata.target_type,
            target_parameters=definition.target_parameters,
        )

    @staticmethod
    def load_all_from_directory(
        directory: Path, organization_id: str
    ) -> List[StackCreate]:
        """
        Charge tous les stacks valides d'un répertoire.

        Un fichier invalide est journalisé (``logger.warning``) et **sauté**
        sans interrompre les autres (même comportement que le seed). Les
        fichiers commençant par ``_`` sont ignorés.

        Args:
            directory: Répertoire contenant les fichiers YAML
            organization_id: ID de l'organisation

        Returns:
            List[StackCreate]: Liste des schémas de création valides
        """
        stacks: List[StackCreate] = []

        if not directory.exists():
            return stacks

        for yaml_file in sorted(directory.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                # Ignorer les fichiers commençant par _
                continue

            try:
                definition = StackLoaderService.load_definition(yaml_file)
                stack_create = StackLoaderService.to_stack_create(
                    definition, organization_id
                )
                stacks.append(stack_create)
                logger.info("✓ Chargé: %s - %s", yaml_file.name, stack_create.name)
            except ValidationError as e:
                # Erreurs formatées sans valeur d'input (rules 40)
                details = "; ".join(format_validation_errors(e))
                logger.warning(
                    "✗ Erreur de validation pour %s: %s", yaml_file.name, details
                )
            except Exception as e:
                logger.warning(
                    "✗ Erreur lors du chargement de %s: %s", yaml_file.name, e
                )
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
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[-\s]+", "-", name)
        return f"{name}.yaml"
