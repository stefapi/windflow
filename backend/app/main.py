"""
Application FastAPI principale pour WindFlow Backend.

Architecture modulaire avec support SQLite par défaut et extensions optionnelles.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import db
from .api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion du cycle de vie de l'application.

    Connexion et déconnexion de la base de données au démarrage/arrêt.
    """
    # Startup
    await db.connect()
    await db.create_tables()

    yield

    # Shutdown
    await db.disconnect()


# Application FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Plateforme intelligente de déploiement Docker avec IA intégrée",
    lifespan=lifespan,
    debug=settings.debug,
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routers API
app.include_router(api_router)


@app.get("/")
async def root():
    """
    Endpoint racine.

    Returns:
        dict: Informations sur l'API
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint pour monitoring.

    Vérifie l'état de la base de données et des services optionnels.

    Returns:
        dict: Statut de santé des services
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

    # Check Redis (si activé)
    if settings.redis_enabled:
        health_status["services"]["redis"] = {
            "status": "not_implemented",
            "enabled": True
        }
    else:
        health_status["services"]["redis"] = {
            "status": "disabled",
            "enabled": False
        }

    # Check Vault (si activé)
    if settings.vault_enabled:
        health_status["services"]["vault"] = {
            "status": "not_implemented",
            "enabled": True
        }
    else:
        health_status["services"]["vault"] = {
            "status": "disabled",
            "enabled": False
        }

    # Déterminer le statut global
    if not db_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=503,
            content=health_status
        )

    return health_status


@app.get("/api/v1/info")
async def api_info():
    """
    Informations sur l'API et configuration.

    Returns:
        dict: Configuration et capacités de l'API
    """
    return {
        "api_version": "v1",
        "app_version": settings.app_version,
        "environment": settings.environment,
        "features": {
            "database": "sqlite" if "sqlite" in settings.database_url else "postgresql",
            "redis_cache": settings.redis_enabled,
            "keycloak_sso": settings.keycloak_enabled,
            "vault_secrets": settings.vault_enabled,
            "celery_workers": settings.celery_enabled,
            "litellm_ai": settings.litellm_enabled,
            "prometheus_metrics": settings.prometheus_enabled
        },
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
