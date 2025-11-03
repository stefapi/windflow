"""
Service métier pour gestion des cibles de déploiement.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.target import Target, TargetStatus
from ..models.target_capability import CapabilityType, TargetCapability
from ..schemas.target import TargetCreate, TargetUpdate


class TargetService:
    """Service de gestion des serveurs cibles."""

    @staticmethod
    async def get_by_id(db: AsyncSession, target_id: str) -> Optional[Target]:
        """Récupère une cible par son ID."""
        result = await db.execute(select(Target).where(Target.id == target_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(
        db: AsyncSession,
        organization_id: str,
        name: str
    ) -> Optional[Target]:
        """Récupère une cible par son nom dans une organisation."""
        result = await db.execute(
            select(Target).where(
                Target.organization_id == organization_id,
                Target.name == name
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession,
        organization_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Target]:
        """Liste les cibles d'une organisation."""
        result = await db.execute(
            select(Target)
            .where(Target.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        target_data: TargetCreate,
        organization_id: Optional[str] = None
    ) -> Target:
        """Crée une nouvelle cible."""
        payload = target_data.model_dump()
        if organization_id:
            payload["organization_id"] = organization_id

        target = Target(**payload)
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def update(
        db: AsyncSession,
        target_id: str,
        target_data: TargetUpdate
    ) -> Optional[Target]:
        """Met à jour les informations d'une cible."""
        target = await TargetService.get_by_id(db, target_id)
        if target is None:
            return None

        update_data = target_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return target

        for key, value in update_data.items():
            setattr(target, key, value)

        target.updated_at = datetime.utcnow()
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def delete(db: AsyncSession, target_id: str) -> bool:
        """Supprime une cible."""
        target = await TargetService.get_by_id(db, target_id)
        if target is None:
            return False

        await db.delete(target)
        await db.commit()
        return True

    @staticmethod
    async def mark_scan_in_progress(
        db: AsyncSession,
        target: Target
    ) -> Target:
        """Indique qu'un scan est en cours pour la cible."""
        target.scan_success = None
        target.updated_at = datetime.utcnow()

        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def mark_scan_failed(
        db: AsyncSession,
        target: Target,
        scan_date: Optional[datetime] = None
    ) -> Target:
        """Indique qu'un scan a échoué pour la cible."""
        scan_time = scan_date or datetime.utcnow()

        target.scan_success = False
        target.scan_date = scan_time
        target.status = TargetStatus.ERROR
        target.last_check = scan_time
        target.updated_at = datetime.utcnow()

        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def list_capabilities(
        db: AsyncSession,
        target_id: str,
        capability_type: Optional[CapabilityType] = None
    ) -> List[TargetCapability]:
        """Récupère les capacités persistées pour une cible."""
        stmt = select(TargetCapability).where(TargetCapability.target_id == target_id)
        if capability_type is not None:
            stmt = stmt.where(TargetCapability.capability_type == capability_type)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def apply_scan_result(
        db: AsyncSession,
        target: Target,
        *,
        capabilities: Sequence[Dict[str, Any]],
        scan_date: datetime,
        success: bool,
        platform_info: Optional[Dict[str, Any]] = None,
        os_info: Optional[Dict[str, Any]] = None
    ) -> Target:
        """Persiste le résultat d'un scan de capacités."""
        target.scan_date = scan_date
        target.scan_success = success
        target.platform_info = platform_info
        target.os_info = os_info
        target.updated_at = datetime.utcnow()

        # Update status based on scan result
        if success:
            target.status = TargetStatus.ONLINE
        else:
            target.status = TargetStatus.ERROR

        target.last_check = scan_date

        await db.execute(
            delete(TargetCapability).where(TargetCapability.target_id == target.id)
        )

        for capability in capabilities:
            capability_type_value = capability.get("capability_type")
            if isinstance(capability_type_value, CapabilityType):
                capability_type_enum = capability_type_value
            elif isinstance(capability_type_value, str):
                try:
                    capability_type_enum = CapabilityType(capability_type_value)
                except ValueError:
                    continue
            else:
                continue

            detected_at_value = capability.get("detected_at", scan_date)
            if isinstance(detected_at_value, str):
                try:
                    detected_at_value = datetime.fromisoformat(detected_at_value)
                except ValueError:
                    detected_at_value = scan_date

            details_value = capability.get("details")
            if details_value is not None and not isinstance(details_value, dict):
                details_value = None

            db.add(
                TargetCapability(
                    target_id=target.id,
                    capability_type=capability_type_enum,
                    is_available=bool(capability.get("is_available", False)),
                    version=capability.get("version"),
                    details=details_value,
                    detected_at=detected_at_value,
                )
            )

        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target
