"""
Routes de gestion des cibles de déploiement.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...database import get_db
from ...models.user import User
from ...schemas.target import TargetResponse, TargetCreate, TargetUpdate, TargetType
from ...schemas.target_scan import (
    ScanResult,
    TargetCapabilitiesResponse,
    TargetDiscoveryRequest,
    TargetDiscoveryResponse,
)
from ...services.target_scanner_service import TargetScannerService
from ...services.target_service import TargetService

router = APIRouter()


@router.get("/", response_model=List[TargetResponse])
async def list_targets(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> List[TargetResponse]:
    """
    Liste les cibles de déploiement de l'organisation.
    """
    targets = await TargetService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return [TargetResponse.model_validate(t) for t in targets]


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """
    Récupère une cible par son ID.
    """
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    return TargetResponse.model_validate(target)


@router.post("/", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    target_data: TargetCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """
    Crée une nouvelle cible de déploiement.
    """
    existing = await TargetService.get_by_name(
        session,
        current_user.organization_id,
        target_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{target_data.name}' existe déjà"
        )

    target = await TargetService.create(
        session,
        target_data,
        organization_id=current_user.organization_id
    )
    return TargetResponse.model_validate(target)


@router.put("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: str,
    target_data: TargetUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """
    Met à jour une cible de déploiement.
    """
    existing_target = await TargetService.get_by_id(session, target_id)
    if not existing_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if existing_target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    if target_data.name and target_data.name != existing_target.name:
        existing_name = await TargetService.get_by_name(
            session,
            current_user.organization_id,
            target_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cible avec le nom '{target_data.name}' existe déjà"
            )

    target = await TargetService.update(session, target_id, target_data)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour de la cible"
        )
    return TargetResponse.model_validate(target)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> None:
    """
    Supprime une cible de déploiement.
    """
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    await TargetService.delete(session, target_id)


@router.post(
    "/discover",
    response_model=TargetDiscoveryResponse,
    status_code=status.HTTP_201_CREATED
)
async def discover_target(
    discovery_request: TargetDiscoveryRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetDiscoveryResponse:
    """
    Découvre automatiquement les capacités d'une machine et crée la cible associée.
    """
    organization_id = discovery_request.organization_id or current_user.organization_id
    if organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Impossible de découvrir une cible pour une autre organisation"
        )

    existing = await TargetService.get_by_name(session, organization_id, discovery_request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cible avec le nom '{discovery_request.name}' existe déjà"
        )

    scanner = TargetScannerService()
    host = discovery_request.host
    is_localhost = host in {"localhost", "127.0.0.1"}

    scan_result = await (
        scanner.scan_localhost()
        if is_localhost
        else scanner.scan_remote(discovery_request)
    )

    target_type = discovery_request.preferred_type or _infer_target_type(scan_result)

    credentials = {
        "username": discovery_request.username,
        "password": discovery_request.password,
    }
    if discovery_request.sudo_user:
        credentials["sudo_user"] = discovery_request.sudo_user
    if discovery_request.sudo_password:
        credentials["sudo_password"] = discovery_request.sudo_password

    target_payload = TargetCreate(
        name=discovery_request.name,
        description=discovery_request.description,
        host=discovery_request.host,
        port=discovery_request.port,
        type=target_type,
        credentials=credentials,
        organization_id=organization_id,
        extra_metadata={
            "auto_discovered": True,
            "discovery_date": scan_result.scan_date.isoformat(),
            "source": "target_discovery_endpoint",
        },
    )

    target = await TargetService.create(
        session,
        target_payload,
        organization_id=organization_id
    )

    await TargetService.update_discovered_capabilities(
        db=session,
        target=target,
        capabilities=scan_result.model_dump(mode="json"),
        scan_date=scan_result.scan_date,
        status="completed" if scan_result.success else "failed"
    )

    return TargetDiscoveryResponse(
        target=TargetResponse.model_validate(target),
        scan_result=scan_result
    )


@router.post("/{target_id}/scan", response_model=TargetResponse)
async def scan_target(
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetResponse:
    """
    Lance un scan des capacités pour une cible existante.
    """
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    scanner = TargetScannerService()
    updated_target = await scanner.scan_and_update_target(target, session)
    return TargetResponse.model_validate(updated_target)


@router.get("/{target_id}/capabilities", response_model=TargetCapabilitiesResponse)
async def get_target_capabilities(
    target_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
) -> TargetCapabilitiesResponse:
    """
    Récupère les capacités découvertes pour une cible.
    """
    target = await TargetService.get_by_id(session, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cible {target_id} non trouvée"
        )

    if target.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette cible"
        )

    scan_result: ScanResult | None = None
    if target.discovered_capabilities:
        try:
            scan_result = ScanResult.model_validate(target.discovered_capabilities)
        except ValidationError:
            scan_result = None

    return TargetCapabilitiesResponse(
        scan_status=target.scan_status,
        last_scan_date=target.last_scan_date,
        scan_result=scan_result
    )


def _infer_target_type(scan_result: ScanResult) -> TargetType:
    """
    Déduit le type de cible à partir des capacités détectées.
    """
    docker_caps = scan_result.docker
    if docker_caps and docker_caps.swarm and docker_caps.swarm.available:
        return TargetType.DOCKER_SWARM
    if docker_caps and docker_caps.installed:
        return TargetType.DOCKER

    if any(tool.available for tool in scan_result.kubernetes.values()):
        return TargetType.KUBERNETES

    if any(tool.available for tool in scan_result.virtualization.values()):
        return TargetType.VM

    return TargetType.PHYSICAL
