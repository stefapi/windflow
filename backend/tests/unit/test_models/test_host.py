"""Tests unitaires du modèle ``Host`` (STORY-166.1).

Couvre (cf. story § Tests à écrire) :

  HostCapability`` (AC 2 — même classe, même table) ;
- les defaults canoniques : ``origin == managed``, ``installed_engines
  == []``, ``status == offline`` ;
- la property hybride ``type`` : getter/setter avec table d'arbitrage +
  trace ``extra_metadata.migrated_type`` ;
- les synonyms ``scan_date``/``platform_info`` (mêmes données, zéro
  duplication) ;
- le ``__repr__`` sans credentials ni donnée sensible (règle 40) ;
- la non-régression STORY-103 : chiffrement/ré-encryptage au premier
  accès inchangés (comportement détaillé couvert par test_target.py,
  conservé — le modèle est la même classe).

Les credentials des fixtures sont factices.
"""

from __future__ import annotations

import pytest

from app.core.secret_manager import reset_secret_manager
from app.enums.host import HostProfile, HostStatus, WorkloadOrigin
from app.enums.target import TargetType
from app.models.host import Host
from app.models.host_capability import HostCapability

REMOTE = "192.168.1.50"


@pytest.fixture(autouse=True)
def _fresh_secret_manager():
    """Instance SecretManager isolée par test (clé déterministe)."""
    reset_secret_manager()
    yield
    reset_secret_manager()


def _make_host(**overrides) -> Host:
    """Host minimal distant (credentials chiffrés factices)."""
    defaults: dict = {
        "id": "host-1",
        "name": "srv-prod",
        "host": REMOTE,
        "port": 22,
        "organization_id": "org-1",
        "credentials": {"_encrypted": "gAAAAA-fake-token"},
    }
    defaults.update(overrides)
    return Host(**defaults)


class TestCanonicalTablenames:
    """Tables canoniques (alias de transition purgés — STORY-166.6)."""

    def test_tablename_is_hosts(self) -> None:
        assert Host.__tablename__ == "hosts"

    def test_capability_tablename_and_unique(self) -> None:
        """Table ``host_capabilities`` + UNIQUE(host_id, capability_type)
        nommée ``uq_host_capability_type``."""
        assert HostCapability.__tablename__ == "host_capabilities"
        constraints = {
            c.name for c in HostCapability.__table_args__ if hasattr(c, "name")
        }
        assert "uq_host_capability_type" in constraints


class TestCanonicalDefaults:
    """Defaults du schéma canonique (spec 06) — appliqués au flush
    (SQLAlchemy ``mapped_column(default=...)``), vérifiés via session
    in-memory."""

    def test_defaults_origin_managed_engines_empty_status_offline(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from app.database import Base

        engine = create_engine("sqlite://")
        Base.metadata.create_all(
            engine, tables=[Host.__table__, HostCapability.__table__]
        )
        with Session(engine) as session:
            host = _make_host()
            session.add(host)
            session.flush()  # defaults colonne appliqués ici

            assert host.origin is WorkloadOrigin.MANAGED
            assert host.installed_engines == []
            assert host.status is HostStatus.OFFLINE
            # profile : valeur explicite par défaut (baremetal)
            assert host.profile is HostProfile.HOST_BAREMETAL

            reloaded = session.get(Host, host.id)
            assert reloaded is not None
            assert reloaded.installed_engines == []


class TestLegacyTypeHybrid:
    """Property hybride ``type`` (transition — divergence n°4)."""

    def test_setter_docker_remote_maps_profile_and_traces(self) -> None:
        host = _make_host()
        host.type = TargetType.DOCKER
        assert host.profile is HostProfile.HOST_REMOTE_DOCKER
        assert host.extra_metadata["migrated_type"] == "docker"

    def test_setter_docker_localhost_maps_baremetal(self) -> None:
        host = _make_host(host="localhost")
        host.type = "docker"
        assert host.profile is HostProfile.HOST_BAREMETAL

    def test_setter_accepts_host_profile_passthrough(self) -> None:
        """Assignation directe d'un HostProfile : sans transformation."""
        host = _make_host()
        host.type = HostProfile.HOST_PROXMOX
        assert host.profile is HostProfile.HOST_PROXMOX

    def test_setter_none_is_noop(self) -> None:
        """``type = None`` ne déclenche ni mapping ni trace."""
        host = _make_host()
        host.type = None
        assert host.profile is None  # inchangé (jamais touché par le setter)
        assert not (host.extra_metadata or {}).get("migrated_type")

    def test_getter_returns_migrated_type_trace(self) -> None:
        host = _make_host(
            extra_metadata={"migrated_type": "kubernetes"},
            profile=HostProfile.HOST_BAREMETAL,
        )
        assert host.type is TargetType.KUBERNETES

    def test_getter_falls_back_from_profile(self) -> None:
        """Sans trace : host_remote_docker → docker, sinon physical."""
        docker_host = _make_host(profile=HostProfile.HOST_REMOTE_DOCKER)
        assert docker_host.type is TargetType.DOCKER
        baremetal = _make_host()
        assert baremetal.type is TargetType.PHYSICAL


class TestSynonyms:
    """Synonyms de transition (mêmes données, zéro duplication)."""

    def test_scan_date_synonym_writes_last_scan_at(self) -> None:
        from datetime import datetime, timezone

        host = _make_host()
        now = datetime.now(timezone.utc)
        host.scan_date = now
        assert host.last_scan_at is now

    def test_platform_info_synonym_writes_hardware_info(self) -> None:
        host = _make_host()
        host.platform_info = {"os": "linux"}
        assert host.hardware_info == {"os": "linux"}


class TestReprSecurity:
    """Règle 40 — aucune donnée sensible dans ``__repr__``."""

    def test_repr_does_not_expose_credentials(self) -> None:
        host = _make_host(
            credentials={
                "_encrypted": "gAAAAA-fake",
                "password": "S3cr3t!",
                "username": "deploy",
            }
        )
        representation = repr(host)
        assert "credentials" not in representation
        assert "S3cr3t" not in representation
        assert "deploy" not in representation
        assert "_encrypted" not in representation

    def test_capability_repr_without_details(self) -> None:
        cap = HostCapability(
            host_id="host-1",
            capability_type="docker",
            details={"secret_env": "leak"},
        )
        representation = repr(cap)
        assert "secret_env" not in representation
        assert "leak" not in representation


class TestCredentialsStory103Regression:
    """Non-régression STORY-103 : le comportement de chiffrement est
    inchangé sur la classe renommée (double lecture + ré-encryptage)."""

    def test_decrypted_credentials_legacy_clear_line_reencrypts(self) -> None:
        host = _make_host(credentials={"auth_method": "password", "password": "pw-123"})
        clear = host.decrypted_credentials
        assert clear["password"] == "pw-123"
        # Ré-encryptage au premier accès : la colonne devient opaque.
        assert "_encrypted" in host.credentials
        assert host.credentials != {"auth_method": "password", "password": "pw-123"}

    def test_empty_credentials_returns_empty_dict(self) -> None:
        host = _make_host(credentials={})
        assert host.decrypted_credentials == {}
