"""
Commandes d'authentification pour le CLI WindFlow.
"""

import argparse
import sys
from cli.client import api_client
from cli.session import session
from cli.utils import print_success, print_error, print_info, print_json


def setup_auth_parser(subparsers) -> None:
    """Configure le parser pour les commandes d'authentification."""
    auth_parser = subparsers.add_parser(
        'auth',
        help='Gestion de l\'authentification'
    )
    auth_subparsers = auth_parser.add_subparsers(dest='auth_action', help='Actions d\'authentification')

    # Login
    login_parser = auth_subparsers.add_parser('login', help='Se connecter à WindFlow')
    login_parser.add_argument('--username', required=True, help='Nom d\'utilisateur')
    login_parser.add_argument('--password', required=True, help='Mot de passe')

    # Logout
    auth_subparsers.add_parser('logout', help='Se déconnecter')

    # Status
    auth_subparsers.add_parser('status', help='Vérifier le statut d\'authentification')


def handle_auth_command(args) -> int:
    """Gère les commandes d'authentification."""
    if not hasattr(args, 'auth_action') or args.auth_action is None:
        print_error("Action d'authentification requise. Utilisez --help pour plus d'informations.")
        return 1

    try:
        if args.auth_action == 'login':
            return handle_login(args.username, args.password)
        elif args.auth_action == 'logout':
            return handle_logout()
        elif args.auth_action == 'status':
            return handle_status()
        else:
            print_error(f"Action inconnue: {args.auth_action}")
            return 1
    except Exception as e:
        print_error(f"Erreur lors de l'exécution de la commande: {e}")
        return 1


def handle_login(username: str, password: str) -> int:
    """Gère la connexion utilisateur."""
    try:
        print_info(f"Connexion en tant que {username}...")
        result = api_client.login(username, password)

        user_info = session.get_user_info()
        if user_info:
            print_success(f"Connecté avec succès en tant que {user_info.get('username', username)}")
            print_info(f"Email: {user_info.get('email', 'N/A')}")
            if user_info.get('is_superadmin'):
                print_info("Privilèges: Super Admin")
        else:
            print_success("Connecté avec succès")

        return 0
    except Exception as e:
        print_error(f"Échec de la connexion: {e}")
        return 1


def handle_logout() -> int:
    """Gère la déconnexion utilisateur."""
    try:
        if not session.is_authenticated():
            print_info("Vous n'êtes pas connecté")
            return 0

        api_client.logout()
        print_success("Déconnecté avec succès")
        return 0
    except Exception as e:
        print_error(f"Erreur lors de la déconnexion: {e}")
        return 1


def handle_status() -> int:
    """Affiche le statut d'authentification."""
    try:
        if session.is_authenticated():
            user_info = session.get_user_info()
            if user_info:
                print_success("Authentifié")
                print_info(f"Utilisateur: {user_info.get('username', 'N/A')}")
                print_info(f"Email: {user_info.get('email', 'N/A')}")
                print_info(f"ID: {user_info.get('id', 'N/A')}")
                if user_info.get('is_superadmin'):
                    print_info("Rôle: Super Admin")
            else:
                print_success("Authentifié (informations utilisateur non disponibles)")
        else:
            print_info("Non authentifié")
            print_info("Utilisez 'windflow auth login' pour vous connecter")

        return 0
    except Exception as e:
        print_error(f"Erreur lors de la vérification du statut: {e}")
        return 1
