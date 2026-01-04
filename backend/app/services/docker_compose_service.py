"""
Service pour gestion des templates Docker Compose.

Substitution de variables, génération de fichiers compose et déploiement.
"""

import re
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import subprocess
import logging

from backend.app.helper.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)


class DockerComposeService:
    """Service de gestion Docker Compose."""

    def __init__(self):
        """Initialise le service avec le renderer de templates."""
        self.renderer = TemplateRenderer()

    def substitute_variables(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Substitue les variables dans le template Docker Compose.

        Utilise le TemplateRenderer centralisé qui supporte toutes les
        fonctions Jinja2 disponibles (generate_password, generate_secret, etc.)

        Args:
            template: Template Docker Compose en format dict
            variables: Dictionnaire des valeurs de variables

        Returns:
            Template avec variables substituées

        Example:
            >>> service = DockerComposeService()
            >>> template = {"services": {"app": {"image": "{{ app_image }}"}}}
            >>> variables = {"app_image": "nginx:latest"}
            >>> result = service.substitute_variables(template, variables)
            >>> result["services"]["app"]["image"]
            'nginx:latest'
        """
        return self.renderer.render_dict(template, variables)

    def validate_compose(self, compose_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Valide un fichier docker-compose.

        Args:
            compose_data: Données du compose à valider

        Returns:
            Tuple[bool, Optional[str]]: (Valide, Message d'erreur)
        """
        try:
            # Vérifier la version
            if 'version' not in compose_data:
                return False, "Version du compose manquante"

            # Vérifier qu'il y a des services
            if 'services' not in compose_data or not compose_data['services']:
                return False, "Aucun service défini"

            # Vérifier que chaque service a une image ou un build
            for service_name, service_config in compose_data['services'].items():
                if not isinstance(service_config, dict):
                    return False, f"Service {service_name} invalide"

                if 'image' not in service_config and 'build' not in service_config:
                    return False, f"Service {service_name} doit avoir 'image' ou 'build'"

            return True, None

        except Exception as e:
            return False, f"Erreur de validation: {str(e)}"

    def generate_compose_file(
        self,
        compose_data: Dict[str, Any],
        output_path: Path
    ) -> Path:
        """
        Génère un fichier docker-compose.yml.

        Args:
            compose_data: Données du compose
            output_path: Chemin du fichier de sortie

        Returns:
            Path du fichier généré
        """
        # Créer le répertoire parent si nécessaire
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Écrire le fichier YAML
        with open(output_path, 'w') as f:
            yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Fichier docker-compose généré: {output_path}")
        return output_path

    async def deploy_compose(
        self,
        compose_file: Path,
        project_name: str,
        env_vars: Optional[Dict[str, str]] = None
    ) -> tuple[bool, str]:
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
            # Construire la commande (Docker Compose V2)
            cmd = [
                'docker', 'compose',
                '-f', str(compose_file),
                '-p', project_name,
                'up', '-d'
            ]

            # Préparer l'environnement
            import os
            env = os.environ.copy()
            if env_vars:
                env.update(env_vars)

            # Exécuter la commande
            logger.info(f"Exécution: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=300  # 5 minutes max
            )

            if result.returncode == 0:
                logger.info(f"Déploiement réussi: {project_name}")
                return True, result.stdout
            else:
                logger.error(f"Échec du déploiement: {result.stderr}")
                return False, result.stderr

        except subprocess.TimeoutExpired:
            error_msg = "Timeout lors du déploiement (> 5 minutes)"
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Erreur lors du déploiement: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def get_compose_status(
        self,
        project_name: str
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Récupère le statut d'un projet Docker Compose.

        Args:
            project_name: Nom du projet

        Returns:
            Tuple[bool, Dict]: (Succès, Statut des services)
        """
        try:
            cmd = ['docker', 'compose', '-p', project_name, 'ps', '--format', 'json']

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parser le JSON output
                import json
                services = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        services.append(json.loads(line))

                return True, {'services': services}
            else:
                return False, {'error': result.stderr}

        except Exception as e:
            logger.error(f"Erreur récupération statut: {e}")
            return False, {'error': str(e)}

    async def stop_compose(
        self,
        project_name: str
    ) -> tuple[bool, str]:
        """
        Arrête un projet Docker Compose.

        Args:
            project_name: Nom du projet

        Returns:
            Tuple[bool, str]: (Succès, Output/Error)
        """
        try:
            cmd = ['docker', 'compose', '-p', project_name, 'down']

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"Projet arrêté: {project_name}")
                return True, result.stdout
            else:
                logger.error(f"Échec arrêt: {result.stderr}")
                return False, result.stderr

        except Exception as e:
            error_msg = f"Erreur lors de l'arrêt: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def remove_compose(
        self,
        project_name: str,
        remove_volumes: bool = True
    ) -> tuple[bool, str]:
        """
        Supprime complètement un projet Docker Compose (conteneurs, réseaux, volumes).

        Args:
            project_name: Nom du projet
            remove_volumes: Si True, supprime aussi les volumes (défaut: True)

        Returns:
            Tuple[bool, str]: (Succès, Output/Error)
        """
        try:
            cmd = ['docker', 'compose', '-p', project_name, 'down']

            if remove_volumes:
                cmd.append('-v')  # Supprime aussi les volumes

            cmd.append('--remove-orphans')  # Supprime les conteneurs orphelins

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Projet supprimé complètement: {project_name}")
                return True, result.stdout
            else:
                logger.error(f"Échec suppression: {result.stderr}")
                return False, result.stderr

        except Exception as e:
            error_msg = f"Erreur lors de la suppression: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def get_compose_logs(
        self,
        project_name: str,
        service: Optional[str] = None,
        tail: int = 100
    ) -> tuple[bool, str]:
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
            cmd = ['docker', 'compose', '-p', project_name, 'logs', '--tail', str(tail)]

            if service:
                cmd.append(service)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr

        except Exception as e:
            logger.error(f"Erreur récupération logs: {e}")
            return False, str(e)

    def extract_variables_from_compose(
        self,
        compose_data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extrait les variables d'un template docker-compose.

        Détecte les patterns {{ variable_name }} et {{ variable_name:-default }}

        Args:
            compose_data: Template docker-compose

        Returns:
            Dictionnaire des variables détectées avec métadonnées
        """
        # Convertir en YAML string
        yaml_str = yaml.dump(compose_data, default_flow_style=False)

        # Pattern pour détecter {{ variable_name }} ou {{ variable_name:-default }}
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::-([^}]+))?\s*\}\}'

        variables = {}
        for match in re.finditer(pattern, yaml_str):
            var_name = match.group(1)
            default_value = match.group(2)

            if var_name not in variables:
                # Déterminer le type basé sur le nom
                var_type = self._guess_variable_type(var_name, default_value)

                variables[var_name] = {
                    'type': var_type,
                    'label': var_name.replace('_', ' ').title(),
                    'required': default_value is None,
                }

                if default_value:
                    variables[var_name]['default'] = default_value.strip()

                # Ajouter generate=True pour les passwords
                if 'password' in var_name.lower() or 'secret' in var_name.lower():
                    variables[var_name]['generate'] = True
                    variables[var_name]['min_length'] = 12

        return variables

    def _guess_variable_type(self, var_name: str, default_value: Optional[str]) -> str:
        """
        Devine le type d'une variable basé sur son nom et valeur par défaut.

        Args:
            var_name: Nom de la variable
            default_value: Valeur par défaut

        Returns:
            Type de variable ('string', 'number', 'boolean', 'password', 'select')
        """
        var_name_lower = var_name.lower()

        # Password/secret
        if 'password' in var_name_lower or 'secret' in var_name_lower or 'key' in var_name_lower:
            return 'password'

        # Boolean
        if 'enable' in var_name_lower or 'debug' in var_name_lower:
            return 'boolean'

        # Number
        if any(word in var_name_lower for word in ['port', 'count', 'size', 'limit', 'workers', 'replicas']):
            return 'number'

        # Select (si plusieurs valeurs possibles détectées)
        if default_value and '|' in default_value:
            return 'select'

        # Default
        return 'string'
