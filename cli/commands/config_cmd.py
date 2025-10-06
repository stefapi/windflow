"""
Commandes de configuration pour le CLI WindFlow.
"""

import argparse
from cli.config import config_manager
from cli.utils import print_success, print_error, print_info, print_json


def setup_config_parser(subparsers) -> None:
    """Configure le parser pour les commandes de configuration."""
    config_parser = subparsers.add_parser(
        'config',
        help='Gestion de la configuration'
    )
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='Actions de configuration')

    # Set URL
    set_url_parser = config_subparsers.add_parser('set-url', help='Définir l\'URL de l\'API')
    set_url_parser.add_argument('url', help='URL de l\'API WindFlow')

    # Get URL
    config_subparsers.add_parser('get-url', help='Afficher l\'URL de l\'API')

    # Show all config
    config_subparsers.add_parser('show', help='Afficher toute la configuration')

    # Set any value
    set_parser = config_subparsers.add_parser('set', help='Définir une valeur de configuration')
    set_parser.add_argument('key', help='Clé de configuration')
    set_parser.add_argument('value', help='Valeur')

    # Get any value
    get_parser = config_subparsers.add_parser('get', help='Récupérer une valeur de configuration')
    get_parser.add_argument('key', help='Clé de configuration')


def handle_config_command(args) -> int:
    """Gère les commandes de configuration."""
    if not hasattr(args, 'config_action') or args.config_action is None:
        print_error("Action de configuration requise. Utilisez --help pour plus d'informations.")
        return 1

    try:
        if args.config_action == 'set-url':
            return handle_set_url(args.url)
        elif args.config_action == 'get-url':
            return handle_get_url()
        elif args.config_action == 'show':
            return handle_show()
        elif args.config_action == 'set':
            return handle_set(args.key, args.value)
        elif args.config_action == 'get':
            return handle_get(args.key)
        else:
            print_error(f"Action inconnue: {args.config_action}")
            return 1
    except Exception as e:
        print_error(f"Erreur lors de l'exécution de la commande: {e}")
        return 1


def handle_set_url(url: str) -> int:
    """Définit l'URL de l'API."""
    try:
        config_manager.set('api_url', url)
        print_success(f"URL de l'API définie: {url}")
        return 0
    except Exception as e:
        print_error(f"Erreur lors de la définition de l'URL: {e}")
        return 1


def handle_get_url() -> int:
    """Affiche l'URL de l'API."""
    try:
        url = config_manager.get('api_url')
        print(url)
        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération de l'URL: {e}")
        return 1


def handle_show() -> int:
    """Affiche toute la configuration."""
    try:
        config = config_manager.show()
        print_info("Configuration actuelle:")
        print_json(config)
        return 0
    except Exception as e:
        print_error(f"Erreur lors de l'affichage de la configuration: {e}")
        return 1


def handle_set(key: str, value: str) -> int:
    """Définit une valeur de configuration."""
    try:
        # Conversion de type basique
        if value.lower() in ('true', 'false'):
            value = value.lower() == 'true'
        elif value.isdigit():
            value = int(value)

        config_manager.set(key, value)
        print_success(f"Configuration mise à jour: {key} = {value}")
        return 0
    except Exception as e:
        print_error(f"Erreur lors de la mise à jour de la configuration: {e}")
        return 1


def handle_get(key: str) -> int:
    """Récupère une valeur de configuration."""
    try:
        value = config_manager.get(key)
        if value is None:
            print_info(f"Clé non trouvée: {key}")
            return 1
        print(value)
        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération de la valeur: {e}")
        return 1
