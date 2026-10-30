"""Tests du seed database — auto-détection du host local (STORY-166.5).

Couvre les AC 1/2 de la story :
- setting ``auto_detect_local_host=False`` → **aucun host créé**, le scan
  localhost ne s'exécute pas du tout, et le chargement des stack
  definitions n'est pas court-circuité ;
- setting on (défaut ``True``) → host local présent avec profil canonique
  ``host_baremetal``, ``origin=managed``, capacités scannées persistées,
  rattaché à l'organisation par défaut, sans aucun credentials réel ;
- idempotence : double seed → un seul host localhost (garde explicite
  ``get_by_name`` dans ``_create_local_host`` + early-return global de
  ``seed_database``) ;
- échec du scan → le seed ne casse pas le démarrage ;
- articulation STORY-166.3 : le host seedé est résolvable par
  ``_resolve_local_host`` (fallback placeholder conservé si absent).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import settings
from app.database_seed import _create_local_host, seed_database
from app.enums.host import HostProfile, WorkloadOrigin
from app.models.host import Host
from app.models.organization import Organization
from app.schemas.target_scan import (
    DockerCapabilities,
    OSInfo,
    PlatformArchitecture,
    PlatformInfo,
    ScanResult,
)


@pytest.fixture(autouse=True)
def _valid_admin_email():
    """Robustesse inter-versions d'email-validator (cf. test_database.py).

    Lancé depuis la racine (Makefile), ``Settings()`` charge le ``.env``
    racine qui pose ``SUPERADMIN_EMAIL=admin@windflow.local`` — TLD
    réservé rejeté par les versions récentes d'email-validator, sans
    lien avec le seed du host. Override systématique + restauration.
    """
    original = settings.admin_email
    settings.admin_email = "admin-seed-test@example.com"
    yield
    settings.admin_email = original


def _build_scan_result() -> ScanResult:
    """Scan localhost déterministe (docker installé) pour les tests."""
    return ScanResult(
        host="localhost",
        scan_date=datetime.now(timezone.utc),
        success=True,
        docker=DockerCapabilities(
            installed=True,
            version="27.0.0",
            running=True,
            socket_accessible=True,
        ),
        platform=PlatformInfo(architecture=PlatformArchitecture.X86_64, cpu_cores=8),
        os=OSInfo(system="Linux", distribution="Debian", version="12"),
    )


async def _seeded_hosts(session) -> list[Host]:
    result = await session.execute(select(Host))
    return list(result.scalars().all())


class TestSeedAutoDetectSettingOff:
    """AC 1 : setting off → aucun host créé, aucun scan exécuté."""

    async def test_setting_off_creates_no_host_and_skips_scan(
        self, db_session, capsys
    ) -> None:
        original = settings.auto_detect_local_host
        settings.auto_detect_local_host = False
        try:
            scan_mock = AsyncMock(return_value=_build_scan_result())
            stack_loader = AsyncMock()
            with patch(
                "app.services.host_scanner_service.HostScannerService"
            ) as scanner_cls, patch(
                "app.database_seed.seed_stack_definitions", new=stack_loader
            ):
                scanner_cls.return_value.scan_localhost = scan_mock
                await seed_database(db_session)

            hosts = await _seeded_hosts(db_session)
            assert hosts == [], "Aucun host ne doit être créé avec le setting off"
            # Le scan localhost ne doit pas s'exécuter avec le setting off.
            scan_mock.assert_not_awaited()
            # Le chargement des stacks n'est pas court-circuité par le setting.
            stack_loader.assert_awaited_once()

            output = capsys.readouterr().out
            assert "auto-détection désactivée" in output
            assert "AUTO_DETECT_LOCAL_HOST=false" in output
        finally:
            settings.auto_detect_local_host = original


class TestSeedAutoDetectDefaultOn:
    """AC 1 : setting on (défaut) → host local canonique + capacités."""

    async def test_setting_on_creates_canonical_local_host(self, db_session) -> None:
        original = settings.auto_detect_local_host
        settings.auto_detect_local_host = True
        try:
            scan_mock = AsyncMock(return_value=_build_scan_result())
            with patch(
                "app.services.host_scanner_service.HostScannerService"
            ) as scanner_cls, patch(
                "app.database_seed.seed_stack_definitions", new=AsyncMock()
            ):
                scanner_cls.return_value.scan_localhost = scan_mock
                await seed_database(db_session)
            scan_mock.assert_awaited_once()

            hosts = await _seeded_hosts(db_session)
            assert len(hosts) == 1, "Un seul host local doit être seedé"

            host = hosts[0]
            assert host.name == "localhost"
            assert host.host == "localhost"
            assert host.profile == HostProfile.HOST_BAREMETAL
            assert host.origin == WorkloadOrigin.MANAGED
            assert host.extra_metadata["auto_created"] is True
            assert host.extra_metadata["creation_source"] == "database_seed"
            assert host.extra_metadata["seed_profile"] == "host_baremetal"
            # Capacités scannées persistées (docker détecté dans le mock).
            assert host.scan_success is True
            assert host.status.value == "online"
            docker_engines = [
                e
                for e in host.installed_engines
                if e.get("capability_type") == "docker"
            ]
            assert docker_engines, "La capacité docker doit être persistée"
            assert docker_engines[0]["version"] == "27.0.0"
            assert host.hardware_info is not None
        finally:
            settings.auto_detect_local_host = original

    async def test_local_host_attached_to_default_org(self, db_session) -> None:
        """Isolation org (règle 40) : host rattaché à l'organisation seedée."""
        with patch(
            "app.services.host_scanner_service.HostScannerService"
        ) as scanner_cls, patch(
            "app.database_seed.seed_stack_definitions", new=AsyncMock()
        ):
            scanner_cls.return_value.scan_localhost = AsyncMock(
                return_value=_build_scan_result()
            )
            await seed_database(db_session)

        orgs = (
            (
                await db_session.execute(
                    select(Organization).where(
                        Organization.slug == settings.default_org_slug
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(orgs) == 1
        host = (await _seeded_hosts(db_session))[0]
        assert host.organization_id == orgs[0].id

    async def test_local_host_has_no_real_credentials(self, db_session) -> None:
        """Règle 40 : aucun credentials réel sur le host local seedé."""
        with patch(
            "app.services.host_scanner_service.HostScannerService"
        ) as scanner_cls, patch(
            "app.database_seed.seed_stack_definitions", new=AsyncMock()
        ):
            scanner_cls.return_value.scan_localhost = AsyncMock(
                return_value=_build_scan_result()
            )
            await seed_database(db_session)

        host = (await _seeded_hosts(db_session))[0]
        assert host.auth_method == "local"
        assert host.username is None
        assert not host.has_sudo
        assert host.ssh_key_id is None


class TestSeedIdempotence:
    """AC 2 : redémarrage → pas de doublon (garde explicite)."""

    async def test_double_seed_creates_single_host(self, db_session) -> None:
        original = settings.auto_detect_local_host
        settings.auto_detect_local_host = True
        try:
            scan_mock = AsyncMock(return_value=_build_scan_result())
            with patch(
                "app.services.host_scanner_service.HostScannerService"
            ) as scanner_cls, patch(
                "app.database_seed.seed_stack_definitions", new=AsyncMock()
            ):
                scanner_cls.return_value.scan_localhost = scan_mock
                await seed_database(db_session)
                # Redémarrage : second seed sur la même base.
                await seed_database(db_session)

            hosts = await _seeded_hosts(db_session)
            assert len(hosts) == 1, "Le double seed ne doit pas dupliquer le host"
            # Le scan ne doit pas être relancé au second démarrage.
            scan_mock.assert_awaited_once()
        finally:
            settings.auto_detect_local_host = original

    async def test_create_local_host_guard_on_existing_host(
        self, db_session, test_organization
    ) -> None:
        """Garde explicite de ``_create_local_host`` (indépendante de
        l'early-return global de ``seed_database``)."""
        scan_mock = AsyncMock(return_value=_build_scan_result())
        with patch(
            "app.services.host_scanner_service.HostScannerService"
        ) as scanner_cls:
            scanner_cls.return_value.scan_localhost = scan_mock

            created_first = await _create_local_host(db_session, test_organization.id)
            details_second = await _create_local_host(db_session, test_organization.id)

        assert created_first[0] is True
        assert details_second[0] is False
        assert any("déjà présent" in d for d in details_second[1])
        # La garde doit court-circuiter avant tout scan.
        scan_mock.assert_awaited_once()
        hosts = await _seeded_hosts(db_session)
        assert len(hosts) == 1


class TestSeedScanFailure:
    """Échec du scan → le seed ne casse pas le démarrage."""

    async def test_scan_failure_returns_false_with_details(
        self, db_session, test_organization
    ) -> None:
        with patch(
            "app.services.host_scanner_service.HostScannerService"
        ) as scanner_cls:
            scanner_cls.return_value.scan_localhost = AsyncMock(
                side_effect=RuntimeError("scan boom")
            )
            created, details = await _create_local_host(
                db_session, test_organization.id
            )

        assert created is False
        assert any("scan boom" in d for d in details)


class TestSeededHostResolvable:
    """Articulation STORY-166.3 : ``_resolve_local_host`` voit le host seedé."""

    async def test_seeded_host_resolved_by_compute_service(self, db_session) -> None:
        from app.services.compute_service import _resolve_local_host

        with patch(
            "app.services.host_scanner_service.HostScannerService"
        ) as scanner_cls, patch(
            "app.database_seed.seed_stack_definitions", new=AsyncMock()
        ):
            scanner_cls.return_value.scan_localhost = AsyncMock(
                return_value=_build_scan_result()
            )
            await seed_database(db_session)

        org = (
            await db_session.execute(
                select(Organization).where(
                    Organization.slug == settings.default_org_slug
                )
            )
        ).scalar_one()
        host = (await _seeded_hosts(db_session))[0]

        host_id, host_name = await _resolve_local_host(db_session, [org.id])
        assert host_id == host.id
        assert host_name == "localhost"

    async def test_fallback_placeholder_when_no_host(
        self, db_session, test_organization
    ) -> None:
        """Fallback ``("local", "Local Docker")`` conservé si aucun host."""
        from app.services.compute_service import LOCAL_HOST_ID, _resolve_local_host

        host_id, host_name = await _resolve_local_host(
            db_session, [test_organization.id]
        )
        assert host_id == LOCAL_HOST_ID
        assert host_name == "Local Docker"
