"""
API REST v1 pour WindFlow.

Points d'entrée pour toutes les routes API version 1.
"""

from fastapi import APIRouter

from .admin import admin_router
from .auth import router as auth_router
from .compute import router as compute_router
from .deployments import router as deployments_router
from .discovery import router as discovery_router
from .docker import router as docker_router
from .hosts import router as hosts_router
from .import_export import router as import_export_router
from .metrics import router as metrics_router
from .organizations import router as organizations_router
from .plugin_registry import router as plugin_registry_router
from .plugins import router as plugins_router
from .schedules import router as schedules_router
from .ssh_keys import router as ssh_keys_router
from .stacks import router as stacks_router
from .stats import router as stats_router
from .system import router as system_router
from .targets_legacy import router as targets_alias_router
from .users import router as users_router
from .websockets import router as websockets_router

# Router principal v1
api_router = APIRouter(prefix="/api/v1")

# Enregistrement des sous-routers
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(
    organizations_router, prefix="/organizations", tags=["organizations"]
)
# STORY-166.2 : surface canonique /hosts (famille Hosts — spec 09) +
# alias /targets déprécié (handlers partagés, header Deprecation,
# removal plan F3 / STORY-166.6).
api_router.include_router(hosts_router, prefix="/hosts", tags=["hosts"])
api_router.include_router(targets_alias_router, tags=["targets"])
# STORY-131.2 : gestion des clés SSH réutilisables (entité globale
# partagée — require_admin sur chaque endpoint, pas de scoping org).
api_router.include_router(ssh_keys_router, prefix="/ssh-keys", tags=["ssh-keys"])
api_router.include_router(stacks_router, prefix="/stacks", tags=["stacks"])
api_router.include_router(
    deployments_router, prefix="/deployments", tags=["deployments"]
)
api_router.include_router(websockets_router, prefix="/ws", tags=["websockets"])
api_router.include_router(stats_router, tags=["statistics"])
api_router.include_router(import_export_router, tags=["import-export"])
api_router.include_router(schedules_router, tags=["schedules"])
api_router.include_router(admin_router)  # Le préfixe /admin est déjà dans le router
api_router.include_router(docker_router, prefix="/docker", tags=["docker"])
api_router.include_router(compute_router, prefix="/compute", tags=["compute"])
api_router.include_router(discovery_router, prefix="/discovery", tags=["discovery"])
api_router.include_router(plugins_router, prefix="/plugins", tags=["plugins"])
api_router.include_router(
    plugin_registry_router, prefix="/registry", tags=["plugin-registry"]
)
api_router.include_router(system_router, prefix="/system", tags=["system"])
# STORY-172 : exposition Prometheus — route /metrics sous /api/v1 (scrape
# interne Docker, sans auth — cf. infrastructure/docker/prometheus.yml),
# 404 si prometheus_enabled=False.
api_router.include_router(metrics_router, tags=["metrics"])

__all__ = ["api_router"]
