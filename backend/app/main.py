"""
Application FastAPI principale pour WindFlow Backend.

Architecture modulaire avec support SQLite par défaut et extensions optionnelles.
"""

print("=== LOADING backend.app.main MODULE ===", flush=True)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

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
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=== Application startup ===")

    await db.connect()
    await db.create_tables()
    await db.seed_tables()

    logger.info("=== Database initialized ===")

    # Recovery des déploiements PENDING au démarrage
    try:
        from .services.deployment_service import DeploymentService
        from .database import AsyncSessionLocal

        logger.info("=== Lancement du recovery des déploiements PENDING au démarrage ===")

        async with AsyncSessionLocal() as db_session:
            stats = await DeploymentService.recover_pending_deployments(
                db_session,
                max_age_minutes=0,  # Réessayer tous les PENDING
                timeout_minutes=60  # Marquer FAILED ceux > 60min
            )

            logger.info(
                f"Recovery au démarrage terminé: {stats['retried']} réessayés, "
                f"{stats['failed']} marqués FAILED, {stats['errors']} erreurs"
            )
    except Exception as e:
        logger.error(f"Erreur lors du recovery au démarrage: {e}")
        # Ne pas bloquer le démarrage si le recovery échoue

    logger.info("=== Application ready ===")

    yield

    # Shutdown
    logger.info("=== Application shutdown ===")
    await db.disconnect()


# Configuration CORS standard avec FastAPI

# Application FastAPI
_app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Plateforme intelligente de déploiement Docker avec IA intégrée",
    lifespan=lifespan,
    debug=settings.debug,
)

# Configuration CORS - doit être ajoutée AVANT les routers
_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Utilise la configuration depuis settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    allow_origin_regex=None  # Important pour les WebSockets
)

# Configuration WebSocket explicite pour Uvicorn
from uvicorn.config import Config
import os
os.environ["WEBSOCKETS_ENABLED"] = "true"

# Ajouter les middlewares personnalisés
from .middleware import logging_middleware, error_handler_middleware
_app.middleware("http")(logging_middleware)
_app.middleware("http")(error_handler_middleware)

# Enregistrement des routers API sur l'app interne
_app.include_router(api_router)


@_app.get("/")
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


@_app.get("/health")
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


@_app.get("/api/v1/info")
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


# Export de l'application avec CORS configuré
app = _app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
