"""Browse du contenu d'un volume Docker — conteneur éphémère sécurisé (STORY-173).

Sécurité (décision D3, checklist rules 40) — le browse monte **jamais**
le socket ni le filesystem hôte, il exécute ``ls`` dans un conteneur
éphémère durci :

- **image épinglée** : ``busybox:1.37`` (tag de version explicite —
  jamais ``:latest``, pas de mutation silencieuse du binaire exécuté) ;
- **montage read-only** : le volume est monté ``mode="ro"`` — le browse
  est une opération de lecture, aucune écriture n'est possible ;
- **réseau isolé** : ``network_mode="none"`` — aucun réseau, aucune
  exfiltration possible ;
- **pas de privileged** (défaut ``False`` du wrapper) et filesystem
  racine en lecture seule (``readonly_rootfs=True``) ;
- **exec en args-liste, aucun shell** : la commande est passée en
  ``["ls", "-1p", "/vol/..."]`` — aucune interpolation de chaîne vers
  le démon, aucune injection possible ;
- **anti-traversal** : le sous-chemin est validé (rejet ``..`` et
  chemins absolus) et le nom de volume par regex Docker ;
- **nettoyage garanti** : le conteneur éphémère est retiré en
  ``finally``, même sur erreur d'exec (aucun conteneur orphelin).

Le pull de l'image au premier appel (réflexe Docker sur image absente)
est un comportement documenté.
"""

import logging
import re
from typing import List, Optional
from uuid import uuid4

from ..core.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
    UnprocessableEntityError,
    WindFlowException,
)
from ..helper.pagination import paginate_sequence
from ..schemas.common import PaginatedResponse
from ..schemas.compute import VolumeBrowseEntry
from .docker_client_service import DockerClientService

logger = logging.getLogger(__name__)

# Image de browse épinglée (STORY-173 D3) — JAMAIS :latest.
BROWSE_IMAGE = "busybox:1.37"

# Point de montage du volume dans le conteneur éphémère (read-only).
BROWSE_MOUNT_DESTINATION = "/vol"

# Regex de nom de volume Docker (spec Engine — référence du schéma
# VolumeCreateRequest du router docker) : alphanumérique en tête,
# puis alphanumérique/_/.- , 256 caractères max.
VOLUME_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")


def _validate_volume_name(name: str) -> None:
    """Valide le nom de volume (regex Docker) — 422 sinon.

    Rules 40 (injection) : un nom malformé ne peut jamais atteindre le
    path de l'API Engine ni le nom du conteneur éphémère.
    """
    if not VOLUME_NAME_PATTERN.match(name):
        raise UnprocessableEntityError(
            f"Nom de volume invalide : {name!r} (doit matcher "
            "^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$)"
        )


def _validate_subpath(subpath: str) -> None:
    """Valide le sous-chemin (anti-traversal) — 422 sinon.

    Rejette tout chemin absolu (``/etc``) et toute tentative de
    remontée (``..``) — le sous-chemin reste relatif au point de
    montage ``/vol`` du conteneur éphémère.
    """
    if not subpath:
        return
    if subpath.startswith("/") or subpath.startswith("\\"):
        raise UnprocessableEntityError(
            f"Sous-chemin invalide : {subpath!r} (chemin relatif attendu)"
        )
    parts = re.split(r"[\\/]+", subpath)
    if any(part == ".." for part in parts):
        raise UnprocessableEntityError(
            f"Sous-chemin invalide : {subpath!r} (.. interdit)"
        )


def _parse_ls_output(output: str, prefix: str) -> List[VolumeBrowseEntry]:
    """Parse la sortie ``ls -1p`` en entrées fichier/dossier.

    ``ls -1p`` liste une entrée par ligne, les dossiers avec un suffixe
    ``/``. Le ``prefix`` (sous-chemin demandé, sans slash final) est
    reporté sur le champ ``path`` de chaque entrée.
    """
    entries: List[VolumeBrowseEntry] = []
    prefix_clean = prefix.strip("/")
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        is_dir = line.endswith("/")
        name = line.rstrip("/")
        if not name:
            continue
        path = f"{prefix_clean}/{name}" if prefix_clean else name
        entries.append(VolumeBrowseEntry(name=name, is_dir=is_dir, path=path))
    return entries


async def browse_volume(
    name: str,
    subpath: Optional[str],
    page: int,
    per_page: int,
) -> PaginatedResponse:
    """Liste le contenu d'un volume via un conteneur éphémère sécurisé.

    Pipeline (D3) :

    1. validations d'entrée (nom regex + subpath anti-traversal → 422) ;
    2. existence du volume (``list_volumes`` → 404 si absent) ;
    3. conteneur éphémère ``windflow-browse-{uuid8}`` (image épinglée,
       montage read-only, réseau none, label transitoire) ;
    4. exec ``ls -1p /vol[/{subpath}]`` (args liste — aucun shell) ;
    5. parsing de la sortie + pagination mémoire ;
    6. ``finally`` : ``remove_container(force=True)`` garanti, même sur
       erreur d'exec.

    Docker indisponible → :class:`ServiceUnavailableError` explicite
    (jamais de 200 vide trompeur — rules 40/20).

    Args:
        name: Nom du volume Docker.
        subpath: Sous-chemin optionnel dans le volume (relatif, sans ..).
        page: Page demandée (1-indexée).
        per_page: Taille de page (bornée par PaginationQuery).

    Returns:
        :class:`PaginatedResponse` d'entrées :class:`VolumeBrowseEntry`.

    Raises:
        UnprocessableEntityError: Nom de volume ou sous-chemin invalide.
        NotFoundError: Volume introuvable sur le démon.
        ServiceUnavailableError: Docker indisponible.
        WindFlowException: Erreur d'exécution du browse (exec non nul).
    """
    _validate_volume_name(name)
    if subpath is not None:
        _validate_subpath(subpath)
    subpath_clean = (subpath or "").strip("/")

    client = DockerClientService()
    try:
        # Existence : comparaison de liste (le daemon n'expose pas de
        # GET /volumes/{name} fiable sur toutes les versions).
        try:
            volumes = await client.list_volumes()
        except Exception as exc:
            logger.warning("browse_volume : Docker indisponible (%s)", exc)
            raise ServiceUnavailableError(
                "Docker indisponible — le browse de volume requiert le démon local"
            ) from exc
        if not any(v.name == name for v in volumes):
            raise NotFoundError(f"Volume {name} non trouvé")

        # Conteneur éphémère durci (D3) — image épinglée, montage
        # read-only, réseau none, pas de privileged, racine read-only.
        container_name = f"windflow-browse-{uuid4().hex[:8]}"
        container_id = await client.create_container(
            name=container_name,
            image=BROWSE_IMAGE,
            command=["sleep", "30"],
            network_mode="none",
            privileged=False,
            readonly_rootfs=True,
            mounts=[
                {
                    "type": "volume",
                    "source": name,
                    "destination": BROWSE_MOUNT_DESTINATION,
                    "mode": "ro",
                }
            ],
            labels={"windflow.transient": "true"},
        )
        try:
            await client.start_container(container_id)
            target = (
                f"{BROWSE_MOUNT_DESTINATION}/{subpath_clean}"
                if subpath_clean
                else BROWSE_MOUNT_DESTINATION
            )
            # Args liste — AUCUN shell, aucune concaténation vers le démon.
            result = await client.exec_in_container(container_id, ["ls", "-1p", target])
            if result.exit_code != 0:
                raise WindFlowException(
                    f"Impossible de lister le contenu du volume {name} "
                    f"(exit={result.exit_code})"
                )
            entries = _parse_ls_output(result.output, subpath_clean)
            return paginate_sequence(entries, page, per_page)
        finally:
            # Nettoyage garanti — même sur erreur d'exec (aucun orphelin).
            try:
                await client.remove_container(container_id, force=True)
            except Exception as exc:  # best-effort, déjà loggé
                logger.warning(
                    "browse_volume : conteneur éphémère %s non retiré (%s)",
                    container_name,
                    exc,
                )
    finally:
        await client.close()
