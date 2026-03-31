"""
Routes de gestion des cibles de déploiement.

Toute route vérifie systématiquement l'appartenance de la cible
à l'organisation de l'utilisateur authentifié via ``_get_target_for_org``.
"""

from fastapi import APIRouter

from .capabilities import router as capabilities_router
from .connectivity import router as connectivity_router
from .crud import router as crud_router
from .scanning import router as scanning_router

router = APIRouter()

# Enregistrement des sous-routers
router.include_router(crud_router)
router.include_router(connectivity_router)
router.include_router(scanning_router)
router.include_router(capabilities_router)

__all__ = ["router"]
