"""Test structurel d'exhaustivité RBAC (STORY-122.7, Tâche 2 — AC 2).

Anti-oubli systémique : toute route ``/api/v1`` non blanchie DOIT porter
une dépendance de protection (``require_*`` / ``get_current_active_user`` /
``get_current_user_ws``). Toute future route non protégée fait échouer la CI.

Divergence documentée (FastAPI 0.141, inclusions lazy ``_IncludedRouter``) :
``app.routes`` n'expose pas directement les routes des sous-routers — un
aplatissement récursif (``original_router`` + cumul des
``include_context.prefix``) reconstruit les chemins absolus (même intention
que le test non-régression Docker qui passe par le schéma OpenAPI).

Canaux WebSocket à auth « premier message » (général, terminal) : la garde
n'est pas une dépendance FastAPI mais réside dans le handler
(``authenticate_ws_first_message`` puis ``ensure_role_ws`` — STORY-122.6) :
vérifiée par inspection du code source du handler.
"""

import inspect
from importlib import import_module

from app.main import app

# Routes API volontairement publiques (liste blanche fermée : toute ajout
# de route publique DOIT modifier explicitement cette liste — revue obligatoire)
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/register",
        # STORY-129 : sondes système sans auth (exemptions spec 09 § Système
        # — signal de démarrage consommé par les orchestrateurs compose/
        # traefik/install ; payload anti-fingerprinting, aucun secret)
        "/api/v1/system/health",
        "/api/v1/system/ready",
    }
)

# Dépendances de protection reconnues. Les factories ``require_role(...)`` /
# ``require_role_ws(...)`` produisent des fermetures nommées ``role_checker`` /
# ``role_checker_ws`` (socle STORY-122.1) ; les dépendances auth historiques
# (``get_current_active_user`` ≡ viewer-equivalent, ``get_current_user_ws``)
# comptent comme protégées.
PROTECTED_DEPENDENCY_NAMES: frozenset[str] = frozenset(
    {
        "role_checker",
        "role_checker_ws",
        "get_current_active_user",
        "get_current_user_ws",
    }
)

# Comptes de routes par module router — garde-fou §2.G : aucun endpoint
# supprimé ; tout ajout/suppression doit être un choix explicite (revue).
EXPECTED_ROUTE_COUNTS: dict[str, int] = {
    # STORY-124.3 : +3 routes /api-keys (POST/GET/DELETE, protégées
    # get_current_active_user) — évolution explicite revue §2.G.
    # STORY-129 : +1 PUT /password (self-service authentifié) — 8 → 9.
    "auth": 9,
    "users": 8,
    "organizations": 10,
    # STORY-166.2 : package targets renommé hosts (mêmes 16 routes —
    # CRUD 5, health-check, capabilities 3, fingerprints 3, discover,
    # scan, test-reachability, test-connection) + router alias
    # targets_legacy (re-montage des 16 mêmes handlers sous /targets,
    # dépréciés — remise à zéro du compteur par la purge 166.6).
    "hosts": 16,
    "targets_legacy": 16,
    # STORY-131.2 : router ssh_keys — 6 routes (list/generate/import/
    # get/put/delete, toutes require_admin).
    "ssh_keys": 6,
    "stacks": 15,
    # STORY-167 : +1 route events (GET /deployments/{id}/events).
    "deployments": 9,
    "workflows": 1,
    "websockets": 8,
    "stats": 2,
    "import_export": 2,
    # STORY-161 : +4 routes exécutions (liste par tâche, vue globale,
    # détail, run manuel) — les 6 routes historiques restent inchangées.
    "schedules": 10,
    "admin": 16,
    "docker": 35,
    "compute": 2,
    "discovery": 2,
    "plugins": 9,
    "plugin_registry": 2,
    # STORY-129 : router system — GET /health + GET /ready sans auth
    # (exemptions spec 09, blanchies dans PUBLIC_PATHS).
    "system": 2,
}

WS_GENERAL = "/api/v1/ws/"
WS_TERMINAL = "/api/v1/ws/terminal/{container_id}"
WS_DEDICATED = (
    "/api/v1/ws/deployments/{deployment_id}/logs",
    "/api/v1/ws/docker/containers/{container_id}/logs",
    "/api/v1/ws/docker/containers/{container_id}/stats",
    "/api/v1/ws/batch/{batch_id}",
)
# Canaux dédiés Operator+ (matrice spec 08 § Hosts — STORY-164.2)
WS_DEDICATED_OPERATOR = (
    "/api/v1/ws/ssh/{host_id}",
    "/api/v1/ws/journal/{host_id}",
)


# --- Helpers -----------------------------------------------------------------


def _flatten_routes(routes: list, prefix: str = "") -> list[tuple[str, object]]:
    """Aplatit récursivement les inclusions lazy de routers FastAPI 0.141.

    Chaque ``_IncludedRouter`` est résolu vers son ``original_router`` avec le
    cumul des préfixes d'inclusion (``include_context.prefix``), produisant
    des couples ``(chemin_absolu, route)``.
    """
    flat: list[tuple[str, object]] = []
    for route in routes:
        if hasattr(route, "original_router") and hasattr(route, "include_context"):
            sub_prefix = prefix + route.include_context.prefix
            flat.extend(_flatten_routes(route.original_router.routes, sub_prefix))
        else:
            flat.append((prefix + getattr(route, "path", "?"), route))
    return flat


def _dependency_names(route) -> set[str]:
    """Noms des fonctions de dépendance de la route (parcours récursif)."""
    names: set[str] = set()
    dependant = getattr(route, "dependant", None)
    stack = [dependant] if dependant is not None else []
    while stack:
        current = stack.pop()
        for sub in getattr(current, "dependencies", []):
            names.add(getattr(sub.call, "__name__", repr(sub.call)))
            stack.append(sub)
    return names


def _api_v1_routes() -> dict[str, object]:
    """Routes ``/api/v1`` aplaties, indexées par chemin."""
    flat = _flatten_routes(app.routes)
    return {path: route for path, route in flat if path.startswith("/api/v1")}


# --- Test 1 : exhaustivité de la protection HTTP ------------------------------


class TestEveryApiRouteIsProtected:
    """Anti-oubli : chaque route HTTP non blanchie porte une dépendance de rôle."""

    def test_every_api_route_is_protected(self):
        """Toute route HTTP ``/api/v1`` non publique → dépendance de protection.

        Message d'erreur actionnable : liste les routes fautives pour
        correction immédiate (ajout ``require_role(...)`` ou liste blanche
        motivée).
        """
        unprotected = []
        for path, route in sorted(_api_v1_routes().items()):
            if path in PUBLIC_PATHS:
                continue
            if type(route).__name__ != "APIRoute":
                continue  # canaux WebSocket : test dédié ci-dessous
            if not (_dependency_names(route) & PROTECTED_DEPENDENCY_NAMES):
                unprotected.append(path)

        assert not unprotected, (
            "Routes /api/v1 sans dépendance de protection (require_role/"
            f"get_current_active_user) : {unprotected} — protéger la route ou "
            "justifier son entrée dans PUBLIC_PATHS (revue obligatoire)"
        )

    def test_public_whitelist_minimal(self):
        """Anti-dérive : chaque entrée de la liste blanche est une route réelle."""
        api_paths = set(_api_v1_routes())
        ghosts = PUBLIC_PATHS - api_paths
        assert (
            not ghosts
        ), f"Entrées de liste blanche inexistantes (routes supprimées ?) : {ghosts}"


# --- Test 2 : canaux WebSocket protégés ----------------------------------------


class TestWebSocketRoutesProtected:
    """Les 5 canaux ``/api/v1/ws/*`` ont une garde auth (+ rôle terminal)."""

    def test_dedicated_channels_have_auth_dependency(self):
        """Logs/stats/déploiements/batch : dépendance ``get_current_user_ws``
        au handshake + garde ``ensure_role_ws`` viewer dans le router."""
        routes = _api_v1_routes()
        for path in WS_DEDICATED:
            route = routes.get(path)
            assert route is not None, f"Canal WebSocket manquant : {path}"
            names = _dependency_names(route)
            assert (
                "get_current_user_ws" in names
            ), f"{path} : dépendance get_current_user_ws absente"

        # Canaux Operator+ (STORY-164.2 — matrice spec 08 § Hosts)
        for path in WS_DEDICATED_OPERATOR:
            route = routes.get(path)
            assert route is not None, f"Canal WebSocket manquant : {path}"
            names = _dependency_names(route)
            assert (
                "get_current_user_ws" in names
            ), f"{path} : dépendance get_current_user_ws absente"

        # Garde de rôle posée dans le router (STORY-122.6 + 164.2) :
        # viewer × (déploiements/logs/stats/batch), operator × (ssh/journal)
        from app.api.v1 import websockets as ws_router_module

        source = inspect.getsource(ws_router_module)
        assert source.count('ensure_role_ws(websocket, user, "viewer"') == len(
            WS_DEDICATED
        ), "Garde ensure_role_ws(viewer) attendue sur les canaux dédiés viewer"
        assert source.count('ensure_role_ws(websocket, user, "operator"') == len(
            WS_DEDICATED_OPERATOR
        ), "Garde ensure_role_ws(operator) attendue sur ssh/journal"

    def test_first_message_channels_guarded_in_handlers(self):
        """Général + terminal : auth premier message + ``ensure_role_ws`` dans
        le handler (garde 1008 sans exécuter le canal — STORY-122.6)."""
        from app.websocket import general as general_module
        from app.websocket import terminal as terminal_module

        general_source = inspect.getsource(general_module)
        assert (
            "authenticate_ws_first_message" in general_source
        ), "Canal général : authenticate_ws_first_message absent du handler"
        assert (
            'ensure_role_ws(websocket, user, "viewer"' in general_source
        ), "Canal général : garde ensure_role_ws(viewer) absente du handler"

        terminal_source = inspect.getsource(terminal_module)
        assert (
            "authenticate_ws_first_message" in terminal_source
        ), "Canal terminal : authenticate_ws_first_message absent du handler"
        assert (
            'ensure_role_ws(websocket, ws_user, "operator"' in terminal_source
        ), "Canal terminal : garde ensure_role_ws(operator) absente du handler"

    def test_websocket_route_inventory(self):
        """Inventaire : exactement les 8 canaux attendus sous ``/api/v1/ws``."""
        ws_paths = {
            path
            for path, route in _api_v1_routes().items()
            if type(route).__name__ == "APIWebSocketRoute"
        }
        expected = {
            WS_GENERAL,
            WS_TERMINAL,
            *WS_DEDICATED,
            *WS_DEDICATED_OPERATOR,
        }
        assert (
            ws_paths == expected
        ), f"Canaux WS inattendus/manquants : {ws_paths ^ expected}"


# --- Test 3 : comptes de routes stables par router ------------------------------


class TestRouterRouteCountsStable:
    """Garde-fou §2.G : aucun endpoint supprimé — comptes par module router."""

    def test_router_route_counts_stable(self):
        """Chaque module router expose exactement le nombre de routes attendu.

        ``targets`` et ``admin`` sont des packages : leurs sous-routers
        (inclusions lazy) sont comptés aplaties.
        """
        mismatches = []
        total = 0
        for module_name, expected in sorted(EXPECTED_ROUTE_COUNTS.items()):
            module = import_module(f"app.api.v1.{module_name}")
            router = getattr(module, "router", None) or getattr(module, "admin_router")
            count = len(_flatten_routes(router.routes))
            total += count
            if count != expected:
                mismatches.append(f"{module_name}: {count} routes (attendu {expected})")

        assert not mismatches, (
            f"Comptes de routes divergents : {mismatches} — toute évolution "
            "doit être un choix explicite (mise à jour du tableau + revue §2.G)"
        )
        assert total == sum(
            EXPECTED_ROUTE_COUNTS.values()
        ), f"Total routes {total} != {sum(EXPECTED_ROUTE_COUNTS.values())}"
