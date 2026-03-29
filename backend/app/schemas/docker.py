"""
Schémas Pydantic pour l'API Docker REST.

Ces schémas sont utilisés pour la validation et la sérialisation
des réponses de l'API Docker.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Containers
# =============================================================================


class PortBinding(BaseModel):
    """Binding d'un port Docker."""

    host_ip: Optional[str] = Field(None, alias="HostIp")
    host_port: Optional[str] = Field(None, alias="HostPort")

    model_config = ConfigDict(populate_by_name=True)


class MountPoint(BaseModel):
    """Point de montage d'un container."""

    type: str
    name: Optional[str] = None
    source: str
    destination: str
    mode: str = "rw"
    propagation: str = ""

    model_config = ConfigDict(populate_by_name=True)


class ContainerResponse(BaseModel):
    """Réponse API pour un container (liste)."""

    id: str = Field(..., description="Container ID (12 premiers caractères)")
    name: str = Field(..., description="Nom du container")
    image: str = Field(..., description="Image Docker utilisée")
    image_id: str = Field(..., alias="imageId", description="ID de l'image")
    command: str = Field(..., description="Commande exécutée")
    created: datetime = Field(..., description="Date de création")
    state: str = Field(..., description="État (running, exited, paused, etc.)")
    status: str = Field(..., description="Status texte (ex: 'Up 2 hours')")
    ports: list[dict[str, Any]] = Field(
        default_factory=list, description="Ports exposés"
    )
    labels: dict[str, str] = Field(
        default_factory=dict, description="Labels du container"
    )
    networks: list[str] = Field(default_factory=list, description="Réseaux attachés")
    mounts: list[dict[str, Any]] = Field(
        default_factory=list, description="Points de montage"
    )
    restart_count: int = Field(0, description="Nombre de redémarrages")

    model_config = ConfigDict(populate_by_name=True)


class ContainerDetailResponse(BaseModel):
    """Réponse API pour les détails d'un container."""

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


class ContainerCreateRequest(BaseModel):
    """Requête de création d'un container."""

    name: str = Field(
        ..., description="Nom du container", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"
    )
    image: str = Field(..., description="Image Docker")
    command: Optional[list[str]] = Field(None, description="Commande à exécuter")
    env: Optional[list[str]] = Field(None, description="Variables d'environnement")
    ports: Optional[dict[str, dict[str, str]]] = Field(
        None, description="Ports à exposer"
    )
    volumes: Optional[dict[str, str]] = Field(None, description="Volumes à monter")
    labels: Optional[dict[str, str]] = Field(None, description="Labels")
    restart_policy: str = Field("no", description="Politique de redémarrage")
    network_mode: str = Field("bridge", description="Mode réseau")
    privileged: bool = Field(False, description="Mode privilégié")


class ContainerLogsRequest(BaseModel):
    """Requête de récupération des logs."""

    tail: int = Field(100, ge=1, le=10000, description="Nombre de lignes")
    timestamps: bool = Field(False, description="Inclure les timestamps")
    since: Optional[int] = Field(None, description="Timestamp de début")
    until: Optional[int] = Field(None, description="Timestamp de fin")


class ContainerLogsResponse(BaseModel):
    """Réponse de logs d'un container."""

    logs: str
    container_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Images
# =============================================================================


class ImageResponse(BaseModel):
    """Réponse API pour une image."""

    id: str = Field(..., description="Image ID")
    repo_tags: list[str] = Field(
        default_factory=list, alias="repoTags", description="Tags"
    )
    repo_digests: list[str] = Field(
        default_factory=list, alias="repoDigests", description="Digests"
    )
    created: datetime = Field(..., description="Date de création")
    size: int = Field(..., description="Taille en bytes")
    virtual_size: int = Field(0, alias="virtualSize", description="Taille virtuelle")
    labels: dict[str, str] = Field(default_factory=dict, description="Labels")

    model_config = ConfigDict(populate_by_name=True)


class ImagePullRequest(BaseModel):
    """Requête de pull d'une image."""

    name: str = Field(..., description="Nom de l'image (ex: nginx, postgres:15)")
    tag: str = Field("latest", description="Tag de l'image")


class ImagePullResponse(BaseModel):
    """Réponse du pull d'image."""

    status: str = Field(..., description="Status de l'opération")
    progress: Optional[str] = Field(None, description="Progression texte")
    id: Optional[str] = Field(None, description="ID de l'image/layer")


# =============================================================================
# Volumes
# =============================================================================


class VolumeResponse(BaseModel):
    """Réponse API pour un volume."""

    name: str = Field(..., description="Nom du volume")
    driver: str = Field("local", description="Driver de stockage")
    mountpoint: str = Field(..., alias="Mountpoint", description="Point de montage")
    created_at: datetime = Field(..., alias="CreatedAt", description="Date de création")
    labels: dict[str, str] = Field(default_factory=dict, description="Labels")
    scope: str = Field("local", description="Scope")

    model_config = ConfigDict(populate_by_name=True)


class VolumeCreateRequest(BaseModel):
    """Requête de création d'un volume."""

    name: str = Field(
        ..., description="Nom du volume", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"
    )
    driver: str = Field("local", description="Driver de stockage")
    labels: Optional[dict[str, str]] = Field(None, description="Labels")


# =============================================================================
# Networks
# =============================================================================


class NetworkResponse(BaseModel):
    """Réponse API pour un réseau."""

    id: str = Field(..., description="Network ID")
    name: str = Field(..., description="Nom du réseau")
    driver: str = Field(..., description="Driver réseau")
    scope: str = Field(..., description="Scope")
    internal: bool = Field(False, description="Réseau interne")
    attachable: bool = Field(False, description="Attachable")
    ingress: bool = Field(False, description="Ingress")
    created: datetime = Field(..., description="Date de création")
    subnet: str = Field("", description="Sous-réseau")
    gateway: str = Field("", description="Passerelle")


# =============================================================================
# System
# =============================================================================


class SystemInfoResponse(BaseModel):
    """Réponse API pour les infos système Docker."""

    id: str = Field(..., alias="ID", description="Docker ID")
    name: str = Field(..., alias="Name", description="Nom de la machine")
    server_version: str = Field(
        ..., alias="ServerVersion", description="Version Docker"
    )
    containers: int = Field(0, description="Nombre total de containers")
    containers_running: int = Field(
        0, alias="ContainersRunning", description="Containers running"
    )
    containers_paused: int = Field(
        0, alias="ContainersPaused", description="Containers pausés"
    )
    containers_stopped: int = Field(
        0, alias="ContainersStopped", description="Containers stoppés"
    )
    images: int = Field(0, description="Nombre d'images")
    driver: str = Field("", description="Driver de stockage")
    docker_root_dir: str = Field(
        "", alias="DockerRootDir", description="Répertoire Docker"
    )
    kernel_version: str = Field(
        "", alias="KernelVersion", description="Version du kernel"
    )
    operating_system: str = Field("", alias="OperatingSystem", description="OS")
    os_type: str = Field("", alias="OSType", description="Type d'OS")
    architecture: str = Field("", description="Architecture")
    cpus: int = Field(0, alias="NCPU", description="Nombre de CPUs")
    memory: int = Field(0, alias="MemTotal", description="Mémoire totale")

    model_config = ConfigDict(populate_by_name=True)


class SystemVersionResponse(BaseModel):
    """Réponse API pour la version Docker."""

    version: str = Field(..., description="Version Docker")
    api_version: str = Field(..., alias="ApiVersion", description="Version API")
    min_api_version: str = Field(
        "", alias="MinAPIVersion", description="Version API minimale"
    )
    git_commit: str = Field("", alias="GitCommit", description="Commit Git")
    go_version: str = Field("", alias="GoVersion", description="Version Go")
    os: str = Field("", description="OS")
    arch: str = Field("", description="Architecture")
    kernel_version: str = Field("", alias="KernelVersion", description="Version kernel")
    build_time: str = Field("", alias="BuildTime", description="Date de build")

    model_config = ConfigDict(populate_by_name=True)


class PingResponse(BaseModel):
    """Réponse du ping Docker."""

    available: bool = Field(..., description="Docker est disponible")
    message: Optional[str] = Field(None, description="Message optionnel")


# =============================================================================
# Erreurs
# =============================================================================


class DockerErrorResponse(BaseModel):
    """Réponse d'erreur Docker standardisée."""

    error: str = Field(..., description="Type d'erreur")
    message: str = Field(..., description="Message d'erreur")
    details: Optional[dict[str, Any]] = Field(
        None, description="Détails supplémentaires"
    )


# =============================================================================
# Processes (container top)
# =============================================================================


class ContainerProcess(BaseModel):
    """Un processus dans un container."""

    pid: int = Field(..., description="Process ID")
    user: str = Field("", description="Utilisateur")
    cpu: float = Field(0.0, description="Utilisation CPU (%)")
    mem: float = Field(0.0, description="Utilisation mémoire (%)")
    time: str = Field("", description="Temps CPU")
    command: str = Field("", description="Commande")


class ContainerProcessListResponse(BaseModel):
    """Réponse API pour la liste des processus d'un container."""

    container_id: str = Field(..., description="Container ID")
    titles: list[str] = Field(default_factory=list, description="En-têtes du tableau")
    processes: list[ContainerProcess] = Field(
        default_factory=list, description="Liste des processus"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Stats
# =============================================================================


class ContainerStatsResponse(BaseModel):
    """Statistiques d'un container."""

    container_id: str
    cpu_stats: dict[str, Any]
    pre_cpu_stats: dict[str, Any]
    memory_stats: dict[str, Any]
    networks: dict[str, Any]
    blkio_stats: dict[str, Any]
    timestamp: datetime

    @classmethod
    def from_docker_stats(
        cls, container_id: str, data: dict[str, Any]
    ) -> "ContainerStatsResponse":
        return cls(
            container_id=container_id,
            cpu_stats=data.get("cpu_stats", {}),
            pre_cpu_stats=data.get("precpu_stats", data.get("cpu_stats", {})),
            memory_stats=data.get("memory_stats", {}),
            networks=data.get("networks", {}),
            blkio_stats=data.get("blkio_stats", {}),
            timestamp=datetime.now(timezone.utc),
        )
