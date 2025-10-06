"""
Point d'entrée principal du CLI WindFlow.

Usage:
    windflow <command> [options]

Commandes disponibles:
    auth    - Gestion de l'authentification
    config  - Gestion de la configuration
    org     - Gestion des organisations
    deploy  - Gestion des déploiements
"""

import argparse
import sys
from cli import __version__
from cli.commands import (
    setup_auth_parser,
    handle_auth_command,
    setup_config_parser,
    handle_config_command,
    setup_org_parser,
    handle_org_command,
    setup_env_parser,
    handle_env_command,
    setup_deploy_parser,
    handle_deploy_command,
)
from cli.utils import print_error


def create_parser() -> argparse.ArgumentParser:
    """Crée le parser principal de commandes."""
    parser = argparse.ArgumentParser(
        prog='windflow',
        description='WindFlow CLI - Interface en ligne de commande pour WindFlow',
        epilog='Pour plus d\'informations sur une commande: windflow <command> --help'
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    # Sous-commandes
    subparsers = parser.add_subparsers(
        dest='command',
        help='Commande à exécuter'
    )

    # Configuration des parsers pour chaque commande
    setup_auth_parser(subparsers)
    setup_config_parser(subparsers)
    setup_org_parser(subparsers)
    setup_env_parser(subparsers)
    setup_deploy_parser(subparsers)

    return parser


def main() -> int:
    """Point d'entrée principal du CLI."""
    parser = create_parser()

    # Si aucun argument, afficher l'aide
    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    # Parser les arguments
    args = parser.parse_args()

    # Vérifier qu'une commande a été fournie
    if not args.command:
        parser.print_help()
        return 1

    # Router vers le gestionnaire approprié
    try:
        if args.command == 'auth':
            return handle_auth_command(args)
        elif args.command == 'config':
            return handle_config_command(args)
        elif args.command == 'org':
            return handle_org_command(args)
        elif args.command == 'env':
            return handle_env_command(args)
        elif args.command == 'deploy':
            return handle_deploy_command(args)
        else:
            print_error(f"Commande inconnue: {args.command}")
            return 1
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur")
        return 130
    except Exception as e:
        print_error(f"Erreur inattendue: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
