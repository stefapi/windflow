# WindFlow API Middlewares

## Overview

Middlewares are executed in a specific order for each request. Understanding this order is critical for proper functionality.

## Middleware Order

Middlewares are applied in **reverse order** from how they appear in code. The **last** middleware added is the **first** to execute.

### Execution Order (Request → Response)

```
Request
  ↓
1. CORS Middleware (first to receive request)
  ↓
2. Security Headers Middleware
  ↓
3. Timing Middleware (starts timer)
  ↓
4. Correlation ID Middleware
  ↓
5. Logging Middleware
  ↓
6. API Response Envelope Middleware (STORY-126.1)
  ↓
7. Error Handler Middleware
  ↓
8. Route Handler (endpoint function)
  ↓
7. Error Handler Middleware (catches exceptions)
  ↓
6. API Response Envelope Middleware (envelopes 2xx JSON /api/v1 when flag on)
  ↓
5. Logging Middleware (logs response)
  ↓
4. Correlation ID Middleware (adds header)
  ↓
3. Timing Middleware (adds timing header)
  ↓
2. Security Headers Middleware (adds security headers)
  ↓
1. CORS Middleware (adds CORS headers)
  ↓
Response
```

### Code Order in main.py

```python
# This is the REVERSE order of execution:

# 1. Add CORS first (executes FIRST in chain)
app.add_middleware(CORSMiddleware, ...)

# 2. Add Security Headers (executes SECOND)
app.add_middleware(SecurityHeadersMiddleware)

# 3. Add Timing (executes THIRD)
app.middleware("http")(timing_middleware)

# 4. Add Correlation ID (executes FOURTH)
app.middleware("http")(correlation_middleware)

# 5. Add Logging (executes FIFTH)
app.middleware("http")(logging_middleware)

# 6. Add API Response Envelope (executes SIXTH)
app.middleware("http")(api_response_middleware)

# 7. Add Error Handler (executes LAST, catches all errors)
app.middleware("http")(error_handler_middleware)
```

## Middleware Descriptions

### 1. CORS Middleware
- **Purpose**: Handle Cross-Origin Resource Sharing
- **When to modify**: When adding new frontend origins
- **Configuration**: `settings.cors_*` variables

### 2. Security Headers Middleware
- **Purpose**: Add security headers (CSP, HSTS, X-Frame-Options, etc.)
- **When to modify**: When adjusting security policies
- **Configuration**: `settings.csp_*` and `settings.hsts_*` variables

### 3. Timing Middleware
- **Purpose**: Measure request processing time
- **Headers added**: `X-Process-Time`
- **Logging**: Warns on requests > 1 second

### 4. Correlation ID Middleware
- **Purpose**: Add unique ID to each request for tracing
- **Headers**: Reads/sets `X-Correlation-ID`
- **Usage**: Access via `request.state.correlation_id` in endpoints

### 5. Logging Middleware
- **Purpose**: Log all requests and responses
- **Format**: JSON structured logging
- **Includes**: Method, path, status, correlation ID

### 6. API Response Envelope Middleware (STORY-126.1)
- **Purpose**: Wrap 2xx JSON responses of `/api/v1/*` in spec-09 envelopes `{"data": ..., "message": ...}` — systematic since STORY-126.2 (transitional flag removed by STORY-126.3)
- **Position rationale**: Starlette applies the LAST registered middleware as the OUTERMOST. This middleware is registered BEFORE the error handler, making it more inner: on the way out it envelopes the response after correlation/timing (even more inner) have set their headers (copied into the enveloped response), while 500 responses produced by the outermost error handler never pass through it — no double envelope possible. Error responses (non-2xx) pass through untouched (handled by exception handlers).
- **Skips**: WebSocket connections, non-`/api/v1` paths, non-2xx status, `204 No Content`, non-JSON content types, undecodable bodies
- **Configuration**: none — envelopes are always on (flag removed by STORY-126.3)

### 7. Error Handler Middleware
- **Purpose**: Catch and format all exceptions
- **Returns**: Standardized error responses (spec-09 envelope `{"error": {"code", "message"}}` — always, since STORY-126.3)
- **Includes**: Correlation ID in error responses

### Exception handlers (STORY-127) — inside the middleware stack

The `@app.exception_handler(...)` handlers registered in `main.py` live in Starlette's **internal** `ExceptionMiddleware`, which wraps the route handler **inside** all `app.middleware("http")` layers. Execution on error:

```
Route handler raises WindFlowException (typed hierarchy from core/exceptions.py)
  ↓
ExceptionMiddleware (internal) — @app.exception_handler(WindFlowException)
  → envelope {"error": {"code", "message", "details"?}, "correlation_id"?}
  → status/headers from the exception (e.g. 401 + WWW-Authenticate: Bearer)
  ↓
Typed exceptions NEVER reach the outer error_handler_middleware
```

- **`WindFlowException` handler** (STORY-127): routes by MRO — one handler on the base class catches every subclass (`APIError`, `NotFoundError`, `ConflictError`, `PermissionDeniedError`, `AuthenticationError`, `RateLimitError`, `ServiceUnavailableError`, …). It reuses `build_error_payload` (same envelope format as STORY-126) and preserves `correlation_id`. Security (rules 40): `CommandExecutionError.stderr` is excluded from the HTTP payload (full details server-side log only); no stack trace is ever exposed.
- **Fallback**: any `WindFlowException` subclass that would escape (should not happen) is caught by the outer `error_handler_middleware` as a generic 500 `INTERNAL_ERROR`.
- **Unchanged handlers**: `StarletteHTTPException` (framework-level HTTP errors), `RequestValidationError` / pydantic `ValidationError` (422 with Pydantic errors in `error.details`).

## Best Practices

1. **Never modify middleware order** without understanding implications
2. **Always test** after adding new middlewares
3. **Use correlation IDs** in all logging statements
4. **Keep middlewares lightweight** (< 10ms overhead)
5. **Document changes** to middleware configuration

## Testing Middlewares

```bash
# Test CORS
curl -H "Origin: http://localhost:5173" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:8000/api/v1/deployments

# Test Correlation ID
curl -H "X-Correlation-ID: test-123" \
     http://localhost:8000/health

# Test Security Headers
curl -I http://localhost:8000/health

# Test Timing
curl -w "\nTime: %{time_total}s\n" \
     http://localhost:8000/api/v1/deployments
```

## Troubleshooting

### CSP Breaking API Docs

If Scalar/Swagger doesn't work, adjust CSP:

```python
csp_script_src: List[str] = ["'self'", "'unsafe-inline'", "'unsafe-eval'"]
```

### CORS Issues

Check that frontend origin is in `CORS_ORIGINS`:

```bash
CORS_ORIGINS='["http://localhost:5173"]'
```

### Rate Limiting Not Working

Ensure Redis is running:

```bash
docker run -d -p 6379:6379 redis:alpine
```
