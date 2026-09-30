"""
Middleware de gestion des erreurs personnalisées.

Capture et formate les exceptions de manière cohérente.

STORY-126.1 : les sorties 422 (validation), SQLAlchemy (500 ``DB_ERROR``)
et 500 (``INTERNAL_ERROR``) de ce middleware adoptent l'enveloppe d'erreur
spec 09 ``{"error": {"code", "message", "details"?}, "correlation_id"?}``
— flag transitoire retiré par STORY-126.3.

STORY-127 : :func:`windflow_exception_handler` convertit toute
:class:`~app.core.exceptions.WindFlowException` non interceptée en
enveloppe d'erreur typée (statut/code portés par la classe). Fonction
réutilisable : enregistrée sur l'app principale via
``app.add_exception_handler`` dans ``main.py`` ET sur les apps de test
minimales (cf. tests docker qui ne montent pas ``main.app``).
"""

import logging
from typing import Any, Optional

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..core.exceptions import CommandExecutionError, WindFlowException
from .api_response import build_error_payload

logger = logging.getLogger(__name__)


async def windflow_exception_handler(
    request: Request, exc: WindFlowException
) -> JSONResponse:
    """Convertit une ``WindFlowException`` en enveloppe spec 09 (STORY-127).

    Routage Starlette par MRO : enregistré sur la classe base, il attrape
    toutes les sous-classes (``APIError``, ``NotFoundError``,
    ``ConflictError``, ``PermissionDeniedError``, ``AuthenticationError``,
    ``RateLimitError``, ``ServiceUnavailableError``…). Réutilise
    :func:`build_error_payload` (format identique STORY-126) et préserve
    le ``correlation_id`` ainsi que les headers de l'exception (ex.
    ``WWW-Authenticate`` sur les 401).

    Sécurité (rules 40) : pas de stack trace ni de donnée sensible —
    ``CommandExecutionError`` voit son ``stderr`` exclu du payload HTTP
    (message générique + ``details`` réduits à command/exit_status ;
    log complet côté serveur uniquement).
    """
    correlation_id: Optional[str] = getattr(request.state, "correlation_id", None)

    # Sécurité : CommandExecutionError → stderr jamais exposé en HTTP
    # (ni dans details, ni dans le message — le message de la classe
    # embarque la sortie stderr brute)
    if isinstance(exc, CommandExecutionError):
        details: Optional[Any] = {
            "command": exc.command,
            "exit_status": exc.exit_status,
        }
        logger.error(
            "Command execution error on %s: command=%r exit_status=%s stderr=%r",
            request.url.path,
            exc.command,
            exc.exit_status,
            exc.stderr,
            extra={"correlation_id": correlation_id},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(
                exc.status_code,
                message="Command execution failed",
                details=details,
                path=request.url.path,
                correlation_id=correlation_id,
            ),
        )
    else:
        details = exc.details or None
        log_fn = logger.error if exc.status_code >= 500 else logger.warning
        log_fn(
            "WindFlow exception on %s: %s [%s] status=%s",
            request.url.path,
            exc.message,
            getattr(exc, "code", type(exc).error_code),
            exc.status_code,
            extra={"correlation_id": correlation_id},
        )

    payload = build_error_payload(
        exc.status_code,
        message=exc.message,
        details=details,
        path=request.url.path,
        correlation_id=correlation_id,
        # Override d'instance (APIError) : ex. INVALID_CREDENTIALS sur le
        # login — prime sur la spécialisation chemin de _status_to_code.
        code=getattr(exc, "code", None),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers=getattr(exc, "http_headers", None),
    )


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
