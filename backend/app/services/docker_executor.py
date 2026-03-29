"""
Couche d'abstraction pour l'exécution Docker.

Support de deux méthodes d'exécution :
1. CLI (subprocess) - prioritaire pour le débogage
2. Socket (Docker REST API via Unix socket) - fallback

La priorité est donnée à CLI car elle offre une meilleure visibility pour le debug.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .docker_client_service import DockerClientService, get_docker_client

logger = logging.getLogger(__name__)

# Chemin par défaut du socket Docker
DEFAULT_DOCKER_SOCKET = "/var/run/docker.sock"


class DockerExecutorBase(ABC):
    """Classe de base abstraite pour les exécuteurs Docker."""

    @abstractmethod
    async def deploy_container(
        self, config: Dict[str, Any], container_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Déploie un container Docker."""

    @abstractmethod
    async def start_container(self, container_name: str) -> Tuple[bool, str]:
        """Démarre un container."""

    @abstractmethod
    async def stop_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Arrête un container."""

    @abstractmethod
    async def restart_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Redémarre un container."""

    @abstractmethod
    async def remove_container(
        self, container_name: str, force: bool = False, remove_volumes: bool = True
    ) -> Tuple[bool, str]:
        """Supprime un container."""

    @abstractmethod
    async def get_container_status(
        self, container_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Récupère le statut d'un container."""

    @abstractmethod
    async def get_container_logs(
        self, container_name: str, tail: int = 100, since: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Récupère les logs d'un container."""

    @abstractmethod
    async def remove_volume(
        self, volume_name: str, force: bool = False
    ) -> Tuple[bool, str]:
        """Supprime un volume Docker."""


class CLIDockerExecutor(DockerExecutorBase):
    """
    Exécuteur Docker via CLI (subprocess).

    Prioritaire pour le débogage - offre une meilleure visibility.
    """

    def __init__(self, docker_path: str = "docker"):
        """
        Initialise l'exécuteur CLI.

        Args:
            docker_path: Chemin vers l'exécutable docker (défaut: 'docker')
        """
        self.docker_path = docker_path

    def _build_run_command(
        self, config: Dict[str, Any], container_name: Optional[str] = None
    ) -> List[str]:
        """Construit la commande docker run."""
        cmd = [self.docker_path, "run", "-d"]

        # Nom du container
        name = container_name or config.get("container_name")
        if name:
            cmd.extend(["--name", name])

        # Variables d'environnement
        env_vars = config.get("environment", {})
        for key, value in env_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Ports
        ports = config.get("ports", [])
        for port_mapping in ports:
            cmd.extend(["-p", port_mapping])

        # Volumes
        volumes = config.get("volumes", [])
        for volume_mapping in volumes:
            cmd.extend(["-v", volume_mapping])

        # Restart policy
        restart_policy = config.get("restart_policy", "unless-stopped")
        cmd.extend(["--restart", restart_policy])

        # Health check
        healthcheck = config.get("healthcheck")
        if healthcheck and isinstance(healthcheck, dict):
            test = healthcheck.get("test")
            if test:
                if isinstance(test, list):
                    test_str = (
                        " ".join(test[1:]) if test[0] == "CMD-SHELL" else " ".join(test)
                    )
                else:
                    test_str = str(test)
                cmd.extend(["--health-cmd", test_str])

            if "interval" in healthcheck:
                cmd.extend(["--health-interval", healthcheck["interval"]])
            if "timeout" in healthcheck:
                cmd.extend(["--health-timeout", healthcheck["timeout"]])
            if "retries" in healthcheck:
                cmd.extend(["--health-retries", str(healthcheck["retries"])])
            if "start_period" in healthcheck:
                cmd.extend(["--health-start-period", healthcheck["start_period"]])

        # Labels
        labels = config.get("labels", {})
        for key, value in labels.items():
            cmd.extend(["--label", f"{key}={value}"])

        # Image (doit être à la fin)
        cmd.append(config["image"])

        return cmd

    async def deploy_container(
        self, config: Dict[str, Any], container_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Déploie un container via CLI."""
        cmd = self._build_run_command(config, container_name)

        try:
            logger.info(f"CLI: Exécution: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=300  # 5 minutes
            )

            if process.returncode == 0:
                container_id = stdout.decode().strip()
                logger.info(f"CLI: Container déployé: {container_id}")
                return True, container_id
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"CLI: Échec déploiement: {error_msg}")
                return False, error_msg

        except asyncio.TimeoutError:
            return False, "Timeout lors du déploiement (> 5 minutes)"
        except Exception as e:
            return False, f"Erreur lors du déploiement: {str(e)}"

    async def start_container(self, container_name: str) -> Tuple[bool, str]:
        """Démarre un container via CLI."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_path,
                "start",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                logger.info(f"CLI: Container démarré: {container_name}")
                return True, f"Container {container_name} démarré"
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"CLI: Échec démarrage: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors du démarrage: {str(e)}"

    async def stop_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Arrête un container via CLI."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_path,
                "stop",
                "-t",
                str(timeout),
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout + 5
            )

            if process.returncode == 0:
                logger.info(f"CLI: Container arrêté: {container_name}")
                return True, f"Container {container_name} arrêté"
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"CLI: Échec arrêt: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors de l'arrêt: {str(e)}"

    async def restart_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Redémarre un container via CLI."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_path,
                "restart",
                "-t",
                str(timeout),
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout + 5
            )

            if process.returncode == 0:
                logger.info(f"CLI: Container redémarré: {container_name}")
                return True, f"Container {container_name} redémarré"
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"CLI: Échec redémarrage: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors du redémarrage: {str(e)}"

    async def remove_container(
        self, container_name: str, force: bool = False, remove_volumes: bool = True
    ) -> Tuple[bool, str]:
        """Supprime un container via CLI."""
        try:
            cmd = [self.docker_path, "rm"]
            if force:
                cmd.append("-f")
            if remove_volumes:
                cmd.append("-v")
            cmd.append(container_name)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                logger.info(f"CLI: Container supprimé: {container_name}")
                return True, f"Container {container_name} supprimé"
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"CLI: Échec suppression: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors de la suppression: {str(e)}"

    async def get_container_status(
        self, container_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Récupère le statut via CLI (docker inspect)."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.docker_path,
                "inspect",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                container_info = json.loads(stdout.decode())[0]

                status_info = {
                    "id": container_info["Id"],
                    "name": container_info["Name"].lstrip("/"),
                    "image": container_info["Config"]["Image"],
                    "state": container_info["State"]["Status"],
                    "running": container_info["State"]["Running"],
                    "started_at": container_info["State"]["StartedAt"],
                    "health": container_info["State"]
                    .get("Health", {})
                    .get("Status", "none"),
                    "restart_count": container_info["RestartCount"],
                }

                return True, status_info
            else:
                return False, {"error": stderr.decode().strip()}

        except Exception as e:
            logger.error(f"CLI: Erreur récupération statut: {e}")
            return False, {"error": str(e)}

    async def get_container_logs(
        self, container_name: str, tail: int = 100, since: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Récupère les logs via CLI."""
        try:
            cmd = [self.docker_path, "logs", "--tail", str(tail)]
            if since:
                cmd.extend(["--since", since])
            cmd.append(container_name)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                logs = stdout.decode() + stderr.decode()
                return True, logs
            else:
                return False, stderr.decode().strip()

        except Exception as e:
            logger.error(f"CLI: Erreur récupération logs: {e}")
            return False, str(e)

    async def remove_volume(
        self, volume_name: str, force: bool = False
    ) -> Tuple[bool, str]:
        """Supprime un volume via CLI."""
        try:
            cmd = [self.docker_path, "volume", "rm"]
            if force:
                cmd.append("-f")
            cmd.append(volume_name)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                logger.info(f"CLI: Volume supprimé: {volume_name}")
                return True, f"Volume {volume_name} supprimé"
            else:
                error_msg = stderr.decode().strip()
                # Volume n'existe pas = succès
                if (
                    "no such volume" in error_msg.lower()
                    or "not found" in error_msg.lower()
                ):
                    logger.warning(f"CLI: Volume {volume_name} n'existe pas")
                    return True, f"Volume {volume_name} n'existe pas"
                logger.error(f"CLI: Échec suppression volume: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors de la suppression du volume: {str(e)}"


class SocketDockerExecutor(DockerExecutorBase):
    """
    Exécuteur Docker via socket Unix (Docker REST API).

    Fallback quand CLI n'est pas disponible.
    """

    def __init__(self, socket_path: str = DEFAULT_DOCKER_SOCKET):
        """
        Initialise l'exécuteur socket.

        Args:
            socket_path: Chemin vers le socket Docker Unix
        """
        self.socket_path = socket_path
        self._client: Optional[DockerClientService] = None

    async def _get_client(self) -> Optional[DockerClientService]:
        """Récupère ou crée le client Docker."""
        if self._client is None:
            try:
                self._client = await get_docker_client(socket_path=self.socket_path)
                # Test de connexion
                await self._client.ping()
            except Exception as e:
                logger.error(f"Socket: Échec connexion Docker: {e}")
                return None
        return self._client

    async def deploy_container(
        self, config: Dict[str, Any], container_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Déploie un container via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            name = container_name or config.get("container_name")

            # Préparer la config pour l'API Docker
            container_config: Dict[str, Any] = {
                "Image": config.get("image"),
                "name": name,
                "Env": [f"{k}={v}" for k, v in config.get("environment", {}).items()],
                "ExposedPorts": {},
                "HostConfig": {
                    "RestartPolicy": {
                        "Name": config.get("restart_policy", "unless-stopped")
                    },
                    "PortBindings": {},
                    "Binds": config.get("volumes", []),
                },
            }

            # Parser les ports
            for port_mapping in config.get("ports", []):
                host_port, container_port = port_mapping.split(":")
                container_port_proto = container_port.split("/")
                container_port = container_port_proto[0]
                proto = (
                    container_port_proto[1] if len(container_port_proto) > 1 else "tcp"
                )

                container_config["ExposedPorts"].update(
                    {f"{container_port}/{proto}": {}}
                )
                container_config["HostConfig"]["PortBindings"].update(
                    {f"{container_port}/{proto}": [{"HostPort": host_port}]}
                )

            # Labels
            if config.get("labels"):
                container_config["Labels"] = config["labels"]

            # Healthcheck
            if config.get("healthcheck"):
                hc = config["healthcheck"]
                container_config["Healthcheck"] = {
                    "Test": hc.get("test"),
                    "Interval": hc.get("interval"),
                    "Timeout": hc.get("timeout"),
                    "Retries": hc.get("retries"),
                    "StartPeriod": hc.get("start_period"),
                }

            # Créer et démarrer le container - extraction typée
            c_name: str = str(container_config.get("name", ""))
            c_image: str = str(container_config.get("Image", ""))
            c_env: Optional[List[str]] = container_config.get("Env")  # type: ignore[assignment]
            c_labels: Optional[Dict[str, str]] = container_config.get("Labels")  # type: ignore[assignment]
            host_config: Dict[str, Any] = container_config.get("HostConfig", {})  # type: ignore[assignment]
            port_bindings = host_config.get("PortBindings", {})
            restart_policy_name = str(
                host_config.get("RestartPolicy", {}).get("Name", "no")
            )

            container_id = await client.create_container(
                name=c_name,
                image=c_image,
                env=c_env,
                ports=port_bindings,
                labels=c_labels,
                restart_policy=restart_policy_name,
            )
            await client.start_container(container_id)

            logger.info(f"Socket: Container déployé: {container_id}")
            return True, container_id

        except Exception as e:
            logger.error(f"Socket: Échec déploiement: {e}")
            return False, str(e)

    async def start_container(self, container_name: str) -> Tuple[bool, str]:
        """Démarre un container via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            await client.start_container(container_name)
            logger.info(f"Socket: Container démarré: {container_name}")
            return True, f"Container {container_name} démarré"
        except Exception as e:
            logger.error(f"Socket: Échec démarrage: {e}")
            return False, str(e)

    async def stop_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Arrête un container via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            await client.stop_container(container_name, timeout=timeout)
            logger.info(f"Socket: Container arrêté: {container_name}")
            return True, f"Container {container_name} arrêté"
        except Exception as e:
            logger.error(f"Socket: Échec arrêt: {e}")
            return False, str(e)

    async def restart_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Redémarre un container via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            await client.restart_container(container_name, timeout=timeout)
            logger.info(f"Socket: Container redémarré: {container_name}")
            return True, f"Container {container_name} redémarré"
        except Exception as e:
            logger.error(f"Socket: Échec redémarrage: {e}")
            return False, str(e)

    async def remove_container(
        self, container_name: str, force: bool = False, remove_volumes: bool = True
    ) -> Tuple[bool, str]:
        """Supprime un container via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            await client.remove_container(container_name, force=force, remove_volumes=remove_volumes)
            logger.info(f"Socket: Container supprimé: {container_name}")
            return True, f"Container {container_name} supprimé"
        except Exception as e:
            logger.error(f"Socket: Échec suppression: {e}")
            return False, str(e)

    async def get_container_status(
        self, container_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Récupère le statut via socket."""
        client = await self._get_client()
        if not client:
            return False, {"error": f"Docker non accessible via {self.socket_path}"}

        try:
            container = await client.get_container(container_name)
            if container:
                return True, {
                    "id": container.id,
                    "name": container.name,
                    "image": container.image,
                    "state": container.state,
                    "running": container.state == "running",
                    "started_at": container.created,
                    "health": getattr(container, "health", "none"),
                    "restart_count": getattr(container, "restart_count", 0),
                }
            return False, {"error": "Container non trouvé"}
        except Exception as e:
            logger.error(f"Socket: Erreur récupération statut: {e}")
            return False, {"error": str(e)}

    async def get_container_logs(
        self, container_name: str, tail: int = 100, since: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Récupère les logs via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            log_lines = []
            async for line in client.container_logs(
                container_name, tail=tail
            ):
                log_lines.append(line)
            logs = "\n".join(log_lines)
            return True, logs
        except Exception as e:
            logger.error(f"Socket: Erreur récupération logs: {e}")
            return False, str(e)

    async def remove_volume(
        self, volume_name: str, force: bool = False
    ) -> Tuple[bool, str]:
        """Supprime un volume via socket."""
        client = await self._get_client()
        if not client:
            return False, f"Docker non accessible via {self.socket_path}"

        try:
            await client.remove_volume(volume_name, force=force)
            logger.info(f"Socket: Volume supprimé: {volume_name}")
            return True, f"Volume {volume_name} supprimé"
        except Exception as e:
            error_msg = str(e)
            if "no such volume" in error_msg.lower():
                logger.warning(f"Socket: Volume {volume_name} n'existe pas")
                return True, f"Volume {volume_name} n'existe pas"
            logger.error(f"Socket: Échec suppression volume: {e}")
            return False, error_msg


def get_docker_executor(
    prefer_cli: bool = True,
    socket_path: str = DEFAULT_DOCKER_SOCKET,
    docker_path: str = "docker",
) -> DockerExecutorBase:
    """
    Factory pour récupérer un exécuteur Docker.

    Args:
        prefer_cli: Si True, retourne CLI en premier, Socket en fallback
        socket_path: Chemin vers le socket Docker
        docker_path: Chemin vers l'exécutable docker

    Returns:
        Instance de DockerExecutorBase
    """
    if prefer_cli:
        # CLI en premier - vérifier si disponible
        try:
            # Test rapide avec docker --version
            import subprocess

            result = subprocess.run(
                [docker_path, "--version"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                logger.info("DockerExecutor: Utilisation de CLI (prioritaire)")
                return CLIDockerExecutor(docker_path=docker_path)
        except Exception:
            pass

        # Fallback sur socket
        logger.info("DockerExecutor: CLI non disponible, utilisation socket")
        return SocketDockerExecutor(socket_path=socket_path)
    else:
        # Socket en premier
        logger.info("DockerExecutor: Utilisation de Socket")
        return SocketDockerExecutor(socket_path=socket_path)


class DockerExecutor:
    """
    Classe principale qui combine CLI et Socket avec fallback automatique.

    Utilise CLI en priorité pour le débogage, bascule sur Socket si nécessaire.
    """

    def __init__(
        self,
        prefer_cli: bool = True,
        socket_path: str = DEFAULT_DOCKER_SOCKET,
        docker_path: str = "docker",
    ):
        """
        Initialise l'exécuteur Docker avec fallback.

        Args:
            prefer_cli: Si True, essaie CLI en premier (défaut: True)
            socket_path: Chemin vers le socket Docker
            docker_path: Chemin vers l'exécutable docker
        """
        self._cli = CLIDockerExecutor(docker_path=docker_path)
        self._socket = SocketDockerExecutor(socket_path=socket_path)
        self._prefer_cli = prefer_cli
        self._cli_available: Optional[bool] = None  # Lazy check

    async def _get_executor(self) -> DockerExecutorBase:
        """Récupère l'exécuteur appropriate avec fallback."""
        if self._prefer_cli:
            if self._cli_available is None:
                # Test CLI une fois
                try:
                    process = await asyncio.create_subprocess_exec(
                        "docker",
                        "--version",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await asyncio.wait_for(process.communicate(), timeout=5)
                    self._cli_available = process.returncode == 0
                except Exception:
                    self._cli_available = False

            if self._cli_available:
                return self._cli

            logger.warning("DockerExecutor: CLI unavailable, falling back to socket")
            return self._socket

        return self._socket

    async def deploy_container(
        self, config: Dict[str, Any], container_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Déploie un container avec fallback automatique."""
        executor = await self._get_executor()
        return await executor.deploy_container(config, container_name)

    async def start_container(self, container_name: str) -> Tuple[bool, str]:
        """Démarre un container avec fallback."""
        executor = await self._get_executor()
        return await executor.start_container(container_name)

    async def stop_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Arrête un container avec fallback."""
        executor = await self._get_executor()
        return await executor.stop_container(container_name, timeout)

    async def restart_container(
        self, container_name: str, timeout: int = 10
    ) -> Tuple[bool, str]:
        """Redémarre un container avec fallback."""
        executor = await self._get_executor()
        return await executor.restart_container(container_name, timeout)

    async def remove_container(
        self, container_name: str, force: bool = False, remove_volumes: bool = True
    ) -> Tuple[bool, str]:
        """Supprime un container avec fallback."""
        executor = await self._get_executor()
        return await executor.remove_container(container_name, force, remove_volumes)

    async def get_container_status(
        self, container_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Récupère le statut avec fallback."""
        executor = await self._get_executor()
        return await executor.get_container_status(container_name)

    async def get_container_logs(
        self, container_name: str, tail: int = 100, since: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Récupère les logs avec fallback."""
        executor = await self._get_executor()
        return await executor.get_container_logs(container_name, tail, since)

    async def remove_volume(
        self, volume_name: str, force: bool = False
    ) -> Tuple[bool, str]:
        """Supprime un volume avec fallback."""
        executor = await self._get_executor()
        return await executor.remove_volume(volume_name, force)


class ComposeExecutor:
    """
    Exécuteur pour Docker Compose via CLI (async).

    Docker Compose n'a pas d'API REST équivalente, donc on utilise
    uniquement CLI avec asyncio.create_subprocess_exec.
    """

    def __init__(self, docker_compose_path: str = "docker"):
        """
        Initialise l'exécuteur Compose.

        Args:
            docker_compose_path: Chemin vers le binaire docker (utilisé pour 'docker compose')
        """
        self.docker_path = docker_compose_path

    async def deploy_compose(
        self,
        compose_file: Path,
        project_name: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str]:
        """
        Déploie un fichier docker-compose.

        Args:
            compose_file: Chemin vers le fichier docker-compose.yml
            project_name: Nom du projet Docker Compose
            env_vars: Variables d'environnement additionnelles

        Returns:
            Tuple[bool, str]: (Succès, Output/Error)
        """
        try:
            cmd = [
                self.docker_path,
                "compose",
                "-f",
                str(compose_file),
                "-p",
                project_name,
                "up",
                "-d",
            ]

            logger.info(f"Compose: Exécution: {' '.join(cmd)}")

            # Préparer l'environnement
            import os

            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=300  # 5 minutes
            )

            if process.returncode == 0:
                logger.info(f"Compose: Déploiement réussi: {project_name}")
                return True, stdout.decode()
            else:
                error_msg = stderr.decode()
                logger.error(f"Compose: Échec déploiement: {error_msg}")
                return False, error_msg

        except asyncio.TimeoutError:
            return False, "Timeout lors du déploiement (> 5 minutes)"
        except Exception as e:
            return False, f"Erreur lors du déploiement: {str(e)}"

    async def get_compose_status(
        self, project_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Récupère le statut d'un projet Docker Compose.

        Args:
            project_name: Nom du projet

        Returns:
            Tuple[bool, Dict]: (Succès, Statut des services)
        """
        try:
            cmd = [
                self.docker_path,
                "compose",
                "-p",
                project_name,
                "ps",
                "--format",
                "json",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                import json

                services = []
                for line in stdout.decode().strip().split("\n"):
                    if line:
                        services.append(json.loads(line))
                return True, {"services": services}
            else:
                return False, {"error": stderr.decode()}

        except Exception as e:
            logger.error(f"Compose: Erreur récupération statut: {e}")
            return False, {"error": str(e)}

    async def stop_compose(self, project_name: str) -> Tuple[bool, str]:
        """
        Arrête un projet Docker Compose.

        Args:
            project_name: Nom du projet

        Returns:
            Tuple[bool, str]: (Succès, Output/Error)
        """
        try:
            cmd = [self.docker_path, "compose", "-p", project_name, "down"]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode == 0:
                logger.info(f"Compose: Projet arrêté: {project_name}")
                return True, stdout.decode()
            else:
                error_msg = stderr.decode()
                logger.error(f"Compose: Échec arrêt: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors de l'arrêt: {str(e)}"

    async def remove_compose(
        self, project_name: str, remove_volumes: bool = True
    ) -> Tuple[bool, str]:
        """
        Supprime complètement un projet Docker Compose.

        Args:
            project_name: Nom du projet
            remove_volumes: Si True, supprime aussi les volumes

        Returns:
            Tuple[bool, str]: (Succès, Output/Error)
        """
        try:
            cmd = [self.docker_path, "compose", "-p", project_name, "down"]

            if remove_volumes:
                cmd.append("-v")
            cmd.append("--remove-orphans")

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

            if process.returncode == 0:
                logger.info(f"Compose: Projet supprimé: {project_name}")
                return True, stdout.decode()
            else:
                error_msg = stderr.decode()
                logger.error(f"Compose: Échec suppression: {error_msg}")
                return False, error_msg

        except Exception as e:
            return False, f"Erreur lors de la suppression: {str(e)}"

    async def get_compose_logs(
        self, project_name: str, service: Optional[str] = None, tail: int = 100
    ) -> Tuple[bool, str]:
        """
        Récupère les logs d'un projet Docker Compose.

        Args:
            project_name: Nom du projet
            service: Nom du service spécifique (optionnel)
            tail: Nombre de lignes à récupérer

        Returns:
            Tuple[bool, str]: (Succès, Logs)
        """
        try:
            cmd = [
                self.docker_path,
                "compose",
                "-p",
                project_name,
                "logs",
                "--tail",
                str(tail),
            ]

            if service:
                cmd.append(service)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

            if process.returncode == 0:
                return True, stdout.decode()
            else:
                return False, stderr.decode()

        except Exception as e:
            logger.error(f"Compose: Erreur récupération logs: {e}")
            return False, str(e)
