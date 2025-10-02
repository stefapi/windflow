"""
API REST v1 pour WindFlow.

Points d'entrée pour toutes les routes API version 1.
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .users import router as users_router
from .targets import router as targets_router
from .stacks import router as stacks_router
from .deployments import router as deployments_router

# Router principal v1
api_router = APIRouter(prefix="/api/v1")

# Enregistrement des sous-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(targets_router, prefix="/targets", tags=["targets"])
api_router.include_router(stacks_router, prefix="/stacks", tags=["stacks"])
api_router.include_router(deployments_router, prefix="/deployments", tags=["deployments"])

__all__ = ["api_router"]
