# WindFlow CLI

Interface en ligne de commande moderne pour WindFlow - Gestionnaire intelligent de déploiements de containers.

## ✨ Fonctionnalités

- 🎨 **Interface moderne** avec Rich (tableaux colorés, messages stylisés)
- 🔐 **Authentification** complète (login, logout, status)
- ⚙️ **Configuration** hiérarchique (fichier + env + CLI)
- 🏢 **Organisations** (list, get, create, delete)
- 🌍 **Environnements** (list, get, create, delete)
- 🚀 **Déploiements** (create, list, status, logs)
- 📊 **Logs en temps réel** avec mode --follow
- ⌨️ **Auto-complétion** bash/zsh
- 🔌 **Architecture modulaire** extensible

## Installation

Le CLI WindFlow est inclus dans le projet principal. Pour l'installer :

```bash
# Depuis la racine du projet
pip install -e .

# Ou avec poetry
poetry install

# Installer les dépendances
pip install rich httpx pyyaml
```

Après l'installation, la commande `windflow` sera disponible globalement.

### Activer l'auto-complétion

```bash
# Pour bash
source cli/completion.sh
# Ajouter à ~/.bashrc pour activation permanente :
echo "source $(pwd)/cli/completion.sh" >> ~/.bashrc

# Pour zsh
# Ajouter à ~/.zshrc :
autoload -U +X compinit && compinit
autoload -U +X bashcompinit && bashcompinit
source cli/completion.sh
```

## Configuration

### Configuration initiale

```bash
# Définir l'URL de l'API WindFlow
windflow config set-url http://localhost:8000

# Afficher la configuration actuelle
windflow config show
```

### Fichier de configuration

Le CLI utilise une configuration hiérarchique :
- Fichier : `~/.windflow/config.yaml`
- Variables d'environnement : `WINDFLOW_*`
- Arguments en ligne de commande

Exemple de fichier `~/.windflow/config.yaml` :

```yaml
api:
  url: "http://localhost:8000"
  timeout: 30
  prefix: "/api/v1"

auth:
  auto_refresh: true

output:
  format: "table"

defaults:
  organization: null
  environment: null
```

### Variables d'environnement supportées

```bash
export WINDFLOW_API_URL="http://localhost:8000"
export WINDFLOW_OUTPUT_FORMAT="json"  # ou "table"
export WINDFLOW_DEFAULT_ORG="org-id"
export WINDFLOW_DEFAULT_ENV="env-id"
```

## Utilisation

### Authentification

```bash
# Se connecter
windflow auth login --username admin --password changeme123

# Vérifier le statut d'authentification
windflow auth status

# Se déconnecter
windflow auth logout
```

### Configuration

```bash
# Définir l'URL de l'API
windflow config set-url http://localhost:8000

# Récupérer l'URL de l'API
windflow config get-url

# Définir une valeur de configuration
windflow config set output_format json

# Récupérer une valeur
windflow config get output_format

# Afficher toute la configuration
windflow config show
```

### Organisations

```bash
# Lister les organisations (tableau coloré avec Rich)
windflow org list

# Lister en format JSON
windflow org list --format json

# Détails d'une organisation
windflow org get <org-id>
```

### Environnements

```bash
# Lister les environnements
windflow env list

# Filtrer par organisation
windflow env list --org <org-id>

# Lister en format JSON
windflow env list --format json

# Détails d'un environnement
windflow env get <env-id>

# Créer un environnement
windflow env create --name staging --org <org-id> --type staging

# Types disponibles: development, staging, production
windflow env create --name prod --org <org-id> --type production

# Supprimer un environnement
windflow env delete <env-id>

# Avec confirmation automatique
windflow env delete <env-id> --confirm
```

### Déploiements

```bash
# Créer un déploiement
windflow deploy create --stack <stack-id> --environment <env-id>

# Avec nom et cible personnalisés
windflow deploy create \
  --stack <stack-id> \
  --environment <env-id> \
  --name "mon-deploiement" \
  --target docker

# Lister les déploiements
windflow deploy list

# Filtrer par environnement
windflow deploy list --environment <env-id>

# Filtrer par statut
windflow deploy list --status running

# En format JSON
windflow deploy list --format json

# Voir le statut d'un déploiement
windflow deploy status <deployment-id>

# Voir les logs
windflow deploy logs <deployment-id>

# Limiter le nombre de lignes
windflow deploy logs <deployment-id> --tail 50

# 📊 Suivre les logs en temps réel (NOUVEAU)
windflow deploy logs <deployment-id> --follow

# Suivre avec limitation
windflow deploy logs <deployment-id> --follow --tail 100

# Les logs se rafraîchissent toutes les 2 secondes
# Appuyez sur Ctrl+C pour arrêter le suivi
```

## 🎨 Interface moderne avec Rich

Le CLI utilise maintenant la bibliothèque Rich pour un affichage moderne et coloré :

### Tableaux colorés
- En-têtes en **cyan gras**
- Bordures élégantes automatiques
- Alignement intelligent des colonnes
- Support des caractères Unicode (✓, ✗, etc.)

### Messages stylisés
```
✓ Opération réussie          (vert)
✗ Erreur: Message d'erreur   (rouge)
⚠ Attention                   (jaune)
ℹ Information                 (bleu)
```

### Syntaxe JSON colorée
```bash
# JSON avec coloration syntaxique automatique
windflow org list --format json
```

## ⌨️ Auto-complétion

Le CLI inclut un système d'auto-complétion pour bash et zsh :

### Activation
```bash
# Temporaire (session en cours)
source cli/completion.sh

# Permanent pour bash
echo "source $(pwd)/cli/completion.sh" >> ~/.bashrc
source ~/.bashrc

# Permanent pour zsh
cat >> ~/.zshrc << 'EOF'
autoload -U +X compinit && compinit
autoload -U +X bashcompinit && bashcompinit
source $(pwd)/cli/completion.sh
EOF
source ~/.zshrc
```

### Fonctionnalités de complétion
- ✅ Commandes principales : `windflow <TAB>`
- ✅ Sous-commandes : `windflow deploy <TAB>`
- ✅ Options : `windflow deploy create --<TAB>`
- ✅ Arguments nommés

### Exemples d'utilisation
```bash
# Taper et appuyer sur TAB
windflow <TAB>
# Affiche: auth config org env deploy --help --version

windflow deploy <TAB>
# Affiche: create list status logs

windflow deploy create --<TAB>
# Affiche: --stack --environment --target --name
```

## 🔌 Architecture modulaire

Le CLI utilise une architecture modulaire permettant d'ajouter facilement de nouvelles fonctionnalités.

### Classe de base CLIServiceBase

Tous les services CLI héritent de `CLIServiceBase` :

```python
from cli.services.base import CLIServiceBase, register_service

@register_service
class MonNouveauService(CLIServiceBase):
    """Service CLI personnalisé."""
    
    # Noms de commandes gérées
    commands = ["mon-service", "ms"]
    
    # Configuration par défaut
    default_config = {
        "option": "valeur_par_defaut"
    }
    
    def subparser(self, parser):
        """Configure le parser pour ce service."""
        service_parser = parser.add_parser(
            'mon-service',
            help='Description du service'
        )
        subparsers = service_parser.add_subparsers(dest='action')
        
        # Ajouter les sous-commandes
        list_parser = subparsers.add_parser('list', help='Lister')
        create_parser = subparsers.add_parser('create', help='Créer')
        create_parser.add_argument('--name', required=True)
        
    def handle_command(self, args):
        """Traite les commandes du service."""
        if args.action == 'list':
            return self.list_items()
        elif args.action == 'create':
            return self.create_item(args.name)
        return 1
    
    def list_items(self):
        """Liste les éléments."""
        print("Liste des éléments...")
        return 0
    
    def create_item(self, name):
        """Crée un élément."""
        print(f"Création de {name}...")
        return 0
```

### Enregistrement automatique

Le décorateur `@register_service` enregistre automatiquement le service :

```python
# Le service est automatiquement découvert et intégré
windflow mon-service list
windflow mon-service create --name "test"
```

### Store centralisé

Le `CLIServiceStore` gère tous les services :

```python
from cli.services.base import service_store

# Récupérer tous les services
services = service_store.get_all_services()

# Trouver un service par nom
service = service_store.find_service("mon-service")

# Configurer tous les parsers
service_store.setup_parsers(main_parser)
```

## Exemples

### Workflow complet

```bash
# 1. Configuration initiale
windflow config set-url http://localhost:8000

# 2. Authentification
windflow auth login --username admin --password changeme123

# 3. Vérifier les organisations
windflow org list

# 4. Créer un déploiement
windflow deploy create \
  --stack web-app \
  --environment staging \
  --name "web-app-v1"

# 5. Suivre le statut
windflow deploy status <deployment-id>

# 6. Voir les logs
windflow deploy logs <deployment-id>
```

### Automatisation avec scripts

```bash
#!/bin/bash
# deploy.sh - Script de déploiement automatisé

set -e

# Configuration
export WINDFLOW_API_URL="http://localhost:8000"

# Authentification
windflow auth login \
  --username "${WINDFLOW_USER}" \
  --password "${WINDFLOW_PASSWORD}"

# Créer le déploiement
DEPLOY_ID=$(windflow deploy create \
  --stack "$1" \
  --environment "$2" \
  --format json | jq -r '.id')

echo "Déploiement créé: $DEPLOY_ID"

# Attendre la fin
while true; do
  STATUS=$(windflow deploy status "$DEPLOY_ID" --format json | jq -r '.status')
  echo "Statut: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 5
done

# Afficher les logs finaux
windflow deploy logs "$DEPLOY_ID"
```

## Structure de fichiers

```
~/.windflow/
├── config.yaml     # Configuration utilisateur
└── session.json    # Session et tokens (créé automatiquement)
```

## Formats de sortie

Le CLI supporte deux formats de sortie principaux :

### Format Table (par défaut)

```bash
windflow org list
```

```
+-----------+---------------------+--------+-------+---------------------+
| ID        | Nom                 | Slug   | Actif | Créé le             |
+-----------+---------------------+--------+-------+---------------------+
| 12345678... | Production        | prod   | ✓     | 2025-01-15 10:30:00 |
| 87654321... | Development       | dev    | ✓     | 2025-01-14 09:15:00 |
+-----------+---------------------+--------+-------+---------------------+
Total: 2 organisation(s)
```

### Format JSON

```bash
windflow org list --format json
```

```json
[
  {
    "id": "12345678-1234-5678-9012-123456789012",
    "name": "Production",
    "slug": "prod",
    "is_active": true,
    "created_at": "2025-01-15T10:30:00Z"
  }
]
```

## Codes de retour

- `0` : Succès
- `1` : Erreur générale
- `130` : Interruption par l'utilisateur (Ctrl+C)

## Dépannage

### Erreur "Non authentifié"

```bash
# Vérifier le statut d'authentification
windflow auth status

# Se reconnecter si nécessaire
windflow auth login --username <user> --password <pass>
```

### Erreur de connexion

```bash
# Vérifier l'URL de l'API
windflow config get-url

# Mettre à jour si nécessaire
windflow config set-url http://localhost:8000
```

### Debug

Pour obtenir plus d'informations sur une erreur, utilisez le format JSON :

```bash
windflow <commande> --format json
```

## Développement

### Structure du code complète

```
cli/
├── __init__.py              # Package CLI (version 0.1.0)
├── __main__.py              # Point d'entrée principal
├── config.py                # Gestion configuration hiérarchique
├── client.py                # Client HTTP avec gestion auth
├── session.py               # Gestion session/tokens persistants
├── utils.py                 # Utilitaires avec Rich (tableaux, messages colorés)
├── completion.sh            # Script auto-complétion bash/zsh
├── README.md                # Documentation (ce fichier)
├── commands/                # Commandes CLI modulaires
│   ├── __init__.py         # Exports des commandes
│   ├── auth.py             # Authentification (login, logout, status)
│   ├── config_cmd.py       # Configuration (set-url, show, get, set)
│   ├── org.py              # Organisations (list, get)
│   ├── env.py              # Environnements (list, get, create, delete) ✨ NOUVEAU
│   └── deploy.py           # Déploiements (create, list, status, logs + --follow) ✨
└── services/                # Architecture modulaire ✨ NOUVEAU
    ├── __init__.py         # Exports des services
    └── base.py             # CLIServiceBase + CLIServiceStore
```

### Ajouter une nouvelle commande (méthode simple)

1. **Créer un fichier** dans `cli/commands/` (ex: `stack.py`)
2. **Implémenter les fonctions** :
   ```python
   def setup_stack_parser(subparsers):
       """Configure le parser pour les commandes stack."""
       stack_parser = subparsers.add_parser('stack', help='Gestion des stacks')
       # ... ajouter les sous-commandes
   
   def handle_stack_command(args):
       """Gère les commandes stack."""
       # ... logique de traitement
       return 0  # Code de retour
   ```
3. **Ajouter dans** `cli/commands/__init__.py` :
   ```python
   from cli.commands.stack import setup_stack_parser, handle_stack_command
   
   __all__ = [..., 'setup_stack_parser', 'handle_stack_command']
   ```
4. **Ajouter dans** `cli/__main__.py` :
   ```python
   # Dans les imports
   from cli.commands import (..., setup_stack_parser, handle_stack_command)
   
   # Dans create_parser()
   setup_stack_parser(subparsers)
   
   # Dans main()
   elif args.command == 'stack':
       return handle_stack_command(args)
   ```

### Ajouter un service (méthode modulaire)

Pour des commandes plus complexes, utilisez l'architecture modulaire :

```python
# cli/services/stack_service.py
from cli.services.base import CLIServiceBase, register_service
from cli.utils import print_success, print_error, print_table

@register_service
class StackService(CLIServiceBase):
    """Service de gestion des stacks."""
    
    commands = ["stack", "stacks"]  # Noms de commandes gérées
    
    default_config = {
        "default_format": "table",
        "cache_enabled": True
    }
    
    def subparser(self, parser):
        """Configure le parser."""
        stack_parser = parser.add_parser(
            'stack',
            help='Gestion des stacks'
        )
        subparsers = stack_parser.add_subparsers(dest='stack_action')
        
        # Liste
        list_parser = subparsers.add_parser('list', help='Lister les stacks')
        list_parser.add_argument('--format', choices=['table', 'json'])
        
        # Déployer
        deploy_parser = subparsers.add_parser('deploy', help='Déployer un stack')
        deploy_parser.add_argument('stack_name', help='Nom du stack')
    
    def handle_command(self, args):
        """Traite les commandes."""
        if args.stack_action == 'list':
            return self.list_stacks(args.format or 'table')
        elif args.stack_action == 'deploy':
            return self.deploy_stack(args.stack_name)
        return 1
    
    def list_stacks(self, format):
        """Liste les stacks."""
        # Votre logique ici
        print_success("Stacks récupérés")
        return 0
    
    def deploy_stack(self, name):
        """Déploie un stack."""
        # Votre logique ici
        print_success(f"Stack {name} déployé")
        return 0
```

Le service est **automatiquement découvert** et intégré grâce au décorateur `@register_service`.

### Bonnes pratiques

1. **Type hints** : Utilisez les annotations de type
2. **Docstrings** : Documentez toutes les fonctions
3. **Gestion d'erreurs** : Utilisez try/except avec messages clairs
4. **Codes de retour** : 0 pour succès, >0 pour erreur
5. **Affichage Rich** : Utilisez `print_success`, `print_error`, `print_table` de `cli.utils`
6. **Tests** : Ajoutez des tests pour chaque nouvelle commande

### Utilitaires disponibles

```python
from cli.utils import (
    print_success,      # Message de succès (vert)
    print_error,        # Message d'erreur (rouge)
    print_warning,      # Message d'avertissement (jaune)
    print_info,         # Message d'information (bleu)
    print_table,        # Tableau Rich coloré
    print_json,         # JSON simple
    print_json_rich,    # JSON avec coloration syntaxique
    print_panel,        # Panneau Rich
    create_progress,    # Barre de progression
    confirm,            # Demander confirmation
    truncate,           # Tronquer texte
    format_timestamp,   # Formater timestamp ISO
    console             # Console Rich globale
)
```

### Exemple complet

Voir `cli/commands/env.py` pour un exemple complet avec :
- Configuration du parser
- Gestion des sous-commandes
- Formatage table/JSON
- Gestion d'erreurs
- Confirmation utilisateur

## Licence

Voir le fichier LICENSE à la racine du projet.
