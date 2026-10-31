"""
Application FastAPI principale pour WindFlow Backend.

Enterprise-grade API with:
- Scalar API documentation
- Comprehensive security headers
- Rate limiting
- Request tracing
- Performance monitoring
"""

print("=== LOADING backend.app.main MODULE ===", flush=True)

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

import redis.asyncio as redis
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

# Rate limiting
from fastapi_limiter import FastAPILimiter
from pydantic import ValidationError
from scalar_fastapi import get_scalar_api_reference
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.v1 import api_router
from .api.v1.targets_legacy import DeprecationHeadersMiddleware
from .config import enforce_production_secrets, settings
from .core.exceptions import WindFlowException
from .database import db
from .middleware import (
    api_response_middleware,
    build_error_payload,
    correlation_middleware,
    error_handler_middleware,
    logging_middleware,
    security_headers_middleware,
    timing_middleware,
    windflow_exception_handler,
)
from .schemas.common import (
    APIResponse,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if settings.log_format == "text"
        else '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    ),
)

# BUG-004 (rules 40) : le logger "sqlalchemy.engine" à INFO journalise tout le
# SQL avec ses paramètres bindés (hash de mots de passe, key_hash, parameters
# des tâches planifiées…) quel que soit le flag `echo` des engines. Il est
# donc bridé à WARNING, sauf en LOG_LEVEL=DEBUG où l'echo SQL reste un choix
# de debug explicite (engine `echo=True` dans database.py).
logging.getLogger("sqlalchemy.engine").setLevel(
    logging.DEBUG if settings.log_level == "DEBUG" else logging.WARNING
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.

    Startup:
    - Initialize database
    - Setup event bridge
    - Initialize rate limiter
    - Recover pending deployments

    Shutdown:
    - Close database connections
    - Close Redis connections
    """
    # === STARTUP ===
    # Garde-fou sécurité (STORY-101 / P0-2) : refuser le démarrage AVANT toute
    # connexion DB ou exposition réseau si des secrets de développement sont
    # détectés en production (jwt_secret dev, admin changeme123, disable_auth).
    enforce_production_secrets(settings)

    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)

    # Database initialization — schéma par migrations Alembic uniquement
    # (STORY-120.2 : plus aucun create_all nu au démarrage)
    await db.connect()
    await db.run_migrations()
    await db.seed_tables()
    logger.info("✓ Database initialized")

    # Event bus canonique (STORY-162 — P2-2/F6) : in-memory par défaut
    # (mode léger), Redis Pub/Sub si CACHE_URL configuré et joignable.
    # Initialisé AVANT le pont WebSocket (le pont s'abonne au bus actif).
    from .core.events import init_event_bus

    await init_event_bus()
    logger.info("✓ Event bus initialized")

    # Setup Event Bridge
    from .websocket.event_bridge import setup_event_bridge

    setup_event_bridge()
    logger.info("✓ Event bridge initialized")

    # Plugin hooks bridge (STORY-163 — pont bus canonique → hooks @on_event
    # des plugins extension/hybrid) : abonnement aux 18 événements
    # canoniques uniquement (jamais les extra-canoniques sécurité) ;
    # chargement best-effort des hooks_module des plugins installés en
    # base (aucun échec de plugin ne compromet le startup). Tant que
    # STORY-169 (installation réelle) n'est pas faite, ce chargement
    # examinera zéro fichier — mécanisme posé ici.
    plugin_hooks_service_instance = None
    if settings.plugin_hooks_enabled:
        try:
            from .services.plugin_hooks_service import PluginHooksService

            plugin_hooks_service_instance = PluginHooksService()
            plugin_hooks_service_instance.start()
            loaded = await plugin_hooks_service_instance.load_installed_hooks()
            if settings.plugin_hooks_demo_enabled:
                from .plugins.examples.demo_logger_hooks import DemoLoggerHooks

                plugin_hooks_service_instance.register(DemoLoggerHooks())
                loaded += 1
                logger.info(
                    "✓ Plugin hooks demo loaded (plugin_hooks_demo_enabled=true)"
                )
            logger.info(
                f"✓ Plugin hooks service started ({loaded} plugin hook(s) loaded)"
            )
        except Exception as e:
            plugin_hooks_service_instance = None
            logger.warning(f"✗ Plugin hooks service could not start: {e}")
    else:
        logger.info("○ Plugin hooks disabled (PLUGIN_HOOKS_ENABLED=false)")

    # Plugin dynamic API routes (STORY-170.1 — spec 11 § Extension de
    # l'API) : monte les routes /api/v1/plugins/{name}/… des plugins
    # extension/hybrid installés (extensions.api_module). Best-effort :
    # un échec de plugin ne compromet jamais le startup (WARNING) ;
    # montages process-local (divergence n°6 — single-worker, arbitrage
    # F1), le démonstrateur hooks démo n'est pas étendu ici.
    if settings.plugin_dynamic_routes_enabled:
        try:
            from .services.plugin_api_router_service import (
                get_plugin_api_router_service,
            )

            plugin_router_service = get_plugin_api_router_service()
            plugin_router_service.initialize(app)
            mounted_routers = await plugin_router_service.load_installed_routers()
            logger.info(
                f"✓ Plugin dynamic routes enabled ({mounted_routers} "
                "plugin router(s) mounted)"
            )
        except Exception as e:
            logger.warning(f"✗ Plugin dynamic routes could not load: {e}")
    else:
        logger.info(
            "○ Plugin dynamic routes disabled (PLUGIN_DYNAMIC_ROUTES_ENABLED=false)"
        )

    # Plugin pre-deploy gates (STORY-170.2 — spec 11 § Hooks de
    # déploiement) : charge les gates deploy_hooks.pre_deploy des
    # plugins extension/hybrid installés dans le registre process-local.
    # Best-effort : un échec de plugin ne compromet jamais le startup
    # (WARNING) ; registre process-local (divergence n°6 — single-worker,
    # arbitrage F1), aucune gate chargée = déploiements inchangés (le
    # core ne bloque jamais par défaut).
    if settings.plugin_gates_enabled:
        try:
            from .services.plugin_gate_service import get_plugin_gate_service

            gate_service = get_plugin_gate_service()
            loaded_gates = await gate_service.load_installed_gates()
            logger.info(
                f"✓ Plugin gates enabled ({loaded_gates} plugin gate(s) loaded)"
            )
        except Exception as e:
            logger.warning(f"✗ Plugin gates could not load: {e}")
    else:
        logger.info("○ Plugin gates disabled (PLUGIN_GATES_ENABLED=false)")

    # Initialize rate limiter — 3 états observables (STORY-102 / P0-3) :
    # Redis distribué, fallback mémoire process-local, ou désactivé.
    if settings.rate_limit_enabled and settings.rate_limit_storage_url:
        try:
            redis_client = redis.from_url(
                settings.rate_limit_storage_url, encoding="utf-8", decode_responses=True
            )
            await FastAPILimiter.init(redis_client)
            # URL sans credentials (masque :password@ et ?password=)
            import re as _re

            _safe_url = _re.sub(
                r"://[^@/]+@", "://***@", settings.rate_limit_storage_url
            )
            logger.info(f"✓ Rate limiting: Redis distribué ({_safe_url})")
        except Exception as e:
            logger.warning(f"✗ Rate limiter Redis initialization failed: {e}")
            logger.warning("  Basculement en mode mémoire process-local")
    elif settings.rate_limit_enabled:
        logger.warning(
            "⚠ Rate limiting: mémoire process-local (RATE_LIMIT_STORAGE_URL absent) "
            "— compteurs non partagés entre workers"
        )
    else:
        logger.warning("⚠ Rate limiting: DÉSACTIVÉ (RATE_LIMIT_ENABLED=false)")

    # Recover pending deployments
    try:
        from .services.deployment_orchestrator import DeploymentOrchestrator

        stats = await DeploymentOrchestrator.recover_pending_deployments(
            max_age_minutes=0, timeout_minutes=60
        )

        logger.info(
            f"✓ Deployment recovery: {stats['retried']} retried, {stats['failed']} failed"
        )
    except Exception as e:
        logger.error(f"✗ Deployment recovery failed: {e}")

    # Start periodic target health check (asyncio runtime — arbitrage F1,
    # STORY-130)
    health_task: asyncio.Task | None = None
    try:
        # Import with relative paths (works regardless of entry point)
        from .database import AsyncSessionLocal as _AsyncSessionLocal
        from .services.host_service import HostService as _HostService

        async def _periodic_health_check() -> None:
            """Background loop: run target health check every 5 minutes."""
            while True:
                try:
                    async with _AsyncSessionLocal() as db:
                        await _HostService.check_all_health(db)
                except Exception as exc:
                    logger.error("Periodic health check error: %s", exc)
                await asyncio.sleep(300)  # 5 minutes

        health_task = asyncio.create_task(_periodic_health_check())
        logger.info("✓ Periodic target health check started (every 5 min)")
    except Exception as e:
        logger.warning(f"✗ Periodic health check could not start: {e}")

    # Periodic refresh token purge (STORY-123.4 — boucle asyncio au lifespan ;
    # arbitrage F1 consommé le 2026-10-02 par STORY-130, runtime asyncio unique).
    # Consomme RefreshTokenService.purge_expired() ; logs = comptages
    # uniquement (rules 40 — jamais de données sensibles).
    purge_task: asyncio.Task | None = None
    try:
        from .database import AsyncSessionLocal as _PurgeSessionLocal
        from .services.refresh_token_service import (
            RefreshTokenService as _RefreshTokenService,
        )

        _purge_interval = settings.refresh_token_purge_interval_hours * 3600

        async def _periodic_refresh_token_purge() -> None:
            """Background loop: purge expired/revoked refresh tokens."""
            while True:
                try:
                    async with _PurgeSessionLocal() as purge_db:
                        removed = await _RefreshTokenService.purge_expired(purge_db)
                    if removed:
                        logger.info("Refresh token purge: %d entries removed", removed)
                except Exception as exc:
                    logger.error("Refresh token purge error: %s", exc)
                await asyncio.sleep(_purge_interval)

        purge_task = asyncio.create_task(_periodic_refresh_token_purge())
        logger.info(
            "✓ Periodic refresh token purge started "
            f"(every {settings.refresh_token_purge_interval_hours}h)"
        )
    except Exception as e:
        logger.warning(f"✗ Periodic refresh token purge could not start: {e}")

    # Periodic audit trail purge (STORY-125.3 — boucle asyncio dédiée au
    # lifespan, pattern STORY-123.4 : intervalles et logs distincts, sans
    # fusion des deux boucles). Consomme AuditService.purge_expired() —
    # purge par âge uniquement (rules 40) ; logs = comptages uniquement.
    audit_purge_task: asyncio.Task | None = None
    if settings.audit_retention_days is None:
        # Démarrage conditionnel : rétention illimitée par défaut (spec
        # 15) — un réveil horaire ne ferait que des no-op.
        logger.info("○ Audit retention disabled (keep forever) — purge job not started")
    else:
        try:
            from .database import AsyncSessionLocal as _AuditSessionLocal
            from .services.audit_service import AuditService as _AuditService

            _audit_interval = settings.audit_purge_interval_hours * 3600

            async def _periodic_audit_purge() -> None:
                """Background loop: purge audit entries past retention."""
                while True:
                    try:
                        async with _AuditSessionLocal() as audit_db:
                            removed = await _AuditService.purge_expired(audit_db)
                        if removed:
                            logger.info("Audit purge: %d entries removed", removed)
                    except Exception as exc:
                        logger.error("Audit purge error: %s", exc)
                    await asyncio.sleep(_audit_interval)

            audit_purge_task = asyncio.create_task(_periodic_audit_purge())
            logger.info(
                "✓ Periodic audit purge started "
                f"(retention={settings.audit_retention_days}d, "
                f"every {settings.audit_purge_interval_hours}h)"
            )
        except Exception as e:
            logger.warning(f"✗ Periodic audit purge could not start: {e}")

    # Periodic scheduled task executions purge (STORY-161 — 5ᵉ tâche
    # lifespan, pattern audit 125.3 : boucle dédiée, sans fusion des
    # boucles existantes). Consomme DatabaseExecutionStore.purge_expired
    # — purge uniforme des lignes au-delà de la rétention ; l'audit est
    # gouverné séparément (jamais touché ici). Logs = comptages.
    executions_purge_task: asyncio.Task | None = None
    if settings.scheduler_executions_retention_days is None:
        # Démarrage conditionnel : rétention désactivée (défaut) — pas
        # de boucle, un réveil ne ferait que des no-op.
        logger.info(
            "○ Scheduled task executions retention disabled "
            "(keep forever) — purge job not started"
        )
    else:
        try:
            from .services.scheduler_execution_store import (
                DatabaseExecutionStore as _ExecutionsStore,
            )

            _executions_interval = (
                settings.scheduler_executions_purge_interval_hours * 3600
            )
            _executions_store = _ExecutionsStore()

            async def _periodic_executions_purge() -> None:
                """Background loop: purge executions past retention."""
                while True:
                    try:
                        removed = await _executions_store.purge_expired(
                            settings.scheduler_executions_retention_days or 1
                        )
                        if removed:
                            logger.info(
                                "Scheduled task executions purge: "
                                "%d entries removed",
                                removed,
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.error("Scheduled task executions purge error: %s", exc)
                    await asyncio.sleep(_executions_interval)

            executions_purge_task = asyncio.create_task(_periodic_executions_purge())
            logger.info(
                "✓ Periodic scheduled task executions purge started "
                f"(retention={settings.scheduler_executions_retention_days}d, "
                f"every {settings.scheduler_executions_purge_interval_hours}h)"
            )
        except Exception as e:
            logger.warning(f"✗ Periodic executions purge could not start: {e}")

    # Periodic deployment events purge (STORY-167 — 6ᵉ tâche lifespan,
    # pattern audit 125.3 / exécutions 161 : boucle dédiée, sans fusion
    # des boucles existantes). Consomme DeploymentEventStore.purge_expired
    # — purge par cutoff idempotente, coordonnée avec l'action scheduler
    # ``deployment_events.purge`` (une exécution simultanée est
    # inoffensive). Les deployments et l'audit ne sont jamais touchés.
    # Logs = comptages uniquement.
    deployment_events_purge_task: asyncio.Task | None = None
    if settings.deployment_events_retention_days is None:
        # Démarrage conditionnel : rétention désactivée (défaut) — pas
        # de boucle, un réveil ne ferait que des no-op.
        logger.info(
            "○ Deployment events retention disabled (keep forever) "
            "— purge job not started"
        )
    else:
        try:
            from .services.deployment_event_store import (
                DeploymentEventStore as _DeploymentEventsStore,
            )

            _deployment_events_interval = (
                settings.deployment_events_purge_interval_hours * 3600
            )
            _deployment_events_store = _DeploymentEventsStore()

            async def _periodic_deployment_events_purge() -> None:
                """Background loop: purge deployment events past retention."""
                while True:
                    try:
                        removed = await _deployment_events_store.purge_expired(
                            settings.deployment_events_retention_days or 1
                        )
                        if removed:
                            logger.info(
                                "Deployment events purge: %d entries removed",
                                removed,
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.error("Deployment events purge error: %s", exc)
                    await asyncio.sleep(_deployment_events_interval)

            deployment_events_purge_task = asyncio.create_task(
                _periodic_deployment_events_purge()
            )
            logger.info(
                "✓ Periodic deployment events purge started "
                f"(retention={settings.deployment_events_retention_days}d, "
                f"every {settings.deployment_events_purge_interval_hours}h)"
            )
        except Exception as e:
            logger.warning(f"✗ Periodic deployment events purge could not start: {e}")

    # Scheduler engine (STORY-160.2 — 4ᵉ tâche lifespan, arbitrage F1 :
    # runtime asyncio dans le processus API). Évalue les crons des
    # définitions spec 17 via croniter vendored et exécute les actions du
    # registre ; verrou anti-chevauchement en mémoire, orphelins récupérés
    # au démarrage. ⚠ Limite multi-workers : le verrou et le suivi des
    # échéances sont process-local — avec --workers > 1 chaque worker
    # aurait sa propre boucle (exécutions dupliquées possibles). Le
    # déploiement supporté est single-worker (défaut, arbitrage F1).
    scheduler_task: asyncio.Task | None = None
    scheduler_event_triggers = None
    if settings.scheduler_enabled:
        try:
            # Handlers d'actions (STORY-160.3) : enregistrement explicite
            # des handlers réels/stubs au registre canonique (source de
            # vérité du dispatch moteur). Au lifespan uniquement : hors
            # scheduler actif, le registre reste en état « pré-160.3 »
            # (tests moteur 160.2 : handler None → failed explicite).
            from .services.scheduler_actions import register_scheduler_actions
            from .services.scheduler_engine import SchedulerEngine

            register_scheduler_actions()

            # STORY-161 : le moteur est branché sur le store DB — les
            # exécutions (cron/event/manual) sont matérialisées dans
            # scheduled_task_executions (traçabilité spec 06/17).
            from .services.scheduler_execution_store import (
                DatabaseExecutionStore,
            )

            scheduler_engine = SchedulerEngine(
                settings=settings, store=DatabaseExecutionStore()
            )
            scheduler_task = asyncio.create_task(scheduler_engine.run())
            logger.info(
                "✓ Scheduler engine started "
                f"(tick={settings.scheduler_tick_seconds}s, "
                f"timeout={settings.scheduler_task_timeout_seconds}s)"
            )
            # Triggers événement (STORY-160.3, tâche 6) : abonnement
            # EventBus pour les définitions trigger_type="event" —
            # exécution déléguée au chemin moteur (jamais inline dans
            # la callback du bus) ; shutdown avec le moteur ci-dessous.
            from .services.scheduler_event_triggers import (
                SchedulerEventTriggers,
            )

            scheduler_event_triggers = SchedulerEventTriggers(scheduler_engine)
            scheduler_event_triggers.start()
            logger.info("✓ Scheduler event triggers subscribed to bus")
        except Exception as e:
            logger.warning(f"✗ Scheduler engine could not start: {e}")
    else:
        logger.info("○ Scheduler engine disabled (SCHEDULER_ENABLED=false)")

    logger.info("=" * 60)
    logger.info(f"🚀 {settings.app_name} is ready!")
    logger.info(f"   Docs: http://{settings.api_host}:{settings.api_port}/docs")
    logger.info(f"   Health: http://{settings.api_host}:{settings.api_port}/health")
    logger.info("=" * 60)

    yield

    # === SHUTDOWN ===
    logger.info("Shutting down application...")

    # Cancel periodic health check task
    if health_task and not health_task.done():
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass
        logger.info("✓ Periodic health check task cancelled")

    # Cancel periodic refresh token purge task
    if purge_task and not purge_task.done():
        purge_task.cancel()
        try:
            await purge_task
        except asyncio.CancelledError:
            pass
        logger.info("✓ Periodic refresh token purge task cancelled")

    # Cancel periodic audit purge task (STORY-125.3 — pas démarrée si
    # rétention illimitée : None → garde naturellement satisfaite)
    if audit_purge_task and not audit_purge_task.done():
        audit_purge_task.cancel()
        try:
            await audit_purge_task
        except asyncio.CancelledError:
            pass
        logger.info("✓ Periodic audit purge task cancelled")

    # Cancel periodic scheduled task executions purge (STORY-161 — pas
    # démarrée si rétention désactivée : None → garde satisfaite)
    if executions_purge_task and not executions_purge_task.done():
        executions_purge_task.cancel()
        try:
            await executions_purge_task
        except asyncio.CancelledError:
            pass
        logger.info("✓ Periodic scheduled task executions purge task cancelled")

    # Cancel periodic deployment events purge (STORY-167 — pas démarrée
    # si rétention désactivée : None → garde satisfaite)
    if deployment_events_purge_task and not deployment_events_purge_task.done():
        deployment_events_purge_task.cancel()
        try:
            await deployment_events_purge_task
        except asyncio.CancelledError:
            pass
        logger.info("✓ Periodic deployment events purge task cancelled")

    # Plugin hooks shutdown (STORY-163 — désabonnement du pont avant
    # l'arrêt du bus, même séquence que scheduler_event_triggers).
    if plugin_hooks_service_instance is not None:
        plugin_hooks_service_instance.stop()
        logger.info("✓ Plugin hooks service stopped")

    # Shutdown event bus (STORY-162 — arrêt du transport Redis Pub/Sub et
    # de la tâche subscriber APRÈS le désabonnement des consommateurs).
    from .core.events import shutdown_event_bus

    await shutdown_event_bus()
    logger.info("✓ Event bus shut down")

    # Close unified cache client (STORY-168 — fermeture idempotente du
    # client Redis du cache unifié RBAC/registry/LLM ; no-op en mémoire).
    from .core.cache import shutdown_cache

    await shutdown_cache()

    # Cancel scheduler engine task (STORY-160.2 — les exécutions en cours
    # sont annulées proprement et tracées failed dans l'ExecutionStore) ;
    # désabonnement des triggers événement (STORY-160.3) avant l'arrêt
    # du moteur : plus aucun événement ne peut déclencher d'exécution.
    if scheduler_event_triggers is not None:
        scheduler_event_triggers.stop()
        logger.info("✓ Scheduler event triggers unsubscribed from bus")
    if scheduler_task and not scheduler_task.done():
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("✓ Scheduler engine task cancelled")

    # Close rate limiter
    if settings.rate_limit_enabled and settings.rate_limit_storage_url:
        try:
            await FastAPILimiter.close()
            logger.info("✓ Rate limiter closed")
        except Exception:
            pass

    # Close database
    await db.disconnect()
    logger.info("✓ Database disconnected")

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## Overview
WindFlow is an intelligent Docker deployment platform with integrated AI capabilities.

## Features
- **Smart Deployments**: Deploy Docker containers and Compose stacks
- **AI Integration**: LLM-powered deployment optimization
- **Real-time Monitoring**: WebSocket-based deployment tracking
- **Stack Templates**: Pre-configured application stacks
- **Multi-tenancy**: Organization and user management
- **Role-based Access**: Granular permissions control

## Authentication
WindFlow uses JWT-based authentication:
1. Login via `/api/v1/auth/login` to get access token
2. Include token in `Authorization: Bearer <token>` header
3. Refresh tokens available for long-running sessions

## Rate Limits
- Default: {rate_limit}
- Authenticated requests have higher limits
- Rate limit info in `X-RateLimit-*` headers

## Response Envelopes (STORY-126.1, flag retiré par STORY-126.3)
All `/api/v1/*` responses are wrapped in spec-09 envelopes:

- **Success (2xx JSON)**: `{{"data": <payload>, "message": <string|null>}}`
- **Paginated lists**: `{{"data": [...], "pagination": {{"page", "per_page", "total", "pages"}}}}`
- **Errors**: `{{"error": {{"code", "message", "details"?}}, "correlation_id"?}}`
  with stable machine codes (`NOT_FOUND`, `VALIDATION_ERROR`, `CONFLICT`,
  `PERMISSION_DENIED`, `TOO_MANY_ATTEMPTS`, `INTERNAL_ERROR`, ...)

Not enveloped: `204` responses (empty body), non-JSON payloads (file exports),
`/health`, documentation pages and WebSocket channels (distinct `type`/`data`
format). See schemas `APIResponse`, `PaginatedResponse`, `ErrorResponse`,
`ErrorDetail`, `PaginationMeta` in `components.schemas`.

## Support
- Documentation: /docs
- API Reference: /redoc
- Health Check: /health (alias) and /api/v1/system/health (spec 09)
- Readiness (orchestrators: compose healthchecks, Traefik, install): /api/v1/system/ready
- GitHub: https://github.com/stefapi/windflow
    """.format(
        rate_limit=(
            settings.rate_limit_default if settings.rate_limit_enabled else "Unlimited"
        )
    ),
    servers=settings.build_server_urls(),
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "WindFlow Support",
        "email": "support@windflow.io",
        "url": "https://windflow.io/support",
    },
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "auth", "description": "Authentication and authorization endpoints"},
        {"name": "deployments", "description": "Docker deployment management"},
        {"name": "stacks", "description": "Application stack templates"},
        {
            "name": "organizations",
            "description": "Multi-tenant organization management",
        },
        {
            "name": "hosts",
            "description": (
                "Deployment hosts management (canonical surface — spec 09): "
                "CRUD, health-check, capabilities, scan, connectivity tests, "
                "SSH fingerprints (TOFU)"
            ),
        },
        {
            "name": "targets",
            "description": (
                "Deprecated alias of /api/v1/hosts (STORY-166.2) — every "
                "response carries `Deprecation: true` + `Sunset` headers. "
                "Migrate to the canonical /api/v1/hosts surface; removal "
                "planned by STORY-166.6 (plan F3)."
            ),
        },
        {"name": "users", "description": "User account management"},
        {"name": "health", "description": "Health checks and monitoring"},
        {
            "name": "system",
            "description": (
                "System health & readiness probes (no authentication) — "
                "spec 09 exemptions"
            ),
        },
        {"name": "websocket", "description": "Real-time WebSocket connections"},
        {
            "name": "metrics",
            "description": (
                "Prometheus exposition (STORY-172) — internal scrape "
                "endpoint, no authentication (spec 09 probe exemption); "
                "404 when prometheus_enabled=false"
            ),
        },
    ],
    swagger_ui_parameters={
        "syntaxHighlight.theme": "monokai",
        "displayRequestDuration": True,
        "filter": True,
        "defaultModelsExpandDepth": 1,
        "persistAuthorization": True,
    },
)

# === MIDDLEWARE CONFIGURATION ===
# ⚠️  Order is CRITICAL - see backend/app/middleware/README.md

# 0. Deprecation headers (STORY-166.2) — ASGI pur, ajouté en premier
# dans le code donc le PLUS EXTERNE de la pile : ses headers sont posés
# au plus près du protocole, après toutes les reconstructions de réponse
# (error handler, enveloppe API) — la marque de dépréciation de l'alias
# /targets survit à toute réponse, y compris les erreurs.
app.add_middleware(DeprecationHeadersMiddleware)
logger.info("✓ /targets deprecation headers middleware enabled (STORY-166.2)")

# 1. CORS (first to receive request)
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
        expose_headers=["X-Correlation-ID", "X-Process-Time"],
    )
    logger.info(f"✓ CORS enabled for origins: {settings.cors_origins_list}")

# 2. Security Headers
if settings.csp_enabled:
    app.middleware("http")(security_headers_middleware)
    logger.info("✓ Security headers middleware enabled")

# 3. Timing (must be early to wrap entire request)
if settings.enable_timing_middleware:
    app.middleware("http")(timing_middleware)
    logger.info("✓ Timing middleware enabled")

# 4. Correlation ID
if settings.enable_correlation_id:
    app.middleware("http")(correlation_middleware)
    logger.info("✓ Correlation ID middleware enabled")

# 5. Logging
app.middleware("http")(logging_middleware)

# 6. API Response Envelope (STORY-126.1) — registered BEFORE the error
#    handler in code, hence MORE INNER in the stack. On the way out,
#    correlation/timing (even more inner) have already set their headers
#    on the response — they get copied into the enveloped one. Being
#    inner, this middleware never sees the 500 responses generated by
#    the (outermost) error handler: no double envelope possible.
app.middleware("http")(api_response_middleware)

# 7. Error Handler (last to catch all errors)
app.middleware("http")(error_handler_middleware)

# === ROUTERS ===
app.include_router(api_router)


# === OPENAPI — SCHÉMAS D'ENVELOPPE (STORY-126.1, décision 8) ==========
def custom_openapi() -> dict:
    """OpenAPI enrichi des schémas d'enveloppe spec 09.

    FastAPI n'expose un modèle dans ``components.schemas`` que s'il est
    référencé par un endpoint ; les enveloppes étant un habillage
    transport (middleware, pas ``response_model``), elles sont inscrites
    manuellement ici pour rester documentées dans l'OpenAPI généré.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        contact=app.contact,
        license_info=app.license_info,
    )

    components = schema.setdefault("components", {}).setdefault("schemas", {})
    envelope_models = (
        APIResponse,
        PaginatedResponse,
        ErrorResponse,
        ErrorDetail,
        PaginationMeta,
    )
    for model in envelope_models:
        components[model.__name__] = model.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]

# === ROOT ENDPOINTS ===


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "documentation": {
            "scalar": "/docs",
            "swagger": "/swagger",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        },
        "api": "/api/v1",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    STORY-129 : la logique est factorisée dans ``SystemService`` (délegation,
    zéro duplication) et partagée avec ``/api/v1/system/health``. Le contrat
    historique est préservé à l'identique (non-régression compose/traefik/
    tests) — cette route racine reste le **alias** non enveloppé, le chemin
    canonique spec 09 est ``/api/v1/system/health``.

    Returns:
        Health status including database and optional services
    """
    # STORY-129 : délégation au service commun (comportement identique)
    from .services.system_service import SystemService

    health_status = await SystemService.get_health()
    if health_status["status"] != "healthy":
        return JSONResponse(status_code=503, content=health_status)
    return health_status


# === SCALAR API DOCUMENTATION ===


@app.get("/docs", include_in_schema=False)
async def scalar_docs():
    """
    Scalar API documentation with modern UI and code snippets.

    Scalar provides:
    - Beautiful, modern interface
    - Interactive examples
    - Code generation in multiple languages
    - Search and filtering
    """
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Reference",
        scalar_favicon_url="https://windflow.io/favicon.ico",
    )


# === EXCEPTION HANDLERS ===


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTP exceptions — enveloppe spec 09 (STORY-126.1, flag
    retiré par STORY-126.3).

    ``{"error": {"code", "message", "details"?}, "correlation_id"?}``
    avec mapping statut → code machine spec 09 (401 sur ``/auth/login``
    → ``INVALID_CREDENTIALS``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)

    # detail str → message ; detail dict → details structurés
    message: Optional[str] = None
    details: Optional[Any] = None
    if isinstance(exc.detail, dict):
        details = exc.detail
    elif exc.detail is not None:
        message = str(exc.detail)

    payload = build_error_payload(
        exc.status_code,
        message=message,
        details=details,
        path=request.url.path,
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=exc.status_code, content=payload, headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI validation errors."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        f"Validation error: {exc.errors()}", extra={"correlation_id": correlation_id}
    )

    # STORY-126.1 : erreurs Pydantic migrent de detail vers error.details
    # (flag retiré par STORY-126.3 — enveloppe systématique).
    # STORY-160.1 : jsonable_encoder requis — les validators Pydantic V2
    # placent l'objet ValueError source dans ctx.error (non sérialisable
    # JSON tel quel → 500 au lieu de 422 sinon).
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_payload(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation Error",
            details=jsonable_encoder(exc.errors()),
            path=request.url.path,
            correlation_id=correlation_id,
        ),
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        f"Pydantic validation error: {exc.errors()}",
        extra={"correlation_id": correlation_id},
    )

    # STORY-160.1 : jsonable_encoder requis (ctx.error ValueError non
    # sérialisable JSON tel quel — cf. validation_exception_handler).
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_error_payload(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Validation Error",
            details=jsonable_encoder(exc.errors()),
            path=request.url.path,
            correlation_id=correlation_id,
        ),
    )


# STORY-127 : handler global des WindFlowException (hiérarchie typée de
# core/exceptions.py) — implémentation partagée dans
# ``middleware/error_handler.py`` (réutilisée par les apps de test
# minimales). Routage Starlette par MRO : un handler sur la classe base
# attrape toutes les sous-classes. Il vit dans l'ExceptionMiddleware
# (interne), donc AVANT le error_handler_middleware externe (cf.
# ``middleware/README.md``) — une exception typée ne devient jamais un
# 500 générique.
app.add_exception_handler(WindFlowException, windflow_exception_handler)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.debug,
        reload_dirs=["backend/app"] if settings.debug else None,
        log_level=settings.log_level.lower(),
    )
