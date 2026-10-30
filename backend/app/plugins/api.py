"""SDK des routes API dynamiques des plugins WindFlow (STORY-170.1 — T2).

Contrat public exposé aux plugins extension/hybrid pour étendre l'API
core (spec 11 § Extension de l'API) :

- :func:`plugin_router` : factory retournant un ``APIRouter`` **préfixé**
  ``/api/v1/plugins/{name}`` et tagué ``plugin-{name}`` (documentation
  OpenAPI visible sur ``/docs``). Le nom est validé kebab-case **au
  moment de la factory** (fail-fast à l'import du module du plugin) ;
- ré-exports d'auth : ``get_current_active_user``, ``require_viewer``,
  ``require_operator``, ``require_admin`` — pour que chaque endpoint du
  plugin déclare son RBAC core (spec 08 : lecture Viewer, écriture
  Operator, config Admin).

Garanties du montage (portées par
:class:`~app.services.plugin_api_router_service.PluginApiRouterService`,
pas par cette factory) :

- **préfixe forcé** : un router monté hors de
  ``/api/v1/plugins/{name}`` est refusé (un plugin ne peut pas injecter
  de routes hors de son espace de noms) ;
- **défense en profondeur JWT** : ``get_current_active_user`` est
  injecté au niveau du ``include_router`` même si le plugin l'oublie ;
- **invalidation OpenAPI** : le cache ``app.openapi_schema`` est
  invalidé à chaque montage/démontage (routes visibles/disparues de
  ``/openapi.json``) ;
- **désenregistrement** : les routes sont retirées à la désinstallation
  du plugin.

Divergence assumée (n°3 de l'analyse STORY-170) : ``plugins.name`` est
unique **globalement** (arbitrage 169.3 n°5) → les routes dynamiques
sont montées **process-wide** et la confidentialité repose sur le JWT +
RBAC core (rôle global). Le scoping par organisation par route n'est
pas mis en œuvre (coût par requête, aucune colonne d'appartenance
exploitable au niveau HTTP) — les plugins sensibles appliquent leur
propre vérification dans leurs handlers.

Divergence n°6 : le montage à chaud est process-local — cohérent avec
l'arbitrage F1 (déploiement supporté single-worker).

Exemple :

    from app.plugins.api import (
        plugin_router,
        require_operator,
    )

    router = plugin_router("my-plugin")

    @router.get("/status", dependencies=[Depends(require_viewer)])
    async def status() -> dict:
        return {"ok": True}
"""

from __future__ import annotations

import re

from fastapi import APIRouter

from ..auth.dependencies import get_current_active_user
from ..auth.rbac import require_admin, require_operator, require_viewer

#: Préfixe canonique des routes dynamiques de plugins (spec 11).
PLUGINS_API_PREFIX = "/api/v1/plugins"

#: Pattern kebab-case des noms de plugins (spec 11 § manifest ``name``) :
#: minuscules alphanumériques séparées par des tirets, ni préfixe ni
#: suffixe ``-``.
_KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

__all__ = [
    "PLUGINS_API_PREFIX",
    "get_current_active_user",
    "is_valid_plugin_name",
    "plugin_router",
    "require_admin",
    "require_operator",
    "require_viewer",
]


def is_valid_plugin_name(name: str) -> bool:
    """Vérifie qu'un nom de plugin est kebab-case valide (spec 11).

    Utilisé par la factory (fail-fast) et en défense en profondeur par
    le service de montage (garde de préfixe — STORY-170.1).

    Args:
        name: Nom à valider.

    Returns:
        ``True`` si le nom est kebab-case valide.
    """
    return bool(_KEBAB_CASE_PATTERN.match(name))


def plugin_router(name: str) -> APIRouter:
    """Construit le router API d'un plugin, préfixé et tagué (spec 11).

    La factory applique le contrat standardisé de l'extension de l'API :

    - préfixe ``/api/v1/plugins/{name}`` (espace de noms du plugin —
      la garde de préfixe du service de montage refuse tout router
      hors de cet espace) ;
    - tag OpenAPI ``plugin-{name}`` (regroupement visible sur ``/docs``) ;
    - validation kebab-case de ``name`` **ici** (fail-fast à l'import
      du module du plugin, pas au montage).

    Args:
        name: Nom du plugin (kebab-case, ex. ``"my-plugin"``).

    Returns:
        Un ``APIRouter`` préfixé et tagué, à remplir par le plugin puis
        exposé via la variable module-level ``router``.

    Raises:
        WindFlowException: Si ``name`` n'est pas kebab-case valide
            (``error_type=invalid_plugin_name``).
    """
    from ..core.exceptions import WindFlowException

    if not isinstance(name, str) or not _KEBAB_CASE_PATTERN.match(name):
        raise WindFlowException(
            f"plugin_router : nom de plugin invalide {name!r} — attendu "
            "kebab-case (minuscules alphanumériques et tirets, ex. "
            "'my-plugin')",
            details={"error_type": "invalid_plugin_name", "plugin_name": name},
        )

    return APIRouter(
        prefix=f"{PLUGINS_API_PREFIX}/{name}",
        tags=[f"plugin-{name}"],
    )
