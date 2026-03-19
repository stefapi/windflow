"""Security headers middleware including CSP, HSTS, and other security headers."""

from fastapi import Request
from starlette.responses import Response

from ..config import settings


async def security_headers_middleware(request: Request, call_next) -> Response:
    """
    Add comprehensive security headers to all responses.

    Implements:
    - Content Security Policy (CSP)
    - HTTP Strict Transport Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy

    Note: This middleware skips WebSocket connections to avoid interference
    with WebSocket upgrade handshakes.
    """
    # Skip WebSocket connections - they don't need security headers
    # and BaseHTTPMiddleware-style processing breaks them
    if request.scope.get("type") == "websocket":
        return await call_next(request)

    response = await call_next(request)

    # Content Security Policy
    if settings.csp_enabled:
        response.headers["Content-Security-Policy"] = settings.build_csp_header()

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Clickjacking protection
    response.headers["X-Frame-Options"] = settings.frame_options

    # XSS Protection (legacy but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # HSTS (only in production with HTTPS)
    if settings.hsts_enabled and settings.is_production:
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains; preload"
        )

    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions Policy (restrict browser features)
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
    )

    return response
