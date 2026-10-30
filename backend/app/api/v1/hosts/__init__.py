"""
Routes de gestion des hôtes de déploiement (famille Hosts — spec 09).

Surface canonique ``/api/v1/hosts/*`` (STORY-166.2). L'ancien chemin
``/api/v1/targets/*`` est maintenu en alias déprécié par
:mod:`app.api.v1.targets_legacy` (header ``Deprecation``).

Toute route vérifie systématiquement l'appartenance de l'hôte
à l'organisation de l'utilisateur authentifié (``is_member`` /
``_get_host_for_org`` — une ressource étrangère est traitée comme
inexistante).
"""

from fastapi import APIRouter

from .capabilities import router as capabilities_router
from .connectivity import router as connectivity_router
from .crud import router as crud_router
from .fingerprints import router as fingerprints_router
from .scanning import router as scanning_router

router = APIRouter()

# Enregistrement des sous-routers
router.include_router(crud_router)
router.include_router(connectivity_router)
router.include_router(scanning_router)
router.include_router(capabilities_router)
router.include_router(fingerprints_router)

__all__ = ["router"]
