"""Performance timing middleware for monitoring request duration."""

import time
import logging
from fastapi import Request
from starlette.responses import Response


logger = logging.getLogger(__name__)


async def timing_middleware(request: Request, call_next) -> Response:
    """
    Measure request processing time.

    - Adds X-Process-Time header to response
    - Logs slow requests (>1s) as warnings
    - Useful for performance monitoring and optimization
    """
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate processing time
    process_time = time.time() - start_time
    process_time_ms = process_time * 1000

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
                "process_time_ms": process_time_ms
            }
        )

    return response
