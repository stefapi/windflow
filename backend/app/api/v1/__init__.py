"""
API REST v1 pour WindFlow.

Points d'entrée pour toutes les routes API version 1.
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .users import router as users_router
from .organizations import router as organizations_router
from .targets import router as targets_router
from .stacks import router as stacks_router
from .deployments import router as deployments_router
from .workflows import router as workflows_router
from .websockets import router as websockets_router
from .stats import router as stats_router
from .import_export import router as import_export_router
from .schedules import router as schedules_router
from .admin import admin_router
from .docker import router as docker_router

# Router principal v1
api_router = APIRouter(prefix="/api/v1")

# Enregistrement des sous-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(organizations_router, prefix="/organizations", tags=["organizations"])
api_router.include_router(targets_router, prefix="/targets", tags=["targets"])
api_router.include_router(stacks_router, prefix="/stacks", tags=["stacks"])
api_router.include_router(deployments_router, prefix="/deployments", tags=["deployments"])
api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
api_router.include_router(websockets_router, prefix="/ws", tags=["websockets"])
api_router.include_router(stats_router, tags=["statistics"])
api_router.include_router(import_export_router, tags=["import-export"])
api_router.include_router(schedules_router, tags=["schedules"])
api_router.include_router(admin_router)  # Le préfixe /admin est déjà dans le router
api_router.include_router(docker_router, prefix="/docker", tags=["docker"])

__all__ = ["api_router"]
