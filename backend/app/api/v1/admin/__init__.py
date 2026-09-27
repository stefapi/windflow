"""
API Admin pour WindFlow.

Routes d'administration réservées aux superadmins.
"""

from fastapi import APIRouter

from .audit import router as audit_router
from .stacks_management import router as stacks_management_router

# Router principal admin
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Enregistrement des sous-routers
admin_router.include_router(stacks_management_router, prefix="/stacks-management")

# STORY-125.3 : consultation de l'audit trail (super_admin, lecture seule)
admin_router.include_router(audit_router, prefix="/audit")

__all__ = ["admin_router"]
