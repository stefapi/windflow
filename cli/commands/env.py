"""
Commandes de gestion des environnements pour le CLI WindFlow.
"""

import argparse
from cli.client import api_client
from cli.utils import (
    print_success, print_error, print_info, print_json,
    print_table, format_timestamp, truncate
)


def setup_env_parser(subparsers) -> None:
    """Configure le parser pour les commandes d'environnement."""
    env_parser = subparsers.add_parser(
        'env',
        help='Gestion des environnements'
    )
    env_subparsers = env_parser.add_subparsers(dest='env_action', help='Actions sur les environnements')

    # List
    list_parser = env_subparsers.add_parser('list', help='Lister les environnements')
    list_parser.add_argument('--org', help='Filtrer par organisation')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Format de sortie')

    # Get
    get_parser = env_subparsers.add_parser('get', help='Détails d\'un environnement')
    get_parser.add_argument('env_id', help='ID de l\'environnement')
    get_parser.add_argument('--format', choices=['table', 'json'], default='json', help='Format de sortie')

    # Create
    create_parser = env_subparsers.add_parser('create', help='Créer un environnement')
    create_parser.add_argument('--name', required=True, help='Nom de l\'environnement')
    create_parser.add_argument('--org', required=True, help='ID de l\'organisation')
    create_parser.add_argument('--type', choices=['development', 'staging', 'production'],
                               default='development', help='Type d\'environnement')

    # Delete
    delete_parser = env_subparsers.add_parser('delete', help='Supprimer un environnement')
    delete_parser.add_argument('env_id', help='ID de l\'environnement')
    delete_parser.add_argument('--confirm', action='store_true', help='Confirmer la suppression')


def handle_env_command(args) -> int:
    """Gère les commandes d'environnement."""
    if not hasattr(args, 'env_action') or args.env_action is None:
        print_error("Action d'environnement requise. Utilisez --help pour plus d'informations.")
        return 1

    try:
        if args.env_action == 'list':
            return handle_list(args.org, args.format)
        elif args.env_action == 'get':
            return handle_get(args.env_id, args.format)
        elif args.env_action == 'create':
            return handle_create(args.name, args.org, args.type)
        elif args.env_action == 'delete':
            return handle_delete(args.env_id, args.confirm)
        else:
            print_error(f"Action inconnue: {args.env_action}")
            return 1
    except Exception as e:
        print_error(f"Erreur lors de l'exécution de la commande: {e}")
        return 1


def handle_list(org_id: str = None, output_format: str = 'table') -> int:
    """Liste tous les environnements."""
    try:
        params = {}
        if org_id:
            params['organization_id'] = org_id

        response = api_client.get('/environments', params=params)

        if output_format == 'json':
            print_json(response)
            return 0

        # Format tableau
        environments = response if isinstance(response, list) else response.get('data', [])

        if not environments:
            print_info("Aucun environnement trouvé")
            return 0

        headers = ['ID', 'Nom', 'Type', 'Organisation', 'Créé le']
        rows = []

        for env in environments:
            rows.append([
                str(env.get('id', 'N/A'))[:8] + '...',
                truncate(env.get('name', 'N/A'), 30),
                env.get('type', 'N/A'),
                truncate(env.get('organization_name', 'N/A'), 20),
                format_timestamp(env.get('created_at', 'N/A'))
            ])

        print_table(headers, rows)
        print_info(f"Total: {len(environments)} environnement(s)")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération des environnements: {e}")
        return 1


def handle_get(env_id: str, output_format: str = 'json') -> int:
    """Affiche les détails d'un environnement."""
    try:
        env = api_client.get(f'/environments/{env_id}')

        if output_format == 'json':
            print_json(env)
            return 0

        # Format lisible
        print_info("Détails de l'environnement:")
        print(f"  ID: {env.get('id', 'N/A')}")
        print(f"  Nom: {env.get('name', 'N/A')}")
        print(f"  Type: {env.get('type', 'N/A')}")
        print(f"  Organisation: {env.get('organization_name', 'N/A')}")
        print(f"  Créé le: {format_timestamp(env.get('created_at', 'N/A'))}")
        print(f"  Modifié le: {format_timestamp(env.get('updated_at', 'N/A'))}")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération de l'environnement: {e}")
        return 1


def handle_create(name: str, org_id: str, env_type: str) -> int:
    """Crée un nouvel environnement."""
    try:
        print_info(f"Création de l'environnement '{name}'...")

        data = {
            "name": name,
            "organization_id": org_id,
            "type": env_type
        }

        env = api_client.post('/environments', data)

        print_success("Environnement créé avec succès!")
        print_info(f"ID: {env.get('id')}")
        print_info(f"Nom: {env.get('name')}")
        print_info(f"Type: {env.get('type')}")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la création de l'environnement: {e}")
        return 1


def handle_delete(env_id: str, confirm: bool = False) -> int:
    """Supprime un environnement."""
    try:
        if not confirm:
            from cli.utils import confirm as ask_confirm
            if not ask_confirm(f"Voulez-vous vraiment supprimer l'environnement {env_id} ?"):
                print_info("Suppression annulée")
                return 0

        api_client.delete(f'/environments/{env_id}')
        print_success("Environnement supprimé avec succès")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la suppression de l'environnement: {e}")
        return 1
