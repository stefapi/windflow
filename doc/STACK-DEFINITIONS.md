# Stack Definitions - Guide du Développeur

## Vue d'ensemble

Le système de **Stack Definitions** permet de définir des templates de déploiement réutilisables dans des fichiers YAML. Ces définitions sont automatiquement chargées dans la base de données au démarrage du backend, créant ainsi un marketplace de stacks prêts à l'emploi.

## Architecture

### Composants

1. **Fichiers YAML** (`stacks_definitions/*.yaml`)
   - Définitions des stacks avec metadata, template et variables
   - Format validé par Pydantic

2. **Schemas de validation** (`backend/app/schemas/stack_definition.py`)
   - `StackDefinition`: Structure complète d'une définition
   - `StackDefinitionMetadata`: Informations sur le stack
   - `StackDefinitionVariable`: Configuration des variables

3. **Service de chargement** (`backend/app/services/stack_definitions_loader.py`)
   - `StackDefinitionsLoader`: Scanne et charge les définitions
   - Gestion des stratégies de mise à jour
   - Comparaison de versions

4. **Intégration au démarrage** (`backend/app/database_seed.py`)
   - `seed_stack_definitions()`: Fonction appelée au premier démarrage
   - Chargement automatique si activé dans la configuration

### Flux de chargement

```
Démarrage backend
    ↓
database_seed.py
    ↓
seed_stack_definitions()
    ↓
StackDefinitionsLoader
    ↓
Scan stacks_definitions/*.yaml
    ↓
Validation Pydantic
    ↓
Insertion/Mise à jour en base
    ↓
Table `stacks` peuplée
```

## Configuration

### Variables d'environnement

Dans `.env` ou configuration backend :

```bash
# Chemin vers les définitions YAML
STACK_DEFINITIONS_PATH=stacks_definitions

# Activer le chargement automatique au démarrage
AUTO_LOAD_STACK_DEFINITIONS=true

# Stratégie de mise à jour
# - skip_existing: Ne rien faire si le stack existe
# - update_if_newer: Mettre à jour si version plus récente
# - force_update: Toujours écraser
STACK_UPDATE_STRATEGY=update_if_newer
```

### Configuration dans `backend/app/config.py`

```python
class Settings(BaseSettings):
    # ...
    stack_definitions_path: str = "stacks_definitions"
    auto_load_stack_definitions: bool = True
    stack_update_strategy: str = "update_if_newer"
```

## Format des fichiers YAML

### Structure complète

```yaml
# ============================================================================
# MÉTADONNÉES DU STACK
# ============================================================================
metadata:
  name: "Nom du Stack"              # Requis - Nom affiché
  version: "1.0.0"                  # Requis - Version semver
  category: "Database"              # Requis - Catégorie
  author: "Auteur"                  # Optionnel
  license: "MIT"                    # Optionnel
  
  description: |                    # Requis - Description détaillée
    Description du stack avec fonctionnalités principales.
    Peut être sur plusieurs lignes.
  
  icon_url: "https://..."           # Optionnel - URL de l'icône
  documentation_url: "https://..."  # Optionnel - Lien documentation
  screenshots:                      # Optionnel - Liste de screenshots
    - "https://..."
  
  tags:                             # Requis - Liste de tags
    - database
    - postgresql
  
  is_public: true                   # Requis - Visibilité publique
  
  target_type: "docker"             # Requis - Type de déploiement

# ============================================================================
# TEMPLATE DE DÉPLOIEMENT
# ============================================================================
template:
  # Contenu du template (Docker, Docker Compose, etc.)
  # Variables Jinja2 avec {{ variable_name }}
  image: "postgres:{{ version }}"
  environment:
    DB_PASSWORD: "{{ db_password }}"

# ============================================================================
# VARIABLES CONFIGURABLES
# ============================================================================
variables:
  version:
    type: string                    # Types: string, number, boolean, password
    label: "Version PostgreSQL"     # Label affiché dans l'interface
    description: "Version à déployer"
    default: "16"                   # Valeur par défaut
    required: true                  # Champ obligatoire
    enum:                           # Liste de valeurs possibles
      - "16"
      - "15"
      - "14"
    group: "Configuration"          # Groupe dans l'interface
    help: "Texte d'aide pour l'utilisateur"
    
  db_password:
    type: password
    label: "Mot de passe"
    default: "{{ generate_password(24) }}"  # Génération automatique
    required: true
    min_length: 12                  # Validation min/max
```

### Types de déploiement (`target_type`)

Valeurs possibles dans l'enum `TargetType` :
- `docker` : Container Docker simple
- `docker_compose` : Stack Docker Compose multi-services
- `docker_swarm` : Stack Docker Swarm
- `kubernetes` : Déploiement Kubernetes
- `vm` : Machine virtuelle
- `physical` : Serveur physique

### Types de variables

#### String
```yaml
name:
  type: string
  label: "Nom du service"
  default: "myservice"
  required: true
  pattern: "^[a-z0-9-]+$"     # Regex de validation
  min_length: 3
  max_length: 50
  enum:                        # Liste de choix (optionnel)
    - "option1"
    - "option2"
```

#### Number
```yaml
port:
  type: number
  label: "Port"
  default: 8080
  required: true
  minimum: 1
  maximum: 65535
```

#### Boolean
```yaml
enable_ssl:
  type: boolean
  label: "Activer SSL"
  default: true
  required: false
```

#### Password
```yaml
password:
  type: password
  label: "Mot de passe"
  default: "{{ generate_password(24) }}"
  required: true
  min_length: 12
```

### Validation Pydantic

Toutes les définitions YAML sont validées par Pydantic au chargement. Erreurs courantes :

- **Version invalide** : Doit être au format semver (ex: `1.0.0`)
- **target_type invalide** : Doit être une valeur de l'enum `TargetType`
- **Champs requis manquants** : name, version, category, description, tags, is_public, target_type
- **Types de variables invalides** : Doit être string, number, boolean ou password

## Exemples

### Exemple 1 : Container Docker simple (PostgreSQL)

```yaml
metadata:
  name: "PostgreSQL"
  version: "1.0.0"
  category: "Database"
  description: "Base de données PostgreSQL"
  tags:
    - database
    - postgresql
  is_public: true
  target_type: "docker"

template:
  image: "postgres:{{ version }}"
  container_name: "{{ name }}"
  environment:
    POSTGRES_PASSWORD: "{{ password }}"
  ports:
    - "{{ port }}:5432"
  volumes:
    - "postgres_data:/var/lib/postgresql/data"

variables:
  version:
    type: string
    label: "Version"
    default: "16"
    required: true
  
  name:
    type: string
    label: "Nom du container"
    default: "postgres"
    required: true
  
  password:
    type: password
    label: "Mot de passe"
    default: "{{ generate_password(24) }}"
    required: true
    min_length: 12
  
  port:
    type: number
    label: "Port"
    default: 5432
    required: true
```

### Exemple 2 : Docker Compose (Application multi-services)

```yaml
metadata:
  name: "Web Application Stack"
  version: "1.0.0"
  category: "Web"
  description: "Stack complet avec frontend, backend et base de données"
  tags:
    - web
    - fullstack
  is_public: true
  target_type: "docker_compose"

template:
  version: "3.9"
  
  services:
    frontend:
      image: "nginx:{{ nginx_version }}"
      ports:
        - "{{ frontend_port }}:80"
      depends_on:
        - backend
    
    backend:
      image: "{{ backend_image }}"
      environment:
        DATABASE_URL: "postgresql://postgres:{{ db_password }}@db:5432/app"
      depends_on:
        - db
    
    db:
      image: "postgres:{{ postgres_version }}"
      environment:
        POSTGRES_PASSWORD: "{{ db_password }}"
      volumes:
        - db_data:/var/lib/postgresql/data
  
  volumes:
    db_data:

variables:
  nginx_version:
    type: string
    label: "Version Nginx"
    default: "alpine"
    required: true
  
  backend_image:
    type: string
    label: "Image backend"
    default: "myapp/backend:latest"
    required: true
  
  postgres_version:
    type: string
    label: "Version PostgreSQL"
    default: "16"
    required: true
  
  frontend_port:
    type: number
    label: "Port frontend"
    default: 8080
    required: true
  
  db_password:
    type: password
    label: "Mot de passe DB"
    default: "{{ generate_password(20) }}"
    required: true
    min_length: 12
```

## Workflow de développement

### 1. Créer une nouvelle définition

```bash
# Créer un nouveau fichier YAML
cd stacks_definitions/
touch mon-stack.yaml
```

### 2. Éditer le fichier

Suivre la structure documentée ci-dessus avec tous les champs requis.

### 3. Valider localement

```python
# Script de validation (optionnel)
from backend.app.schemas.stack_definition import StackDefinition
import yaml

with open('stacks_definitions/mon-stack.yaml') as f:
    data = yaml.safe_load(f)
    definition = StackDefinition(**data)
    print(f"✓ Définition valide: {definition.metadata.name}")
```

### 4. Tester le chargement

```bash
# Supprimer la base de données pour forcer le seeding
rm -f data/windflow/windflow.db

# Redémarrer le backend
make backend

# Vérifier les logs de démarrage
# Devrait afficher : "Stack definitions: X créé(s), Y mis à jour"
```

### 5. Vérifier en base de données

```bash
# Se connecter à la base
sqlite3 data/windflow/windflow.db

# Lister les stacks chargés
SELECT name, version, category, target_type FROM stacks;
```

## Stratégies de mise à jour

### skip_existing

Ne charge que les nouveaux stacks. Si un stack avec le même nom et version existe, il est ignoré.

```bash
STACK_UPDATE_STRATEGY=skip_existing
```

**Cas d'usage** : Production stable, pas de modifications des définitions existantes.

### update_if_newer

Met à jour uniquement si la version dans le YAML est plus récente que celle en base.

```bash
STACK_UPDATE_STRATEGY=update_if_newer  # Recommandé
```

**Cas d'usage** : Développement actif, mise à jour progressive des stacks.

**Comparaison de versions** : Utilise la comparaison semver (1.2.0 > 1.1.9).

### force_update

Écrase toujours les stacks existants avec les définitions YAML, quelle que soit la version.

```bash
STACK_UPDATE_STRATEGY=force_update
```

**Cas d'usage** : Développement, correction de bugs dans les templates.

⚠️ **Attention** : Peut écraser des modifications manuelles en base.

## Gestion des versions

### Format Semver

Toutes les versions doivent suivre le format Semver : `MAJOR.MINOR.PATCH`

```yaml
version: "1.0.0"    # ✓ Valide
version: "2.1.3"    # ✓ Valide
version: "1.0"      # ✗ Invalide (manque PATCH)
version: "v1.0.0"   # ✗ Invalide (pas de préfixe)
```

### Règles de versionnement

- **MAJOR** : Changements incompatibles (ex: structure template modifiée)
- **MINOR** : Nouvelles fonctionnalités compatibles (ex: nouvelles variables)
- **PATCH** : Corrections de bugs (ex: fix dans le template)

### Identifiant unique

Chaque stack est identifié par la combinaison **name + version**.

Cela permet d'avoir plusieurs versions du même stack :
- `PostgreSQL v1.0.0`
- `PostgreSQL v1.1.0`
- `PostgreSQL v2.0.0`

## Variables Jinja2

Les templates utilisent Jinja2 pour les substitutions de variables.

### Syntaxe de base

```yaml
template:
  image: "{{ image_name }}:{{ image_tag }}"
  environment:
    PASSWORD: "{{ password }}"
```

### Fonctions disponibles

#### generate_password(length)

Génère un mot de passe aléatoire sécurisé.

```yaml
password:
  type: password
  default: "{{ generate_password(24) }}"
```

#### generate_secret(length)

Génère une clé secrète pour chiffrement.

```yaml
secret_key:
  type: password
  default: "{{ generate_secret(50) }}"
```

## Bonnes pratiques

### ✅ À faire

1. **Versionner correctement** : Incrémenter la version à chaque modification
2. **Documenter** : Description détaillée et notes de déploiement
3. **Valider** : Tester le chargement avant de commit
4. **Sécuriser** : Utiliser `type: password` pour les secrets
5. **Grouper** : Organiser les variables par groupe logique
6. **Aider** : Ajouter des `help` pour guider les utilisateurs

### ❌ À éviter

1. **Secrets en dur** : Ne jamais mettre de mots de passe en clair
2. **Versions fixes** : Ne pas figer sur `latest` sans justification
3. **Validation manquante** : Toujours définir min_length, pattern, etc.
4. **Documentation vide** : Les utilisateurs ont besoin de contexte
5. **target_type incorrect** : Doit correspondre au template réel

## Dépannage

### Erreur : "Le répertoire stacks_definitions n'existe pas"

```bash
mkdir -p stacks_definitions
```

### Erreur : "Version invalide"

Vérifier que la version suit le format semver strict `X.Y.Z`.

### Erreur : "target_type invalide"

Valeurs autorisées : `docker`, `docker_compose`, `docker_swarm`, `kubernetes`, `vm`, `physical`.

### Les stacks ne se chargent pas

1. Vérifier que `AUTO_LOAD_STACK_DEFINITIONS=true`
2. Vérifier les logs au démarrage du backend
3. Valider le YAML manuellement avec Python

### Les mises à jour ne s'appliquent pas

1. Vérifier que la version dans le YAML est plus récente
2. Utiliser `STACK_UPDATE_STRATEGY=force_update` temporairement
3. Supprimer et recréer la base de données en développement

## API et utilisation

### Lister les stacks disponibles

```bash
GET /api/v1/stacks
```

### Créer un déploiement depuis un stack

```bash
POST /api/v1/deployments
{
  "stack_id": "uuid-du-stack",
  "variables": {
    "version": "16",
    "port": 5432,
    "password": "mon-mot-de-passe"
  }
}
```

## Références

- **Modèle Stack** : `backend/app/models/stack.py`
- **Schemas** : `backend/app/schemas/stack_definition.py`
- **Loader** : `backend/app/services/stack_definitions_loader.py`
- **Seeding** : `backend/app/database_seed.py`
- **Exemples** : `stacks_definitions/postgresql.yaml`, `stacks_definitions/baserow.yaml`

---

**Version** : 1.0.0  
**Dernière mise à jour** : 2025-01-19
