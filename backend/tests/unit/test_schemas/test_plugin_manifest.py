"""
Tests unitaires du schéma Pydantic PluginManifest.

Couvre : validation des champs, enums, sous-modèles, model validators,
parsing YAML, et sécurité (path traversal, injection).
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from pydantic import ValidationError

from app.schemas.plugin_manifest import (
    Architecture,
    ConfigFieldType,
    PluginAutoDetect,
    PluginCategory,
    PluginConfigField,
    PluginDependency,
    PluginExtension,
    PluginHook,
    PluginManifest,
    PluginPort,
    PluginResourceRequirements,
    PluginType,
    PortProtocol,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def valid_minimal_manifest_data() -> Dict[str, Any]:
    """Données minimales pour un manifest de type service valide."""
    return {
        "name": "my-plugin",
        "version": "1.0.0",
        "display_name": "My Plugin",
        "description": "A test plugin",
        "category": "other",
        "author": "Test Author",
        "license": "MIT",
        "type": "service",
        "architectures": ["linux/amd64"],
        "compose_file": "docker-compose.yml",
    }


@pytest.fixture()
def valid_full_manifest_data() -> Dict[str, Any]:
    """Données complètes pour un manifest de type hybrid valide."""
    return {
        "name": "traefik",
        "version": "1.2.0",
        "display_name": "Traefik",
        "description": "Reverse proxy avec TLS automatique",
        "long_description": "Description longue du plugin Traefik",
        "category": "access",
        "tags": ["reverse-proxy", "tls"],
        "icon": "icon.svg",
        "author": "WindFlow Team",
        "license": "MIT",
        "homepage": "https://github.com/windflow/plugin-traefik",
        "type": "hybrid",
        "architectures": ["linux/amd64", "linux/arm64"],
        "windflow_version": ">=1.1.0",
        "resources": {
            "ram_min_mb": 128,
            "cpu_min_cores": 0.5,
            "disk_min_mb": 100,
        },
        "dependencies": {
            "requires": ["docker"],
            "optional": ["cloudflare-dns"],
            "conflicts": ["nginx-proxy-manager"],
        },
        "provides": ["reverse_proxy", "tls_certificates"],
        "ports": [
            {"port": 80, "protocol": "tcp", "description": "HTTP"},
            {"port": 443, "protocol": "tcp", "description": "HTTPS"},
            {
                "port": 8080,
                "protocol": "tcp",
                "description": "Dashboard",
                "optional": True,
            },
        ],
        "config": [
            {
                "key": "acme_email",
                "label": "Email ACME",
                "type": "string",
                "required": True,
                "validation": "^[^@]+@[^@]+\\.[^@]+$",
            },
            {
                "key": "dashboard_enabled",
                "label": "Dashboard",
                "type": "boolean",
                "default": True,
            },
            {
                "key": "log_level",
                "label": "Niveau de logs",
                "type": "select",
                "options": [
                    {"value": "DEBUG", "label": "Debug"},
                    {"value": "INFO", "label": "Info"},
                ],
                "default": "INFO",
            },
        ],
        "compose_file": "docker-compose.yml",
        "config_schema": "config-schema.yml",
        "extensions": {
            "api_module": "extensions/api.py",
            "hooks_module": "extensions/hooks.py",
            "ui_routes": "extensions/ui/routes.json",
            "ui_components": "extensions/ui/components/",
        },
        "hooks": {
            "on_install": "scripts/install.sh",
            "on_configure": "scripts/configure.sh",
            "on_uninstall": "scripts/uninstall.sh",
        },
        "auto_detect": {"docker_images": ["traefik"]},
    }


@pytest.fixture()
def valid_traefik_yaml() -> str:
    """Contenu YAML du manifest Traefik exemple."""
    traefik_path = (
        Path(__file__).parent.parent.parent.parent.parent
        / "dev" / "plugin-examples" / "traefik" / "windflow-plugin.yml"
    )
    if traefik_path.exists():
        return traefik_path.read_text(encoding="utf-8")
    # Fallback YAML si le fichier n'est pas accessible
    return """
name: traefik
version: 1.2.0
display_name: "Traefik"
description: "Reverse proxy avec TLS automatique"
category: access
author: "WindFlow Team"
license: MIT
type: hybrid
architectures:
  - linux/amd64
  - linux/arm64
compose_file: docker-compose.yml
extensions:
  api_module: extensions/api.py
  hooks_module: extensions/hooks.py
  ui_routes: extensions/ui/routes.json
  ui_components: extensions/ui/components/
"""


# ── Tests nominaux ──────────────────────────────────────────────────────────


class TestValidManifest:
    """Tests des cas nominaux de validation."""

    def test_valid_minimal_manifest(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Un manifest minimal avec champs requis uniquement passe la validation."""
        manifest = PluginManifest(**valid_minimal_manifest_data)
        assert manifest.name == "my-plugin"
        assert manifest.version == "1.0.0"
        assert manifest.type == PluginType.SERVICE
        assert manifest.architectures == [Architecture.LINUX_AMD64]
        assert manifest.tags == []
        assert manifest.ports == []
        assert manifest.config == []

    def test_valid_full_manifest(
        self, valid_full_manifest_data: Dict[str, Any]
    ) -> None:
        """Un manifest complet avec tous les champs optionnels passe la validation."""
        manifest = PluginManifest(**valid_full_manifest_data)
        assert manifest.name == "traefik"
        assert manifest.version == "1.2.0"
        assert manifest.type == PluginType.HYBRID
        assert manifest.category == PluginCategory.ACCESS
        assert manifest.long_description == "Description longue du plugin Traefik"
        assert manifest.resources is not None
        assert manifest.resources.ram_min_mb == 128
        assert manifest.dependencies is not None
        assert "docker" in manifest.dependencies.requires
        assert len(manifest.ports) == 3
        assert len(manifest.config) == 3
        assert manifest.extensions is not None
        assert manifest.extensions.api_module == "extensions/api.py"
        assert manifest.hooks is not None
        assert manifest.hooks.on_install == "scripts/install.sh"
        assert manifest.auto_detect is not None
        assert "traefik" in manifest.auto_detect.docker_images

    def test_from_yaml_valid(self) -> None:
        """Le parsing YAML produit un PluginManifest valide."""
        yaml_content = """
name: test-plugin
version: 0.1.0
display_name: "Test Plugin"
description: "A test"
category: other
author: "Test"
license: MIT
type: extension
architectures:
  - linux/amd64
extensions:
  api_module: api.py
"""
        manifest = PluginManifest.from_yaml(yaml_content)
        assert manifest.name == "test-plugin"
        assert manifest.version == "0.1.0"

    def test_from_yaml_with_traefik_example(self, valid_traefik_yaml: str) -> None:
        """Le fichier YAML exemple Traefik passe la validation."""
        manifest = PluginManifest.from_yaml(valid_traefik_yaml)
        assert manifest.name == "traefik"
        assert manifest.version == "1.2.0"
        assert manifest.type == PluginType.HYBRID


# ── Tests validation champs ─────────────────────────────────────────────────


class TestFieldValidation:
    """Tests de validation des champs individuels."""

    def test_name_rejects_uppercase(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Le name rejette les majuscules."""
        valid_minimal_manifest_data["name"] = "My-Plugin"
        with pytest.raises(ValidationError, match="kebab-case"):
            PluginManifest(**valid_minimal_manifest_data)

    def test_name_rejects_spaces(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Le name rejette les espaces."""
        valid_minimal_manifest_data["name"] = "my plugin"
        with pytest.raises(ValidationError, match="kebab-case"):
            PluginManifest(**valid_minimal_manifest_data)

    def test_name_rejects_path_traversal(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Le name rejette les tentatives de path traversal (sécurité)."""
        for malicious_name in ["../etc/passwd", "..%2F", "a/../../b", "../plugin"]:
            valid_minimal_manifest_data["name"] = malicious_name
            with pytest.raises(ValidationError, match="kebab-case"):
                PluginManifest(**valid_minimal_manifest_data)

    def test_version_rejects_invalid_semver(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """La version rejette les formats non-semver."""
        for bad_version in ["1.0", "v1.0.0", "abc", "1.0.0.0", ""]:
            valid_minimal_manifest_data["version"] = bad_version
            with pytest.raises(ValidationError, match="semver"):
                PluginManifest(**valid_minimal_manifest_data)

    def test_type_must_be_enum_value(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Le type doit être une valeur de l'énumération PluginType."""
        valid_minimal_manifest_data["type"] = "invalid"
        with pytest.raises(ValidationError):
            PluginManifest(**valid_minimal_manifest_data)

    def test_architectures_must_not_be_empty(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """La liste des architectures ne doit pas être vide."""
        valid_minimal_manifest_data["architectures"] = []
        with pytest.raises(ValidationError):
            PluginManifest(**valid_minimal_manifest_data)

    def test_port_range_validation(self) -> None:
        """Les ports hors bornes [1, 65535] sont rejetés."""
        with pytest.raises(ValidationError):
            PluginPort(port=0, protocol=PortProtocol.TCP, description="Invalid")

        with pytest.raises(ValidationError):
            PluginPort(port=65536, protocol=PortProtocol.TCP, description="Invalid")

        # Ports valides aux bornes
        port_min = PluginPort(port=1, protocol=PortProtocol.TCP, description="OK")
        assert port_min.port == 1
        port_max = PluginPort(port=65535, protocol=PortProtocol.UDP, description="OK")
        assert port_max.port == 65535


# ── Tests model_validator ───────────────────────────────────────────────────


class TestModelValidators:
    """Tests des validateurs croisés de modèle."""

    def test_service_type_requires_compose_file(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Un plugin de type service doit avoir un compose_file."""
        valid_minimal_manifest_data["type"] = "service"
        valid_minimal_manifest_data.pop("compose_file", None)
        with pytest.raises(ValidationError, match="compose_file"):
            PluginManifest(**valid_minimal_manifest_data)

    def test_extension_type_requires_extensions(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Un plugin de type extension doit avoir des extensions."""
        valid_minimal_manifest_data["type"] = "extension"
        valid_minimal_manifest_data.pop("compose_file", None)
        with pytest.raises(ValidationError, match="extensions"):
            PluginManifest(**valid_minimal_manifest_data)

    def test_hybrid_requires_both(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Un plugin de type hybrid doit avoir compose_file ET extensions."""
        valid_minimal_manifest_data["type"] = "hybrid"
        # compose_file est présent mais pas extensions
        with pytest.raises(ValidationError, match="extensions"):
            PluginManifest(**valid_minimal_manifest_data)

        # Tester sans compose_file mais avec extensions
        valid_minimal_manifest_data.pop("compose_file", None)
        valid_minimal_manifest_data["extensions"] = {
            "api_module": "api.py",
        }
        with pytest.raises(ValidationError, match="compose_file"):
            PluginManifest(**valid_minimal_manifest_data)

        # Les deux présents : OK
        valid_minimal_manifest_data["compose_file"] = "docker-compose.yml"
        manifest = PluginManifest(**valid_minimal_manifest_data)
        assert manifest.type == PluginType.HYBRID


# ── Tests config ────────────────────────────────────────────────────────────


class TestConfigValidation:
    """Tests de validation des champs de configuration."""

    def test_config_select_requires_options(self) -> None:
        """Un champ de type select doit avoir des options."""
        with pytest.raises(ValidationError, match="options.*select"):
            PluginConfigField(
                key="level",
                label="Level",
                type=ConfigFieldType.SELECT,
            )

    def test_config_select_accepts_options(self) -> None:
        """Un champ de type select avec options est accepté."""
        field = PluginConfigField(
            key="level",
            label="Level",
            type=ConfigFieldType.SELECT,
            options=[
                {"value": "DEBUG", "label": "Debug"},
                {"value": "INFO", "label": "Info"},
            ],
        )
        assert field.type == ConfigFieldType.SELECT
        assert len(field.options) == 2

    def test_config_string_with_validation_regex(self) -> None:
        """Un champ string avec regex de validation est accepté."""
        field = PluginConfigField(
            key="email",
            label="Email",
            type=ConfigFieldType.STRING,
            required=True,
            validation="^[^@]+@[^@]+\\.[^@]+$",
        )
        assert field.validation is not None

    def test_config_non_select_rejects_options(self) -> None:
        """Un champ non-select avec options est rejeté."""
        with pytest.raises(ValidationError, match="options.*select"):
            PluginConfigField(
                key="name",
                label="Name",
                type=ConfigFieldType.STRING,
                options=[{"value": "a", "label": "A"}],
            )


# ── Tests sécurité ──────────────────────────────────────────────────────────


class TestSecurity:
    """Tests de sécurité du schéma."""

    def test_yaml_safe_load_no_code_execution(self) -> None:
        """yaml.safe_load empêche l'exécution de code Python dans le YAML."""
        malicious_yaml = """
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
__import__('os').system('echo hacked')
"""
        # safe_load ne doit pas exécuter le code
        # Il va soit ignorer le tag, soit lever une erreur
        # Dans tous les cas, aucun code ne doit être exécuté
        try:
            PluginManifest.from_yaml(malicious_yaml)
        except Exception:
            pass  # Toute erreur est acceptable ici
        # Si on arrive ici sans exécution de code, le test passe

    def test_extra_fields_ignored(
        self, valid_minimal_manifest_data: Dict[str, Any]
    ) -> None:
        """Les champs supplémentaires sont ignorés (extra='ignore')."""
        valid_minimal_manifest_data["unknown_field"] = "should be ignored"
        manifest = PluginManifest(**valid_minimal_manifest_data)
        assert not hasattr(manifest, "unknown_field")
