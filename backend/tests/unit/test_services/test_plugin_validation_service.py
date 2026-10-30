"""
Tests unitaires du service PluginValidationService (STORY-169.2).

Couvre l'étape VALIDATE du pipeline d'installation (volet environnement) :
architecture locale (arbitrage n°7 : skip-warning hors Linux/machine non
mappable), ressources (arbitrage n°6 : stdlib + skip-warning, insuffisances
cumulées), contrainte ``windflow_version`` (réutilisation de
``validate_version_constraint``), orchestration avec court-circuit et
hygiène des logs (rules 40 — jamais de contenu YAML du manifest).
"""

import logging
import os
import platform
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from app.config import Settings
from app.core.exceptions import WindFlowException
from app.schemas.plugin_manifest import PluginManifest
from app.services import plugin_validation_service as pvs
from app.services.plugin_validation_service import PluginValidationService

# ── Fixtures & helpers ───────────────────────────────────────────────────────


@pytest.fixture()
def val_settings(tmp_path: Path) -> Settings:
    """Settings isolés : plugins_base_dir dans tmp_path (STORY-169.2)."""
    return Settings(plugins_base_dir=str(tmp_path))


@pytest.fixture()
def service(val_settings: Settings) -> PluginValidationService:
    """Instance du service de validation d'environnement."""
    return PluginValidationService(val_settings)


@pytest.fixture()
def linux_amd64(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environnement hôte simulé : Linux x86_64 (mappé ``linux/amd64``)."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")


def _build_manifest(**overrides: Any) -> PluginManifest:
    """Construit un manifest valide — base neutre : les deux plateformes,
    pas de ``resources`` ni ``windflow_version`` (cas non-arch)."""
    data: Dict[str, Any] = {
        "name": "test-plugin",
        "version": "1.0.0",
        "display_name": "Test Plugin",
        "description": "A test plugin for validation tests",
        "category": "other",
        "author": "Test Author",
        "license": "MIT",
        "type": "extension",
        "architectures": ["linux/amd64", "linux/arm64"],
        "extensions": {"api_module": "extensions/api.py"},
    }
    data.update(overrides)
    return PluginManifest(**data)


def _mock_disk(monkeypatch: pytest.MonkeyPatch, free_mb: int) -> None:
    """Simule ``shutil.disk_usage`` avec ``free_mb`` Mo disponibles."""
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=10**12, used=0, free=free_mb * 1024 * 1024),
    )


def _mock_meminfo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, available_mb: int
) -> None:
    """Écrit un faux ``/proc/meminfo`` avec ``MemAvailable`` en Mo."""
    fake = tmp_path / "meminfo"
    fake.write_text(
        f"MemTotal: 4096000 kB\nMemAvailable: {available_mb * 1024} kB\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pvs, "_MEMINFO_PATH", str(fake))


def _mock_cpu(monkeypatch: pytest.MonkeyPatch, cores: Any) -> None:
    """Simule ``os.cpu_count``."""
    monkeypatch.setattr(os, "cpu_count", lambda: cores)


# ── Cas nominaux (AC 1) ──────────────────────────────────────────────────────


class TestArchitectureNominal:
    """Vérifications nominales du check architecture."""

    def test_architecture_amd64_compatible(
        self, service: PluginValidationService, linux_amd64: None
    ) -> None:
        """Cas nominal : machine x86_64, manifest linux/amd64 → passe."""
        manifest = _build_manifest(architectures=["linux/amd64"])
        service.validate_environment(manifest)  # ne lève pas

    def test_architecture_arm64_compatible(
        self, service: PluginValidationService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cas nominal : machine aarch64, manifest linux/arm64 → passe."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.setattr(platform, "machine", lambda: "aarch64")
        manifest = _build_manifest(architectures=["linux/arm64"])
        service.validate_environment(manifest)  # ne lève pas


class TestResourcesNominal:
    """Vérifications nominales du check ressources (arbitrage n°6)."""

    def test_resources_absent_passes(
        self, service: PluginValidationService, linux_amd64: None
    ) -> None:
        """Cas nominal : manifest sans ``resources`` → passe."""
        assert _build_manifest().resources is None
        service.validate_environment(_build_manifest())  # ne lève pas

    def test_resources_sufficient_passes(
        self,
        service: PluginValidationService,
        val_settings: Settings,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Cas nominal : disk/ram/cpu au-dessus des minima → passe."""
        _mock_disk(monkeypatch, free_mb=10240)
        _mock_meminfo(monkeypatch, tmp_path, available_mb=8192)
        _mock_cpu(monkeypatch, cores=8)
        manifest = _build_manifest(
            resources={"ram_min_mb": 1024, "cpu_min_cores": 0.5, "disk_min_mb": 100}
        )
        service.validate_environment(manifest)  # ne lève pas


class TestWindflowVersionNominal:
    """Vérifications nominales du check ``windflow_version``."""

    def test_windflow_version_absent_passes(
        self, service: PluginValidationService, linux_amd64: None
    ) -> None:
        """Cas nominal : ``windflow_version=None`` → passe."""
        manifest = _build_manifest(windflow_version=None)
        service.validate_environment(manifest)  # ne lève pas

    @pytest.mark.parametrize("constraint", [">=0.1.0", "==0.1.0"])
    def test_windflow_version_satisfied_passes(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        constraint: str,
    ) -> None:
        """Cas nominal : contrainte satisfaite par la version courante
        (0.1.0) → passe."""
        manifest = _build_manifest(windflow_version=constraint)
        service.validate_environment(manifest)  # ne lève pas


# ── Cas d'erreur (AC 1 / AC 3 — rejets typés avec message explicite) ─────────


class TestArchitectureRejected:
    """Rejets du check architecture."""

    def test_architecture_incompatible_rejected(
        self,
        service: PluginValidationService,
        linux_amd64: None,
    ) -> None:
        """Cas d'erreur : machine x86_64, manifest linux/arm64 uniquement →
        ``architecture_incompatible``, message avec architecture locale et
        architectures supportées."""
        manifest = _build_manifest(architectures=["linux/arm64"])

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert exc_info.value.details.get("error_type") == "architecture_incompatible"
        assert exc_info.value.details.get("local_architecture") == "linux/amd64"
        assert exc_info.value.details.get("supported_architectures") == ["linux/arm64"]
        assert "linux/amd64" in exc_info.value.message
        assert "linux/arm64" in exc_info.value.message


class TestResourcesRejected:
    """Rejets du check ressources — insuffisances cumulées (AC 3)."""

    def test_disk_insufficient_rejected(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cas d'erreur : espace disque < disk_min_mb →
        ``insufficient_resources`` (shortcoming ``disk``)."""
        _mock_disk(monkeypatch, free_mb=50)
        manifest = _build_manifest(
            resources={"ram_min_mb": 0, "cpu_min_cores": 0.0, "disk_min_mb": 100}
        )

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert exc_info.value.details.get("error_type") == "insufficient_resources"
        shortcomings = exc_info.value.details.get("shortcomings")
        assert shortcomings == [{"resource": "disk", "required": 100, "available": 50}]

    def test_ram_insufficient_rejected(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Cas d'erreur : MemAvailable < ram_min_mb →
        ``insufficient_resources`` (shortcoming ``ram``)."""
        _mock_meminfo(monkeypatch, tmp_path, available_mb=2048)
        manifest = _build_manifest(
            resources={"ram_min_mb": 4096, "cpu_min_cores": 0.0, "disk_min_mb": 0}
        )

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert exc_info.value.details.get("error_type") == "insufficient_resources"
        shortcomings = exc_info.value.details.get("shortcomings")
        assert shortcomings == [
            {"resource": "ram", "required": 4096, "available": 2048}
        ]

    def test_cpu_insufficient_rejected(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cas d'erreur : cpu_count < cpu_min_cores →
        ``insufficient_resources`` (shortcoming ``cpu``)."""
        _mock_cpu(monkeypatch, cores=2)
        manifest = _build_manifest(
            resources={"ram_min_mb": 0, "cpu_min_cores": 4.0, "disk_min_mb": 0}
        )

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert exc_info.value.details.get("error_type") == "insufficient_resources"
        shortcomings = exc_info.value.details.get("shortcomings")
        assert shortcomings == [{"resource": "cpu", "required": 4.0, "available": 2.0}]

    def test_all_resource_shortcomings_accumulated(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """AC 3 : les 3 métriques insuffisantes → **une seule** exception
        listant les 3 shortcomings (message cumulatif)."""
        _mock_disk(monkeypatch, free_mb=50)
        _mock_meminfo(monkeypatch, tmp_path, available_mb=2048)
        _mock_cpu(monkeypatch, cores=2)
        manifest = _build_manifest(
            resources={"ram_min_mb": 4096, "cpu_min_cores": 4.0, "disk_min_mb": 100}
        )

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert exc_info.value.details.get("error_type") == "insufficient_resources"
        shortcomings = exc_info.value.details.get("shortcomings")
        assert shortcomings == [
            {"resource": "disk", "required": 100, "available": 50},
            {"resource": "ram", "required": 4096, "available": 2048},
            {"resource": "cpu", "required": 4.0, "available": 2.0},
        ]
        # Message cumulatif : chaque métrique mentionnée
        message = exc_info.value.message
        assert "disque" in message
        assert "RAM" in message
        assert "CPU" in message
        assert "Libérez" in message or "augmentez" in message


class TestWindflowVersionRejected:
    """Rejets du check ``windflow_version``."""

    def test_windflow_version_incompatible_rejected(
        self, service: PluginValidationService, linux_amd64: None
    ) -> None:
        """AC 1 : contrainte >=1.1.0 vs version courante 0.1.0 →
        ``windflow_version_incompatible``, message avec version courante +
        contrainte + suggestion de mise à jour."""
        manifest = _build_manifest(windflow_version=">=1.1.0")

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert (
            exc_info.value.details.get("error_type") == "windflow_version_incompatible"
        )
        assert exc_info.value.details.get("current_version") == "0.1.0"
        assert exc_info.value.details.get("required_constraint") == ">=1.1.0"
        message = exc_info.value.message
        assert "0.1.0" in message
        assert ">=1.1.0" in message
        assert "Mettez à jour" in message

    def test_windflow_version_equality_rejected(
        self, service: PluginValidationService, linux_amd64: None
    ) -> None:
        """Cas d'erreur : contrainte ==9.9.9 non satisfaite → rejet."""
        manifest = _build_manifest(windflow_version="==9.9.9")

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert (
            exc_info.value.details.get("error_type") == "windflow_version_incompatible"
        )


# ── Dégradations documentées (AC 3 — arbitrage n°6 : skip avec warning) ──────


class TestSkippedChecks:
    """Incapacité d'évaluer → skip avec warning, jamais de rejet (AC 3)."""

    def test_non_linux_os_skips_architecture_check(
        self,
        service: PluginValidationService,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Dégradation : OS non-Linux (Darwin) → check architecture skippé
        avec warning ``architecture_check_skipped`` (reason non_linux_os)."""
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        manifest = _build_manifest(architectures=["linux/arm64"])

        with caplog.at_level(logging.WARNING):
            service.validate_environment(manifest)  # ne lève pas

        skip_logs = [
            r
            for r in caplog.records
            if r.message == "architecture_check_skipped"
            and getattr(r, "reason", None) == "non_linux_os"
        ]
        assert skip_logs, "un warning architecture_check_skipped était attendu"

    def test_unmapped_machine_skips_architecture_check(
        self,
        service: PluginValidationService,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Dégradation : machine non mappable (riscv64) → check skippé avec
        warning (reason unmapped_machine)."""
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.setattr(platform, "machine", lambda: "riscv64")
        manifest = _build_manifest(architectures=["linux/arm64"])

        with caplog.at_level(logging.WARNING):
            service.validate_environment(manifest)  # ne lève pas

        skip_logs = [
            r
            for r in caplog.records
            if r.message == "architecture_check_skipped"
            and getattr(r, "reason", None) == "unmapped_machine"
        ]
        assert skip_logs, "un warning architecture_check_skipped était attendu"

    def test_meminfo_unavailable_skips_ram_check(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Dégradation : /proc/meminfo indisponible → RAM skippée
        (warning), disque/CPU toujours vérifiés — jamais de rejet sur
        simple incapacité d'évaluer."""
        monkeypatch.setattr(pvs, "_MEMINFO_PATH", str(tmp_path / "inexistant-meminfo"))
        _mock_disk(monkeypatch, free_mb=10240)
        _mock_cpu(monkeypatch, cores=8)
        manifest = _build_manifest(
            resources={"ram_min_mb": 999999, "cpu_min_cores": 0.5, "disk_min_mb": 100}
        )

        with caplog.at_level(logging.WARNING):
            service.validate_environment(manifest)  # ne lève pas

        skip_logs = [
            r
            for r in caplog.records
            if r.message == "resource_check_skipped"
            and getattr(r, "resource", None) == "ram"
        ]
        assert skip_logs, "un warning resource_check_skipped (ram) était attendu"

    def test_disk_usage_error_skips_disk_check(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Dégradation : shutil.disk_usage lève OSError → disque skippé
        (warning), pas de rejet."""
        monkeypatch.setattr(
            shutil,
            "disk_usage",
            lambda path: (_ for _ in ()).throw(OSError("indisponible")),
        )
        _mock_meminfo(monkeypatch, tmp_path, available_mb=8192)
        _mock_cpu(monkeypatch, cores=8)
        manifest = _build_manifest(
            resources={
                "ram_min_mb": 1024,
                "cpu_min_cores": 0.5,
                "disk_min_mb": 999999,
            }
        )

        with caplog.at_level(logging.WARNING):
            service.validate_environment(manifest)  # ne lève pas

        skip_logs = [
            r
            for r in caplog.records
            if r.message == "resource_check_skipped"
            and getattr(r, "resource", None) == "disk"
        ]
        assert skip_logs, "un warning resource_check_skipped (disk) était attendu"

    def test_cpu_count_none_skips_cpu_check(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Dégradation : os.cpu_count() → None → CPU skippé (warning)."""
        _mock_disk(monkeypatch, free_mb=10240)
        _mock_meminfo(monkeypatch, tmp_path, available_mb=8192)
        _mock_cpu(monkeypatch, cores=None)
        manifest = _build_manifest(
            resources={
                "ram_min_mb": 1024,
                "cpu_min_cores": 99.0,
                "disk_min_mb": 100,
            }
        )

        with caplog.at_level(logging.WARNING):
            service.validate_environment(manifest)  # ne lève pas

        skip_logs = [
            r
            for r in caplog.records
            if r.message == "resource_check_skipped"
            and getattr(r, "resource", None) == "cpu"
        ]
        assert skip_logs, "un warning resource_check_skipped (cpu) était attendu"


# ── Comportement transverse ──────────────────────────────────────────────────


class TestOrchestrationBehaviour:
    """Court-circuit, edge zéro et hygiène des logs."""

    def test_first_failure_short_circuits(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Ordre arbitrage n°4 : architecture ET ressources ET version
        KO → seule ``architecture_incompatible`` remonte (premier check)."""
        _mock_disk(monkeypatch, free_mb=1)
        _mock_meminfo(monkeypatch, tmp_path, available_mb=1)
        _mock_cpu(monkeypatch, cores=1)
        manifest = _build_manifest(
            architectures=["linux/arm64"],
            resources={"ram_min_mb": 9999, "cpu_min_cores": 99.0, "disk_min_mb": 9999},
            windflow_version=">=9.0.0",
        )

        with pytest.raises(WindFlowException) as exc_info:
            service.validate_environment(manifest)

        assert exc_info.value.details.get("error_type") == "architecture_incompatible"

    def test_zero_requirements_pass(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Edge : exigences à zéro → passe même si les métriques sont
        totalement indisponibles (guards ``> 0`` court-circuitent)."""
        monkeypatch.setattr(pvs, "_MEMINFO_PATH", str(tmp_path / "inexistant-meminfo"))
        monkeypatch.setattr(
            shutil,
            "disk_usage",
            lambda path: (_ for _ in ()).throw(OSError("indisponible")),
        )
        _mock_cpu(monkeypatch, cores=None)
        manifest = _build_manifest(
            resources={"ram_min_mb": 0, "cpu_min_cores": 0.0, "disk_min_mb": 0}
        )

        service.validate_environment(manifest)  # ne lève pas

    def test_logs_contain_no_manifest_content(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sécurité (rules 40) : aucun contenu YAML du manifest dans les
        entrées loggées — uniquement name/version et valeurs numériques
        (transportés via ``extra``, pas dans le corps du message)."""
        manifest = _build_manifest(
            description="DESCRIPTION-CONFIDENTIELLE-XYZ42",
            windflow_version=">=0.1.0",
        )

        with caplog.at_level(logging.INFO):
            service.validate_environment(manifest)  # succès → logs émis

        # Ni dans les messages, ni dans les extras des records
        assert "DESCRIPTION-CONFIDENTIELLE-XYZ42" not in caplog.text
        for record in caplog.records:
            assert "DESCRIPTION-CONFIDENTIELLE-XYZ42" not in str(record.__dict__)
        # Les identifiants non sensibles restent tracés (name/version)
        validated = [
            r for r in caplog.records if r.message == "plugin_environment_validated"
        ]
        assert validated
        assert getattr(validated[0], "plugin_name") == "test-plugin"
        assert getattr(validated[0], "version") == "1.0.0"

    def test_success_emits_validated_log(
        self,
        service: PluginValidationService,
        linux_amd64: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Comportement : succès → log info ``plugin_environment_validated``
        avec les trois checks."""
        with caplog.at_level(logging.INFO):
            service.validate_environment(_build_manifest())

        validated = [
            r for r in caplog.records if r.message == "plugin_environment_validated"
        ]
        assert validated
        assert getattr(validated[0], "plugin_name") == "test-plugin"
        assert getattr(validated[0], "checks") == [
            "architecture",
            "resources",
            "windflow_version",
        ]
