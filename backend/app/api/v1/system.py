"""Router système — santé et readiness sans authentification (STORY-129).

Spec 09 § Système : ``GET /system/health`` et ``GET /system/ready`` sont
**exempts d'authentification** (signal de démarrage consommé par les
orchestrateurs — docker compose healthcheck, Traefik, install). Aucune
dépendance ``get_current_user`` ici (exemptions spec 09, règles 40).

Contrat d'enveloppe (arbitrage n°3 de l'analyse STORY-129) :
- **200** : payload dict → enveloppé ``{"data": ..., "message": null}`` par
  le middleware STORY-126 (aucune exclusion à ajouter) ;
- **503** : ``JSONResponse`` direct **non enveloppé** avec le même payload
  de checks — symétrique du ``/health`` racine historique ; l'orchestrateur
  (``curl -f``) ne lit que le code HTTP.

Rate limiting : volontairement absent — zéro friction pour les sondes
(le ``/health`` racine ne l'est pas non plus ; ``test_rate_limiting.py``
vérifie ce comportement).
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...services.system_service import SystemService

router = APIRouter()


@router.get(
    "/health",
    summary="Health check",
    description="""
Lightweight health check of the WindFlow API (spec 09 — no authentication).

Returns the same payload as the historical root `/health` endpoint:
database connectivity, optional rate-limiter (Redis) storage and global
status. This route is the spec-09 canonical path (`/api/v1/system/health`);
the root `/health` is kept as a non-breaking alias.

**Use `/api/v1/system/ready` instead for startup orchestration** (docker
compose healthchecks, Traefik, install scripts): readiness additionally
verifies that database migrations are applied.

**No Authentication Required** — probe endpoint (spec 09 exemptions).
""",
    responses={
        200: {
            "description": "API healthy — payload enveloppé spec 09",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "status": "healthy",
                            "version": "0.1.0",
                            "environment": "development",
                            "services": {
                                "database": {"status": "healthy", "type": "sqlite"},
                                "rate_limiter": {"status": "healthy"},
                            },
                        },
                        "message": None,
                    }
                }
            },
        },
        503: {
            "description": (
                "API unhealthy — payload **nu** (non enveloppé), "
                "symétrique du /health racine"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "version": "0.1.0",
                        "environment": "development",
                        "services": {
                            "database": {"status": "unhealthy", "type": "sqlite"}
                        },
                    }
                }
            },
        },
    },
    tags=["system"],
)
async def system_health():
    """Health check — délègue à ``SystemService.get_health``."""
    payload = await SystemService.get_health()
    if payload.get("status") != "healthy":
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get(
    "/ready",
    summary="Readiness check",
    description="""
Startup readiness signal for orchestrators (spec 09 — no authentication).

Intended for docker compose healthchecks (`curl -f`), Traefik
`loadbalancer.healthcheck` and install scripts waiting for the API to be
ready. Returns **200 when ready**, **503 with failure causes when not**.

## Checks
- **database**: `SELECT 1` connectivity check
- **migrations**: current Alembic revision (table `alembic_version`) must
  equal the head revision — a non-versioned or partially migrated schema
  makes the API unready
- **redis**: only when rate limiting is enabled and a storage URL is
  configured (optional dependency — absent from checks otherwise)

## Anti-fingerprinting (rules 40)
The response contains **no application version, no environment name and
no connection details** — only the global status, per-check states and
the current/head schema revisions (internal, non-sensitive identifiers).

**Envelope contract**: 200 responses are wrapped in the standard spec-09
envelope (`{"data": ..., "message": null}`); 503 responses are returned
**bare** (orchestrators only read the HTTP status code).

**No Authentication Required** — probe endpoint (spec 09 exemptions).
""",
    responses={
        200: {
            "description": "API ready — payload enveloppé spec 09",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "status": "ready",
                            "checks": {
                                "database": {"status": "healthy"},
                                "migrations": {
                                    "status": "ok",
                                    "current": "a1b2c3d4e5f6",
                                    "head": "a1b2c3d4e5f6",
                                },
                            },
                        },
                        "message": None,
                    }
                }
            },
        },
        503: {
            "description": (
                "API not ready — payload **nu** (non enveloppé) avec les "
                "causes par check"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "status": "unready",
                        "checks": {
                            "database": {"status": "unhealthy"},
                            "migrations": {
                                "status": "pending",
                                "current": None,
                                "head": "a1b2c3d4e5f6",
                            },
                        },
                    }
                }
            },
        },
    },
    tags=["system"],
)
async def system_ready():
    """Readiness check — délègue à ``SystemService.get_readiness``."""
    payload, code = await SystemService.get_readiness()
    if code != 200:
        return JSONResponse(status_code=code, content=payload)
    return payload
