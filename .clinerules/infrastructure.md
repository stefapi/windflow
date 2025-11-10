# Règles d'Infrastructure et Fichiers Annexes - WindFlow

## Vue d'Ensemble

Ce document définit les règles de structuration et d'organisation des fichiers annexes de type infrastructure, outils de développement, et fichiers de support pour le projet WindFlow.

## Principes Généraux

### Organisation Hiérarchique
- **Fichiers de configuration racine** : Variables d'environnement, configuration Docker, outils de développement
- **Répertoire dev/** : Outils, données et templates de développement
- **Scripts spécialisés** : Génération de code, automatisation, validation
- **Templates modulaires** : Génération automatique de code et configuration

### Conventions de Nommage
- **kebab-case** pour les fichiers Docker et compose : `docker-compose.yml`, `docker-compose.override.yml`
- **lowercase** pour les fichiers de configuration : `makefile`, `dockerfile`, `.env`
- **UPPERCASE** pour les fichiers de documentation projet : `README.md`, `CHANGELOG.md`
- **snake_case** pour les scripts Python : `generate_api.py`, `validate_config.py`

## Makefile - Orchestrateur Principal

### Structure Obligatoire
Le Makefile doit être organisé en sections clairement délimitées :

#### Section Variables
```makefile
# ============================================================================
# VARIABLES
# ============================================================================

# Core tools
PYTHON ?= python3
POETRY ?= poetry
PNPM ?= pnpm
DOCKER ?= docker
DOCKER_COMPOSE ?= docker-compose

# Project paths
BACKEND_DIR = windflow
FRONTEND_DIR = frontend
CLI_DIR = cli

# Git and versioning
GIT_BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
VERSION = $(shell git describe --long --first-parent 2>/dev/null || echo "0.1.0-dev")
```

#### Section Helper Scripts
```makefile
# ============================================================================
# HELPER SCRIPTS
# ============================================================================

define BROWSER_PYSCRIPT
import os, webbrowser, sys
from urllib.request import pathname2url
webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys
for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT
```

#### Sections de Commandes
1. **COMMON COMMANDS** : `help`, `setup`, `install`, `outdated`
2. **CLEANING COMMANDS** : `clean`, `clean-build`, `clean-tests`, `clean-data`
3. **BACKEND COMMANDS** : `backend`, `backend-test`, `backend-lint`, `backend-format`
4. **FRONTEND COMMANDS** : `frontend`, `frontend-test`, `frontend-lint`, `frontend-build`
5. **CLI COMMANDS** : `cli`, `cli-test`, `cli-build`, `cli-install`
6. **DEVELOPMENT COMMANDS** : `dev`, `serve`, `migrate`, `format`, `lint`, `test`
7. **DOCKER COMMANDS** : `docker-build`, `docker-up`, `docker-dev`, `docker-prod`
8. **DEPLOYMENT COMMANDS** : `dist`, `release`, `stage`
9. **CODE GENERATION COMMANDS** : `generate-api`, `generate-types`, `generate-docs`
10. **ALL-IN-ONE COMMANDS** : `all`, `ci`, `prepare`

### Conventions de Commandes
- **Préfixes obligatoires** : `backend-`, `frontend-`, `cli-`, `docker-`
- **Suffixes standards** : `-test`, `-lint`, `-format`, `-build`, `-clean`
- **Aide contextuelle** : Chaque commande doit avoir un commentaire `## Description`
- **Gestion d'erreurs** : Utilisation de `set -e` et validation des prérequis

## Configuration Docker

### Dockerfile Backend
**Objectifs** : Image multi-stage optimisée, sécurité non-root, cache dépendances, healthcheck
- FROM python:3.11-slim (base et runtime stages)
- USER appuser (sécurité)
- HEALTHCHECK + labels obligatoires

### Dockerfile Frontend  
**Objectifs** : Build optimisé cache NPM, nginx production, security headers
- FROM node:20-alpine (builder) + nginx:alpine (runtime)
- Multi-stage pour optimisation taille

### Docker Compose - Structure Modulaire

#### docker-compose.yml (Base)
**Objectifs** : Services production-ready, réseaux isolés, volumes persistants, variables d'environnement
- Services : backend, frontend, database (postgres), redis
- Networks : backend-network, frontend-network  
- Volumes nommés pour persistance

#### docker-compose.override.yml (Développement)
**Objectifs** : Hot reload, ports debug, volumes bind code source, services dev
- Surcharges : build local, volumes bind, ports exposés
- Services dev : adminer, mailhog
- Environment : DEBUG=true, RELOAD=true

#### docker-compose.prod.yml (Production)
**Objectifs** : Configuration sécurisée, reverse proxy SSL, monitoring, backup
- Restart policies et resource limits
- Services : traefik (proxy), prometheus, grafana
- Volumes : letsencrypt, monitoring data

## Scripts de Développement

### Structure dev/scripts/

#### Scripts de Configuration
```
dev/scripts/setup/
├── install-dependencies.py    # Installation complète environnement
├── setup-database.py         # Initialisation base de données
├── configure-vault.py        # Configuration HashiCorp Vault
└── setup-git-hooks.sh       # Installation hooks Git
```

#### Scripts de Génération
```
dev/scripts/generation/
├── generate-api-client.py     # Client TypeScript depuis OpenAPI
├── generate-types.py          # Types partagés backend/frontend
├── generate-migrations.py     # Migrations base de données
├── generate-docs.py           # Documentation automatique
└── generate-terraform.py      # Infrastructure as Code
```

#### Scripts de Validation
```
dev/scripts/validation/
├── validate-commit-msg.py     # Convention commits
├── validate-api-schema.py     # Cohérence schémas API
├── validate-translations.py   # Traductions complètes
└── check-security.py          # Audit sécurité automatique
```

#### Scripts de Déploiement
```
dev/scripts/deployment/
├── build-images.py            # Construction images Docker
├── deploy-staging.py          # Déploiement environnement staging
├── deploy-production.py       # Déploiement production
└── backup-database.py         # Sauvegarde base de données
```

### Conventions des Scripts
- **Shebang obligatoire** : `#!/usr/bin/env python3` ou `#!/bin/bash`
- **Documentation** : Docstring détaillée avec usage et exemples
- **Gestion d'erreurs** : Exit codes appropriés et messages explicites
- **Configuration** : Variables d'environnement et arguments CLI
- **Logging** : Utilisation du logging Python structuré
- **Idempotence** : Scripts réexécutables sans effet de bord

### Scripts Racine Spécialisés

#### entrypoint.sh (Docker)
```bash
# Objectifs :
# - Point d'entrée standardisé pour containers
# - Initialisation base de données si nécessaire
# - Configuration runtime dynamique
# - Gestion gracieuse des signaux

#!/bin/bash
set -e

# Initialisation base de données
if [ "$1" = "init-db" ]; then
    python -m windflow.database.init_db
    shift
fi

# Démarrage de l'application
exec "$@"
```

#### debug.sh (Développement)
```bash
# Objectifs :
# - Démarrage rapide en mode debug
# - Variables d'environnement de développement
# - Hot reload et logging verbeux
# - Outils de debugging intégrés

#!/bin/bash
export DEBUG=true
export LOG_LEVEL=DEBUG
export RELOAD=true

python -m windflow.main --reload --log-level debug
```

#### install.sh (Installation automatique)
```bash
# Objectifs :
# - Installation complète automatisée
# - Détection de l'environnement système
# - Installation des dépendances système
# - Configuration initiale du projet

#!/bin/bash
set -e

echo "🚀 Installation WindFlow"

# Détection système
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y python3-pip
elif command -v brew >/dev/null 2>&1; then
    brew install python
fi

# Installation Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Installation projet
poetry install --with dev
poetry run pre-commit install

echo "✅ Installation terminée"
```

## Templates de Génération

### Structure dev/templates/

#### Templates Backend
```
dev/templates/backend/
├── service.py.jinja           # Service métier avec Repository pattern
├── model.py.jinja             # Modèle SQLAlchemy avec relations
├── schema.py.jinja            # Schéma Pydantic avec validation
├── router.py.jinja            # Router FastAPI avec documentation
├── test_service.py.jinja      # Tests unitaires service
└── test_endpoints.py.jinja    # Tests intégration endpoints
```

#### Templates Frontend
```
dev/templates/frontend/
├── component.vue.jinja        # Composant Vue.js avec TypeScript
├── composable.ts.jinja        # Composable avec tests
├── store.ts.jinja             # Store Pinia avec persistence
├── service.ts.jinja           # Service API avec interceptors
├── types.ts.jinja             # Types TypeScript générés
└── test.ts.jinja              # Tests Vitest
```

#### Templates Infrastructure
```
dev/templates/infrastructure/
├── dockerfile.jinja           # Dockerfile optimisé multi-stage
├── docker-compose.jinja       # Compose avec services spécifiques
├── nginx.conf.jinja           # Configuration nginx sécurisée
├── kubernetes.yaml.jinja      # Manifestes Kubernetes
└── terraform.tf.jinja         # Modules Terraform
```

#### Templates Documentation
```
dev/templates/documentation/
├── api-doc.md.jinja          # Documentation endpoint API
├── architecture.md.jinja     # Documentation architecture
├── contributing.md.jinja     # Guide de contribution
└── changelog.md.jinja        # Template changelog
```

### Conventions des Templates
- **Extension .jinja** : Tous les templates utilisent Jinja2
- **Variables contextuelles** : `{{ project_name }}`, `{{ service_name }}`, `{{ model_name }}`
- **Conditions** : `{% if feature_enabled %}...{% endif %}`
- **Boucles** : `{% for field in fields %}...{% endfor %}`
- **Includes** : `{% include 'common/header.jinja' %}`
- **Macros** : Réutilisation de blocs communs

## Package.json Frontend

### Structure Obligatoire des Scripts
**Objectifs** : Scripts groupés par fonction, engines Node >=20 + pnpm >=9, type module
1. **Build & Dev** : `dev`, `build`, `build-prod`, `preview*`
2. **Quality Assurance** : `typecheck`, `lint*`, `css*`, `format*`
3. **Testing** : `test*`, `e2e*`, `record`
4. **Maintenance** : `up`, `sizecheck`, `unlighthouse`

### Configuration Dependencies
- **Engines** : Node.js >=20, pnpm >=9
- **Type** : `"module"` pour ES modules
- **Private** : `"private": true` pour projets non-publiés
- **Lint-staged** : Configuration hooks pre-commit

## Fichiers de Configuration

### Variables d'Environnement (.env)
**Objectifs** : Documentation variables requises, valeurs sécurisées, groupement logique
- **Application** : APP_NAME, APP_VERSION, APP_ENV, DEBUG
- **API** : API_HOST, API_PORT, API_WORKERS
- **Database** : DATABASE_URL, DATABASE_POOL_SIZE
- **Security** : SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES
- **Services externes** : VAULT_URL, LLM_PROVIDER

### .env.example (Template)
**Objectifs** : Template avec commentaires explicatifs et valeurs par défaut sécurisées
- Sections délimitées par commentaires
- Alternatives de configuration documentées
- Instructions de génération (ex: openssl rand -hex 32)

### .gitignore Structuré
**Objectifs** : Exclusions organisées par technologie avec sections délimitées
- **Python** : __pycache__, *.pyc, venv/, .env
- **Node.js** : node_modules/, npm-debug.log*
- **Databases** : *.db, *.sqlite
- **Development** : dev/data/, *.log, .coverage
- **IDEs** : .vscode/, .idea/, *.swp
- **OS** : .DS_Store, Thumbs.db

## Monitoring et Observabilité

### Prometheus Configuration
**Objectifs** : Métriques application/infrastructure, service discovery, alerting rules
- Configuration scrape_configs pour windflow-backend, windflow-frontend
- Retention adaptée à l'usage, règles d'alerting définies

### Grafana Dashboard Config
**Objectifs** : Tableaux de bord pour métriques clés WindFlow
- API Response Time, Deployment Success Rate
- Panels configurés avec requêtes PromQL appropriées

## Validation et Contrôle Qualité

### Pre-commit Configuration
**Objectifs** : Validation automatique, formatage cohérent, détection sécurité, performance CI/CD
- **Hooks standards** : trailing-whitespace, end-of-file-fixer, check-yaml
- **Python** : black, isort, flake8, mypy, bandit
- **Frontend** : lint personnalisé avec pnpm

Ces règles assurent une infrastructure cohérente, maintenable et scalable pour WindFlow.
