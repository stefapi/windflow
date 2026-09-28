"""Middleware d'enveloppe des réponses API spec 09 (STORY-126.1).

Les réponses 2xx JSON de ``/api/v1/*`` sont transportées sous
``{"data": ..., "message": ...}`` (spec 09 § Format de réponse) —
activation par défaut par STORY-126.2, flag transitoire retiré par
STORY-126.3.

Exclusions (garde-fous STORY-126.1) :
- WebSocket : format ``type``/``data`` distinct (spec 09 § WebSocket) ;
- chemins hors ``/api/v1`` (``/health``, ``/``, ``/docs``…) ;
- statuts non-2xx et ``204`` (body vide) ;
- réponses non-JSON (export YAML/fichiers, ``application/x-tar``…) ;
- corps JSON non décodable : restitution à l'identique.

Ce module porte également les helpers d'erreur partagés par les handlers
d'exception de ``main.py`` et ``error_handler.py`` :
- :func:`_status_to_code` : mapping statut HTTP → code machine spec 09 ;
- :func:`build_error_payload` : construction de l'enveloppe
  ``{"error": {"code", "message", "details"?}, "correlation_id"?}``.
"""

import json
import logging
from http import HTTPStatus
from typing import Any, Awaitable, Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Préfixe des endpoints soumis à l'enveloppe (AC 2 / garde-fous AC 5)
API_PREFIX = "/api/v1"

# Mapping statut HTTP → code machine spec 09 (§ Gestion des erreurs).
# 401 bénéficie d'une spécialisation par chemin (login → INVALID_CREDENTIALS).
_STATUS_CODE_MAP: dict[int, str] = {
    400: "INVALID_INPUT",
    401: "INVALID_OR_EXPIRED_TOKEN",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_ATTEMPTS",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _status_to_code(status_code: int, path: str = "") -> str:
    """Mappe un statut HTTP au code d'erreur machine spec 09.

    Fonction pure (testée unitairement) — table complète :
    400/401/403/404/409/422/429/500/503, spécialisation 401 login,
    défaut ``ERROR_<status>`` pour tout statut non répertorié.

    Args:
        status_code: Statut HTTP de la réponse d'erreur.
        path: Chemin de la requête (spécialise le 401 de ``/auth/login``).

    Returns:
        Code machine stable (ex. ``NOT_FOUND``, ``ERROR_418``).
    """
    if status_code == 401 and path.endswith("/auth/login"):
        return "INVALID_CREDENTIALS"
    code = _STATUS_CODE_MAP.get(status_code)
    if code is not None:
        return code
    return f"ERROR_{status_code}"


def build_error_payload(
    status_code: int,
    *,
    message: Optional[str] = None,
    details: Optional[Any] = None,
    path: str = "",
    correlation_id: Optional[str] = None,
    code: Optional[str] = None,
) -> dict[str, Any]:
    """Construit l'enveloppe d'erreur spec 09.

    Args:
        status_code: Statut HTTP (détermine ``error.code`` via
            :func:`_status_to_code` sauf override explicite).
        message: Message lisible ; défaut : la phrase HTTP standard.
        details: Contexte structuré optionnel (ex. ``exc.errors()``
            Pydantic pour les 422).
        path: Chemin de la requête (spécialisation 401 login).
        correlation_id: Identifiant de corrélation (tracing distribué).
        code: Override du code machine (ex. ``DB_ERROR`` pour les
            erreurs SQLAlchemy).

    Returns:
        Payload ``{"error": {"code", "message", "details"?},
        "correlation_id"?}`` prêt pour ``JSONResponse``.
    """
    try:
        default_message = HTTPStatus(status_code).phrase
    except ValueError:
        default_message = "Request failed"

    payload: dict[str, Any] = {
        "error": {
            "code": code if code else _status_to_code(status_code, path),
            "message": message if message else default_message,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    if correlation_id:
        payload["correlation_id"] = correlation_id
    return payload


def _is_success_json(response: Response) -> bool:
    """Vérifie qu'une réponse est un succès 2xx JSON enveloppable (pas 204)."""
    if response.status_code == 204:
        return False
    if not 200 <= response.status_code < 300:
        return False
    content_type = response.headers.get("content-type", "")
    return "application/json" in content_type


async def _read_body(response: Response) -> bytes:
    """Consomme le body iterator d'une réponse streaming en bytes."""
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, bytes):
            chunks.append(chunk)
        else:
            chunks.append(str(chunk).encode("utf-8"))
    return b"".join(chunks)


def _copy_transport_headers(source: Response, target: JSONResponse) -> None:
    """Copie les headers transport (correlation, timing, rate-limit…).

    ``content-length``/``content-type`` sont recalculés par la nouvelle
    réponse et exclus de la copie.
    """
    for key, value in source.headers.items():
        if key.lower() in ("content-length", "content-type"):
            continue
        target.headers[key] = value


async def api_response_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Enveloppe les réponses 2xx JSON de ``/api/v1/*`` (flag STORY-126.1).

    Position dans la pile : enregistrée AVANT ``error_handler_middleware``
    dans le code — au retour, l'enveloppe s'applique donc APRÈS que
    correlation/timing aient posé leurs headers (copiés dans la réponse
    enveloppée), l'error handler restant le plus externe pour rattraper
    toute exception (cf. ``middleware/README.md``).
    """
    # WebSocket : format type/data distinct (spec 09 § WebSocket)
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    # Hors /api/v1 (docs, /health, /) : jamais enveloppé
    if not request.url.path.startswith(API_PREFIX):
        return await call_next(request)

    response = await call_next(request)

    if not _is_success_json(response):
        return response

    raw_body = await _read_body(response)

    try:
        data = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Corps non décodable : restitution à l'identique, pas d'enveloppe
        logger.warning(
            "Undecodable JSON body on %s — skipping envelope",
            request.url.path,
        )
        return Response(
            content=raw_body,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items()},
        )

    envelope = JSONResponse(
        status_code=response.status_code,
        content={
            "data": data,
            # Header interne optionnel : message de succès transporté
            "message": request.headers.get("X-API-Message"),
        },
    )
    _copy_transport_headers(response, envelope)
    return envelope
