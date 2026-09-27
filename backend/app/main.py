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

import redis.asyncio as redis
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Rate limiting
from fastapi_limiter import FastAPILimiter
from pydantic import ValidationError
from scalar_fastapi import get_scalar_api_reference

from .api.v1 import api_router
from .config import enforce_production_secrets, settings
from .database import db
from .middleware import (
    correlation_middleware,
    error_handler_middleware,
    logging_middleware,
    security_headers_middleware,
    timing_middleware,
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

# Force SQLAlchemy engine logger to respect configured LOG_LEVEL
# This prevents SQLAlchemy from using its own handler at INFO level when echo=True
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, settings.log_level))

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

    # Setup Event Bridge
    from .websocket.event_bridge import setup_event_bridge

    setup_event_bridge()
    logger.info("✓ Event bridge initialized")

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

    # Start periodic target health check (asyncio fallback when Celery is unavailable)
    health_task: asyncio.Task | None = None
    try:
        # Import with relative paths (works regardless of entry point)
        from .database import AsyncSessionLocal as _AsyncSessionLocal
        from .services.target_service import TargetService as _TargetService

        async def _periodic_health_check() -> None:
            """Background loop: run target health check every 5 minutes."""
            while True:
                try:
                    async with _AsyncSessionLocal() as db:
                        await _TargetService.check_all_health(db)
                except Exception as exc:
                    logger.error("Periodic health check error: %s", exc)
                await asyncio.sleep(300)  # 5 minutes

        health_task = asyncio.create_task(_periodic_health_check())
        logger.info("✓ Periodic target health check started (every 5 min)")
    except Exception as e:
        logger.warning(f"✗ Periodic health check could not start: {e}")

    # Periodic refresh token purge (STORY-123.4 — boucle asyncio au
    # lifespan, sans Celery : arbitrage F1 reporté à STORY-130).
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

## Support
- Documentation: /docs
- API Reference: /redoc
- Health Check: /health
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
        {"name": "users", "description": "User account management"},
        {"name": "health", "description": "Health checks and monitoring"},
        {"name": "websocket", "description": "Real-time WebSocket connections"},
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

# 6. Error Handler (last to catch all errors)
app.middleware("http")(error_handler_middleware)

# === ROUTERS ===
app.include_router(api_router)

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

    Returns:
        Health status including database and optional services
    """
    health_status = {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
        "services": {},
    }

    # Check database
    db_healthy = await db.health_check()
    health_status["services"]["database"] = {
        "status": "healthy" if db_healthy else "unhealthy",
        "type": "sqlite" if "sqlite" in settings.database_url else "postgresql",
    }

    # Check rate limiter
    if settings.rate_limit_enabled and settings.rate_limit_storage_url:
        try:
            # Simple Redis ping
            redis_client = redis.from_url(settings.rate_limit_storage_url)
            await redis_client.ping()
            health_status["services"]["rate_limiter"] = {"status": "healthy"}
            await redis_client.close()
        except Exception:
            health_status["services"]["rate_limiter"] = {"status": "unhealthy"}

    # Global status
    if not db_healthy:
        health_status["status"] = "unhealthy"
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI validation errors."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        f"Validation error: {exc.errors()}", extra={"correlation_id": correlation_id}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "correlation_id": correlation_id,
        },
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        f"Pydantic validation error: {exc.errors()}",
        extra={"correlation_id": correlation_id},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "correlation_id": correlation_id,
        },
    )


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
