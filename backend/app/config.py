"""
Configuration centralisée pour WindFlow Backend.

Utilise Pydantic Settings pour la gestion des variables d'environnement
avec support SQLite par défaut et PostgreSQL optionnel.
"""

from typing import Optional, List
from pydantic import Field
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

    # API
    api_prefix: str = "/api/v1"
    api_host: str = "localhost"
    api_port: int = 8000

    # === API Public Configuration ===
    api_public_url: Optional[str] = Field(
        default=None,
        description="Public URL for OpenAPI docs (e.g., https://api.windflow.io). "
                   "If not set, uses http://{api_host}:{api_port}"
    )

    # === CORS Configuration ===
    cors_enabled: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000", "http://localhost:8010"],
        description="Allowed CORS origins"
    )
    cors_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_methods: List[str] = Field(default=["*"], description="Allowed HTTP methods")
    cors_headers: List[str] = Field(default=["*"], description="Allowed headers")

    # === Security Headers (CSP) ===
    csp_enabled: bool = Field(default=True, description="Enable Content Security Policy")
    csp_default_src: List[str] = Field(default=["'self'"], description="CSP default-src")
    csp_script_src: List[str] = Field(
        default=["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        description="CSP script-src (unsafe-inline and unsafe-eval needed for API docs)"
    )
    csp_style_src: List[str] = Field(
        default=["'self'", "'unsafe-inline'"],
        description="CSP style-src"
    )
    csp_img_src: List[str] = Field(
        default=["'self'", "data:", "https:"],
        description="CSP img-src"
    )
    csp_connect_src: List[str] = Field(default=["'self'"], description="CSP connect-src")
    csp_report_uri: Optional[str] = Field(default=None, description="CSP report-uri for violations")

    # === HSTS Configuration ===
    hsts_enabled: bool = Field(default=False, description="Enable HSTS (production only)")
    hsts_max_age: int = Field(default=31536000, description="HSTS max-age in seconds (1 year)")
    hsts_include_subdomains: bool = Field(default=True, description="Include subdomains in HSTS")
    hsts_preload: bool = Field(default=False, description="Enable HSTS preload")
    frame_options: str = Field(default="SAMEORIGIN", description="X-Frame-Options header")

    # === Rate Limiting ===
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_default: str = Field(default="100/minute", description="Default rate limit")
    rate_limit_storage_url: Optional[str] = Field(
        default=None,
        description="Redis URL for distributed rate limiting (e.g., redis://localhost:6379/0)"
    )

    # === Performance ===
    enable_timing_middleware: bool = Field(default=True, description="Enable request timing middleware")
    slow_request_threshold: float = Field(default=1.0, description="Threshold for slow request logging (seconds)")
    enable_correlation_id: bool = Field(default=True, description="Enable correlation ID tracking")

    # LiteLLM (optionnel - désactivé par défaut)
    litellm_enabled: bool = False
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # Monitoring
    prometheus_enabled: bool = True
    prometheus_multiproc_dir: Optional[str] = None

    # === Logging ===
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(default="json", pattern="^(json|text)$")

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

    # Helper methods
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    def build_csp_header(self) -> str:
        """Build Content Security Policy header from configuration."""
        policies = [
            f"default-src {' '.join(self.csp_default_src)}",
            f"script-src {' '.join(self.csp_script_src)}",
            f"style-src {' '.join(self.csp_style_src)}",
            f"img-src {' '.join(self.csp_img_src)}",
            f"connect-src {' '.join(self.csp_connect_src)}",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]

        if self.csp_report_uri:
            policies.append(f"report-uri {self.csp_report_uri}")

        return "; ".join(policies)

    def build_server_urls(self) -> List[dict]:
        """Build server URLs for OpenAPI documentation."""
        servers = []

        if self.api_public_url:
            servers.append({
                "url": self.api_public_url,
                "description": f"{self.environment.capitalize()} server"
            })
        else:
            servers.append({
                "url": f"http://{self.api_host}:{self.api_port}",
                "description": "Development server"
            })

        return servers

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Instance globale des settings
settings = Settings()
