"""Golden tests de non-régression des payloads du scan (STORY-166.3 — garde-fou §2.G).

Le renommage ``target_scan_parsers`` → ``host_scan_parsers`` (et
``target_access_profile`` → ``host_access_profile``) est un
**renommage/wrapping, pas une réécriture** : ces tests figent les
sorties des parseurs, de :func:`build_capabilities_payload` et du
:class:`HostAccessProfileDetector` sur des fixtures réalistes
commitées (``tests/fixtures/golden/``) — toute divergence de payload
aujourd'hui ou demain casse le build.

Références :
- fixture : ``tests/fixtures/golden/scan_results/realistic_host.json`` ;
- golden payload : ``tests/fixtures/golden/scan_results/realistic_host_capabilities.golden.json``
  (capturé sur le code pré-renommage — l'ancien module
  ``target_scan_parsers`` reste importable via l'alias de transition
  et produit la **même sortie**, test ci-dessous).

Aucune clé de payload ne contient le mot ``target`` (inventaire figé
par ``test_payload_keys_contain_no_target_token``) : les clés
contractuelles legacy (``windflow.target_id`` dans les labels Docker,
``target_id`` dans les params scheduler ``HostScanParams``) vivent
hors de ces payloads et sont traitées par STORY-166.2/166.6.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.enums.host import AccessLevel, CapabilityType
from app.schemas.target_scan import PlatformArchitecture, ScanResult
from app.services.commands import CommandResult
from app.services.host_access_profile import HostAccessProfileDetector
from app.services.host_scan_parsers import (
    build_capabilities_payload,
    extract_capability_names,
    map_architecture,
    parse_docker_version,
    parse_k3s_version,
    parse_kubeadm_version,
    parse_kubectl_version,
    parse_qemu_version,
    parse_runc_version,
    parse_vagrant_version,
    parse_version_only,
    strip_quotes,
)

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "golden" / "scan_results"
FIXED_SCAN_DATE = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)


def _load_scan_fixture() -> ScanResult:
    """Charge la fixture ScanResult figée (round-trip JSON complet)."""
    raw = json.loads((FIXTURES_DIR / "realistic_host.json").read_text())
    return ScanResult.model_validate(raw)


def _normalize(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise enum/datetime pour comparaison JSON stable."""
    return [
        {
            **cap,
            "capability_type": cap["capability_type"].value,
            "detected_at": cap["detected_at"].isoformat(),
        }
        for cap in payload
    ]


# ─── Golden : build_capabilities_payload ──────────────────────────


class TestGoldenCapabilitiesPayload:
    """Le payload de capacités complet est identique au golden commité."""

    def test_payload_matches_golden_file(self) -> None:
        scan = _load_scan_fixture()
        golden = json.loads(
            (FIXTURES_DIR / "realistic_host_capabilities.golden.json").read_text()
        )
        assert _normalize(build_capabilities_payload(scan)) == golden

    def test_payload_keys_are_stable(self) -> None:
        """Stabilité contractuelle : clés et ordre des entrées figés."""
        scan = _load_scan_fixture()
        payload = build_capabilities_payload(scan)
        types = [cap["capability_type"].value for cap in payload]
        assert types == [
            "virsh",
            "qemu_kvm",
            "podman",
            "docker",
            "docker_compose",
            "docker_swarm",
            "kubectl",
            "helm",
            "lxd",
            "containerd",
            "runc",
            "buildah",
            "skopeo",
        ]

    def test_only_available_capabilities_are_emitted(self) -> None:
        """Les outils absents (libvirt, virtualbox, k3s…) n'émettent rien."""
        scan = _load_scan_fixture()
        payload = build_capabilities_payload(scan)
        types = {cap["capability_type"].value for cap in payload}
        for absent in (
            "libvirt",
            "virtualbox",
            "vagrant",
            "proxmox",
            "multipass",
            "kubeadm",
            "k3s",
            "microk8s",
            "lxc",
            "incus",
            "crun",
            "podman_compose",
        ):
            assert absent not in types

    def test_payload_keys_contain_no_target_token(self) -> None:
        """Inventaire §2.G : aucune clé de payload ne contient ``target``."""
        scan = _load_scan_fixture()
        for cap in build_capabilities_payload(scan):
            for key in cap.keys():
                assert "target" not in key

    def test_fixture_round_trip_is_stable(self) -> None:
        """La fixture figée survit à un round-trip ScanResult→JSON→ScanResult."""
        scan = _load_scan_fixture()
        again = ScanResult.model_validate(json.loads(scan.model_dump_json()))
        assert _normalize(build_capabilities_payload(again)) == _normalize(
            build_capabilities_payload(scan)
        )


# ─── Golden : parseurs par famille ────────────────────────────────


class TestGoldenParsers:
    """Sorties de parseurs figées — un cas par famille (§2.G)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Docker version 27.3.1, build 1223a1b", "27.3.1"),
            ("Docker version 24.0.7", "24.0.7"),
            ("docker: command not found", None),
        ],
    )
    def test_docker_version(self, raw: str, expected: str | None) -> None:
        assert parse_docker_version(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Vagrant 2.4.1", {"version": "2.4.1", "raw": "Vagrant 2.4.1"}),
            ("no version here", {}),
        ],
    )
    def test_vagrant_version(self, raw: str, expected: dict) -> None:
        assert parse_vagrant_version(raw) == expected

    def test_qemu_version(self) -> None:
        assert parse_qemu_version(
            "QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-2)\nCopyright"
        ) == {
            "version": "8.2.2",
            "raw": "QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-2)",
        }

    def test_kubectl_version_json(self) -> None:
        raw = json.dumps(
            {"clientVersion": {"major": "1", "minor": "31", "gitVersion": "v1.31.0"}}
        )
        assert parse_kubectl_version(raw) == {
            "version": "v1.31.0",
            "major": "1",
            "minor": "31",
        }

    def test_kubectl_version_text_fallback(self) -> None:
        assert parse_kubectl_version("Client Version: v1.30.1") == {"version": "1.30.1"}

    def test_kubeadm_version_json(self) -> None:
        raw = json.dumps(
            {"clientVersion": {"major": "1", "minor": "30", "gitVersion": "v1.30.4"}}
        )
        assert parse_kubeadm_version(raw) == {
            "version": "v1.30.4",
            "major": "1",
            "minor": "30",
        }

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("k3s version v1.28.4+k3s2 (abcd)\n", {"version": "1.28.4+k3s2"}),
            ("k3s version unknown", {}),
        ],
    )
    def test_k3s_version(self, raw: str, expected: dict) -> None:
        assert parse_k3s_version(raw) == expected

    def test_runc_version_multiline(self) -> None:
        raw = "runc version 1.1.14\ncommit: v1.1.14-0-gf92bad2\nspec: 1.0.2-dev"
        assert parse_runc_version(raw) == {"version": "1.1.14"}

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("podman version 5.2.3", {"version": "5.2.3"}),
            ("", {}),
        ],
    )
    def test_version_only(self, raw: str, expected: dict) -> None:
        assert parse_version_only(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ('"Debian GNU/Linux"', "Debian GNU/Linux"),
            ("'12'", "12"),
            ("plain", "plain"),
        ],
    )
    def test_strip_quotes(self, raw: str, expected: str) -> None:
        assert strip_quotes(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("x86_64", PlatformArchitecture.X86_64),
            ("aarch64", PlatformArchitecture.ARM64),
            ("armv7l", PlatformArchitecture.ARMV7),
            ("sun4u", PlatformArchitecture.UNKNOWN),
        ],
    )
    def test_map_architecture(self, raw: str, expected: PlatformArchitecture) -> None:
        assert map_architecture(raw) is expected

    def test_extract_capability_names_sorted_unique(self) -> None:
        payload = [
            {"capability_type": CapabilityType.DOCKER},
            {"capability_type": CapabilityType.HELM},
            {"capability_type": CapabilityType.DOCKER},
        ]
        assert extract_capability_names(payload) == ["docker", "helm"]


# ─── Golden : profils d'accès ─────────────────────────────────────


class _StubExecutor:
    """Executor déterministe — mappe commandes → réponses mockées.

    Duck-typé sur le protocole ``CommandExecutor`` (``run`` uniquement).
    """

    def __init__(self, responses: dict[str, tuple[int, str, str]]) -> None:
        self._responses = responses

    async def run(self, command: str, timeout: int = 30):  # type: ignore[override]
        exit_code, stdout, stderr = self._responses.get(command, (1, "", "not found"))
        return CommandResult(exit_code, stdout, stderr)


def _detector() -> HostAccessProfileDetector:
    return HostAccessProfileDetector()


class TestGoldenAccessProfiles:
    """Profils d'accès figés pour chaque scénario de commandes mockées."""

    @pytest.mark.asyncio
    async def test_root_profile(self) -> None:
        executor = _StubExecutor({"whoami": (0, "root", "")})
        profile = await _detector().detect(executor=executor, ssh_user="root")
        assert profile.access_level is AccessLevel.ROOT
        assert profile.is_root_user is True
        assert profile.sudo_user == "root"
        assert profile.can_install_packages is True
        assert profile.sudo_verified is False

    @pytest.mark.asyncio
    async def test_sudo_passwordless_root_profile(self) -> None:
        executor = _StubExecutor(
            {
                "whoami": (0, "deploy", ""),
                "which sudo 2>/dev/null": (0, "/usr/bin/sudo", ""),
                "sudo -n whoami 2>/dev/null": (0, "root", ""),
            }
        )
        profile = await _detector().detect(
            executor=executor, ssh_user="deploy", sudo_enabled=True
        )
        assert profile.access_level is AccessLevel.SUDO_PASSWORDLESS
        assert profile.sudo_passwordless is True
        assert profile.sudo_verified is True
        assert profile.sudo_user == "root"
        assert profile.can_install_packages is True

    @pytest.mark.asyncio
    async def test_sudo_password_profile(self) -> None:
        # Remote executor (pas LocalCommandExecutor) → sudo -S via executor
        executor = _StubExecutor(
            {
                "whoami": (0, "deploy", ""),
                "which sudo 2>/dev/null": (0, "/usr/bin/sudo", ""),
                "sudo -S -p '' -u deploy whoami 2>/dev/null": (0, "deploy", ""),
            }
        )
        profile = await _detector().detect(
            executor=executor,
            ssh_user="deploy",
            sudo_user="deploy",
            sudo_password="s3cr3t",
            sudo_enabled=True,
        )
        assert profile.access_level is AccessLevel.SUDO
        assert profile.sudo_verified is True
        assert profile.sudo_passwordless is False
        assert profile.can_install_packages is False  # sudo vers soi-même, pas root

    @pytest.mark.asyncio
    async def test_limited_profile(self) -> None:
        executor = _StubExecutor(
            {
                "whoami": (0, "deploy", ""),
                "which sudo 2>/dev/null": (1, "", "not found"),
            }
        )
        profile = await _detector().detect(executor=executor, ssh_user="deploy")
        assert profile.access_level is AccessLevel.LIMITED
        assert profile.sudo_available is False
        assert profile.sudo_verified is False
        assert profile.can_install_packages is False
        assert profile.sudo_user is None


# ─── Sécurité (règle 40) ──────────────────────────────────────────


class TestGoldenSecurity:
    """Aucun secret ne transite dans les payloads/profils golden."""

    def test_access_profile_schema_has_no_secret_fields(self) -> None:
        from app.schemas.host import HostAccessProfile

        secrets = {"password", "sudo_password", "ssh_private_key", "credentials"}
        field_names = set(HostAccessProfile.model_fields.keys())
        assert field_names & secrets == set()

    def test_capability_payload_has_no_secret_keys(self) -> None:
        scan = _load_scan_fixture()
        secret_keys = {"password", "credentials", "ssh_private_key", "passphrase"}
        for cap in build_capabilities_payload(scan):
            assert not (set(cap.keys()) & secret_keys)
            # Les clés imbriquées des details ne portent pas de secret non plus
            if isinstance(cap.get("details"), dict):
                assert not (set(cap["details"].keys()) & secret_keys)
