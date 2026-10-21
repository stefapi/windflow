"""Sous-router empreintes SSH d'hôtes — cycle TOFU (STORY-131.2, tâche 10 mère).

Consultation, **acceptation explicite** et reset des empreintes d'hôtes
(``known_hosts`` — modèle STORY-131.1, spec 15 § Hosts distants) :

- une empreinte enregistrée mais ``accepted=False`` (PENDING) ne fait
  pas autorité — l'enregistrement runtime des empreintes présentées est
  porté par STORY-131.3 ;
- l'acceptation ne peut **valider qu'une ligne PENDING existante**
  matching ``(hostname, port, key_type)`` avec une empreinte
  strictement identique — sinon 409 : jamais d'ajout ni d'écrasement
  silencieux (anti-MITM) ;
- le reset (DELETE) supprime la ligne : une re-acceptation sera
  requise au prochain cycle TOFU.

Sécurité (rules 40) :

- tous les endpoints ``Depends(require_admin)`` (gestion des hosts —
  matrice spec 08) + **isolation organisationnelle** via
  ``UserOrganizationService.is_member`` (pattern ``targets/crud.py`` —
  une cible étrangère est traitée comme inexistante : 404) ;
- audit ``target.fingerprint_accepted`` / ``target.fingerprint_reset``
  (details sans secret — l'empreinte d'hôte est publique par nature) ;
- événement ``EventType.TARGET_SSH_FINGERPRINT_ACCEPTED`` émis sur le
  bus canonique (STORY-164 consommera).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.rbac import require_admin
from ....core.events import EventType, event_bus
from ....core.exceptions import ConflictError, NotFoundError
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....models.host_ssh_fingerprint import HostSSHFingerprint
from ....models.target import Target
from ....models.user import User
from ....schemas.ssh_key import FingerprintAcceptRequest, HostFingerprintResponse
from ....services.audit_service import AuditService
from ....services.target_service import TargetService
from ....services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_target_for_org(
    session: AsyncSession, current_user: User, target_id: str
) -> Target:
    """Résout une cible en imposant l'isolation organisationnelle.

    Une cible inexistante **ou** appartenant à une organisation dont
    l'utilisateur n'est pas membre est traitée comme inexistante
    (404 — anti-énumération, pattern ``targets/crud.py`` ; le bypass
    superuser est intégré à ``is_member``).

    Args:
        session: Session de base de données async.
        current_user: Utilisateur authentifié (admin).
        target_id: Identifiant de la cible.

    Returns:
        La ``Target`` accessible.

    Raises:
        NotFoundError: Cible inexistante ou étrangère (404).
    """
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise NotFoundError(f"Cible {target_id} non trouvée")

    if not await UserOrganizationService.is_member(
        session, current_user, target.organization_id
    ):
        # Cible d'une organisation étrangère → 404 (pas d'oracle
        # d'existence cross-org).
        raise NotFoundError(f"Cible {target_id} non trouvée")
    return target


@router.get(
    "/{target_id}/ssh-fingerprints",
    response_model=list[HostFingerprintResponse],
    status_code=status.HTTP_200_OK,
    summary="List SSH host fingerprints of a target",
    description="""
List the SSH host fingerprints (known_hosts entries — STORY-131.2)
recorded for a deployment target, with their TOFU status:

- `accepted=false` → **PENDING**: the fingerprint was recorded but does
  not yet make authority — accept it explicitly via
  `POST /targets/{id}/ssh-fingerprints/accept`;
- `accepted=true` → verified at each connection (STORY-131.3 runtime).

A divergence between the presented key and an accepted fingerprint
blocks the connection (anti-MITM, spec 15).

## Access control
Requires the global `admin` role + organization isolation (a foreign
target is reported as not found).

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    responses={
        200: {
            "description": "Fingerprints of the target with TOFU status",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "5a1c9b7e-2d4f-4a6b-9c8d-0e1f2a3b4c5d",
                            "host_id": "550e8400-e29b-41d4-a716-446655440000",
                            "hostname": "prod-vm01.example.com",
                            "port": 22,
                            "key_type": "ssh-ed25519",
                            "fingerprint": (
                                "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
                            ),
                            "accepted": False,
                            "accepted_at": None,
                            "created_at": "2026-10-16T10:00:00Z",
                        }
                    ]
                }
            },
        },
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        404: {"description": "Target not found (or foreign organization)"},
    },
    tags=["targets"],
)
async def list_ssh_fingerprints(
    request: Request,
    target_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[HostFingerprintResponse]:
    """Liste des empreintes SSH d'une cible avec statut TOFU."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing SSH fingerprints for target %s",
        target_id,
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id,
        },
    )
    await _get_target_for_org(session, current_user, target_id)

    rows = (
        (
            await session.execute(
                select(HostSSHFingerprint)
                .where(HostSSHFingerprint.host_id == target_id)
                .order_by(HostSSHFingerprint.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [HostFingerprintResponse.model_validate(row) for row in rows]


@router.post(
    "/{target_id}/ssh-fingerprints/accept",
    response_model=HostFingerprintResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept an SSH host fingerprint (explicit TOFU)",
    description="""
Explicitly accept a **pending** SSH host fingerprint (TOFU — *Trust On
First Use*, STORY-131.2 / spec 15).

## Rules (anti-MITM)
- The payload must match an existing **pending** line for this target
  on `(hostname, port, key_type)`;
- the submitted `fingerprint` must be **strictly identical** to the
  recorded one → otherwise **409 CONFLICT** (a mismatch is a potential
  MITM indicator: never overwrite silently);
- acceptance sets `accepted=true` + `accepted_at` — the fingerprint
  then makes authority for every future connection (STORY-131.3).

## Audit & events
Writes an audit line `target.fingerprint_accepted` and emits a
`TARGET_SSH_FINGERPRINT_ACCEPTED` event (consumed by STORY-164).

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        200: {"description": "Fingerprint accepted (accepted=true)"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        404: {
            "description": (
                "Target not found (or foreign org) / no pending fingerprint "
                "matching (hostname, port, key_type)"
            ),
        },
        409: {
            "description": (
                "Submitted fingerprint differs from the recorded pending one"
            ),
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "CONFLICT",
                            "message": (
                                "L'empreinte soumise diffère de celle "
                                "enregistrée — divergence potentielle (MITM ?)"
                            ),
                        }
                    }
                }
            },
        },
        422: {
            "description": "Invalid payload (malformed fingerprint, missing fields)",
        },
    },
    tags=["targets"],
)
async def accept_ssh_fingerprint(
    request: Request,
    target_id: str,
    data: FingerprintAcceptRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> HostFingerprintResponse:
    """Acceptation explicite TOFU d'une empreinte PENDING existante."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Accepting SSH fingerprint for target %s",
        target_id,
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id,
        },
    )
    await _get_target_for_org(session, current_user, target_id)

    row = (
        await session.execute(
            select(HostSSHFingerprint).where(
                HostSSHFingerprint.host_id == target_id,
                HostSSHFingerprint.hostname == data.hostname,
                HostSSHFingerprint.port == data.port,
                HostSSHFingerprint.key_type == data.key_type,
                HostSSHFingerprint.accepted.is_(False),
            )
        )
    ).scalar_one_or_none()

    if row is None:
        raise NotFoundError(
            "Aucune empreinte PENDING ne correspond à "
            f"({data.hostname}, {data.port}, {data.key_type}) "
            f"pour la cible {target_id}"
        )

    if row.fingerprint != data.fingerprint:
        # Divergence : jamais d'écrasement silencieux (anti-MITM).
        logger.warning(
            "target.fingerprint_mismatch target_id=%s hostname=%s",
            target_id,
            data.hostname,
        )
        raise ConflictError(
            "L'empreinte soumise diffère de celle enregistrée — "
            "divergence potentielle (MITM ?)"
        )

    row.accepted = True
    row.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(row)
    await session.commit()
    await session.refresh(row)

    # Événement canonique (STORY-164 consommera) — payload sans secret.
    await event_bus.emit(
        EventType.TARGET_SSH_FINGERPRINT_ACCEPTED,
        {
            "target_id": target_id,
            "host_id": target_id,
            "hostname": row.hostname,
            "port": row.port,
            "key_type": row.key_type,
            "fingerprint": row.fingerprint,
            "accepted_by": str(current_user.id),
        },
    )

    await AuditService.log_from_request(
        request,
        "target.fingerprint_accepted",
        user=current_user,
        organization_id=None,
        resource_type="host_ssh_fingerprint",
        resource_id=row.id,
        details={
            "target_id": target_id,
            "hostname": row.hostname,
            "port": row.port,
            "key_type": row.key_type,
            "fingerprint": row.fingerprint,
        },
        db=session,
    )

    return HostFingerprintResponse.model_validate(row)


@router.delete(
    "/{target_id}/ssh-fingerprints/{fingerprint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset an SSH host fingerprint (re-acceptance required)",
    description="""
Delete a host fingerprint entry (TOFU reset — STORY-131.2): the next
connection will re-enter the first-use cycle and require a new explicit
acceptance via `POST /targets/{id}/ssh-fingerprints/accept`.

Typical use: host re-provisioning (new host key) after verifying the
change is legitimate.

**Authentication Required — Admin**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        204: {"description": "Fingerprint deleted — re-acceptance required"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin role required"},
        404: {
            "description": (
                "Target not found (or foreign org) / fingerprint not found "
                "for this target"
            ),
        },
    },
    tags=["targets"],
)
async def reset_ssh_fingerprint(
    request: Request,
    target_id: str,
    fingerprint_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Reset d'une empreinte (suppression → re-acceptation requise)."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Resetting SSH fingerprint %s for target %s",
        fingerprint_id,
        target_id,
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "target_id": target_id,
            "fingerprint_id": fingerprint_id,
        },
    )
    await _get_target_for_org(session, current_user, target_id)

    row = (
        await session.execute(
            select(HostSSHFingerprint).where(
                HostSSHFingerprint.id == fingerprint_id,
                HostSSHFingerprint.host_id == target_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(
            f"Empreinte {fingerprint_id} introuvable pour la cible {target_id}"
        )

    hostname, fingerprint = row.hostname, row.fingerprint
    await session.delete(row)
    await session.commit()

    await AuditService.log_from_request(
        request,
        "target.fingerprint_reset",
        user=current_user,
        resource_type="host_ssh_fingerprint",
        resource_id=fingerprint_id,
        details={
            "target_id": target_id,
            "hostname": hostname,
            "fingerprint": fingerprint,
        },
        db=session,
    )
