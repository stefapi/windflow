"""
Configuration centralisée pour WindFlow Backend.

Utilise Pydantic Settings pour la gestion des variables d'environnement
avec support SQLite par défaut et PostgreSQL optionnel.
"""

import json
import logging
from typing import List, Optional, Union

from pydantic import AliasChoices, Field, field_validator
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
    jwt_secret_key: str = (
        "dev-secret-key-change-in-production-please-use-a-long-random-string-minimum-32-characters"
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = (
        15  # Short-lived access tokens for better security
    )

    # Durée de vie des refresh tokens opaques révocables (STORY-123.1).
    # Source de vérité pour la colonne refresh_tokens.expires_at —
    # remplace l'ancien refresh JWT 7 j (retiré par STORY-123.2).
    # Env var : REFRESH_TOKEN_EXPIRE_DAYS.
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Lifetime (days) of opaque revocable refresh tokens "
        "(spec 07 § Configuration, default 7 days).",
    )

    # Intervalle du job de purge des refresh tokens expirés/révoqués
    # (STORY-123.4 — boucle asyncio au lifespan, runtime asyncio unique :
    # arbitrage F1 consommé le 2026-10-02 par STORY-130).
    # Env var : REFRESH_TOKEN_PURGE_INTERVAL_HOURS.
    refresh_token_purge_interval_hours: int = Field(
        default=24,
        ge=1,
        description="Interval (hours) between refresh token purge runs "
        "(background lifespan job; logs counts only).",
    )

    # Rétention de l'audit trail (STORY-125.1). Source de vérité pour
    # AuditService.purge_expired — None = conservation indéfinie (défaut,
    # spec 15 § Rétention). Env var : AUDIT_RETENTION_DAYS.
    audit_retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Audit log retention in days (None = keep forever, "
        "spec 15 § Rétention ; e.g. 90 on RPi).",
    )

    # Intervalle du job de purge de l'audit trail (STORY-125.3 — boucle
    # asyncio au lifespan). Env var : AUDIT_PURGE_INTERVAL_HOURS.
    audit_purge_interval_hours: int = Field(
        default=24,
        ge=1,
        description="Interval (hours) between audit log purge runs "
        "(background lifespan job).",
    )

    # === Scheduler (STORY-160.1 — défauts de définition spec 17) ===
    # Fuseau IANA par défaut des définitions sans timezone explicite
    # (None = stocké NULL, résolu au runtime par le moteur). Env var :
    # SCHEDULER_DEFAULT_TIMEZONE.
    scheduler_default_timezone: Optional[str] = Field(
        default=None,
        description="Default IANA timezone for scheduled task definitions "
        "without explicit timezone (None = resolved at runtime; e.g. "
        "'Europe/Paris').",
    )
    # Politique d'erreur par défaut des définitions : ignore | retry |
    # disable (spec 17 § Scheduler core). Env var :
    # SCHEDULER_DEFAULT_ERROR_POLICY.
    scheduler_default_error_policy: str = Field(
        default="ignore",
        description="Default error policy for scheduled tasks "
        "(ignore | retry | disable, spec 17).",
    )

    # === Scheduler runtime (STORY-160.2 — moteur asyncio au lifespan,
    # arbitrage F1 : single-worker par défaut). Env var : SCHEDULER_ENABLED. ===
    # ⚠ Limite multi-workers : le verrou anti-chevauchement est en mémoire
    # process-local — avec uvicorn --workers > 1, chaque worker aurait sa
    # propre boucle et ses propres verrous (exécutions dupliquées possibles).
    # Le déploiement supporté est single-worker (default), cf. doc.
    scheduler_enabled: bool = Field(
        default=False,
        description="Start the scheduler engine loop at lifespan "
        "(single-worker only — in-memory anti-overlap lock, arbitrage F1).",
    )
    # Intervalle du tick (~30-60 s : granularité cron = minute). Env var :
    # SCHEDULER_TICK_SECONDS.
    scheduler_tick_seconds: int = Field(
        default=30,
        ge=1,
        le=3600,
        description="Interval (seconds) between scheduler engine ticks "
        "(cron granularity is the minute).",
    )
    # Timeout par exécution (défaut 10 min, spec 17 § Bonnes pratiques).
    # Env var : SCHEDULER_TASK_TIMEOUT_SECONDS.
    scheduler_task_timeout_seconds: int = Field(
        default=600,
        ge=1,
        description="Per-execution timeout (seconds) — asyncio.wait_for, "
        "the engine loop never dies (spec 17: 10 min).",
    )
    # Retentes retry max (backoff). Env var : SCHEDULER_RETRY_BACKOFF.
    scheduler_retry_backoff: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Max retries (with backoff) for error_policy='retry' "
        "definitions.",
    )

    # === Rétention des exécutions scheduler (STORY-161 — AC 4) ===
    # Rétention des lignes scheduled_task_executions. None = purge
    # désactivée (conservation infinie — pattern audit 125.3, défaut).
    # Env var : SCHEDULER_EXECUTIONS_RETENTION_DAYS.
    scheduler_executions_retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Scheduled task executions retention in days (None = "
        "purge disabled, keep forever).",
    )
    # Intervalle du job de purge des exécutions (STORY-161 — boucle
    # asyncio au lifespan, 5ᵉ tâche de fond). Env var :
    # SCHEDULER_EXECUTIONS_PURGE_INTERVAL_HOURS.
    scheduler_executions_purge_interval_hours: int = Field(
        default=24,
        ge=1,
        description="Interval (hours) between scheduled task executions "
        "purge runs (background lifespan job).",
    )

    # === Rétention des événements de déploiement (STORY-167 — AC 4) ===
    # Rétention des lignes deployment_events. None = purge désactivée
    # (conservation infinie — pattern audit 125.3 / exécutions 161,
    # défaut). Env var : DEPLOYMENT_EVENTS_RETENTION_DAYS.
    deployment_events_retention_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Deployment events retention in days (None = purge "
        "disabled, keep forever).",
    )
    # Intervalle du job de purge des événements (STORY-167 — boucle
    # asyncio dédiée au lifespan, 6ᵉ tâche de fond ; coordonnée avec
    # l'action scheduler `deployment_events.purge`, les deux délèguent
    # au même purge_expired idempotent). Env var :
    # DEPLOYMENT_EVENTS_PURGE_INTERVAL_HOURS.
    deployment_events_purge_interval_hours: int = Field(
        default=24,
        ge=1,
        description="Interval (hours) between deployment events purge "
        "runs (background lifespan job).",
    )

    @field_validator("scheduler_default_timezone")
    @classmethod
    def _validate_default_timezone(cls, value: Optional[str]) -> Optional[str]:
        """Valide le fuseau IANA par défaut au chargement (défense en
        profondeur — la validation par définition est déjà en place 160.1)."""
        if value is None:
            return None
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"scheduler_default_timezone: unknown IANA timezone {value!r}"
            ) from exc
        return value

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

    # === Cache Redis mode standard (STORY-162 — bus d'événements) ===
    # URL Redis du mode standard : active le bus Pub/Sub (canal
    # ``windflow:events``) ; réutilisée par STORY-168 (cache unifié).
    # None = mode léger in-memory (défaut, aucune connexion tentée).
    # Env var : CACHE_URL.
    cache_url: Optional[str] = Field(
        default=None,
        description="Redis URL for standard mode (event bus Pub/Sub + shared "
        "cache, e.g. redis://localhost:6379/1) — None = lightweight "
        "in-memory mode",
    )
    # Borne du fallback mémoire du cache unifié (STORY-168, AC 4) :
    # nombre maximum d'entrées conservées en mode léger — au-delà,
    # purge des expirées puis éviction FIFO de la plus ancienne insertion
    # (politique simple, consommation mémoire bornée).
    # Env var : CACHE_MEMORY_MAX_ENTRIES.
    cache_memory_max_entries: int = Field(
        default=10_000,
        gt=0,
        description="Maximum number of entries kept by the in-memory cache "
        "fallback (expired entries purged first, then FIFO eviction of the "
        "oldest insertion)",
    )

    # === Protocole WebSocket : heartbeat + acknowledgment (STORY-164.1) ===
    # Expiration des connexions muettes : le serveur ping périodiquement
    # (tous les ``ws_heartbeat_interval_seconds``) et ferme toute connexion
    # sans activité reçue (pong ou tout message client) pendant
    # ``ws_heartbeat_timeout_factor × ws_heartbeat_interval_seconds``.
    # Env var : WS_HEARTBEAT_INTERVAL_SECONDS.
    ws_heartbeat_interval_seconds: int = Field(
        default=30,
        gt=0,
        description="WebSocket server ping interval in seconds (idle expiry "
        "applies after ws_heartbeat_timeout_factor × this interval without "
        "any client activity)",
    )
    # Env var : WS_HEARTBEAT_TIMEOUT_FACTOR.
    ws_heartbeat_timeout_factor: int = Field(
        default=2,
        ge=1,
        description="Multiplier on ws_heartbeat_interval_seconds after which "
        "a silent connection is closed server-side",
    )
    # Acknowledgment des messages critiques : un message critique non
    # acquitté au-delà du TTL est journalisé en WARNING (dégradation) et
    # re-diffusé à la reconnexion du même utilisateur tant que l'entrée
    # n'a pas été purgée (purge paresseuse).
    # Env var : WS_ACK_TTL_SECONDS.
    ws_ack_ttl_seconds: int = Field(
        default=30,
        gt=0,
        description="TTL in seconds for unacknowledged critical WebSocket "
        "messages (degradation WARNING beyond, re-delivery on reconnect)",
    )
    # Env var : WS_ACK_CRITICAL_TYPES (JSON array ou comma-separated).
    ws_ack_critical_types: List[str] = Field(
        default=["DEPLOYMENT_STATUS_CHANGED", "NOTIFICATION_USER"],
        description="WebSocket event types carrying an ack id (UUID) — "
        "streaming logs, heartbeats and toasts are excluded by design",
    )

    # === Double émission WS legacy (STORY-162 — période de transition) ===
    # Borne la double diffusion des événements deployment.* sur le pont
    # WebSocket (clé canonique + ancien DEPLOYMENT_STATUS_CHANGED pour le
    # frontend). Retrait tracé STORY-253/254. Env var :
    # LEGACY_WS_EVENT_NAMES_ENABLED.
    legacy_ws_event_names_enabled: bool = Field(
        default=True,
        description="Also broadcast deployment.* events under the legacy "
        "DEPLOYMENT_STATUS_CHANGED WebSocket key (transition period, "
        "removal tracked by STORY-253/254)",
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

    # === RBAC (STORY-122.1) ===
    # TTL du cache des rôles (spec 08 — RBAC & permissions) : un changement
    # de rôle est pris en compte au plus tard après expiration, ou
    # immédiatement via l'invalidation explicite (écritures membres).
    rbac_role_cache_ttl: int = Field(
        default=300,
        description="TTL du cache des rôles RBAC en secondes (défaut : 5 minutes)",
    )

    # === Protection brute-force du login ===
    # Compteur d'échecs PAR USERNAME (distinct du rate limit volumétrique par IP)
    # — cf. docs/general_specs/07-authentification.md § Protection brute-force.
    auth_max_attempts: int = Field(
        default=5,
        description="Failed login attempts per username before lockout (brute-force protection)",
    )
    auth_lockout_seconds: int = Field(
        default=300,
        description="Lockout duration in seconds after too many failed logins",
    )
    auth_attempt_window_seconds: int = Field(
        default=600,
        description="Sliding window in seconds counting failed login attempts",
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

    # === Database seed / bootstrap (STORY-166.5) ===
    auto_detect_local_host: bool = Field(
        default=True,
        description=(
            "Détecte et seed le host local au premier démarrage (scan des "
            "capacités inclus — profil canonique host_baremetal, "
            "origin=managed). Désactivable (AUTO_DETECT_LOCAL_HOST=false) "
            "pour les installations sans substrat local : aucun host n'est "
            "créé et le scan localhost ne s'exécute pas."
        ),
    )

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

    # === Plugin Package (STORY-169.1 — download sécurisé) ===
    plugin_package_max_size_mb: int = Field(
        default=200,
        ge=1,
        description=(
            "Taille maximale en Mo d'un package plugin téléchargé — borne "
            "le streaming download et la taille d'extraction autorisée "
            "(défaut : 200 Mo, packages {name}-{version}.tar.gz spec 12)"
        ),
    )
    plugin_package_download_timeout: int = Field(
        default=60,
        ge=1,
        description=(
            "Timeout total en secondes du téléchargement d'un package "
            "plugin (cohérent avec plugin_registry_timeout=10 × marge "
            "download volumineux)"
        ),
    )

    # === Plugins Hooks ===
    plugins_base_dir: str = Field(
        default="./data/plugins/",
        description="Répertoire de base pour la résolution des chemins de scripts hooks des plugins",
    )
    plugin_hooks_enabled: bool = Field(
        default=True,
        description=(
            "Active le pont bus d'événements → hooks @on_event des plugins "
            "extension/hybrid (STORY-163)"
        ),
    )
    plugin_hooks_timeout_seconds: int = Field(
        default=30,
        description=(
            "Timeout d'exécution de chaque hook @on_event en secondes — "
            "cohérent avec HOOK_TIMEOUT_SECONDS des hooks lifecycle "
            "(plugin_lifecycle_service)"
        ),
    )
    plugin_hooks_demo_enabled: bool = Field(
        default=False,
        description=(
            "Charge le plugin démonstrateur app/plugins/examples/ au startup "
            "(désactivé par défaut — aucun comportement ajouté en production)"
        ),
    )
    # STORY-170.1 : feature flag du montage dynamique des routes API des
    # plugins (spec 11 § Extension de l'API).
    plugin_dynamic_routes_enabled: bool = Field(
        default=True,
        description=(
            "Active le montage dynamique des routes API des plugins "
            "extension/hybrid sous /api/v1/plugins/{name}/… (STORY-170.1, "
            "spec 11 § Extension de l'API) — routes préfixées, protégées "
            "JWT + RBAC core, documentées OpenAPI et démontées à la "
            "désinstallation"
        ),
    )
    # STORY-170.1 : feature flag du montage dynamique des routes API des
    # plugins (spec 11 § Extension de l'API).
    plugin_dynamic_routes_enabled: bool = Field(
        default=True,
        description=(
            "Active le montage dynamique des routes API des plugins "
            "extension/hybrid sous /api/v1/plugins/{name}/… (STORY-170.1, "
            "spec 11 § Extension de l'API) — routes préfixées, protégées "
            "JWT + RBAC core, documentées OpenAPI et démontées à la "
            "désinstallation"
        ),
    )
    # STORY-170.2 : gates pre-deploy (spec 11 § Hooks de déploiement) —
    # timeout par défaut et flag d'activation du mécanisme.
    plugin_gate_timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description=(
            "Timeout d'exécution par défaut de chaque gate pre-deploy en "
            "secondes (spec 11 — surchargeable par manifest via "
            "deploy_hooks.pre_deploy.timeout) ; au timeout, refus prudent "
            "GATE_TIMEOUT sauf on_timeout: approve"
        ),
    )
    plugin_gates_enabled: bool = Field(
        default=True,
        description=(
            "Active les gates pre-deploy des plugins extension/hybrid "
            "(STORY-170.2, spec 11 § Hooks de déploiement) — exécutées "
            "après résolution d'images, avant création des containers ; "
            "un refus s'exprime comme un échec de déploiement classique"
        ),
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
