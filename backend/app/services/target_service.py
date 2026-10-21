"""
Service métier pour gestion des cibles de déploiement.

Implémente le pattern Repository avec SQLAlchemy 2.0 async.
Les horodatages sont gérés par SQLAlchemy (default/onupdate) ;
aucune attribution manuelle de ``updated_at`` n'est nécessaire.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import UnprocessableEntityError
from ..enums.target import CapabilityType, TargetStatus
from ..models.ssh_key import SSHKey
from ..models.target import Target, encrypt_credentials_for_storage
from ..models.target_capability import TargetCapability
from ..schemas.target import TargetCreate, TargetUpdate

logger = logging.getLogger(__name__)

# Limite de concurrence pour les health checks parallèles
_HEALTH_CHECK_CONCURRENCY = 10


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

    @staticmethod
    async def list_by_organizations(
        db: AsyncSession,
        organization_ids: list[str],
        page: int = 1,
        per_page: int = 20,
    ) -> list[Target]:
        """Liste les cibles d'un ensemble d'organisations (STORY-128).

        Requête unique ``WHERE organization_id IN (...)`` avec tri stable
        ``ORDER BY name`` — remplace la boucle par-organisation de
        ``list_targets`` dont l'application de skip/limit **par org**
        produisait des pages chevauchantes et un total faux.

        Args:
            db: Session de base de données async
            organization_ids: Identifiants des organisations scopées
                (appartenances de l'utilisateur)
            page: Page demandée (1-indexée)
            per_page: Taille de page (bornée 1-100 par le Query endpoint)

        Returns:
            Liste des cibles de la page, triée par nom
        """
        if not organization_ids:
            return []
        result = await db.execute(
            select(Target)
            .where(Target.organization_id.in_(organization_ids))
            .order_by(Target.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_by_organizations(
        db: AsyncSession, organization_ids: list[str]
    ) -> int:
        """Compte les cibles d'un ensemble d'organisations (STORY-128).

        ``COUNT`` avec le **même scoping** que
        :meth:`list_by_organizations` (rules 40 — pas d'oracle de
        comptage cross-org).

        Args:
            db: Session de base de données async
            organization_ids: Identifiants des organisations scopées

        Returns:
            Nombre total de cibles correspondant au scoping
        """
        if not organization_ids:
            return 0
        result = await db.execute(
            select(func.count())
            .select_from(Target)
            .where(Target.organization_id.in_(organization_ids))
        )
        return int(result.scalar() or 0)

    # ─── Écriture ──────────────────────────────────────────────

    @staticmethod
    async def _validate_ssh_key_ref(
        db: AsyncSession, ssh_key_id: str | None
    ) -> None:
        """Valide l'existence de la clé SSH référencée (STORY-131.3).

        Args:
            db: Session de base de données async.
            ssh_key_id: Identifiant de clé à valider (``None`` = rien
                à valider).

        Raises:
            UnprocessableEntityError: Clé inexistante (422 — le
                référencement d'une clé supprimée est impossible ; la
                FK resterait de toute façon insatisfiable).
        """
        if ssh_key_id is None:
            return
        exists = (
            await db.execute(select(SSHKey.id).where(SSHKey.id == ssh_key_id))
        ).scalar_one_or_none()
        if exists is None:
            raise UnprocessableEntityError(
                f"La clé SSH {ssh_key_id} référencée n'existe pas"
            )

    @staticmethod
    async def create(
        db: AsyncSession,
        target_data: TargetCreate,
        organization_id: str | None = None,
    ) -> Target:
        """Crée une nouvelle cible (référence clé SSH — STORY-131.3)."""
        await TargetService._validate_ssh_key_ref(db, target_data.ssh_key_id)

        payload = target_data.model_dump(
            exclude={"credentials", "extra_metadata"},
        )
        if organization_id:
            payload["organization_id"] = organization_id

        # Dépréciation (STORY-131.3) : credentials.ssh_private_key →
        # clé référencée ssh_key_id (voie canonique). Warning loggé,
        # pas de rejet : compatibilité transition.
        if target_data.credentials.ssh_private_key:
            logger.warning(
                "target.create legacy ssh_private_key in credentials — "
                "déprécié, référencez une clé SSH (ssh_key_id)"
            )

        # Credentials → dict JSON chiffré via SecretManager (STORY-103.2)
        payload["credentials"] = encrypt_credentials_for_storage(
            target_data.credentials.to_storage_dict()
        )

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
        """Met à jour les informations d'une cible (ssh_key_id — STORY-131.3)."""
        target = await TargetService.get_by_id(db, target_id)
        if target is None:
            return None

        if target_data.ssh_key_id is not None:
            await TargetService._validate_ssh_key_ref(db, target_data.ssh_key_id)

        update_data = target_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return target

        # Handle credentials merge — déchiffrement transparent (STORY-103.2) :
        # la fusion s'effectue sur les credentials en clair, le résultat est
        # ré-encrypté avant persistance.
        if "credentials" in update_data:
            update_data["credentials"] = TargetService._merge_credentials(
                existing=target.decrypted_credentials,
                update_schema=target_data.credentials,
            )
            if update_data["credentials"] is None:
                del update_data["credentials"]
            else:
                update_data["credentials"] = encrypt_credentials_for_storage(
                    update_data["credentials"]
                )

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
        access_profile: dict[str, Any] | None = None,
    ) -> Target:
        """Persiste le résultat d'un scan de capacités.

        Args:
            db: Session de base de données.
            target: Instance de la cible.
            capabilities: Liste des capacités détectées.
            scan_date: Date du scan.
            success: Succès du scan.
            platform_info: Informations de plateforme.
            os_info: Informations OS.
            access_profile: Profil d'accès détecté (dict JSON).
        """
        # Update target fields
        target.scan_date = scan_date
        target.scan_success = success
        target.platform_info = platform_info
        target.os_info = os_info
        target.access_profile = access_profile
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

    # ─── Health Check ──────────────────────────────────────────

    #: Timeout (seconds) for TCP health-check probes.
    HEALTH_CHECK_TIMEOUT: float = 5.0

    @staticmethod
    async def check_health(db: AsyncSession, target: Target) -> TargetStatus:
        """Perform a lightweight TCP reachability probe and persist the result.

        Only tests if the relevant port is open — **no** SSH login or
        Docker API call.  The *status* and *last_check* fields are
        updated in-place and committed.

        Args:
            db: Async database session.
            target: Target model instance (must already be loaded).

        Returns:
            The new :class:`TargetStatus` that was persisted.
        """
        check_time = datetime.now(timezone.utc)
        port = TargetService._get_health_check_port(target)

        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target.host, port),
                timeout=TargetService.HEALTH_CHECK_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
            new_status = TargetStatus.ONLINE
        except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
            new_status = TargetStatus.OFFLINE
        except Exception:
            logger.exception(
                "Unexpected error during health check for target %s",
                target.id,
            )
            new_status = TargetStatus.ERROR

        target.status = new_status
        target.last_check = check_time
        db.add(target)
        await db.commit()
        await db.refresh(target)

        logger.info(
            "Health check for target %s (%s:%s) → %s",
            target.id,
            target.host,
            port,
            new_status.value,
        )
        return new_status

    @staticmethod
    async def check_all_health(db: AsyncSession) -> list[dict[str, Any]]:
        """Lance un health check sur **toutes** les cibles, en parallèle.

        Utilise un sémaphore pour limiter la concurrence à
        ``_HEALTH_CHECK_CONCURRENCY`` cibles simultanées.

        Returns:
            Liste de dicts ``{"target_id": ..., "name": ..., "status": ...}``
            pour chaque cible vérifiée.
        """
        result = await db.execute(select(Target))
        targets = list(result.scalars().all())

        semaphore = asyncio.Semaphore(_HEALTH_CHECK_CONCURRENCY)

        async def _check_one(target: Target) -> dict[str, Any]:
            async with semaphore:
                try:
                    new_status = await TargetService.check_health(db, target)
                    return {
                        "target_id": target.id,
                        "name": target.name,
                        "status": new_status.value,
                    }
                except Exception as exc:
                    logger.error(
                        "Health check failed for target %s: %s", target.id, exc
                    )
                    return {
                        "target_id": target.id,
                        "name": target.name,
                        "error": str(exc),
                    }

        return list(await asyncio.gather(*(_check_one(t) for t in targets)))

    @staticmethod
    def _get_health_check_port(target: Target) -> int:
        """Return the TCP port to probe for reachability.

        Always uses the **configured** port (``target.port``) which
        represents the management channel (typically SSH).  Type-specific
        ports (2376 for Docker, 6443 for K8s…) are rarely exposed on the
        network — Docker is usually accessed via Unix socket over SSH.
        """
        return target.port

    # ─── Private helpers ───────────────────────────────────────

    @staticmethod
    def _merge_credentials(
        existing: dict[str, Any],
        update_schema: Any,
    ) -> dict[str, Any] | None:
        """Fusionne les credentials existants avec la mise à jour.

        Returns None si ``update_schema`` est None (pas de changement).

        Quand ``sudo_enabled`` est explicitement ``False``, supprime
        ``sudo_user`` et ``sudo_password`` du dict stocké.
        """
        if update_schema is None:
            return None

        merged = {**existing}
        new_values = update_schema.model_dump(exclude_unset=True, exclude_none=True)
        merged.update(new_values)

        # Ensure auth_method is stored as string value
        if update_schema.auth_method is not None:
            merged["auth_method"] = update_schema.auth_method.value

        # Handle sudo_enabled: when explicitly set to False, clear sudo fields
        if update_schema.sudo_enabled is False:
            merged["sudo_enabled"] = False
            merged.pop("sudo_user", None)
            merged.pop("sudo_password", None)
        elif update_schema.sudo_enabled is True:
            merged["sudo_enabled"] = True

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
