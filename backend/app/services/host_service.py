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
from ..enums.host import CapabilityType, HostStatus
from ..models.host import Host, encrypt_credentials_for_storage
from ..models.host_capability import HostCapability
from ..models.ssh_key import SSHKey
from ..schemas.host import HostCreateRequest, HostUpdate

logger = logging.getLogger(__name__)

# Limite de concurrence pour les health checks parallèles
_HEALTH_CHECK_CONCURRENCY = 10


class HostService:
    """Service de gestion des serveurs cibles."""

    # ─── Lecture ────────────────────────────────────────────────

    @staticmethod
    async def get_by_id(db: AsyncSession, host_id: str) -> Host | None:
        """Récupère une cible par son ID."""
        result = await db.execute(select(Host).where(Host.id == host_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(
        db: AsyncSession, organization_id: str, name: str
    ) -> Host | None:
        """Récupère une cible par son nom dans une organisation."""
        result = await db.execute(
            select(Host).where(
                Host.organization_id == organization_id,
                Host.name == name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_organization(
        db: AsyncSession, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[Host]:
        """Liste les cibles d'une organisation."""
        result = await db.execute(
            select(Host)
            .where(Host.organization_id == organization_id)
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
    ) -> list[Host]:
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
            select(Host)
            .where(Host.organization_id.in_(organization_ids))
            .order_by(Host.name)
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
            .select_from(Host)
            .where(Host.organization_id.in_(organization_ids))
        )
        return int(result.scalar() or 0)

    # ─── Écriture ──────────────────────────────────────────────

    @staticmethod
    async def _validate_ssh_key_ref(db: AsyncSession, ssh_key_id: str | None) -> None:
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
        host_data: HostCreateRequest,
        organization_id: str | None = None,
    ) -> Host:
        """Crée une nouvelle cible (référence clé SSH — STORY-131.3)."""
        await HostService._validate_ssh_key_ref(db, host_data.ssh_key_id)

        payload = host_data.model_dump(
            exclude={"credentials", "extra_metadata"},
        )
        if organization_id:
            payload["organization_id"] = organization_id

        # Dépréciation (STORY-131.3) : credentials.ssh_private_key →
        # clé référencée ssh_key_id (voie canonique). Warning loggé,
        # pas de rejet : compatibilité transition.
        if host_data.credentials.ssh_private_key:
            logger.warning(
                "host.create legacy ssh_private_key in credentials — "
                "déprécié, référencez une clé SSH (ssh_key_id)"
            )

        # Credentials → dict JSON chiffré via SecretManager (STORY-103.2)
        payload["credentials"] = encrypt_credentials_for_storage(
            host_data.credentials.to_storage_dict()
        )

        # extra_metadata → metadata column
        if host_data.extra_metadata is not None:
            payload["extra_metadata"] = host_data.extra_metadata

        host = Host(**payload)
        # STORY-166.1 : l'arbitrage TargetType→HostProfile exige l'adresse
        # ``host`` (local/distant) — non garantie à la construction (ordre
        # des kwargs). Le profil est posé après coup via le setter
        # ``type`` (table d'arbitrage + trace ``migrated_type``).
        legacy_type = payload.get("type")
        if legacy_type is not None:
            # hybrid property (setter) : l'assignation est volontaire.
            host.type = legacy_type  # type: ignore[method-assign]
        db.add(host)
        await db.commit()
        await db.refresh(host)
        return host

    @staticmethod
    async def update(
        db: AsyncSession, host_id: str, host_data: HostUpdate
    ) -> Host | None:
        """Met à jour les informations d'une cible (ssh_key_id — STORY-131.3)."""
        host = await HostService.get_by_id(db, host_id)
        if host is None:
            return None

        if host_data.ssh_key_id is not None:
            await HostService._validate_ssh_key_ref(db, host_data.ssh_key_id)

        update_data = host_data.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return host

        # Handle credentials merge — déchiffrement transparent (STORY-103.2) :
        # la fusion s'effectue sur les credentials en clair, le résultat est
        # ré-encrypté avant persistance.
        if "credentials" in update_data:
            update_data["credentials"] = HostService._merge_credentials(
                existing=host.decrypted_credentials,
                update_schema=host_data.credentials,
            )
            if update_data["credentials"] is None:
                del update_data["credentials"]
            else:
                update_data["credentials"] = encrypt_credentials_for_storage(
                    update_data["credentials"]
                )

        for key, value in update_data.items():
            setattr(host, key, value)

        # updated_at is handled by SQLAlchemy onupdate
        db.add(host)
        await db.commit()
        await db.refresh(host)
        return host

    @staticmethod
    async def delete(db: AsyncSession, host_id: str) -> bool:
        """Supprime une cible."""
        host = await HostService.get_by_id(db, host_id)
        if host is None:
            return False

        await db.delete(host)
        await db.commit()
        return True

    # ─── Scan helpers ──────────────────────────────────────────

    @staticmethod
    async def mark_scan_in_progress(db: AsyncSession, host: Host) -> Host:
        """Indique qu'un scan est en cours pour la cible.

        STORY-166.1 : pose le statut canonique ``HostStatus.SCANNING``
        (au lieu de ne toucher que ``scan_success=None``) — la valeur
        legacy ``error`` n'est plus écrite après la migration 1661 ;
        exploitation complète en STORY-166.3.
        """
        host.scan_success = None
        host.status = HostStatus.SCANNING
        db.add(host)
        await db.commit()
        await db.refresh(host)
        return host

    @staticmethod
    async def mark_scan_failed(
        db: AsyncSession, host: Host, scan_date: datetime | None = None
    ) -> Host:
        """Indique qu'un scan a échoué pour la cible.

        STORY-166.1 : ``TargetStatus.ERROR`` legacy → statut canonique
        ``HostStatus.UNREACHABLE`` (table d'arbitrage — la migration
        1661 a déjà converti les données existantes, le service ne doit
        plus écrire de valeur legacy).
        """
        scan_time = scan_date or datetime.now(timezone.utc)
        host.scan_success = False
        host.last_scan_at = scan_time
        host.status = HostStatus.UNREACHABLE
        host.last_check = scan_time
        db.add(host)
        await db.commit()
        await db.refresh(host)
        return host

    @staticmethod
    async def list_capabilities(
        db: AsyncSession,
        host_id: str,
        capability_type: CapabilityType | None = None,
    ) -> list[HostCapability]:
        """Récupère les capacités persistées pour une cible."""
        stmt = select(HostCapability).where(HostCapability.host_id == host_id)
        if capability_type is not None:
            stmt = stmt.where(HostCapability.capability_type == capability_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def apply_scan_result(
        db: AsyncSession,
        host: Host,
        *,
        capabilities: Sequence[dict[str, Any]],
        scan_date: datetime,
        success: bool,
        platform_info: dict[str, Any] | None = None,
        os_info: dict[str, Any] | None = None,
        access_profile: dict[str, Any] | None = None,
    ) -> Host:
        """Persiste le résultat d'un scan de capacités.

        Args:
            db: Session de base de données.
            host: Instance de la cible.
            capabilities: Liste des capacités détectées.
            scan_date: Date du scan.
            success: Succès du scan.
            platform_info: Informations de plateforme.
            os_info: Informations OS.
            access_profile: Profil d'accès détecté (dict JSON).
        """
        # Update host fields (synonyms de transition scan_date/
        # platform_info → last_scan_at/hardware_info, STORY-166.1)
        host.last_scan_at = scan_date
        host.scan_success = success
        host.hardware_info = platform_info
        host.os_info = os_info
        host.access_profile = access_profile
        host.status = HostStatus.ONLINE if success else HostStatus.UNREACHABLE
        host.last_check = scan_date
        # STORY-166.1 : éclat des capacités — payload par capacité du
        # scan (spec 06 ``installed_engines``), remplacé à chaque scan.
        host.installed_engines = [
            {
                "capability_type": cap_dict.get("capability_type"),
                "version": cap_dict.get("version"),
                "is_available": bool(cap_dict.get("is_available", False)),
            }
            for cap_dict in capabilities
            if HostService._resolve_capability_type(cap_dict.get("capability_type"))
            is not None
        ]

        # Delete old capabilities
        await db.execute(
            delete(HostCapability).where(HostCapability.host_id == host.id)
        )

        # Insert new capabilities
        for cap_dict in capabilities:
            cap_model = HostService._build_capability_model(
                host.id, cap_dict, scan_date
            )
            if cap_model is not None:
                db.add(cap_model)

        db.add(host)
        await db.commit()
        await db.refresh(host)
        return host

    # ─── Health Check ──────────────────────────────────────────

    #: Timeout (seconds) for TCP health-check probes.
    HEALTH_CHECK_TIMEOUT: float = 5.0

    @staticmethod
    async def check_health(db: AsyncSession, host: Host) -> HostStatus:
        """Perform a lightweight TCP reachability probe and persist the result.

        Only tests if the relevant port is open — **no** SSH login or
        Docker API call.  The *status* and *last_check* fields are
        updated in-place and committed.

        STORY-166.1 : retourne et persiste le statut canonique
        :class:`~app.enums.host.HostStatus` (l'ancien ``ERROR`` devient
        ``UNREACHABLE`` — table d'arbitrage ; la migration 1661 a déjà
        converti les données existantes).

        Args:
            db: Async database session.
            host: Host model instance (must already be loaded).

        Returns:
            The new :class:`HostStatus` that was persisted.
        """
        check_time = datetime.now(timezone.utc)
        port = HostService._get_health_check_port(host)
        was_online = host.status == HostStatus.ONLINE

        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host.host, port),
                timeout=HostService.HEALTH_CHECK_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
            new_status = HostStatus.ONLINE
        except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
            new_status = HostStatus.OFFLINE
        except Exception:
            logger.exception(
                "Unexpected error during health check for host %s",
                host.id,
            )
            new_status = HostStatus.UNREACHABLE

        # STORY-162 (AC 3, décision 4) : transition joignable→injoignable
        # → événement canonique ``host.offline`` (émetteur naturel = health
        # check périodique). Best-effort après persistance du statut :
        # n'interrompt jamais le cycle de vérification ; payload sans
        # secret (rules 40 — IDs/nom/timestamp).
        if was_online and new_status != HostStatus.ONLINE:
            try:
                from ..core.events import EventType, get_event_bus

                await get_event_bus().emit(
                    EventType.HOST_OFFLINE,
                    {
                        "host_id": str(host.id),
                        "name": host.name,
                        "last_seen": (
                            host.last_check.isoformat() if host.last_check else None
                        ),
                    },
                )
            except Exception:
                logger.warning(
                    "host.offline event emission failed for host %s",
                    host.id,
                )

        host.status = new_status
        host.last_check = check_time
        db.add(host)
        await db.commit()
        await db.refresh(host)

        logger.info(
            "Health check for host %s (%s:%s) → %s",
            host.id,
            host.host,
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
            Liste de dicts ``{"host_id": ..., "name": ..., "status": ...}``
            pour chaque cible vérifiée.
        """
        result = await db.execute(select(Host))
        hosts = list(result.scalars().all())

        semaphore = asyncio.Semaphore(_HEALTH_CHECK_CONCURRENCY)

        async def _check_one(host: Host) -> dict[str, Any]:
            async with semaphore:
                try:
                    new_status = await HostService.check_health(db, host)
                    return {
                        "host_id": host.id,
                        "name": host.name,
                        "status": new_status.value,
                    }
                except Exception as exc:
                    logger.error("Health check failed for host %s: %s", host.id, exc)
                    return {
                        "host_id": host.id,
                        "name": host.name,
                        "error": str(exc),
                    }

        return list(await asyncio.gather(*(_check_one(t) for t in hosts)))

    @staticmethod
    def _get_health_check_port(host: Host) -> int:
        """Return the TCP port to probe for reachability.

        Always uses the **configured** port (``host.port``) which
        represents the management channel (typically SSH).  Type-specific
        ports (2376 for Docker, 6443 for K8s…) are rarely exposed on the
        network — Docker is usually accessed via Unix socket over SSH.
        """
        return host.port

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
        host_id: str,
        cap_dict: dict[str, Any],
        fallback_date: datetime,
    ) -> HostCapability | None:
        """Construit un modèle HostCapability depuis un dict de scan.

        Retourne None si le ``capability_type`` est invalide.
        """
        raw_type = cap_dict.get("capability_type")
        cap_type = HostService._resolve_capability_type(raw_type)
        if cap_type is None:
            return None

        detected_at = HostService._parse_detected_at(
            cap_dict.get("detected_at", fallback_date),
            fallback_date,
        )

        details = cap_dict.get("details")
        if details is not None and not isinstance(details, dict):
            details = None

        return HostCapability(
            host_id=host_id,
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


# Alias de transition (STORY-166.3) — purge par STORY-166.6
TargetService = HostService
