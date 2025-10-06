"""
Endpoints API pour les statistiques marketplace.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from ...database import get_db
from ...models.stack import Stack
from ...models.deployment import Deployment
from ...models.stack_review import StackReview

router = APIRouter()


@router.get("/stats/marketplace")
async def get_marketplace_stats(db: AsyncSession = Depends(get_db)):
    """Statistiques globales de la marketplace."""

    # Total stacks publics
    total_stacks_stmt = select(func.count()).select_from(Stack).where(Stack.is_public == True)
    total_stacks = (await db.execute(total_stacks_stmt)).scalar()

    # Total déploiements
    total_deployments_stmt = select(func.count()).select_from(Deployment)
    total_deployments = (await db.execute(total_deployments_stmt)).scalar()

    # Déploiements réussis
    success_deployments_stmt = select(func.count()).select_from(Deployment).where(Deployment.status == 'success')
    success_deployments = (await db.execute(success_deployments_stmt)).scalar()

    # Note moyenne globale
    avg_rating_stmt = select(func.avg(Stack.rating)).where(Stack.is_public == True)
    avg_rating = (await db.execute(avg_rating_stmt)).scalar() or 0.0

    # Stacks les plus populaires (par downloads)
    popular_stacks_stmt = (
        select(Stack)
        .where(Stack.is_public == True)
        .order_by(Stack.downloads.desc())
        .limit(10)
    )
    popular_stacks = (await db.execute(popular_stacks_stmt)).scalars().all()

    # Stacks récents
    recent_stacks_stmt = (
        select(Stack)
        .where(Stack.is_public == True)
        .order_by(Stack.created_at.desc())
        .limit(10)
    )
    recent_stacks = (await db.execute(recent_stacks_stmt)).scalars().all()

    return {
        "total_stacks": total_stacks,
        "total_deployments": total_deployments,
        "success_rate": (success_deployments / total_deployments * 100) if total_deployments > 0 else 0,
        "average_rating": float(avg_rating),
        "popular_stacks": [{"id": s.id, "name": s.name, "downloads": s.downloads} for s in popular_stacks],
        "recent_stacks": [{"id": s.id, "name": s.name, "created_at": s.created_at} for s in recent_stacks]
    }


@router.get("/stats/stacks/{stack_id}")
async def get_stack_stats(stack_id: str, db: AsyncSession = Depends(get_db)):
    """Statistiques détaillées d'un stack."""

    # Déploiements par statut
    deployments_by_status_stmt = (
        select(Deployment.status, func.count(Deployment.id))
        .where(Deployment.stack_id == stack_id)
        .group_by(Deployment.status)
    )
    deployments_by_status = (await db.execute(deployments_by_status_stmt)).all()

    # Reviews stats
    reviews_count_stmt = select(func.count()).select_from(StackReview).where(StackReview.stack_id == stack_id)
    reviews_count = (await db.execute(reviews_count_stmt)).scalar()

    # Déploiements sur les 30 derniers jours
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_deployments_stmt = (
        select(func.count())
        .select_from(Deployment)
        .where(Deployment.stack_id == stack_id)
        .where(Deployment.created_at >= thirty_days_ago)
    )
    recent_deployments = (await db.execute(recent_deployments_stmt)).scalar()

    return {
        "deployments_by_status": {status: count for status, count in deployments_by_status},
        "total_reviews": reviews_count,
        "deployments_last_30_days": recent_deployments
    }
