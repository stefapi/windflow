"""Correlation ID middleware for distributed request tracing."""

import logging
from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

from fastapi import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

#: Contextvar du correlation ID (STORY-251 — décision D8).
#:
#: Contrairement à ``request.state`` (limité au cycle de vie de la
#: requête HTTP), une contextvar est propagée aux tâches créées via
#: ``asyncio.create_task`` (copie du contexte d'exécution) : les tâches
#: de déploiement (``deploy_stack_async``) et les couches non-HTTP
#: (circuit breakers) peuvent joindre le correlation_id de la requête
#: d'origine à leurs logs de transition.
#:
#: Valeur ``None`` hors requête HTTP (exécutions scheduler, workers
#: autonomes — hypothèse H3 : loggé sans correlation, acceptable).
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "windflow_correlation_id", default=None
)


def get_correlation_id() -> Optional[str]:
    """Retourne le correlation ID courant, ou ``None`` hors requête HTTP.

    Consommé par les couches non-HTTP (logs de transition des circuit
    breakers — STORY-251) ; en contexte requête, identique au
    ``X-Correlation-ID`` de la réponse (déjà exposé publiquement —
    aucune donnée sensible).
    """
    return correlation_id_var.get()


async def correlation_middleware(request: Request, call_next) -> Response:
    """
    Add correlation ID to requests for distributed tracing.

    - Reads X-Correlation-ID from request headers or generates a new UUID
    - Adds correlation ID to response headers
    - Stores correlation ID in request.state for logging
    - Stores correlation ID in a contextvar (STORY-251) so that tasks
      spawned via ``asyncio.create_task`` (e.g. deployment background
      tasks) inherit it in their logs

    This allows tracking requests across multiple services and log aggregation.
    """
    # Skip WebSocket connections
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    # Get existing correlation ID or generate new one
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid4())

    # Store in request state for access in endpoints and logging
    request.state.correlation_id = correlation_id

    # Store in contextvar for non-HTTP layers (STORY-251) — the token
    # is reset after the request so the worker's context stays clean.
    token = correlation_id_var.set(correlation_id)

    # Process request
    try:
        response = await call_next(request)
    finally:
        correlation_id_var.reset(token)

    # Add to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response
