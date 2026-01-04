"""
Endpoints API pour la marketplace WindFlow.

Gestion des stacks publics et déploiements depuis la marketplace.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ...database import get_db
from ...services.marketplace_service import MarketplaceService
from ...schemas.stack import (
    MarketplaceStackResponse,
    StackResponse,
    DeploymentConfigRequest
)
from ...auth.dependencies import get_current_user
from ...models.user import User

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/stacks", response_model=dict)
async def list_marketplace_stacks(
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    search: Optional[str] = Query(None, description="Recherche textuelle"),
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(20, ge=1, le=100, description="Limite résultats"),
    db: AsyncSession = Depends(get_db)
):
    """
    Liste les stacks publics de la marketplace.

    Supporte la recherche textuelle et le filtrage par catégorie.
    """
    stacks, total = await MarketplaceService.list_public_stacks(
        db=db,
        category=category,
        search=search,
        skip=skip,
        limit=limit
    )

    # Convertir en response schema (sans le template complet)
    stack_responses = [
        MarketplaceStackResponse.model_validate(stack)
        for stack in stacks
    ]

    return {
        "data": stack_responses,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/stacks/{stack_id}", response_model=StackResponse)
async def get_marketplace_stack(
    stack_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Récupère les détails complets d'un stack marketplace.

    Inclut le template et les variables pour le déploiement.
    """
    stack = await MarketplaceService.get_stack_details(db, stack_id)

    if not stack:
        raise HTTPException(
            status_code=404,
            detail=f"Stack {stack_id} non trouvé ou non public"
        )

    return StackResponse.model_validate(stack)


@router.get("/categories", response_model=List[str])
async def list_categories(
    db: AsyncSession = Depends(get_db)
):
    """
    Liste les catégories disponibles dans la marketplace.
    """
    categories = await MarketplaceService.get_categories(db)
    return categories


@router.get("/stacks/popular", response_model=List[MarketplaceStackResponse])
async def get_popular_stacks(
    limit: int = Query(10, ge=1, le=50, description="Nombre de stacks"),
    db: AsyncSession = Depends(get_db)
):
    """
    Récupère les stacks les plus populaires (par téléchargements).
    """
    stacks = await MarketplaceService.get_popular_stacks(db, limit)

    return [
        MarketplaceStackResponse.model_validate(stack)
        for stack in stacks
    ]


@router.get("/stacks/recent", response_model=List[MarketplaceStackResponse])
async def get_recent_stacks(
    limit: int = Query(10, ge=1, le=50, description="Nombre de stacks"),
    db: AsyncSession = Depends(get_db)
):
    """
    Récupère les stacks récemment ajoutés.
    """
    stacks = await MarketplaceService.get_recent_stacks(db, limit)

    return [
        MarketplaceStackResponse.model_validate(stack)
        for stack in stacks
    ]


@router.post("/stacks/{stack_id}/deploy", response_model=dict)
async def deploy_marketplace_stack(
    stack_id: str,
    config: DeploymentConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Déploie un stack depuis la marketplace.

    Lance une tâche asyncio pour le déploiement via DeploymentOrchestrator.
    Retourne l'ID du déploiement créé.
    """
    try:
        deployment_id = await MarketplaceService.deploy_from_marketplace(
            db=db,
            stack_id=stack_id,
            config=config,
            user_id=current_user.id
        )

        return {
            "deployment_id": deployment_id,
            "status": "pending",
            "message": "Déploiement lancé avec succès"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du déploiement: {str(e)}")


@router.post("/stacks/{stack_id}/install", response_model=StackResponse)
async def install_stack_to_organization(
    stack_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Copie un stack public dans l'organisation de l'utilisateur.

    Permet de personnaliser un stack marketplace avant déploiement.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=400,
            detail="Utilisateur doit appartenir à une organisation"
        )

    try:
        new_stack = await MarketplaceService.install_to_organization(
            db=db,
            stack_id=stack_id,
            organization_id=current_user.organization_id,
            user_id=current_user.id
        )

        return StackResponse.model_validate(new_stack)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'installation: {str(e)}"
        )
