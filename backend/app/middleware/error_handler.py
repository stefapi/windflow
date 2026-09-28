"""
Middleware de gestion des erreurs personnalisées.

Capture et formate les exceptions de manière cohérente.

STORY-126.1 : les sorties 422 (validation), SQLAlchemy (500 ``DB_ERROR``)
et 500 (``INTERNAL_ERROR``) de ce middleware adoptent l'enveloppe d'erreur
spec 09 ``{"error": {"code", "message", "details"?}, "correlation_id"?}``
— flag transitoire retiré par STORY-126.3.
"""

import logging
from typing import Optional

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .api_response import build_error_payload

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next):
    """
    Middleware de gestion globale des erreurs.

    Capture les exceptions non gérées et retourne des réponses JSON formatées.
    """
    # Skip WebSocket connections - they handle their own errors
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    correlation_id: Optional[str] = getattr(request.state, "correlation_id", None)

    try:
        response = await call_next(request)
        return response
    except RequestValidationError as exc:
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=build_error_payload(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Validation Error",
                details=exc.errors(),
                path=request.url.path,
                correlation_id=correlation_id,
            ),
        )
    except SQLAlchemyError as exc:
        logger.error(f"Database error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error_payload(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An error occurred while accessing the database",
                path=request.url.path,
                correlation_id=correlation_id,
                code="DB_ERROR",
            ),
        )
    except Exception as exc:
        logger.exception(f"Unhandled exception: {exc}")
        detail = (
            str(exc)
            if logger.level <= logging.DEBUG
            else "An unexpected error occurred"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error_payload(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=detail,
                path=request.url.path,
                correlation_id=correlation_id,
            ),
        )
