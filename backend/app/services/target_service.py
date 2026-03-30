"""
Service métier pour gestion des cibles de déploiement.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
Les horodatages sont gérés par SQLAlchemy (default/onupdate) ;
aucune attribution manuelle de ``updated_at`` n'est nécessaire.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums.target import CapabilityType, TargetStatus
from ..models.target import Target
from ..models.target_capability import TargetCapability
from ..schemas.target import TargetCreate, TargetUpdate


class TargetService:
    """Service de gestion des serveurs cibles."""

    # ─── Lecture ────────────────────────────────────────────────

    @staticmethod
    async def get_by_id(db: AsyncSession, target_id: str) -> Target | None:
        """Récupère une cible par son ID."""
        result = await db.execute(select(Target).where(Target.id == target_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(
        db: AsyncSession, organization_id: str, name: str
    ) -> Target | None:
        """Récupère une cible par son nom dans une organisation."""
        result = await db.execute(
            select(Target).where(
                Target.organization_id == organization_id,
                Target.name == name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[Target]:
        """Liste les cibles d'une organisation."""
        result = await db.execute(
            select(Target)
            .where(Target.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    # ─── Écriture ──────────────────────────────────────────────

    @staticmethod
    async def create(
        db: AsyncSession,
        target_data: TargetCreate,
        organization_id: str | None = None,
    ) -> Target:
        """Crée une nouvelle cible."""
        payload = target_data.model_dump(
            exclude={"credentials", "extra_metadata"},
        )
        if organization_id:
            payload["organization_id"] = organization_id

        # Credentials → dict JSON
        payload["credentials"] = target_data.credentials.to_storage_dict()

        # extra_metadata → metadata column
        if target_data.extra_metadata is not None:
            payload["extra_metadata"] = target_data.extra_metadata

        target = Target(**payload)
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def update(
        db: AsyncSession, target_id: str, target_data: TargetUpdate
    ) -> Target | None:
        """Met à jour les informations d'une cible."""
        target = await TargetService.get_by_id(db, target_id)
        if target is None:
            return None

        update_data = target_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return target

        # Handle credentials merge
        if "credentials" in update_data:
            update_data["credentials"] = TargetService._merge_credentials(
                existing=target.credentials or {},
                update_schema=target_data.credentials,
            )
            if update_data["credentials"] is None:
                del update_data["credentials"]

        for key, value in update_data.items():
            setattr(target, key, value)

        # updated_at is handled by SQLAlchemy onupdate
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

    # ─── Scan helpers ──────────────────────────────────────────

    @staticmethod
    async def mark_scan_in_progress(db: AsyncSession, target: Target) -> Target:
        """Indique qu'un scan est en cours pour la cible."""
        target.scan_success = None
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def mark_scan_failed(
        db: AsyncSession, target: Target, scan_date: datetime | None = None
    ) -> Target:
        """Indique qu'un scan a échoué pour la cible."""
        scan_time = scan_date or datetime.now(timezone.utc)
        target.scan_success = False
        target.scan_date = scan_time
        target.status = TargetStatus.ERROR
        target.last_check = scan_time
        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    @staticmethod
    async def list_capabilities(
        db: AsyncSession,
        target_id: str,
        capability_type: CapabilityType | None = None,
    ) -> list[TargetCapability]:
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
        capabilities: Sequence[dict[str, Any]],
        scan_date: datetime,
        success: bool,
        platform_info: dict[str, Any] | None = None,
        os_info: dict[str, Any] | None = None,
    ) -> Target:
        """Persiste le résultat d'un scan de capacités."""
        # Update target fields
        target.scan_date = scan_date
        target.scan_success = success
        target.platform_info = platform_info
        target.os_info = os_info
        target.status = TargetStatus.ONLINE if success else TargetStatus.ERROR
        target.last_check = scan_date

        # Delete old capabilities
        await db.execute(
            delete(TargetCapability).where(TargetCapability.target_id == target.id)
        )

        # Insert new capabilities
        for cap_dict in capabilities:
            cap_model = TargetService._build_capability_model(target.id, cap_dict, scan_date)
            if cap_model is not None:
                db.add(cap_model)

        db.add(target)
        await db.commit()
        await db.refresh(target)
        return target

    # ─── Private helpers ───────────────────────────────────────

    @staticmethod
    def _merge_credentials(
        existing: dict[str, Any],
        update_schema: Any,
    ) -> dict[str, Any] | None:
        """Fusionne les credentials existants avec la mise à jour.

        Returns None si ``update_schema`` est None (pas de changement).
        """
        if update_schema is None:
            return None

        merged = {**existing}
        new_values = update_schema.model_dump(exclude_unset=True, exclude_none=True)
        merged.update(new_values)

        # Ensure auth_method is stored as string value
        if update_schema.auth_method is not None:
            merged["auth_method"] = update_schema.auth_method.value

        return merged

    @staticmethod
    def _build_capability_model(
        target_id: str,
        cap_dict: dict[str, Any],
        fallback_date: datetime,
    ) -> TargetCapability | None:
        """Construit un modèle TargetCapability depuis un dict de scan.

        Retourne None si le ``capability_type`` est invalide.
        """
        raw_type = cap_dict.get("capability_type")
        cap_type = TargetService._resolve_capability_type(raw_type)
        if cap_type is None:
            return None

        detected_at = TargetService._parse_detected_at(
            cap_dict.get("detected_at", fallback_date), fallback_date,
        )

        details = cap_dict.get("details")
        if details is not None and not isinstance(details, dict):
            details = None

        return TargetCapability(
            target_id=target_id,
            capability_type=cap_type,
            is_available=bool(cap_dict.get("is_available", False)),
            version=cap_dict.get("version"),
            details=details,
            detected_at=detected_at,
        )

    @staticmethod
    def _resolve_capability_type(raw: Any) -> CapabilityType | None:
        """Résout une valeur en CapabilityType ou None."""
        if isinstance(raw, CapabilityType):
            return raw
        if isinstance(raw, str):
            try:
                return CapabilityType(raw)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_detected_at(value: Any, fallback: datetime) -> datetime:
        """Parse une date détectée, avec fallback."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return fallback
        return fallback
