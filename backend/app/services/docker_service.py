"""
Service pour gestion des déploiements Docker containers simples.

Gère les containers Docker uniques (pas docker-compose) avec substitution
de variables, génération de mots de passe, et gestion complète du cycle de vie.

 utilise DockerExecutor pour l'exécution (CLI avec fallback socket).
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple, List

from backend.app.helper.template_renderer import TemplateRenderer
from backend.app.services.docker_executor import DockerExecutor, get_docker_executor

logger = logging.getLogger(__name__)


class DockerService:
    """Service de gestion des containers Docker simples."""

    def __init__(self, executor: Optional[DockerExecutor] = None):
        """Initialise le service avec le renderer de templates et l'exécuteur Docker.

        Args:
            executor: Instance de DockerExecutor (optionnel, sera créé si non fourni)
        """
        self.renderer = TemplateRenderer()
        self._executor = executor

    @property
    def executor(self) -> DockerExecutor:
        """Récupère l'exécuteur Docker (lazy initialization)."""
        if self._executor is None:
            self._executor = DockerExecutor()
        return self._executor

    @executor.setter
    def executor(self, value: DockerExecutor) -> None:
        """Définit l'exécuteur Docker."""
        self._executor = value

    def substitute_variables(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Substitue les variables dans le template container avec support
        des fonctions Jinja2 personnalisées.

        Utilise le TemplateRenderer centralisé qui supporte toutes les
        fonctions Jinja2 disponibles (generate_password, generate_secret, etc.)

        Args:
            template: Template container en format dict
            variables: Dictionnaire des valeurs de variables

        Returns:
            Template avec variables substituées

        Example:
            >>> service = DockerService()
            >>> template = {"environment": {"POSTGRES_PASSWORD": "{{ generate_password(24) }}"}}
            >>> result = service.substitute_variables(template, {})
            >>> len(result["environment"]["POSTGRES_PASSWORD"])
            24
        """
        return self.renderer.render_dict(template, variables)

    def validate_container_config(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Valide une configuration de container Docker.

        Args:
            config: Configuration du container à valider

        Returns:
            Tuple[bool, Optional[str]]: (Valide, Message d'erreur)
        """
        try:
            # Vérifier qu'il y a une image
            if 'image' not in config:
                return False, "Image Docker manquante"

            # Vérifier le format de l'image
            image = config['image']
            if not isinstance(image, str) or not image.strip():
                return False, "Image Docker invalide"

            # Vérifier le container_name si présent
            if 'container_name' in config:
                container_name = config['container_name']
                if not isinstance(container_name, str) or not container_name.strip():
                    return False, "Nom du container invalide"

                # Valider le format du nom (alphanumérique, -, _)
                if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$', container_name):
                    return False, "Nom du container doit être alphanumérique (-, _ autorisés)"

            # Vérifier les ports si présents
            if 'ports' in config and config['ports']:
                if not isinstance(config['ports'], list):
                    return False, "Les ports doivent être une liste"

                for port_mapping in config['ports']:
                    if not isinstance(port_mapping, str):
                        return False, f"Mapping de port invalide: {port_mapping}"

                    # Vérifier le format "host_port:container_port"
                    if ':' not in port_mapping:
                        return False, f"Format de port invalide: {port_mapping} (attendu: host:container)"

            # Vérifier les variables d'environnement si présentes
            if 'environment' in config and config['environment']:
                if not isinstance(config['environment'], dict):
                    return False, "Les variables d'environnement doivent être un dictionnaire"

            # Vérifier les volumes si présents
            if 'volumes' in config and config['volumes']:
                if not isinstance(config['volumes'], list):
                    return False, "Les volumes doivent être une liste"

            return True, None

        except Exception as e:
            return False, f"Erreur de validation: {str(e)}"

    def build_docker_run_command(
        self,
        config: Dict[str, Any],
        container_name: Optional[str] = None
    ) -> List[str]:
        """
        Construit la commande docker run à partir de la configuration.

        Args:
            config: Configuration du container
            container_name: Nom du container (override celui dans config)

        Returns:
            Liste des arguments de la commande docker run

        Example:
            >>> config = {
            ...     "image": "postgres:16",
            ...     "container_name": "postgres_db",
            ...     "environment": {"POSTGRES_USER": "admin"},
            ...     "ports": ["5432:5432"]
            ... }
            >>> cmd = DockerService.build_docker_run_command(config)
            >>> cmd[0:2]
            ['docker', 'run']
        """
        cmd = ['docker', 'run', '-d']  # -d pour mode detached

        # Nom du container
        name = container_name or config.get('container_name')
        if name:
            cmd.extend(['--name', name])

        # Variables d'environnement
        env_vars = config.get('environment', {})
        for key, value in env_vars.items():
            cmd.extend(['-e', f"{key}={value}"])

        # Ports
        ports = config.get('ports', [])
        for port_mapping in ports:
            cmd.extend(['-p', port_mapping])

        # Volumes
        volumes = config.get('volumes', [])
        for volume_mapping in volumes:
            cmd.extend(['-v', volume_mapping])

        # Restart policy
        restart_policy = config.get('restart_policy', 'unless-stopped')
        cmd.extend(['--restart', restart_policy])

        # Health check (optionnel)
        healthcheck = config.get('healthcheck')
        if healthcheck and isinstance(healthcheck, dict):
            test = healthcheck.get('test')
            if test:
                # Le test est parfois une liste comme ["CMD-SHELL", "pg_isready"]
                if isinstance(test, list):
                    test_str = ' '.join(test[1:]) if test[0] == 'CMD-SHELL' else ' '.join(test)
                else:
                    test_str = str(test)

                cmd.extend(['--health-cmd', test_str])

            if 'interval' in healthcheck:
                cmd.extend(['--health-interval', healthcheck['interval']])

            if 'timeout' in healthcheck:
                cmd.extend(['--health-timeout', healthcheck['timeout']])

            if 'retries' in healthcheck:
                cmd.extend(['--health-retries', str(healthcheck['retries'])])

            if 'start_period' in healthcheck:
                cmd.extend(['--health-start-period', healthcheck['start_period']])

        # Labels
        labels = config.get('labels', {})
        for key, value in labels.items():
            cmd.extend(['--label', f"{key}={value}"])

        # Image (doit être à la fin)
        cmd.append(config['image'])

        return cmd

    async def deploy_container(
        self,
        config: Dict[str, Any],
        container_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Déploie un container Docker.

        Utilise DockerExecutor qui essaie CLI en premier, puis socket en fallback.

        Args:
            config: Configuration du container
            container_name: Nom du container (override)

        Returns:
            Tuple[bool, str]: (Succès, Container ID ou Message d'erreur)
        """
        try:
            return await self.executor.deploy_container(config, container_name)
        except Exception as e:
            error_msg = f"Erreur lors du déploiement: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def get_container_status(
        self,
        container_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Récupère le statut d'un container Docker.

        Args:
            container_name: Nom ou ID du container

        Returns:
            Tuple[bool, Dict]: (Succès, Informations du container)
        """
        try:
            return await self.executor.get_container_status(container_name)
        except Exception as e:
            logger.error(f"Erreur récupération statut: {e}")
            return False, {'error': str(e)}

    async def stop_container(
        self,
        container_name: str,
        timeout: int = 10
    ) -> Tuple[bool, str]:
        """
        Arrête un container Docker.

        Args:
            container_name: Nom ou ID du container
            timeout: Timeout en secondes avant kill forcé

        Returns:
            Tuple[bool, str]: (Succès, Message)
        """
        try:
            return await self.executor.stop_container(container_name, timeout)
        except Exception as e:
            error_msg = f"Erreur lors de l'arrêt: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def remove_container(
        self,
        container_name: str,
        force: bool = False,
        remove_volumes: bool = True
    ) -> Tuple[bool, str]:
        """
        Supprime un container Docker.

        Args:
            container_name: Nom ou ID du container
            force: Forcer la suppression même si running
            remove_volumes: Supprimer les volumes anonymes associés (défaut: True)

        Returns:
            Tuple[bool, str]: (Succès, Message)
        """
        try:
            return await self.executor.remove_container(container_name, force, remove_volumes)
        except Exception as e:
            error_msg = f"Erreur lors de la suppression: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def get_container_logs(
        self,
        container_name: str,
        tail: int = 100,
        since: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Récupère les logs d'un container Docker.

        Args:
            container_name: Nom ou ID du container
            tail: Nombre de lignes à récupérer
            since: Timestamp depuis lequel récupérer les logs (optionnel)

        Returns:
            Tuple[bool, str]: (Succès, Logs)
        """
        try:
            return await self.executor.get_container_logs(container_name, tail, since)
        except Exception as e:
            logger.error(f"Erreur récupération logs: {e}")
            return False, str(e)

    async def restart_container(
        self,
        container_name: str,
        timeout: int = 10
    ) -> Tuple[bool, str]:
        """
        Redémarre un container Docker.

        Args:
            container_name: Nom ou ID du container
            timeout: Timeout en secondes

        Returns:
            Tuple[bool, str]: (Succès, Message)
        """
        try:
            return await self.executor.restart_container(container_name, timeout)
        except Exception as e:
            error_msg = f"Erreur lors du redémarrage: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def remove_volume(
        self,
        volume_name: str,
        force: bool = False
    ) -> Tuple[bool, str]:
        """
        Supprime un volume Docker nommé.

        Args:
            volume_name: Nom du volume Docker
            force: Forcer la suppression même si le volume est utilisé

        Returns:
            Tuple[bool, str]: (Succès, Message)
        """
        try:
            return await self.executor.remove_volume(volume_name, force)
        except Exception as e:
            error_msg = f"Erreur lors de la suppression du volume: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
