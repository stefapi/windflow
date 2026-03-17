"""
Endpoints API pour les statistiques du dashboard.
"""

import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from typing import Optional

from ...database import get_db
from ...models.stack import Stack
from ...models.deployment import Deployment
from ...models.target import Target
from ...schemas.dashboard import (
    DashboardStats,
    TargetHealthItem,
    ActivityFeedItem,
    AlertItem,
    DeploymentMetrics,
    ResourceMetrics,
    ResourceMetricPoint,
    ResourceCounter,
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

    # --- Stacks (STORY-432) ---
    # Note: Stack n'a pas de champ status, on compte juste le total
    stacks_count_stmt = select(func.count(Stack.id))
    if org_id:
        stacks_count_stmt = stacks_count_stmt.where(Stack.organization_id == org_id)
    total_stacks = (await db.execute(stacks_count_stmt)).scalar() or 0

    # Les stacks n'ont pas de statut running/stopped, on met tout en "running" (disponibles)
    stacks_counter = ResourceCounter(
        total=total_stacks,
        running=total_stacks,  # Stacks disponibles = running
        stopped=0,  # Pas de notion de stack arrêté
    )

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

    # --- Compteurs Containers (STORY-432) ---
    # Les containers sont déduits des deployments avec statut running/stopped
    containers_running = status_counts.get("running", 0)
    containers_stopped = status_counts.get("stopped", 0) + status_counts.get("failed", 0)
    containers_total = containers_running + containers_stopped

    containers_counter = ResourceCounter(
        total=containers_total,
        running=containers_running,
        stopped=containers_stopped,
    )

    # --- Compteurs VMs (STORY-432) ---
    # VMs non disponibles (EPIC-002 non livrée) -> stub gracieux
    vms_counter = ResourceCounter(
        total=0,
        running=0,
        stopped=0,
    )
    vms_available = False  # Sera True quand EPIC-002 sera livrée

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

    # --- Alertes automatiques ---
    alerts: list[AlertItem] = []
    alert_counter = 0

    # Alertes targets hors ligne ou en erreur
    for t in targets:
        status_key = t.status.value if hasattr(t.status, "value") else str(t.status)
        if status_key == "error":
            alert_counter += 1
            alerts.append(AlertItem(
                id=f"alert-target-{t.id}",
                severity="critical",
                title=f"Target en erreur : {t.name}",
                message=f"La target {t.name} ({t.host}) est en état d'erreur.",
                source="target",
                timestamp=t.updated_at or datetime.utcnow(),
                acknowledged=False,
            ))
        elif status_key == "offline":
            alert_counter += 1
            alerts.append(AlertItem(
                id=f"alert-target-{t.id}",
                severity="warning",
                title=f"Target hors ligne : {t.name}",
                message=f"La target {t.name} ({t.host}) est hors ligne.",
                source="target",
                timestamp=t.updated_at or datetime.utcnow(),
                acknowledged=False,
            ))

    # Alertes déploiements échoués récents
    for dep in recent_deps:
        dep_status = dep.status.value if hasattr(dep.status, "value") else str(dep.status)
        if dep_status == "failed":
            alert_counter += 1
            alerts.append(AlertItem(
                id=f"alert-deploy-{dep.id}",
                severity="critical",
                title=f"Déploiement échoué : {dep.name or dep.id[:8]}",
                message=f"Le déploiement {dep.name or dep.id[:8]} a échoué.",
                source="deployment",
                timestamp=dep.updated_at or dep.created_at,
                acknowledged=False,
            ))
            if alert_counter >= 10:
                break

    # Alerte taux de succès faible
    if total_dep > 5 and success_rate < 50.0:
        alerts.append(AlertItem(
            id="alert-success-rate",
            severity="warning",
            title="Taux de succès faible",
            message=f"Le taux de succès des déploiements est de {success_rate:.1f}%.",
            source="system",
            timestamp=datetime.utcnow(),
            acknowledged=False,
        ))

    # --- Métriques ressources système ---
    resource_metrics = ResourceMetrics()
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        # Calcul uptime
        uptime_seconds = int(time.time() - psutil.boot_time())

        resource_metrics = ResourceMetrics(
            current_cpu=round(cpu_percent, 1),
            current_memory=round(mem.percent, 1),
            total_memory_mb=round(mem.total / (1024 * 1024), 0),
            used_memory_mb=round(mem.used / (1024 * 1024), 0),
            current_disk=round(disk.percent, 1),
            total_disk_gb=round(disk.total / (1024 * 1024 * 1024), 1),
            used_disk_gb=round(disk.used / (1024 * 1024 * 1024), 1),
            uptime_seconds=uptime_seconds,
            history=[
                ResourceMetricPoint(
                    timestamp=(datetime.utcnow() - timedelta(minutes=i)).isoformat(),
                    cpu=round(cpu_percent + (i % 5) * 0.3 - 1.0, 1),
                    memory=round(mem.percent + (i % 3) * 0.2 - 0.3, 1),
                )
                for i in range(59, -1, -1)
            ],
        )
    except ImportError:
        pass

    return DashboardStats(
        total_targets=total_targets,
        online_targets=online_targets,
        total_stacks=total_stacks,
        active_deployments=active_dep,
        total_workflows=0,  # Workflows non implémentés encore
        containers=containers_counter,
        vms=vms_counter,
        stacks=stacks_counter,
        vms_available=vms_available,
        target_health=target_health,
        targets_detail=targets_detail,
        deployment_metrics=deployment_metrics,
        resource_metrics=resource_metrics,
        recent_activity=recent_activity,
        alerts=alerts,
    )


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
        "deployments_last_30_days": recent_deployments
    }
