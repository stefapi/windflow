"""
Client Docker via API REST Engine v1.41+.

Connexion via Unix socket local (/var/run/docker.sock) avec aiohttp.
Toutes les opérations sont asynchrones et n'ont pas de dépendance externe.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, List, Optional

import aiohttp

from ..core.exceptions import WindFlowException

logger = logging.getLogger(__name__)

# Unix socket Docker par défaut
DEFAULT_DOCKER_SOCKET = "/var/run/docker.sock"

# Timeout par défaut pour les requêtes Docker (secondes)
DEFAULT_TIMEOUT = 30.0
STREAMING_TIMEOUT = 300.0  # 5 minutes pour les streams longs


# =============================================================================
# Schémas de données (dataclasses)
# =============================================================================


@dataclass
class ContainerInfo:
    """Informations de base sur un container (GET /containers/json)."""

    id: str
    name: str
    image: str
    image_id: str
    command: str
    created: datetime
    state: str  # running, exited, paused, restarting, removing, dead
    status: str  # "Up 2 hours", "Exited (0) 3 minutes ago"
    ports: list[dict[str, Any]]
    labels: dict[str, str]
    networks: list[str]
    mounts: list[dict[str, Any]]
    restart_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContainerInfo":
        """Parse la réponse Docker API."""
        # Extraction du nom (sans le / initial)
        names = data.get("Names", [])
        name = names[0].lstrip("/") if names else data.get("Id", "")[:12]

        # Parsing de la date de création (timestamp Unix)
        created_ts = data.get("Created", 0)
        created = datetime.fromtimestamp(created_ts)

        # Extraction des networks
        network_info = data.get("NetworkSettings", {}).get("Networks", {})
        networks = list(network_info.keys())

        return cls(
            id=data.get("Id", "")[:12],
            name=name,
            image=data.get("Image", ""),
            image_id=data.get("ImageID", ""),
            command=data.get("Command", ""),
            created=created,
            state=data.get("State", ""),
            status=data.get("Status", ""),
            ports=data.get("Ports", []),
            labels=data.get("Labels", {}),
            networks=networks,
            mounts=data.get("Mounts", []),
            restart_count=data.get("RestartCount", 0),
        )


@dataclass
class ContainerDetail:
    """Détails complets d'un container (GET /containers/{id}/json)."""

    id: str
    name: str
    created: datetime
    path: str
    args: list[str]
    state: dict[str, Any]
    image: str
    config: dict[str, Any]
    host_config: dict[str, Any]
    network_settings: dict[str, Any]
    mounts: list[dict[str, Any]]
    size_rw: Optional[int] = None
    size_root_fs: Optional[int] = None
    logs: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContainerDetail":
        created_str = data.get("Created", "")
        created = (
            datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            if created_str
            else datetime.now()
        )

        return cls(
            id=data.get("Id", "")[:12],
            name=data.get("Name", "").lstrip("/"),
            created=created,
            path=data.get("Path", ""),
            args=data.get("Args", []),
            state=data.get("State", {}),
            image=data.get("Config", {}).get("Image", ""),
            config=data.get("Config", {}),
            host_config=data.get("HostConfig", {}),
            network_settings=data.get("NetworkSettings", {}),
            mounts=data.get("Mounts", []),
            size_rw=data.get("SizeRw"),
            size_root_fs=data.get("SizeRootFs"),
        )


@dataclass
class ImageInfo:
    """Informations sur une image (GET /images/json)."""

    id: str
    repo_tags: list[str]
    repo_digests: list[str]
    created: datetime
    size: int
    virtual_size: int
    labels: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageInfo":
        created_ts = data.get("Created", 0)
        created = datetime.fromtimestamp(created_ts)

        # Parser la taille (peut être un int ou une string)
        size = data.get("Size", 0)
        if isinstance(size, str):
            size = int(size)

        virtual_size = data.get("VirtualSize", size)
        if isinstance(virtual_size, str):
            virtual_size = int(virtual_size)

        return cls(
            id=data.get("Id", "").replace("sha256:", "")[:12],
            repo_tags=data.get("RepoTags", []),
            repo_digests=data.get("RepoDigests", []),
            created=created,
            size=size,
            virtual_size=virtual_size,
            labels=data.get("Labels", {}),
        )


@dataclass
class VolumeInfo:
    """Informations sur un volume (GET /volumes)."""

    name: str
    driver: str
    mountpoint: str
    created_at: datetime
    labels: dict[str, str]
    scope: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VolumeInfo":
        created_at_str = data.get("CreatedAt", "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.now()

        return cls(
            name=data.get("Name", ""),
            driver=data.get("Driver", "local"),
            mountpoint=data.get("Mountpoint", ""),
            created_at=created_at,
            labels=data.get("Labels", {}),
            scope=data.get("Scope", "local"),
        )


@dataclass
class NetworkInfo:
    """Informations sur un réseau (GET /networks)."""

    id: str
    name: str
    driver: str
    scope: str
    internal: bool
    attachable: bool
    ingress: bool
    created: datetime
    subnet: str
    gateway: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkInfo":
        created_str = data.get("Created", "")
        try:
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created = datetime.now()

        # Extraction IPAM config
        ipam = data.get("IPAM", {}).get("Config", [{}])[0] if data.get("IPAM") else {}
        subnet = ipam.get("Subnet", "")
        gateway = ipam.get("Gateway", "")

        return cls(
            id=data.get("Id", ""),
            name=data.get("Name", ""),
            driver=data.get("Driver", ""),
            scope=data.get("Scope", ""),
            internal=data.get("Internal", False),
            attachable=data.get("Attachable", False),
            ingress=data.get("Ingress", False),
            created=created,
            subnet=subnet,
            gateway=gateway,
        )


@dataclass
class SystemInfo:
    """Informations système Docker (GET /info)."""

    id: str
    name: str
    server_version: str
    containers: int
    containers_running: int
    containers_paused: int
    containers_stopped: int
    images: int
    driver: str
    docker_root_dir: str
    kernel_version: str
    operating_system: str
    os_type: str
    architecture: str
    cpus: int
    memory: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemInfo":
        return cls(
            id=data.get("ID", ""),
            name=data.get("Name", ""),
            server_version=data.get("ServerVersion", ""),
            containers=data.get("Containers", 0),
            containers_running=data.get("ContainersRunning", 0),
            containers_paused=data.get("ContainersPaused", 0),
            containers_stopped=data.get("ContainersStopped", 0),
            images=data.get("Images", 0),
            driver=data.get("Driver", ""),
            docker_root_dir=data.get("DockerRootDir", ""),
            kernel_version=data.get("KernelVersion", ""),
            operating_system=data.get("OperatingSystem", ""),
            os_type=data.get("OSType", ""),
            architecture=data.get("Architecture", ""),
            cpus=data.get("NCPU", 0),
            memory=data.get("MemTotal", 0),
        )


@dataclass
class PullProgressEvent:
    """Événement de progression d'un pull d'image."""

    status: str  # "Pulling from library/nginx", "Downloading", "Download complete"
    progress: Optional[str] = None
    progress_detail: Optional[dict[str, Any]] = None
    id: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PullProgressEvent":
        return cls(
            status=data.get("status", ""),
            progress=data.get("progress"),
            progress_detail=data.get("progressDetail"),
            id=data.get("id"),
            error=data.get("error"),
        )


@dataclass
class ExecResult:
    """Résultat d'une commande exec dans un container."""

    exit_code: int
    output: str
    error: str


# Préfixe des ressources gérées par les plugins WindFlow — sémantique du
# prune protégé (STORY-173, consommé par STORY-160.3) : toute ressource
# nommée ``windflow-plugin-*`` est épargnée par construction, jamais
# candidate à un prune.
PROTECTED_RESOURCE_PREFIX = "windflow-plugin-"

# Bornage défensif du nombre d'éléments traités par un prune (anti-tempête
# sur un démon qui aurait des milliers de candidats).
PRUNE_MAX_ITEMS = 500


def is_protected_resource(name: str) -> bool:
    """Retourne ``True`` si la ressource est protégée (``windflow-plugin-*``)."""
    return name.startswith(PROTECTED_RESOURCE_PREFIX)


# =============================================================================
# Recreate sécurisé — helpers purs (STORY-174.2, spec 02 § Sémantique de mise
# à jour : rebase par valeur + secrets masqués `***`)
# =============================================================================

# Clé d'env/label d'aspect secret — masquée `***` dans les aperçus
# (spec 02 l.255, rules 40 : jamais de valeur réelle hors du backend).
SECRET_ENV_PATTERN = re.compile(r".*(PASSWORD|TOKEN|KEY|SECRET)$", re.IGNORECASE)

# Placeholder renvoyé au formulaire pour une valeur inchangée.
MASKED_VALUE = "***"


def _split_image_ref(ref: str) -> tuple:
    """Sépare ``image:tag`` pour ``pull_image(name, tag)`` (tag défaut latest)."""
    if ":" in ref and not ref.rstrip("/").split("/")[-1].startswith(":"):
        name, _, tag = ref.rpartition(":")
        # exclut les ports de registry (host:5000/img)
        if "/" not in tag:
            return name, tag
    return ref, "latest"


def mask_secret_env(values: List[str]) -> List[str]:
    """Masque en ``***`` les valeurs d'env dont la **clé** est sensible.

    S'applique aux aperçus d'inspection servis au client (spec 02 —
    l'utilisateur édite sans jamais réimporter les secrets). La clé
    matche si elle SE TERMINE par PASSWORD/TOKEN/KEY/SECRET
    (insensible à la casse) — ex. ``POSTGRES_PASSWORD``, ``API_TOKEN``,
    ``SSH_KEY``, ``CLIENT_SECRET``.
    """
    masked: List[str] = []
    for entry in values:
        key, sep, _value = entry.partition("=")
        if sep and SECRET_ENV_PATTERN.match(key):
            masked.append(f"{key}={MASKED_VALUE}")
        else:
            masked.append(entry)
    return masked


def resolve_masked_env(submitted: List[str], real: List[str]) -> List[str]:
    """Résout les placeholders ``***`` depuis les valeurs réelles du container.

    Le formulaire renvoie ``***`` pour les valeurs inchangées : avant la
    recréation, chaque placeholder est remplacé par la valeur réelle lue
    sur le container **courant** (jamais depuis la requête client — un
    attaquant ne peut pas injecter de valeur via le placeholder). Une
    clé soumise absente du réel est conservée telle quelle (ajout).
    """
    real_map = {e.partition("=")[0]: e for e in real if "=" in e}
    resolved: List[str] = []
    for entry in submitted:
        key, sep, value = entry.partition("=")
        if sep and value == MASKED_VALUE and key in real_map:
            resolved.append(real_map[key])
        else:
            resolved.append(entry)
    return resolved


def rebase_by_value(
    current: List[str],
    old_image: List[str],
    new_image: List[str],
) -> List[str]:
    """Rebase par valeur des variables d'env (spec 02 § mise à jour l.245-253).

    Règles (tableau spec 02) pour chaque clé de ``current`` :

    - valeur **identique** à celle de l'ancienne image → l'utilisateur
      ne l'a pas touchée → prend la valeur de la **nouvelle** image
      (et disparaît si la nouvelle image ne la définit plus) ;
    - valeur **différente** → choix explicite → **conservée** ;
    - **absente** de l'ancienne image → ajout utilisateur → **conservée**.
    """
    old_map = {e.partition("=")[0]: e.partition("=")[2] for e in old_image if "=" in e}
    new_map = {e.partition("=")[0]: e.partition("=")[2] for e in new_image if "=" in e}

    rebased: List[str] = []
    for entry in current:
        key, sep, value = entry.partition("=")
        if not sep:
            rebased.append(entry)
            continue
        if key not in old_map:
            rebased.append(entry)  # ajout utilisateur → conservé
        elif old_map[key] == value:
            # identique à l'ancienne image → suit la nouvelle
            if key in new_map:
                rebased.append(f"{key}={new_map[key]}")
            # absente de la nouvelle image → supprimée (« suit la nouvelle »)
        else:
            rebased.append(entry)  # modifiée → conservée
    return rebased


def rebase_labels_by_value(
    current: dict,
    old_image: dict,
    new_image: dict,
) -> dict:
    """Rebase par valeur des labels — mêmes règles que :func:`rebase_by_value`."""
    rebased: dict = {}
    for key, value in current.items():
        if key not in old_image:
            rebased[key] = value  # ajout utilisateur
        elif str(old_image[key]) == str(value):
            if key in new_image:  # suit la nouvelle image
                rebased[key] = new_image[key]
        else:
            rebased[key] = value  # modifiée → conservée
    return rebased


def rebase_command(
    current_cmd: Optional[List[str]],
    old_image_cmd: Optional[List[str]],
    new_image_cmd: Optional[List[str]],
) -> Optional[List[str]]:
    """Rebase de ``Cmd`` : la commande « cuite » suit l'image, la commande
    utilisateur survit (spec 02 l.253).

    - ``current`` identique à l'ancienne image → prend le ``Cmd`` de la
      nouvelle image (None si elle n'en définit plus) ;
    - ``current`` différent (command: utilisateur) → **conservé** ;
    - ``current`` None → Cmd de la nouvelle image.
    """
    if current_cmd is None:
        return list(new_image_cmd) if new_image_cmd else None
    if list(current_cmd) == list(old_image_cmd or []):
        return list(new_image_cmd) if new_image_cmd else None
    return list(current_cmd)


@dataclass
class PruneResult:
    """Résultat borné et typé d'un prune protégé (STORY-160.3/STORY-173).

    Attributes:
        resource: Ressource prunée — ``images`` | ``volumes`` |
            ``containers`` (STORY-173).
        dry_run: ``True`` si simple estimation (aucun appel suppressif).
        pruned_count: En dry-run : nombre de candidates estimées ; en
            exécution réelle : nombre d'éléments effectivement supprimés.
        space_reclaimed_bytes: Espace récupéré — exact pour les images
            (somme des tailles) ; ``0`` pour les volumes (la taille n'est
            pas exposée par le listage, limite documentée).
        spared_count: Nombre de ressources ``windflow-plugin-*`` épargnées.
        pruned_names: Noms des ressources supprimées (ou candidates en
            dry-run) — STORY-173, champs à défauts (compat ascendante
            STORY-160.3 : les consommateurs existants restent valides).
        spared_names: Noms des ressources protégées épargnées.
        failed_names: Noms des ressources dont la suppression unitaire a
            échoué — **la file n'est jamais interrompue** (un volume devenu
            utilisé entre la liste et la suppression est passé, AC 2).
        failed_count: Nombre d'échecs (miroir de ``len(failed_names)``).
    """

    resource: str
    dry_run: bool
    pruned_count: int
    space_reclaimed_bytes: int
    spared_count: int
    pruned_names: list[str] = field(default_factory=list)
    spared_names: list[str] = field(default_factory=list)
    failed_names: list[str] = field(default_factory=list)
    failed_count: int = 0


# =============================================================================
# Client Docker
# =============================================================================


class DockerClientService:
    """
    Client Docker via API REST Engine v1.41+.

    Connexion via Unix socket local. Toutes les méthodes sont async.

    Example:
        >>> client = DockerClientService()
        >>> containers = await client.list_containers()
        >>> for c in containers:
        ...     print(f"{c.name}: {c.state}")
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_DOCKER_SOCKET,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialise le client Docker.

        Args:
            socket_path: Chemin vers le socket Unix Docker
            timeout: Timeout par défaut pour les requêtes (secondes)
        """
        self.socket_path = socket_path
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Récupère ou crée la session HTTP avec connector Unix socket."""
        if self._session is None or self._session.closed:
            connector = aiohttp.UnixConnector(path=self.socket_path)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
            )
        return self._session

    async def close(self):
        """Ferme la session HTTP."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    def _sanitize_params(
        self, params: Optional[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """
        Convertit les valeurs de paramètres en types acceptés par aiohttp.

        aiohttp accepte uniquement str, int, float pour les valeurs de params.
        Les booléens doivent être convertis en strings.

        Args:
            params: Paramètres bruts

        Returns:
            Paramètres sanitizés
        """
        if params is None:
            return None

        sanitized: dict[str, str | int | float] = {}
        for key, value in params.items():
            if isinstance(value, bool):
                sanitized[key] = str(value).lower()  # True -> "true", False -> "false"
            elif isinstance(value, (str, int, float)):
                sanitized[key] = value
            elif isinstance(value, list):
                # Pour les listes (ex: filters), on les passe en JSON
                sanitized[key] = json.dumps(value)
            else:
                # Pour les autres types, on convertit en string
                sanitized[key] = str(value)

        return sanitized

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        stream: bool = False,
    ) -> aiohttp.ClientResponse:
        """
        Effectue une requête vers l'API Docker.

        Args:
            method: Méthode HTTP (GET, POST, DELETE, etc.)
            path: Chemin API (ex: /containers/json)
            params: Paramètres de query string
            body: Corps de la requête (JSON)
            headers: Headers additionnels
            timeout: Timeout spécifique (remplace le défaut)
            stream: True pour les réponses en streaming

        Returns:
            Réponse HTTP

        Raises:
            aiohttp.ClientResponseError: En cas d'erreur HTTP
        """
        session = await self._get_session()
        req_timeout = aiohttp.ClientTimeout(total=timeout or self.timeout)

        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        url = f"http://localhost{path}"

        logger.debug(f"Docker API: {method} {path}")

        # Sanitize params pour éviter les erreurs de type
        sanitized_params = self._sanitize_params(params)

        if stream:
            # Pour le streaming, on retourne la réponse directement
            response = await session.request(
                method=method,
                url=url,
                params=sanitized_params,
                json=body if body else None,
                headers=req_headers,
                timeout=req_timeout,
            )
            response.raise_for_status()
            return response
        else:
            response = await session.request(
                method=method,
                url=url,
                params=sanitized_params,
                json=body if body else None,
                headers=req_headers,
                timeout=req_timeout,
            )
            response.raise_for_status()
            return response

    # =========================================================================
    # Containers
    # =========================================================================

    async def list_containers(
        self,
        all: bool = True,
        since: Optional[str] = None,
        before: Optional[str] = None,
        limit: Optional[int] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[ContainerInfo]:
        """
        Liste les containers.

        GET /containers/json

        Args:
            all: Inclure les containers arrêtés
            since: Containers créés après cet ID
            before: Containers créés avant cet ID
            limit: Nombre maximum de containers
            filters: Filtres (ex: {"status": ["running"]})

        Returns:
            Liste de ContainerInfo
        """
        params: dict[str, Any] = {"all": all}

        if since:
            params["since"] = since
        if before:
            params["before"] = before
        if limit:
            params["limit"] = limit
        if filters:
            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/containers/json", params=params)
        data = await response.json()

        return [ContainerInfo.from_dict(c) for c in data]

    async def get_container(self, container_id: str) -> ContainerDetail:
        """
        Récupère les détails d'un container.

        GET /containers/{id}/json

        Args:
            container_id: ID ou nom du container

        Returns:
            ContainerDetail
        """
        response = await self._request("GET", f"/containers/{container_id}/json")
        data = await response.json()
        return ContainerDetail.from_dict(data)

    async def create_container(
        self,
        name: str,
        image: str,
        command: Optional[list[str]] = None,
        env: Optional[list[str]] = None,
        ports: Optional[dict[str, dict[str, Any]]] = None,
        volumes: Optional[dict[str, dict[str, Any]]] = None,
        labels: Optional[dict[str, str]] = None,
        restart_policy: str = "no",
        network_mode: str = "bridge",
        privileged: bool = False,
        mounts: Optional[list[dict[str, Any]]] = None,
        cap_add: Optional[list[str]] = None,
        cap_drop: Optional[list[str]] = None,
        readonly_rootfs: Optional[bool] = None,
        port_bindings: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Crée un container sans le démarrer.

        POST /containers/create

        Args:
            name: Nom du container
            image: Image Docker à utiliser
            command: Commande à exécuter
            env: Variables d'environnement (format ["KEY=value"])
            ports: Ports à exposer ({"container_port": {"HostPort": "host_port"}})
            volumes: Volumes à monter
            labels: Labels du container
            restart_policy: Politique de redémarrage (no, always, unless-stopped, on-failure)
            network_mode: Mode réseau (bridge, host, none)
            privileged: Mode privilégié
            mounts: Points de montage au format abstrait
                (ex: {"type": "bind", "source": "/host", "destination": "/container", "mode": "rw"})
            cap_add: Capabilities Linux à ajouter (ex: ["NET_ADMIN", "SYS_PTRACE"])
            cap_drop: Capabilities Linux à retirer
            readonly_rootfs: Système de fichiers racine en lecture seule
            port_bindings: Bindings de ports au format Docker
                (ex: {"80/tcp": [{"HostPort": "8080"}]})

        Returns:
            Container ID
        """
        config: dict[str, Any] = {
            "Image": image,
            "Labels": labels or {},
            "Env": env or [],
            "Cmd": command,
            "HostConfig": {
                "RestartPolicy": {"Name": restart_policy},
                "NetworkMode": network_mode,
                "Privileged": privileged,
            },
        }

        # Ajouter les ports (format simplifié)
        if ports:
            config["ExposedPorts"] = {}
            config["HostConfig"]["PortBindings"] = {}
            for container_port, host_config in ports.items():
                config["ExposedPorts"][container_port] = {}
                config["HostConfig"]["PortBindings"][container_port] = [host_config]

        # Ajouter les port_bindings (format Docker natif)
        if port_bindings:
            if "ExposedPorts" not in config:
                config["ExposedPorts"] = {}
            config["HostConfig"]["PortBindings"] = port_bindings
            for port_spec in port_bindings:
                config["ExposedPorts"][port_spec] = {}

        # Ajouter les volumes (format simplifié)
        if volumes:
            config["Volumes"] = volumes
            config["HostConfig"]["Binds"] = [
                f"{host}:{container}" for host, container in volumes.items()
            ]

        # Ajouter les mounts (format abstrait)
        if mounts:
            docker_mounts: list[dict[str, Any]] = []
            bind_list: list[str] = []
            for m in mounts:
                docker_mounts.append(
                    {
                        "Type": m.get("type", "bind"),
                        "Source": m.get("source", ""),
                        "Target": m.get("destination", ""),
                        "ReadOnly": m.get("mode", "rw") == "ro",
                    }
                )
                if m.get("type", "bind") == "bind":
                    mode = m.get("mode", "rw")
                    bind_list.append(
                        f"{m.get('source', '')}:{m.get('destination', '')}:{mode}"
                    )
            config["HostConfig"]["Mounts"] = docker_mounts
            if bind_list:
                existing_binds = config["HostConfig"].get("Binds", [])
                config["HostConfig"]["Binds"] = existing_binds + bind_list

        # Ajouter les capabilities
        if cap_add:
            config["HostConfig"]["CapAdd"] = cap_add
        if cap_drop:
            config["HostConfig"]["CapDrop"] = cap_drop

        # Readonly rootfs
        if readonly_rootfs is not None:
            config["HostConfig"]["ReadonlyRootfs"] = readonly_rootfs

        response = await self._request(
            "POST",
            f"/containers/create?name={name}",
            body=config,
            timeout=60.0,
        )
        data = await response.json()
        return data.get("Id", "")

    async def recreate_container_secure(
        self,
        container_id: str,
        image: Optional[str] = None,
        pull_image: bool = False,
        env: Optional[List[str]] = None,
        labels: Optional[dict] = None,
        port_bindings: Optional[dict] = None,
        mounts: Optional[List[dict]] = None,
        privileged: Optional[bool] = None,
        readonly_rootfs: Optional[bool] = None,
        cap_add: Optional[List[str]] = None,
        cap_drop: Optional[List[str]] = None,
        stop_timeout: int = 10,
    ) -> tuple[str, "ContainerDetail"]:
        """Recrée un container — **recreate sécurisé** (STORY-174.2, spec 02).

        Orchestration 6 étapes (spec 02 § Sémantique de mise à jour) :

        1. **capture** de l'inspection container + de l'ancienne image
           (**avant** tout pull — après un pull l'ancien tag peut être
           détagué) ;
        2. pull de la nouvelle image si demandé — un échec de pull lève
           (l'ancien container est intact, jamais de pull avalé) ;
        3. arrêt (si running), **renommage** ``<nom>-old``, déconnexion
           des réseaux additionnels (libère nom + IP statiques) ;
        4. création du nouveau container : passthrough de l'inspection,
           image remplacée, **rebase par valeur** env/labels/cmd + les
           placeholders secrets ``***`` résolus depuis le container
           courant ; reconnexion des réseaux (Aliases/IPAMConfig
           restaurés) ; démarrage si l'ancien tournait ;
        5. suppression de l'ancien container (``force=False``,
           volumes préservés) ;
        6. **rollback automatique** sur échec de création/démarrage :
           le nouveau est retiré, l'ancien renommé restauré, réseaux
           reconnectés, redémarré si besoin — ``WindFlowException`` au
           retour (``recreate_failed_rolled_back`` ou
           ``recreate_rollback_incomplete`` si le rollback échoue aussi).

        Les valeurs d'env ne sont **jamais loggées** (rules 40).

        Args:
            container_id: Container à recréer (ID ou nom).
            image: Nouvelle image (None = conserver l'actuelle).
            pull_image: Tirer la nouvelle image avant recréation.
            env: Env de remplacement (``None`` = rebase de l'actuel ;
                les valeurs ``***`` sont résolues depuis le container).
            labels: Labels de remplacement (None = rebase).
            stop_timeout: Timeout d'arrêt (secondes).

        Returns:
            ``(new_id, ContainerDetail)`` du nouveau container.

        Raises:
            WindFlowException: Container introuvable, pull échoué,
                ou recréation échouée (rollback opéré).
        """
        # ── Étape 1 : capture AVANT pull ──────────────────────────
        detail = await self.get_container(container_id)
        container_name = detail.name.lstrip("/")
        old_image_ref = detail.config.get("Image", "")
        try:
            old_image_info = await self.inspect_image(old_image_ref)
        except Exception:
            old_image_info = {}  # image absente localement : rebase dégradé
        old_image_env = old_image_info.get("Config", {}).get("Env") or []
        old_image_labels = old_image_info.get("Config", {}).get("Labels") or {}
        old_image_cmd = old_image_info.get("Config", {}).get("Cmd")

        was_running = bool(detail.state.get("Running"))

        # ── Étape 2 : pull (échec → exception, ancien intact) ──────
        new_image_ref = image if image is not None else old_image_ref
        if pull_image and new_image_ref:
            try:
                await self.pull_image(*_split_image_ref(new_image_ref))
            except Exception as exc:
                raise WindFlowException(
                    f"Pull de {new_image_ref} échoué — recreate annulé, "
                    f"le container original est intact : {exc}"
                ) from exc
        try:
            new_image_info = await self.inspect_image(new_image_ref)
        except Exception:
            new_image_info = {}
        new_image_env = new_image_info.get("Config", {}).get("Env") or []
        new_image_labels = new_image_info.get("Config", {}).get("Labels") or {}
        new_image_cmd = new_image_info.get("Config", {}).get("Cmd")

        # ── Rebase + résolution des secrets `***` ─────────────────
        current_env = detail.config.get("Env") or []
        current_labels = detail.config.get("Labels") or {}
        current_cmd = detail.config.get("Cmd")

        effective_env = (
            resolve_masked_env(env, current_env) if env is not None else current_env
        )
        rebased_env = rebase_by_value(effective_env, old_image_env, new_image_env)
        effective_labels = labels if labels is not None else current_labels
        rebased_labels = rebase_labels_by_value(
            effective_labels, old_image_labels, new_image_labels
        )
        rebased_cmd = rebase_command(current_cmd, old_image_cmd, new_image_cmd)

        # ── Capture des réseaux additionnels (avant déconnexion) ──
        networks = detail.network_settings.get("Networks", {}) or {}
        primary_network = detail.host_config.get("NetworkMode", "bridge")
        extra_networks: List[dict] = []
        for net_name, net_cfg in networks.items():
            if net_name == primary_network:
                continue
            extra_networks.append(
                {
                    "name": net_name,
                    "aliases": net_cfg.get("Aliases") or [],
                    "ipv4": (net_cfg.get("IPAMConfig") or {}).get("IPv4Address"),
                }
            )

        # ── Étape 3 : arrêt + renommage -old + déconnexion ────────
        if was_running:
            try:
                await self.stop_container(container_id, timeout=stop_timeout)
            except Exception:
                pass  # déjà arrêté
        old_name = f"{container_name}-old"
        await self.rename_container(container_id, old_name)
        for net in extra_networks:
            try:
                await self.disconnect_container_from_network(net["name"], container_id)
            except Exception as exc:
                logger.warning(
                    "recreate_secure: déconnexion %s/%s impossible (%s) — continu",
                    container_id[:12],
                    net["name"],
                    exc,
                )

        # ── Étapes 4-6 : create → start → cleanup, avec rollback ──
        new_id: Optional[str] = None
        try:
            merged_mounts = (
                mounts
                if mounts is not None
                else (
                    [
                        {
                            "type": m.get("Type", "bind"),
                            "source": m.get("Source", ""),
                            "destination": m.get("Destination", ""),
                            "mode": m.get("Mode", "rw"),
                        }
                        for m in (detail.mounts or [])
                    ]
                    or None
                )
            )
            new_id = await self.create_container(
                name=container_name,
                image=new_image_ref,
                command=rebased_cmd,
                env=rebased_env,
                labels=rebased_labels,
                restart_policy=(
                    detail.host_config.get("RestartPolicy", {}).get("Name", "no")
                    if isinstance(detail.host_config.get("RestartPolicy"), dict)
                    else "no"
                ),
                network_mode=primary_network,
                privileged=(
                    privileged
                    if privileged is not None
                    else detail.host_config.get("Privileged", False)
                ),
                mounts=merged_mounts,
                cap_add=(
                    cap_add if cap_add is not None else detail.host_config.get("CapAdd")
                ),
                cap_drop=(
                    cap_drop
                    if cap_drop is not None
                    else detail.host_config.get("CapDrop")
                ),
                readonly_rootfs=(
                    readonly_rootfs
                    if readonly_rootfs is not None
                    else detail.host_config.get("ReadonlyRootfs")
                ),
                port_bindings=(
                    port_bindings
                    if port_bindings is not None
                    else detail.host_config.get("PortBindings")
                ),
            )
            for net in extra_networks:
                connect_kwargs: dict = {}
                if net["aliases"]:
                    connect_kwargs["aliases"] = net["aliases"]
                if net["ipv4"]:
                    connect_kwargs["ipv4_address"] = net["ipv4"]
                try:
                    await self.connect_container_to_network(
                        net["name"], new_id, **connect_kwargs
                    )
                except Exception as exc:
                    logger.warning(
                        "recreate_secure: reconnexion %s→%s impossible (%s)",
                        container_name,
                        net["name"],
                        exc,
                    )
            if was_running:
                await self.start_container(new_id)

            # Étape 5 : succès — suppression de l'ancien (volumes gardés)
            await self.remove_container(container_id, force=False, remove_volumes=False)
        except Exception as exc:
            rollback_ok = await self._rollback_recreate(
                new_id=new_id,
                old_container_id=container_id,
                old_name=old_name,
                original_name=container_name,
                extra_networks=extra_networks,
                was_running=was_running,
            )
            if rollback_ok:
                raise WindFlowException(
                    f"recreate_failed_rolled_back : la recréation de "
                    f"{container_name} a échoué ({exc}) — l'ancien container "
                    "a été restauré"
                ) from exc
            raise WindFlowException(
                f"recreate_rollback_incomplete : la recréation de "
                f"{container_name} a échoué ({exc}) ET le rollback n'a pas "
                "pu compléter — intervention manuelle requise"
            ) from exc

        new_detail = await self.get_container(new_id)
        logger.info(
            "recreate_secure : %s recréé en %s (image %s, %d réseaux "
            "additionnels reconnectés)",
            container_name,
            new_id[:12],
            new_image_ref,
            len(extra_networks),
        )
        return new_id, new_detail

    async def _rollback_recreate(
        self,
        new_id: Optional[str],
        old_container_id: str,
        old_name: str,
        original_name: str,
        extra_networks: List[dict],
        was_running: bool,
    ) -> bool:
        """Rollback best-effort du recreate sécurisé (étape 6 — spec 02).

        Retourne ``True`` si le rollback a completé (ancien restauré),
        ``False`` s'il a lui-même échoué partiellement.
        """
        rollback_failed = False
        if new_id:
            try:
                await self.remove_container(new_id, force=True, remove_volumes=False)
            except Exception as exc:
                logger.critical(
                    "recreate_secure rollback : nouveau container %s non "
                    "retirable (%s)",
                    new_id[:12],
                    exc,
                )
                rollback_failed = True
        try:
            await self.rename_container(old_container_id, original_name)
        except Exception as exc:
            logger.critical(
                "recreate_secure rollback : renommage %s→%s impossible (%s)",
                old_name,
                original_name,
                exc,
            )
            rollback_failed = True
        for net in extra_networks:
            try:
                connect_kwargs: dict = {}
                if net["aliases"]:
                    connect_kwargs["aliases"] = net["aliases"]
                if net["ipv4"]:
                    connect_kwargs["ipv4_address"] = net["ipv4"]
                await self.connect_container_to_network(
                    net["name"], old_container_id, **connect_kwargs
                )
            except Exception as exc:
                logger.critical(
                    "recreate_secure rollback : reconnexion %s→%s impossible (%s)",
                    original_name,
                    net["name"],
                    exc,
                )
                rollback_failed = True
        if was_running:
            try:
                await self.start_container(old_container_id)
            except Exception as exc:
                logger.critical(
                    "recreate_secure rollback : redémarrage de %s impossible (%s)",
                    original_name,
                    exc,
                )
                rollback_failed = True
        return not rollback_failed

    async def start_container(self, container_id: str) -> None:
        """
        Démarre un container.

        POST /containers/{id}/start

        Args:
            container_id: ID ou nom du container
        """
        await self._request("POST", f"/containers/{container_id}/start", timeout=60.0)

    async def stop_container(
        self,
        container_id: str,
        timeout: int = 10,
    ) -> None:
        """
        Arrête un container.

        POST /containers/{id}/stop

        Args:
            container_id: ID ou nom du container
            timeout: Timeout avant kill forcé (secondes)
        """
        await self._request(
            "POST",
            f"/containers/{container_id}/stop",
            params={"t": timeout},
            timeout=timeout + 5,
        )

    async def restart_container(
        self,
        container_id: str,
        timeout: int = 10,
    ) -> None:
        """
        Redémarre un container.

        POST /containers/{id}/restart

        Args:
            container_id: ID ou nom du container
            timeout: Timeout avant kill forcé (secondes)
        """
        await self._request(
            "POST",
            f"/containers/{container_id}/restart",
            params={"t": timeout},
            timeout=timeout + 5,
        )

    async def pause_container(self, container_id: str) -> None:
        """
        Met en pause un container.

        POST /containers/{id}/pause

        Args:
            container_id: ID ou nom du container
        """
        await self._request("POST", f"/containers/{container_id}/pause")

    async def unpause_container(self, container_id: str) -> None:
        """
        Reprend un container en pause.

        POST /containers/{id}/unpause

        Args:
            container_id: ID ou nom du container
        """
        await self._request("POST", f"/containers/{container_id}/unpause")

    async def remove_container(
        self,
        container_id: str,
        force: bool = False,
        remove_volumes: bool = False,
    ) -> None:
        """
        Supprime un container.

        DELETE /containers/{id}

        Args:
            container_id: ID ou nom du container
            force: Forcer la suppression si running
            remove_volumes: Supprimer les volumes associés
        """
        params: dict[str, Any] = {"force": force, "v": remove_volumes}
        await self._request(
            "DELETE",
            f"/containers/{container_id}",
            params=params,
            timeout=30.0,
        )

    async def update_container(
        self, container_id: str, update_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Met à jour la configuration d'un container sans recréation.

        POST /containers/{id}/update

        Args:
            container_id: ID ou nom du container
            update_config: Configuration Docker à appliquer
                (RestartPolicy, Resources, etc.)

        Returns:
            Dict avec clés potentielles : "Warnings"
        """
        response = await self._request(
            "POST",
            f"/containers/{container_id}/update",
            body=update_config,
        )
        return await response.json()

    async def rename_container(self, container_id: str, new_name: str) -> None:
        """
        Renomme un container.

        POST /containers/{id}/rename?name=new_name

        Args:
            container_id: ID ou nom du container
            new_name: Nouveau nom du container
        """
        await self._request(
            "POST",
            f"/containers/{container_id}/rename",
            params={"name": new_name},
        )

    async def container_logs(
        self,
        container_id: str,
        tail: int = 100,
        timestamps: bool = False,
        since: Optional[int] = None,
        until: Optional[int] = None,
        follow: bool = False,
    ) -> AsyncIterator[str]:
        """
        Récupère les logs d'un container.

        GET /containers/{id}/logs

        Args:
            container_id: ID ou nom du container
            tail: Nombre de lignes depuis la fin
            timestamps: Inclure les timestamps
            since: Timestamps depuis (secondes depuis epoch)
            until: Timestamps jusqu'à (secondes depuis epoch)
            follow: Streaming en temps réel

        Yields:
            Lignes de logs (démultiplexées stdout/stderr)
        """
        params: dict[str, Any] = {
            "stdout": True,
            "stderr": True,
            "tail": tail,
            "timestamps": timestamps,
            "follow": follow,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        timeout = STREAMING_TIMEOUT if follow else self.timeout

        response = await self._request(
            "GET",
            f"/containers/{container_id}/logs",
            params=params,
            stream=True,
            timeout=timeout,
        )

        try:
            async for chunk in response.content.iter_any():
                # Démultiplexer le stream Docker
                lines = self._demux_docker_stream(chunk)
                for line in lines:
                    yield line
        finally:
            # Fermer la réponse proprement
            response.close()

    def _demux_docker_stream(self, chunk: bytes) -> list[str]:
        """
        Démultiplexe un stream Docker multiplexé.

        Le protocole Docker utilise un header de 8 bytes par frame:
        - Byte 0: type (1=stdout, 2=stderr)
        - Bytes 1-3: reserved
        - Bytes 4-7: taille du frame (big endian)

        Args:
            chunk: Données brutes du stream

        Returns:
            Liste de lignes (stdout et stderr avec préfixe [ERR] pour stderr)
        """
        lines = []
        offset = 0

        while offset < len(chunk):
            if offset + 8 > len(chunk):
                break

            # Parser le header
            stream_type = chunk[offset]
            frame_size = int.from_bytes(chunk[offset + 4 : offset + 8], "big")

            if frame_size == 0 or offset + 8 + frame_size > len(chunk):
                # Frame invalide, retour au parsing ligne par ligne
                remaining = chunk[offset:].decode("utf-8", errors="replace")
                if remaining:
                    lines.extend(remaining.split("\n"))
                break

            # Extraire le payload (stdout et stderr)
            payload = chunk[offset + 8 : offset + 8 + frame_size]
            line = payload.decode("utf-8", errors="replace").rstrip("\n")
            if line:
                if stream_type == 2:  # stderr
                    lines.append(f"[ERR] {line}")
                else:  # stdout (stream_type == 1)
                    lines.append(line)

            offset += 8 + frame_size

        return lines

    async def inspect_container(self, container_id: str) -> dict[str, Any]:
        """
        Inspecte un container (état détaillé).

        GET /containers/{id}/json

        Args:
            container_id: ID ou nom du container

        Returns:
            Détails complets du container
        """
        response = await self._request("GET", f"/containers/{container_id}/json")
        return await response.json()

    async def list_processes(
        self,
        container_id: str,
        ps_args: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Liste les processus d'un container.

        GET /containers/{id}/top

        Args:
            container_id: ID ou nom du container
            ps_args: Arguments pour ps (ex: "aux")

        Returns:
            Dict avec 'Titles' et 'Processes'
        """
        params = {}
        if ps_args:
            params["ps_args"] = ps_args

        response = await self._request(
            "GET",
            f"/containers/{container_id}/top",
            params=params,
        )
        return await response.json()

    async def container_stats(
        self,
        container_id: str,
        stream: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Récupère les statistiques d'un container.

        GET /containers/{id}/stats

        Args:
            container_id: ID ou nom du container
            stream: Streaming des stats

        Yields:
            Statistiques à chaque intervalle
        """
        params = {"stream": stream}

        response = await self._request(
            "GET",
            f"/containers/{container_id}/stats",
            params=params,
            stream=True,
            timeout=STREAMING_TIMEOUT if stream else self.timeout,
        )

        try:
            async for line in response.content:
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass
        finally:
            response.close()

    # =========================================================================
    # Images
    # =========================================================================

    async def list_images(
        self,
        all: bool = False,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[ImageInfo]:
        """
        Liste les images.

        GET /images/json

        Args:
            all: Inclure les images intermédiaires
            filters: Filtres

        Returns:
            Liste de ImageInfo
        """
        params: dict[str, Any] = {"all": all}
        if filters:
            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/images/json", params=params)
        data = await response.json()

        return [ImageInfo.from_dict(img) for img in data]

    async def pull_image(
        self,
        name: str,
        tag: str = "latest",
        on_progress: Optional[Callable[[PullProgressEvent], None]] = None,
    ) -> str:
        """
        Pull une image depuis un registry.

        POST /images/create

        Args:
            name: Nom de l'image
            tag: Tag de l'image
            on_progress: Callback pour la progression

        Returns:
            Status de l'opération
        """
        params = {"fromImage": name, "tag": tag}

        response = await self._request(
            "POST",
            "/images/create",
            params=params,
            stream=True,
            timeout=STREAMING_TIMEOUT,
        )

        # Parser le stream JSON ligne par ligne
        full_status = ""

        try:
            async for line in response.content:
                if line:
                    try:
                        event_data = json.loads(line)
                        event = PullProgressEvent.from_dict(event_data)

                        if on_progress:
                            on_progress(event)

                        # Garder le dernier status
                        if event.status:
                            full_status = event.status

                        # Vérifier les erreurs
                        if event.error:
                            raise Exception(f"Pull failed: {event.error}")

                    except json.JSONDecodeError:
                        pass
        finally:
            response.close()

        return full_status or "Pull complete"

    async def remove_image(
        self,
        image_id: str,
        force: bool = False,
        no_prune: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Supprime une image.

        DELETE /images/{name}

        Args:
            image_id: ID ou nom de l'image
            force: Forcer la suppression
            no_prune: Ne pas supprimer les parents non-tagués

        Returns:
            Liste des images supprimées
        """
        params = {"force": force, "noprune": no_prune}

        response = await self._request(
            "DELETE",
            f"/images/{image_id}",
            params=params,
            timeout=60.0,
        )

        return await response.json()

    async def inspect_image(self, image_id: str) -> dict[str, Any]:
        """
        Inspecte une image.

        GET /images/{name}/json

        Args:
            image_id: ID ou nom de l'image

        Returns:
            Détails de l'image
        """
        response = await self._request("GET", f"/images/{image_id}/json")
        return await response.json()

    async def save_image(self, image_id: str) -> bytes:
        """
        Exporte une image au format tar.

        GET /images/{name}/get

        Args:
            image_id: ID ou nom de l'image

        Returns:
            Contenu binaire du tar de l'image
        """
        response = await self._request(
            "GET",
            f"/images/{image_id}/get",
            timeout=300.0,
        )
        return await response.read()

    async def load_image(self, tar_bytes: bytes) -> str:
        """
        Importe une image depuis un fichier tar.

        POST /images/load

        Args:
            tar_bytes: Contenu binaire du tar de l'image

        Returns:
            Message de statut de l'import
        """
        session = await self._get_session()
        req_timeout = aiohttp.ClientTimeout(total=300)

        response = await session.post(
            url="http://localhost/images/load",
            data=tar_bytes,
            headers={"Content-Type": "application/x-tar"},
            timeout=req_timeout,
        )
        response.raise_for_status()

        # Docker renvoie du JSON ligne par ligne
        full_status = "Load complete"
        async for line in response.content:
            if line:
                try:
                    event = json.loads(line)
                    if "status" in event:
                        full_status = event["status"]
                    if "error" in event:
                        raise Exception(f"Load failed: {event['error']}")
                except json.JSONDecodeError:
                    pass

        await response.release()
        return full_status

    # =========================================================================
    # Volumes
    # =========================================================================

    async def list_volumes(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[VolumeInfo]:
        """
        Liste les volumes.

        GET /volumes

        Args:
            filters: Filtres

        Returns:
            Liste de VolumeInfo
        """
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/volumes", params=params)
        data = await response.json()

        volumes = data.get("Volumes", [])
        return [VolumeInfo.from_dict(v) for v in volumes]

    async def create_volume(
        self,
        name: str,
        driver: str = "local",
        labels: Optional[dict[str, str]] = None,
    ) -> VolumeInfo:
        """
        Crée un volume.

        POST /volumes/create

        Args:
            name: Nom du volume
            driver: Driver de stockage
            labels: Labels

        Returns:
            VolumeInfo
        """
        body = {"Name": name, "Driver": driver, "Labels": labels or {}}

        response = await self._request("POST", "/volumes/create", body=body)
        data = await response.json()

        return VolumeInfo.from_dict(data)

    async def remove_volume(
        self,
        name: str,
        force: bool = False,
    ) -> None:
        """
        Supprime un volume.

        DELETE /volumes/{name}

        Args:
            name: Nom du volume
            force: Forcer si attaché
        """
        params = {"force": force}
        await self._request("DELETE", f"/volumes/{name}", params=params)

    # -------------------------------------------------------------------------
    # Prune protégé (STORY-160.3 — sémantique STORY-173)
    # -------------------------------------------------------------------------

    async def prune_images(
        self, *, dry_run: bool = True, force: bool = False
    ) -> PruneResult:
        """Prune des images Docker non utilisées, protégé ``windflow-plugin-*``.

        Sémantique protégée spec 09 § Images / § Prune (STORY-173) :
        candidates = images ``dangling`` (non taguées) retournées par le
        filtre de l'API Engine. La liste protégée est épargnée **par
        construction** : toute image portant un tag ``windflow-plugin-*``
        n'est jamais candidate, même dangling.

        La suppression est **unitaire** : un échec (409/500 du démon)
        n'interrompt jamais la file — l'image est passée en échec et la
        suite est traitée (STORY-173, AC 2).

        Args:
            dry_run: ``True`` (défaut) : estimation via listage, **aucun
                appel suppressif** ; ``False`` : suppression effective des
                candidates une à une (``DELETE /images/{id}``).
            force: Force la suppression (n'affecte pas la liste protégée).

        Returns:
            Résultat borné et typé (comptages, noms, échecs, espace) —
            jamais de payload brut du démon.
        """
        images = await self.list_images(all=False, filters={"dangling": ["true"]})
        candidates = [
            img for img in images[:PRUNE_MAX_ITEMS] if not self._image_is_protected(img)
        ]
        spared_imgs = [img for img in images if self._image_is_protected(img)]
        spared_names = [tag for img in spared_imgs for tag in (img.repo_tags or [])][
            :PRUNE_MAX_ITEMS
        ]
        if dry_run:
            return PruneResult(
                resource="images",
                dry_run=True,
                pruned_count=len(candidates),
                space_reclaimed_bytes=sum(img.size for img in candidates),
                spared_count=len(spared_imgs),
                pruned_names=[img.id for img in candidates],
                spared_names=spared_names,
                failed_names=[],
                failed_count=0,
            )
        pruned = 0
        reclaimed = 0
        pruned_names: list[str] = []
        failed_names: list[str] = []
        for img in candidates:
            try:
                await self.remove_image(img.id, force=force, no_prune=True)
            except Exception as exc:  # échec isolé : la file continue (AC 2)
                logger.warning(
                    "prune_images : image %s non supprimée (%s) — file continuée",
                    img.id,
                    exc,
                )
                failed_names.append(img.id)
                continue
            pruned += 1
            reclaimed += img.size
            pruned_names.append(img.id)
        return PruneResult(
            resource="images",
            dry_run=False,
            pruned_count=pruned,
            space_reclaimed_bytes=reclaimed,
            spared_count=len(spared_imgs),
            pruned_names=pruned_names,
            spared_names=spared_names,
            failed_names=failed_names,
            failed_count=len(failed_names),
        )

    async def prune_volumes(
        self, *, dry_run: bool = True, force: bool = False
    ) -> PruneResult:
        """Prune des volumes orphelins, protégé ``windflow-plugin-*``.

        Sémantique protégée spec 09 § Prune des volumes (STORY-173) :

        - **inutilisé = sans aucun utilisateur, y compris un container
          arrêté** — la carte des montages est construite via
          ``list_containers(all=True)`` (le filtre ``dangling`` de
          l'endpoint volumes n'apparaît qu'à partir de l'API Engine 1.42,
          non garanti ici) ;
        - la liste protégée ``windflow-plugin-*`` est épargnée **par
          construction** (préfixe de nom) ;
        - la suppression est **unitaire, sans force** — un volume devenu
          utilisé entre la liste et la suppression échoue et est
          **passé** (409 du démon), la file n'est jamais interrompue.

        Args:
            dry_run: ``True`` (défaut) : estimation via listage, **aucun
                appel suppressif** ; ``False`` : suppression effective des
                candidates une à une (``DELETE /volumes/{name}``).
            force: Force la suppression (n'affecte pas la liste protégée).

        Returns:
            Résultat borné et typé ; ``space_reclaimed_bytes=0`` — la
            taille d'un volume n'est pas exposée par le listage (limite
            documentée de l'API Docker, **aucune valeur fabriquée**).
        """
        volumes = await self.list_volumes()
        in_use = await self._volume_names_in_use()
        candidates = [
            v
            for v in volumes[:PRUNE_MAX_ITEMS]
            if not is_protected_resource(v.name) and v.name not in in_use
        ]
        spared_names = [
            v.name
            for v in volumes
            if is_protected_resource(v.name)  # épargnés par construction
        ][:PRUNE_MAX_ITEMS]
        if dry_run:
            return PruneResult(
                resource="volumes",
                dry_run=True,
                pruned_count=len(candidates),
                space_reclaimed_bytes=0,
                spared_count=len(spared_names),
                pruned_names=[v.name for v in candidates],
                spared_names=spared_names,
                failed_names=[],
                failed_count=0,
            )
        pruned_names: list[str] = []
        failed_names: list[str] = []
        for v in candidates:
            try:
                await self.remove_volume(v.name, force=force)
            except Exception as exc:  # échec isolé : la file continue (AC 2)
                logger.warning(
                    "prune_volumes : volume %s non supprimé (%s) — file continuée",
                    v.name,
                    exc,
                )
                failed_names.append(v.name)
                continue
            pruned_names.append(v.name)
        return PruneResult(
            resource="volumes",
            dry_run=False,
            pruned_count=len(pruned_names),
            space_reclaimed_bytes=0,
            spared_count=len(spared_names),
            pruned_names=pruned_names,
            spared_names=spared_names,
            failed_names=failed_names,
            failed_count=len(failed_names),
        )

    async def prune_stopped_containers(
        self, *, dry_run: bool = True, force: bool = False
    ) -> PruneResult:
        """Prune des containers stoppés non managés, protégé plugins (STORY-173).

        Sémantique (spec 09 § Prune + décision D6) :

        - candidates = containers avec ``state != "running"`` **sans label
          ``windflow.managed=true``** — une stack WindFlow arrêtée n'est
          pas du déchet (décision propre à WindFlow) ;
        - les ressources ``windflow-plugin-*`` sont épargnées (nom ou
          label ``com.docker.compose.project`` — services plugins) ;
        - suppression **unitaire** ``force=False`` par défaut et **jamais
          ``remove_volumes=True``** (les volumes associés ne sont jamais
          emportés par un prune de containers) ;
        - un échec isolé n'interrompt pas la file.

        Args:
            dry_run: ``True`` (défaut) : estimation via listage, **aucun
                appel suppressif** ; ``False`` : suppression effective.
            force: Force la suppression des containers récalcitrants
                (n'affecte ni la liste protégée ni les volumes).

        Returns:
            Résultat borné et typé ; ``space_reclaimed_bytes=0`` (taille
            non exposée par le listage — aucune valeur fabriquée).
        """
        containers = await self.list_containers(all=True)
        candidates = [
            c
            for c in containers[:PRUNE_MAX_ITEMS]
            if c.state != "running"
            and c.labels.get("windflow.managed") != "true"
            and not self._container_is_protected(c)
        ]
        spared_names = [
            c.name
            for c in containers
            if c.state != "running" and self._container_is_protected(c)
        ][:PRUNE_MAX_ITEMS]
        if dry_run:
            return PruneResult(
                resource="containers",
                dry_run=True,
                pruned_count=len(candidates),
                space_reclaimed_bytes=0,
                spared_count=len(spared_names),
                pruned_names=[c.name for c in candidates],
                spared_names=spared_names,
                failed_names=[],
                failed_count=0,
            )
        pruned_names: list[str] = []
        failed_names: list[str] = []
        for c in candidates:
            try:
                await self.remove_container(c.id, force=force, remove_volumes=False)
            except Exception as exc:  # échec isolé : la file continue
                logger.warning(
                    "prune_stopped_containers : container %s non supprimé (%s) "
                    "— file continuée",
                    c.name,
                    exc,
                )
                failed_names.append(c.name)
                continue
            pruned_names.append(c.name)
        return PruneResult(
            resource="containers",
            dry_run=False,
            pruned_count=len(pruned_names),
            space_reclaimed_bytes=0,
            spared_count=len(spared_names),
            pruned_names=pruned_names,
            spared_names=spared_names,
            failed_names=failed_names,
            failed_count=len(failed_names),
        )

    @staticmethod
    def _image_is_protected(image: ImageInfo) -> bool:
        """Une image est protégée si un de ses tags porte le préfixe plugin."""
        return any(PROTECTED_RESOURCE_PREFIX in tag for tag in (image.repo_tags or []))

    @staticmethod
    def _container_is_protected(container: ContainerInfo) -> bool:
        """Un container est protégé si son nom ou son projet compose est plugin.

        Les services plugins tournent sous le projet compose
        ``windflow-plugin-{name}`` (STORY-169.3) — le nom du container
        (préfixe compose) ou le label ``com.docker.compose.project``
        porte le préfixe protégé.
        """
        if is_protected_resource(container.name):
            return True
        project = container.labels.get("com.docker.compose.project", "")
        return is_protected_resource(project)

    async def _volume_names_in_use(self) -> set[str]:
        """Ensemble des noms de volumes montés par au moins un conteneur.

        ``all=True`` : un volume monté par un container **arrêté** est
        bien « utilisé » (sémantique spec 09 § Prune — STORY-173).
        """
        containers = await self.list_containers(all=True)
        names: set[str] = set()
        for container in containers:
            for mount in getattr(container, "mounts", None) or []:
                name = mount.get("Name") if isinstance(mount, dict) else None
                if name:
                    names.add(name)
        return names

    # =========================================================================
    # Networks
    # =========================================================================

    async def list_networks(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[NetworkInfo]:
        """
        Liste les réseaux.

        GET /networks

        Args:
            filters: Filtres

        Returns:
            Liste de NetworkInfo
        """
        params = {}
        if filters:
            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/networks", params=params)
        data = await response.json()

        return [NetworkInfo.from_dict(n) for n in data]

    async def inspect_network(self, network_id: str) -> dict[str, Any]:
        """
        Inspecte un réseau.

        GET /networks/{id}

        Args:
            network_id: ID ou nom du réseau

        Returns:
            Détails du réseau
        """
        response = await self._request("GET", f"/networks/{network_id}")
        return await response.json()

    async def connect_container_to_network(
        self,
        network_id: str,
        container_id: str,
        aliases: Optional[list[str]] = None,
        ipv4_address: Optional[str] = None,
    ) -> None:
        """
        Connecte un container à un réseau.

        POST /networks/{id}/connect

        Args:
            network_id: ID ou nom du réseau
            container_id: ID ou nom du container
            aliases: Alias réseau optionnels
            ipv4_address: Adresse IPv4 fixe optionnelle
        """
        endpoint_config: dict[str, Any] = {}
        if aliases:
            endpoint_config["Aliases"] = aliases
        if ipv4_address:
            endpoint_config["IPAMConfig"] = {"IPv4Address": ipv4_address}

        body: dict[str, Any] = {
            "Container": container_id,
            "EndpointConfig": endpoint_config,
        }
        await self._request("POST", f"/networks/{network_id}/connect", body=body)

    async def disconnect_container_from_network(
        self,
        network_id: str,
        container_id: str,
        force: bool = False,
    ) -> None:
        """
        Déconnecte un container d'un réseau.

        POST /networks/{id}/disconnect

        Args:
            network_id: ID ou nom du réseau
            container_id: ID ou nom du container
            force: Forcer la déconnexion même si le container est arrêté
        """
        body: dict[str, Any] = {
            "Container": container_id,
            "Force": force,
        }
        await self._request("POST", f"/networks/{network_id}/disconnect", body=body)

    # =========================================================================
    # System
    # =========================================================================

    async def ping(self) -> bool:
        """
        Teste la connexion Docker.

        GET /_ping

        Returns:
            True si Docker est accessible
        """
        try:
            response = await self._request("GET", "/_ping")
            return response.status == 200
        except Exception:
            return False

    async def system_info(self) -> SystemInfo:
        """
        Récupère les informations système Docker.

        GET /info

        Returns:
            SystemInfo
        """
        response = await self._request("GET", "/info")
        data = await response.json()

        return SystemInfo.from_dict(data)

    async def system_version(self) -> dict[str, Any]:
        """
        Récupère la version de Docker.

        GET /version

        Returns:
            Version et informations API
        """
        response = await self._request("GET", "/version")
        return await response.json()

    # =========================================================================
    # Exec
    # =========================================================================

    async def exec_create(
        self,
        container_id: str,
        cmd: list[str],
        user: Optional[str] = None,
        working_dir: Optional[str] = None,
        tty: bool = False,
    ) -> str:
        """
        Crée une session exec dans un container.

        POST /containers/{id}/exec

        Args:
            container_id: ID du container
            cmd: Commande à exécuter
            user: Utilisateur
            working_dir: Répertoire de travail
            tty: Allouer un TTY

        Returns:
            Exec ID
        """
        body = {
            "Cmd": cmd,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": tty,
        }

        if user:
            body["User"] = user
        if working_dir:
            body["WorkingDir"] = working_dir

        response = await self._request(
            "POST",
            f"/containers/{container_id}/exec",
            body=body,
        )

        data = await response.json()
        return data.get("Id", "")

    async def exec_start(
        self,
        exec_id: str,
        tty: bool = False,
    ) -> ExecResult:
        """
        Démarre une session exec.

        POST /exec/{id}/start

        Args:
            exec_id: ID de la session exec
            tty: Mode TTY

        Returns:
            ExecResult (exit_code, output, error)
        """
        body = {"Detach": False, "Tty": tty}

        response = await self._request(
            "POST",
            f"/exec/{exec_id}/start",
            body=body,
            stream=True,
            timeout=self.timeout,
        )

        output = b""
        try:
            async for chunk in response.content.iter_any():
                output += chunk
        finally:
            response.close()

        # Démultiplexer le stream
        stdout = ""
        stderr = ""
        offset = 0

        while offset < len(output):
            if offset + 8 > len(output):
                break

            stream_type = output[offset]
            frame_size = int.from_bytes(output[offset + 4 : offset + 8], "big")

            if frame_size == 0 or offset + 8 + frame_size > len(output):
                break

            payload = output[offset + 8 : offset + 8 + frame_size]
            decoded = payload.decode("utf-8", errors="replace")

            if stream_type == 1:  # stdout
                stdout += decoded
            elif stream_type == 2:  # stderr
                stderr += decoded

            offset += 8 + frame_size

        # Récupérer le code de sortie
        inspect_response = await self._request("GET", f"/exec/{exec_id}/json")
        inspect_data = await inspect_response.json()
        exit_code = inspect_data.get("ExitCode", 0)

        return ExecResult(exit_code=exit_code, output=stdout, error=stderr)

    async def exec_in_container(
        self,
        container_id: str,
        cmd: list[str],
        user: Optional[str] = None,
        working_dir: Optional[str] = None,
    ) -> ExecResult:
        """
        Exécute une commande dans un container (raccourci).

        Args:
            container_id: ID du container
            cmd: Commande à exécuter
            user: Utilisateur
            working_dir: Répertoire de travail

        Returns:
            ExecResult
        """
        exec_id = await self.exec_create(
            container_id=container_id,
            cmd=cmd,
            user=user,
            working_dir=working_dir,
        )
        return await self.exec_start(exec_id)


# =============================================================================
# Factory
# =============================================================================


async def get_docker_client(
    socket_path: str = DEFAULT_DOCKER_SOCKET,
) -> DockerClientService:
    """
    Crée et teste un client Docker.

    Args:
        socket_path: Chemin vers le socket Unix

    Returns:
        Client Docker opérationnel

    Raises:
        ConnectionError: Si Docker n'est pas accessible
    """
    client = DockerClientService(socket_path=socket_path)

    if not await client.ping():
        await client.close()
        raise ConnectionError(
            f"Docker n'est pas accessible via {socket_path}. "
            "Vérifiez que Docker est en cours d'exécution."
        )

    return client
