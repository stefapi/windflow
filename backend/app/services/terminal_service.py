"""
Service de terminal interactif pour conteneurs Docker.

Gère les sessions exec interactives via docker CLI (approche CLI-first de WindFlow).
Permet le streaming bidirectionnel stdin/stdout/stderr et le redimensionnement TTY.
"""

import asyncio
import logging
import os
import signal
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from .docker_client_service import DockerClientService, get_docker_client

logger = logging.getLogger(__name__)


# =============================================================================
# Modèles de données
# =============================================================================


@dataclass
class ShellInfo:
    """Informations sur un shell disponible."""
    path: str
    label: str
    available: bool


@dataclass
class ExecSession:
    """Session exec active dans un conteneur."""
    exec_id: str
    container_id: str
    shell: str
    user: str
    cols: int
    rows: int
    process: Optional[asyncio.subprocess.Process] = None


# =============================================================================
# Service Terminal
# =============================================================================


class TerminalService:
    """
    Service de terminal interactif pour conteneurs Docker.

    Utilise subprocess (docker exec -it) pour le streaming bidirectionnel,
    suivant l'approche CLI-first de WindFlow pour une meilleure visibilité debug.

    Example:
        >>> service = TerminalService()
        >>> session = await service.create_session("container123", "/bin/bash", "root")
        >>> async for output in service.stream_output(session):
        ...     print(output)
    """

    # Shells à tester pour la détection
    AVAILABLE_SHELLS = [
        {"path": "/bin/bash", "label": "Bash"},
        {"path": "/bin/zsh", "label": "Zsh"},
        {"path": "/bin/sh", "label": "Shell (sh)"},
        {"path": "/bin/ash", "label": "Ash (Alpine)"},
        {"path": "/bin/dash", "label": "Dash"},
        {"path": "/bin/ksh", "label": "Korn Shell"},
    ]

    def __init__(self, docker_client: Optional[DockerClientService] = None):
        """
        Initialise le service terminal.

        Args:
            docker_client: Client Docker optionnel (sera créé si non fourni)
        """
        self._docker_client = docker_client
        self._sessions: dict[str, ExecSession] = {}

    async def _get_docker_client(self) -> DockerClientService:
        """Récupère le client Docker (lazy initialization)."""
        if self._docker_client is None:
            self._docker_client = await get_docker_client()
        return self._docker_client

    async def create_session(
        self,
        container_id: str,
        shell: str = "/bin/sh",
        user: str = "root",
        cols: int = 80,
        rows: int = 24,
    ) -> ExecSession:
        """
        Crée une session exec interactive dans un conteneur.

        Utilise `docker exec -it` via subprocess pour le streaming interactif.

        Args:
            container_id: ID ou nom du conteneur
            shell: Shell à utiliser (ex: /bin/bash, /bin/sh)
            user: Utilisateur pour l'exécution
            cols: Nombre de colonnes TTY
            rows: Nombre de lignes TTY

        Returns:
            ExecSession avec le processus démarré

        Raises:
            ValueError: Si le conteneur n'existe pas ou n'est pas en cours d'exécution
            RuntimeError: Si la création du processus échoue
        """
        # Vérifier que le conteneur existe et est en cours d'exécution
        docker = await self._get_docker_client()

        try:
            container = await docker.get_container(container_id)
            if container.state.get("Status") != "running":
                raise ValueError(f"Container {container_id} is not running")
        except Exception as e:
            raise ValueError(f"Container not found: {e}")

        # Générer un ID de session unique
        import uuid
        exec_id = str(uuid.uuid4())[:8]

        # Construire la commande docker exec
        # -i: interactive (keep stdin open)
        # -t: allocate a pseudo-TTY
        # -w: working dir
        cmd = [
            "docker", "exec",
            "-i", "-t",
            "-w", "/",
            "-e", f"TERM=xterm-256color",
        ]

        # Ajouter l'utilisateur si différent de root
        if user != "root":
            cmd.extend(["-u", user])

        # Ajouter le conteneur et la commande
        cmd.extend([container_id, shell])

        logger.info(f"Creating terminal session {exec_id} for container {container_id}")

        try:
            # Créer le processus avec pipes pour stdin/stdout/stderr
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Envoyer les dimensions TTY initiales via stdin (SIOCSWINSZ)
            # On utilise une commande shell pour设置 la taille
            resize_cmd = f"\x1b[8;{rows};{cols}t"
            process.stdin.write(resize_cmd.encode())
            await process.stdin.flush()

            session = ExecSession(
                exec_id=exec_id,
                container_id=container_id,
                shell=shell,
                user=user,
                cols=cols,
                rows=rows,
                process=process,
            )

            self._sessions[exec_id] = session
            logger.info(f"Terminal session {exec_id} created successfully")

            return session

        except Exception as e:
            logger.error(f"Failed to create terminal session: {e}")
            raise RuntimeError(f"Failed to create terminal session: {e}")

    async def stream_output(self, session: ExecSession) -> AsyncIterator[tuple[bytes, bool]]:
        """
        Stream la sortie stdout/stderr du terminal.

        Args:
            session: Session exec active

        Yields:
            Tuple (data, is_stderr)
        """
        if session.process is None or session.process.stdout is None:
            return

        try:
            while True:
                # Lire depuis stdout
                if session.process.stdout:
                    try:
                        data = await asyncio.wait_for(
                            session.process.stdout.read(4096),
                            timeout=0.1
                        )
                        if data:
                            yield (data, False)
                        else:
                            # EOF atteint, le processus a peut-être terminé
                            break
                    except asyncio.TimeoutError:
                        # Pas de données, continuer
                        pass

                # Lire depuis stderr
                if session.process.stderr:
                    try:
                        data = await asyncio.wait_for(
                            session.process.stderr.read(4096),
                            timeout=0.1
                        )
                        if data:
                            yield (data, True)
                    except asyncio.TimeoutError:
                        pass

                # Vérifier si le processus est terminé
                if session.process.returncode is not None:
                    # Lire les dernières données
                    if session.process.stdout:
                        try:
                            data = await asyncio.wait_for(
                                session.process.stdout.read(),
                                timeout=1.0
                            )
                            if data:
                                yield (data, False)
                        except asyncio.TimeoutError:
                            pass

                    if session.process.stderr:
                        try:
                            data = await asyncio.wait_for(
                                session.process.stderr.read(),
                                timeout=1.0
                            )
                            if data:
                                yield (data, True)
                        except asyncio.TimeoutError:
                            pass

                    break

                # Petit délai pour éviter de monopoliser le CPU
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Error streaming output: {e}")
            raise

    async def send_input(self, session: ExecSession, data: str) -> None:
        """
        Envoie des données d'entrée au terminal.

        Args:
            session: Session exec active
            data: Données à envoyer (commandes, keystrokes)
        """
        if session.process is None or session.process.stdin is None:
            raise RuntimeError("Session not initialized")

        try:
            session.process.stdin.write(data.encode())
            await session.process.stdin.flush()
        except Exception as e:
            logger.error(f"Error sending input: {e}")
            raise

    async def resize_tty(self, session: ExecSession, cols: int, rows: int) -> None:
        """
        Redimensionne le TTY du terminal.

        Utilise la séquence d'échappement xterm pour redimensionner.

        Args:
            session: Session exec active
            cols: Nouveau nombre de colonnes
            rows: Nouveau nombre de lignes
        """
        if session.process is None or session.process.stdin is None:
            raise RuntimeError("Session not initialized")

        # Séquence d'échappement xterm pour resize
        # \x1b[8;rows;colst
        resize_seq = f"\x1b[8;{rows};{cols}t"

        try:
            session.process.stdin.write(resize_seq.encode())
            await session.process.stdin.flush()
            session.cols = cols
            session.rows = rows
            logger.debug(f"Terminal {session.exec_id} resized to {cols}x{rows}")
        except Exception as e:
            logger.error(f"Error resizing terminal: {e}")
            raise

    async def cleanup_session(self, session: ExecSession) -> None:
        """
        Nettoie une session terminal (termine le processus).

        Args:
            session: Session à nettoyer
        """
        if session.exec_id in self._sessions:
            del self._sessions[session.exec_id]

        if session.process:
            try:
                # Envoyer SIGHUP pour terminates proprement
                if session.process.returncode is None:
                    session.process.terminate()
                    try:
                        await asyncio.wait_for(
                            session.process.wait(),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        # Forcer la termination si nécessaire
                        session.process.kill()
                        await session.process.wait()
            except Exception as e:
                logger.warning(f"Error cleaning up process: {e}")

            # Fermer les pipes
            try:
                if session.process.stdin:
                    session.process.stdin.close()
                if session.process.stdout:
                    await session.process.stdout.close()
                if session.process.stderr:
                    await session.process.stderr.close()
            except Exception:
                pass

        logger.info(f"Terminal session {session.exec_id} cleaned up")

    async def detect_shells(self, container_id: str) -> list[ShellInfo]:
        """
        Détecte les shells disponibles dans un conteneur.

        Teste la présence de chaque shell connu.

        Args:
            container_id: ID du conteneur

        Returns:
            Liste de ShellInfo avec la disponibilité
        """
        docker = await self._get_docker_client()
        shells = []

        for shell_def in self.AVAILABLE_SHELLS:
            shell_path = shell_def["path"]

            # Tester si le shell existe avec docker exec
            try:
                result = await docker.exec_in_container(
                    container_id=container_id,
                    cmd=["test", "-f", shell_path],
                )
                available = result.exit_code == 0
            except Exception:
                available = False

            shells.append(ShellInfo(
                path=shell_path,
                label=shell_def["label"],
                available=available,
            ))

        return shells

    async def get_session(self, exec_id: str) -> Optional[ExecSession]:
        """Récupère une session par son ID."""
        return self._sessions.get(exec_id)

    async def close(self) -> None:
        """Ferme toutes les sessions et le client Docker."""
        # Nettoyer toutes les sessions
        sessions_copy = list(self._sessions.values())
        for session in sessions_copy:
            await self.cleanup_session(session)

        # Fermer le client Docker
        if self._docker_client:
            await self._docker_client.close()
            self._docker_client = None


# =============================================================================
# Factory
# =============================================================================


async def get_terminal_service() -> TerminalService:
    """
    Crée une instance du service terminal.

    Returns:
        TerminalService opérationnel
    """
    return TerminalService()
