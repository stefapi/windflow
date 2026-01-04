"""
Service de chargement des définitions de stacks depuis fichiers YAML.

Scanne le répertoire stacks_definitions/ et charge les stacks dans la base de données.
"""

import yaml
from pathlib import Path
from typing import List, Tuple, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError
from packaging.version import Version, InvalidVersion

from ..schemas.stack_definition import (
    StackDefinition,
    StackDefinitionMetadata,
    StackDefinitionVariable
)
from ..models.stack import Stack
import logging

logger = logging.getLogger(__name__)


class StackDefinitionsLoader:
    """Charge les définitions de stacks depuis les fichiers YAML."""

    def __init__(self, definitions_path: str = "stacks_definitions"):
        """
        Initialise le loader.

        Args:
            definitions_path: Chemin vers le répertoire des définitions YAML
        """
        self.definitions_path = Path(definitions_path)

        if not self.definitions_path.exists():
            raise ValueError(f"Le répertoire {definitions_path} n'existe pas")

        if not self.definitions_path.is_dir():
            raise ValueError(f"{definitions_path} n'est pas un répertoire")

    def scan_definitions(self) -> List[StackDefinition]:
        """
        Scanne tous les fichiers .yaml du répertoire.

        Returns:
            Liste des définitions de stacks valides
        """
        definitions = []
        errors = []

        # Scanner tous les fichiers .yaml
        yaml_files = list(self.definitions_path.glob("*.yaml"))

        logger.info(f"Scan de {len(yaml_files)} fichiers YAML dans {self.definitions_path}")

        for yaml_file in yaml_files:
            try:
                definition = self._parse_yaml_file(yaml_file)
                definitions.append(definition)
                logger.debug(f"✓ {yaml_file.name}: {definition.metadata.name} v{definition.metadata.version}")
            except Exception as e:
                error_msg = f"✗ {yaml_file.name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        if errors:
            logger.warning(f"{len(errors)} fichier(s) avec erreurs sur {len(yaml_files)}")

        return definitions

    def _parse_yaml_file(self, file_path: Path) -> StackDefinition:
        """
        Parse et valide un fichier YAML.

        Args:
            file_path: Chemin vers le fichier YAML

        Returns:
            StackDefinition validée

        Raises:
            ValidationError: Si le fichier est invalide
            yaml.YAMLError: Si le YAML est malformé
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)

        if not raw_data:
            raise ValueError("Fichier YAML vide")

        # Valider avec Pydantic
        definition = StackDefinition(**raw_data)

        return definition

    async def load_into_database(
        self,
        session: AsyncSession,
        organization_id: str,
        strategy: str = "update_if_newer"
    ) -> Tuple[int, int, List[str]]:
        """
        Charge les définitions dans la base de données.

        Args:
            session: Session de base de données
            organization_id: ID de l'organisation propriétaire
            strategy: Stratégie de mise à jour
                - "skip_existing": Ne rien faire si existe
                - "update_if_newer": Mettre à jour si version plus récente
                - "force_update": Toujours écraser

        Returns:
            Tuple (created_count, updated_count, errors)
        """
        definitions = self.scan_definitions()

        created_count = 0
        updated_count = 0
        errors = []

        for definition in definitions:
            try:
                result = await self._load_single_stack(
                    session,
                    definition,
                    organization_id,
                    strategy
                )

                if result == "created":
                    created_count += 1
                elif result == "updated":
                    updated_count += 1

            except Exception as e:
                error_msg = f"{definition.metadata.name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Erreur lors du chargement: {error_msg}")

        return created_count, updated_count, errors

    async def _load_single_stack(
        self,
        session: AsyncSession,
        definition: StackDefinition,
        organization_id: str,
        strategy: str
    ) -> str:
        """
        Charge un stack unique dans la base de données.

        Returns:
            "created", "updated" ou "skipped"
        """
        # Chercher un stack existant par nom et version
        stmt = select(Stack).where(
            Stack.name == definition.metadata.name,
            Stack.version == definition.metadata.version,
            Stack.organization_id == organization_id
        )
        result = await session.execute(stmt)
        existing_stack = result.scalar_one_or_none()

        if existing_stack:
            # Stack existe déjà
            if strategy == "skip_existing":
                logger.debug(f"Stack {definition.metadata.name} v{definition.metadata.version} existe déjà, ignoré")
                return "skipped"

            elif strategy == "update_if_newer":
                # Comparer les versions
                if self._is_version_newer(definition.metadata.version, existing_stack.version):
                    await self._update_stack(session, existing_stack, definition)
                    logger.info(f"Stack {definition.metadata.name} mis à jour: v{existing_stack.version} → v{definition.metadata.version}")
                    return "updated"
                else:
                    logger.debug(f"Stack {definition.metadata.name} v{definition.metadata.version} pas plus récent, ignoré")
                    return "skipped"

            elif strategy == "force_update":
                await self._update_stack(session, existing_stack, definition)
                logger.info(f"Stack {definition.metadata.name} v{definition.metadata.version} écrasé (force)")
                return "updated"

        else:
            # Créer un nouveau stack
            new_stack = await self._create_stack(session, definition, organization_id)
            logger.info(f"Stack {definition.metadata.name} v{definition.metadata.version} créé")
            return "created"

    async def _create_stack(
        self,
        session: AsyncSession,
        definition: StackDefinition,
        organization_id: str
    ) -> Stack:
        """Crée un nouveau stack dans la base de données."""

        stack = Stack(
            name=definition.metadata.name,
            description=definition.metadata.description,
            version=definition.metadata.version,
            category=definition.metadata.category,
            tags=definition.metadata.tags,
            target_type=definition.metadata.target_type,
            template=definition.template,
            variables=self._convert_variables_to_db_format(definition.variables),
            target_parameters=definition.target_parameters,
            is_public=definition.metadata.is_public,
            icon_url=definition.metadata.icon_url,
            screenshots=definition.metadata.screenshots,
            documentation_url=definition.metadata.documentation_url,
            author=definition.metadata.author,
            license=definition.metadata.license,
            deployment_name=definition.metadata.deployment_name,
            organization_id=organization_id
        )

        session.add(stack)
        await session.flush()

        return stack

    async def _update_stack(
        self,
        session: AsyncSession,
        stack: Stack,
        definition: StackDefinition
    ) -> None:
        """Met à jour un stack existant."""

        stack.description = definition.metadata.description
        stack.version = definition.metadata.version
        stack.category = definition.metadata.category
        stack.tags = definition.metadata.tags
        stack.target_type = definition.metadata.target_type
        stack.template = definition.template
        stack.variables = self._convert_variables_to_db_format(definition.variables)
        stack.target_parameters = definition.target_parameters
        stack.is_public = definition.metadata.is_public
        stack.icon_url = definition.metadata.icon_url
        stack.screenshots = definition.metadata.screenshots
        stack.documentation_url = definition.metadata.documentation_url
        stack.author = definition.metadata.author
        stack.license = definition.metadata.license
        stack.deployment_name = definition.metadata.deployment_name

        await session.flush()

    def _convert_variables_to_db_format(
        self,
        variables: Dict[str, StackDefinitionVariable]
    ) -> Dict[str, Any]:
        """
        Convertit les variables Pydantic en format dict pour la DB.

        Args:
            variables: Dictionnaire de StackDefinitionVariable

        Returns:
            Dictionnaire JSON-serializable pour la base de données
        """
        if not variables:
            return {}

        db_variables = {}
        for var_name, var_def in variables.items():
            db_variables[var_name] = var_def.model_dump(exclude_none=True)

        return db_variables

    def _is_version_newer(self, version1: str, version2: str) -> bool:
        """
        Compare deux versions semver en utilisant la librairie packaging.

        Cette méthode utilise packaging.version.Version qui gère correctement:
        - Les versions semver standards (1.2.3)
        - Les pre-releases (1.0.0a1, 1.0.0-alpha)
        - Les versions post-release (1.0.0.post1)
        - Les versions dev (1.0.0.dev1)
        - Les versions locales (1.0.0+local)

        Args:
            version1: Nouvelle version potentielle
            version2: Version existante

        Returns:
            True si version1 > version2

        Examples:
            >>> _is_version_newer("1.2.0", "1.1.9")
            True
            >>> _is_version_newer("2.0.0", "1.9.9")
            True
            >>> _is_version_newer("1.0.0", "1.0.0")
            False
            >>> _is_version_newer("1.0.0a1", "1.0.0")
            False  # Les pre-releases sont considérées comme antérieures
        """
        try:
            # Utiliser packaging.version.Version pour une comparaison robuste
            v1 = Version(version1)
            v2 = Version(version2)

            # Comparaison directe grâce à l'implémentation de __gt__
            return v1 > v2

        except InvalidVersion as e:
            # Si une des versions est invalide, logger et faire un fallback
            logger.warning(
                f"Version invalide détectée lors de la comparaison: "
                f"{version1} vs {version2}. Erreur: {e}. "
                f"Utilisation d'une comparaison textuelle en fallback."
            )
            # Fallback sur comparaison textuelle (pas idéal mais mieux que de planter)
            return version1 > version2
