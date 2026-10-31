"""Endpoint d'exposition Prometheus ``GET /api/v1/metrics`` (STORY-172 — D5).

**Sans authentification** (exemption sondes spec 09 — pattern
:mod:`app.api.v1.system`) : scrapé par Prometheus sur le réseau interne
Docker uniquement, **jamais routé vers Internet** (aucun router Traefik ne
l'expose ; Prometheus lui-même est behind basic-auth en prod). Voir la
checklist sécurité rules 40 évaluée dans la story.

Le flag ``prometheus_enabled`` gouverne le handler : désactivé → **404**
(choix documenté — l'endpoint reste résolu mais refuse, testable sans
re-création d'app).

La réponse est une ``PlainTextResponse`` au format d'exposition classique
Prometheus (``generate_latest`` + ``CONTENT_TYPE_LATEST``) — le content-type
n'est pas JSON, le middleware d'enveloppe STORY-126 la laisse passer nue.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from prometheus_client import REGISTRY, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from ...config import settings

router = APIRouter()


@router.get(
    "/metrics",
    tags=["metrics"],
    include_in_schema=True,
    summary="Exposition Prometheus (scrape interne)",
    description="""
Exposes all WindFlow Prometheus series in the classic text exposition
format (scraped by the internal Prometheus on the Docker network).

**Series families** (see `app/core/metrics.py` and
`app/websocket/metrics.py`):

- HTTP: `windflow_http_requests_total{method,path,status}`,
  `windflow_http_request_duration_seconds{method,path}` (paths are
  normalized — UUID → `{id}`, numeric → `{n}`; never any query string);
- Deployments: `windflow_deployments_total{result}`,
  `windflow_deployment_duration_seconds`, `windflow_deployments_active`;
- Scheduler: `windflow_scheduler_executions_total{status}`,
  `windflow_scheduler_execution_duration_seconds`;
- WebSocket: `windflow_websocket_*` (14 series).

**No Authentication Required** — probe/scrape endpoint (spec 09
exemptions, same rationale as `/system/health`). Internal Docker network
only: no Traefik router exposes this path to the Internet.

**`prometheus_enabled = false` → 404** (documented behaviour: the route
resolves but the handler refuses — hot-testable without app recreation).
""",
    responses={
        200: {
            "description": (
                "Payload Prometheus (text/plain) — jamais enveloppé "
                "(content-type non JSON, STORY-126)"
            ),
            "content": {
                "text/plain": {
                    "example": (
                        "# HELP windflow_http_requests_total …\n"
                        "# TYPE windflow_http_requests_total counter\n"
                        "windflow_http_requests_total"
                        '{method="GET",path="/api/v1/system/health",'
                        'status="200"} 42\n'
                    )
                }
            },
        },
        404: {
            "description": ("Instrumentation désactivée (``prometheus_enabled=false``)")
        },
    },
)
async def expose_metrics() -> PlainTextResponse:
    """Expose le registre Prometheus global au format texte.

    Raises:
        HTTPException: 404 si ``prometheus_enabled`` est désactivé.
    """
    if not settings.prometheus_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrumentation Prometheus désactivée (prometheus_enabled=false)",
        )
    return PlainTextResponse(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
