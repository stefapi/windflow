"""
Classe de base pour les services CLI modulaires.

Permet d'étendre facilement le CLI avec de nouveaux services suivant un pattern cohérent.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import argparse


class CLIServiceBase(ABC):
    """
    Classe de base pour tous les services CLI.

    Cette classe définit l'interface que tous les services CLI doivent implémenter
    pour être intégrés de manière cohérente dans WindFlow CLI.

    Exemple d'utilisation:
        class MonService(CLIServiceBase):
            commands = ["mon-service", "ms"]
            default_config = {"option": "valeur"}

            def subparser(self, parser):
                service_parser = parser.add_parser('mon-service')
                service_parser.add_argument('--option', help='Description')

            def handle_command(self, args):
                # Logique du service
                return 0
    """

    # Liste des noms de commandes gérées par ce service
    commands: List[str] = []

    # Configuration par défaut du service
    default_config: Dict[str, Any] = {}

    # Liens entre paramètres (pour compatibilité entre versions)
    params_link: Dict[str, Any] = {}

    @abstractmethod
    def subparser(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure le sous-parser pour ce service.

        Args:
            parser: Parser argparse parent où ajouter le sous-parser

        Example:
            def subparser(self, parser):
                service_parser = parser.add_parser(
                    'mon-service',
                    help='Description du service'
                )
                subparsers = service_parser.add_subparsers(dest='action')

                # Ajouter les sous-commandes
                list_parser = subparsers.add_parser('list')
                create_parser = subparsers.add_parser('create')
        """
        pass

    @abstractmethod
    def handle_command(self, args: argparse.Namespace) -> int:
        """
        Traite la commande du service.

        Args:
            args: Arguments parsés depuis la ligne de commande

        Returns:
            Code de retour (0 pour succès, >0 pour erreur)

        Example:
            def handle_command(self, args):
                if args.action == 'list':
                    return self.list_items()
                elif args.action == 'create':
                    return self.create_item(args.name)
                return 1
        """
        pass

    @staticmethod
    def test_name(name: str) -> bool:
        """
        Teste si ce service gère ce nom de commande.

        Args:
            name: Nom de la commande à tester

        Returns:
            True si ce service gère cette commande

        Example:
            @staticmethod
            def test_name(name: str) -> bool:
                return name in MonService.commands
        """
        return False

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration pour ce service.

        Args:
            key: Clé de configuration
            default: Valeur par défaut si la clé n'existe pas

        Returns:
            Valeur de configuration ou valeur par défaut
        """
        return self.default_config.get(key, default)

    def validate_args(self, args: argparse.Namespace) -> bool:
        """
        Valide les arguments de la commande.

        Args:
            args: Arguments à valider

        Returns:
            True si les arguments sont valides
        """
        return True


class CLIServiceStore:
    """
    Store centralisé pour la gestion des services CLI.

    Permet d'enregistrer et de découvrir dynamiquement les services disponibles.
    """

    def __init__(self):
        self.services: List[CLIServiceBase] = []
        self._service_map: Dict[str, CLIServiceBase] = {}

    def register_service(self, service: CLIServiceBase) -> None:
        """
        Enregistre un nouveau service dans le store.

        Args:
            service: Service à enregistrer
        """
        self.services.append(service)

        # Mapper tous les noms de commandes au service
        for command_name in service.commands:
            self._service_map[command_name] = service

    def find_service(self, command_name: str) -> CLIServiceBase | None:
        """
        Trouve le service approprié pour une commande.

        Args:
            command_name: Nom de la commande

        Returns:
            Service gérant cette commande ou None
        """
        return self._service_map.get(command_name)

    def get_all_services(self) -> List[CLIServiceBase]:
        """
        Retourne tous les services enregistrés.

        Returns:
            Liste de tous les services
        """
        return self.services.copy()

    def setup_parsers(self, parser: argparse.ArgumentParser) -> None:
        """
        Configure tous les parsers des services enregistrés.

        Args:
            parser: Parser principal
        """
        for service in self.services:
            service.subparser(parser)


# Store global des services
service_store = CLIServiceStore()


def register_service(service_class: type[CLIServiceBase]) -> None:
    """
    Décorateur pour enregistrer automatiquement un service.

    Example:
        @register_service
        class MonService(CLIServiceBase):
            commands = ["mon-service"]

            def subparser(self, parser):
                # ...

            def handle_command(self, args):
                # ...
                return 0
    """
    service = service_class()
    service_store.register_service(service)
    return service_class
