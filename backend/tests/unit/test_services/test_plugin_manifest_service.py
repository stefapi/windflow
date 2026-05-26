"""
Tests unitaires du service PluginManifestService.

Couvre : validation de manifests, lecture de fichiers, batch,
gestion d'erreurs, edge cases et sécurité.
"""

import os
from pathlib import Path
from typing import Any, Dict

import pytest

from app.core.exceptions import WindFlowException
from app.schemas.plugin_manifest import PluginManifest
from app.services.plugin_manifest_service import PluginManifestService


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def service() -> PluginManifestService:
    """Instance du service de validation."""
    return PluginManifestService()


@pytest.fixture()
def valid_yaml_content() -> str:
    """Contenu YAML valide pour un plugin de type extension."""
    return """
name: test-plugin
version: 1.0.0
display_name: "Test Plugin"
description: "A test plugin"
category: other
author: "Test Author"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: extensions/api.py
  hooks_module: extensions/hooks.py
"""


@pytest.fixture()
def valid_service_yaml_content() -> str:
    """Contenu YAML valide pour un plugin de type service."""
    return """
name: my-service
version: 2.0.0
display_name: "My Service"
description: "A service plugin"
category: monitoring
author: "Test Author"
license: Apache-2.0
type: service
architectures:
  - linux/amd64
  - linux/arm64
compose_file: docker-compose.yml
"""


@pytest.fixture()
def valid_hybrid_yaml_content() -> str:
    """Contenu YAML valide pour un plugin de type hybrid."""
    return """
name: traefik
version: 1.2.0
display_name: "Traefik"
description: "Reverse proxy"
category: access
author: "WindFlow Team"
license: MIT
type: hybrid
architectures:
  - linux/amd64
compose_file: docker-compose.yml
extensions:
  api_module: extensions/api.py
"""


@pytest.fixture()
def tmp_plugin_dir(tmp_path: Path) -> Path:
    """Répertoire temporaire avec un manifest plugin valide."""
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    manifest_content = """
name: test-plugin
version: 1.0.0
display_name: "Test Plugin"
description: "A test plugin"
category: other
author: "Test Author"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: extensions/api.py
"""
    (plugin_dir / "windflow-plugin.yml").write_text(manifest_content, encoding="utf-8")
    return tmp_path


# ── Tests nominaux ──────────────────────────────────────────────────────────


class TestValidateManifest:
    """Tests de la méthode validate_manifest."""

    def test_validate_manifest_valid_yaml(
        self, service: PluginManifestService, valid_yaml_content: str
    ) -> None:
        """Un YAML valide retourne un PluginManifest."""
        manifest = service.validate_manifest(valid_yaml_content)
        assert isinstance(manifest, PluginManifest)
        assert manifest.name == "test-plugin"
        assert manifest.version == "1.0.0"

    def test_validate_manifest_file_valid(
        self, service: PluginManifestService, tmp_path: Path
    ) -> None:
        """Un fichier YAML valide retourne un PluginManifest."""
        manifest_file = tmp_path / "windflow-plugin.yml"
        manifest_file.write_text(
            """
name: file-plugin
version: 0.5.0
display_name: "File Plugin"
description: "From file"
category: database
author: "Author"
license: MIT
type: service
architectures:
  - linux/amd64
compose_file: docker-compose.yml
""",
            encoding="utf-8",
        )

        manifest = service.validate_manifest_file(manifest_file)
        assert manifest.name == "file-plugin"

    def test_validate_manifest_batch_valid(
        self, service: PluginManifestService, tmp_path: Path
    ) -> None:
        """Un répertoire avec des manifests valides retourne tous les manifests."""
        # Créer deux plugins valides
        for name in ["plugin-a", "plugin-b"]:
            plugin_dir = tmp_path / name
            plugin_dir.mkdir()
            (plugin_dir / "windflow-plugin.yml").write_text(
                f"""
name: {name}
version: 1.0.0
display_name: "{name}"
description: "Test"
category: other
author: "Test"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: api.py
""",
                encoding="utf-8",
            )

        manifests, errors = service.validate_manifest_batch(tmp_path)
        assert len(manifests) == 2
        assert len(errors) == 0
        names = {m.name for m in manifests}
        assert names == {"plugin-a", "plugin-b"}


# ── Tests erreurs ───────────────────────────────────────────────────────────


class TestValidateManifestErrors:
    """Tests des cas d'erreur de validation."""

    def test_validate_manifest_invalid_yaml_syntax(
        self, service: PluginManifestService
    ) -> None:
        """Un YAML malformé lève une WindFlowException."""
        bad_yaml = """
name: test
  invalid_indent: true
    broken: [1, 2
"""
        with pytest.raises(WindFlowException, match="syntaxe YAML"):
            service.validate_manifest(bad_yaml)

    def test_validate_manifest_missing_required_fields(
        self, service: PluginManifestService
    ) -> None:
        """Des champs requis manquants lèvent une WindFlowException."""
        incomplete_yaml = """
name: test-plugin
version: 1.0.0
"""
        with pytest.raises(WindFlowException, match="validation"):
            service.validate_manifest(incomplete_yaml)

    def test_validate_manifest_file_not_found(
        self, service: PluginManifestService, tmp_path: Path
    ) -> None:
        """Un fichier inexistant lève une WindFlowException."""
        missing_file = tmp_path / "nonexistent" / "windflow-plugin.yml"
        with pytest.raises(WindFlowException, match="introuvable"):
            service.validate_manifest_file(missing_file)

    def test_validate_manifest_batch_with_errors(
        self, service: PluginManifestService, tmp_path: Path
    ) -> None:
        """Un batch avec des manifests invalides retourne les erreurs."""
        # Plugin valide
        valid_dir = tmp_path / "valid-plugin"
        valid_dir.mkdir()
        (valid_dir / "windflow-plugin.yml").write_text(
            """
name: valid-plugin
version: 1.0.0
display_name: "Valid"
description: "Valid plugin"
category: other
author: "Test"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: api.py
""",
            encoding="utf-8",
        )

        # Plugin invalide (pas de compose_file pour service)
        invalid_dir = tmp_path / "invalid-plugin"
        invalid_dir.mkdir()
        (invalid_dir / "windflow-plugin.yml").write_text(
            """
name: invalid-plugin
version: 1.0.0
display_name: "Invalid"
description: "Missing compose_file"
category: other
author: "Test"
license: MIT
type: service
architectures:
  - linux/amd64
""",
            encoding="utf-8",
        )

        manifests, errors = service.validate_manifest_batch(tmp_path)
        assert len(manifests) == 1
        assert len(errors) == 1
        assert manifests[0].name == "valid-plugin"
        assert "invalid-plugin" in errors[0]


# ── Tests edge cases ────────────────────────────────────────────────────────


class TestValidateManifestEdgeCases:
    """Tests des cas limites."""

    def test_validate_manifest_empty_yaml(
        self, service: PluginManifestService
    ) -> None:
        """Un YAML vide lève une WindFlowException."""
        with pytest.raises(WindFlowException, match="vide"):
            service.validate_manifest("")

        with pytest.raises(WindFlowException, match="vide"):
            service.validate_manifest("   \n  \n")

    def test_validate_manifest_extra_fields_ignored(
        self, service: PluginManifestService
    ) -> None:
        """Des champs supplémentaires dans le YAML sont ignorés."""
        yaml_with_extras = """
name: test-plugin
version: 1.0.0
display_name: "Test"
description: "Test"
category: other
author: "Test"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: api.py
custom_unknown_field: "should be ignored"
another_extra: 42
"""
        manifest = service.validate_manifest(yaml_with_extras)
        assert manifest.name == "test-plugin"
        assert not hasattr(manifest, "custom_unknown_field")


# ── Tests sécurité ──────────────────────────────────────────────────────────


class TestValidateManifestSecurity:
    """Tests de sécurité du service."""

    def test_yaml_safe_load_no_code_execution(
        self, service: PluginManifestService
    ) -> None:
        """Les tags Python dans le YAML sont rejetés par safe_load."""
        malicious_yaml = """
name: !!python/object/apply:os.system ['echo hacked']
version: 1.0.0
display_name: "Test"
description: "Test"
category: other
author: "Test"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: api.py
"""
        # safe_load doit rejeter les tags Python
        with pytest.raises((WindFlowException, Exception)):
            service.validate_manifest(malicious_yaml)

    def test_validate_manifest_batch_directory_not_found(
        self, service: PluginManifestService
    ) -> None:
        """Un répertoire inexistant lève une WindFlowException."""
        with pytest.raises(WindFlowException, match="introuvable"):
            service.validate_manifest_batch(Path("/nonexistent/directory"))
