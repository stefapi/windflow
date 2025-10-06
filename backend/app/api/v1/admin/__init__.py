"""
API Admin pour WindFlow.

Routes d'administration réservées aux superadmins.
"""

from fastapi import APIRouter
from .stacks_management import router as stacks_management_router

# Router principal admin
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Enregistrement des sous-routers
admin_router.include_router(stacks_management_router, prefix="/stacks-management")

__all__ = ["admin_router"]
