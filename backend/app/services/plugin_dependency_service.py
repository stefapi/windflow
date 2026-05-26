"""
Service de résolution et validation des dépendances entre plugins.

Responsable de la vérification des dépendances à l'installation,
la détection des dépendants à la désinstallation, la résolution
transitive, la détection de cycles et la validation des contraintes de version.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from packaging.version import Version
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import WindFlowException
from ..models.plugin import Plugin
from ..schemas.plugin_manifest import (
    PluginDependencyRef,
    PluginManifest,
    parse_dependency_string,
)

logger = logging.getLogger(__name__)


# ── Modèles internes ─────────────────────────────────────────────────────────


class VersionMismatch(BaseModel):
    """Décalage de version entre exigence et installation."""

    dependency_name: str
    required_constraint: str
    installed_version: str


class DependencyCheckResult(BaseModel):
    """Résultat de la vérification des dépendances à l'installation."""

    can_proceed: bool
    satisfied: List[PluginDependencyRef] = []
    missing: List[PluginDependencyRef] = []
    version_mismatches: List[VersionMismatch] = []
    conflicts: List[str] = []


# ── Service ──────────────────────────────────────────────────────────────────


class PluginDependencyService:
    """Service dédié à la gestion des dépendances entre plugins."""

    def __init__(self, local_manifests_dir: Optional[str] = None) -> None:
        """Initialise le service.

        Args:
            local_manifests_dir: Répertoire des manifests locaux pour
                la résolution transitive. Par défaut ``dev/plugin-examples/``.
        """
        if local_manifests_dir:
            self._manifests_dir = Path(local_manifests_dir)
        else:
            # Répertoire par défaut relatif à la racine du projet
            self._manifests_dir = (
                Path(__file__).parent.parent.parent.parent
                / "dev"
                / "plugin-examples"
            )

    # ── Vérification à l'installation ──────────────────────────────────────

    async def check_install_dependencies(
        self,
        db: AsyncSession,
        manifest: PluginManifest,
        organization_id: str,
    ) -> DependencyCheckResult:
        """Vérifie que toutes les dépendances sont satisfaites pour l'installation.

        Args:
            db: Session de base de données.
            manifest: Manifest du plugin à installer.
            organization_id: ID de l'organisation.

        Returns:
            DependencyCheckResult avec le détail des dépendances.
        """
        satisfied: List[PluginDependencyRef] = []
        missing: List[PluginDependencyRef] = []
        version_mismatches: List[VersionMismatch] = []
        conflicts: List[str] = []

        # Récupérer tous les plugins installés de l'organisation
        installed_plugins = await self._get_installed_plugins(db, organization_id)
        installed_map: Dict[str, Plugin] = {p.name: p for p in installed_plugins}

        # Vérifier les dépendances requises
        if manifest.dependencies:
            for dep_ref in manifest.dependencies.get_resolved_requires():
                plugin = installed_map.get(dep_ref.name)
                if plugin is None:
                    missing.append(dep_ref)
                elif dep_ref.version_constraint:
                    if not self.validate_version_constraint(
                        plugin.version, dep_ref.version_constraint
                    ):
                        version_mismatches.append(
                            VersionMismatch(
                                dependency_name=dep_ref.name,
                                required_constraint=dep_ref.version_constraint,
                                installed_version=plugin.version,
                            )
                        )
                    else:
                        satisfied.append(dep_ref)
                else:
                    satisfied.append(dep_ref)

            # Vérifier les conflits
            for conflict_ref in manifest.dependencies.get_resolved_conflicts():
                if conflict_ref.name in installed_map:
                    conflicts.append(conflict_ref.name)

        can_proceed = (
            len(missing) == 0
            and len(version_mismatches) == 0
            and len(conflicts) == 0
        )

        logger.info(
            "dependency_check",
            extra={
                "plugin_name": manifest.name,
                "can_proceed": can_proceed,
                "satisfied_count": len(satisfied),
                "missing_count": len(missing),
                "version_mismatches_count": len(version_mismatches),
                "conflicts_count": len(conflicts),
                "organization_id": organization_id,
            },
        )

        return DependencyCheckResult(
            can_proceed=can_proceed,
            satisfied=satisfied,
            missing=missing,
            version_mismatches=version_mismatches,
            conflicts=conflicts,
        )

    # ── Vérification à la désinstallation ──────────────────────────────────

    async def check_uninstall_dependents(
        self,
        db: AsyncSession,
        plugin_name: str,
        organization_id: str,
    ) -> List[str]:
        """Retourne les noms des plugins installés qui dépendent du plugin ciblé.

        Args:
            db: Session de base de données.
            plugin_name: Nom du plugin à désinstaller.
            organization_id: ID de l'organisation.

        Returns:
            Liste des noms de plugins dépendants.
        """
        installed_plugins = await self._get_installed_plugins(db, organization_id)
        dependents: List[str] = []

        for plugin in installed_plugins:
            if plugin.name == plugin_name:
                continue

            # Extraire les dépendances du manifest_data
            manifest_data = plugin.manifest_data or {}
            deps_data = manifest_data.get("dependencies") or {}
            requires: List[str] = deps_data.get("requires", [])

            for req in requires:
                try:
                    dep_ref = parse_dependency_string(req)
                    if dep_ref.name == plugin_name:
                        dependents.append(plugin.name)
                        break
                except ValueError:
                    # Ignorer les dépendances mal formatées (déjà validées à l'install)
                    continue

        logger.info(
            "uninstall_dependents_check",
            extra={
                "plugin_name": plugin_name,
                "dependents_count": len(dependents),
                "dependents": dependents,
                "organization_id": organization_id,
            },
        )

        return dependents

    # ── Résolution transitive ──────────────────────────────────────────────

    async def resolve_transitive_dependencies(
        self,
        db: AsyncSession,
        manifest: PluginManifest,
        organization_id: str,
    ) -> List[PluginManifest]:
        """Résout les dépendances manquantes depuis les manifests locaux.

        Pour chaque dépendance manquante, cherche un manifest local dans
        le répertoire configuré (ex: ``dev/plugin-examples/*/windflow-plugin.yml``).

        Args:
            db: Session de base de données.
            manifest: Manifest du plugin à installer.
            organization_id: ID de l'organisation.

        Returns:
            Liste des manifests à installer pour résoudre les dépendances.

        Raises:
            WindFlowException: Si un manifest est introuvable localement.
        """
        installed_plugins = await self._get_installed_plugins(db, organization_id)
        installed_names: Set[str] = {p.name for p in installed_plugins}

        # Collecter les dépendances manquantes
        missing_refs: List[PluginDependencyRef] = []
        if manifest.dependencies:
            missing_refs = [
                ref
                for ref in manifest.dependencies.get_resolved_requires()
                if ref.name not in installed_names
            ]

        if not missing_refs:
            return []

        resolved: List[PluginManifest] = []
        resolved_names: Set[str] = set()
        still_missing: List[str] = []

        # Résoudre chaque dépendance manquante
        self._resolve_refs_recursive(
            missing_refs=missing_refs,
            resolved=resolved,
            resolved_names=resolved_names,
            still_missing=still_missing,
            installed_names=installed_names,
        )

        if still_missing:
            raise WindFlowException(
                f"Manifests introuvables localement pour les dépendances : "
                f"{', '.join(still_missing)}",
                details={
                    "error_type": "dependency_error",
                    "missing_dependencies": still_missing,
                },
            )

        logger.info(
            "transitive_dependencies_resolved",
            extra={
                "plugin_name": manifest.name,
                "resolved_count": len(resolved),
                "resolved_names": [r.name for r in resolved],
            },
        )

        return resolved

    def _resolve_refs_recursive(
        self,
        missing_refs: List[PluginDependencyRef],
        resolved: List[PluginManifest],
        resolved_names: Set[str],
        still_missing: List[str],
        installed_names: Set[str],
    ) -> None:
        """Résout récursivement les dépendances manquantes.

        Args:
            missing_refs: Références de dépendances à résoudre.
            resolved: Liste accumulée des manifests résolus.
            resolved_names: Noms déjà résolus (pour éviter les doublons).
            still_missing: Noms introuvables (accumulés).
            installed_names: Noms des plugins déjà installés.
        """
        for ref in missing_refs:
            if ref.name in installed_names or ref.name in resolved_names:
                continue

            # Chercher le manifest local
            manifest = self._find_local_manifest(ref.name)
            if manifest is None:
                still_missing.append(ref.name)
                continue

            resolved.append(manifest)
            resolved_names.add(manifest.name)

            # Résoudre les sous-dépendances
            if manifest.dependencies:
                sub_refs = manifest.dependencies.get_resolved_requires()
                self._resolve_refs_recursive(
                    missing_refs=sub_refs,
                    resolved=resolved,
                    resolved_names=resolved_names,
                    still_missing=still_missing,
                    installed_names=installed_names,
                )

    def _find_local_manifest(self, plugin_name: str) -> Optional[PluginManifest]:
        """Cherche un manifest local pour un plugin donné.

        Args:
            plugin_name: Nom du plugin à chercher.

        Returns:
            PluginManifest si trouvé, None sinon.
        """
        if not self._manifests_dir.exists():
            return None

        # Chercher dans dev/plugin-examples/{plugin_name}/windflow-plugin.yml
        manifest_path = self._manifests_dir / plugin_name / "windflow-plugin.yml"
        if manifest_path.exists():
            try:
                content = manifest_path.read_text(encoding="utf-8")
                return PluginManifest.from_yaml(content)
            except Exception:
                logger.warning(
                    "local_manifest_parse_error",
                    extra={"plugin_name": plugin_name, "path": str(manifest_path)},
                )
                return None

        return None

    # ── Détection de cycles ────────────────────────────────────────────────

    @staticmethod
    def detect_circular_dependencies(
        manifests: List[PluginManifest],
    ) -> List[List[str]]:
        """Détecte les cycles dans le graphe de dépendances (algorithme DFS).

        Args:
            manifests: Liste des manifests à analyser.

        Returns:
            Liste des cycles trouvés (chaque cycle est une liste de noms).
        """
        # Construire le graphe d'adjacence
        graph: Dict[str, List[str]] = {}
        for m in manifests:
            deps = []
            if m.dependencies:
                for ref in m.dependencies.get_resolved_requires():
                    deps.append(ref.name)
            graph[m.name] = deps

        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in graph:
                    # Dépendance externe, ignorer
                    continue
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Cycle détecté
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        return cycles

    # ── Validation de contrainte de version ────────────────────────────────

    @staticmethod
    def validate_version_constraint(
        installed_version: str,
        constraint: str,
    ) -> bool:
        """Évalue une contrainte de version contre la version installée.

        Supporte les opérateurs : ``>=``, ``<=``, ``>``, ``<``, ``==``, ``!=``, ``~=``.

        Args:
            installed_version: Version installée (ex: ``"1.2.0"``).
            constraint: Contrainte à évaluer (ex: ``">=1.0.0"``).

        Returns:
            True si la contrainte est satisfaite, False sinon.
        """
        # Parser l'opérateur et la version de la contrainte
        match = re.match(r"^(>=|<=|>|<|==|!=|~=)\s*(.+)$", constraint)
        if not match:
            return False

        operator = match.group(1)
        constraint_version_str = match.group(2).strip()

        try:
            installed = Version(installed_version)
            constraint_version = Version(constraint_version_str)
        except Exception:
            return False

        if operator == ">=":
            return installed >= constraint_version
        elif operator == "<=":
            return installed <= constraint_version
        elif operator == ">":
            return installed > constraint_version
        elif operator == "<":
            return installed < constraint_version
        elif operator == "==":
            return installed == constraint_version
        elif operator == "!=":
            return installed != constraint_version
        elif operator == "~=":
            # Compatible release : ~=1.1.0 signifie >=1.1.0, <1.2.0
            # ~=1.1 signifie >=1.1, <2.0
            parts = constraint_version_str.split(".")
            if len(parts) < 2:
                return installed >= constraint_version
            # Incrémenter l'avant-dernier segment
            upper_parts = parts[:-1]
            upper_parts[-1] = str(int(upper_parts[-1]) + 1)
            upper_version = Version(".".join(upper_parts))
            return installed >= constraint_version and installed < upper_version

        return False

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    async def _get_installed_plugins(
        db: AsyncSession,
        organization_id: str,
    ) -> List[Plugin]:
        """Récupère tous les plugins installés d'une organisation.

        Args:
            db: Session de base de données.
            organization_id: ID de l'organisation.

        Returns:
            Liste des plugins installés.
        """
        result = await db.execute(
            select(Plugin).where(Plugin.organization_id == organization_id)
        )
        return list(result.scalars().all())
