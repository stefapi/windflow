"""
Service de validation d'environnement pour l'installation des plugins.

Étape VALIDATE du pipeline d'installation (spec 11, § Étapes d'installation)
— volet environnement : vérifie que la machine hôte peut réellement héberger
le plugin **avant toute inscription en base ou déploiement** :

- architecture locale vs ``architectures`` déclarées au manifest ;
- ressources disponibles (disque, RAM, CPU) vs ``resources`` déclarées ;
- contrainte ``windflow_version`` vs version courante du backend
  (évaluation par réutilisation de
  ``PluginDependencyService.validate_version_constraint``).

Arbitrage n°6 de l'analyse STORY-169.2 (ressources) : **stdlib uniquement**,
aucune nouvelle dépendance — disque via ``shutil.disk_usage`` mesuré sous
``plugins_base_dir`` (emplacement réel du package extrait et des volumes
prévisibles), RAM via ``MemAvailable`` de ``/proc/meminfo``, CPU via
``os.cpu_count()``. Une métrique **non évaluable** (OS non-Linux, machine
non mappable, ``/proc/meminfo`` absent, ``cpu_count()`` à ``None``,
``plugins_base_dir`` non résolvable) entraîne un **skip avec warning**
structuré — jamais un rejet sur simple incapacité d'évaluer. Une métrique
évaluable et insuffisante entraîne un rejet typé ``insufficient_resources``
**cumulant toutes les insuffisances** en une seule erreur.

Ordre d'exécution (arbitrage n°4) : architecture → ressources →
``windflow_version``, avec court-circuit sur la première erreur.

Hors périmètre : dépendances et conflits entre plugins (déjà couverts par
``PluginDependencyService`` dans le manager) et validation de structure du
manifest (``PluginManifestService``, socle sain conservé tel quel).

Sécurité (rules 40) : le manifest est un input externe non fiable — les
logs ne contiennent **jamais** son contenu, uniquement ``name``/``version``
et les valeurs numériques de ressources (non sensibles).
"""

import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Settings
from ..core.exceptions import WindFlowException
from ..schemas.plugin_manifest import PluginManifest
from .plugin_dependency_service import PluginDependencyService

logger = logging.getLogger(__name__)

# Version courante du backend — source de vérité app.__version__
# (synchronisée avec pyproject.toml). Fallback importlib.metadata en
# défense en profondeur si l'import package échouait.
try:
    from .. import __version__ as CURRENT_WINDFLOW_VERSION
except ImportError:  # pragma: no cover — chemin de secours défensif
    from importlib.metadata import PackageNotFoundError, version

    try:
        CURRENT_WINDFLOW_VERSION = version("windflow")
    except PackageNotFoundError:
        CURRENT_WINDFLOW_VERSION = "0.0.0"

# Chemin de /proc/meminfo — constante module (patchable en tests) pour
# lire MemAvailable sans dépendance externe (arbitrage n°6).
_MEMINFO_PATH = "/proc/meminfo"


class PluginValidationService:
    """Valide la compatibilité d'un plugin avec l'environnement local.

    Consommé par ``PluginManagerService.install_plugin`` **après** la
    validation du manifest et **avant** toute inscription en base
    (étape VALIDATE de la spec 11, volet environnement).

    Un service = une classe ; ``Settings`` injecté (pattern
    ``PluginPackageService``). Toutes les erreurs sont des
    ``WindFlowException`` typées via ``details={"error_type": ...}`` avec
    un message cause + suggestion.
    """

    # Mapping machine locale (platform.machine(), minuscule) → plateforme
    # Docker complète. Toute machine absente de cette table est non
    # mappable → skip avec warning (arbitrage n°7 — postes dev
    # macOS/Windows ou architectures exotiques).
    _ARCH_ALIASES: Dict[str, str] = {
        "x86_64": "linux/amd64",
        "amd64": "linux/amd64",
        "aarch64": "linux/arm64",
        "arm64": "linux/arm64",
    }

    # Libellés lisibles des ressources pour les messages de rejet (AC 3).
    _RESOURCE_LABELS: Dict[str, str] = {
        "disk": "disque",
        "ram": "RAM",
        "cpu": "CPU",
    }

    def __init__(self, settings: Settings) -> None:
        """
        Args:
            settings: Settings de l'application (``plugins_base_dir``
                utilisé comme point de mesure de l'espace disque).
        """
        self._settings = settings

    # ── Orchestration ────────────────────────────────────────────────────

    def validate_environment(self, manifest: PluginManifest) -> None:
        """Valide que l'environnement local peut héberger le plugin.

        Exécute séquentiellement : architecture → ressources →
        ``windflow_version`` ; la **première erreur remonte**
        (court-circuit, arbitrage n°4 de l'analyse).

        Args:
            manifest: Manifest du plugin, déjà validé structurellement
                par ``PluginManifestService``.

        Raises:
            WindFlowException: ``architecture_incompatible``,
                ``insufficient_resources`` ou
                ``windflow_version_incompatible`` — message cause +
                suggestion, ``details`` typés.
        """
        self._check_architecture(manifest)
        self._check_resources(manifest)
        self._check_windflow_version(manifest)

        logger.info(
            "plugin_environment_validated",
            extra={
                "plugin_name": manifest.name,
                "version": manifest.version,
                "checks": ["architecture", "resources", "windflow_version"],
            },
        )

    # ── Check architecture (T1) ──────────────────────────────────────────

    def _check_architecture(self, manifest: PluginManifest) -> None:
        """Vérifie que la plateforme Linux locale est déclarée au manifest.

        Arbitrage n°7 : skip avec warning sur OS non-Linux ou machine non
        mappable — seul un Linux identifiable absent de la liste déclarée
        (non-vide garantie par le schéma) est rejeté.

        Args:
            manifest: Manifest du plugin (``architectures`` non vide).

        Raises:
            WindFlowException: ``architecture_incompatible`` si la
                plateforme locale est absente des architectures supportées.
        """
        system = platform.system()
        if system != "Linux":
            logger.warning(
                "architecture_check_skipped",
                extra={
                    "plugin_name": manifest.name,
                    "reason": "non_linux_os",
                    "operating_system": system,
                },
            )
            return

        machine = platform.machine().lower()
        local_architecture = self._ARCH_ALIASES.get(machine)
        if local_architecture is None:
            logger.warning(
                "architecture_check_skipped",
                extra={
                    "plugin_name": manifest.name,
                    "reason": "unmapped_machine",
                    "machine": machine,
                },
            )
            return

        supported = [arch.value for arch in manifest.architectures]
        if local_architecture not in supported:
            raise WindFlowException(
                f"Architecture incompatible : le plugin '{manifest.name}' "
                f"exige l'une des architectures {', '.join(supported)} mais "
                f"la machine locale est '{local_architecture}'. Installez un "
                f"package compatible avec cette architecture ou déployez "
                f"sur une machine adaptée.",
                details={
                    "error_type": "architecture_incompatible",
                    "plugin_name": manifest.name,
                    "local_architecture": local_architecture,
                    "supported_architectures": supported,
                },
            )

    # ── Check ressources (T2 — arbitrage n°6) ────────────────────────────

    def _check_resources(self, manifest: PluginManifest) -> None:
        """Vérifie les ressources disponibles contre les exigences déclarées.

        Arbitrage n°6 : stdlib uniquement ; chaque métrique non évaluable
        est **skippée avec warning** (jamais de rejet sur incapacité
        d'évaluer) ; les insuffisances évaluables sont **cumulées** en une
        seule erreur ``insufficient_resources`` (message unique listant
        chaque manque + suggestion).

        Args:
            manifest: Manifest du plugin (``resources`` optionnel —
                absence → passe immédiatement).

        Raises:
            WindFlowException: ``insufficient_resources`` avec la liste
                complète des ``shortcomings``
                (``resource``/``required``/``available``) si au moins une
                métrique évaluable est insuffisante.
        """
        resources = manifest.resources
        if resources is None:
            return

        shortcomings: List[Dict[str, Any]] = []

        # Disque : espace disponible sous plugins_base_dir (emplacement
        # réel du package extrait et des volumes prévisibles).
        required_disk = resources.disk_min_mb
        if required_disk > 0:
            try:
                usage = shutil.disk_usage(Path(self._settings.plugins_base_dir))
            except OSError:
                logger.warning(
                    "resource_check_skipped",
                    extra={
                        "plugin_name": manifest.name,
                        "resource": "disk",
                        "reason": "disk_usage_unavailable",
                    },
                )
            else:
                available_disk_mb = usage.free // (1024 * 1024)
                if available_disk_mb < required_disk:
                    shortcomings.append(
                        {
                            "resource": "disk",
                            "required": required_disk,
                            "available": available_disk_mb,
                        }
                    )

        # RAM : MemAvailable de /proc/meminfo (kB → Mo).
        required_ram = resources.ram_min_mb
        if required_ram > 0:
            available_ram_mb = self._read_mem_available_mb()
            if available_ram_mb is None:
                logger.warning(
                    "resource_check_skipped",
                    extra={
                        "plugin_name": manifest.name,
                        "resource": "ram",
                        "reason": "meminfo_unavailable",
                    },
                )
            elif available_ram_mb < required_ram:
                shortcomings.append(
                    {
                        "resource": "ram",
                        "required": required_ram,
                        "available": available_ram_mb,
                    }
                )

        # CPU : cœurs logiques vs cpu_min_cores (float, ex. 0.5).
        required_cpu = resources.cpu_min_cores
        if required_cpu > 0:
            cpu_count = os.cpu_count()
            if cpu_count is None:
                logger.warning(
                    "resource_check_skipped",
                    extra={
                        "plugin_name": manifest.name,
                        "resource": "cpu",
                        "reason": "cpu_count_unavailable",
                    },
                )
            elif float(cpu_count) < required_cpu:
                shortcomings.append(
                    {
                        "resource": "cpu",
                        "required": required_cpu,
                        "available": float(cpu_count),
                    }
                )

        if shortcomings:
            parts = []
            for shortcoming in shortcomings:
                resource = shortcoming["resource"]
                unit = "cœur(s)" if resource == "cpu" else "Mo"
                parts.append(
                    f"{self._RESOURCE_LABELS[resource]} : "
                    f"{shortcoming['available']:g} {unit} disponibles "
                    f"pour {shortcoming['required']:g} {unit} requis"
                )
            raise WindFlowException(
                f"Ressources insuffisantes pour installer "
                f"'{manifest.name}' : {' ; '.join(parts)}. Libérez de "
                f"l'espace disque ou augmentez les ressources de l'hôte "
                f"(RAM/CPU) avant de réessayer.",
                details={
                    "error_type": "insufficient_resources",
                    "plugin_name": manifest.name,
                    "shortcomings": shortcomings,
                },
            )

    def _read_mem_available_mb(self) -> Optional[int]:
        """Lit la mémoire disponible (``MemAvailable``) en Mo.

        Arbitrage n°6 : lecture directe de ``/proc/meminfo`` (kB → Mo),
        sans dépendance externe ; toute indisponibilité (fichier absent,
        illisible, valeur non parsable) retourne ``None`` → l'appelant
        skip la vérification RAM avec warning.

        Returns:
            Mémoire disponible en Mo, ou ``None`` si non évaluable.
        """
        try:
            content = Path(_MEMINFO_PATH).read_text(encoding="utf-8")
        except OSError:
            return None

        for line in content.splitlines():
            if line.startswith("MemAvailable:"):
                fields = line.split()
                if len(fields) < 2:
                    return None
                try:
                    available_kb = int(fields[1])
                except ValueError:
                    return None
                return available_kb // 1024
        return None

    # ── Check version WindFlow (T3) ──────────────────────────────────────

    def _check_windflow_version(self, manifest: PluginManifest) -> None:
        """Évalue la contrainte ``windflow_version`` contre la version locale.

        Réutilisation directe de
        ``PluginDependencyService.validate_version_constraint`` (le format
        de la contrainte est déjà validé par le schéma du manifest —
        pas de re-parse à écrire).

        Args:
            manifest: Manifest du plugin (``windflow_version`` optionnel
                — absence → passe immédiatement).

        Raises:
            WindFlowException: ``windflow_version_incompatible`` avec la
                version courante, la contrainte exigée et une suggestion
                de mise à jour.
        """
        constraint = manifest.windflow_version
        if constraint is None:
            return

        satisfied = PluginDependencyService.validate_version_constraint(
            CURRENT_WINDFLOW_VERSION, constraint
        )
        if not satisfied:
            raise WindFlowException(
                f"Version WindFlow insuffisante pour '{manifest.name}' : "
                f"ce plugin exige une version {constraint} mais WindFlow "
                f"installé est en {CURRENT_WINDFLOW_VERSION}. Mettez à "
                f"jour WindFlow avant d'installer ce plugin.",
                details={
                    "error_type": "windflow_version_incompatible",
                    "plugin_name": manifest.name,
                    "current_version": CURRENT_WINDFLOW_VERSION,
                    "required_constraint": constraint,
                },
            )

        logger.debug(
            "windflow_version_check_passed",
            extra={
                "plugin_name": manifest.name,
                "constraint": constraint,
                "current_version": CURRENT_WINDFLOW_VERSION,
            },
        )
