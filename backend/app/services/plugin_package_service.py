"""
Service de téléchargement et d'extraction sécurisés des packages plugins.

STORY-169.1 — volet DOWNLOAD du pipeline d'installation (spec 11, étape 1) :

- **validation SSRF** de l'URL du registre (schéma HTTPS strict, pas de
  userinfo/fragment, rejet des IP non publiques — littérales comme résolues,
  redirections revalidées à chaque hop, OWASP SSRF) ;
- **téléchargement streaming borné** (jamais tout-en-mémoire) avec calcul
  du SHA-256 pendant le flux et abandon immédiat au-delà de
  ``plugin_package_max_size_mb`` ;
- **checksum SHA-256 obligatoire** sourcé de ``RegistryPluginEntry`` —
  comparaison en temps constant (``hmac.compare_digest``), rejet sur écart
  ou absence ;
- **extraction durcie** (pré-scan complet avant toute écriture : anti
  path-traversal, symlinks/hardlinks/devices/FIFO rejetés en bloc,
  anti-bombe par nombre de membres et taille décompressée totale) ;
- **install atomique** : extraction en staging (même filesystem que
  ``plugins_base_dir``) puis renommage atomique vers
  ``plugins_base_dir/{name}/`` ;
- **aucun résidu filesystem** : le staging est purgé en ``finally`` sur
  tous les chemins (succès comme échec).

Aucune logique HTTP n'est exposée hors de ce service (consumé par
``PluginManagerService``). Les logs sont structurés et ne contiennent
jamais de contenu de package ni de données sensibles (rules 40).
"""

import asyncio
import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import shutil
import socket
import tarfile
import time
from pathlib import Path
from typing import Optional, Tuple, Union

import aiohttp
import yarl

from ..config import Settings
from ..core.exceptions import WindFlowException
from ..schemas.plugin_package import PluginPackageResult
from ..schemas.plugin_registry import RegistryPluginEntry

logger = logging.getLogger(__name__)

#: Statuts HTTP considérés comme redirections (suivies manuellement).
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

#: Type union des adresses IP manipulées par la validation SSRF.
_IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


class PluginPackageService:
    """Service métier de téléchargement/extraction sécurisés d'un package.

    Un service = une classe, DI ``Settings`` (pattern
    ``PluginRegistryService``). La méthode publique ``download_and_extract``
    orchestre le pipeline complet : validation SSRF → download streaming
    borné → checksum obligatoire → extraction durcie → install atomique.
    """

    #: Nombre maximal de redirections suivies (chacune revalidée SSRF).
    MAX_REDIRECTS: int = 5

    #: Taille des chunks du streaming download (64 KiB).
    CHUNK_SIZE: int = 64 * 1024

    #: Nombre maximal de membres dans l'archive (anti-bombe).
    MAX_ARCHIVE_MEMBERS: int = 2000

    #: Facteur de la borne décompressée : plugin_package_max_size_mb × 10.
    MAX_EXTRACTION_FACTOR: int = 10

    def __init__(self, settings: Settings) -> None:
        """Initialise le service avec la configuration donnée.

        Args:
            settings: Instance des settings de l'application.
        """
        self._settings = settings

    # ── Pipeline public ──────────────────────────────────────────────────────

    async def download_and_extract(
        self, entry: RegistryPluginEntry
    ) -> PluginPackageResult:
        """Télécharge, vérifie et extrait le package d'une entrée du registre.

        Args:
            entry: Entrée du registre officiel (source de vérité du
                ``download_url`` HTTPS et du ``checksum_sha256`` attendu).

        Returns:
            ``PluginPackageResult`` décrivant le package extrait sous
            ``plugins_base_dir/{name}/``.

        Raises:
            WindFlowException: Typée via ``details["error_type"]`` —
                ``invalid_download_url`` / ``ssrf_blocked`` /
                ``too_many_redirects`` / ``download_http_error`` /
                ``download_timeout`` / ``download_failed`` /
                ``package_too_large`` / ``checksum_missing`` /
                ``checksum_mismatch`` / ``package_unsafe_member`` /
                ``package_bomb`` / ``package_invalid`` /
                ``target_exists`` / ``package_storage_error``.
        """
        staging_dir = (
            Path(self._settings.plugins_base_dir)
            / ".staging"
            / f"{entry.name}-{secrets.token_hex(8)}"
        )
        try:
            staging_dir.mkdir(parents=True, exist_ok=True)
            archive_path = staging_dir / "package.tar.gz"

            digest_hex, size_bytes = await self._download(entry, archive_path)
            self._verify_checksum(entry.checksum_sha256, digest_hex)
            files_count = self._extract_package(archive_path, staging_dir, entry)

            result = PluginPackageResult(
                name=entry.name,
                version=entry.version,
                checksum_sha256=digest_hex,
                package_size_bytes=size_bytes,
                extracted_path=str(Path(self._settings.plugins_base_dir) / entry.name),
                files_count=files_count,
            )
            logger.info(
                "plugin_package_extracted",
                extra={
                    "plugin_name": entry.name,
                    "version": entry.version,
                    "files_count": files_count,
                    "package_size_bytes": size_bytes,
                },
            )
            return result
        finally:
            # Aucun résidu filesystem, succès comme échec (AC 3) :
            # le contenu extrait a déjà été renommé hors du staging en
            # cas de succès — il ne reste que l'archive à purger.
            shutil.rmtree(staging_dir, ignore_errors=True)
            try:
                # Purge du parent .staging si vide (concurrence safe :
                # rmdir échoue silencieusement s'il n'est pas vide).
                staging_dir.parent.rmdir()
            except OSError:
                pass

    # ── Download (validation SSRF + streaming borné) ─────────────────────────

    async def _download(
        self, entry: RegistryPluginEntry, archive_path: Path
    ) -> Tuple[str, int]:
        """Télécharge le package en streaming vers ``archive_path``.

        Redirections gérées manuellement (``allow_redirects=False``) avec
        revalidation SSRF complète à chaque hop — jamais de redirection
        suivie sans validation préalable (OWASP SSRF).

        Args:
            entry: Entrée du registre (nom + URL de téléchargement).
            archive_path: Chemin du fichier archive à écrire (staging).

        Returns:
            Tuple (sha256_hexdigest, taille en octets du package).

        Raises:
            WindFlowException: Erreurs typées download/SSRF (voir
                ``download_and_extract``).
        """
        max_bytes = self._settings.plugin_package_max_size_mb * 1024 * 1024
        timeout = aiohttp.ClientTimeout(
            total=self._settings.plugin_package_download_timeout
        )
        current_url = self._validate_url(entry.download_url)
        await self._assert_public_host(current_url.host or "")

        logger.info(
            "plugin_package_download_started",
            extra={"plugin_name": entry.name, "host": current_url.host},
        )
        started = time.monotonic()
        redirects = 0

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while True:
                    async with session.get(
                        str(current_url), allow_redirects=False
                    ) as response:
                        if response.status in _REDIRECT_STATUSES:
                            redirects += 1
                            if redirects > self.MAX_REDIRECTS:
                                raise WindFlowException(
                                    f"Trop de redirections (max {self.MAX_REDIRECTS}) "
                                    f"lors du téléchargement du package '{entry.name}'",
                                    details={
                                        "error_type": "too_many_redirects",
                                        "redirects": redirects,
                                    },
                                )
                            location = self._require_location(response)
                            next_url = self._validate_url(location)
                            # Revalidation SSRF complète à chaque hop
                            await self._assert_public_host(next_url.host or "")
                            current_url = next_url
                            continue

                        if response.status != 200:
                            raise WindFlowException(
                                f"Erreur HTTP {response.status} lors du "
                                f"téléchargement du package '{entry.name}'",
                                details={
                                    "error_type": "download_http_error",
                                    "status": response.status,
                                },
                            )

                        digest_hex, size_bytes = await self._stream_to_file(
                            response, archive_path, max_bytes
                        )
                        logger.info(
                            "plugin_package_download_completed",
                            extra={
                                "plugin_name": entry.name,
                                "package_size_bytes": size_bytes,
                                "duration_seconds": round(
                                    time.monotonic() - started, 3
                                ),
                            },
                        )
                        return digest_hex, size_bytes

        except asyncio.TimeoutError as exc:
            logger.warning(
                "plugin_package_download_failed",
                extra={"plugin_name": entry.name, "reason": "timeout"},
            )
            raise WindFlowException(
                f"Timeout lors du téléchargement du package '{entry.name}'",
                details={"error_type": "download_timeout"},
            ) from exc

        except aiohttp.ClientError as exc:
            logger.warning(
                "plugin_package_download_failed",
                extra={"plugin_name": entry.name, "reason": "network"},
            )
            raise WindFlowException(
                f"Erreur réseau lors du téléchargement du package "
                f"'{entry.name}' : {exc}",
                details={"error_type": "download_failed"},
            ) from exc

    async def _stream_to_file(
        self,
        response: aiohttp.ClientResponse,
        archive_path: Path,
        max_bytes: int,
    ) -> Tuple[str, int]:
        """Stream la réponse vers le disque en bornant la taille totale.

        Le SHA-256 est calculé pendant le flux (jamais de relecture) et le
        compteur d'octets abandonne immédiatement au-delà de la borne —
        sans consommer la fin du flux.

        Args:
            response: Réponse HTTP 200 ouverte.
            archive_path: Fichier archive de destination (staging).
            max_bytes: Borne stricte en octets.

        Returns:
            Tuple (sha256_hexdigest, taille en octets écrits).

        Raises:
            WindFlowException: ``package_too_large`` au-delà de la borne,
                ``download_failed`` sur erreur d'écriture disque.
        """
        hasher = hashlib.sha256()
        size = 0
        try:
            with archive_path.open("wb") as fh:
                async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise WindFlowException(
                            f"Package trop volumineux : dépasse la limite de "
                            f"{max_bytes // (1024 * 1024)} Mo",
                            details={
                                "error_type": "package_too_large",
                                "max_size_bytes": max_bytes,
                            },
                        )
                    hasher.update(chunk)
                    fh.write(chunk)
        except OSError as exc:
            raise WindFlowException(
                f"Erreur d'écriture du package téléchargé : {exc}",
                details={"error_type": "download_failed"},
            ) from exc
        return hasher.hexdigest(), size

    @staticmethod
    def _require_location(response: aiohttp.ClientResponse) -> str:
        """Extrait l'en-tête ``Location`` d'une réponse de redirection.

        Args:
            response: Réponse HTTP avec statut 3xx.

        Returns:
            La valeur brute de l'en-tête ``Location``.

        Raises:
            WindFlowException: ``download_http_error`` si absente.
        """
        location = response.headers.get("Location")
        if not location:
            raise WindFlowException(
                "Redirection sans en-tête Location",
                details={"error_type": "download_http_error"},
            )
        return location

    # ── Validation SSRF ──────────────────────────────────────────────────────

    @staticmethod
    def _validate_url(url: str) -> yarl.URL:
        """Valide statiquement une URL de téléchargement (divergence n°9).

        Contrôles : schéma ``https`` strict, hôte non vide, pas de
        userinfo (``user:pass@host``), pas de fragment, rejet de tout
        hôte IP littéral non public (``ipaddress`` — privé, loopback,
        link-local dont ``169.254.169.254``, réservé, multicast,
        non spécifié, IPv4-mapped IPv6 inclus).

        Args:
            url: URL brute à valider.

        Returns:
            L'URL parsée (``yarl.URL``).

        Raises:
            WindFlowException: ``invalid_download_url`` (malformée, non
                HTTPS, userinfo/fragment) ou ``ssrf_blocked`` (IP
                littérale non publique).
        """
        try:
            parsed = yarl.URL(url)
        except (ValueError, TypeError) as exc:
            raise WindFlowException(
                f"URL de téléchargement invalide : {url}",
                details={"error_type": "invalid_download_url"},
            ) from exc

        if parsed.scheme != "https" or not parsed.host:
            raise WindFlowException(
                "L'URL de téléchargement doit être en HTTPS avec un hôte valide",
                details={"error_type": "invalid_download_url"},
            )
        if parsed.user is not None or parsed.password is not None or parsed.fragment:
            raise WindFlowException(
                "URL de téléchargement avec userinfo ou fragment interdite",
                details={"error_type": "invalid_download_url"},
            )

        # Hôte IP littéral : rejet immédiat de toute adresse non publique
        try:
            literal_ip = ipaddress.ip_address(parsed.host)
        except ValueError:
            return parsed  # hostname — contrôlé à la résolution DNS
        if not PluginPackageService._is_public_ip(literal_ip):
            raise WindFlowException(
                f"Hôte IP non public interdit (protection SSRF) : {parsed.host}",
                details={"error_type": "ssrf_blocked", "host": parsed.host},
            )
        return parsed

    async def _assert_public_host(self, host: str) -> None:
        """Vérifie que le hôte résout exclusivement vers des IP publiques.

        Anti DNS-rebinding partiel : **toutes** les adresses résolues via
        ``getaddrinfo`` doivent être publiques, sinon rejet.

        Args:
            host: Nom d'hôte (déjà validé syntaxiquement).

        Raises:
            WindFlowException: ``invalid_download_url`` si hôte vide,
                ``download_failed`` si la résolution échoue,
                ``ssrf_blocked`` si une adresse résolue n'est pas publique.
        """
        if not host:
            raise WindFlowException(
                "Hôte de téléchargement vide",
                details={"error_type": "invalid_download_url"},
            )
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(
                host, 443, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
            )
        except socket.gaierror as exc:
            raise WindFlowException(
                f"Impossible de résoudre l'hôte de téléchargement : {host}",
                details={"error_type": "download_failed", "host": host},
            ) from exc

        for info in infos:
            address = info[4][0]
            try:
                resolved_ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            if not self._is_public_ip(resolved_ip):
                raise WindFlowException(
                    f"L'hôte '{host}' résout vers une adresse non publique "
                    f"(protection SSRF) : {address}",
                    details={"error_type": "ssrf_blocked", "host": host},
                )

    @staticmethod
    def _is_public_ip(ip: _IPAddress) -> bool:
        """Indique si une adresse IP est strictement publique.

        Les IPv4-mapped IPv6 sont normalisées vers leur IPv4 incluse
        avant contrôle (couvre ``::ffff:127.0.0.1`` par exemple).

        Args:
            ip: Adresse à contrôler.

        Returns:
            True si publique, False sinon.
        """
        candidate: _IPAddress = ip
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            candidate = ip.ipv4_mapped
        return not (
            candidate.is_private
            or candidate.is_loopback
            or candidate.is_link_local
            or candidate.is_reserved
            or candidate.is_multicast
            or candidate.is_unspecified
        )

    # ── Checksum obligatoire ─────────────────────────────────────────────────

    @staticmethod
    def _verify_checksum(expected: Optional[str], actual_hex: str) -> None:
        """Vérifie le checksum SHA-256 obligatoire (AC 2).

        Défense en profondeur : le schéma registre rend déjà le checksum
        requis, mais le downloader revalide (absence → rejet). La
        comparaison utilise ``hmac.compare_digest`` (temps constant).

        Args:
            expected: Checksum attendu (source registre).
            actual_hex: Checksum calculé pendant le téléchargement.

        Raises:
            WindFlowException: ``checksum_missing`` si absent/vide,
                ``checksum_mismatch`` sur écart (message explicite :
                attendu vs obtenu tronqués, cause et suggestion).
        """
        if not expected:
            raise WindFlowException(
                "Checksum SHA-256 absent de l'entrée du registre — le "
                "téléchargement d'un package sans somme de contrôle est "
                "refusé",
                details={"error_type": "checksum_missing"},
            )
        if not hmac.compare_digest(expected.lower(), actual_hex.lower()):
            raise WindFlowException(
                f"Checksum SHA-256 invalide pour le package téléchargé : "
                f"attendu {expected[:12]}…, obtenu {actual_hex[:12]}… — le "
                f"contenu ne correspond pas à la somme publiée par le "
                f"registre (package corrompu ou compromis). Réessayez ; si "
                f"l'écart persiste, contactez l'administrateur du registre.",
                details={
                    "error_type": "checksum_mismatch",
                    "expected_prefix": expected[:12],
                    "actual_prefix": actual_hex[:12],
                },
            )

    # ── Extraction durcie + install atomique ─────────────────────────────────

    def _extract_package(
        self, archive_path: Path, staging_dir: Path, entry: RegistryPluginEntry
    ) -> int:
        """Extrait l'archive tar.gz de manière durcie (AC 3, divergence n°8).

        Pré-scan de **tous** les membres avant toute écriture : types
        (fichiers réguliers + répertoires uniquement — symlinks/hardlinks/
        devices/FIFO rejetés en bloc), noms (``..``, chemins absolus,
        backslashes rejetés ; containment ``realpath``/``commonpath``),
        anti-bombe (nombre de membres et taille décompressée totale
        bornés). L'extraction passe ensuite par ``filter="data"`` (PEP
        706) en défense en profondeur, puis renommage atomique du
        répertoire extrait vers ``plugins_base_dir/{name}`` (même
        filesystem que le staging).

        Args:
            archive_path: Archive téléchargée (vérifiée checksum).
            staging_dir: Répertoire de staging (purge garantie par
                l'appelant).
            entry: Entrée du registre (nom = répertoire cible, déjà
                validé kebab-case par le schéma registre — anti
                path-traversal natif).

        Returns:
            Nombre de membres extraits.

        Raises:
            WindFlowException: ``package_bomb`` (membres/taille),
                ``package_unsafe_member`` (type ou nom de membre),
                ``package_invalid`` (archive illisible),
                ``target_exists`` (répertoire cible déjà présent —
                l'upgrade/overwrite est arbitrée en STORY-169.3),
                ``package_storage_error`` (échec filesystem local).
        """
        extract_dir = staging_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        resolved_root = os.path.realpath(extract_dir)
        max_decompressed = (
            self._settings.plugin_package_max_size_mb
            * 1024
            * 1024
            * self.MAX_EXTRACTION_FACTOR
        )

        try:
            with tarfile.open(archive_path, mode="r:gz") as tar:
                members = tar.getmembers()

                # -- Pré-scan : aucun membre n'est écrit avant que TOUS
                #    ne soient validés (rejet sans écriture partielle).
                if len(members) > self.MAX_ARCHIVE_MEMBERS:
                    raise WindFlowException(
                        f"Archive suspectée de bombe : {len(members)} membres "
                        f"(max {self.MAX_ARCHIVE_MEMBERS})",
                        details={
                            "error_type": "package_bomb",
                            "members_count": len(members),
                            "max_members": self.MAX_ARCHIVE_MEMBERS,
                        },
                    )

                total_size = 0
                for member in members:
                    # Types : fichiers réguliers et répertoires uniquement
                    if not (member.isfile() or member.isdir()):
                        raise WindFlowException(
                            f"Membre d'archive interdit (seuls les fichiers "
                            f"et répertoires sont autorisés) : {member.name}",
                            details={
                                "error_type": "package_unsafe_member",
                                "member": member.name,
                            },
                        )
                    # Noms : anti path-traversal
                    if self._is_unsafe_member_name(member.name):
                        raise WindFlowException(
                            f"Chemin de membre d'archive interdit "
                            f"(path traversal) : {member.name}",
                            details={
                                "error_type": "package_unsafe_member",
                                "member": member.name,
                            },
                        )
                    target_path = os.path.realpath(extract_dir / member.name)
                    if (
                        os.path.commonpath([resolved_root, target_path])
                        != resolved_root
                    ):
                        raise WindFlowException(
                            f"Chemin de membre d'archive hors du répertoire "
                            f"d'extraction : {member.name}",
                            details={
                                "error_type": "package_unsafe_member",
                                "member": member.name,
                            },
                        )
                    total_size += member.size

                # -- Anti-bombe : taille décompressée totale bornée
                if total_size > max_decompressed:
                    raise WindFlowException(
                        f"Archive suspectée de bombe : taille décompressée "
                        f"totale {total_size} octets > borne "
                        f"{max_decompressed} octets",
                        details={
                            "error_type": "package_bomb",
                            "total_size": total_size,
                            "max_decompressed": max_decompressed,
                        },
                    )

                # -- Extraction avec filter="data" (PEP 706) : défense en
                #    profondeur en plus des contrôles explicites ci-dessus.
                tar.extractall(path=extract_dir, members=members, filter="data")

            # -- Racine du contenu utile : les packages conventionnels
            #    ({name}-{version}.tar.gz, spec 12) enveloppent le contenu
            #    dans un répertoire {name}/ ; d'autres servent le manifest
            #    à la racine. Dans tous les cas le manifest doit aboutir
            #    sous plugins_base_dir/{name}/windflow-plugin.yml.
            content_root = extract_dir
            nested_root = extract_dir / entry.name
            if not (content_root / "windflow-plugin.yml").exists() and (
                nested_root.is_dir()
            ):
                content_root = nested_root

            # -- Install atomique : renommage (même filesystem que le
            #    staging). entry.name est déjà validé kebab-case.
            target_dir = Path(self._settings.plugins_base_dir) / entry.name
            if target_dir.exists():
                raise WindFlowException(
                    f"Le répertoire cible existe déjà : {target_dir} "
                    f"(l'upgrade est arbitré en STORY-169.3)",
                    details={"error_type": "target_exists", "target": str(target_dir)},
                )
            content_root.rename(target_dir)
            return len(members)

        except tarfile.TarError as exc:
            raise WindFlowException(
                f"Archive du package invalide ou corrompue : {exc}",
                details={"error_type": "package_invalid"},
            ) from exc
        except OSError as exc:
            raise WindFlowException(
                f"Erreur filesystem lors de l'extraction : {exc}",
                details={"error_type": "package_storage_error"},
            ) from exc

    @staticmethod
    def _is_unsafe_member_name(name: str) -> bool:
        """Détecte un nom de membre d'archive dangereux.

        Args:
            name: Nom brut du membre dans l'archive.

        Returns:
            True si le nom est un chemin absolu, contient ``..``,
            contient un backslash (chemin Windows) ou est vide.
        """
        if not name:
            return True
        if name.startswith("/") or name.startswith("\\"):
            return True
        if "\\" in name:
            return True
        return ".." in name.split("/")
