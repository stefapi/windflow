"""Alias déprécié ``/api/v1/targets/*`` → ``/api/v1/hosts/*`` (STORY-166.2).

Router alias **mince** : il re-monte les handlers canoniques du package
:mod:`app.api.v1.hosts` sans aucune logique dupliquée — les garanties
(RBAC ``require_*``, rate limiting, enveloppes STORY-126/128, isolation
organisationnelle, émissions ``host.*``) sont celles du chemin canonique.

Dépréciation signalée conformément au plan F3 (removal ciblée par
STORY-166.6 — docs/backend_remediation_plan.md §3) :

- headers de réponse ``Deprecation: true`` (RFC 8594 provisional —
  forme ``true`` tant qu'aucune date de retrait ferme n'est arbitrée)
  et ``Sunset`` **indicatif**, posés par le middleware
  :func:`deprecation_headers_middleware` (enregistré dans ``main.py``) :
  contrairement à une dépendance, un middleware couvre **toutes** les
  réponses de l'alias, y compris celles reconstruites par l'error
  handler (401/403/404/422/5xx) — un consommateur de l'alias reçoit
  la marque quelle que soit l'issue de l'appel ;
- OpenAPI : chaque opération de l'alias est marquée ``deprecated: true``
  (propagée par ``APIRouter(deprecated=True)``) et le tag ``targets``
  documente la migration (``main.py`` ``openapi_tags``).

Le chemin canonique ``/hosts`` n'est **jamais** marqué (headers et
``deprecated`` absents — testés par ``test_hosts_alias_contract.py``).

Purge complète de l'alias par STORY-166.6 (suppression du router ET du
middleware).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .hosts import router as hosts_router

#: Date indicative de retrait (ISO 8601) — alignée sur la fin de
#: transition prévue par le plan de remédiation (STORY-166.6). Non
#: contractuelle : l'objectif est d'inciter la migration, pas d'engager
#: une échéance ferme.
_SUNSET_DATE = "2027-01-01"

#: Préfixe des chemins aliasés (montage dans ``api/v1/__init__.py``).
TARGETS_ALIAS_PREFIX = "/api/v1/targets"


class DeprecationHeadersMiddleware:
    """Middleware ASGI pur : marque les réponses de l'alias ``/targets``.

    Implémentation ASGI brute (pas ``BaseHTTPMiddleware``) : le wrapper
    Starlette recrée la réponse au retour, ce qui masquerait les headers
    posés en amont par l'error handler ; ici les headers sont injectés
    au plus près du protocole (``http.response.start``), donc **après**
    tous les middlewares applicatifs — ils ne peuvent plus être perdus.

    Filtre strict sur le préfixe : le canonique ``/hosts`` n'est jamais
    touché.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if not path.startswith(TARGETS_ALIAS_PREFIX):
            await self.app(scope, receive, send)
            return

        async def send_with_deprecation(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"deprecation", b"true"))
                headers.append((b"sunset", _SUNSET_DATE.encode("ascii")))
            await send(message)

        await self.app(scope, receive, send_with_deprecation)


async def deprecation_headers_middleware(request: Request, call_next) -> Response:
    """Versatile ``http`` middleware (inutilisé — conservé pour référence).

    L'implémentation active est :class:`DeprecationHeadersMiddleware`
    (ASGI pur) : un middleware ``http`` fonction-based poserait les
    headers avant le passage dans l'error handler externe, qui les
    perdrait en reconstruisant sa ``JSONResponse``.
    """
    response = await call_next(request)
    return response


router = APIRouter(
    prefix="/targets",
    deprecated=True,
)

# Re-montage à l'identique des handlers canoniques (aucune copie) —
# les opérations héritent de ``deprecated=True`` du router alias.
router.include_router(hosts_router)

__all__ = ["router", "DeprecationHeadersMiddleware", "TARGETS_ALIAS_PREFIX"]
