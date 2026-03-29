"""
Middleware de gestion des erreurs personnalisées.

Capture et formate les exceptions de manière cohérente.
"""

import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next):
    """
    Middleware de gestion globale des erreurs.

    Capture les exceptions non gérées et retourne des réponses JSON formatées.
    """
    # Skip WebSocket connections - they handle their own errors
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    try:
        response = await call_next(request)
        return response
    except RequestValidationError as exc:
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "detail": exc.errors(),
                "path": str(request.url),
            },
        )
    except SQLAlchemyError as exc:
        logger.error(f"Database error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Database Error",
                "detail": "An error occurred while accessing the database",
                "path": str(request.url),
            },
        )
    except Exception as exc:
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": (
                    str(exc)
                    if logger.level <= logging.DEBUG
                    else "An unexpected error occurred"
                ),
                "path": str(request.url),
            },
        )
