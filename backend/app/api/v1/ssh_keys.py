"""Endpoints de gestion des clés SSH réutilisables (STORY-131.2, tâche 9 mère).

Surface REST admin (spec 15 § Hosts distants — gestion des credentials =
Admin+ selon matrice spec 08) : génération serveur, import, consultation
paginée, renommage et suppression contrôlée. Le cycle TOFU des empreintes
d'hôtes vit dans ``api/v1/targets/fingerprints.py`` (tâche 10 mère).

Sécurité (rules 40) :

- tous les endpoints ``Depends(require_admin)`` — un viewer/operator
  reçoit 403, sans token 401 ;
- réponses **sans aucun matériau de clé privée** — ``SSHKeyResponse``
  (schemas 131.2) n'expose ni ``private_key_encrypted`` ni
  ``decrypted_private_key`` ; la clé privée en clair n'apparaît que
  dans les réponses 201 (affichage unique, pattern STORY-124) ;
- audit ``ssh_key.created`` / ``ssh_key.deleted`` via
  ``AuditService.log_from_request`` (details : name/key_type/fingerprint
  — l'empreinte est publique par nature, jamais de secret) ;
- logs d'endpoint limités à key_id/name (jamais de matériau).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...helper.pagination import PaginationQuery, build_meta
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.ssh_key import (
    SSHKeyCreated,
    SSHKeyGenerateRequest,
    SSHKeyImportRequest,
    SSHKeyResponse,
    SSHKeyUpdate,
)
from ...services.audit_service import AuditService
from ...services.ssh_key_service import SSHKeyService

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_response(row, targets_count: int = 0) -> SSHKeyResponse:
    """Construit ``SSHKeyResponse`` avec le compteur de cibles calculé."""
    payload = SSHKeyResponse.model_validate(row).model_dump()
    payload["targets_count"] = targets_count
    return SSHKeyResponse.model_validate(payload)


@router.get(
    "",
    response_model=PaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="List SSH keys",
    description="""
List the reusable SSH keys (STORY-131.2) — paginated `?page&per_page`
(max 100), envelope `PaginatedResponse{data, pagination{...}}` (spec 09).

## Features
- **Shared entity**: a key can be referenced by N targets —
  `targets_count` reports the number of referencing targets
- **No secrets**: responses never include the private key (encrypted or
  clear) — public key and fingerprint only
- **Stable order**: `created_at desc` (most recent first)

## Access control
Requires the global `admin` role (credential management — spec 08).

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Paginated list of SSH keys — enveloppe spec 09",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "3f2b8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                                "name": "prod-deploy-ed25519",
                                "key_type": "ssh-ed25519",
                                "public_key": (
                                    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..."
                                ),
                                "fingerprint": (
                                    "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7"
                                    "QZtoInqt30SgFpc"
                                ),
                                "last_used_at": "2026-10-16T14:22:05Z",
                                "created_at": "2026-10-16T10:00:00Z",
                                "targets_count": 3,
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 1,
                            "pages": 1,
                        },
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_OR_EXPIRED_TOKEN",
                            "message": "Missing or invalid authentication token",
                        }
                    }
                }
            },
        },
        403: {
            "description": "Admin role required (credential management)",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "PERMISSION_DENIED",
                            "message": "Not enough permissions",
                        }
                    }
                }
            },
        },
    },
    tags=["ssh-keys"],
)
async def list_ssh_keys(
    request: Request,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """Liste paginée des clés SSH (STORY-128/131.2).

    Nécessite le rôle global ``admin`` minimum (gestion des credentials
    — matrice spec 08).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing SSH keys",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "page": page,
            "per_page": per_page,
        },
    )
    rows = await SSHKeyService.list_keys(session, page=page, per_page=per_page)
    total = await SSHKeyService.count(session)
    data = [
        _to_response(row, targets_count).model_dump() for row, targets_count in rows
    ]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.post(
    "/generate",
    response_model=SSHKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new SSH key pair (server-side)",
    description="""
Generate a new SSH key pair server-side (STORY-131.2) — `ssh-ed25519`
recommended (default), `ssh-rsa` accepted for legacy targets.

## One-time display
The response carries the **clear private key** — this is the **only**
time it is returned. The server stores exclusively an encrypted copy
(Fernet via SecretManager); once lost, delete and regenerate the key.

## Uniqueness
- `name` must be unique → 409 on duplicate;
- the key material itself is deduplicated by fingerprint → 409 if the
  same key is already registered (invariant of the service).

## Access control
Requires the global `admin` role (credential management — spec 08).

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        201: {
            "description": (
                "Key created — private key displayed ONCE in this response"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "id": "3f2b8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                        "name": "prod-deploy-ed25519",
                        "key_type": "ssh-ed25519",
                        "public_key": ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..."),
                        "fingerprint": (
                            "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
                        ),
                        "last_used_at": None,
                        "created_at": "2026-10-16T10:00:00Z",
                        "targets_count": 0,
                        "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\\n...",
                    }
                }
            },
        },
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        409: {
            "description": "Duplicate name or already-registered key material",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "CONFLICT",
                            "message": (
                                "Une clé SSH nommée « prod-deploy-ed25519 » "
                                "existe déjà"
                            ),
                        }
                    }
                }
            },
        },
        422: {
            "description": "Invalid body (empty/too-long name, unknown key_type)",
        },
    },
    tags=["ssh-keys"],
)
async def generate_ssh_key(
    request: Request,
    data: SSHKeyGenerateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> SSHKeyCreated:
    """Génère une paire de clés SSH côté serveur (affichage unique)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Generating SSH key",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "key_type": data.key_type,
        },
    )
    row, private_key = await SSHKeyService.generate(session, data)

    # Audit (rules 40) : empreinte publique uniquement, jamais de secret.
    await AuditService.log_from_request(
        request,
        "ssh_key.created",
        user=current_user,
        resource_type="ssh_key",
        resource_id=row.id,
        details={
            "name": row.name,
            "key_type": row.key_type,
            "fingerprint": row.fingerprint,
            "origin": "generated",
        },
        db=session,
    )

    response = _to_response(row).model_dump()
    response["private_key"] = private_key
    return SSHKeyCreated.model_validate(response)


@router.post(
    "/import",
    response_model=SSHKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Import an existing SSH private key",
    description="""
Import an existing SSH private key (STORY-131.2) — PEM/OpenSSH formats.

## Passphrase handling
The optional `passphrase` is used **only to read** the key at import
time. The key is then re-stored **passphrase-free but encrypted**
(Fernet via SecretManager) — standard key-manager behavior; subsequent
connections never need the passphrase. The passphrase itself is never
stored nor logged.

## Validation
- unreadable PEM or wrong passphrase → 422 (generic message);
- duplicate `name` or already-registered fingerprint → 409.

## One-time display
The response carries the **clear (decrypted) private key** — the only
time it is returned.

## Access control
Requires the global `admin` role (credential management — spec 08).

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        201: {
            "description": (
                "Key imported — private key displayed ONCE in this response"
            ),
        },
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        409: {"description": "Duplicate name or already-registered fingerprint"},
        422: {
            "description": "Unreadable key or wrong passphrase",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": (
                                "Clé privée illisible ou passphrase incorrecte"
                            ),
                        }
                    }
                }
            },
        },
    },
    tags=["ssh-keys"],
)
async def import_ssh_key(
    request: Request,
    data: SSHKeyImportRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> SSHKeyCreated:
    """Importe une clé privée SSH existante (affichage unique)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Importing SSH key",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
        },
    )
    row, private_key = await SSHKeyService.import_key(session, data)

    await AuditService.log_from_request(
        request,
        "ssh_key.created",
        user=current_user,
        resource_type="ssh_key",
        resource_id=row.id,
        details={
            "name": row.name,
            "key_type": row.key_type,
            "fingerprint": row.fingerprint,
            "origin": "imported",
        },
        db=session,
    )

    response = _to_response(row).model_dump()
    response["private_key"] = private_key
    return SSHKeyCreated.model_validate(response)


@router.get(
    "/{key_id}",
    response_model=SSHKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an SSH key by ID",
    description="""
Retrieve a reusable SSH key by ID (STORY-131.2) — metadata only
(public key, fingerprint, usage), **never the private key**.

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {"description": "SSH key metadata (no private key material)"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        404: {
            "description": "Key not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "SSH key not found: 3f2b8a4f-...",
                        }
                    }
                }
            },
        },
    },
    tags=["ssh-keys"],
)
async def get_ssh_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> SSHKeyResponse:
    """Détail d'une clé SSH (aucun matériau de clé privée)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Getting SSH key %s",
        key_id,
        extra={"correlation_id": correlation_id, "key_id": key_id},
    )
    row = await SSHKeyService.get(session, key_id)
    targets_count = len(await SSHKeyService.targets_using(session, key_id))
    return _to_response(row, targets_count)


@router.put(
    "/{key_id}",
    response_model=SSHKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Rename an SSH key",
    description="""
Rename an SSH key (STORY-131.2). Renaming is the only mutation — key
**rotation is done by creating a new key**, never by mutating material.

Returns 409 if the new name is already taken by another key.

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        200: {"description": "Renamed key"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        404: {"description": "Key not found"},
        409: {"description": "New name already taken"},
        422: {"description": "Invalid body (empty/too-long name)"},
    },
    tags=["ssh-keys"],
)
async def rename_ssh_key(
    request: Request,
    key_id: str,
    data: SSHKeyUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> SSHKeyResponse:
    """Renomme une clé SSH (rotation = nouvelle clé)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Renaming SSH key %s",
        key_id,
        extra={"correlation_id": correlation_id, "key_id": key_id},
    )
    row = await SSHKeyService.rename(session, key_id, data.name)
    targets_count = len(await SSHKeyService.targets_using(session, key_id))
    return _to_response(row, targets_count)


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an SSH key (controlled)",
    description="""
Delete an SSH key (STORY-131.2) — **never silently** when referenced:

- if N targets reference the key (`targets.ssh_key_id`) and
  `force=false` (default) → **409 CONFLICT**: unreference the targets
  first, or pass `force=true` explicitly;
- `force=true` → explicit dereferencing (`targets.ssh_key_id = NULL`
  for all referencing targets), then deletion.

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        204: {"description": "Key deleted (targets dereferenced if force=true)"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        404: {"description": "Key not found"},
        409: {
            "description": "Key still referenced by targets (use force=true)",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "CONFLICT",
                            "message": (
                                "La clé SSH « prod-deploy-ed25519 » est "
                                "référencée par 2 cible(s) — déréférencez-les "
                                "ou utilisez force=true"
                            ),
                        }
                    }
                }
            },
        },
    },
    tags=["ssh-keys"],
)
async def delete_ssh_key(
    request: Request,
    key_id: str,
    force: bool = Query(
        False,
        description=(
            "Dereference all targets using this key before deletion "
            "(explicit opt-in — default false returns 409 if referenced)"
        ),
    ),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Supprime une clé SSH (contrôlée : 409 si référencée sans force)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Deleting SSH key %s (force=%s)",
        key_id,
        force,
        extra={
            "correlation_id": correlation_id,
            "key_id": key_id,
            "force": force,
        },
    )
    row = await SSHKeyService.get(session, key_id)
    name, fingerprint = row.name, row.fingerprint
    dereferenced = await SSHKeyService.delete(session, key_id, force=force)

    await AuditService.log_from_request(
        request,
        "ssh_key.deleted",
        user=current_user,
        resource_type="ssh_key",
        resource_id=key_id,
        details={
            "name": name,
            "fingerprint": fingerprint,
            "force": force,
            "dereferenced_targets": dereferenced,
        },
        db=session,
    )
