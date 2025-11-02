"""
Module de seeding pour initialisation de la base de données.

Crée les données minimales requises au premier démarrage :
- Organisation par défaut
- Utilisateur admin avec droits superuser
- Cible localhost auto-scannée
"""

from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models.organization import Organization
from .models.user import User
from .schemas.user import UserCreate
from .services.user_service import UserService
from .config import settings


async def seed_database(session: AsyncSession) -> None:
    """
    Initialise la base de données avec les données minimales.

    Crée une organisation par défaut et un utilisateur administrateur
    si la base de données est vide (première initialisation).

    Args:
        session: Session de base de données async

    Raises:
        Exception: En cas d'erreur lors du seeding
    """
    try:
        # Vérifier si des organisations existent déjà
        result = await session.execute(select(Organization))
        existing_org = result.scalar_one_or_none()

        if existing_org:
            # Base de données déjà initialisée
            return

        # Créer l'organisation par défaut
        default_org = Organization(
            name=settings.default_org_name,
            slug=settings.default_org_slug,
            description="Organisation créée automatiquement lors de l'initialisation",
            settings={}
        )
        session.add(default_org)
        await session.flush()  # Pour obtenir l'ID de l'organisation

        # Vérifier si un utilisateur admin existe déjà
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Utilisateur admin déjà existant
            await session.commit()
            return

        # Créer l'utilisateur admin
        admin_data = UserCreate(
            email=settings.admin_email,
            username=settings.admin_username,
            full_name=settings.admin_full_name,
            password=settings.admin_password,
            organization_id=default_org.id,
            is_superuser=True
        )

        await UserService.create(session, admin_data)

        target_created, target_messages = await _create_localhost_target(
            session,
            default_org.id
        )

        print(f"✓ Base de données initialisée avec succès")
        print(f"  - Organisation: {default_org.name} ({default_org.slug})")
        print(f"  - Admin: {settings.admin_username} ({settings.admin_email})")
        if target_created:
            print("  - Target: localhost (créée automatiquement)")
        else:
            print("  - Target: localhost non créée (voir détails)")
        for message in target_messages:
            print(f"    • {message}")
        print(f"  - Mot de passe par défaut: {settings.admin_password}")
        print(f"  ⚠️  IMPORTANT: Changez le mot de passe admin en production!")

    except Exception as e:
        await session.rollback()
        print(f"✗ Erreur lors du seeding de la base de données: {e}")
        raise


async def _create_localhost_target(
    session: AsyncSession,
    organization_id: str
) -> Tuple[bool, List[str]]:
    """
    Scanne localhost et crée la cible associée lors du premier démarrage.

    Returns:
        Tuple[bool, List[str]]: Statut de création et détails d'exécution.
    """
    from .schemas.target import TargetCreate
    from .services.target_scanner_service import TargetScannerService
    from .services.target_service import TargetService

    details: List[str] = []
    try:
        scanner = TargetScannerService()
        scan_result = await scanner.scan_localhost()

        target_type = _infer_target_type_from_scan(scan_result)
        details.append(f"type détecté: {target_type.value}")

        if scan_result.docker and scan_result.docker.installed:
            docker_version = scan_result.docker.version or "présent"
            details.append(f"Docker: {docker_version}")
            if scan_result.docker.swarm and scan_result.docker.swarm.available:
                swarm_state = "actif" if scan_result.docker.swarm.active else "disponible"
                details.append(f"Swarm: {swarm_state}")
        libvirt_tool = scan_result.virtualization.get("libvirt")
        if libvirt_tool and libvirt_tool.available:
            details.append(f"Libvirt: {libvirt_tool.version or 'présent'}")

        target_payload = TargetCreate(
            name="localhost",
            description="Local machine automatically discovered during initial database bootstrap",
            host="localhost",
            port=22,
            type=target_type,
            credentials={},
            organization_id=organization_id,
            extra_metadata={
                "auto_created": True,
                "creation_source": "database_seed"
            }
        )

        target = await TargetService.create(session, target_payload)

        capabilities_payload = scanner.build_capabilities_payload(scan_result)
        platform_payload = (
            scan_result.platform.model_dump(mode="json")
            if scan_result.platform
            else None
        )
        os_payload = (
            scan_result.os.model_dump(mode="json")
            if scan_result.os
            else None
        )

        await TargetService.apply_scan_result(
            db=session,
            target=target,
            capabilities=capabilities_payload,
            scan_date=scan_result.scan_date,
            success=scan_result.success,
            platform_info=platform_payload,
            os_info=os_payload
        )
        details.append("capabilities persistées avec succès")
        return True, details

    except Exception as exc:  # noqa: B902 - log et continuer
        details.append(f"erreur: {exc}")
        if "target" in locals():
            await TargetService.mark_scan_failed(session, target)
        return False, details


def _infer_target_type_from_scan(scan_result: "ScanResult") -> "TargetType":
    """Déduit le type de cible optimal depuis un ScanResult."""
    from .schemas.target import TargetType
    from .schemas.target_scan import ScanResult

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


async def check_admin_exists(session: AsyncSession) -> bool:
    """
    Vérifie si un utilisateur admin existe dans la base de données.

    Args:
        session: Session de base de données async

    Returns:
        bool: True si au moins un superuser existe
    """
    result = await session.execute(
        select(User).where(User.is_superuser == True)
    )
    admin = result.scalar_one_or_none()
    return admin is not None
