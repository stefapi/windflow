"""
Endpoints API pour les statistiques marketplace et dashboard.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from typing import Optional

from ...database import get_db
from ...models.stack import Stack
from ...models.deployment import Deployment
from ...models.target import Target
from ...models.stack_review import StackReview
from ...schemas.dashboard import (
    DashboardStats,
    TargetHealthItem,
    ActivityFeedItem,
    DeploymentMetrics,
)
from ...auth.dependencies import get_current_active_user
from ...models.user import User

router = APIRouter()


@router.get("/stats/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    organization_id: Optional[str] = Query(None, description="ID de l'organisation"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DashboardStats:
    """
    Statistiques consolidées pour le dashboard.

    Agrège les métriques targets, stacks, déploiements et workflows
    filtrées par organisation de l'utilisateur courant.
    """
    org_id = organization_id or current_user.organization_id

    # --- Targets ---
    targets_base = select(Target)
    if org_id:
        targets_base = targets_base.where(Target.organization_id == org_id)
    targets_result = await db.execute(targets_base)
    targets = targets_result.scalars().all()

    total_targets = len(targets)
    target_health: dict[str, int] = {"online": 0, "offline": 0, "error": 0, "maintenance": 0}
    targets_detail: list[TargetHealthItem] = []
    for t in targets:
        status_key = t.status.value if hasattr(t.status, "value") else str(t.status)
        target_health[status_key] = target_health.get(status_key, 0) + 1
        targets_detail.append(TargetHealthItem(
            id=t.id,
            name=t.name,
            status=status_key,
            host=t.host,
            last_check=t.last_check,
        ))
    online_targets = target_health.get("online", 0)

    # --- Stacks ---
    stacks_count_stmt = select(func.count()).select_from(Stack)
    if org_id:
        stacks_count_stmt = stacks_count_stmt.where(Stack.organization_id == org_id)
    total_stacks = (await db.execute(stacks_count_stmt)).scalar() or 0

    # --- Deployments ---
    dep_base = select(Deployment)
    if org_id:
        dep_base = dep_base.where(Deployment.organization_id == org_id)

    # Compteurs par statut
    dep_status_stmt = (
        select(Deployment.status, func.count(Deployment.id))
        .group_by(Deployment.status)
    )
    if org_id:
        dep_status_stmt = dep_status_stmt.where(Deployment.organization_id == org_id)
    dep_status_result = await db.execute(dep_status_stmt)
    status_counts: dict[str, int] = {}
    for s, c in dep_status_result.all():
        key = s.value if hasattr(s, "value") else str(s)
        status_counts[key] = c

    total_dep = sum(status_counts.values())
    success_dep = status_counts.get("running", 0)
    failed_dep = status_counts.get("failed", 0)
    active_dep = status_counts.get("running", 0) + status_counts.get("pending", 0) + status_counts.get("deploying", 0)
    success_rate = (success_dep / total_dep * 100) if total_dep > 0 else 0.0

    deployment_metrics = DeploymentMetrics(
        total=total_dep,
        success=success_dep,
        failed=failed_dep,
        running=active_dep,
        success_rate=round(success_rate, 1),
    )

    # --- Activité récente (derniers déploiements) ---
    recent_dep_stmt = (
        select(Deployment)
        .order_by(Deployment.created_at.desc())
        .limit(20)
    )
    if org_id:
        recent_dep_stmt = recent_dep_stmt.where(Deployment.organization_id == org_id)
    recent_deps = (await db.execute(recent_dep_stmt)).scalars().all()

    recent_activity: list[ActivityFeedItem] = []
    for dep in recent_deps:
        dep_status = dep.status.value if hasattr(dep.status, "value") else str(dep.status)
        recent_activity.append(ActivityFeedItem(
            id=dep.id,
            type="deployment",
            title=f"Déploiement {dep.name or dep.id[:8]}",
            status=dep_status,
            timestamp=dep.created_at,
            details=f"Stack: {dep.stack_id[:8]}... → Target: {dep.target_id[:8]}...",
        ))

    return DashboardStats(
        total_targets=total_targets,
        online_targets=online_targets,
        total_stacks=total_stacks,
        active_deployments=active_dep,
        total_workflows=0,  # Workflows non implémentés encore
        target_health=target_health,
        targets_detail=targets_detail,
        deployment_metrics=deployment_metrics,
        recent_activity=recent_activity,
    )


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
