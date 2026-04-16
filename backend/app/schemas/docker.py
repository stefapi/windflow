"""
Schémas Pydantic pour l'API Docker REST.

Ces schémas sont utilisés pour la validation et la sérialisation
des réponses de l'API Docker.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class ContainerHealthLogEntry(BaseModel):
    """Entrée du log de health check d'un container."""

    start: Optional[str] = Field(None, description="Date de début du check")
    end: Optional[str] = Field(None, description="Date de fin du check")
    exit_code: Optional[int] = Field(None, description="Code de sortie du check")
    output: Optional[str] = Field(None, description="Sortie du check")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerHealthLogEntry":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        return cls(
            start=data.get("Start"),
            end=data.get("End"),
            exit_code=data.get("ExitCode"),
            output=data.get("Output"),
        )


class ContainerHealthInfo(BaseModel):
    """Information de health check d'un container."""

    status: Optional[str] = Field(None, description="Statut du health check (healthy, unhealthy, starting)")
    failing_streak: Optional[int] = Field(None, description="Nombre de checks échoués consécutifs")
    log: list[ContainerHealthLogEntry] = Field(default_factory=list, description="Historique des checks")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerHealthInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        log_data = data.get("Log", [])
        return cls(
            status=data.get("Status"),
            failing_streak=data.get("FailingStreak"),
            log=[ContainerHealthLogEntry.from_docker_dict(e) for e in log_data] if log_data else [],
        )


class ContainerStateInfo(BaseModel):
    """État détaillé d'un container (bloc State de l'API Docker)."""

    status: Optional[str] = Field(None, description="Statut (running, exited, paused, dead, created, restarting)")
    running: Optional[bool] = Field(None, description="Le container est-il en cours d'exécution")
    paused: Optional[bool] = Field(None, description="Le container est-il en pause")
    restarting: Optional[bool] = Field(None, description="Le container est-il en cours de redémarrage")
    oom_killed: Optional[bool] = Field(None, description="Le container a-t-il été tué par OOM")
    dead: Optional[bool] = Field(None, description="Le container est-il mort")
    exit_code: Optional[int] = Field(None, description="Code de sortie du container")
    error: Optional[str] = Field(None, description="Message d'erreur lié à l'état")
    started_at: Optional[str] = Field(None, description="Date/heure de démarrage (ISO 8601)")
    finished_at: Optional[str] = Field(None, description="Date/heure d'arrêt (ISO 8601)")
    health: Optional[ContainerHealthInfo] = Field(None, description="Informations de health check")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerStateInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        health_data = data.get("Health")
        return cls(
            status=data.get("Status"),
            running=data.get("Running"),
            paused=data.get("Paused"),
            restarting=data.get("Restarting"),
            oom_killed=data.get("OOMKilled"),
            dead=data.get("Dead"),
            exit_code=data.get("ExitCode"),
            error=data.get("Error"),
            started_at=data.get("StartedAt"),
            finished_at=data.get("FinishedAt"),
            health=ContainerHealthInfo.from_docker_dict(health_data) if health_data else None,
        )


class ContainerConfigInfo(BaseModel):
    """Configuration d'un container (bloc Config de l'API Docker)."""

    hostname: Optional[str] = Field(None, description="Hostname du container")
    domainname: Optional[str] = Field(None, description="Nom de domaine")
    user: Optional[str] = Field(None, description="Utilisateur")
    attach_stdin: Optional[bool] = Field(None, description="Attacher stdin")
    attach_stdout: Optional[bool] = Field(None, description="Attacher stdout")
    attach_stderr: Optional[bool] = Field(None, description="Attacher stderr")
    tty: Optional[bool] = Field(None, description="Terminal interactif")
    open_stdin: Optional[bool] = Field(None, description="Stdin ouvert")
    stdin_once: Optional[bool] = Field(None, description="Fermer stdin après un client")
    env: Optional[list[str]] = Field(None, description="Variables d'environnement")
    cmd: Optional[list[str]] = Field(None, description="Commande exécutée")
    entrypoint: Optional[list[str]] = Field(None, description="Point d'entrée")
    image: Optional[str] = Field(None, description="Image source")
    working_dir: Optional[str] = Field(None, description="Répertoire de travail")
    labels: Optional[dict[str, str]] = Field(None, description="Labels du container")
    stop_signal: Optional[str] = Field(None, description="Signal d'arrêt (ex: SIGTERM)")
    stop_timeout: Optional[int] = Field(None, description="Délai avant force-kill (secondes)")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerConfigInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        return cls(
            hostname=data.get("Hostname"),
            domainname=data.get("Domainname"),
            user=data.get("User"),
            attach_stdin=data.get("AttachStdin"),
            attach_stdout=data.get("AttachStdout"),
            attach_stderr=data.get("AttachStderr"),
            tty=data.get("Tty"),
            open_stdin=data.get("OpenStdin"),
            stdin_once=data.get("StdinOnce"),
            env=data.get("Env"),
            cmd=data.get("Cmd"),
            entrypoint=data.get("Entrypoint"),
            image=data.get("Image"),
            working_dir=data.get("WorkingDir"),
            labels=data.get("Labels"),
            stop_signal=data.get("StopSignal"),
            stop_timeout=data.get("StopTimeout"),
        )


class ContainerLogConfigInfo(BaseModel):
    """Configuration de logging d'un container."""

    type: Optional[str] = Field(None, description="Driver de log (json-file, syslog, etc.)")
    config: Optional[dict[str, str]] = Field(None, description="Configuration du driver de log")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerLogConfigInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        return cls(
            type=data.get("Type"),
            config=data.get("Config"),
        )


class ContainerRestartPolicyInfo(BaseModel):
    """Politique de redémarrage d'un container."""

    name: Optional[str] = Field(None, description="Nom de la politique (no, always, on-failure, unless-stopped)")
    maximum_retry_count: Optional[int] = Field(None, description="Nombre max de tentatives (pour on-failure)")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerRestartPolicyInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        return cls(
            name=data.get("Name"),
            maximum_retry_count=data.get("MaximumRetryCount"),
        )


class ContainerResourcesInfo(BaseModel):
    """Limites de ressources d'un container."""

    memory: Optional[int] = Field(None, description="Limite mémoire en bytes")
    memory_reservation: Optional[int] = Field(None, description="Réservation mémoire en bytes")
    memory_swap: Optional[int] = Field(None, description="Limite swap en bytes (-1 = unlimited)")
    memory_swappiness: Optional[int] = Field(None, description="Swappiness (0-100)")
    cpu_shares: Optional[int] = Field(None, description="Poids CPU relatif")
    cpu_period: Optional[int] = Field(None, description="Période CFS en microsecondes")
    cpu_quota: Optional[int] = Field(None, description="Quota CFS en microsecondes")
    cpus: Optional[int] = Field(None, description="Nombre de CPUs")
    cpuset_cpus: Optional[str] = Field(None, description="CPUs autorisés (ex: '0-3')")
    cpuset_mems: Optional[str] = Field(None, description="Nœuds mémoire autorisés")
    devices: Optional[list[dict[str, Any]]] = Field(None, description="Périphériques mappés")
    ulimits: Optional[list[dict[str, Any]]] = Field(None, description="Ulimits")
    pids_limit: Optional[int] = Field(None, description="Limite de PID")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerResourcesInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        return cls(
            memory=data.get("Memory"),
            memory_reservation=data.get("MemoryReservation"),
            memory_swap=data.get("MemorySwap"),
            memory_swappiness=data.get("MemorySwappiness"),
            cpu_shares=data.get("CpuShares"),
            cpu_period=data.get("CpuPeriod"),
            cpu_quota=data.get("CpuQuota"),
            cpus=data.get("NanoCpus"),
            cpuset_cpus=data.get("CpusetCpus"),
            cpuset_mems=data.get("CpusetMems"),
            devices=data.get("Devices"),
            ulimits=data.get("Ulimits"),
            pids_limit=data.get("PidsLimit"),
        )


class ContainerHostConfigInfo(BaseModel):
    """Configuration hôte d'un container (bloc HostConfig de l'API Docker)."""

    binds: Optional[list[str]] = Field(None, description="Montages bind")
    container_id_file: Optional[str] = Field(None, description="Fichier d'ID du container")
    log_config: Optional[ContainerLogConfigInfo] = Field(None, description="Configuration de logging")
    network_mode: Optional[str] = Field(None, description="Mode réseau (bridge, host, none, etc.)")
    port_bindings: Optional[dict[str, Any]] = Field(None, description="Bindings de ports")
    restart_policy: Optional[ContainerRestartPolicyInfo] = Field(None, description="Politique de redémarrage")
    auto_remove: Optional[bool] = Field(None, description="Suppression automatique à l'arrêt")
    volume_driver: Optional[str] = Field(None, description="Driver de volume")
    volumes_from: Optional[list[str]] = Field(None, description="Volumes hérités d'autres containers")
    cap_add: Optional[list[str]] = Field(None, description="Capabilities ajoutées")
    cap_drop: Optional[list[str]] = Field(None, description="Capabilities retirées")
    cgroupns_mode: Optional[str] = Field(None, description="Mode cgroup namespace")
    dns: Optional[list[str]] = Field(None, description="Serveurs DNS")
    dns_options: Optional[list[str]] = Field(None, description="Options DNS")
    dns_search: Optional[list[str]] = Field(None, description="Domaines de recherche DNS")
    extra_hosts: Optional[list[str]] = Field(None, description="Entrées /etc/hosts supplémentaires")
    group_add: Optional[list[str]] = Field(None, description="Groupes supplémentaires")
    ipc_mode: Optional[str] = Field(None, description="Mode IPC")
    cgroup: Optional[str] = Field(None, description="Cgroup parent")
    links: Optional[list[str]] = Field(None, description="Links vers d'autres containers")
    oom_score_adj: Optional[int] = Field(None, description="Ajustement du score OOM")
    pid_mode: Optional[str] = Field(None, description="Mode PID")
    privileged: Optional[bool] = Field(None, description="Mode privilégié")
    publish_all_ports: Optional[bool] = Field(None, description="Publier tous les ports exposés")
    readonly_rootfs: Optional[bool] = Field(None, description="Système de fichiers en lecture seule")
    security_opt: Optional[list[str]] = Field(None, description="Options de sécurité")
    storage_opt: Optional[dict[str, Any]] = Field(None, description="Options de stockage")
    tmpfs: Optional[dict[str, str]] = Field(None, description="Montages tmpfs")
    uts_mode: Optional[str] = Field(None, description="Mode UTS")
    userns_mode: Optional[str] = Field(None, description="Mode user namespace")
    shm_size: Optional[int] = Field(None, description="Taille /dev/shm en bytes")
    sysctls: Optional[dict[str, str]] = Field(None, description="Paramètres sysctl")
    runtime: Optional[str] = Field(None, description="Runtime (runc, etc.)")
    console_size: Optional[list[int]] = Field(None, description="Taille de la console [hauteur, largeur]")
    isolation: Optional[str] = Field(None, description="Technologie d'isolation")
    resources: Optional[ContainerResourcesInfo] = Field(None, description="Limites de ressources")
    mount_label: Optional[str] = Field(None, description="Label de montage SELinux")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerHostConfigInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        log_config_data = data.get("LogConfig")
        restart_policy_data = data.get("RestartPolicy")
        resources_data = data.get("Resources")
        return cls(
            binds=data.get("Binds"),
            container_id_file=data.get("ContainerIDFile"),
            log_config=ContainerLogConfigInfo.from_docker_dict(log_config_data) if log_config_data else None,
            network_mode=data.get("NetworkMode"),
            port_bindings=data.get("PortBindings"),
            restart_policy=ContainerRestartPolicyInfo.from_docker_dict(restart_policy_data) if restart_policy_data else None,
            auto_remove=data.get("AutoRemove"),
            volume_driver=data.get("VolumeDriver"),
            volumes_from=data.get("VolumesFrom"),
            cap_add=data.get("CapAdd"),
            cap_drop=data.get("CapDrop"),
            cgroupns_mode=data.get("CgroupnsMode"),
            dns=data.get("Dns"),
            dns_options=data.get("DnsOptions"),
            dns_search=data.get("DnsSearch"),
            extra_hosts=data.get("ExtraHosts"),
            group_add=data.get("GroupAdd"),
            ipc_mode=data.get("IpcMode"),
            cgroup=data.get("Cgroup"),
            links=data.get("Links"),
            oom_score_adj=data.get("OomScoreAdj"),
            pid_mode=data.get("PidMode"),
            privileged=data.get("Privileged"),
            publish_all_ports=data.get("PublishAllPorts"),
            readonly_rootfs=data.get("ReadonlyRootfs"),
            security_opt=data.get("SecurityOpt"),
            storage_opt=data.get("StorageOpt"),
            tmpfs=data.get("Tmpfs"),
            uts_mode=data.get("UTSMode"),
            userns_mode=data.get("UsernsMode"),
            shm_size=data.get("ShmSize"),
            sysctls=data.get("Sysctls"),
            runtime=data.get("Runtime"),
            console_size=data.get("ConsoleSize"),
            isolation=data.get("Isolation"),
            resources=ContainerResourcesInfo.from_docker_dict(resources_data) if resources_data else None,
            mount_label=data.get("MountLabel"),
        )


class ContainerNetworkEndpointInfo(BaseModel):
    """Information d'un endpoint réseau d'un container."""

    ip_address: Optional[str] = Field(None, description="Adresse IPv4")
    gateway: Optional[str] = Field(None, description="Passerelle IPv4")
    mac_address: Optional[str] = Field(None, description="Adresse MAC")
    network_id: Optional[str] = Field(None, description="ID du réseau Docker")
    endpoint_id: Optional[str] = Field(None, description="ID de l'endpoint")
    ipv6_gateway: Optional[str] = Field(None, description="Passerelle IPv6")
    global_ipv6_address: Optional[str] = Field(None, description="Adresse IPv6 globale")
    global_ipv6_prefix_len: Optional[int] = Field(None, description="Longueur préfixe IPv6 globale")
    ip_prefix_len: Optional[int] = Field(None, description="Longueur du préfixe IPv4")
    driver: Optional[str] = Field(None, description="Driver réseau de l'endpoint")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerNetworkEndpointInfo":
        """Crée une instance depuis un dict Docker API (PascalCase)."""
        if not data:
            return cls()
        return cls(
            ip_address=data.get("IPAddress"),
            gateway=data.get("Gateway"),
            mac_address=data.get("MacAddress"),
            network_id=data.get("NetworkID"),
            endpoint_id=data.get("EndpointID"),
            ipv6_gateway=data.get("IPv6Gateway"),
            global_ipv6_address=data.get("GlobalIPv6Address"),
            global_ipv6_prefix_len=data.get("GlobalIPv6PrefixLen"),
            ip_prefix_len=data.get("IPPrefixLen"),
            driver=data.get("Driver"),
        )


class ContainerNetworkSettingsInfo(BaseModel):
    """Paramètres réseau d'un container (bloc NetworkSettings de l'API Docker)."""

    networks: dict[str, ContainerNetworkEndpointInfo] = Field(
        default_factory=dict, description="Réseaux attachés (clé = nom du réseau)"
    )

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_docker_dict(cls, data: dict[str, Any]) -> "ContainerNetworkSettingsInfo":
        """Crée une instance depuis un dict Docker API (PascalCase).

        Attend le bloc NetworkSettings complet, avec une clé 'Networks' contenant
        les endpoints par nom de réseau.
        """
        if not data:
            return cls()
        networks_data = data.get("Networks", {})
        networks = {
            name: ContainerNetworkEndpointInfo.from_docker_dict(ep_data)
            for name, ep_data in networks_data.items()
        }
        return cls(networks=networks)


class ContainerDetailResponse(BaseModel):
    """Réponse API pour les détails d'un container."""

    id: str
    name: str
    created: datetime
    path: str
    args: list[str]
    state: ContainerStateInfo = Field(..., description="État détaillé du container")
    image: str
    config: ContainerConfigInfo = Field(..., description="Configuration du container")
    host_config: ContainerHostConfigInfo = Field(..., description="Configuration hôte")
    network_settings: ContainerNetworkSettingsInfo = Field(..., description="Paramètres réseau")
    mounts: list[dict[str, Any]]
    size_rw: Optional[int] = Field(None, description="Taille des modifications en bytes (layer writable)")
    size_root_fs: Optional[int] = Field(None, description="Taille totale du filesystem en bytes")


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


class ContainerRecreateRequest(BaseModel):
    """
    Requête de recréation d'un container avec overrides optionnels.

    Tous les champs sont optionnels. Si un champ est None, la valeur actuelle
    du container est conservée (merge, pas remplacement total).
    """

    image: Optional[str] = Field(
        None,
        description="Nouvelle image Docker. Si None, conserve l'image actuelle.",
    )
    pull_image: bool = Field(
        False,
        description="Puller l'image avant de recréer le container.",
    )
    env: Optional[list[str]] = Field(
        None,
        description="Variables d'environnement (format KEY=VALUE). Si None, conserve les variables actuelles.",
    )
    labels: Optional[dict[str, str]] = Field(
        None,
        description="Labels du container. Si None, conserve les labels actuels.",
    )
    port_bindings: Optional[dict[str, Any]] = Field(
        None,
        description=(
            "Bindings de ports au format Docker "
            '(ex: {"80/tcp": [{"HostPort": "8080"}]}). '
            "Si None, conserve les bindings actuels."
        ),
    )
    mounts: Optional[list[dict[str, Any]]] = Field(
        None,
        description=(
            "Points de montage au format abstrait "
            '(ex: {"type": "bind", "source": "/host", "destination": "/container", "mode": "rw"}). '
            "Si None, conserve les mounts actuels."
        ),
    )
    privileged: Optional[bool] = Field(
        None,
        description="Mode privilégié. Si None, conserve la valeur actuelle.",
    )
    readonly_rootfs: Optional[bool] = Field(
        None,
        description="Système de fichiers racine en lecture seule. Si None, conserve la valeur actuelle.",
    )
    cap_add: Optional[list[str]] = Field(
        None,
        description="Capabilities à ajouter (ex: ['NET_ADMIN', 'SYS_PTRACE']). Si None, conserve les caps actuelles.",
    )
    cap_drop: Optional[list[str]] = Field(
        None,
        description="Capabilities à retirer. Si None, conserve les caps actuelles.",
    )
    stop_timeout: int = Field(
        10,
        ge=0,
        le=300,
        description="Timeout d'arrêt en secondes avant SIGKILL (0-300s, défaut 10s).",
    )


class ContainerRecreateResponse(BaseModel):
    """
    Réponse de recréation d'un container Docker.

    Contient les identifiants de l'ancien et du nouveau container,
    ainsi que les détails complets du nouveau container.
    """

    success: bool = Field(..., description="Indique si la recréation a réussi.")
    message: str = Field(..., description="Message descriptif du résultat.")
    old_container_id: str = Field(
        ...,
        description="ID de l'ancien container (supprimé).",
    )
    new_container_id: str = Field(
        ...,
        description="ID du nouveau container (créé et démarré).",
    )
    container: ContainerDetailResponse = Field(
        ...,
        description="Détails complets du nouveau container.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Avertissements retournés par Docker lors de la création.",
    )


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

    @field_validator("repo_tags", "repo_digests", mode="before")
    @classmethod
    def none_to_list(cls, v: Any) -> Any:
        """Convert None to empty list — Docker may return None for dangling images."""
        return v if v is not None else []

    @field_validator("labels", mode="before")
    @classmethod
    def none_to_dict(cls, v: Any) -> Any:
        """Convert None to empty dict — Docker may return None for dangling images."""
        return v if v is not None else {}

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
# Container Update & Rename (requests / responses)
# =============================================================================


class ContainerUpdateRestartPolicyRequest(BaseModel):
    """Requête de mise à jour de la politique de redémarrage d'un container."""

    name: str = Field(
        ...,
        description="Politique de redémarrage",
        pattern=r"^(no|always|on-failure|unless-stopped)$",
    )
    maximum_retry_count: Optional[int] = Field(
        None,
        description="Nombre max de tentatives (pour on-failure)",
        ge=0,
    )


class ContainerUpdateResourcesRequest(BaseModel):
    """Requête de mise à jour des limites de ressources d'un container."""

    memory_limit: Optional[int] = Field(
        None,
        description="Limite mémoire en bytes",
        ge=0,
    )
    cpu_shares: Optional[int] = Field(
        None,
        description="Poids CPU relatif",
        ge=0,
    )
    pids_limit: Optional[int] = Field(
        None,
        description="Limite de PID (-1 = unlimited)",
        ge=-1,
    )


class ContainerRenameRequest(BaseModel):
    """Requête de renommage d'un container."""

    new_name: str = Field(
        ...,
        description="Nouveau nom du container",
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$",
    )


class ContainerUpdateResponse(BaseModel):
    """Réponse de mise à jour d'un container (restart policy ou resources)."""

    warnings: Optional[list[str]] = Field(
        default=None,
        description="Avertissements retournés par Docker (None si aucun)",
    )


class ContainerRenameResponse(BaseModel):
    """Réponse de renommage d'un container."""

    success: bool = Field(..., description="Succès de l'opération")
    message: str = Field(..., description="Message de confirmation")


class ContainerPromoteRequest(BaseModel):
    """Requête de promotion d'un container standalone en stack WindFlow."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nom de la stack à créer",
    )


class ContainerPromoteResponse(BaseModel):
    """Réponse de promotion d'un container en stack."""

    success: bool = Field(..., description="Succès de l'opération")
    message: str = Field(..., description="Message de confirmation")
    stack_id: str = Field(..., description="ID de la stack créée")
    stack_name: str = Field(..., description="Nom de la stack créée")


# =============================================================================
# Processes (container top)
# =============================================================================


class ContainerShellResponse(BaseModel):
    """Shell disponible dans un container."""

    path: str = Field(..., description="Chemin absolu du shell (ex: /bin/bash)")
    label: str = Field(..., description="Nom affichable du shell (ex: bash)")
    available: bool = Field(..., description="Si le shell est disponible dans le container")

    model_config = ConfigDict(populate_by_name=True)


class ContainerProcess(BaseModel):
    """Un processus dans un container."""

    pid: int = Field(..., description="Process ID")
    user: str = Field("", description="Utilisateur")
    cpu: float = Field(0.0, description="Utilisation CPU (%)")
    mem: float = Field(0.0, description="Utilisation mémoire (%)")
    time: str = Field("", description="Temps CPU")
    command: str = Field("", description="Commande")


class BatchContainerActionRequest(BaseModel):
    """Requête d'action batch sur un ensemble de containers."""

    container_ids: list[str] = Field(
        ...,
        description="Liste des IDs de containers à traiter",
        min_length=1,
        max_length=100,
    )


class BatchContainerActionResponse(BaseModel):
    """Réponse d'une action batch sur des containers."""

    success: bool
    message: str
    action: str
    affected: int
    errors: list[str] = Field(default_factory=list)


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


class NetworkInterfaceStats(BaseModel):
    """Métriques réseau par interface."""

    name: str = Field(..., description="Nom de l'interface (ex: eth0)")
    rx_bytes: int = Field(0, description="Bytes reçus")
    tx_bytes: int = Field(0, description="Bytes envoyés")
    rx_packets: int = Field(0, description="Packets reçus")
    tx_packets: int = Field(0, description="Packets envoyés")
    rx_errors: int = Field(0, description="Erreurs en réception")
    tx_errors: int = Field(0, description="Erreurs en émission")
    rx_dropped: int = Field(0, description="Packets dropped en réception")
    tx_dropped: int = Field(0, description="Packets dropped en émission")

    model_config = ConfigDict(populate_by_name=True)


class NetworkStats(BaseModel):
    """Métriques réseau agrégées (totaux + détail par interface)."""

    rx_bytes: int = Field(0, description="Total bytes reçus (toutes interfaces)")
    tx_bytes: int = Field(0, description="Total bytes envoyés (toutes interfaces)")
    total_rx_errors: int = Field(0, description="Total erreurs en réception")
    total_tx_errors: int = Field(0, description="Total erreurs en émission")
    total_rx_dropped: int = Field(0, description="Total packets dropped en réception")
    total_tx_dropped: int = Field(0, description="Total packets dropped en émission")
    interfaces: list[NetworkInterfaceStats] = Field(
        default_factory=list, description="Détail par interface réseau"
    )

    model_config = ConfigDict(populate_by_name=True)


class BlkioDeviceStats(BaseModel):
    """Métriques Block I/O par device."""

    major: int = Field(..., description="Device major number")
    minor: int = Field(..., description="Device minor number")
    read_bytes: int = Field(0, description="Bytes lus")
    write_bytes: int = Field(0, description="Bytes écrits")
    read_ops: int = Field(0, description="Opérations de lecture (IOPS)")
    write_ops: int = Field(0, description="Opérations d'écriture (IOPS)")

    model_config = ConfigDict(populate_by_name=True)


class BlkioStats(BaseModel):
    """Métriques Block I/O agrégées (totaux + détail par device)."""

    read_bytes: int = Field(0, description="Total bytes lus (tous devices)")
    write_bytes: int = Field(0, description="Total bytes écrits (tous devices)")
    devices: list[BlkioDeviceStats] = Field(
        default_factory=list, description="Détail par device"
    )

    model_config = ConfigDict(populate_by_name=True)


class ContainerStatsResponse(BaseModel):
    """Statistiques d'un container — format pré-calculé."""

    type: str = "stats"
    container_id: str
    timestamp: str
    cpu: dict[str, Any]
    memory: dict[str, Any]
    network: NetworkStats = Field(..., description="Métriques réseau détaillées")
    block_io: BlkioStats = Field(..., description="Métriques Block I/O détaillées")
