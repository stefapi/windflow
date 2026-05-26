"""
Service de validation des manifests de plugins WindFlow.

Responsable du parsing et de la validation des manifests plugin
depuis des fichiers ou des contenus YAML bruts.
"""

import logging
from pathlib import Path
from typing import List, Tuple

import yaml
from pydantic import ValidationError

from ..core.exceptions import WindFlowException
from ..schemas.plugin_manifest import PluginManifest

logger = logging.getLogger(__name__)


class PluginManifestService:
    """Service métier de parsing et validation des manifests plugin."""

    def validate_manifest(self, yaml_content: str) -> PluginManifest:
        """Parse et valide un contenu YAML de manifest plugin.

        Args:
            yaml_content: Contenu YAML brut du manifest.

        Returns:
            PluginManifest validé.

        Raises:
            WindFlowException: Si le YAML est malformé ou la validation échoue.
        """
        try:
            manifest = PluginManifest.from_yaml(yaml_content)
            logger.info(
                "manifest_validated",
                extra={
                    "plugin_name": manifest.name,
                    "version": manifest.version,
                },
            )
            return manifest
        except yaml.YAMLError as exc:
            raise WindFlowException(
                f"Erreur de syntaxe YAML : {exc}",
                details={"error_type": "yaml_syntax"},
            ) from exc
        except ValidationError as exc:
            raise WindFlowException(
                f"Erreur de validation du manifest : {exc}",
                details={"error_type": "validation"},
            ) from exc
        except ValueError as exc:
            raise WindFlowException(
                f"Erreur de validation du manifest : {exc}",
                details={"error_type": "value"},
            ) from exc

    def validate_manifest_file(self, file_path: Path) -> PluginManifest:
        """Lit et valide un fichier manifest plugin.

        Args:
            file_path: Chemin vers le fichier windflow-plugin.yml.

        Returns:
            PluginManifest validé.

        Raises:
            WindFlowException: Si le fichier est introuvable ou invalide.
        """
        if not file_path.exists():
            raise WindFlowException(
                f"Fichier manifest introuvable : {file_path}",
                details={"error_type": "file_not_found", "path": str(file_path)},
            )

        try:
            yaml_content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise WindFlowException(
                f"Impossible de lire le fichier manifest : {exc}",
                details={"error_type": "file_read", "path": str(file_path)},
            ) from exc

        manifest = self.validate_manifest(yaml_content)
        logger.info(
            "manifest_file_validated",
            extra={
                "plugin_name": manifest.name,
                "version": manifest.version,
                "file_path": str(file_path),
            },
        )
        return manifest

    def validate_manifest_batch(
        self, directory: Path
    ) -> Tuple[List[PluginManifest], List[str]]:
        """Scanne et valide tous les manifests d'un répertoire.

        Recherche tous les fichiers nommés ``windflow-plugin.yml`` dans le
        répertoire donné (non récursif).

        Args:
            directory: Répertoire contenant les sous-dossiers de plugins.

        Returns:
            Tuple (manifests_valides, liste_erreurs).
        """
        valid_manifests: List[PluginManifest] = []
        errors: List[str] = []

        if not directory.exists():
            raise WindFlowException(
                f"Répertoire introuvable : {directory}",
                details={"error_type": "directory_not_found", "path": str(directory)},
            )

        manifest_files = list(directory.glob("*/windflow-plugin.yml"))
        logger.info(
            "batch_scan_started",
            extra={
                "directory": str(directory),
                "files_found": len(manifest_files),
            },
        )

        for manifest_file in manifest_files:
            try:
                manifest = self.validate_manifest_file(manifest_file)
                valid_manifests.append(manifest)
            except WindFlowException as exc:
                error_msg = f"{manifest_file.parent.name}: {exc.message}"
                errors.append(error_msg)
                logger.warning(
                    "batch_manifest_invalid",
                    extra={
                        "file": str(manifest_file),
                        "error": exc.message,
                    },
                )

        logger.info(
            "batch_scan_completed",
            extra={
                "valid_count": len(valid_manifests),
                "error_count": len(errors),
            },
        )

        return valid_manifests, errors
