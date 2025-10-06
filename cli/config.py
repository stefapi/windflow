"""
Gestion de la configuration pour le CLI WindFlow.

Supporte une configuration hiérarchique avec fusion de multiples sources.
"""

from typing import Any, Dict, Optional
from pathlib import Path
import os
import yaml
from pydantic import BaseModel, Field


class CLIConfig(BaseModel):
    """Configuration du CLI WindFlow."""

    # API
    api_url: str = Field(default="http://localhost:8000", description="URL de l'API WindFlow")
    api_timeout: int = Field(default=30, description="Timeout des requêtes API en secondes")
    api_prefix: str = Field(default="/api/v1", description="Préfixe des endpoints API")

    # Auth
    auth_auto_refresh: bool = Field(default=True, description="Rafraîchir automatiquement les tokens")

    # Output
    output_format: str = Field(default="table", description="Format de sortie par défaut (table, json)")

    # Defaults
    default_organization: Optional[str] = Field(default=None, description="Organisation par défaut")
    default_environment: Optional[str] = Field(default=None, description="Environnement par défaut")

    class Config:
        extra = "allow"


class ConfigManager:
    """Gestionnaire de configuration avec sources hiérarchiques."""

    def __init__(self):
        self.config_dir = Path.home() / ".windflow"
        self.config_file = self.config_dir / "config.yaml"
        self._config: Optional[CLIConfig] = None

    def ensure_config_dir(self) -> None:
        """Assure que le répertoire de configuration existe."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> CLIConfig:
        """
        Charge la configuration depuis les sources hiérarchiques.

        Ordre de priorité (du plus bas au plus haut):
        1. Valeurs par défaut
        2. Fichier de configuration ~/.windflow/config.yaml
        3. Variables d'environnement WINDFLOW_*
        """
        if self._config is not None:
            return self._config

        # 1. Valeurs par défaut
        config_data = {}

        # 2. Fichier de configuration
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f) or {}
                config_data.update(self._flatten_config(file_config))

        # 3. Variables d'environnement
        env_config = self._load_from_env()
        config_data.update(env_config)

        self._config = CLIConfig(**config_data)
        return self._config

    def _flatten_config(self, config: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Aplatit une configuration hiérarchique."""
        result = {}
        for key, value in config.items():
            full_key = f"{prefix}_{key}" if prefix else key
            if isinstance(value, dict):
                result.update(self._flatten_config(value, full_key))
            else:
                result[full_key] = value
        return result

    def _load_from_env(self) -> Dict[str, Any]:
        """Charge la configuration depuis les variables d'environnement."""
        env_mapping = {
            "WINDFLOW_API_URL": "api_url",
            "WINDFLOW_API_TIMEOUT": "api_timeout",
            "WINDFLOW_API_PREFIX": "api_prefix",
            "WINDFLOW_OUTPUT_FORMAT": "output_format",
            "WINDFLOW_DEFAULT_ORG": "default_organization",
            "WINDFLOW_DEFAULT_ENV": "default_environment",
        }

        config = {}
        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Conversion de type si nécessaire
                if config_key == "api_timeout":
                    config[config_key] = int(value)
                elif config_key == "auth_auto_refresh":
                    config[config_key] = value.lower() in ("true", "1", "yes")
                else:
                    config[config_key] = value

        return config

    def save(self, config: CLIConfig) -> None:
        """Sauvegarde la configuration dans le fichier."""
        self.ensure_config_dir()

        config_data = {
            "api": {
                "url": config.api_url,
                "timeout": config.api_timeout,
                "prefix": config.api_prefix,
            },
            "auth": {
                "auto_refresh": config.auth_auto_refresh,
            },
            "output": {
                "format": config.output_format,
            },
            "defaults": {
                "organization": config.default_organization,
                "environment": config.default_environment,
            }
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        """Récupère une valeur de configuration."""
        config = self.load()
        return getattr(config, key, default)

    def set(self, key: str, value: Any) -> None:
        """Définit une valeur de configuration."""
        config = self.load()
        setattr(config, key, value)
        self.save(config)

    def show(self) -> Dict[str, Any]:
        """Retourne toute la configuration."""
        config = self.load()
        return config.model_dump()


# Instance globale
config_manager = ConfigManager()
