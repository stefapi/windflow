# Workflow dev, commits, dépendances

Toutes les commandes standards sont présentes dans le `Makefile` à la racine du projet.

---

## Cibles Makefile principales

### Setup & nettoyage

| Cible | Description |
|-------|-------------|
| `make setup` | 🏗 Setup complet de l'environnement de dev (Poetry install + pnpm install + .env) |
| `make install` | 📦 Installation de la version de développement (Poetry install) |
| `make clean` | 🧹 Nettoyage complet (data, pyc, tests, frontend) |
| `make clean-data` | ⚠️ Suppression de toutes les données dev |
| `make clean-build` | 🧹 Nettoyage des artefacts de build Python |
| `make clean-tests` | 🧹 Suppression des artefacts de test et coverage |
| `make clean-pyc` | 🧹 Suppression des fichiers .pyc et __pycache__ |
| `make clean-frontend` | 🧹 Suppression des artefacts de build frontend |
| `make purge` | 🧹 Suppression complète pour environnement frais (clean + venv) |

### Backend

| Cible | Description |
|-------|-------------|
| `make backend` | 🎬 Démarrer le serveur de développement backend (uvicorn --reload) |
| `make backend-format` | 🧺 Formater le code backend (isort + black) |
| `make backend-lint` | 🧹 Linter le code backend (isort --check + black --check + flake8 + mypy + bandit) |
| `make backend-typecheck` | 🔍 Vérification des types mypy |
| `make backend-test-unit` | 🧪 Tests unitaires backend uniquement |
| `make backend-test-integration` | 🧪 Tests d'intégration backend uniquement |
| `make backend-test-all` | 🧪 Tous les tests backend (unit + integration) |
| `make backend-test-coverage` | ☂️ Tests backend avec rapport de couverture (ouvre navigateur) |
| `make backend-coverage` | ☂️ Générer et visualiser le rapport de couverture |
| `make backend-build` | 🏗 Build du package backend (Poetry build) |
| `make backend-all` | 🧪 Tous les checks backend (format + lint + typecheck + test) |

### Frontend

| Cible | Description |
|-------|-------------|
| `make frontend` | 🎬 Démarrer le serveur de développement frontend (pnpm dev --open) |
| `make frontend-install` | 📦 Installer les dépendances frontend (pnpm install) |
| `make frontend-build` | 🏗 Build frontend pour la production |
| `make frontend-build-prod` | 🏗 Build frontend et copie vers app directory |
| `make frontend-dev` | 🎬 Démarrer le serveur de développement frontend |
| `make frontend-preview` | 🔍 Preview du build de production |
| `make frontend-format` | 🧺 Formater le code frontend (Prettier) |
| `make frontend-lint` | 🧹 Linter le code frontend (ESLint) |
| `make frontend-lint-check` | 🧹 Vérification lint sans correction |
| `make frontend-lint-fix` | 🧹 Corriger les problèmes de lint |
| `make frontend-css-check` | 🧹 Vérification CSS (Stylelint) |
| `make frontend-css-fix` | 🧹 Corriger les problèmes CSS |
| `make frontend-test` | 🧪 Tests frontend (CI mode) |
| `make frontend-test-unit` | 🧪 Tests unitaires frontend uniquement |
| `make frontend-test-unit-watch` | 🧪 Tests unitaires frontend en mode watch |
| `make frontend-test-integration` | 🧪 Tests d'intégration frontend |
| `make frontend-test-coverage` | ☂️ Tests frontend avec couverture |
| `make frontend-test-e2e` | 🧪 Tests end-to-end (Playwright) |
| `make frontend-test-e2e-dev` | 🧪 Tests E2E avec dev server |
| `make frontend-test-e2e-ui` | 🧪 Tests E2E avec UI Playwright |
| `make frontend-test-all` | 🧪 Tous les tests frontend (unit + integration + e2e) |
| `make frontend-typecheck` | 🔍 Vérification des types TypeScript |
| `make frontend-sizecheck` | 📊 Analyse de la taille du bundle |
| `make frontend-all` | 🧪 Tous les checks frontend (format + lint + css + typecheck + test) |

### CLI

| Cible | Description |
|-------|-------------|
| `make cli` | 🖥️ Démarrer l'interface CLI WindFlow |
| `make cli-install` | 📦 Installer le CLI globalement |
| `make cli-format` | 🧺 Formater le code CLI (black + isort) |
| `make cli-lint` | 🧹 Linter le code CLI (flake8 + mypy) |
| `make cli-test` | 🧪 Tests CLI |
| `make cli-build` | 🏗 Build de l'exécutable CLI (PyInstaller) |
| `make cli-all` | 🧪 Tous les checks CLI (format + lint + test) |

### Docker

| Cible | Description |
|-------|-------------|
| `make docker-build` | 🐳 Build de toutes les images Docker (api + frontend + worker) |
| `make docker-build-backend` | 🐳 Build de l'image Docker backend |
| `make docker-build-frontend` | 🐳 Build de l'image Docker frontend |
| `make docker-build-worker` | 🐳 Build de l'image Docker worker |
| `make docker-up` | 🐳 Démarrer les conteneurs Docker |
| `make docker-down` | 🐳 Arrêter les conteneurs Docker |
| `make docker-logs` | 🐳 Afficher les logs Docker |
| `make docker-dev` | 🐳 Démarrer l'environnement Docker de développement |
| `make docker-prod` | 🐳 Démarrer l'environnement Docker de production |

### Architecture modulaire — modes de démarrage

| Cible | Description |
|-------|-------------|
| `make minimal` | 📦 Démarrage minimal (core uniquement : <512MB, <2min) |
| `make dev-full` | 🔧 Démarrage développement (toutes extensions) |
| `make prod` | 🚀 Démarrage production |

### Extensions (activer/désactiver)

| Cible | Description |
|-------|-------------|
| `make enable-database` / `make disable-database` | 🗄️ PostgreSQL |
| `make enable-cache` / `make disable-cache` | 🔄 Redis |
| `make enable-monitoring` / `make disable-monitoring` | 📊 Prometheus + Grafana |
| `make enable-workers` / `make disable-workers` | ⚙️ Celery workers |
| `make enable-secrets` / `make disable-secrets` | 🔐 HashiCorp Vault |
| `make enable-sso` / `make disable-sso` | 🔑 Keycloak SSO |

### CI/CD (exécution locale)

| Cible | Description |
|-------|-------------|
| `make ci-full` | ✅ Pipeline CI complet (lint + test + sécurité backend + frontend) |
| `make ci-quick` | ⚡ CI rapide (lint uniquement) |
| `make ci-lint-backend` | 🔍 CI : Lint backend |
| `make ci-lint-frontend` | 🔍 CI : Lint frontend |
| `make ci-test-backend` | 🧪 CI : Tests backend avec couverture (`--cov-fail-under=80`) |
| `make ci-test-frontend` | 🧪 CI : Tests frontend |
| `make ci-security-backend` | 🔒 CI : Audit sécurité backend (bandit + safety) |
| `make ci-security-frontend` | 🔒 CI : Audit sécurité frontend (pnpm audit) |
| `make ci-build-docker` | 🐳 CI : Build des images Docker |

### Qualité — raccourcis globaux

| Cible | Description |
|-------|-------------|
| `make format` | 🧺 Formater tout le code (backend + frontend + CLI) |
| `make lint` | 🧹 Linter tout le code (backend + frontend + CLI) |
| `make test` | 🧪 Lancer tous les tests (backend + frontend + CLI) |
| `make typecheck` | 🔍 Vérification des types (backend + frontend) |

### Développement

| Cible | Description |
|-------|-------------|
| `make dev` | 🎬 Démarrer backend + frontend simultanément |
| `make run` | 🎬 Lancer le serveur en mode production |
| `make migrate` | 🗃️ Générer une migration Alembic |
| `make status` | 📊 Statut de tous les services WindFlow |
| `make logs` | 📋 Logs de tous les services |
| `make stop` | ⏹️ Arrêter tous les services WindFlow |
| `make help` | 📖 Afficher l'aide complète de toutes les cibles |

### Génération de code

| Cible | Description |
|-------|-------------|
| `make generate-api` | 🔄 Régénérer le client TypeScript API depuis les routes backend |
| `make generate-types` | 🔧 Générer les types TypeScript partagés |
| `make generate-docs` | 📚 Générer la documentation automatique |
| `make generate-openapi-docs` | 📋 Générer la spécification OpenAPI complète |

---

## Raccourcis usuels

```bash
make setup          # Premier setup
make dev            # Démarrer le développement (backend + frontend)
make test           # Lancer tous les tests
make lint           # Vérifier la qualité du code
make help           # Voir toutes les cibles disponibles
```
