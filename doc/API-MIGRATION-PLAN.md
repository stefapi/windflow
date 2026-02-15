# WindFlow API Migration Plan - Enterprise Standards

**Version:** 1.0  
**Date:** January 2, 2026  
**Status:** Planning  
**Estimated Time:** 8-10 hours

## Overview

This document describes the complete migration plan to upgrade WindFlow's FastAPI backend to enterprise-grade standards, based on the EASI Pokai API reference implementation. The goal is to implement:

- **Scalar API Documentation** (replacing Swagger/ReDoc)
- **Security Headers** (CSP, HSTS, CORS, etc.)
- **Rate Limiting** (using fastapi-limiter)
- **Request Tracing** (Correlation IDs)
- **Performance Metrics** (Timing middleware)
- **Comprehensive API Documentation** (all endpoints and models)

## Table of Contents

1. [Dependencies and Configuration](#1-dependencies-and-configuration)
2. [Middleware Implementation](#2-middleware-implementation)
3. [Main Application Updates](#3-main-application-updates)
4. [Endpoint Documentation Standards](#4-endpoint-documentation-standards)
5. [Model Documentation Standards](#5-model-documentation-standards)
6. [Testing Strategy](#6-testing-strategy)
7. [Implementation Checklist](#7-implementation-checklist)

---

## 1. Dependencies and Configuration

### 1.1 New Dependencies

Add to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
scalar-fastapi = "^1.0.3"      # Modern API documentation
fastapi-limiter = "^0.1.6"     # Rate limiting
redis = "^5.0.0"                # For distributed rate limiting
```

Install:
```bash
poetry add scalar-fastapi fastapi-limiter redis
```

### 1.2 Configuration Updates

**File:** `backend/app/config.py`

Add new configuration sections:

```python
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Existing configs...
    
    # === API Public Configuration ===
    api_public_url: Optional[str] = Field(
        default=None,
        description="Public URL for OpenAPI docs (e.g., https://api.windflow.io). "
                   "If not set, uses http://{api_host}:{api_port}"
    )
    
    # === CORS Configuration ===
    cors_enabled: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins"
    )
    cors_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_methods: List[str] = Field(default=["*"], description="Allowed HTTP methods")
    cors_headers: List[str] = Field(default=["*"], description="Allowed headers")
    
    # === Security Headers (CSP) ===
    csp_enabled: bool = Field(default=True, description="Enable Content Security Policy")
    csp_default_src: List[str] = Field(default=["'self'"], description="CSP default-src")
    csp_script_src: List[str] = Field(
        default=["'self'", "'unsafe-inline'"],
        description="CSP script-src (unsafe-inline needed for API docs)"
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
    hsts_enabled: bool = Field(default=True, description="Enable HSTS (production only)")
    hsts_max_age: int = Field(default=31536000, description="HSTS max-age in seconds (1 year)")
    frame_options: str = Field(default="DENY", description="X-Frame-Options header")
    
    # === Rate Limiting ===
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_default: str = Field(default="100/minute", description="Default rate limit")
    rate_limit_storage_url: Optional[str] = Field(
        default=None,
        description="Redis URL for distributed rate limiting (e.g., redis://localhost:6379/0)"
    )
    
    # === Performance ===
    enable_timing_middleware: bool = Field(default=True, description="Enable timing middleware")
    enable_correlation_id: bool = Field(default=True, description="Enable correlation ID tracking")
    
    # === Logging ===
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(default="json", pattern="^(json|text)$")
    
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
```

### 1.3 Environment Variables

**File:** `env.example`

Add new variables:

```bash
# === API Configuration ===
API_PUBLIC_URL=https://api.windflow.io  # Production URL (optional)

# === CORS Configuration ===
CORS_ENABLED=true
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
CORS_CREDENTIALS=true

# === Security Headers ===
CSP_ENABLED=true
CSP_DEFAULT_SRC=["'self'"]
CSP_SCRIPT_SRC=["'self'","'unsafe-inline'"]
CSP_STYLE_SRC=["'self'","'unsafe-inline'"]
CSP_IMG_SRC=["'self'","data:","https:"]
CSP_CONNECT_SRC=["'self'"]
CSP_REPORT_URI=  # Optional CSP violation reporting endpoint

HSTS_ENABLED=true
HSTS_MAX_AGE=31536000
FRAME_OPTIONS=DENY

# === Rate Limiting ===
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/0  # For production

# === Performance ===
ENABLE_TIMING_MIDDLEWARE=true
ENABLE_CORRELATION_ID=true

# === Logging ===
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 2. Middleware Implementation

### 2.1 Directory Structure

Create middleware directory:

```
backend/app/middleware/
├── __init__.py
├── security.py         # Security headers middleware
├── correlation.py      # Correlation ID middleware
├── timing.py          # Performance timing middleware
└── README.md          # Middleware documentation
```

### 2.2 Security Headers Middleware

**File:** `backend/app/middleware/security.py`

```python
"""Security headers middleware including CSP, HSTS, and other security headers."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add comprehensive security headers to all responses.
    
    Implements:
    - Content Security Policy (CSP)
    - HTTP Strict Transport Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Content Security Policy
        if settings.csp_enabled:
            response.headers["Content-Security-Policy"] = settings.build_csp_header()

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Clickjacking protection
        response.headers["X-Frame-Options"] = settings.frame_options
        
        # XSS Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS (only in production with HTTPS)
        if settings.hsts_enabled and settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.hsts_max_age}; includeSubDomains; preload"
            )

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (restrict browser features)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        return response
```

### 2.3 Correlation ID Middleware

**File:** `backend/app/middleware/correlation.py`

```python
"""Correlation ID middleware for distributed request tracing."""

import logging
from uuid import uuid4
from fastapi import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)


async def correlation_middleware(request: Request, call_next) -> Response:
    """
    Add correlation ID to requests for distributed tracing.
    
    - Reads X-Correlation-ID from request headers or generates a new UUID
    - Adds correlation ID to response headers
    - Stores correlation ID in request.state for logging
    
    This allows tracking requests across multiple services and log aggregation.
    """
    # Get existing correlation ID or generate new one
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid4())
    
    # Store in request state for access in endpoints and logging
    request.state.correlation_id = correlation_id

    # Process request
    response = await call_next(request)
    
    # Add to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response
```

### 2.4 Timing Middleware

**File:** `backend/app/middleware/timing.py`

```python
"""Performance timing middleware for monitoring request duration."""

import time
import logging
from fastapi import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)


async def timing_middleware(request: Request, call_next) -> Response:
    """
    Measure request processing time.
    
    - Adds X-Process-Time header to response
    - Logs slow requests (>1s) as warnings
    - Useful for performance monitoring and optimization
    """
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    process_time_ms = process_time * 1000
    
    # Add to response headers
    response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"
    
    # Log slow requests
    if process_time > 1.0:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.warning(
            f"Slow request detected: {request.method} {request.url.path} "
            f"took {process_time_ms:.2f}ms",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "process_time_ms": process_time_ms
            }
        )
    
    return response
```

### 2.5 Middleware Package

**File:** `backend/app/middleware/__init__.py`

```python
"""Middleware package for WindFlow API."""

from .security import SecurityHeadersMiddleware
from .correlation import correlation_middleware
from .timing import timing_middleware

# Existing middlewares
from .logging import logging_middleware
from .error_handling import error_handler_middleware

__all__ = [
    "SecurityHeadersMiddleware",
    "correlation_middleware",
    "timing_middleware",
    "logging_middleware",
    "error_handler_middleware",
]
```

### 2.6 Middleware Documentation

**File:** `backend/app/middleware/README.md`

```markdown
# WindFlow API Middlewares

## Overview

Middlewares are executed in a specific order for each request. Understanding this order is critical for proper functionality.

## Middleware Order

Middlewares are applied in **reverse order** from how they appear in code. The **last** middleware added is the **first** to execute.

### Execution Order (Request → Response)

```
Request
  ↓
1. CORS Middleware (first to receive request)
  ↓
2. Security Headers Middleware
  ↓
3. Timing Middleware (starts timer)
  ↓
4. Correlation ID Middleware
  ↓
5. Logging Middleware
  ↓
6. Error Handler Middleware
  ↓
7. Route Handler (endpoint function)
  ↓
6. Error Handler Middleware (catches exceptions)
  ↓
5. Logging Middleware (logs response)
  ↓
4. Correlation ID Middleware (adds header)
  ↓
3. Timing Middleware (adds timing header)
  ↓
2. Security Headers Middleware (adds security headers)
  ↓
1. CORS Middleware (adds CORS headers)
  ↓
Response
```

### Code Order in main.py

```python
# This is the REVERSE order of execution:

# 1. Add CORS first (executes FIRST in chain)
app.add_middleware(CORSMiddleware, ...)

# 2. Add Security Headers (executes SECOND)
app.add_middleware(SecurityHeadersMiddleware)

# 3. Add Timing (executes THIRD)
app.middleware("http")(timing_middleware)

# 4. Add Correlation ID (executes FOURTH)
app.middleware("http")(correlation_middleware)

# 5. Add Logging (executes FIFTH)
app.middleware("http")(logging_middleware)

# 6. Add Error Handler (executes LAST, catches all errors)
app.middleware("http")(error_handler_middleware)
```

## Middleware Descriptions

### 1. CORS Middleware
- **Purpose**: Handle Cross-Origin Resource Sharing
- **When to modify**: When adding new frontend origins
- **Configuration**: `settings.cors_*` variables

### 2. Security Headers Middleware
- **Purpose**: Add security headers (CSP, HSTS, X-Frame-Options, etc.)
- **When to modify**: When adjusting security policies
- **Configuration**: `settings.csp_*` and `settings.hsts_*` variables

### 3. Timing Middleware
- **Purpose**: Measure request processing time
- **Headers added**: `X-Process-Time`
- **Logging**: Warns on requests > 1 second

### 4. Correlation ID Middleware
- **Purpose**: Add unique ID to each request for tracing
- **Headers**: Reads/sets `X-Correlation-ID`
- **Usage**: Access via `request.state.correlation_id` in endpoints

### 5. Logging Middleware
- **Purpose**: Log all requests and responses
- **Format**: JSON structured logging
- **Includes**: Method, path, status, correlation ID

### 6. Error Handler Middleware
- **Purpose**: Catch and format all exceptions
- **Returns**: Standardized error responses
- **Includes**: Correlation ID in error responses

## Best Practices

1. **Never modify middleware order** without understanding implications
2. **Always test** after adding new middlewares
3. **Use correlation IDs** in all logging statements
4. **Keep middlewares lightweight** (< 10ms overhead)
5. **Document changes** to middleware configuration

## Testing Middlewares

```bash
# Test CORS
curl -H "Origin: http://localhost:5173" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:8000/api/v1/deployments

# Test Correlation ID
curl -H "X-Correlation-ID: test-123" \
     http://localhost:8000/health

# Test Security Headers
curl -I http://localhost:8000/health

# Test Timing
curl -w "\nTime: %{time_total}s\n" \
     http://localhost:8000/api/v1/deployments
```

## Troubleshooting

### CSP Breaking API Docs

If Scalar/Swagger doesn't work, adjust CSP:

```python
csp_script_src: List[str] = ["'self'", "'unsafe-inline'", "'unsafe-eval'"]
```

### CORS Issues

Check that frontend origin is in `CORS_ORIGINS`:

```bash
CORS_ORIGINS='["http://localhost:5173"]'
```

### Rate Limiting Not Working

Ensure Redis is running:

```bash
docker run -d -p 6379:6379 redis:alpine
```


---

## 3. Main Application Updates

### 3.1 Updated main.py

**File:** `backend/app/main.py`

Key changes:
1. Add Scalar documentation
2. Register all new middlewares in correct order
3. Enhance OpenAPI schema
4. Add rate limiting
5. Improve startup/shutdown logging

```python
"""
Application FastAPI principale pour WindFlow Backend.

Enterprise-grade API with:
- Scalar API documentation
- Comprehensive security headers
- Rate limiting
- Request tracing
- Performance monitoring
"""

import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from scalar_fastapi import get_scalar_api_reference

# Rate limiting
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
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
    if settings.rate_limit_enabled:
        await FastAPILimiter.close()
        logger.info("✓ Rate limiter closed")
    
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
        status_code=status.HTTP_
```

## 4. Endpoint Documentation Standards

### 4.1 Documentation Template

Every endpoint MUST include:

1. **Summary** - One-line description
2. **Description** - Detailed markdown description
3. **openapi_extra** - Multiple request examples
4. **responses** - All possible HTTP responses with examples

### 4.2 Example: Deployment Creation Endpoint

**File:** `backend/app/api/v1/deployments.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_limiter.depends import RateLimiter
from typing import List

router = APIRouter()

@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new deployment",
    description="""
Create a new Docker deployment from a stack configuration.

## Process
1. Validates stack configuration
2. Prepares deployment environment
3. Initiates deployment process (async)
4. Returns deployment details with status

## Stack Types
- **Docker Container**: Single container deployment
- **Docker Compose**: Multi-container stack
- **Kubernetes**: K8s manifest deployment

## AI Optimization
When enabled, the LLM backend can:
- Optimize resource allocation
- Suggest security improvements
- Auto-configure health checks
- Recommend scaling strategies

## Real-time Updates
Subscribe to WebSocket endpoint `/ws/deployments/{deployment_id}` 
for real-time deployment status updates.

**Authentication Required**
""",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "simple_nginx": {
                            "summary": "Simple Nginx deployment",
                            "description": "Basic web server deployment",
                            "value": {
                                "name": "my-nginx",
                                "stack_id": "550e8400-e29b-41d4-a716-446655440000",
                                "target_type": "docker",
                                "environment_id": "prod-env-1"
                            }
                        },
                        "with_ai_optimization": {
                            "summary": "Deployment with AI optimization",
                            "description": "Let AI optimize configuration",
                            "value": {
                                "name": "optimized-api",
                                "stack_id": "660e8400-e29b-41d4-a716-446655440001",
                                "target_type": "docker",
                                "environment_id": "staging-env",
                                "enable_ai_optimization": True,
                                "configuration": {
                                    "optimization_level": "balanced"
                                }
                            }
                        },
                        "docker_compose": {
                            "summary": "Docker Compose stack",
                            "description": "Multi-container application",
                            "value": {
                                "name": "full-stack-app",
                                "stack_id": "770e8400-e29b-41d4-a716-446655440002",
                                "target_type": "docker-compose",
                                "configuration": {
                                    "scale": {
                                        "web": 3,
                                        "api": 2
                                    }
                                }
                            }
                        },
                        "kubernetes": {
                            "summary": "Kubernetes deployment",
                            "description": "Deploy to K8s cluster",
                            "value": {
                                "name": "k8s-microservice",
                                "stack_id": "880e8400-e29b-41d4-a716-446655440003",
                                "target_type": "kubernetes",
                                "configuration": {
                                    "namespace": "production",
                                    "replicas": 5
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Deployment created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "name": "my-nginx",
                        "status": "pending",
                        "target_type": "docker",
                        "created_at": "2026-01-02T22:30:00Z",
                        "stack": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "nginx-stack"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_stack": {
                            "summary": "Stack not found",
                            "value": {
                                "error": "Stack Not Found",
                                "detail": "Stack with ID 550e8400-... does not exist",
                                "correlation_id": "abc-123"
                            }
                        },
                        "invalid_config": {
                            "summary": "Invalid configuration",
                            "value": {
                                "error": "Configuration Error",
                                "detail": "Missing required field: image",
                                "correlation_id": "abc-124"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "User does not have permission to create deployments"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 10 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def create_deployment(
    request: Request,
    deployment: DeploymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new deployment (implementation)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    
    logger.info(
        f"Creating deployment: {deployment.name}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": str(deployment.stack_id)
        }
    )
    
    # Implementation...
    pass
```

### 4.3 Endpoints to Document

All endpoints in these files need complete documentation:

```
backend/app/api/v1/
├── auth.py           # Login, logout, refresh, register
├── deployments.py    # CRUD deployments
├── stacks.py         # CRUD stacks
├── organizations.py  # CRUD organizations
├── users.py          # CRUD users
├── environments.py   # CRUD environments
├── targets.py        # CRUD targets
└── websockets.py     # WebSocket connections
```

### 4.4 Documentation Checklist Per Endpoint

- [ ] `summary`: Clear, concise title
- [ ] `description`: Full markdown documentation
- [ ] `openapi_extra.requestBody.examples`: 3-5 realistic examples
- [ ] `responses`: All HTTP codes (200, 400, 401, 403, 404, 429, 500)
- [ ] `responses` examples: One example per response code
- [ ] `dependencies`: Rate limiting decorator
- [ ] `tags`: Appropriate OpenAPI tag
- [ ] Logger calls with correlation_id
- [ ] Type hints on all parameters

---

## 5. Model Documentation Standards

### 5.1 Pydantic Model Template

Every Pydantic model MUST include:

1. **model_config** with examples
2. **Field(...) descriptions** for all fields
3. **json_schema_extra** with example values
4. **Validators** with clear error messages
5. **Docstring** explaining the model's purpose

### 5.2 Example: DeploymentCreate Schema

**File:** `backend/app/schemas/deployment.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from uuid import UUID
from enum import Enum


class TargetType(str, Enum):
    """Supported deployment target types."""
    
    DOCKER = "docker"
    DOCKER_COMPOSE = "docker-compose"
    KUBERNETES = "kubernetes"
    VM = "vm"
    PHYSICAL = "physical"


class DeploymentCreate(BaseModel):
    """
    Create a new deployment request.
    
    This schema defines all required and optional parameters
    for creating a new deployment. Deployments are asynchronous
    operations that can be tracked via WebSocket or polling.
    
    **Validation Rules:**
    - name: 1-100 characters, alphanumeric with hyphens/underscores
    - stack_id: Must reference an existing stack
    - target_type: Must be a supported target type
    - configuration: JSON object with target-specific settings
    
    **Examples:**
    See model_config examples below for common use cases.
    """
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "production-nginx",
                    "stack_id": "550e8400-e29b-41d4-a716-446655440000",
                    "target_type": "docker",
                    "environment_id": "prod-env-1"
                },
                {
                    "name": "staging-fullstack",
                    "stack_id": "660e8400-e29b-41d4-a716-446655440001",
                    "target_type": "docker-compose",
                    "configuration": {
                        "scale": {"web": 2, "api": 3}
                    },
                    "enable_ai_optimization": True
                },
                {
                    "name": "k8s-microservice",
                    "stack_id": "770e8400-e29b-41d4-a716-446655440002",
                    "target_type": "kubernetes",
                    "configuration": {
                        "namespace": "production",
                        "replicas": 5,
                        "resources": {
                            "limits": {"cpu": "1000m", "memory": "1Gi"}
                        }
                    }
                }
            ]
        }
    }
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Deployment name (unique within organization)",
        json_schema_extra={"example": "production-api-v2"}
    )
    
    stack_id: UUID = Field(
        ...,
        description="UUID of the stack to deploy",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    
    target_type: TargetType = Field(
        ...,
        description="Target deployment type (docker, docker-compose, kubernetes, vm, physical)",
        json_schema_extra={"example": "docker"}
    )
    
    environment_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Target environment identifier (e.g., production, staging)",
        json_schema_extra={"example": "prod-env-1"}
    )
    
    configuration: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Target-specific configuration (ports, volumes, env vars, etc.)",
        json_schema_extra={
            "example": {
                "ports": [80, 443],
                "environment": {"NODE_ENV": "production"},
                "volumes": ["/data:/var/lib/data"]
            }
        }
    )
    
    enable_ai_optimization: bool = Field(
        default=False,
        description="Enable AI-powered deployment optimization",
        json_schema_extra={"example": True}
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """
        Validate deployment name format.
        
        Rules:
        - Alphanumeric characters only
        - Hyphens and underscores allowed
        - No spaces or special characters
        
        Args:
            v: Name to validate
            
        Returns:
            Validated name
            
        Raises:
            ValueError: If name contains invalid characters
        """
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError(
                'Deployment name can only contain alphanumeric characters, '
                'hyphens, and underscores'
            )
        return v
    
    @field_validator('configuration')
    @classmethod
    def validate_configuration(cls, v: Optional[Dict[str, Any]], info) -> Optional[Dict[str, Any]]:
        """
        Validate target-specific configuration.
        
        Performs basic validation based on target_type.
        Detailed validation is done at deployment time.
        
        Args:
            v: Configuration dictionary
            info: Validation context with other field values
            
        Returns:
            Validated configuration
            
        Raises:
            ValueError: If configuration is invalid for target type
        """
        if v is None:
            return v
        
        # Get target_type from validation context
        target_type = info.data.get('target_type')
        
        # Docker-specific validation
        if target_type == TargetType.DOCKER:
            if 'image' not in v and 'dockerfile' not in v:
                raise ValueError(
                    'Docker deployments require either "image" or "dockerfile" in configuration'
                )
        
        # Kubernetes-specific validation
        elif target_type == TargetType.KUBERNETES:
            if 'namespace' in v and not v['namespace'].replace('-', '').isalnum():
                raise ValueError(
                    'Kubernetes namespace must contain only alphanumeric characters and hyphens'
                )
        
        return v


class DeploymentResponse(BaseModel):
    """
    Deployment response with full details.
    
    Returned after successful deployment creation or when
    querying deployment status. Includes all deployment
    metadata and current status.
    """
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "name": "production-nginx",
                "status": "running",
                "target_type": "docker",
                "created_at": "2026-01-02T22:30:00Z",
                "updated_at": "2026-01-02T22:35:00Z",
                "started_at": "2026-01-02T22:31:00Z",
                "stack": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "nginx-stable"
                },
                "user": {
                    "id": "110e8400-e29b-41d4-a716-446655440000",
                    "username": "admin"
                }
            }
        }
    }
    
    id: UUID = Field(
        ...,
        description="Unique deployment identifier",
        json_schema_extra={"example": "990e8400-e29b-41d4-a716-446655440000"}
    )
    
    name: str = Field(
        ...,
        description="Deployment name",
        json_schema_extra={"example": "production-nginx"}
    )
    
    status: str = Field(
        ...,
        description="Current deployment status (pending, deploying, running, failed, stopped)",
        json_schema_extra={"example": "running"}
    )
    
    target_type: str = Field(
        ...,
        description="Deployment target type",
        json_schema_extra={"example": "docker"}
    )
    
    created_at: str = Field(
        ...,
        description="ISO 8601 timestamp of creation",
        json_schema_extra={"example": "2026-01-02T22:30:00Z"}
    )
    
    updated_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of last update",
        json_schema_extra={"example": "2026-01-02T22:35:00Z"}
    )
    
    started_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp when deployment started",
        json_schema_extra={"example": "2026-01-02T22:31:00Z"}
    )
    
    configuration: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Deployment configuration"
    )
    
    logs: Optional[str] = Field(
        default=None,
        description="Recent deployment logs (last 100 lines)"
    )
```

### 5.3 Models to Document

All Pydantic models in these files:

```
backend/app/schemas/
├── deployment.py      # DeploymentCreate, DeploymentResponse, DeploymentUpdate
├── stack.py           # StackCreate, StackResponse, StackUpdate
├── user.py           # UserCreate, UserResponse, UserUpdate
├── organization.py   # OrganizationCreate, OrganizationResponse
├── environment.py    # EnvironmentCreate, EnvironmentResponse
├── target.py         # TargetCreate, TargetResponse
└── common.py         # Shared models (Pagination, ErrorResponse, etc.)
```

### 5.4 Model Documentation Checklist

- [ ] Class docstring explaining purpose
- [ ] `model_config` with 2-3 complete examples
- [ ] Every field has `Field(...)` with description
- [ ] Every field has `json_schema_extra={"example": ...}`
- [ ] Custom validators have docstrings
- [ ] Validators explain what they check and why
- [ ] Enums are documented with descriptions
- [ ] Complex nested objects are explained

---

## 6. Testing Strategy

### 6.1 Security Headers Testing

**File:** `backend/tests/integration/test_security_headers.py`

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_csp_header_present(client: AsyncClient):
    """Test that CSP header is present."""
    response = await client.get("/health")
    
    assert "Content-Security-Policy" in response.headers
    assert "'self'" in response.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_hsts_header_in_production(client: AsyncClient, monkeypatch):
    """Test HSTS header in production mode."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    response = await client.get("/health")
    
    assert "Strict-Transport-Security" in response.headers
    assert "max-age=" in response.headers["Strict-Transport-Security"]


@pytest.mark.asyncio
async def test_security_headers_complete(client: AsyncClient):
    """Test all security headers are present."""
    response = await client.get("/health")
    
    required_headers = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Permissions-Policy"
    ]
    
    for header in required_headers:
        assert header in response.headers, f"Missing security header: {header}"
```

### 6.2 Correlation ID Testing

**File:** `backend/tests/integration/test_correlation_id.py`

```python
import pytest
from httpx import AsyncClient
import uuid


@pytest.mark.asyncio
async def test_correlation_id_generated(client: AsyncClient):
    """Test correlation ID is generated if not provided."""
    response = await client.get("/health")
    
    assert "X-Correlation-ID" in response.headers
    # Should be valid UUID
    correlation_id = response.headers["X-Correlation-ID"]
    uuid.UUID(correlation_id)  # Raises if invalid


@pytest.mark.asyncio
async def test_correlation_id_preserved(client: AsyncClient):
    """Test provided correlation ID is preserved."""
    test_id = "test-correlation-123"
    
    response = await client.get(
        "/health",
        headers={"X-Correlation-ID": test_id}
    )
    
    assert response.headers["X-Correlation-ID"] == test_id


@pytest.mark.asyncio
async def test_correlation_id_in_logs(client: AsyncClient, caplog):
    """Test correlation ID appears in log messages."""
    test_id = str(uuid.uuid4())
    
    response = await client.post(
        "/api/v1/deployments",
        json={"name": "test", "stack_id": str(uuid.uuid4())},
        headers={"X-Correlation-ID": test_id}
    )
    
    # Check logs contain correlation ID
    assert any(test_id in record.message for record in caplog.records)
```

### 6.3 Rate Limiting Testing

**File:** `backend/tests/integration/test_rate_limiting.py`

```python
import pytest
from httpx import AsyncClient
import asyncio


@pytest.mark.asyncio
async def test_rate_limit_enforcement(client: AsyncClient):
    """Test rate limiting blocks excessive requests."""
    endpoint = "/api/v1/deployments"
    
    # Make requests up to limit (10/minute)
    responses = []
    for _ in range(12):
        response = await client.get(endpoint)
        responses.append(response)
        await asyncio.sleep(0.1)
    
    # First 10 should succeed
    assert all(r.status_code != 429 for r in responses[:10])
    
    # 11th and 12th should be rate limited
    assert any(r.status_code == 429 for r in responses[10:])


@pytest.mark.asyncio
async def test_rate_limit_headers(client: AsyncClient):
    """Test rate limit headers are present."""
    response = await client.get("/api/v1/deployments")
    
    # Should have rate limit headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
```

### 6.4 API Documentation Testing

**File:** `backend/tests/integration/test_openapi.py`

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_openapi_schema_valid(client: AsyncClient):
    """Test OpenAPI schema is valid JSON."""
    response = await client.get("/openapi.json")
    
    assert response.status_code == 200
    schema = response.json()
    
    # Check basic OpenAPI structure
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema
    assert "components" in schema


@pytest.mark.asyncio
async def test_all_endpoints_documented(client: AsyncClient):
    """Test all endpoints have OpenAPI documentation."""
    response = await client.get("/openapi.json")
    schema = response.json()
    
    # Check critical endpoints are documented
    critical_paths = [
        "/api/v1/auth/login",
        "/api/v1/deployments",
        "/api/v1/stacks",
        "/health"
    ]
    
    for path in critical_paths:
        assert path in schema["paths"], f"Missing documentation for {path}"


@pytest.mark.asyncio
async def test_endpoint_examples_present(client: AsyncClient):
    """Test endpoints have request examples."""
    response = await client.get("/openapi.json")
    schema = response.json()
    
    # Check POST /api/v1/deployments has examples
    deployment_post = schema["paths"]["/api/v1/deployments"]["post"]
    
    assert "requestBody" in deployment_post
    assert "content" in deployment_post["requestBody"]
    assert "application/json" in deployment_post["requestBody"]["content"]
    
    json_content = deployment_post["requestBody"]["content"]["application/json"]
    assert "examples" in json_content
    assert len(json_content["examples"]) >= 2  # At least 2 examples


@pytest.mark.asyncio
async def test_scalar_docs_accessible(client: AsyncClient):
    """Test Scalar documentation page loads."""
    response = await client.get("/docs")
    
    assert response.status_code == 200
    assert "scalar" in response.text.lower()
```

---

## 7. Implementation Checklist

### Phase 1: Dependencies and Configuration (30 min)

- [ ] Add dependencies to `pyproject.toml`:
  - [ ] `scalar-fastapi = "^1.0.3"`
  - [ ] `fastapi-limiter = "^0.1.6"`
  - [ ] `redis = "^5.0.0"`
- [ ] Run `poetry add scalar-fastapi fastapi-limiter redis`
- [ ] Update `backend/app/config.py`:
  - [ ] Add `api_public_url` field
  - [ ] Add CORS configuration fields
  - [ ] Add CSP configuration fields
  - [ ] Add HSTS configuration fields
  - [ ] Add rate limiting fields
  - [ ] Add timing/correlation enable flags
  - [ ] Add `build_csp_header()` method
  - [ ] Add `build_server_urls()` method
- [ ] Update `env.example` with new variables
- [ ] Test configuration loads: `python -c "from backend.app.config import settings; print(settings)"`

### Phase 2: Middleware Implementation (1h)

- [ ] Create `backend/app/middleware/security.py`:
  - [ ] Implement `SecurityHeadersMiddleware` class
  - [ ] Add CSP header logic
  - [ ] Add HSTS header logic (production only)
  - [ ] Add all security headers
- [ ] Create `backend/app/middleware/correlation.py`:
  - [ ] Implement `correlation_middleware` function
  - [ ] Generate or preserve correlation ID
  - [ ] Store in request.state
  - [ ] Add to response headers
- [ ] Create `backend/app/middleware/timing.py`:
  - [ ] Implement `timing_middleware` function
  - [ ] Measure request duration
  - [ ] Add X-Process-Time header
  - [ ] Log slow requests (>1s)
- [ ] Update `backend/app/middleware/__init__.py`:
  - [ ] Export new middlewares
  - [ ] Maintain existing exports
- [ ] Create `backend/app/middleware/README.md`:
  - [ ] Document middleware order
  - [ ] Explain each middleware
  - [ ] Include testing examples
  - [ ] Add troubleshooting section

### Phase 3: Main Application Updates (1h)

- [ ] Update `backend/app/main.py`:
  - [ ] Import new dependencies (Scalar, FastAPILimiter, Redis)
  - [ ] Update lifespan function:
    - [ ] Initialize FastAPILimiter with Redis
    - [ ] Add better startup logging
    - [ ] Close Redis on shutdown
  - [ ] Update FastAPI app creation:
    - [ ] Use `settings.build_server_urls()`
    - [ ] Enhanced description with features
    - [ ] Add all OpenAPI tags
    - [ ] Configure swagger_ui_parameters
  - [ ] Add middlewares in correct order:
    - [ ] CORS (first)
    - [ ] SecurityHeadersMiddleware
    - [ ] timing_middleware
    - [ ] correlation_middleware
    - [ ] logging_middleware
    - [ ] error_handler_middleware (last)
  - [ ] Add Scalar endpoint `/docs`
  - [ ] Update exception handlers to include correlation_id
- [ ] Test application starts: `python -m backend.app.main`
- [ ] Test documentation loads: Open `http://localhost:8000/docs`
- [ ] Test security headers: `curl -I http://localhost:8000/health`

### Phase 4: Endpoint Documentation - Auth (30 min) ✅

- [x] Update `backend/app/api/v1/auth.py`:
  - [x] POST `/api/v1/auth/login`:
    - [x] Add summary and description
    - [x] Add 3 request examples (username, email, simple)
    - [x] Document all responses (200, 401, 403, 429, 500)
    - [x] Add rate limiting (5 requests/minute)
  - [x] POST `/api/v1/auth/logout`:
    - [x] Add summary and description
    - [x] Document responses (200, 401, 429, 500)
    - [x] Add rate limiting (20 requests/minute)
  - [x] POST `/api/v1/auth/refresh`:
    - [x] Add summary and description
    - [x] Add 3 request examples (standard, before expiration, after expiration)
    - [x] Document all responses (200, 401 with 3 variants, 429, 500)
    - [x] Add rate limiting (10 requests/minute)
  - [x] POST `/api/v1/auth/register`:
    - [x] Add complete documentation
    - [x] Add 3 request examples (complete, minimal, organization user)
    - [x] Document all responses (201, 400, 409 with 2 variants, 429, 500)
    - [x] Add rate limiting (3 requests/minute)
  - [x] GET `/api/v1/auth/me`:
    - [x] Add summary and description
    - [x] Add 2 response examples (regular user, superuser)
    - [x] Document all responses (200, 401, 429, 500)
    - [x] Add rate limiting (60 requests/minute)

### Phase 5: Endpoint Documentation - Deployments (45 min)

- [ ] Update `backend/app/api/v1/deployments.py`:
  - [ ] GET `/api/v1/deployments`:
    - [ ] Add summary and description
    - [ ] Document query parameters (pagination, filters)
    - [ ] Add response examples (with data, empty list)
    - [ ] Add rate limiting dependency
  - [ ] POST `/api/v1/deployments`:
    - [ ] Add detailed description (see section 4.2)
    - [ ] Add 4-5 request examples (different target types)
    - [ ] Document all responses
    - [ ] Add rate limiting dependency
  - [ ] GET `/api/v1/deployments/{id}`:
    - [ ] Add summary and description
    - [ ] Document path parameter
    - [ ] Add response examples
  - [ ] PUT `/api/v1/deployments/{id}`:
    - [ ] Add documentation
    - [ ] Add request examples
  - [ ] DELETE `/api/v1/deployments/{id}`:
    - [ ] Add documentation
  - [ ] POST `/api/v1/deployments/{id}/stop`:
    - [ ] Add documentation
  - [ ] POST `/api/v1/deployments/{id}/restart`:
    - [ ] Add documentation
  - [ ] GET `/api/v1/deployments/{id}/logs`:
    - [ ] Add documentation
    - [ ] Document query parameters (lines, follow)

### Phase 6: Endpoint Documentation - Stacks (30 min)

- [ ] Update `backend/app/api/v1/stacks.py`:
  - [ ] GET `/api/v1/stacks`:
    - [ ] Add summary, description, examples
  - [ ] POST `/api/v1/stacks`:
    - [ ] Add detailed documentation
    - [ ] Add 3-

## 7. Implementation Checklist (Continued)

### Phase 6: Endpoint Documentation - Stacks (Continued) (30 min)

- [ ] Update `backend/app/api/v1/stacks.py`:
  - [ ] GET `/api/v1/stacks`:
    - [ ] Add summary, description, examples
  - [ ] POST `/api/v1/stacks`:
    - [ ] Add detailed documentation
    - [ ] Add 3-4 request examples (different stack types)
    - [ ] Document all responses
  - [ ] GET `/api/v1/stacks/{id}`:
    - [ ] Add documentation
  - [ ] PUT `/api/v1/stacks/{id}`:
    - [ ] Add documentation
  - [ ] DELETE `/api/v1/stacks/{id}`:
    - [ ] Add documentation

### Phase 7: Endpoint Documentation - Organizations (20 min)

- [ ] Update `backend/app/api/v1/organizations.py`:
  - [ ] GET `/api/v1/organizations`:
    - [ ] Add complete documentation
  - [ ] POST `/api/v1/organizations`:
    - [ ] Add detailed description
    - [ ] Add 2-3 request examples
    - [ ] Document all responses
  - [ ] GET `/api/v1/organizations/{id}`:
    - [ ] Add documentation
  - [ ] PUT `/api/v1/organizations/{id}`:
    - [ ] Add documentation
  - [ ] DELETE `/api/v1/organizations/{id}`:
    - [ ] Add documentation

### Phase 8: Endpoint Documentation - Users (20 min)

- [ ] Update `backend/app/api/v1/users.py`:
  - [ ] GET `/api/v1/users`:
    - [ ] Add complete documentation
    - [ ] Document query parameters (filters, pagination)
  - [ ] POST `/api/v1/users`:
    - [ ] Add detailed description
    - [ ] Add 2-3 request examples
    - [ ] Document all responses
  - [ ] GET `/api/v1/users/{id}`:
    - [ ] Add documentation
  - [ ] PUT `/api/v1/users/{id}`:
    - [ ] Add documentation
  - [ ] DELETE `/api/v1/users/{id}`:
    - [ ] Add documentation
  - [ ] GET `/api/v1/users/me`:
    - [ ] Add documentation for current user endpoint

### Phase 9: Endpoint Documentation - Other Endpoints (30 min)

- [ ] Update `backend/app/api/v1/environments.py` (if exists):
  - [ ] Document all CRUD endpoints
- [ ] Update `backend/app/api/v1/targets.py` (if exists):
  - [ ] Document all CRUD endpoints
- [x] Update `backend/app/api/v1/websockets.py`:
  - [x] Document WebSocket connection endpoint
  - [x] Add connection examples
  - [x] Document message formats

### Phase 10: Model Documentation - Deployment Schemas (45 min)

- [ ] Update `backend/app/schemas/deployment.py`:
  - [ ] `DeploymentCreate`:
    - [ ] Add class docstring
    - [ ] Add model_config with 3 examples
    - [ ] Add Field descriptions for all fields
    - [ ] Add json_schema_extra for all fields
    - [ ] Document validators
  - [ ] `DeploymentResponse`:
    - [ ] Complete documentation
  - [ ] `DeploymentUpdate`:
    - [ ] Complete documentation
  - [ ] `DeploymentList`:
    - [ ] Complete documentation
  - [ ] Any other deployment-related schemas

### Phase 11: Model Documentation - Stack Schemas (30 min)

- [ ] Update `backend/app/schemas/stack.py`:
  - [ ] `StackCreate`:
    - [ ] Add complete documentation
    - [ ] Add 2-3 examples (different target types)
    - [ ] Document all fields
  - [ ] `StackResponse`:
    - [ ] Complete documentation
  - [ ] `StackUpdate`:
    - [ ] Complete documentation
  - [ ] Stack-related enums and nested models

### Phase 12: Model Documentation - User Schemas (30 min)

- [ ] Update `backend/app/schemas/user.py`:
  - [ ] `UserCreate`:
    - [ ] Add complete documentation
    - [ ] Add examples
    - [ ] Document password requirements in validators
  - [ ] `UserResponse`:
    - [ ] Complete documentation
    - [ ] Don't include password in response
  - [ ] `UserUpdate`:
    - [ ] Complete documentation
  - [ ] `UserLogin`:
    - [ ] Complete documentation

### Phase 13: Model Documentation - Organization Schemas (20 min)

- [ ] Update `backend/app/schemas/organization.py`:
  - [ ] `OrganizationCreate`:
    - [ ] Add complete documentation
  - [ ] `OrganizationResponse`:
    - [ ] Complete documentation
  - [ ] `OrganizationUpdate`:
    - [ ] Complete documentation

### Phase 14: Model Documentation - Common Schemas (30 min)

- [ ] Update `backend/app/schemas/common.py`:
  - [ ] `PaginationParams`:
    - [ ] Document pagination fields
    - [ ] Add examples
  - [ ] `PaginatedResponse`:
    - [ ] Document generic paginated response
  - [ ] `ErrorResponse`:
    - [ ] Document error response format
    - [ ] Add examples for different error types
  - [ ] Any other shared models

### Phase 15: Testing - Security (30 min)

- [ ] Create `backend/tests/integration/test_security_headers.py`:
  - [ ] Implement all tests from section 6.1
  - [ ] Run tests: `pytest backend/tests/integration/test_security_headers.py -v`
  - [ ] Verify all security headers are present
  - [ ] Test CSP configuration
  - [ ] Test HSTS in production mode

### Phase 16: Testing - Middleware (30 min)

- [ ] Create `backend/tests/integration/test_correlation_id.py`:
  - [ ] Implement tests from section 6.2
  - [ ] Test correlation ID generation
  - [ ] Test correlation ID preservation
  - [ ] Test correlation ID in logs
- [ ] Create `backend/tests/integration/test_timing.py`:
  - [ ] Test X-Process-Time header present
  - [ ] Test timing accuracy
  - [ ] Test slow request logging

### Phase 17: Testing - Rate Limiting (30 min)

- [ ] Create `backend/tests/integration/test_rate_limiting.py`:
  - [ ] Implement tests from section 6.3
  - [ ] Test rate limit enforcement
  - [ ] Test rate limit headers
  - [ ] Test different endpoints have different limits
- [ ] Ensure Redis is running for tests:
  - [ ] Add Redis to docker-compose-dev.yml if needed
  - [ ] Or use fakeredis for tests

### Phase 18: Testing - OpenAPI Documentation (30 min)

- [ ] Create `backend/tests/integration/test_openapi.py`:
  - [ ] Implement tests from section 6.4
  - [ ] Test OpenAPI schema validity
  - [ ] Test all endpoints documented
  - [ ] Test request examples present
  - [ ] Test Scalar docs accessible
- [ ] Run all documentation tests
- [ ] Fix any missing documentation found by tests

### Phase 19: Manual Testing & Validation (1h)

- [ ] Start application: `make backend` or `uvicorn backend.app.main:app --reload`
- [ ] Test Scalar documentation:
  - [ ] Open http://localhost:8000/docs
  - [ ] Verify modern UI loads
  - [ ] Test interactive examples work
  - [ ] Test code generation in different languages
  - [ ] Verify all endpoints visible
- [ ] Test security headers:
  - [ ] `curl -I http://localhost:8000/health | grep -i "content-security-policy"`
  - [ ] `curl -I http://localhost:8000/health | grep -i "x-frame-options"`
  - [ ] Verify all headers present
- [ ] Test correlation ID:
  - [ ] `curl -H "X-Correlation-ID: test-123" http://localhost:8000/health -v`
  - [ ] Verify ID in response headers
- [ ] Test rate limiting (requires Redis):
  - [ ] Make 15 rapid requests to same endpoint
  - [ ] Verify 429 response after limit
  - [ ] Check X-RateLimit-* headers
- [ ] Test CORS:
  - [ ] Make cross-origin request from frontend
  - [ ] Verify CORS headers present
  - [ ] Test preflight OPTIONS request

### Phase 20: Documentation Updates (30 min)

- [ ] Create `doc/SECURITY-HEADERS.md`:
  - [ ] Explain each security header
  - [ ] CSP configuration guide
  - [ ] HSTS best practices
  - [ ] Troubleshooting common issues
- [ ] Create `doc/API-RATE-LIMITING.md`:
  - [ ] Explain rate limiting configuration
  - [ ] How to set different limits per endpoint
  - [ ] Redis setup for production
  - [ ] Monitoring rate limits
- [ ] Update main `README.md`:
  - [ ] Add security features section
  - [ ] Link to new documentation
  - [ ] Update getting started with Redis requirement

### Phase 21: Production Preparation (30 min)

- [ ] Update `docker-compose.prod.yml`:
  - [ ] Add Redis service
  - [ ] Configure rate limiting
  - [ ] Set security environment variables
- [ ] Update `env.example`:
  - [ ] Verify all new variables documented
  - [ ] Add production-specific examples
  - [ ] Add security warnings/notes
- [ ] Create deployment checklist:
  - [ ] CSP configuration for production domain
  - [ ] HSTS enabled for HTTPS
  - [ ] Rate limiting Redis connection string
  - [ ] CORS origins for production frontend
- [ ] Update CI/CD pipeline (if exists):
  - [ ] Run security header tests
  - [ ] Run OpenAPI validation
  - [ ] Check rate limiting tests

---

## 8. Post-Implementation Validation

### 8.1 Security Validation

**Checklist:**
- [ ] All security headers present in production
- [ ] CSP doesn't block legitimate resources
- [ ] HSTS configured correctly for HTTPS
- [ ] No sensitive data in error responses
- [ ] Correlation IDs working for request tracing

**Commands:**
```bash
# Test security headers
curl -I https://api.windflow.io/health

# Expected headers:
# Content-Security-Policy: default-src 'self'; ...
# Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
# X-Content-Type-Options: nosniff
# X-Frame-Options: DENY
# X-XSS-Protection: 1; mode=block
# Referrer-Policy: strict-origin-when-cross-origin
# Permissions-Policy: geolocation=(), microphone=(), ...
```

### 8.2 Documentation Validation

**Checklist:**
- [ ] Scalar documentation loads without errors
- [ ] All endpoints have examples
- [ ] All request/response schemas documented
- [ ] Code generation works for Python, JavaScript, curl
- [ ] Search functionality works in docs
- [ ] WebSocket endpoints documented

**Manual Check:**
1. Open https://api.windflow.io/docs
2. Try "Try it out" for 3-5 different endpoints
3. Generate code snippets in different languages
4. Search for specific endpoints
5. Verify examples are realistic

### 8.3 Rate Limiting Validation

**Checklist:**
- [ ] Rate limits enforced correctly
- [ ] Different limits for different endpoints
- [ ] Rate limit headers present
- [ ] Redis connection stable
- [ ] Rate limits reset correctly

**Test:**
```bash
# Test rate limiting
for i in {1..15}; do
  curl -w "Status: %{http_code}\n" \
       -H "Authorization: Bearer $TOKEN" \
       https://api.windflow.io/api/v1/deployments
done

# Expected: First 10 succeed (200), remaining 5 fail (429)
```

### 8.4 Performance Validation

**Checklist:**
- [ ] Middleware overhead < 10ms
- [ ] Documentation pages load < 2s
- [ ] No performance regression from baseline
- [ ] Slow requests (>1s) logged properly

**Measurement:**
```bash
# Test response times
curl -w "\nTime: %{time_total}s\n" \
     -o /dev/null -s \
     https://api.windflow.io/api/v1/deployments

# Check X-Process-Time header
curl -I https://api.windflow.io/api/v1/deployments | grep X-Process-Time
```

---

## 9. Rollback Plan

### 9.1 If Scalar Documentation Fails

1. Remove Scalar endpoint:
   ```python
   # Comment out in main.py
   # @app.get("/docs", include_in_schema=False)
   # async def scalar_docs():
   #     ...
   ```

2. Revert to Swagger:
   ```python
   app = FastAPI(
       docs_url="/docs",  # Use default Swagger
       # ...
   )
   ```

### 9.2 If Security Headers Break Frontend

1. Temporarily disable CSP:
   ```bash
   CSP_ENABLED=false
   ```

2. Adjust CSP to allow specific sources:
   ```bash
   CSP_SCRIPT_SRC=["'self'","'unsafe-inline'","'unsafe-eval'"]
   ```

### 9.3 If Rate Limiting Causes Issues

1. Disable rate limiting:
   ```bash
   RATE_LIMIT_ENABLED=false
   ```

2. Or increase limits temporarily:
   ```bash
   RATE_LIMIT_DEFAULT=1000/minute
   ```

### 9.4 Complete Rollback

If major issues occur:

1. **Git revert** to previous commit:
   ```bash
   git revert HEAD~1  # Revert last commit
   git push
   ```

2. **Remove dependencies**:
   ```bash
   poetry remove scalar-fastapi fastapi-limiter redis
   ```

3. **Restore old main.py** from backup

4. **Redeploy** previous version

---

## 10. Success Metrics

### 10.1 Documentation Quality

- [ ] **100% endpoint coverage** - All endpoints documented
- [ ] **Average 3+ examples** per POST/PUT endpoint
- [ ] **All response codes** documented (200, 400, 401, 403, 404, 429, 500)
- [ ] **Search works** - Can find any endpoint easily
- [ ] **Positive user feedback** - Developers find docs helpful

### 10.2 Security Posture

- [ ] **All headers passing** - Security scanners show A+ rating
- [ ] **CSP violations** = 0 in production
- [ ] **HSTS preload** eligible (if applicable)
- [ ] **No sensitive data** in error responses
- [ ] **Correlation IDs** in 100% of logs

### 10.3 Performance

- [ ] **Middleware overhead** < 5ms average
- [ ] **Documentation load time** < 1s
- [ ] **No performance degradation** from baseline
- [ ] **Rate limiting** prevents abuse without false positives

### 10.4 Developer Experience

- [ ] **Time to first API call** reduced by 50%
- [ ] **Support tickets** about API documentation reduced
- [ ] **Code generation** works for all major languages
- [ ] **Interactive examples** reduce trial and error

---

## 11. Maintenance

### 11.1 Regular Updates

**Weekly:**
- [ ] Review rate limiting logs for abuse patterns
- [ ] Check CSP violation reports (if configured)
- [ ] Monitor slow request logs

**Monthly:**
- [ ] Update API examples based on usage patterns
- [ ] Review and update security headers configuration
- [ ] Check for new security best practices

**Quarterly:**
- [ ] Audit all endpoint documentation
- [ ] Update Scalar and dependencies
- [ ] Security headers compliance check
- [ ] Performance optimization review

### 11.2 Adding New Endpoints

When adding new endpoints, always:

1. **Document before implementation**:
   - Write OpenAPI description
   - Create request/response examples
   - Define error responses

2. **Follow template** (section 4.2):
   - Summary, description, examples, responses
   - Rate limiting decorator
   - Correlation ID logging

3. **Test documentation**:
   - Verify examples in Scalar
   - Test code generation
   - Check all response codes

4. **Update checklist**:
   - Add to relevant phase in this document
   - Update test coverage

---

## 12. Resources

### 12.1 Documentation References

- [Scalar Documentation](https://github.com/scalar/scalar) - Official Scalar docs
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) - FastAPI security guide
- [OWASP Headers](https://owasp.org/www-project-secure-headers/) - Security headers guide
- [CSP Guide](https://content-security-policy.com/) - CSP configuration
- [Rate Limiting](https://github.com/long2ice/fastapi-limiter) - FastAPI limiter docs

### 12.2 Testing Tools

- [pytest](https://docs.pytest.org/) - Python testing framework
- [httpx](https://www.python-httpx.org/) - Async HTTP client for testing
- [SecurityHeaders.com](https://securityheaders.com/) - Online security header scanner
- [OWASP ZAP](https://www.zaproxy.org/) - Security testing tool

### 12.3 Monitoring Tools

- **Prometheus** - Metrics collection
- **Grafana** - Metrics visualization
- **Sentry** - Error tracking with correlation IDs
- **CloudWatch/DataDog** - Log aggregation

---

## 13. FAQ

### Q: Why Scalar instead of Swagger/ReDoc?

**A:** Scalar provides:
- More modern, intuitive UI
- Built-in code generation for multiple languages
- Better search and filtering
- Interactive examples that are easier to use
- Active development and regular updates

### Q: Is rate limiting required?

**A:** Not for development, but highly recommended for production to:
- Prevent API abuse
- Protect against DoS attacks
- Ensure fair resource allocation
- Monitor usage patterns

### Q: Can I disable security headers in development?

**A:** Yes, but not recommended. Better to:
- Keep CSP enabled with permissive settings
- Disable HSTS (auto-disabled in non-production)
- Keep other headers for consistency

### Q: How do I handle CSP violations?

**A:**
1. Configure CSP_REPORT_URI
2. Monitor violation reports
3. Adjust CSP policy as needed
4. Never use `unsafe-eval` in production

### Q: What if Redis is down?

**A:** Rate limiting will fail open (allow requests) by default. Consider:
- Redis clustering for high availability
- Fallback to in-memory rate limiting
- Monitoring and alerts for Redis health


## 14. Summary

This migration plan upgrades WindFlow's API to enterprise-grade standards with:

✅ **Modern Documentation** - Scalar API reference with interactive examples  
✅ **Enterprise Security** - CSP, HSTS, comprehensive security headers  
✅ **Rate Limiting** - Protection against abuse with Redis-backed limits  
✅ **Request Tracing** - Correlation IDs for distributed debugging  
✅ **Performance Monitoring** - Timing middleware for optimization  
✅ **Complete Documentation** - Every endpoint and model fully documented

**Total Estimated Time:** 8-10 hours

**Benefits:**
- Better developer experience
- Improved security posture
- Production-ready API
- Easier debugging and monitoring
- Professional documentation

**Next Steps:**
1. Review this plan with team
2. Set up development environment
3. Begin Phase 1 (Dependencies)
4. Follow checklist phase by phase
5. Validate after each phase
6. Deploy to staging first
7. Monitor and iterate
