from __future__ import annotations

"""
Module de seeding pour initialisation de la base de données.

Crée les données minimales requises au premier démarrage :
- Organisation par défaut
- Utilisateur admin avec droits superuser
- Host local auto-détecté avec capacités scannées (STORY-166.5 —
  désactivable via ``AUTO_DETECT_LOCAL_HOST=false``)
"""

from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .enums.host import HostProfile
from .models.organization import Organization
from .models.user import User
from .schemas.user import UserCreate
from .services.user_service import UserService


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
        result = await session.execute(select(Organization).limit(1))
        existing_org = result.scalar_one_or_none()

        if existing_org:
            # Base de données déjà initialisée
            return

        # Créer l'organisation par défaut
        default_org = Organization(
            name=settings.default_org_name,
            slug=settings.default_org_slug,
            description="Organisation créée automatiquement lors de l'initialisation",
            settings={},
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

        # Créer l'utilisateur admin — STORY-121.3 : le User ne porte plus
        # de colonne organisation ; l'association unique (admin) est posée
        # directement (mapping cohérent avec la migration 1213 :
        # superuser → admin, flag is_superuser intact — UserService.create
        # ne saurait rattacher qu'en viewer, ce qui nécessiterait une
        # promotion immédiate)
        admin_data = UserCreate(
            email=settings.admin_email,
            username=settings.admin_username,
            full_name=settings.admin_full_name,
            password=settings.admin_password,
            organization_id=None,  # association posée directement ci-dessous
            is_superuser=True,
        )

        admin = await UserService.create(session, admin_data)

        from .enums.rbac import Role
        from .models.user_organization import UserOrganization

        session.add(
            UserOrganization(
                user_id=admin.id,
                organization_id=default_org.id,
                role=Role.ADMIN,
            )
        )
        await session.commit()

        print("✓ Base de données initialisée avec succès")
        print(f"  - Organisation: {default_org.name} ({default_org.slug})")
        print(f"  - Admin: {settings.admin_username} ({settings.admin_email})")
        if settings.auto_detect_local_host:
            host_created, host_messages = await _create_local_host(
                session, default_org.id
            )
            if host_created:
                print("  - Host: localhost (créé automatiquement)")
            else:
                print("  - Host: localhost non créé (voir détails)")
            for message in host_messages:
                print(f"    • {message}")
        else:
            # Setting off (STORY-166.5) : aucun scan, aucun host créé
            # (AC 1) — le chargement des stack definitions ci-dessous
            # continue normalement (le setting ne porte que sur le host).
            print(
                "  - Host local: auto-détection désactivée "
                "(AUTO_DETECT_LOCAL_HOST=false)"
            )
        print(
            "  - Mot de passe admin: configuré via ADMIN_PASSWORD/SUPERADMIN_PASSWORD"
        )
        print("  ⚠️  IMPORTANT: Changez le mot de passe admin en production!")

        # Charger les définitions de stacks
        await seed_stack_definitions(session, default_org.id)

    except Exception as e:
        await session.rollback()
        print(f"✗ Erreur lors du seeding de la base de données: {e}")
        raise


async def _create_local_host(
    session: AsyncSession, organization_id: str
) -> Tuple[bool, List[str]]:
    """Scanne localhost et crée le host local au premier démarrage (STORY-166.5).

    Aligné sur le modèle ``Host`` canonique (STORY-166.1) :

    - profil canonique ``host_baremetal`` (pilotage direct de la machine
      locale — un Docker sur socket local est ``host_baremetal``, pas
      ``host_remote_docker``) ;
    - ``origin=managed`` : le host est seedé/piloté par WindFlow lui-même
      (arbitrage cohérent 166.4 T5 — ``WorkloadOrigin`` décrit la
      provenance du pilotage, ``external`` serait mensonger) ;
    - ``extra_metadata`` trace la création : ``creation_source=
      "database_seed"`` + ``seed_profile="host_baremetal"``.

    Arbitrage ``host.added`` (analyse STORY-166.5) : **pas d'émission au
    seed** — le bus d'événements n'est pas encore consommable au bootstrap
    (le seed tourne dans le lifespan, avant la mise à disposition de
    l'API/bus) ; l'émission serait au mieux du bruit best-effort. La
    traçabilité est garantie par ``extra_metadata.creation_source``.

    Idempotence : garde explicite ``get_by_name("localhost")`` avant tout
    scan/création — un redémarrage ne duplique jamais le host (AC 2) et
    le scan coûteux n'est pas relancé inutilement.

    Sécurité (règle 40) : ``SSHCredentials(auth_method=LOCAL)`` — aucun
    credentials réel, aucun ``connection_config`` ; les détails remontés
    en console ne contiennent que des versions d'outils détectés.

    Returns:
        Tuple[bool, List[str]]: Statut de création et détails d'exécution.
    """
    from .enums.host import SSHAuthMethod as _SSHAuthMethod
    from .enums.host import WorkloadOrigin
    from .schemas.host import HostCreateRequest
    from .schemas.host import SSHCredentials as _SSHCredentials
    from .services.host_scan_parsers import build_capabilities_payload
    from .services.host_scanner_service import HostScannerService
    from .services.host_service import HostService

    details: List[str] = []

    # Idempotence explicite (AC 2) : ne jamais dupliquer le host local.
    existing = await HostService.get_by_name(session, organization_id, "localhost")
    if existing is not None:
        details.append("host localhost déjà présent, ignoré")
        return False, details

    try:
        scanner = HostScannerService()
        scan_result = await scanner.scan_localhost()

        profile = _default_seed_host_profile()
        details.append(f"profil seed par défaut: {profile.value}")

        if scan_result.docker and scan_result.docker.installed:
            docker_version = scan_result.docker.version or "présent"
            details.append(f"Docker: {docker_version}")
            if scan_result.docker.swarm and scan_result.docker.swarm.available:
                swarm_state = (
                    "actif" if scan_result.docker.swarm.active else "disponible"
                )
                details.append(f"Swarm: {swarm_state}")
        libvirt_tool = scan_result.virtualization.get("libvirt")
        if libvirt_tool and libvirt_tool.available:
            details.append(f"Libvirt: {libvirt_tool.version or 'présent'}")

        host_payload = HostCreateRequest(
            name="localhost",
            description="Local machine automatically discovered during initial database bootstrap",
            host="localhost",
            port=22,
            profile=profile,
            credentials=_SSHCredentials(auth_method=_SSHAuthMethod.LOCAL),
            organization_id=organization_id,
            extra_metadata={
                "auto_created": True,
                "creation_source": "database_seed",
                "seed_profile": "host_baremetal",
            },
        )

        host = await HostService.create(session, host_payload)

        # origin explicite (arbitrage analyse : managed — cf. docstring).
        host.origin = WorkloadOrigin.MANAGED
        session.add(host)
        await session.commit()

        capabilities_payload = build_capabilities_payload(scan_result)
        platform_payload = (
            scan_result.platform.model_dump(mode="json")
            if scan_result.platform
            else None
        )
        os_payload = scan_result.os.model_dump(mode="json") if scan_result.os else None

        await HostService.apply_scan_result(
            db=session,
            host=host,
            capabilities=capabilities_payload,
            scan_date=scan_result.scan_date,
            success=scan_result.success,
            platform_info=platform_payload,
            os_info=os_payload,
        )
        details.append("capabilities persistées avec succès")
        return True, details

    except Exception as exc:  # noqa: B902 - log et continuer
        details.append(f"erreur: {exc}")
        if "host" in locals():
            await HostService.mark_scan_failed(session, host)
        return False, details


def _default_seed_host_profile() -> HostProfile:
    """Retourne le profil canonique du host seedé au bootstrap.

    ``host_baremetal`` : la machine locale est pilotée directement (accès
    local) — le typage fonctionnel est déduit des capacités persistées
    (``host_capabilities``), pas d'un champ exclusif.
    """
    return HostProfile.HOST_BAREMETAL


async def seed_stack_definitions(session: AsyncSession, organization_id: str) -> None:
    """
    Charge les définitions de stacks depuis les fichiers YAML.

    Args:
        session: Session de base de données async
        organization_id: ID de l'organisation propriétaire des stacks

    Note:
        Cette fonction ne lève pas d'exceptions pour ne pas bloquer
        le démarrage de l'application en cas d'erreur.
    """
    try:
        # Vérifier si le chargement automatique est activé
        if not settings.auto_load_stack_definitions:
            print("  - Stack definitions: auto-chargement désactivé")
            return

        # Importer le loader
        from .services.stack_definitions_loader import StackDefinitionsLoader

        # Créer le loader
        loader = StackDefinitionsLoader(settings.stack_definitions_path)

        # Charger les définitions
        created_count, updated_count, errors = await loader.load_into_database(
            session, organization_id, strategy=settings.stack_update_strategy
        )

        # Afficher les résultats
        if created_count > 0 or updated_count > 0:
            print(
                f"  - Stack definitions: {created_count} créé(s), {updated_count} mis à jour"
            )
        else:
            print("  - Stack definitions: aucun changement")

        # Afficher les erreurs si présentes
        if errors:
            print(f"    ⚠️  {len(errors)} erreur(s) lors du chargement:")
            for error in errors:
                print(f"      • {error}")

    except Exception as e:
        # Logger l'erreur mais ne pas bloquer le démarrage
        print(f"    ⚠️  Erreur lors du chargement des stack definitions: {e}")
        # L'erreur est loggée mais ne remonte pas


async def check_admin_exists(session: AsyncSession) -> bool:
    """
    Vérifie si un utilisateur admin existe dans la base de données.

    Args:
        session: Session de base de données async

    Returns:
        bool: True si au moins un superuser existe
    """
    result = await session.execute(select(User).where(User.is_superuser == True))
    admin = result.scalar_one_or_none()
    return admin is not None
