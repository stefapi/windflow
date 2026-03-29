"""
Middleware de logging structuré.

Log toutes les requêtes avec contexte métier en JSON.
"""

import logging
import time

from fastapi import Request

logger = logging.getLogger(__name__)


async def logging_middleware(request: Request, call_next):
    """
    Middleware de logging structuré pour toutes les requêtes.

    Log les informations de requête/réponse avec timing.
    """
    # Skip WebSocket connections to avoid interference
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    start_time = time.time()

    # Log de la requête entrante
    logger.info(
        "Incoming request",
        extra={
            "method": request.method,
            "path": str(request.url.path),
            "query_params": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
        },
    )

    # Traitement de la requête
    response = await call_next(request)

    # Calcul du temps de traitement
    process_time = time.time() - start_time

    # Log de la réponse
    logger.info(
        "Request processed",
        extra={
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "process_time": f"{process_time:.3f}s",
        },
    )

    # Ajouter le header de timing
    response.headers["X-Process-Time"] = str(process_time)

    return response
