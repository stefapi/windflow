# Définitions de Stacks WindFlow Marketplace

Ce répertoire contient les définitions YAML des stacks disponibles dans le marketplace WindFlow.

## 📋 Table des matières

- [Qu'est-ce qu'un stack ?](#quest-ce-quun-stack-)
- [Format du fichier YAML](#format-du-fichier-yaml)
- [Variables et types](#variables-et-types)
- [Génération automatique de secrets](#génération-automatique-de-secrets)
- [Chargement des stacks](#chargement-des-stacks)
- [Créer un nouveau stack](#créer-un-nouveau-stack)
- [Exemples](#exemples)

## Qu'est-ce qu'un stack ?

Un **stack** est un template Docker Compose réutilisable avec des variables configurables qui permet aux utilisateurs de déployer facilement des applications complexes via le marketplace WindFlow.

Chaque stack inclut :
- 🎯 **Métadonnées** : Nom, description, catégorie, auteur, licence
- 🐳 **Template Docker Compose** : Configuration complète des services
- ⚙️ **Variables configurables** : Options personnalisables par l'utilisateur
- 📚 **Documentation** : Guide d'utilisation et notes de déploiement

## Format du fichier YAML

### Structure de base

```yaml
# ============================================================================
# MÉTADONNÉES DU STACK
# ============================================================================
metadata:
  name: "Nom du Stack"
  version: "1.0.0"
  category: "Catégorie"
  author: "Auteur"
  license: "MIT"
  description: |
    Description multiligne du stack.
    
    Fonctionnalités principales, cas d'usage, etc.
  
  icon_url: "https://example.com/icon.svg"
  documentation_url: "https://example.com/docs"
  screenshots:
    - "https://example.com/screenshot1.png"
    - "https://example.com/screenshot2.png"
  tags:
    - tag1
    - tag2
  is_public: true

# ============================================================================
# TEMPLATE DOCKER COMPOSE
# ============================================================================
template:
  version: "3.9"
  services:
    app:
      image: "myapp:{{ version }}"
      environment:
        DB_PASSWORD: "{{ db_password }}"
      ports:
        - "{{ port }}:3000"
  volumes:
    app_data:
      driver: local

# ============================================================================
# VARIABLES CONFIGURABLES
# ============================================================================
variables:
  version:
    type: string
    label: "Version de l'application"
    description: "Version à déployer"
    default: "latest"
    enum: ["latest", "1.0.0", "0.9.0"]
    required: true
    group: "Configuration"
  
  db_password:
    type: password
    label: "Mot de passe base de données"
    description: "Mot de passe sécurisé pour la DB"
    default: "{{ generate_password(20) }}"
    required: true
    min_length: 12
    group: "Sécurité"
  
  port:
    type: number
    label: "Port HTTP"
    description: "Port d'accès à l'application"
    default: 8080
    minimum: 1
    maximum: 65535
    group: "Réseau"
```

## Variables et types

### Types supportés

| Type | Description | Exemple |
|------|-------------|---------|
| `string` | Chaîne de caractères | Nom de domaine, URL |
| `number` | Nombre entier | Port, nombre de workers |
| `boolean` | Booléen true/false | Activer/désactiver une option |
| `password` | Mot de passe masqué | Credentials, secrets |
| `enum` | Liste de choix | Versions, environnements |
| `textarea` | Texte multiligne | Configuration, notes |

### Propriétés des variables

```yaml
variable_name:
  type: string                    # Type de la variable (obligatoire)
  label: "Label affiché"          # Label interface utilisateur (obligatoire)
  description: "Description..."   # Description détaillée
  default: "valeur"               # Valeur par défaut
  required: true                  # Champ obligatoire ?
  group: "Nom du groupe"          # Groupement dans l'interface
  help: "Aide contextuelle"       # Tooltip d'aide
  
  # Contraintes spécifiques selon le type
  pattern: "^[a-z]+$"            # Regex pour string
  enum: ["opt1", "opt2"]         # Liste de choix
  minimum: 1                     # Valeur minimale pour number
  maximum: 100                   # Valeur maximale pour number
  min_length: 8                  # Longueur minimale pour string/password
  max_length: 255                # Longueur maximale pour string/password
  
  # Dépendances conditionnelles
  depends_on:
    autre_variable: true         # Afficher seulement si autre_variable = true
```

### Exemples de variables

#### String avec validation

```yaml
domain:
  type: string
  label: "Nom de domaine"
  description: "Domaine d'accès à l'application"
  default: "app.example.com"
  required: true
  pattern: "^[a-zA-Z0-9][a-zA-Z0-9-\\.]*[a-zA-Z0-9]$"
  help: "Le domaine doit pointer vers votre serveur"
  group: "Configuration réseau"
```

#### Number avec contraintes

```yaml
max_workers:
  type: number
  label: "Nombre de workers"
  description: "Workers pour traiter les requêtes"
  default: 2
  minimum: 1
  maximum: 16
  help: "Recommandé: 2 × nombre de CPU cores"
  group: "Performance"
```

#### Boolean simple

```yaml
enable_ssl:
  type: boolean
  label: "Activer SSL"
  description: "Activer le chiffrement SSL/TLS"
  default: true
  group: "Sécurité"
```

#### Password avec génération automatique

```yaml
db_password:
  type: password
  label: "Mot de passe base de données"
  description: "Mot de passe PostgreSQL (généré automatiquement)"
  default: "{{ generate_password(20) }}"
  required: true
  min_length: 12
  group: "Sécurité"
```

#### Enum avec choix

```yaml
app_version:
  type: string
  label: "Version de l'application"
  description: "Version à déployer"
  default: "1.26.1"
  enum:
    - "1.26.1"
    - "1.25.2"
    - "1.24.2"
    - "latest"
  required: true
  group: "Configuration"
```

#### Variable conditionnelle

```yaml
enable_email:
  type: boolean
  label: "Activer l'envoi d'emails"
  default: false
  group: "Email"

email_host:
  type: string
  label: "Serveur SMTP"
  description: "Adresse du serveur SMTP"
  required: false
  group: "Email"
  depends_on:
    enable_email: true  # Affiché seulement si enable_email = true
```

## Génération automatique de secrets

WindFlow supporte la génération automatique de mots de passe et secrets dans les valeurs par défaut :

### `{{ generate_password(N) }}`

Génère un mot de passe aléatoire sécurisé de N caractères avec lettres, chiffres et symboles.

```yaml
db_password:
  type: password
  label: "Mot de passe DB"
  default: "{{ generate_password(20) }}"  # Génère un mot de passe de 20 caractères
```

### `{{ generate_secret(N) }}`

Génère une clé secrète alphanumérique de N caractères.

```yaml
secret_key:
  type: password
  label: "Clé secrète"
  default: "{{ generate_secret(50) }}"  # Génère une clé de 50 caractères
```

### Références entre variables

Vous pouvez référencer d'autres variables dans les valeurs par défaut :

```yaml
domain:
  type: string
  label: "Domaine"
  default: "app.example.com"

from_email:
  type: string
  label: "Email expéditeur"
  default: "noreply@{{ domain }}"  # Utilise la valeur de 'domain'
```

## Chargement des stacks

### Script CLI

Le script `seed_stacks.py` permet de charger les stacks dans la base de données :

```bash
# Charger tous les stacks
python -m app.scripts.seed_stacks

# Lister les stacks disponibles
python -m app.scripts.seed_stacks --list

# Charger un stack spécifique
python -m app.scripts.seed_stacks --stack baserow

# Forcer la mise à jour des stacks existants
python -m app.scripts.seed_stacks --force

# Valider les fichiers sans importer
python -m app.scripts.seed_stacks --dry-run
```

### Chargement automatique au démarrage

Les stacks sont automatiquement chargés au démarrage de l'application si l'option est activée dans la configuration.

## Créer un nouveau stack

### 1. Créer le fichier YAML

Créez un fichier `mon-stack.yaml` dans ce répertoire avec la structure complète.

### 2. Définir les métadonnées

```yaml
metadata:
  name: "Mon Application"
  version: "1.0.0"
  category: "Web Applications"
  author: "Votre Nom"
  license: "MIT"
  description: |
    Description détaillée de votre stack.
  is_public: true
  tags:
    - webapp
    - nodejs
```

### 3. Créer le template Docker Compose

```yaml
template:
  version: "3.9"
  services:
    app:
      image: "myapp:{{ version }}"
      environment:
        PORT: "{{ port }}"
      ports:
        - "{{ port }}:3000"
```

### 4. Définir les variables

```yaml
variables:
  version:
    type: string
    label: "Version"
    default: "latest"
    required: true
  
  port:
    type: number
    label: "Port HTTP"
    default: 8080
    minimum: 1
    maximum: 65535
```

### 5. Valider et charger

```bash
# Valider le fichier
python -m app.scripts.seed_stacks --dry-run

# Charger le stack
python -m app.scripts.seed_stacks --stack mon-stack
```

## Exemples

### Stack simple (Application web)

Voir `baserow.yaml` pour un exemple complet d'application multi-services avec :
- PostgreSQL
- Redis
- Backend API
- Frontend
- Reverse proxy Caddy

### Bonnes pratiques

1. **Sécurité**
   - Utilisez `generate_password()` pour les credentials
   - Ne jamais mettre de secrets en dur
   - Utilisez le type `password` pour les données sensibles

2. **Documentation**
   - Description claire et détaillée
   - Help contextuel sur les variables complexes
   - Notes de déploiement avec exemples

3. **Variables**
   - Valeurs par défaut sécurisées
   - Validation appropriée (pattern, min/max)
   - Groupement logique des variables

4. **Docker Compose**
   - Health checks pour tous les services
   - Volumes nommés pour la persistance
   - Networks isolés
   - Resource limits appropriées

5. **Nommage**
   - Nom de fichier en kebab-case: `mon-stack.yaml`
   - Variables en snake_case: `db_password`
   - Labels explicites en français

## Support

Pour toute question ou problème :
- Documentation : `/doc/spec/`
- Issues GitHub : `https://github.com/windflow/issues`
- Exemples : Consultez `baserow.yaml` comme référence

---

**WindFlow** - Déploiement intelligent de containers Docker
