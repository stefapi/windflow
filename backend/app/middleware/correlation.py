"""Correlation ID middleware for distributed request tracing."""

import logging
from uuid import uuid4
from fastapi import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)


async def correlation_middleware(request: Request, call_next) -> Response:
    """
    Add correlation ID to requests for distributed tracing.

    - Reads X-Correlation-ID from request headers or generates a new UUID
    - Adds correlation ID to response headers
    - Stores correlation ID in request.state for logging

    This allows tracking requests across multiple services and log aggregation.
    """
    # Get existing correlation ID or generate new one
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid4())

    # Store in request state for access in endpoints and logging
    request.state.correlation_id = correlation_id

    # Process request
    response = await call_next(request)

    # Add to response headers
    response.headers["X-Correlation-ID"] = correlation_id

    return response
