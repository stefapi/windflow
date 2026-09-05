"""
Configuration centralisée pour WindFlow Backend.

Utilise Pydantic Settings pour la gestion des variables d'environnement
avec support SQLite par défaut et PostgreSQL optionnel.
"""

import json
import logging
from typing import List, Optional, Union

from pydantic import AliasChoices, Field
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
    jwt_access_token_expire_minutes: int = (
        15  # Short-lived access tokens for better security
    )
    jwt_refresh_token_expire_days: int = 7  # Longer refresh tokens for better UX

    # Clé maîtresse de chiffrement des secrets au repos (STORY-103.1)
    # Optionnelle : si vide, la clé maîtresse dérive de jwt_secret_key
    # (aucune nouvelle variable obligatoire en dev). Le SecretManager
    # (AES-256/Fernet, PBKDF2HMAC) consomme `master_encryption_key`.
    secret_encryption_key: Optional[str] = Field(
        default=None,
        description="Master key for at-rest secret encryption (Fernet). "
        "Falls back to jwt_secret_key when unset. Generate with: "
        "`openssl rand -hex 32`",
    )

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
        "If not set, uses http://{api_host}:{api_port}",
    )

    # === CORS Configuration ===
    cors_enabled: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://localhost:8010",
        description="Allowed CORS origins (comma-separated or JSON array)",
    )
    cors_credentials: bool = Field(
        default=True, description="Allow credentials in CORS"
    )
    cors_methods: str = Field(
        default="*", description="Allowed HTTP methods (comma-separated or JSON array)"
    )
    cors_headers: str = Field(
        default="*", description="Allowed headers (comma-separated or JSON array)"
    )

    # === Security Headers (CSP) ===
    csp_enabled: bool = Field(
        default=True, description="Enable Content Security Policy"
    )
    csp_default_src: str = Field(
        default="'self'", description="CSP default-src (comma-separated or JSON array)"
    )
    csp_script_src: str = Field(
        default="'self','unsafe-inline','unsafe-eval'",
        description="CSP script-src (comma-separated or JSON array)",
    )
    csp_style_src: str = Field(
        default="'self','unsafe-inline'",
        description="CSP style-src (comma-separated or JSON array)",
    )
    csp_img_src: str = Field(
        default="'self',data:,https:",
        description="CSP img-src (comma-separated or JSON array)",
    )
    csp_connect_src: str = Field(
        default="'self'", description="CSP connect-src (comma-separated or JSON array)"
    )
    csp_report_uri: Optional[str] = Field(
        default=None, description="CSP report-uri for violations"
    )

    # === Propriétés calculées pour les listes ===
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse cors_origins into a list."""
        return self._parse_list(self.cors_origins)

    @property
    def cors_methods_list(self) -> List[str]:
        """Parse cors_methods into a list."""
        return self._parse_list(self.cors_methods)

    @property
    def cors_headers_list(self) -> List[str]:
        """Parse cors_headers into a list."""
        return self._parse_list(self.cors_headers)

    @property
    def csp_default_src_list(self) -> List[str]:
        """Parse csp_default_src into a list."""
        return self._parse_list(self.csp_default_src)

    @property
    def csp_script_src_list(self) -> List[str]:
        """Parse csp_script_src into a list."""
        return self._parse_list(self.csp_script_src)

    @property
    def csp_style_src_list(self) -> List[str]:
        """Parse csp_style_src into a list."""
        return self._parse_list(self.csp_style_src)

    @property
    def csp_img_src_list(self) -> List[str]:
        """Parse csp_img_src into a list."""
        return self._parse_list(self.csp_img_src)

    @property
    def csp_connect_src_list(self) -> List[str]:
        """Parse csp_connect_src into a list."""
        return self._parse_list(self.csp_connect_src)

    @staticmethod
    def _parse_list(value: Union[str, List[str]]) -> List[str]:
        """Parse a string value into a list (supports JSON arrays or comma-separated values)."""
        if isinstance(value, list):
            return value
        if not value:
            return []
        # Try JSON first
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        # Fall back to comma-separated
        return [item.strip() for item in value.split(",")]

    # === HSTS Configuration ===
    hsts_enabled: bool = Field(
        default=False, description="Enable HSTS (production only)"
    )
    hsts_max_age: int = Field(
        default=31536000, description="HSTS max-age in seconds (1 year)"
    )
    hsts_include_subdomains: bool = Field(
        default=True, description="Include subdomains in HSTS"
    )
    hsts_preload: bool = Field(default=False, description="Enable HSTS preload")
    frame_options: str = Field(
        default="SAMEORIGIN", description="X-Frame-Options header"
    )

    # === Rate Limiting ===
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_default: str = Field(
        default="100/minute", description="Default rate limit"
    )
    rate_limit_storage_url: Optional[str] = Field(
        default=None,
        description="Redis URL for distributed rate limiting (e.g., redis://localhost:6379/0)",
    )

    # === Performance ===
    enable_timing_middleware: bool = Field(
        default=True, description="Enable request timing middleware"
    )
    slow_request_threshold: float = Field(
        default=1.0, description="Threshold for slow request logging (seconds)"
    )
    enable_correlation_id: bool = Field(
        default=True, description="Enable correlation ID tracking"
    )

    # LiteLLM (optionnel - désactivé par défaut)
    litellm_enabled: bool = False
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # Monitoring
    prometheus_enabled: bool = True
    prometheus_multiproc_dir: Optional[str] = None

    # === Logging ===
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    log_format: str = Field(default="json", pattern="^(json|text)$")

    # Initial Admin User (pour seeding de la base de données)
    # Alias SUPERADMIN_* : nommage documenté dans env.example / .env.prod.example
    admin_email: str = Field(
        default="admin@windflow.dev",
        validation_alias=AliasChoices("admin_email", "SUPERADMIN_EMAIL"),
    )
    admin_username: str = Field(
        default="admin",
        validation_alias=AliasChoices("admin_username", "SUPERADMIN_USERNAME"),
    )
    admin_password: str = Field(
        default="changeme123",
        validation_alias=AliasChoices("admin_password", "SUPERADMIN_PASSWORD"),
    )
    admin_full_name: str = Field(
        default="Administrator",
        validation_alias=AliasChoices("admin_full_name", "SUPERADMIN_FULL_NAME"),
    )
    default_org_name: str = "Default Organization"
    default_org_slug: str = "default"

    # Stack Definitions Auto-loading
    stack_definitions_path: str = "stacks_definitions"
    auto_load_stack_definitions: bool = True
    stack_update_strategy: str = (
        "update_if_newer"  # skip_existing | update_if_newer | force_update
    )

    # === Plugin Registry ===
    plugin_registry_url: str = Field(
        default="https://registry.windflow.io/index.json",
        description="URL de l'index JSON du registre officiel des plugins",
    )
    plugin_registry_cache_ttl: int = Field(
        default=300,
        description="TTL du cache du registre en secondes (défaut : 5 minutes)",
    )
    plugin_registry_timeout: int = Field(
        default=10,
        description="Timeout HTTP pour fetch l'index du registre en secondes",
    )

    # === Plugins Hooks ===
    plugins_base_dir: str = Field(
        default="./data/plugins/",
        description="Répertoire de base pour la résolution des chemins de scripts hooks des plugins",
    )

    # Mode développement sans authentification
    # ⚠️ DANGER : Ne JAMAIS activer en production !
    # Utilise automatiquement le premier utilisateur superadmin trouvé en base
    disable_auth: bool = False

    # Helper methods
    @property
    def master_encryption_key(self) -> str:
        """Resolve the master key used by the SecretManager (Fernet)."""
        if self.secret_encryption_key:
            return self.secret_encryption_key
        return self.jwt_secret_key

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
            f"default-src {' '.join(self.csp_default_src_list)}",
            f"script-src {' '.join(self.csp_script_src_list)}",
            f"style-src {' '.join(self.csp_style_src_list)}",
            f"img-src {' '.join(self.csp_img_src_list)}",
            f"connect-src {' '.join(self.csp_connect_src_list)}",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        if self.csp_report_uri:
            policies.append(f"report-uri {self.csp_report_uri}")

        return "; ".join(policies)

    def build_server_urls(self) -> List[dict]:
        """Build server URLs for OpenAPI documentation."""
        servers = []

        if self.api_public_url:
            servers.append(
                {
                    "url": self.api_public_url,
                    "description": f"{self.environment.capitalize()} server",
                }
            )
        else:
            servers.append(
                {
                    "url": f"http://{self.api_host}:{self.api_port}",
                    "description": "Development server",
                }
            )

        return servers

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )


# Instance globale des settings
settings = Settings()


# ============================================================================
# GARDE-FOU DE DÉMARRAGE — secrets de développement interdits en production
# (STORY-101 / P0-2 : refuser les valeurs dev prédictibles en production)
# ============================================================================

# Valeurs de secret JWT connues comme étant de développement (défaut code +
# valeur documentée dans env.example). Jamais acceptées en production.
DEV_JWT_SECRET_VALUES: frozenset[str] = frozenset(
    {
        "dev-secret-key-change-in-production-please-use-a-long-random-string-minimum-32-characters",
        "dev-jwt-secret-key-change-in-production",
    }
)

# Mot de passe admin de développement (seeding par défaut).
DEV_ADMIN_PASSWORD = "changeme123"

# Longueur minimale acceptée pour le mot de passe admin en production.
MIN_ADMIN_PASSWORD_LENGTH: int = 16

# Logger dédié au garde-fou (aucune valeur de secret n'y est jamais écrite).
_guard_logger = logging.getLogger("windflow.production_guard")


def validate_production_secrets(config: "Settings") -> List[str]:
    """
    Collecte les violations de secrets de développement en production.

    Fonction pure : retourne la liste des messages de violation (vide = OK).
    Aucun contrôle hors environnement ``production`` (dev/test inchangés).

    Les messages nomment les variables d'environnement concernées et la marche
    à suivre — **jamais la valeur des secrets**.

    Args:
        config: Instance de Settings à vérifier.

    Returns:
        Liste de messages de violation (vide si conforme).
    """
    if not config.is_production:
        return []

    violations: List[str] = []

    if config.jwt_secret_key in DEV_JWT_SECRET_VALUES:
        violations.append(
            "JWT_SECRET_KEY conserve une valeur de développement connue "
            "(forgabilité des tokens). Générez une clé forte : "
            "`openssl rand -hex 32` et définissez JWT_SECRET_KEY."
        )

    # STORY-103.1 : la clé maîtresse de chiffrement des secrets, si une
    # valeur dédiée est fournie, doit elle aussi être forte en production
    # (une valeur dev connue exposerait tous les secrets au repos).
    if config.secret_encryption_key and config.secret_encryption_key in (
        DEV_JWT_SECRET_VALUES
    ):
        violations.append(
            "SECRET_ENCRYPTION_KEY conserve une valeur de développement "
            "connue (déchiffrement possible de tous les secrets au repos). "
            "Générez une clé forte : `openssl rand -hex 32`."
        )

    if config.admin_password == DEV_ADMIN_PASSWORD:
        violations.append(
            "ADMIN_PASSWORD (alias SUPERADMIN_PASSWORD) conserve le mot de passe "
            "de développement 'changeme123' (prise de contrôle immédiate). "
            "Définissez un mot de passe fort et unique."
        )
    elif len(config.admin_password) < MIN_ADMIN_PASSWORD_LENGTH:
        violations.append(
            f"ADMIN_PASSWORD (alias SUPERADMIN_PASSWORD) est trop court "
            f"(< {MIN_ADMIN_PASSWORD_LENGTH} caractères). Définissez un mot de "
            "passe d'au moins 16 caractères."
        )

    if config.disable_auth:
        violations.append(
            "DISABLE_AUTH=true est interdit en production (contourne "
            "l'authentification JWT). Définissez DISABLE_AUTH=false."
        )

    return violations


def enforce_production_secrets(config: "Settings") -> None:
    """
    Refuse le démarrage si des secrets de développement sont détectés en production.

    À appeler au startup **avant** toute connexion DB ou exposition réseau :
    lève ``RuntimeError`` avec la liste consolidée des variables concernées
    et la marche à suivre (les valeurs des secrets ne sont jamais exposées).

    Args:
        config: Instance de Settings à vérifier.

    Raises:
        RuntimeError: Si au moins un secret de développement est détecté
            en environnement production.
    """
    violations = validate_production_secrets(config)
    if not violations:
        return

    _guard_logger.critical(
        "Refus de démarrage : %d secret(s) de développement détecté(s) en "
        "production — variables concernées : %s",
        len(violations),
        "; ".join(v.split("(")[0].strip() for v in violations),
    )
    raise RuntimeError(
        "Refus de démarrage : "
        f"{len(violations)} secret(s) de développement détecté(s) en production.\n"
        + "\n".join(f"  - {violation}" for violation in violations)
        + "\nCorrigez les variables d'environnement listées ci-dessus puis "
        "redémarrez. Aucune exposition de l'API n'a eu lieu."
    )
