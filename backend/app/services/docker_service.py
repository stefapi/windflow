"""
Service pour gestion des déploiements Docker containers simples.

Gère les containers Docker uniques (pas docker-compose) avec substitution
de variables, génération de mots de passe, et gestion complète du cycle de vie.
"""

import re
import subprocess
import logging
from typing import Dict, Any, Optional, Tuple, List

from backend.app.helper.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)


class DockerService:
    """Service de gestion des containers Docker simples."""

    def __init__(self):
        """Initialise le service avec le renderer de templates."""
        self.renderer = TemplateRenderer()

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

        Args:
            config: Configuration du container
            container_name: Nom du container (override)

        Returns:
            Tuple[bool, str]: (Succès, Container ID ou Message d'erreur)
        """
        try:
            # Construire la commande
            cmd = self.build_docker_run_command(config, container_name)

            # Exécuter la commande
            logger.info(f"Exécution: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            if result.returncode == 0:
                container_id = result.stdout.strip()
                logger.info(f"Container déployé avec succès: {container_id}")
                return True, container_id
            else:
                error_msg = result.stderr.strip()
                logger.error(f"Échec du déploiement: {error_msg}")
                return False, error_msg

        except subprocess.TimeoutExpired:
            error_msg = "Timeout lors du déploiement (> 5 minutes)"
            logger.error(error_msg)
            return False, error_msg

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
            # Utiliser docker inspect pour récupérer les infos
            cmd = ['docker', 'inspect', container_name]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                import json
                container_info = json.loads(result.stdout)[0]

                # Extraire les informations pertinentes
                status_info = {
                    "id": container_info['Id'],
                    "name": container_info['Name'].lstrip('/'),
                    "image": container_info['Config']['Image'],
                    "state": container_info['State']['Status'],
                    "running": container_info['State']['Running'],
                    "started_at": container_info['State']['StartedAt'],
                    "health": container_info['State'].get('Health', {}).get('Status', 'none'),
                    "restart_count": container_info['RestartCount']
                }

                return True, status_info
            else:
                return False, {'error': result.stderr.strip()}

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
            cmd = ['docker', 'stop', '-t', str(timeout), container_name]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )

            if result.returncode == 0:
                logger.info(f"Container arrêté: {container_name}")
                return True, f"Container {container_name} arrêté"
            else:
                error_msg = result.stderr.strip()
                logger.error(f"Échec arrêt: {error_msg}")
                return False, error_msg

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
            cmd = ['docker', 'rm']
            if force:
                cmd.append('-f')
            if remove_volumes:
                cmd.append('-v')  # Supprime les volumes anonymes associés
            cmd.append(container_name)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Container supprimé: {container_name}")
                return True, f"Container {container_name} supprimé"
            else:
                error_msg = result.stderr.strip()
                logger.error(f"Échec suppression: {error_msg}")
                return False, error_msg

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
            cmd = ['docker', 'logs', '--tail', str(tail)]

            if since:
                cmd.extend(['--since', since])

            cmd.append(container_name)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # docker logs peut mettre les logs sur stderr aussi
                logs = result.stdout + result.stderr
                return True, logs
            else:
                return False, result.stderr.strip()

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
            cmd = ['docker', 'restart', '-t', str(timeout), container_name]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5
            )

            if result.returncode == 0:
                logger.info(f"Container redémarré: {container_name}")
                return True, f"Container {container_name} redémarré"
            else:
                error_msg = result.stderr.strip()
                logger.error(f"Échec redémarrage: {error_msg}")
                return False, error_msg

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
            cmd = ['docker', 'volume', 'rm']
            if force:
                cmd.append('-f')
            cmd.append(volume_name)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Volume supprimé: {volume_name}")
                return True, f"Volume {volume_name} supprimé"
            else:
                error_msg = result.stderr.strip()
                # Si le volume n'existe pas, considérer comme succès
                if "no such volume" in error_msg.lower() or "not found" in error_msg.lower():
                    logger.warning(f"Volume {volume_name} n'existe pas, considéré comme supprimé")
                    return True, f"Volume {volume_name} n'existe pas (déjà supprimé)"
                logger.error(f"Échec suppression volume: {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = f"Erreur lors de la suppression du volume: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
