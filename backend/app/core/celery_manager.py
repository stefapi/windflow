"""
Gestionnaire de worker Celery intégré.

Ce module permet de démarrer automatiquement un worker Celery local
lorsque Celery est activé mais qu'aucun worker externe n'est disponible.
"""

import asyncio
import logging
import subprocess
import signal
import sys
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddedCeleryWorker:
    """
    Gère un worker Celery intégré dans le processus backend.

    Le worker est lancé en subprocess et monitore son état.
    Redémarre automatiquement en cas de crash.
    """

    def __init__(
        self,
        concurrency: int = 2,
        pool: str = "solo",
        loglevel: str = "info",
        max_restart_attempts: int = 3
    ):
        """
        Initialise le gestionnaire de worker.

        Args:
            concurrency: Nombre de workers concurrents
            pool: Type de pool (solo, prefork, gevent, eventlet)
            loglevel: Niveau de log (debug, info, warning, error)
            max_restart_attempts: Nombre max de tentatives de redémarrage
        """
        self.concurrency = concurrency
        self.pool = pool
        self.loglevel = loglevel
        self.max_restart_attempts = max_restart_attempts

        self.process: Optional[subprocess.Popen] = None
        self.restart_count = 0
        self._running = False
        self._should_stop = False

    def _get_worker_command(self) -> List[str]:
        """
        Génère la commande pour lancer le worker Celery.

        Returns:
            Liste des arguments de la commande
        """
        # Déterminer le chemin vers celery
        celery_cmd = "celery"

        # Construire la commande
        cmd = [
            celery_cmd,
            "-A", "backend.app.celery_app",
            "worker",
            f"--concurrency={self.concurrency}",
            f"--pool={self.pool}",
            f"--loglevel={self.loglevel}",
            "--without-heartbeat",  # Pas de heartbeat requis
            "--without-mingle",     # Pas de sync avec autres workers
            "--without-gossip",     # Pas de broadcast
        ]

        return cmd

    async def start(self) -> bool:
        """
        Démarre le worker Celery en subprocess.

        Returns:
            True si le démarrage a réussi, False sinon
        """
        if self._running:
            logger.warning("Worker Celery déjà en cours d'exécution")
            return True

        try:
            cmd = self._get_worker_command()
            logger.info(f"Démarrage du worker Celery intégré: {' '.join(cmd)}")

            # Lancer le subprocess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            # Attendre un peu pour vérifier que le processus démarre
            await asyncio.sleep(2)

            # Vérifier que le processus est toujours vivant
            if self.process.poll() is not None:
                # Le processus s'est terminé
                stdout, stderr = self.process.communicate()
                logger.error(
                    f"Le worker Celery s'est arrêté immédiatement\n"
                    f"stdout: {stdout}\nstderr: {stderr}"
                )
                return False

            self._running = True
            self._should_stop = False
            logger.info(f"Worker Celery intégré démarré avec PID {self.process.pid}")

            # Démarrer la surveillance en arrière-plan
            asyncio.create_task(self._monitor_worker())

            return True

        except FileNotFoundError:
            logger.error(
                "Commande 'celery' non trouvée. "
                "Assurez-vous que Celery est installé dans l'environnement."
            )
            return False
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du worker Celery: {e}")
            return False

    async def _monitor_worker(self):
        """
        Surveille le worker et le redémarre si nécessaire.
        """
        while not self._should_stop:
            await asyncio.sleep(5)  # Vérifier toutes les 5 secondes

            if self.process and self.process.poll() is not None:
                # Le processus s'est arrêté
                if not self._should_stop:
                    logger.warning(
                        f"Worker Celery s'est arrêté inopinément (code: {self.process.returncode})"
                    )

                    # Tenter de redémarrer
                    if self.restart_count < self.max_restart_attempts:
                        self.restart_count += 1
                        logger.info(
                            f"Tentative de redémarrage {self.restart_count}/"
                            f"{self.max_restart_attempts}..."
                        )

                        self._running = False
                        await asyncio.sleep(2)  # Attendre un peu

                        if not await self.start():
                            logger.error("Échec du redémarrage du worker")
                            break
                    else:
                        logger.error(
                            f"Nombre max de tentatives de redémarrage atteint "
                            f"({self.max_restart_attempts})"
                        )
                        self._running = False
                        break

    async def stop(self, timeout: int = 10) -> bool:
        """
        Arrête proprement le worker Celery.

        Args:
            timeout: Timeout en secondes pour l'arrêt graceful

        Returns:
            True si l'arrêt a réussi
        """
        if not self._running or not self.process:
            logger.debug("Aucun worker à arrêter")
            return True

        self._should_stop = True
        logger.info(f"Arrêt du worker Celery (PID {self.process.pid})...")

        try:
            # Envoyer SIGTERM pour arrêt graceful
            self.process.send_signal(signal.SIGTERM)

            # Attendre que le processus se termine
            try:
                self.process.wait(timeout=timeout)
                logger.info("Worker Celery arrêté proprement")
            except subprocess.TimeoutExpired:
                # Le processus ne s'arrête pas, forcer avec SIGKILL
                logger.warning("Timeout - arrêt forcé du worker avec SIGKILL")
                self.process.kill()
                self.process.wait()

            self._running = False
            self.process = None
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du worker: {e}")
            return False

    def is_running(self) -> bool:
        """
        Vérifie si le worker est en cours d'exécution.

        Returns:
            True si le worker tourne
        """
        if not self._running or not self.process:
            return False

        # Vérifier que le processus est toujours vivant
        return self.process.poll() is None

    def get_info(self) -> dict:
        """
        Retourne les informations sur le worker.

        Returns:
            Dictionnaire avec les infos du worker
        """
        return {
            "running": self.is_running(),
            "pid": self.process.pid if self.process else None,
            "concurrency": self.concurrency,
            "pool": self.pool,
            "loglevel": self.loglevel,
            "restart_count": self.restart_count,
            "max_restart_attempts": self.max_restart_attempts
        }


async def should_start_embedded_worker() -> bool:
    """
    Détermine si un worker Celery intégré doit être démarré.

    Vérifie qu'aucun worker externe n'est déjà disponible.

    Returns:
        True si le worker intégré doit être démarré
    """
    from backend.app.celery_app import is_celery_available
    from backend.app.config import settings

    # Vérifier que Celery est activé
    if not settings.celery_enabled:
        logger.debug("Celery n'est pas activé - pas de worker intégré")
        return False

    # Vérifier que l'auto-start est activé
    if not settings.celery_auto_start_worker:
        logger.debug("Auto-start du worker désactivé")
        return False

    # Vérifier qu'aucun worker externe n'est disponible
    if is_celery_available(timeout=2.0):
        logger.info("Workers Celery externes détectés - pas besoin de worker intégré")
        return False

    logger.info("Aucun worker Celery externe détecté - démarrage du worker intégré")
    return True
