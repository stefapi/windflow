"""
Routes de gestion des déploiements.
"""

from typing import List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.deployment import DeploymentResponse, DeploymentCreate, DeploymentUpdate, DeploymentLogsResponse
from ...services.deployment_service import DeploymentService
from ...auth.dependencies import get_current_active_user
from ...models.user import User

router = APIRouter()


@router.get("/", response_model=List[DeploymentResponse])
async def list_deployments(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste les déploiements de l'organisation.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List[DeploymentResponse]: Liste des déploiements
    """
    deployments = await DeploymentService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )
    return deployments


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère un déploiement par son ID.

    Args:
        deployment_id: ID du déploiement
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        DeploymentResponse: Déploiement demandé

    Raises:
        HTTPException: Si le déploiement n'existe pas ou accès refusé
    """
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier que le déploiement appartient à la même organisation
    if deployment.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    return deployment


@router.get("/{deployment_id}/logs", response_model=DeploymentLogsResponse)
async def get_deployment_logs(
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère les logs d'un déploiement par son ID.

    Args:
        deployment_id: ID du déploiement
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        DeploymentLogsResponse: Logs du déploiement

    Raises:
        HTTPException: Si le déploiement n'existe pas ou accès refusé
    """
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier que le déploiement appartient à la même organisation
    if deployment.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    return DeploymentLogsResponse(
        deployment_id=deployment.id,
        logs=deployment.logs,
        updated_at=deployment.updated_at
    )


@router.post("/", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment_data: DeploymentCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée un nouveau déploiement.

    Args:
        deployment_data: Données du déploiement à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        DeploymentResponse: Déploiement créé

    Raises:
        HTTPException: Si le nom existe déjà dans l'organisation ou si le stack n'existe pas
    """
    # Vérifier que le nom n'existe pas déjà dans l'organisation (seulement si fourni)
    if deployment_data.name:
        existing = await DeploymentService.get_by_name(
            session,
            current_user.organization_id,
            deployment_data.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Déploiement avec le nom '{deployment_data.name}' existe déjà"
            )

    try:
        deployment = await DeploymentService.create(
            session,
            deployment_data,
            current_user.organization_id,
            current_user.id
        )
        return deployment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: UUID,
    deployment_data: DeploymentUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour un déploiement.

    Args:
        deployment_id: ID du déploiement à modifier
        deployment_data: Nouvelles données du déploiement
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        DeploymentResponse: Déploiement mis à jour

    Raises:
        HTTPException: Si le déploiement n'existe pas, accès refusé ou nom en conflit
    """
    # Vérifier que le déploiement existe
    existing_deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not existing_deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if existing_deployment.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if deployment_data.name and deployment_data.name != existing_deployment.name:
        existing_name = await DeploymentService.get_by_name(
            session,
            current_user.organization_id,
            deployment_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Déploiement avec le nom '{deployment_data.name}' existe déjà"
            )

    deployment = await DeploymentService.update(session, str(deployment_id), deployment_data)
    return deployment


@router.post("/{deployment_id}/retry", response_model=DeploymentResponse)
async def retry_deployment(
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Réessaye un déploiement échoué en relançant le même déploiement.

    Args:
        deployment_id: ID du déploiement échoué à réessayer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        DeploymentResponse: Déploiement relancé

    Raises:
        HTTPException: Si le déploiement n'existe pas, accès refusé ou statut invalide
    """
    # Récupérer le déploiement échoué
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if deployment.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    # Vérifier que le déploiement est en statut FAILED ou PENDING
    if deployment.status.value not in ["failed", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le déploiement doit être en statut 'failed' ou 'pending' pour être réessayé (statut actuel: {deployment.status.value})"
        )

    # Relancer le déploiement existant
    success = await DeploymentService.retry_deployment(
        session,
        str(deployment_id),
        str(current_user.id)
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de la relance du déploiement"
        )

    # Récupérer le déploiement mis à jour
    updated_deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    return updated_deployment


@router.post("/{deployment_id}/cancel", response_model=DeploymentResponse)
async def cancel_deployment(
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Annule un déploiement en cours.

    Args:
        deployment_id: ID du déploiement à annuler
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        DeploymentResponse: Déploiement annulé

    Raises:
        HTTPException: Si le déploiement n'existe pas, accès refusé ou statut invalide
    """
    # Récupérer le déploiement
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if deployment.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    # Vérifier que le déploiement peut être annulé
    if deployment.status.value not in ["pending", "deploying"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le déploiement ne peut pas être annulé (statut actuel: {deployment.status.value})"
        )

    # Annuler le déploiement via l'orchestrateur
    from ...services.deployment_orchestrator import DeploymentOrchestrator
    from ...models.deployment import DeploymentStatus

    # Annuler la tâche si elle existe
    await DeploymentOrchestrator.cancel_deployment(str(deployment_id))

    # Mettre à jour le statut
    deployment.status = DeploymentStatus.STOPPED
    deployment.stopped_at = datetime.utcnow()
    if deployment.logs:
        deployment.logs += "\n[SYSTEM] Déploiement annulé par l'utilisateur"
    else:
        deployment.logs = "[SYSTEM] Déploiement annulé par l'utilisateur"

    await session.commit()
    await session.refresh(deployment)

    return deployment


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime un déploiement.

    Args:
        deployment_id: ID du déploiement à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si le déploiement n'existe pas ou accès refusé
    """
    # Vérifier que le déploiement existe
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if deployment.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    await DeploymentService.delete(session, str(deployment_id))
