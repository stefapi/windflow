# Règles de Développement CLI/TUI - WindFlow

## Stack Technologique CLI/TUI

### Framework Principal
- **Rich** pour l'interface CLI moderne avec couleurs et formatage
- **Typer** pour les commandes type-safe avec auto-complétion
- **Textual** pour l'interface TUI (Text User Interface)
- **argparse** pour les parsers de commandes hiérarchiques
- **python-dotenv** pour la gestion de configuration

### Architecture des Services CLI

#### Structure Obligatoire
```
windflow-cli/
├── cli/
│   ├── commands/           # Commandes CLI par catégorie
│   │   ├── auth.py        # Authentification
│   │   ├── deploy.py      # Déploiements
│   │   ├── org.py         # Organisations
│   │   └── stack.py       # Stacks
│   ├── services/          # Services CLI
│   ├── tui/               # Interfaces TUI
│   ├── utils/             # Utilitaires CLI
│   ├── config.py          # Configuration
│   └── main.py           # Point d'entrée CLI
├── tests/                 # Tests CLI/TUI
└── completion/            # Scripts auto-complétion
```

## Conventions CLI

### Architecture des Services Modulaires
```python
# ✅ CORRECT - Service CLI modulaire
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import argparse

class CLIServiceBase(ABC):
    """Classe de base pour tous les services CLI."""
    
    commands: List[str] = []
    params_link: Dict[str, Any] = {}
    default_config: Dict[str, Any] = {}
    
    @abstractmethod
    def subparser(self, parser: argparse.ArgumentParser) -> None:
        """Configurer le sous-parser pour ce service."""
        pass
    
    @abstractmethod
    def handle_command(self, args: argparse.Namespace) -> int:
        """Traiter la commande du service.
        
        Returns:
            Code de retour (0 pour succès, >0 pour erreur)
        """
        pass
    
    @staticmethod
    def test_name(name: str) -> bool:
        """Tester si ce service gère ce nom de commande."""
        return False

# ❌ INCORRECT - Service CLI sans structure
def deploy_command(args):
    # Logique mélangée sans organisation
    pass
```

### Commandes avec Rich et Typer
```python
# ✅ CORRECT - Commande CLI moderne
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from typing import Optional

app = typer.Typer(help="WindFlow CLI - Déploiement intelligent")
console = Console()

@app.command()
def deploy(
    stack: str = typer.Argument(..., help="Nom du stack à déployer"),
    environment: str = typer.Option("staging", help="Environnement cible"),
    target: Optional[str] = typer.Option(None, help="Type de cible"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulation"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mode verbose")
) -> None:
    """Déployer un stack sur l'environnement spécifié."""
    
    if verbose:
        console.print(f"[bold blue]Déploiement de {stack} sur {environment}[/bold blue]")
    
    with Progress() as progress:
        task = progress.add_task("[green]Déploiement en cours...", total=100)
        
        try:
            # Logique de déploiement
            result = deployment_service.deploy(
                stack=stack,
                environment=environment,
                target=target,
                dry_run=dry_run
            )
            
            progress.update(task, completed=100)
            console.print("[bold green]✓ Déploiement terminé avec succès![/bold green]")
            
        except DeploymentError as e:
            console.print(f"[bold red]✗ Erreur: {e}[/bold red]")
            raise typer.Exit(1)

# ❌ INCORRECT - Commande CLI basique
def deploy_command(stack, env, dry_run=False):
    print(f"Deploying {stack} to {env}")
    # Pas de formatage, gestion d'erreur limitée
```

### Gestion des Erreurs CLI
```python
# cli/utils/errors.py
from rich.console import Console
from enum import IntEnum

class ExitCode(IntEnum):
    """Codes de retour standardisés."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    AUTH_ERROR = 2
    CONFIG_ERROR = 3
    NETWORK_ERROR = 4
    PERMISSION_ERROR = 5
    NOT_FOUND = 6

class CLIErrorHandler:
    """Gestionnaire d'erreurs pour CLI."""
    
    def __init__(self, console: Console):
        self.console = console
    
    def handle_error(self, error: Exception, context: str = "") -> int:
        """Gère une erreur et retourne le code de sortie approprié."""
        
        if isinstance(error, AuthenticationError):
            self.console.print(f"[bold red]✗ Erreur d'authentification: {error}[/bold red]")
            self.console.print("[yellow]Utilisez 'windflow auth login' pour vous connecter[/yellow]")
            return ExitCode.AUTH_ERROR
            
        elif isinstance(error, ConfigurationError):
            self.console.print(f"[bold red]✗ Erreur de configuration: {error}[/bold red]")
            return ExitCode.CONFIG_ERROR
            
        elif isinstance(error, NetworkError):
            self.console.print(f"[bold red]✗ Erreur réseau: {error}[/bold red]")
            self.console.print("[yellow]Vérifiez votre connexion et l'URL du serveur[/yellow]")
            return ExitCode.NETWORK_ERROR
            
        else:
            self.console.print(f"[bold red]✗ Erreur inattendue: {error}[/bold red]")
            if context:
                self.console.print(f"[dim]Contexte: {context}[/dim]")
            return ExitCode.GENERAL_ERROR
```

## Interface TUI avec Textual

### Structure des Écrans TUI
```python
# ✅ CORRECT - Écran TUI structuré
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Header, Footer, Static, DataTable
from textual.binding import Binding

class DeploymentManagerTUI(App):
    """Interface TUI pour la gestion des déploiements."""
    
    CSS_PATH = "deployment.css"
    TITLE = "WindFlow - Deployment Manager"
    
    BINDINGS = [
        Binding("d", "deploy", "Deploy", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("l", "logs", "Logs", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=False)
    ]
    
    def compose(self) -> ComposeResult:
        """Composition de l'interface."""
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Static("Deployments", classes="panel-title"),
                    DataTable(id="deployments-table"),
                    classes="panel left-panel"
                ),
                Vertical(
                    Static("Details", classes="panel-title"),
                    Container(id="details-content"),
                    classes="panel right-panel"
                ),
                id="main-container"
            )
        )
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialisation de l'interface."""
        deployments_table = self.query_one("#deployments-table", DataTable)
        deployments_table.add_columns("Name", "Status", "Started", "Environment")
        
        # Chargement des données
        await self.refresh_deployments()
    
    async def action_deploy(self) -> None:
        """Action de déploiement."""
        self.push_screen(DeploymentModal())
    
    async def action_refresh(self) -> None:
        """Actualisation des données."""
        await self.refresh_deployments()
        self.notify("Données actualisées", severity="information")
    
    async def refresh_deployments(self) -> None:
        """Actualise la liste des déploiements."""
        table = self.query_one("#deployments-table", DataTable)
        table.clear()
        
        try:
            deployments = await deployment_service.list_deployments()
            for deployment in deployments:
                table.add_row(
                    deployment.name,
                    deployment.status,
                    deployment.started_at.strftime("%Y-%m-%d %H:%M"),
                    deployment.environment
                )
        except Exception as e:
            self.notify(f"Erreur lors du chargement: {e}", severity="error")
```

### Modales et Widgets Personnalisés
```python
# tui/widgets/deployment_modal.py
from textual.screen import ModalScreen
from textual.containers import Grid
from textual.widgets import Button, Input, Select, Label

class DeploymentModal(ModalScreen[bool]):
    """Modal de création de déploiement."""
    
    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Créer un nouveau déploiement", id="title"),
            Label("Stack:"),
            Select([(stack.name, stack.id) for stack in available_stacks], id="stack-select"),
            Label("Environnement:"),
            Select([(env.name, env.id) for env in available_environments], id="env-select"),
            Label("Cible:"),
            Select([("Docker", "docker"), ("Kubernetes", "kubernetes")], id="target-select"),
            Button("Déployer", variant="primary", id="deploy-btn"),
            Button("Annuler", variant="default", id="cancel-btn"),
            id="deployment-dialog"
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "deploy-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)
```

## Configuration et État

### Configuration Hiérarchique
```python
# cli/config.py
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import os

class CLIConfiguration:
    """Gestion de la configuration CLI avec priorité hiérarchique."""
    
    def __init__(self):
        self.config_sources = [
            "default_values",
            "config_file",
            "environment_variables", 
            "dotenv_file",
            "command_line_arguments"
        ]
        self._config: Dict[str, Any] = {}
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Charge la configuration selon l'ordre de priorité."""
        # 1. Valeurs par défaut
        self._config.update(self._get_default_config())
        
        # 2. Fichier de configuration
        config_file = Path.home() / ".windflow" / "config.yaml"
        if config_file.exists():
            with open(config_file) as f:
                self._config.update(yaml.safe_load(f) or {})
        
        # 3. Variables d'environnement
        env_config = self._get_env_config()
        self._config.update(env_config)
        
        # 4. Fichier .env local
        dotenv_path = Path.cwd() / ".env"
        if dotenv_path.exists():
            from dotenv import dotenv_values
            dotenv_config = dotenv_values(dotenv_path)
            self._config.update(self._convert_env_vars(dotenv_config))
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Configuration par défaut."""
        return {
            "api": {
                "url": "http://localhost:8000",
                "timeout": 30,
                "retries": 3
            },
            "auth": {
                "method": "interactive",
                "auto_refresh": True,
                "store_tokens": True
            },
            "defaults": {
                "output_format": "table",
                "target": "docker"
            },
            "ui": {
                "theme": "dark",
                "show_help_hints": True,
                "page_size": 20
            }
        }
    
    def _get_env_config(self) -> Dict[str, Any]:
        """Configuration depuis les variables d'environnement."""
        env_mapping = {
            "WINDFLOW_API_URL": ("api", "url"),
            "WINDFLOW_API_TIMEOUT": ("api", "timeout"),
            "WINDFLOW_OUTPUT_FORMAT": ("defaults", "output_format"),
            "WINDFLOW_DEFAULT_TARGET": ("defaults", "target"),
            "WINDFLOW_THEME": ("ui", "theme")
        }
        
        config = {}
        for env_var, (section, key) in env_mapping.items():
            value = os.getenv(env_var)
            if value:
                if section not in config:
                    config[section] = {}
                config[section][key] = self._convert_env_value(value)
        
        return config
    
    def get(self, path: str, default: Any = None) -> Any:
        """Récupère une valeur de configuration par chemin."""
        keys = path.split(".")
        value = self._config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, path: str, value: Any) -> None:
        """Définit une valeur de configuration."""
        keys = path.split(".")
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value

# Singleton global
cli_config = CLIConfiguration()
```

### Gestion de l'État et des Sessions
```python
# cli/session.py
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

@dataclass
class CLISession:
    """État de session CLI."""
    user_id: Optional[str] = None
    username: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    organization_id: Optional[str] = None
    environment_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    @property
    def is_authenticated(self) -> bool:
        """Vérifie si l'utilisateur est authentifié."""
        return bool(self.access_token and self.expires_at and self.expires_at > datetime.now())
    
    @property
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur a des privilèges admin."""
        # Implémentation basée sur les claims du token
        return False  # Placeholder

class SessionManager:
    """Gestionnaire de sessions CLI."""
    
    def __init__(self):
        self.session_file = Path.home() / ".windflow" / "session.json"
        self.session_file.parent.mkdir(exist_ok=True)
        self._session = self._load_session()
    
    def _load_session(self) -> CLISession:
        """Charge la session depuis le fichier."""
        if self.session_file.exists():
            try:
                with open(self.session_file) as f:
                    data = json.load(f)
                    if data.get("expires_at"):
                        data["expires_at"] = datetime.fromisoformat(data["expires_at"])
                    return CLISession(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return CLISession()
    
    def save_session(self) -> None:
        """Sauvegarde la session."""
        data = self._session.__dict__.copy()
        if data.get("expires_at"):
            data["expires_at"] = data["expires_at"].isoformat()
        
        with open(self.session_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def clear_session(self) -> None:
        """Efface la session."""
        self._session = CLISession()
        if self.session_file.exists():
            self.session_file.unlink()
    
    @property
    def current(self) -> CLISession:
        """Session actuelle."""
        return self._session

# Singleton global
session_manager = SessionManager()
```

## Tests CLI/TUI

### Tests des Commandes CLI
```python
# tests/test_cli_commands.py
import pytest
from typer.testing import CliRunner
from unittest.mock import Mock, patch
from cli.main import app

runner = CliRunner()

def test_deploy_command_success():
    """Test de la commande deploy avec succès."""
    with patch('cli.services.deployment_service.deploy') as mock_deploy:
        mock_deploy.return_value = {"status": "success", "deployment_id": "dep-123"}
        
        result = runner.invoke(app, [
            "deploy", "web-app",
            "--environment", "staging",
            "--target", "docker"
        ])
        
        assert result.exit_code == 0
        assert "Déploiement terminé avec succès" in result.stdout
        mock_deploy.assert_called_once_with(
            stack="web-app",
            environment="staging",
            target="docker",
            dry_run=False
        )

def test_deploy_command_error():
    """Test de la commande deploy avec erreur."""
    with patch('cli.services.deployment_service.deploy') as mock_deploy:
        mock_deploy.side_effect = DeploymentError("Stack not found")
        
        result = runner.invoke(app, ["deploy", "invalid-stack"])
        
        assert result.exit_code == 1
        assert "Erreur: Stack not found" in result.stdout

def test_deploy_command_dry_run():
    """Test de la commande deploy en mode dry-run."""
    with patch('cli.services.deployment_service.deploy') as mock_deploy:
        mock_deploy.return_value = {"status": "dry_run", "validation": "passed"}
        
        result = runner.invoke(app, [
            "deploy", "web-app",
            "--dry-run"
        ])
        
        assert result.exit_code == 0
        mock_deploy.assert_called_once_with(
            stack="web-app",
            environment="staging",  # valeur par défaut
            target=None,
            dry_run=True
        )
```

### Tests TUI avec Textual
```python
# tests/test_tui.py
import pytest
from textual.testing import TUITestCase
from tui.deployment_manager import DeploymentManagerTUI

class TestDeploymentManagerTUI(TUITestCase):
    """Tests pour l'interface TUI de gestion des déploiements."""
    
    def test_initial_layout(self):
        """Test de la mise en page initiale."""
        app = DeploymentManagerTUI()
        
        with app.run_test() as pilot:
            # Vérification de la présence des éléments
            assert pilot.app.query_one("#deployments-table")
            assert pilot.app.query_one("#details-content")
    
    def test_refresh_action(self):
        """Test de l'action de rafraîchissement."""
        app = DeploymentManagerTUI()
        
        with app.run_test() as pilot:
            # Simulation de l'appui sur 'r'
            pilot.press("r")
            
            # Vérification que l'action a été déclenchée
            assert "Données actualisées" in pilot.app._notifications
    
    def test_deploy_modal(self):
        """Test d'ouverture du modal de déploiement."""
        app = DeploymentManagerTUI()
        
        with app.run_test() as pilot:
            # Simulation de l'appui sur 'd'
            pilot.press("d")
            
            # Vérification que le modal est ouvert
            assert len(pilot.app.screen_stack) == 2
```

## Auto-complétion et Plugins

### Système d'Auto-complétion
```python
# cli/completion.py
from typing import List, Dict, Any
import click

def get_available_stacks() -> List[str]:
    """Récupère la liste des stacks disponibles."""
    # Implémentation d'appel API
    return ["web-app", "api-service", "database-cluster"]

def get_available_environments() -> List[str]:
    """Récupère la liste des environnements disponibles."""
    return ["development", "staging", "production"]

def complete_stack_name(ctx: click.Context, param: click.Parameter, incomplete: str) -> List[str]:
    """Auto-complétion pour les noms de stacks."""
    stacks = get_available_stacks()
    return [stack for stack in stacks if stack.startswith(incomplete)]

def complete_environment_name(ctx: click.Context, param: click.Parameter, incomplete: str) -> List[str]:
    """Auto-complétion pour les environnements."""
    envs = get_available_environments()
    return [env for env in envs if env.startswith(incomplete)]

# Génération des scripts de complétion
def generate_bash_completion() -> str:
    """Génère le script de complétion pour bash."""
    return """
_windflow_completion() {
    COMPREPLY=($(compgen -W "$(windflow completion-words "${COMP_WORDS[@]}")" -- "${COMP_WORDS[COMP_CWORD]}"))
}

complete -F _windflow_completion windflow
"""

def generate_zsh_completion() -> str:
    """Génère le script de complétion pour zsh."""
    return """
#compdef windflow

_windflow() {
    local -a commands
    commands=($(windflow completion-words "${words[@]}"))
    _describe 'commands' commands
}

_windflow "$@"
"""
```

### Système de Plugins
```python
# cli/plugins/plugin_system.py
from abc import ABC, abstractmethod
from typing import Dict, List, Type
import importlib
import pkgutil

class CLIPlugin(ABC):
    """Interface pour les plugins CLI."""
    
    name: str
    version: str
    description: str
    
    @abstractmethod
    def register_commands(self, app) -> None:
        """Enregistre les commandes du plugin."""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict) -> None:
        """Initialise le plugin avec la configuration."""
        pass

class PluginManager:
    """Gestionnaire de plugins CLI."""
    
    def __init__(self):
        self.plugins: Dict[str, CLIPlugin] = {}
        self.enabled_plugins: List[str] = []
    
    def discover_plugins(self) -> None:
        """Découvre automatiquement les plugins disponibles."""
        # Recherche dans le namespace windflow_plugins
        for finder, name, ispkg in pkgutil.iter_namespace(path=["windflow_plugins"]):
            try:
                module = importlib.import_module(f"windflow_plugins.{name}")
                if hasattr(module, 'Plugin'):
                    plugin = module.Plugin()
                    self.plugins[plugin.name] = plugin
            except ImportError:
                continue
    
    def load_plugin(self, plugin_name: str, config: Dict) -> None:
        """Charge un plugin spécifique."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.initialize(config)
            self.enabled_plugins.append(plugin_name)
    
    def register_plugin_commands(self, app) -> None:
        """Enregistre les commandes de tous les plugins actifs."""
        for plugin_name in self.enabled_plugins:
            if plugin_name in self.plugins:
                self.plugins[plugin_name].register_commands(app)

# Exemple de plugin
class AWSIntegrationPlugin(CLIPlugin):
    """Plugin d'intégration AWS."""
    
    name = "aws-integration"
    version = "1.0.0"
    description = "Intégration avec les services AWS"
    
    def register_commands(self, app) -> None:
        @app.command()
        def aws_deploy(
            stack: str,
            region: str = "eu-west-1",
            profile: str = "default"
        ):
            """Déploie un stack sur AWS."""
            # Logique de déploiement AWS
            pass
    
    def initialize(self, config: Dict) -> None:
        """Initialisation du plugin AWS."""
        self.aws_region = config.get("aws", {}).get("region", "eu-west-1")
        self.aws_profile = config.get("aws", {}).get("profile", "default")
```

Ces règles assurent un développement CLI/TUI cohérent, performant et extensible pour WindFlow.
