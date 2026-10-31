"""Performance timing middleware for monitoring request duration.

STORY-172 (décision D4) : ce middleware est le **point de collecte** des
métriques HTTP Prometheus (aucun nouveau middleware — la pile existante
n'est pas réordonnée, garde-fou §2.G) :

- compteur ``windflow_http_requests_total{method, path, status}`` ;
- histogramme ``windflow_http_request_duration_seconds{method, path}`` ;
- ``call_next`` est wrappé ``try/except`` : une requête qui lève compte
  comme ``status="500"`` puis est re-levée inchangée (l'error handler
  central garde la main) ;
- chemins **normalisés** (UUID → ``{id}``, numérique → ``{n}`` —
  cardinalité bornée), **jamais de query string** en label (peut contenir
  des tokens, rules 40) ;
- le scrape Prometheus lui-même (``/api/v1/metrics``) n'est pas compté ;
- l'instrumentation n'est active que si ``prometheus_enabled`` **et**
  ``enable_timing_middleware`` (défauts True/True) ; le header
  ``X-Process-Time`` et le log des requêtes lentes restent inconditionnels
  au montage du middleware (comportement inchangé quand Prometheus est
  désactivé).
"""

import logging
import time

from fastapi import Request
from starlette.responses import Response

from ..core.metrics import METRICS_SCRAPE_PATH, normalize_path, record_http_request

logger = logging.getLogger(__name__)


async def timing_middleware(request: Request, call_next) -> Response:
    """
    Measure request processing time.

    - Adds X-Process-Time header to response
    - Logs slow requests (>1s) as warnings
    - Records Prometheus HTTP metrics (requests counter + latency histogram,
      STORY-172) when ``prometheus_enabled`` — exceptions counted as 500 then
      re-raised for the central error handler
    """
    # Skip WebSocket connections
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    # STORY-172 : le scrape ne se mesure pas lui-même (boucle infinie de
    # séries autrement à chaque intervalle Prometheus).
    metrics_enabled = (
        request.url.path != METRICS_SCRAPE_PATH and _prometheus_metrics_enabled()
    )

    start_time = time.time()

    # Process request — wrap pour capter les exceptions (compteur 500) puis
    # re-raise inchangé (l'error handler central produit la réponse).
    if metrics_enabled:
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.time() - start_time
            record_http_request(
                request.method,
                normalize_path(request.url.path),
                "500",
                elapsed,
            )
            raise
    else:
        response = await call_next(request)

    # Calculate processing time
    process_time = time.time() - start_time
    process_time_ms = process_time * 1000

    # STORY-172 : compteur + histogramme par route normalisée (best-effort —
    # record_http_request ne lève jamais).
    if metrics_enabled:
        record_http_request(
            request.method,
            normalize_path(request.url.path),
            str(response.status_code),
            process_time,
        )

    # Add to response headers
    response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"

    # Log slow requests
    if process_time > 1.0:
        correlation_id = getattr(request.state, "correlation_id", "unknown")
        logger.warning(
            f"Slow request detected: {request.method} {request.url.path} "
            f"took {process_time_ms:.2f}ms",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "process_time_ms": process_time_ms,
            },
        )

    return response


def _prometheus_metrics_enabled() -> bool:
    """Lit le flag ``prometheus_enabled`` (import local — pattern middlewares)."""
    from ..config import settings

    return bool(settings.prometheus_enabled and settings.enable_timing_middleware)
