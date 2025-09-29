# Interface CLI/TUI - WindFlow

## Vue d'Ensemble

WindFlow propose une interface en ligne de commande complète inspirée de VesselHarbor CLI, offrant une alternative puissante à l'interface web pour l'administration et l'automatisation.

### Philosophie CLI/TUI

**Principes de Conception :**
- **Ergonomie** : Interface intuitive avec aide contextuelle
- **Productivité** : Automatisation et scripts avancés
- **Consistance** : API cohérente entre CLI et interface web
- **Extensibilité** : Plugin system pour commandes personnalisées
- **Accessibilité** : Support des terminaux variés et assistances

## Architecture CLI Complète

### Stack Technologique CLI

**Composants Principaux :**
- **argparse** : Parser de commandes avec sous-parsers hiérarchiques
- **rich** : Interface CLI moderne avec couleurs et formatage avancé
- **typer** : CLI type-safe avec auto-complétion
- **click** : Alternative moderne pour commandes complexes
- **python-dotenv** : Support des fichiers .env pour la configuration

**Architecture des Services :**
- **ServiceBase** : Classe de base pour tous les services CLI
- **ServiceStore** : Store centralisé pour l'enregistrement des services
- **ServiceDiscovery** : Découverte automatique des services disponibles
- **ConfigurationMerger** : Fusion intelligente des configurations de services
- **PluginLoader** : Chargement dynamique de plugins CLI

## Commandes Principales

### Authentification

```bash
# Authentification interactive
windflow auth login --username admin --password secret

# Authentification par API key
windflow auth login-key --api-key sk-xxx

# Authentification SSO avec ouverture de navigateur
windflow auth login-sso --provider keycloak

# Vérification du statut d'authentification
windflow auth status

# Logout et nettoyage des tokens
windflow auth logout

# Génération d'une nouvelle API key
windflow auth create-key --name "ci-cd-key" --scopes "deployment,monitoring"
```

### Configuration

```bash
# Configuration du serveur WindFlow
windflow config set-url https://api.windflow.local
windflow config set-server windflow.local --port 8080

# Récupération de la configuration actuelle
windflow config get-url
windflow config show

# Configuration des préférences utilisateur
windflow config set-default-org "production-org"
windflow config set-output-format json

# Configuration des providers cloud
windflow config add-provider aws --region eu-west-1
windflow config add-provider azure --subscription-id xxx
```

### Gestion des Organisations

```bash
# Listing des organisations
windflow org list
windflow org list --format table --filter active=true

# Détails d'une organisation
windflow org get <org_id>
windflow org describe production-org --verbose

# Création d'organisation
windflow org create --name "Production" --description "Environnement de production"

# Mise à jour d'organisation
windflow org update <org_id> --name "New Name" --quotas '{"cpu": 100, "memory": "500GB"}'

# Suppression d'organisation
windflow org delete <org_id> --confirm

# Gestion des utilisateurs dans l'organisation
windflow org add-user <org_id> <user_id> --role admin
windflow org remove-user <org_id> <user_id>
```

### Gestion des Environnements

```bash
# Listing des environnements
windflow env list --org <org_id>
windflow env list --type production --status active

# Détails d'un environnement
windflow env get <env_id>
windflow env describe staging --org production-org

# Création d'environnement
windflow env create --org <org_id> --name "staging" --type staging

# Configuration d'environnement
windflow env config <env_id> --set resource_limits='{"cpu": 50, "memory": "200GB"}'

# Suppression d'environnement
windflow env delete <env_id> --force

# Clonage d'environnement
windflow env clone <source_env_id> --name "staging-v2" --org <target_org_id>
```

### Déploiements

```bash
# Création de déploiement
windflow deploy create --stack web-app --environment staging
windflow deploy create --stack web-app --target docker --config deploy.yaml

# Déploiement avec validation préalable
windflow deploy create --stack api-service --dry-run --validate

# Listing des déploiements
windflow deploy list --environment <env_id>
windflow deploy list --status running --user <user_id>

# Status d'un déploiement
windflow deploy status <deployment_id>
windflow deploy status <deployment_id> --follow --interval 5

# Logs de déploiement
windflow deploy logs <deployment_id> --follow --tail 100
windflow deploy logs <deployment_id> --since 1h --level error

# Rollback de déploiement
windflow deploy rollback <deployment_id>
windflow deploy rollback <deployment_id> --to-version v1.2.3

# Scaling d'un déploiement
windflow deploy scale <deployment_id> --replicas 5
windflow deploy scale <deployment_id> --auto --min 2 --max 10
```

### Stacks et Services

```bash
# Marketplace des stacks
windflow stack list --marketplace
windflow stack search --tag database --category web

# Détails d'un stack
windflow stack get <stack_id>
windflow stack describe lamp-stack --version latest

# Déploiement d'un stack depuis le marketplace
windflow stack deploy wordpress --environment staging --params '{"domain": "test.local"}'

# Création d'un stack personnalisé
windflow stack create --name custom-stack --template template.yaml

# Validation d'un stack
windflow stack validate custom-stack.yaml
windflow stack validate --llm-optimize custom-stack.yaml

# Gestion des services
windflow service list --stack <stack_id>
windflow service logs <service_id> --follow
windflow service scale <service_id> --replicas 3
windflow service restart <service_id>
```

### Monitoring et Logs

```bash
# Métriques en temps réel
windflow metrics show --environment <env_id>
windflow metrics show --stack <stack_id> --live

# Logs centralisés
windflow logs search --query "error" --since 1h
windflow logs tail --service <service_id> --follow

# Health checks
windflow health check --environment <env_id>
windflow health check --stack <stack_id> --verbose

# Alertes
windflow alerts list --severity critical
windflow alerts ack <alert_id>
```

## Architecture des Services CLI

### Système de Services Modulaire

```python
class CLIServiceBase(ABC):
    """Classe de base pour tous les services CLI."""
    
    params_link = {}
    default_config = {}
    
    @abstractmethod
    def subparser(self, parser):
        """Configurer le sous-parser pour ce service."""
        pass
    
    @abstractmethod
    def handle_command(self, args):
        """Traiter la commande du service."""
        pass
    
    @staticmethod
    def test_name(name):
        """Tester si ce service gère ce nom de commande."""
        return False

class CLIServiceStore:
    """Store centralisé pour la gestion des services CLI."""
    
    def __init__(self):
        self.services = []
    
    def register_service(self, service):
        """Enregistrer un nouveau service."""
        self.services.append(service)
    
    def find_service(self, command_name):
        """Trouver le service approprié pour une commande."""
        for service in self.services:
            if service.test_name(command_name):
                return service
        return None
```

### Services CLI Intégrés

#### AuthService - Gestion de l'Authentification

```python
class AuthService(CLIServiceBase):
    commands = ["auth", "login", "logout", "token"]
    
    def subparser(self, parser):
        auth_parser = parser.add_parser('auth', help='Authentication commands')
        auth_subparsers = auth_parser.add_subparsers(dest='auth_action')
        
        # Login avec mot de passe
        login_parser = auth_subparsers.add_parser('login')
        login_parser.add_argument('--username', required=True)
        login_parser.add_argument('--password', required=True)
        
        # Login avec API key
        key_parser = auth_subparsers.add_parser('login-key')
        key_parser.add_argument('--api-key', required=True)
        
        # Status
        auth_subparsers.add_parser('status')
        
        # Logout
        auth_subparsers.add_parser('logout')
    
    def handle_command(self, args):
        if args.auth_action == 'login':
            return self.login(args.username, args.password)
        elif args.auth_action == 'login-key':
            return self.login_with_key(args.api_key)
        elif args.auth_action == 'status':
            return self.show_status()
        elif args.auth_action == 'logout':
            return self.logout()
```

#### OrganizationService - Gestion des Organisations

```python
class OrganizationService(CLIServiceBase):
    commands = ["org", "organization", "organizations"]
    
    def handle_command(self, args):
        if args.action == 'list':
            return self.list_organizations(
                format=args.format,
                filter=args.filter
            )
        elif args.action == 'create':
            return self.create_organization(
                name=args.name,
                description=args.description,
                quotas=args.quotas
            )
        elif args.action == 'get':
            return self.get_organization(args.org_id)
        elif args.action == 'update':
            return self.update_organization(args.org_id, **args.updates)
        elif args.action == 'delete':
            return self.delete_organization(args.org_id, confirm=args.confirm)
```

#### DeploymentService - Gestion des Déploiements

```python
class DeploymentService(CLIServiceBase):
    commands = ["deploy", "deployment", "deployments"]
    
    def handle_command(self, args):
        if args.action == 'create':
            return self.create_deployment(
                stack=args.stack,
                environment=args.environment,
                target=args.target,
                config=args.config,
                dry_run=args.dry_run
            )
        elif args.action == 'list':
            return self.list_deployments(
                environment=args.environment,
                status=args.status,
                user=args.user
            )
        elif args.action == 'status':
            return self.get_deployment_status(
                deployment_id=args.deployment_id,
                follow=args.follow
            )
        elif args.action == 'rollback':
            return self.rollback_deployment(
                deployment_id=args.deployment_id,
                to_version=args.to_version
            )
```

## Interface TUI (Text User Interface)

### Architecture TUI Avancée

WindFlow intègre une interface utilisateur textuelle (TUI) sophistiquée basée sur `curses` et `textual`, offrant une expérience similaire à `cfdisk` pour la gestion visuelle des ressources.

**Composants TUI :**
- **InteractiveBase** : Classe de base pour toutes les interfaces TUI
- **ScreenManager** : Gestionnaire d'écrans avec navigation
- **PanelSystem** : Système de panneaux (liste, détails, actions)
- **KeyboardHandler** : Gestionnaire de raccourcis clavier
- **ColorTheme** : Système de thèmes avec support des couleurs

### Interfaces TUI Disponibles

#### Gestionnaire d'Organisations (`windflow tui orgs`)

```
┌─ WindFlow - Organisation Management ──────────────────────┐
│ ↑/↓: Navigate | Enter: Select | c: Create | d: Delete     │
├────────────────────────────────┬───────────────────────────┤
│ Organizations                  │ Organization Details      │
│ ► Production [org-123]         │ Name: Production          │
│   Development [org-456]        │ ID: org-123               │
│   Staging [org-789]            │ Description: Production   │
│                                │ Environments: 3           │
│                                │ Users: 15                 │
│                                │ Created: 2025-01-15       │
│                                │                           │
├────────────────────────────────┴───────────────────────────┤
│ Commands: c=Create | e=Edit | d=Delete | q=Quit | ?=Help   │
└────────────────────────────────────────────────────────────┘
```

#### Gestionnaire d'Environnements (`windflow tui envs`)

```
┌─ WindFlow - Environment Management ───────────────────────┐
│ Org: Production | ↑/↓: Navigate | Enter: Select | c: Create│
├────────────────────────────────┬───────────────────────────┤
│ Environments                   │ Environment Details       │
│ ► staging [env-456]            │ Name: staging             │
│   production [env-789]         │ ID: env-456               │
│   testing [env-012]            │ Organization: Production  │
│                                │ Elements: 12              │
│                                │ Active Deployments: 8     │
│                                │ Status: Healthy           │
│                                │                           │
├────────────────────────────────┴───────────────────────────┤
│ Commands: c=Create | e=Edit | d=Delete | s=Switch Org      │
└────────────────────────────────────────────────────────────┘
```

#### Gestionnaire de Déploiements (`windflow tui deployments`)

```
┌─ WindFlow - Deployment Management ────────────────────────┐
│ Env: staging | Status: ●8 Running ●2 Pending ●1 Failed   │
├────────────────────────────────┬───────────────────────────┤
│ Deployments                    │ Deployment Details        │
│ ► web-app-v1.2.3 [Running]     │ Name: web-app-v1.2.3      │
│   api-service-v2.1.0 [Running] │ Status: Running           │
│   redis-cluster [Pending]      │ Target: Docker Swarm      │
│   monitoring [Failed]          │ Started: 2025-01-15 14:30│
│                                │ Containers: 3/3 Healthy  │
│                                │ Resources: CPU 45% RAM 60%│
│                                │ Logs: [l] View Logs       │
├────────────────────────────────┴───────────────────────────┤
│ Commands: s=Start | p=Stop | r=Restart | l=Logs | b=Rollback│
└────────────────────────────────────────────────────────────┘
```

### Implémentation TUI avec Textual

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Header, Footer, Static, DataTable

class WindFlowTUI(App):
    """Interface TUI principale de WindFlow."""
    
    CSS_PATH = "windflow.css"
    BINDINGS = [
        ("d", "deploy", "Deploy"),
        ("r", "refresh", "Refresh"),
        ("l", "logs", "Logs"),
        ("q", "quit", "Quit"),
        ("?", "help", "Help")
    ]
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                # Panneau gauche - Liste des ressources
                Vertical(
                    Static("Deployments", classes="panel-title"),
                    DataTable(id="deployments"),
                    classes="panel left-panel"
                ),
                # Panneau droit - Détails
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
        # Configuration des tables
        deployments_table = self.query_one("#deployments", DataTable)
        deployments_table.add_columns("Name", "Status", "Started", "Environment")
        
        # Chargement des données initiales
        await self.refresh_deployments()
    
    async def action_deploy(self) -> None:
        """Action de déploiement."""
        # Ouvrir un modal de sélection de stack
        self.push_screen(DeploymentModal())
    
    async def action_refresh(self) -> None:
        """Actualisation des données."""
        await self.refresh_deployments()
    
    async def action_logs(self) -> None:
        """Affichage des logs."""
        selected_deployment = self.get_selected_deployment()
        if selected_deployment:
            self.push_screen(LogsScreen(selected_deployment['id']))
```

### Fonctionnalités TUI Avancées

#### Navigation et Interaction

- **Navigation fluide** avec les flèches directionnelles
- **Recherche instantanée** avec `/` + terme de recherche
- **Filtrage rapide** par statut, type, ou tag
- **Sélection multiple** avec `Espace` + actions groupées
- **Modes d'affichage** (liste, grille, arbre)

#### Messages et Notifications

```python
class NotificationSystem:
    """Système de notifications pour TUI."""
    
    def __init__(self, app):
        self.app = app
        
    def show_info(self, message: str):
        """Affichage d'une notification d'information."""
        self.app.notify(message, severity="information")
    
    def show_success(self, message: str):
        """Affichage d'une notification de succès.""" 
        self.app.notify(message, severity="success")
    
    def show_error(self, message: str):
        """Affichage d'une notification d'erreur."""
        self.app.notify(message, severity="error")
    
    def show_progress(self, task_name: str, total: int):
        """Affichage d'une barre de progression."""
        return self.app.progress_bar(task_name, total)
```

#### Raccourcis Clavier Globaux

```
Navigation:
  ↑/↓       - Navigation verticale
  ←/→       - Navigation horizontale/changement de panneau
  Page Up/Dn - Navigation rapide
  Home/End   - Début/fin de liste
  /          - Recherche
  Esc        - Annuler/retour

Actions:
  Enter      - Sélectionner/activer
  Espace     - Sélection multiple
  c          - Créer nouvel élément
  e          - Éditer élément sélectionné
  d          - Supprimer élément sélectionné
  r          - Rafraîchir les données
  
Système:
  ?          - Aide contextuelle
  q          - Quitter l'interface
  F1-F12     - Actions spécialisées selon le contexte
```

## Configuration et Extensibilité

### Configuration Hiérarchique

```python
# Ordre de priorité (le plus haut l'emporte)
configuration_sources = [
    "default_values",           # 1. Valeurs par défaut dans le code
    "config_file",             # 2. Fichier de configuration ~/.windflow/config.yaml
    "environment_variables",    # 3. Variables d'environnement WINDFLOW_*
    "dotenv_file",             # 4. Fichier .env dans le répertoire courant
    "command_line_arguments"    # 5. Arguments de ligne de commande (priorité maximale)
]
```

#### Variables d'Environnement Supportées

```bash
export WINDFLOW_API_URL="https://api.windflow.local"
export WINDFLOW_SERVER_NAME="windflow.local"
export WINDFLOW_SERVER_PORT="8080"
export WINDFLOW_USERNAME="admin"
export WINDFLOW_PASSWORD="secret"
export WINDFLOW_API_KEY="sk-xxx"
export WINDFLOW_ORG_ID="org-123"
export WINDFLOW_ENV_ID="env-456"
export WINDFLOW_OUTPUT_FORMAT="json"
export WINDFLOW_DEFAULT_TARGET="docker"
```

#### Fichier de Configuration

```yaml
# ~/.windflow/config.yaml
api:
  url: "https://api.windflow.local"
  timeout: 30
  retries: 3

auth:
  method: "interactive"  # interactive, api_key, sso
  auto_refresh: true
  store_tokens: true

defaults:
  organization: "production-org"
  environment: "staging"
  target: "docker"
  output_format: "table"

services:
  deployment:
    default_target: "docker"
    backup_before_deploy: true
    auto_rollback_on_failure: true
    
  monitoring:
    auto_start_logs: true
    log_level: "info"
    refresh_interval: 5

plugins:
  enabled:
    - "aws-integration"
    - "slack-notifications"
  disabled:
    - "azure-integration"

ui:
  theme: "dark"
  show_help_hints: true
  page_size: 20
```

### Plugin System

```python
# Plugin personnalisé
class CustomStackService(CLIServiceBase):
    commands = ["custom-stack"]
    
    def subparser(self, parser):
        custom_parser = parser.add_parser('custom-stack')
        custom_parser.add_argument('--template', choices=['lamp', 'mean', 'django'])
        
    def handle_command(self, args):
        return self.deploy_custom_stack(args.template)

# Enregistrement automatique
windflow.register_plugin(CustomStackService)
```

### Auto-complétion

```bash
# Installation de l'auto-complétion pour bash
windflow completion bash > /etc/bash_completion.d/windflow

# Installation pour zsh
windflow completion zsh > ~/.zsh/completions/_windflow

# Installation pour fish
windflow completion fish > ~/.config/fish/completions/windflow.fish
```

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Contexte du projet
- [Authentification](05-authentication.md) - Système d'authentification
- [API Design](07-api-design.md) - APIs utilisées par CLI
- [Fonctionnalités Principales](10-core-features.md) - Fonctionnalités accessibles via CLI
- [Guide de Déploiement](15-deployment-guide.md) - Installation et configuration
