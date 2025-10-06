"""
Commandes de gestion des organisations pour le CLI WindFlow.
"""

import argparse
from cli.client import api_client
from cli.utils import print_success, print_error, print_info, print_json, print_table, format_timestamp


def setup_org_parser(subparsers) -> None:
    """Configure le parser pour les commandes d'organisation."""
    org_parser = subparsers.add_parser(
        'org',
        help='Gestion des organisations'
    )
    org_subparsers = org_parser.add_subparsers(dest='org_action', help='Actions sur les organisations')

    # List
    list_parser = org_subparsers.add_parser('list', help='Lister les organisations')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Format de sortie')

    # Get
    get_parser = org_subparsers.add_parser('get', help='Détails d\'une organisation')
    get_parser.add_argument('org_id', help='ID de l\'organisation')
    get_parser.add_argument('--format', choices=['table', 'json'], default='json', help='Format de sortie')


def handle_org_command(args) -> int:
    """Gère les commandes d'organisation."""
    if not hasattr(args, 'org_action') or args.org_action is None:
        print_error("Action d'organisation requise. Utilisez --help pour plus d'informations.")
        return 1

    try:
        if args.org_action == 'list':
            return handle_list(args.format)
        elif args.org_action == 'get':
            return handle_get(args.org_id, args.format)
        else:
            print_error(f"Action inconnue: {args.org_action}")
            return 1
    except Exception as e:
        print_error(f"Erreur lors de l'exécution de la commande: {e}")
        return 1


def handle_list(output_format: str = 'table') -> int:
    """Liste toutes les organisations."""
    try:
        response = api_client.get('/organizations')

        if output_format == 'json':
            print_json(response)
            return 0

        # Format tableau
        organizations = response if isinstance(response, list) else response.get('data', [])

        if not organizations:
            print_info("Aucune organisation trouvée")
            return 0

        headers = ['ID', 'Nom', 'Slug', 'Actif', 'Créé le']
        rows = []

        for org in organizations:
            rows.append([
                str(org.get('id', 'N/A'))[:8] + '...',
                org.get('name', 'N/A'),
                org.get('slug', 'N/A'),
                '✓' if org.get('is_active', True) else '✗',
                format_timestamp(org.get('created_at', 'N/A'))
            ])

        print_table(headers, rows)
        print_info(f"Total: {len(organizations)} organisation(s)")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération des organisations: {e}")
        return 1


def handle_get(org_id: str, output_format: str = 'json') -> int:
    """Affiche les détails d'une organisation."""
    try:
        org = api_client.get(f'/organizations/{org_id}')

        if output_format == 'json':
            print_json(org)
            return 0

        # Format lisible
        print_info("Détails de l'organisation:")
        print(f"  ID: {org.get('id', 'N/A')}")
        print(f"  Nom: {org.get('name', 'N/A')}")
        print(f"  Slug: {org.get('slug', 'N/A')}")
        print(f"  Description: {org.get('description', 'N/A')}")
        print(f"  Actif: {'Oui' if org.get('is_active', True) else 'Non'}")
        print(f"  Créé le: {format_timestamp(org.get('created_at', 'N/A'))}")
        print(f"  Modifié le: {format_timestamp(org.get('updated_at', 'N/A'))}")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération de l'organisation: {e}")
        return 1
