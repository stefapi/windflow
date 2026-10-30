"""
Tests unitaires du service PluginPackageService (STORY-169.1).

Couvre le pipeline DOWNLOAD : validation SSRF de l'URL (schéma, host,
redirections revalidées), téléchargement streaming borné, checksum
SHA-256 obligatoire (rejet sur écart/absence), extraction durcie
(anti path-traversal/symlink/bombe), install atomique et purge du
staging sur tous les chemins — aucun résidu filesystem (AC 1/2/3).
"""

import asyncio
import hashlib
import io
import logging
import socket
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.exceptions import WindFlowException
from app.schemas.plugin_package import PluginPackageResult
from app.schemas.plugin_registry import RegistryPluginEntry
from app.services.plugin_package_service import PluginPackageService

# ── Constantes de test ───────────────────────────────────────────────────────

#: IP publique réelle pour les résolutions DNS simulées. NB : les ranges
#: de documentation TEST-NET (RFC 5737, ex 203.0.113.0/24) sont classés
#: ``is_private`` par le module ipaddress depuis Python 3.12.4+ (fix
#: gh-113171) — ils seraient donc rejetés par la protection SSRF.
PUBLIC_IP = "93.184.216.34"

#: Enregistrement getaddrinfo simulé résolvant vers une IP publique.
PUBLIC_RECORDS: List[Tuple[Any, ...]] = [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 443))
]

DEFAULT_DOWNLOAD_URL = (
    "https://registry.example.com/plugins/traefik/1.2.0/package.tar.gz"
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def pkg_settings(tmp_path: Path) -> Settings:
    """Settings de test avec plugins_base_dir isolé dans tmp_path."""
    return Settings(plugins_base_dir=str(tmp_path))


@pytest.fixture()
def service(pkg_settings: Settings) -> PluginPackageService:
    """Instance du service avec settings de test."""
    return PluginPackageService(pkg_settings)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _file_member(name: str, data: bytes = b"x") -> Tuple[tarfile.TarInfo, io.BytesIO]:
    """Construit un membre tar fichier régulier avec son contenu."""
    info = tarfile.TarInfo(name)
    info.size = len(data)
    return info, io.BytesIO(data)


def _dir_member(name: str) -> tarfile.TarInfo:
    """Construit un membre tar répertoire."""
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    return info


def _special_member(
    name: str, mtype: bytes, linkname: Optional[str] = None
) -> tarfile.TarInfo:
    """Construit un membre tar non régulier (symlink/hardlink/device/FIFO)."""
    info = tarfile.TarInfo(name)
    info.type = mtype
    if linkname is not None:
        info.linkname = linkname
    return info


_Member = Union[tarfile.TarInfo, Tuple[tarfile.TarInfo, io.BytesIO]]


def _build_tar_bytes(members: List[_Member]) -> bytes:
    """Sérialise une liste de membres en archive tar.gz (bytes)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for member in members:
            if isinstance(member, tuple):
                tar.addfile(member[0], member[1])
            else:
                tar.addfile(member)
    return buf.getvalue()


def _valid_package_members() -> List[_Member]:
    """Membres d'un package légitime (répertoire + manifest + readme)."""
    return [
        _dir_member("traefik"),
        _file_member(
            "traefik/windflow-plugin.yml",
            b"name: traefik\nversion: 1.2.0\ndisplay_name: Traefik\n",
        ),
        _file_member("traefik/README.md", b"readme"),
    ]


def _make_entry(
    checksum: Optional[str] = None,
    download_url: str = DEFAULT_DOWNLOAD_URL,
) -> RegistryPluginEntry:
    """Construit une entrée de registre valide pour les tests."""
    return RegistryPluginEntry(
        name="traefik",
        version="1.2.0",
        display_name="Traefik",
        description="Reverse proxy avec TLS automatique",
        category="access",
        type="hybrid",
        author="WindFlow Team",
        license="MIT",
        architectures=["linux/amd64"],
        download_url=download_url,
        checksum_sha256=checksum or hashlib.sha256(b"placeholder").hexdigest(),
    )


class _ChunkStream:
    """Mock de aiohttp response.content avec compteur de chunks consommés."""

    def __init__(self, chunks: List[bytes]) -> None:
        self._chunks = list(chunks)
        self.consumed = 0

    def iter_chunked(self, chunk_size: int) -> Any:
        """Retourne l'itérateur async des chunks (signature aiohttp)."""
        return self._aiter()

    async def _aiter(self) -> Any:
        for chunk in self._chunks:
            self.consumed += 1
            yield chunk


def _make_response(
    status: int = 200,
    chunks: Optional[List[bytes]] = None,
    stream: Optional[_ChunkStream] = None,
    headers: Optional[Dict[str, str]] = None,
) -> AsyncMock:
    """Crée un mock de réponse HTTP aiohttp (async context manager)."""
    response = AsyncMock()
    response.status = status
    response.headers = headers or {}
    response.content = stream or _ChunkStream(chunks or [])
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    return response


def _make_session(
    responses: Optional[List[AsyncMock]] = None,
    side_effect: Optional[Callable[..., Any]] = None,
) -> AsyncMock:
    """Crée un mock de aiohttp.ClientSession (async context manager)."""
    session = AsyncMock()
    if side_effect is not None:
        session.get = MagicMock(side_effect=side_effect)
    else:
        session.get = MagicMock(side_effect=responses or [])
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


@contextmanager
def _dns(resolver: Union[List[Tuple[Any, ...]], Callable[[str], List[Any]]]):
    """Patche loop.getaddrinfo ; yield la liste des hôtes résolus."""
    calls: List[str] = []
    loop = asyncio.get_running_loop()
    original = loop.getaddrinfo

    async def fake_getaddrinfo(
        host: str,
        port: int,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> List[Tuple[Any, ...]]:
        calls.append(host)
        if callable(resolver):
            return resolver(host)
        return resolver

    loop.getaddrinfo = fake_getaddrinfo  # type: ignore[method-assign]
    try:
        yield calls
    finally:
        loop.getaddrinfo = original  # type: ignore[method-assign]


def _chunks_of(data: bytes) -> List[bytes]:
    """Découpe des bytes en chunks de la taille du service."""
    size = PluginPackageService.CHUNK_SIZE
    return [data[i : i + size] for i in range(0, len(data), size)] or [b""]


async def _run_download(
    service: PluginPackageService,
    data: bytes,
    entry: Optional[RegistryPluginEntry] = None,
    session: Optional[AsyncMock] = None,
) -> PluginPackageResult:
    """Exécute download_and_extract sur une archive valide (cas nominal)."""
    checksum = hashlib.sha256(data).hexdigest()
    resolved_entry = entry or _make_entry(checksum=checksum)
    chunks = _chunks_of(data)
    resolved_session = session or _make_session(responses=[_make_response(200, chunks)])
    with patch(
        "app.services.plugin_package_service.aiohttp.ClientSession",
        return_value=resolved_session,
    ):
        with _dns(PUBLIC_RECORDS):
            return await service.download_and_extract(resolved_entry)


# ── Tests cas nominaux ───────────────────────────────────────────────────────


class TestDownloadAndExtractNominal:
    """Tests nominaux du pipeline download + extraction."""

    @pytest.mark.asyncio
    async def test_download_and_extract_success(
        self, service: PluginPackageService, tmp_path: Path
    ) -> None:
        """Cas nominal : archive valide + checksum correct → résultat rempli,
        arborescence extraite sous plugins_base_dir/{name}/, staging purgé."""
        data = _build_tar_bytes(_valid_package_members())

        result = await _run_download(service, data)

        assert isinstance(result, PluginPackageResult)
        assert result.name == "traefik"
        assert result.version == "1.2.0"
        assert result.package_size_bytes == len(data)
        assert result.files_count == 3
        # Checksum du résultat = checksum réel calculé du contenu
        assert result.checksum_sha256 == hashlib.sha256(data).hexdigest()
        # Arborescence extraite à la cible finale
        target = tmp_path / "traefik"
        assert (target / "windflow-plugin.yml").read_bytes().startswith(b"name:")
        assert (target / "README.md").exists()
        # Staging purgé (aucun résidu)
        assert not (tmp_path / ".staging").exists()

    @pytest.mark.asyncio
    async def test_download_follows_validated_redirect(
        self, service: PluginPackageService
    ) -> None:
        """Cas nominal : 301 vers URL publique — chaque hop revalidé (SSRF +
        DNS), puis succès."""
        data = _build_tar_bytes(_valid_package_members())
        checksum = hashlib.sha256(data).hexdigest()
        entry = _make_entry(checksum=checksum)
        redirect = _make_response(
            status=301,
            headers={
                "Location": "https://cdn.example.com/plugins/traefik/package.tar.gz"
            },
        )
        ok = _make_response(200, _chunks_of(data))
        session = _make_session(responses=[redirect, ok])

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS) as dns_calls:
                result = await service.download_and_extract(entry)

        assert result.name == "traefik"
        assert session.get.call_count == 2
        # Les deux hôtes (initial + redirection) ont été résolus/validés
        assert dns_calls == ["registry.example.com", "cdn.example.com"]


class TestDefaultSettings:
    """Tests des settings de bornage (T1)."""

    def test_default_settings_bounds(self) -> None:
        """Défauts : 200 Mo / 60 s (T1)."""
        config = Settings(_env_file=None)
        assert config.plugin_package_max_size_mb == 200
        assert config.plugin_package_download_timeout == 60

    @pytest.mark.parametrize(
        "field", ["plugin_package_max_size_mb", "plugin_package_download_timeout"]
    )
    def test_settings_bounds_ge_one(self, field: str) -> None:
        """Sécurité : ge=1 — valeur 0 rejetée (Validation)Error)."""
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{field: 0})


# ── Tests sécurité SSRF (AC 1) ───────────────────────────────────────────────


class TestSsrfValidation:
    """Tests de la validation SSRF de l'URL de téléchargement."""

    @pytest.mark.asyncio
    async def test_rejects_non_https_url(self, service: PluginPackageService) -> None:
        """Sécurité : URL http:// → rejet invalid_download_url."""
        entry = _make_entry()
        entry.download_url = "http://registry.example.com/package.tar.gz"

        with pytest.raises(WindFlowException) as exc_info:
            await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "invalid_download_url"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "192.168.1.1",
            "::1",
            "fd00::1",
            "::ffff:127.0.0.1",
        ],
    )
    async def test_rejects_private_ip_literal(
        self, service: PluginPackageService, host: str
    ) -> None:
        """Sécurité : hôte IP littéral non public → ssrf_blocked (couvre
        l'IPv4-mapped IPv6 et les metadata cloud 169.254.169.254)."""
        entry = _make_entry(download_url=f"https://{host}/package.tar.gz")

        with pytest.raises(WindFlowException) as exc_info:
            await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") in (
            "ssrf_blocked",
            "invalid_download_url",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "records",
        [
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 443))],
            [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443)),
            ],
        ],
        ids=["all-private", "mixed-public-private"],
    )
    async def test_rejects_host_resolving_to_private_ip(
        self, service: PluginPackageService, records: List[Tuple[Any, ...]]
    ) -> None:
        """Sécurité : DNS résolvant (même partiellement) vers une IP privée
        → ssrf_blocked (anti DNS-rebinding partiel)."""
        entry = _make_entry()

        with _dns(records):
            with pytest.raises(WindFlowException) as exc_info:
                await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "ssrf_blocked"

    @pytest.mark.asyncio
    async def test_rejects_redirect_to_private_ip(
        self, service: PluginPackageService
    ) -> None:
        """Sécurité : 301 vers IP privée → rejet, aucune seconde requête."""
        redirect = _make_response(
            status=301, headers={"Location": "https://127.0.0.1/x.tar.gz"}
        )
        session = _make_session(responses=[redirect])
        entry = _make_entry()

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "ssrf_blocked"
        # Aucune requête vers l'IP privée
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_rejects_too_many_redirects(
        self, service: PluginPackageService
    ) -> None:
        """Sécurité : boucle de redirections > MAX_REDIRECTS → rejet."""
        entry = _make_entry()

        def _always_redirect(*args: Any, **kwargs: Any) -> AsyncMock:
            return _make_response(
                status=302,
                headers={"Location": DEFAULT_DOWNLOAD_URL},
            )

        session = _make_session(side_effect=_always_redirect)

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "too_many_redirects"
        assert session.get.call_count == PluginPackageService.MAX_REDIRECTS + 1

    @pytest.mark.asyncio
    async def test_rejects_redirect_without_location(
        self, service: PluginPackageService
    ) -> None:
        """Sécurité : redirection sans en-tête Location → download_http_error."""
        redirect = _make_response(status=301, headers={})
        session = _make_session(responses=[redirect])
        entry = _make_entry()

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "download_http_error"

    @pytest.mark.asyncio
    async def test_rejects_userinfo_in_url(self, service: PluginPackageService) -> None:
        """Sécurité : URL avec userinfo (user:pass@host) → invalid_download_url."""
        entry = _make_entry(
            download_url="https://user:pass@registry.example.com/package.tar.gz"
        )

        with pytest.raises(WindFlowException) as exc_info:
            await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "invalid_download_url"


# ── Tests checksum obligatoire (AC 2) ────────────────────────────────────────


class TestChecksumVerification:
    """Tests de la vérification obligatoire du checksum SHA-256."""

    @pytest.mark.asyncio
    async def test_rejects_checksum_mismatch(
        self, service: PluginPackageService, tmp_path: Path
    ) -> None:
        """Sécurité : contenu altéré → checksum_mismatch avec message
        explicite, staging purgé."""
        data = _build_tar_bytes(_valid_package_members())
        entry = _make_entry(checksum="b" * 64)

        with pytest.raises(WindFlowException, match="Checksum") as exc_info:
            await _run_download(service, data, entry=entry)

        assert exc_info.value.details.get("error_type") == "checksum_mismatch"
        assert exc_info.value.details.get("expected_prefix") == "bbbbbbbbbbbb"
        assert exc_info.value.details.get("actual_prefix") != "bbbbbbbbbbbb"
        assert not (tmp_path / ".staging").exists()

    @pytest.mark.asyncio
    async def test_rejects_missing_checksum(
        self, service: PluginPackageService
    ) -> None:
        """Sécurité : entrée sans checksum (validation Pydantic bypassée)
        → checksum_missing (défense en profondeur)."""
        data = _build_tar_bytes(_valid_package_members())
        entry = _make_entry()
        entry.checksum_sha256 = ""

        with pytest.raises(WindFlowException) as exc_info:
            await _run_download(service, data, entry=entry)

        assert exc_info.value.details.get("error_type") == "checksum_missing"


# ── Tests streaming borné (AC 1) ─────────────────────────────────────────────


class TestBoundedStreaming:
    """Tests du téléchargement streaming borné et de ses erreurs."""

    @pytest.mark.asyncio
    async def test_rejects_package_over_max_size(self, tmp_path: Path) -> None:
        """Sécurité : flux > plugin_package_max_size_mb → package_too_large,
        arrêt avant la fin du flux, staging purgé."""
        small_settings = Settings(
            plugins_base_dir=str(tmp_path), plugin_package_max_size_mb=1
        )
        service = PluginPackageService(small_settings)
        chunk = b"a" * (512 * 1024)
        stream = _ChunkStream([chunk, chunk, chunk, chunk])
        response = _make_response(200, stream=stream)
        session = _make_session(responses=[response])
        entry = _make_entry()

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "package_too_large"
        # Arrêt avant la fin du flux : 3 chunks consommés sur 4
        assert stream.consumed == 3
        assert not (tmp_path / ".staging").exists()

    @pytest.mark.asyncio
    async def test_rejects_download_timeout(
        self, service: PluginPackageService
    ) -> None:
        """Cas d'erreur : timeout → download_timeout."""
        session = _make_session(side_effect=asyncio.TimeoutError())
        entry = _make_entry()

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "download_timeout"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [404, 500])
    async def test_rejects_http_error_status(
        self, service: PluginPackageService, status: int
    ) -> None:
        """Cas d'erreur : statut HTTP != 200 → download_http_error."""
        session = _make_session(responses=[_make_response(status=status)])
        entry = _make_entry()

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "download_http_error"

    @pytest.mark.asyncio
    async def test_rejects_network_error(self, service: PluginPackageService) -> None:
        """Cas d'erreur : aiohttp.ClientError → download_failed."""
        session = _make_session(side_effect=aiohttp.ClientConnectionError("boom"))
        entry = _make_entry()

        with patch(
            "app.services.plugin_package_service.aiohttp.ClientSession",
            return_value=session,
        ):
            with _dns(PUBLIC_RECORDS):
                with pytest.raises(WindFlowException) as exc_info:
                    await service.download_and_extract(entry)

        assert exc_info.value.details.get("error_type") == "download_failed"


# ── Tests extraction durcie (AC 3, divergence n°8) ───────────────────────────


class TestHardenedExtraction:
    """Tests de l'extraction durcie (pré-scan, anti-bombe, atomique)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("evil_name", ["../evil.sh", "/etc/passwd", "..\\win-path"])
    async def test_rejects_path_traversal_member(
        self,
        service: PluginPackageService,
        tmp_path: Path,
        evil_name: str,
    ) -> None:
        """Sécurité : membre ../, chemin absolu ou backslash →
        package_unsafe_member sans écriture hors staging."""
        members: List[_Member] = [
            _dir_member("traefik"),
            _file_member(evil_name),
        ]
        data = _build_tar_bytes(members)

        with pytest.raises(WindFlowException) as exc_info:
            await _run_download(service, data)

        assert exc_info.value.details.get("error_type") == "package_unsafe_member"
        # Aucune écriture hors staging : la cible finale n'existe pas
        assert not (tmp_path / "traefik").exists()
        assert not (tmp_path / ".staging").exists()
        # Le fichier malveillant n'a jamais été écrit à la racine
        assert not (tmp_path / "evil.sh").exists()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("mtype", "linkname"),
        [
            (tarfile.SYMTYPE, "/etc/passwd"),
            (tarfile.LNKTYPE, "traefik/README.md"),
            (tarfile.FIFOTYPE, None),
            (tarfile.CHRTYPE, None),
        ],
        ids=["symlink", "hardlink", "fifo", "device"],
    )
    async def test_rejects_symlink_and_special_members(
        self,
        service: PluginPackageService,
        tmp_path: Path,
        mtype: bytes,
        linkname: Optional[str],
    ) -> None:
        """Sécurité : symlink/hardlink/FIFO/device → package_unsafe_member
        (seuls fichiers réguliers et répertoires sont autorisés)."""
        members: List[_Member] = [
            _dir_member("traefik"),
            _special_member("traefik/evil", mtype, linkname),
        ]
        data = _build_tar_bytes(members)

        with pytest.raises(WindFlowException) as exc_info:
            await _run_download(service, data)

        assert exc_info.value.details.get("error_type") == "package_unsafe_member"
        assert not (tmp_path / ".staging").exists()

    @pytest.mark.asyncio
    async def test_rejects_member_count_bomb(
        self, service: PluginPackageService
    ) -> None:
        """Sécurité : plus de MAX_ARCHIVE_MEMBERS membres → package_bomb."""
        members: List[_Member] = [
            _file_member(f"f{i}", b"x")
            for i in range(PluginPackageService.MAX_ARCHIVE_MEMBERS + 1)
        ]
        data = _build_tar_bytes(members)

        with pytest.raises(WindFlowException) as exc_info:
            await _run_download(service, data)

        assert exc_info.value.details.get("error_type") == "package_bomb"

    @pytest.mark.asyncio
    async def test_rejects_decompressed_size_bomb(self, tmp_path: Path) -> None:
        """Sécurité : somme des tailles décompressées > max_size × facteur
        → package_bomb (11 Mo de contenu, borne 1 Mo × 10)."""
        small_settings = Settings(
            plugins_base_dir=str(tmp_path), plugin_package_max_size_mb=1
        )
        service = PluginPackageService(small_settings)
        members: List[_Member] = [
            _file_member(f"blob{i}", b"\0" * (1024 * 1024)) for i in range(11)
        ]
        data = _build_tar_bytes(members)

        with pytest.raises(WindFlowException) as exc_info:
            await _run_download(service, data)

        assert exc_info.value.details.get("error_type") == "package_bomb"

    @pytest.mark.asyncio
    async def test_rejects_when_target_exists(
        self, service: PluginPackageService, tmp_path: Path
    ) -> None:
        """Cas d'erreur : plugins_base_dir/{name} pré-existant → target_exists,
        contenu existant intact."""
        target = tmp_path / "traefik"
        target.mkdir()
        (target / "keep.txt").write_text("existing", encoding="utf-8")
        data = _build_tar_bytes(_valid_package_members())

        with pytest.raises(WindFlowException) as exc_info:
            await _run_download(service, data)

        assert exc_info.value.details.get("error_type") == "target_exists"
        # Le contenu existant est intact
        assert (target / "keep.txt").read_text(encoding="utf-8") == "existing"
        assert not (tmp_path / ".staging").exists()


# ── Tests hygiène (résidus + logs) ───────────────────────────────────────────


class TestHygiene:
    """Tests d'hygiène filesystem et de logs."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "scenario",
        ["checksum_mismatch", "unsafe_member", "bomb_count", "target_exists"],
    )
    async def test_no_residue_on_any_failure(
        self,
        service: PluginPackageService,
        tmp_path: Path,
        scenario: str,
    ) -> None:
        """AC 3 : sur tout rejet, le staging est purgé — .staging n'existe
        plus après l'appel."""
        entry = _make_entry()
        if scenario == "checksum_mismatch":
            data = _build_tar_bytes(_valid_package_members())
            entry = _make_entry(checksum="b" * 64)
        elif scenario == "unsafe_member":
            members: List[_Member] = _valid_package_members() + [
                _special_member("traefik/evil", tarfile.SYMTYPE, "/etc/passwd")
            ]
            data = _build_tar_bytes(members)
        elif scenario == "bomb_count":
            members = [
                _file_member(f"f{i}", b"x")
                for i in range(PluginPackageService.MAX_ARCHIVE_MEMBERS + 1)
            ]
            data = _build_tar_bytes(members)
        else:  # target_exists
            (tmp_path / "traefik").mkdir()
            data = _build_tar_bytes(_valid_package_members())

        with pytest.raises(WindFlowException):
            await _run_download(service, data, entry=entry)

        assert not (tmp_path / ".staging").exists()

    @pytest.mark.asyncio
    async def test_logs_contain_no_package_content(
        self,
        service: PluginPackageService,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Rules 40 : aucun contenu de package (ni donnée sensible) dans les
        logs — seulement host/taille/durée."""
        secret = b"TOPSECRET-PACKAGE-PAYLOAD"
        members: List[_Member] = [
            _dir_member("traefik"),
            _file_member("traefik/windflow-plugin.yml", secret),
        ]
        data = _build_tar_bytes(members)

        with caplog.at_level(
            logging.INFO, logger="app.services.plugin_package_service"
        ):
            await _run_download(service, data)

        assert "plugin_package_download_completed" in caplog.text
        assert "TOPSECRET" not in caplog.text
