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

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from scalar_fastapi import get_scalar_api_reference

# Rate limiting
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

from .config import settings
from .database import db
from .api.v1 import api_router
from .middleware import (
    SecurityHeadersMiddleware,
    correlation_middleware,
    timing_middleware,
    logging_middleware,
    error_handler_middleware,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.log_format == "text"
            else '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
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
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)

    # Database initialization
    await db.connect()
    await db.create_tables()
    await db.seed_tables()
    logger.info("✓ Database initialized")

    # Setup Event Bridge
    from .websocket.event_bridge import setup_event_bridge
    setup_event_bridge()
    logger.info("✓ Event bridge initialized")

    # Initialize rate limiter (if enabled and Redis configured)
    if settings.rate_limit_enabled and settings.rate_limit_storage_url:
        try:
            redis_client = redis.from_url(
                settings.rate_limit_storage_url,
                encoding="utf-8",
                decode_responses=True
            )
            await FastAPILimiter.init(redis_client)
            logger.info(f"✓ Rate limiter initialized (Redis: {settings.rate_limit_storage_url})")
        except Exception as e:
            logger.warning(f"✗ Rate limiter initialization failed: {e}")
            logger.warning("  Continuing without rate limiting")
    elif settings.rate_limit_enabled:
        logger.warning("✗ Rate limiting enabled but RATE_LIMIT_STORAGE_URL not configured")
        logger.warning("  For production, configure Redis: RATE_LIMIT_STORAGE_URL=redis://localhost:6379/0")

    # Recover pending deployments
    try:
        from .services.deployment_orchestrator import DeploymentOrchestrator

        stats = await DeploymentOrchestrator.recover_pending_deployments(
            max_age_minutes=0,
            timeout_minutes=60
        )

        logger.info(f"✓ Deployment recovery: {stats['retried']} retried, {stats['failed']} failed")
    except Exception as e:
        logger.error(f"✗ Deployment recovery failed: {e}")

    logger.info("=" * 60)
    logger.info(f"🚀 {settings.app_name} is ready!")
    logger.info(f"   Docs: http://{settings.api_host}:{settings.api_port}/docs")
    logger.info(f"   Health: http://{settings.api_host}:{settings.api_port}/health")
    logger.info("=" * 60)

    yield

    # === SHUTDOWN ===
    logger.info("Shutting down application...")

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
    """.format(rate_limit=settings.rate_limit_default if settings.rate_limit_enabled else "Unlimited"),
    servers=settings.build_server_urls(),
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "WindFlow Support",
        "email": "support@windflow.io",
        "url": "https://windflow.io/support"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    openapi_tags=[
        {
            "name": "auth",
            "description": "Authentication and authorization endpoints"
        },
        {
            "name": "deployments",
            "description": "Docker deployment management"
        },
        {
            "name": "stacks",
            "description": "Application stack templates"
        },
        {
            "name": "organizations",
            "description": "Multi-tenant organization management"
        },
        {
            "name": "users",
            "description": "User account management"
        },
        {
            "name": "health",
            "description": "Health checks and monitoring"
        },
        {
            "name": "websocket",
            "description": "Real-time WebSocket connections"
        }
    ],
    swagger_ui_parameters={
        "syntaxHighlight.theme": "monokai",
        "displayRequestDuration": True,
        "filter": True,
        "defaultModelsExpandDepth": 1,
        "persistAuthorization": True,
    }
)

# === MIDDLEWARE CONFIGURATION ===
# ⚠️  Order is CRITICAL - see backend/app/middleware/README.md

# 1. CORS (first to receive request)
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_credentials,
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
        expose_headers=["X-Correlation-ID", "X-Process-Time"],
    )
    logger.info(f"✓ CORS enabled for origins: {settings.cors_origins}")

# 2. Security Headers
if settings.csp_enabled:
    app.add_middleware(SecurityHeadersMiddleware)
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
            "openapi": "/openapi.json"
        },
        "api": "/api/v1",
        "health": "/health"
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
        "services": {}
    }

    # Check database
    db_healthy = await db.health_check()
    health_status["services"]["database"] = {
        "status": "healthy" if db_healthy else "unhealthy",
        "type": "sqlite" if "sqlite" in settings.database_url else "postgresql"
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
        f"Validation error: {exc.errors()}",
        extra={"correlation_id": correlation_id}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "correlation_id": correlation_id
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.warning(
        f"Pydantic validation error: {exc.errors()}",
        extra={"correlation_id": correlation_id}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "correlation_id": correlation_id
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
