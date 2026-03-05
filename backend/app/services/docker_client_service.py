"""
Client Docker via API REST Engine v1.41+.

Connexion via Unix socket local (/var/run/docker.sock) avec httpx.
Toutes les opérations sont asynchrones et n'ont pas de dépendance externe.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Optional

import httpx

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
    logs: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContainerDetail":
        created_str = data.get("Created", "")
        created = datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else datetime.now()

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
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Récupère ou crée le client HTTP avec transport Unix socket."""
        if self._client is None:
            transport = httpx.AsyncHTTPTransport(uds=self.socket_path)
            self._client = httpx.AsyncClient(
                transport=transport,
                base_url="http://localhost",
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self):
        """Ferme le client HTTP."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        stream: bool = False,
    ) -> httpx.Response:
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
            httpx.HTTPStatusError: En cas d'erreur HTTP
        """
        client = await self._get_client()
        req_timeout = timeout or self.timeout

        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        request = client.build_request(
            method=method,
            url=path,
            params=params,
            json=body if body else None,
            headers=req_headers,
            timeout=req_timeout,
        )

        logger.debug(f"Docker API: {method} {path}")

        if stream:
            # Pour le streaming, on n'attend pas la réponse complète
            response = await client.send(request, stream=True)
            response.raise_for_status()
            return response
        else:
            response = await client.send(request)
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
            import json
            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/containers/json", params=params)
        data = response.json()

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
        data = response.json()
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

        # Ajouter les ports
        if ports:
            config["ExposedPorts"] = {}
            config["HostConfig"]["PortBindings"] = {}
            for container_port, host_config in ports.items():
                config["ExposedPorts"][container_port] = {}
                config["HostConfig"]["PortBindings"][container_port] = [host_config]

        # Ajouter les volumes
        if volumes:
            config["Volumes"] = volumes
            config["HostConfig"]["Binds"] = [
                f"{host}:{container}" for host, container in volumes.items()
            ]

        response = await self._request(
            "POST",
            f"/containers/create?name={name}",
            body=config,
            timeout=60.0,
        )
        data = response.json()
        return data.get("Id", "")

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

        async for chunk in response.aiter_bytes():
            # Démultiplexer le stream Docker
            lines = self._demux_docker_stream(chunk)
            for line in lines:
                yield line

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
            Liste de lignes (stdout uniquement)
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

            # Extraire le payload (stdout seulement, ignorer stderr)
            if stream_type == 1:  # stdout
                payload = chunk[offset + 8 : offset + 8 + frame_size]
                line = payload.decode("utf-8", errors="replace").rstrip("\n")
                if line:
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
        return response.json()

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

        async for line in response.aiter_lines():
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass

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
            import json

            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/images/json", params=params)
        data = response.json()

        return [ImageInfo.from_dict(img) for img in data]

    async def pull_image(
        self,
        name: str,
        tag: str = "latest",
        on_progress: Optional["callable[[PullProgressEvent], None]"] = None,
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

        async for line in response.aiter_lines():
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

        return response.json()

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
        return response.json()

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
            import json

            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/volumes", params=params)
        data = response.json()

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
        data = response.json()

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
            import json

            params["filters"] = json.dumps(filters)

        response = await self._request("GET", "/networks", params=params)
        data = response.json()

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
        return response.json()

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
            return response.status_code == 200
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
        data = response.json()

        return SystemInfo.from_dict(data)

    async def system_version(self) -> dict[str, Any]:
        """
        Récupère la version de Docker.

        GET /version

        Returns:
            Version et informations API
        """
        response = await self._request("GET", "/version")
        return response.json()

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

        data = response.json()
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
        async for chunk in response.aiter_bytes():
            output += chunk

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
        inspect_data = inspect_response.json()
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
