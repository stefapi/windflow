"""
Configuration centralisée pour WindFlow Backend.

Utilise Pydantic Settings pour la gestion des variables d'environnement
avec support SQLite par défaut et PostgreSQL optionnel.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application WindFlow."""

    # Application
    app_name: str = "WindFlow"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Base de données (SQLite par défaut, PostgreSQL optionnel)
    database_url: str = "sqlite+aiosqlite:///./data/windflow/windflow.db"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_recycle: int = 3600

    # JWT Authentication
    jwt_secret_key: str = "dev-secret-key-change-in-production-please-use-a-long-random-string-minimum-32-characters"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15  # Short-lived access tokens for better security
    jwt_refresh_token_expire_days: int = 7     # Longer refresh tokens for better UX

    # Keycloak SSO (optionnel - désactivé par défaut)
    keycloak_enabled: bool = False
    keycloak_url: Optional[str] = None
    keycloak_realm: str = "windflow"
    keycloak_client_id: str = "windflow-api"
    keycloak_client_secret: Optional[str] = None

    # HashiCorp Vault (optionnel - désactivé par défaut)
    vault_enabled: bool = False
    vault_url: Optional[str] = None
    vault_token: Optional[str] = None

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8010"
    ]

    # API
    api_prefix: str = "/api/v1"
    api_rate_limit: int = 100  # requests per minute

    # LiteLLM (optionnel - désactivé par défaut)
    litellm_enabled: bool = False
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # Monitoring
    prometheus_enabled: bool = True
    prometheus_multiproc_dir: Optional[str] = None

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Initial Admin User (pour seeding de la base de données)
    admin_email: str = "admin@windflow.dev"
    admin_username: str = "admin"
    admin_password: str = "changeme123"
    admin_full_name: str = "Administrator"
    default_org_name: str = "Default Organization"
    default_org_slug: str = "default"

    # Stack Definitions Auto-loading
    stack_definitions_path: str = "stacks_definitions"
    auto_load_stack_definitions: bool = True
    stack_update_strategy: str = "update_if_newer"  # skip_existing | update_if_newer | force_update

    # Mode développement sans authentification
    # ⚠️ DANGER : Ne JAMAIS activer en production !
    # Utilise automatiquement le premier utilisateur superadmin trouvé en base
    disable_auth: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Instance globale des settings
settings = Settings()
