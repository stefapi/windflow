"""Tests unitaires des helpers de mapping ``Target``→``Host`` (STORY-166.1).

Couvre les tables de correspondance arbitrées en analyse (divergences 2
et 3 de STORY-166) : ``map_target_to_host_profile`` (règle enum ×
local/distant + tie-breaker capacité docker pour le repli kubernetes)
et ``map_target_status`` (error→unreachable, maintenance→offline) —
mêmes règles que la data migration ``1661``, testables sans base.

Inclut la normalisation **nom ou valeur** (les bases legacy persistent
les noms de membres ``'ONLINE'``/``'DOCKER'`` — baseline Alembic sans
``values_callable``).
"""

from __future__ import annotations

import pytest

from app.enums.host import HostProfile, HostStatus
from app.enums.target import TargetStatus, TargetType
from app.helper.target_host_migration import (
    LOCALHOST_ADDRESSES,
    is_local_host_address,
    map_target_status,
    map_target_to_host_profile,
)

REMOTE = "192.168.1.50"


class TestMapTargetToHostProfile:
    """Table d'arbitrage ``TargetType`` (6) → ``HostProfile`` (3)."""

    @pytest.mark.parametrize(
        ("target_type", "expected"),
        [
            (TargetType.DOCKER, HostProfile.HOST_REMOTE_DOCKER),
            (TargetType.DOCKER_COMPOSE, HostProfile.HOST_REMOTE_DOCKER),
            (TargetType.DOCKER_SWARM, HostProfile.HOST_REMOTE_DOCKER),
        ],
        ids=["docker", "docker_compose", "docker_swarm"],
    )
    def test_docker_family_remote_maps_to_remote_docker(
        self, target_type: TargetType, expected: HostProfile
    ) -> None:
        """La famille docker* **distante** → host_remote_docker."""
        assert map_target_to_host_profile(target_type, REMOTE) is expected

    @pytest.mark.parametrize(
        ("target_type", "local_host"),
        [
            (TargetType.DOCKER, "localhost"),
            (TargetType.DOCKER, "127.0.0.1"),
            (TargetType.DOCKER_COMPOSE, "localhost"),
            (TargetType.DOCKER_SWARM, "localhost"),
        ],
        ids=[
            "docker-localhost",
            "docker-127",
            "docker_compose-localhost",
            "docker_swarm-localhost",
        ],
    )
    def test_docker_family_localhost_maps_to_baremetal(
        self, target_type: TargetType, local_host: str
    ) -> None:
        """Docker sur socket local = pilotage direct → host_baremetal."""
        assert (
            map_target_to_host_profile(target_type, local_host)
            is HostProfile.HOST_BAREMETAL
        )

    def test_kubernetes_remote_with_docker_capability_maps_to_remote_docker(
        self,
    ) -> None:
        """Repli kubernetes : distant + capacité docker disponible →
        host_remote_docker."""
        assert (
            map_target_to_host_profile(
                TargetType.KUBERNETES, REMOTE, has_docker_capability=True
            )
            is HostProfile.HOST_REMOTE_DOCKER
        )

    def test_kubernetes_remote_without_docker_capability_falls_back_to_baremetal(
        self,
    ) -> None:
        """Repli kubernetes : distant **sans** docker scanné →
        host_baremetal (substrat individuel)."""
        assert (
            map_target_to_host_profile(
                TargetType.KUBERNETES, REMOTE, has_docker_capability=False
            )
            is HostProfile.HOST_BAREMETAL
        )

    def test_kubernetes_localhost_maps_to_baremetal(self) -> None:
        """Repli kubernetes : localhost → host_baremetal quoi qu'il arrive."""
        assert (
            map_target_to_host_profile(
                TargetType.KUBERNETES, "localhost", has_docker_capability=True
            )
            is HostProfile.HOST_BAREMETAL
        )

    @pytest.mark.parametrize(
        ("target_type", "host_address"),
        [
            (TargetType.VM, "localhost"),
            (TargetType.VM, REMOTE),
            (TargetType.PHYSICAL, "localhost"),
            (TargetType.PHYSICAL, REMOTE),
        ],
        ids=["vm-local", "vm-remote", "physical-local", "physical-remote"],
    )
    def test_vm_and_physical_always_map_to_baremetal(
        self, target_type: TargetType, host_address: str
    ) -> None:
        """vm/physical : substrats individuels → host_baremetal (local et
        distant — pas de host_vm dans HostProfile)."""
        assert (
            map_target_to_host_profile(target_type, host_address)
            is HostProfile.HOST_BAREMETAL
        )

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("DOCKER", HostProfile.HOST_REMOTE_DOCKER),  # nom legacy stocké
            ("docker", HostProfile.HOST_REMOTE_DOCKER),  # valeur
            ("KUBERNETES", HostProfile.HOST_BAREMETAL),  # nom + repli sans docker
        ],
        ids=["member-name", "value", "kubernetes-name-no-docker"],
    )
    def test_accepts_member_name_or_value(
        self, raw: str, expected: HostProfile
    ) -> None:
        """Normalisation : la migration lit les deux formes (baseline =
        noms uppercase, nouveau code = valeurs)."""
        assert map_target_to_host_profile(raw, REMOTE) is expected

    def test_unknown_type_raises(self) -> None:
        """Valeur inconnue → ValueError explicite (jamais de mapping muet)."""
        with pytest.raises(ValueError, match="ne correspond"):
            map_target_to_host_profile("not-a-type", REMOTE)

    def test_none_type_raises(self) -> None:
        with pytest.raises(ValueError, match="requis"):
            map_target_to_host_profile(None, REMOTE)  # type: ignore[arg-type]


class TestMapTargetStatus:
    """Table d'arbitrage ``TargetStatus`` → ``HostStatus``."""

    @pytest.mark.parametrize(
        ("legacy", "expected"),
        [
            (TargetStatus.ONLINE, HostStatus.ONLINE),
            (TargetStatus.OFFLINE, HostStatus.OFFLINE),
            (TargetStatus.ERROR, HostStatus.UNREACHABLE),
            (TargetStatus.MAINTENANCE, HostStatus.OFFLINE),
        ],
        ids=["online", "offline", "error-unreachable", "maintenance-offline"],
    )
    def test_status_mapping_table(
        self, legacy: TargetStatus, expected: HostStatus
    ) -> None:
        assert map_target_status(legacy) is expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ERROR", HostStatus.UNREACHABLE),  # nom legacy stocké (baseline)
            ("error", HostStatus.UNREACHABLE),  # valeur
            ("MAINTENANCE", HostStatus.OFFLINE),
        ],
        ids=["error-name", "error-value", "maintenance-name"],
    )
    def test_accepts_member_name_or_value(self, raw: str, expected: HostStatus) -> None:
        assert map_target_status(raw) is expected

    def test_unknown_status_raises(self) -> None:
        with pytest.raises(ValueError, match="ne correspond"):
            map_target_status("scanning")  # n'existe pas côté legacy


class TestLocalhostDetection:
    """Détection local/distant (arbitrage du profil)."""

    @pytest.mark.parametrize(
        ("address", "expected"),
        [
            ("localhost", True),
            ("127.0.0.1", True),
            ("LOCALHOST", True),  # casse neutralisée
            ("  localhost  ", True),  # espaces trimés
            (REMOTE, False),
            ("::1", False),  # IPv6 hors périmètre arbitré (documenté)
            ("", False),
            (None, False),
        ],
        ids=[
            "localhost",
            "127",
            "case",
            "trimmed",
            "remote",
            "ipv6",
            "empty",
            "none",
        ],
    )
    def test_is_local_host_address(self, address: str | None, expected: bool) -> None:
        assert is_local_host_address(address) is expected

    def test_localhost_addresses_constant(self) -> None:
        """Constante documentée : exactement localhost + 127.0.0.1."""
        assert LOCALHOST_ADDRESSES == frozenset({"localhost", "127.0.0.1"})
