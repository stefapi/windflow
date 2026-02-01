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
6. Error Handler Middleware
  ↓
7. Route Handler (endpoint function)
  ↓
6. Error Handler Middleware (catches exceptions)
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

# 6. Add Error Handler (executes LAST, catches all errors)
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

### 6. Error Handler Middleware
- **Purpose**: Catch and format all exceptions
- **Returns**: Standardized error responses
- **Includes**: Correlation ID in error responses

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
