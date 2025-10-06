"""
Commandes de gestion des déploiements pour le CLI WindFlow.
"""

import argparse
from typing import Optional
from cli.client import api_client
from cli.utils import print_success, print_error, print_info, print_json, print_table, format_timestamp, truncate


def setup_deploy_parser(subparsers) -> None:
    """Configure le parser pour les commandes de déploiement."""
    deploy_parser = subparsers.add_parser(
        'deploy',
        help='Gestion des déploiements'
    )
    deploy_subparsers = deploy_parser.add_subparsers(dest='deploy_action', help='Actions de déploiement')

    # Create
    create_parser = deploy_subparsers.add_parser('create', help='Créer un déploiement')
    create_parser.add_argument('--stack', required=True, help='ID du stack à déployer')
    create_parser.add_argument('--environment', required=True, help='ID de l\'environnement')
    create_parser.add_argument('--target', help='Type de cible (optionnel)')
    create_parser.add_argument('--name', help='Nom du déploiement (optionnel)')

    # List
    list_parser = deploy_subparsers.add_parser('list', help='Lister les déploiements')
    list_parser.add_argument('--environment', help='Filtrer par environnement')
    list_parser.add_argument('--status', help='Filtrer par statut')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table', help='Format de sortie')

    # Status
    status_parser = deploy_subparsers.add_parser('status', help='Statut d\'un déploiement')
    status_parser.add_argument('deployment_id', help='ID du déploiement')
    status_parser.add_argument('--format', choices=['table', 'json'], default='json', help='Format de sortie')

    # Logs
    logs_parser = deploy_subparsers.add_parser('logs', help='Logs d\'un déploiement')
    logs_parser.add_argument('deployment_id', help='ID du déploiement')
    logs_parser.add_argument('--tail', type=int, help='Nombre de lignes à afficher')
    logs_parser.add_argument('--follow', action='store_true', help='Suivre les logs en temps réel')


def handle_deploy_command(args) -> int:
    """Gère les commandes de déploiement."""
    if not hasattr(args, 'deploy_action') or args.deploy_action is None:
        print_error("Action de déploiement requise. Utilisez --help pour plus d'informations.")
        return 1

    try:
        if args.deploy_action == 'create':
            return handle_create(
                stack_id=args.stack,
                environment_id=args.environment,
                target=args.target,
                name=args.name
            )
        elif args.deploy_action == 'list':
            return handle_list(
                environment_id=args.environment,
                status=args.status,
                output_format=args.format
            )
        elif args.deploy_action == 'status':
            return handle_status(args.deployment_id, args.format)
        elif args.deploy_action == 'logs':
            return handle_logs(args.deployment_id, args.tail, args.follow)
        else:
            print_error(f"Action inconnue: {args.deploy_action}")
            return 1
    except Exception as e:
        print_error(f"Erreur lors de l'exécution de la commande: {e}")
        return 1


def handle_create(
    stack_id: str,
    environment_id: str,
    target: Optional[str] = None,
    name: Optional[str] = None
) -> int:
    """Crée un nouveau déploiement."""
    try:
        print_info("Création du déploiement en cours...")

        data = {
            "stack_id": stack_id,
            "environment_id": environment_id
        }

        if target:
            data["target_type"] = target
        if name:
            data["name"] = name

        deployment = api_client.post('/deployments', data)

        print_success("Déploiement créé avec succès!")
        print_info(f"ID: {deployment.get('id')}")
        print_info(f"Nom: {deployment.get('name', 'N/A')}")
        print_info(f"Statut: {deployment.get('status', 'N/A')}")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la création du déploiement: {e}")
        return 1


def handle_list(
    environment_id: Optional[str] = None,
    status: Optional[str] = None,
    output_format: str = 'table'
) -> int:
    """Liste les déploiements."""
    try:
        params = {}
        if environment_id:
            params['environment_id'] = environment_id
        if status:
            params['status'] = status

        response = api_client.get('/deployments', params=params)

        if output_format == 'json':
            print_json(response)
            return 0

        # Format tableau
        deployments = response if isinstance(response, list) else response.get('data', [])

        if not deployments:
            print_info("Aucun déploiement trouvé")
            return 0

        headers = ['ID', 'Nom', 'Stack', 'Statut', 'Créé le']
        rows = []

        for dep in deployments:
            rows.append([
                str(dep.get('id', 'N/A'))[:8] + '...',
                truncate(dep.get('name', 'N/A'), 30),
                truncate(dep.get('stack_name', 'N/A'), 20),
                dep.get('status', 'N/A'),
                format_timestamp(dep.get('created_at', 'N/A'))
            ])

        print_table(headers, rows)
        print_info(f"Total: {len(deployments)} déploiement(s)")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération des déploiements: {e}")
        return 1


def handle_status(deployment_id: str, output_format: str = 'json') -> int:
    """Affiche le statut d'un déploiement."""
    try:
        deployment = api_client.get(f'/deployments/{deployment_id}')

        if output_format == 'json':
            print_json(deployment)
            return 0

        # Format lisible
        print_info("Statut du déploiement:")
        print(f"  ID: {deployment.get('id', 'N/A')}")
        print(f"  Nom: {deployment.get('name', 'N/A')}")
        print(f"  Stack: {deployment.get('stack_name', 'N/A')}")
        print(f"  Environnement: {deployment.get('environment_name', 'N/A')}")
        print(f"  Statut: {deployment.get('status', 'N/A')}")
        print(f"  Type de cible: {deployment.get('target_type', 'N/A')}")
        print(f"  Créé le: {format_timestamp(deployment.get('created_at', 'N/A'))}")

        if deployment.get('started_at'):
            print(f"  Démarré le: {format_timestamp(deployment['started_at'])}")
        if deployment.get('completed_at'):
            print(f"  Terminé le: {format_timestamp(deployment['completed_at'])}")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération du statut: {e}")
        return 1


def handle_logs(deployment_id: str, tail: Optional[int] = None, follow: bool = False) -> int:
    """Affiche les logs d'un déploiement."""
    try:
        if follow:
            return handle_logs_follow(deployment_id, tail)

        params = {}
        if tail:
            params['tail'] = tail

        logs = api_client.get(f'/deployments/{deployment_id}/logs', params=params)

        if isinstance(logs, dict) and 'logs' in logs:
            log_lines = logs['logs']
        elif isinstance(logs, list):
            log_lines = logs
        else:
            log_lines = [str(logs)]

        for line in log_lines:
            print(line)

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la récupération des logs: {e}")
        return 1


def handle_logs_follow(deployment_id: str, tail: Optional[int] = None) -> int:
    """Suit les logs d'un déploiement en temps réel."""
    import time
    from cli.utils import console

    try:
        print_info(f"Suivi des logs pour le déploiement {deployment_id[:8]}...")
        print_info("Appuyez sur Ctrl+C pour arrêter")

        last_line_count = 0

        with console.status("[bold green]Récupération des logs...") as status:
            while True:
                try:
                    params = {}
                    if tail:
                        params['tail'] = tail

                    logs = api_client.get(f'/deployments/{deployment_id}/logs', params=params)

                    if isinstance(logs, dict) and 'logs' in logs:
                        log_lines = logs['logs']
                    elif isinstance(logs, list):
                        log_lines = logs
                    else:
                        log_lines = [str(logs)]

                    # Afficher uniquement les nouvelles lignes
                    if len(log_lines) > last_line_count:
                        new_lines = log_lines[last_line_count:]
                        for line in new_lines:
                            console.print(line)
                        last_line_count = len(log_lines)

                    # Attendre avant la prochaine requête
                    time.sleep(2)

                except KeyboardInterrupt:
                    print_info("\nSuivi des logs arrêté")
                    return 0
                except Exception as e:
                    print_error(f"Erreur lors du suivi des logs: {e}")
                    time.sleep(5)  # Attendre plus longtemps en cas d'erreur

    except Exception as e:
        print_error(f"Erreur lors du suivi des logs: {e}")
        return 1
