# ============================================================================
# VARIABLES
# ============================================================================

# Core tools
PYTHON ?= python3
POETRY ?= poetry
PNPM ?= pnpm
DOCKER ?= docker
DOCKER_COMPOSE ?= docker compose

# Project paths
BACKEND_DIR = backend
FRONTEND_DIR = frontend
CLI_DIR = cli
INFRASTRUCTURE_DIR = infrastructure

# Git and versioning
GIT_BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
VERSION = $(shell git describe --long --first-parent 2>/dev/null || echo "0.1.0-dev")

# Docker images
DOCKER_REGISTRY ?= windflow
API_IMAGE = $(DOCKER_REGISTRY)/api:$(VERSION)
FRONTEND_IMAGE = $(DOCKER_REGISTRY)/frontend:$(VERSION)
WORKER_IMAGE = $(DOCKER_REGISTRY)/worker:$(VERSION)

# Environment
ENV ?= development
LOG_LEVEL ?= INFO

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

# ============================================================================
# COMMON COMMANDS
# ============================================================================

.PHONY: help
help: ## Afficher l'aide
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

.PHONY: setup
setup: ## Installation complète de l'environnement de développement
	@echo "🚀 Installation de l'environnement WindFlow"
	@make install
	@make dev-deps
	@make docker-build
	@echo "✅ Environnement WindFlow configuré avec succès"

.PHONY: install
install: ## Installation des dépendances
	@echo "📦 Installation des dépendances..."
	@if [ -f "pyproject.toml" ]; then $(POETRY) install --with dev; fi
	@if [ -f "$(FRONTEND_DIR)/package.json" ]; then cd $(FRONTEND_DIR) && $(PNPM) install; fi
	@echo "✅ Dépendances installées"

.PHONY: outdated
outdated: ## Vérifier les dépendances obsolètes
	@echo "🔍 Vérification des dépendances obsolètes..."
	@if [ -f "pyproject.toml" ]; then $(POETRY) show --outdated; fi
	@if [ -f "$(FRONTEND_DIR)/package.json" ]; then cd $(FRONTEND_DIR) && $(PNPM) outdated; fi

# ============================================================================
# CLEANING COMMANDS
# ============================================================================

.PHONY: clean
clean: clean-build clean-tests clean-data ## Nettoyage complet

.PHONY: clean-build
clean-build: ## Nettoyage des artefacts de build
	@echo "🧹 Nettoyage des artefacts de build..."
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@if [ -d "$(FRONTEND_DIR)" ]; then cd $(FRONTEND_DIR) && rm -rf dist/ node_modules/.cache; fi

.PHONY: clean-tests
clean-tests: ## Nettoyage des artefacts de tests
	@echo "🧹 Nettoyage des artefacts de tests..."
	@rm -rf .coverage
	@rm -rf htmlcov/
	@rm -rf .pytest_cache/
	@rm -rf test-results/

.PHONY: clean-data
clean-data: ## Nettoyage des données de développement
	@echo "🧹 Nettoyage des données..."
	@rm -rf logs/*.log
	@rm -rf dev/data/log/*.log

# ============================================================================
# BACKEND COMMANDS
# ============================================================================

.PHONY: backend
backend: ## Démarrer le backend en mode développement
	@echo "🚀 Démarrage du backend WindFlow..."
	@cd $(BACKEND_DIR) && $(POETRY) run uvicorn main:app --reload --host 0.0.0.0 --port 8000

.PHONY: backend-test
backend-test: ## Exécuter les tests backend
	@echo "🧪 Exécution des tests backend..."
	@$(POETRY) run pytest $(BACKEND_DIR)/tests/ -v --cov=$(BACKEND_DIR) --cov-report=html --cov-report=term

.PHONY: backend-lint
backend-lint: ## Linter le code backend
	@echo "🔍 Linting du backend..."
	@$(POETRY) run flake8 $(BACKEND_DIR)/
	@$(POETRY) run mypy $(BACKEND_DIR)/
	@$(POETRY) run bandit -r $(BACKEND_DIR)/

.PHONY: backend-format
backend-format: ## Formatter le code backend
	@echo "✨ Formatage du backend..."
	@$(POETRY) run black $(BACKEND_DIR)/
	@$(POETRY) run isort $(BACKEND_DIR)/

# ============================================================================
# FRONTEND COMMANDS
# ============================================================================

.PHONY: frontend
frontend: ## Démarrer le frontend en mode développement
	@echo "🚀 Démarrage du frontend WindFlow..."
	@cd $(FRONTEND_DIR) && $(PNPM) dev

.PHONY: frontend-test
frontend-test: ## Exécuter les tests frontend
	@echo "🧪 Exécution des tests frontend..."
	@cd $(FRONTEND_DIR) && $(PNPM) test

.PHONY: frontend-lint
frontend-lint: ## Linter le code frontend
	@echo "🔍 Linting du frontend..."
	@cd $(FRONTEND_DIR) && $(PNPM) lint

.PHONY: frontend-build
frontend-build: ## Builder le frontend pour production
	@echo "🏗️ Build du frontend..."
	@cd $(FRONTEND_DIR) && $(PNPM) build

# ============================================================================
# CLI COMMANDS
# ============================================================================

.PHONY: cli
cli: ## Démarrer l'interface CLI
	@echo "🖥️ Interface CLI WindFlow..."
	@$(POETRY) run python -m $(CLI_DIR).main

.PHONY: cli-test
cli-test: ## Exécuter les tests CLI
	@echo "🧪 Exécution des tests CLI..."
	@$(POETRY) run pytest $(CLI_DIR)/tests/ -v

.PHONY: cli-build
cli-build: ## Builder l'exécutable CLI
	@echo "🏗️ Build de l'exécutable CLI..."
	@$(POETRY) run pyinstaller --onefile $(CLI_DIR)/main.py -n windflow

.PHONY: cli-install
cli-install: ## Installer le CLI globalement
	@echo "📦 Installation du CLI WindFlow..."
	@$(POETRY) build
	@pip install dist/windflow-*.whl

# ============================================================================
# DEVELOPMENT COMMANDS
# ============================================================================

.PHONY: dev
dev: ## Démarrer l'environnement de développement complet
	@echo "🚀 Démarrage de l'environnement de développement..."
	@$(DOCKER_COMPOSE) -f docker-compose-dev.yml up -d postgres redis vault
	@sleep 5
	@make migrate
	@$(DOCKER_COMPOSE) -f docker-compose-dev.yml up windflow-api windflow-frontend

.PHONY: dev-deps
dev-deps: ## Installer les outils de développement
	@echo "🛠️ Installation des outils de développement..."
	@$(POETRY) install --with dev
	@$(POETRY) run pre-commit install
	@if [ -d "$(FRONTEND_DIR)" ]; then cd $(FRONTEND_DIR) && $(PNPM) install; fi

.PHONY: serve
serve: ## Démarrer tous les services via Docker Compose (développement)
	@echo "🚀 Démarrage de tous les services (développement)..."
	@$(DOCKER_COMPOSE) up -d

.PHONY: migrate
migrate: ## Exécuter les migrations de base de données
	@echo "🗄️ Exécution des migrations..."
	@$(POETRY) run alembic upgrade head

.PHONY: format
format: backend-format ## Formatter tout le code
	@echo "✨ Formatage complet terminé"

.PHONY: lint
lint: backend-lint frontend-lint ## Linter tout le code
	@echo "🔍 Linting complet terminé"

.PHONY: test
test: backend-test frontend-test cli-test ## Exécuter tous les tests
	@echo "🧪 Tests complets terminés"

# ============================================================================
# DOCKER COMMANDS
# ============================================================================

.PHONY: docker-build
docker-build: ## Builder les images Docker de développement
	@echo "🐳 Build des images Docker (développement)..."
	@$(DOCKER_COMPOSE) -f docker-compose-dev.yml build

.PHONY: docker-build-prod
docker-build-prod: ## Builder les images Docker de production
	@echo "🐳 Build des images Docker (production)..."
	@$(DOCKER_COMPOSE) -f docker-compose.prod.yml build

.PHONY: docker-up
docker-up: ## Démarrer les services Docker de développement
	@echo "🐳 Démarrage des services Docker (développement)..."
	@$(DOCKER_COMPOSE) up -d

.PHONY: docker-dev
docker-dev: ## Démarrer l'environnement Docker de développement
	@echo "🐳 Environnement Docker de développement..."
	@$(DOCKER_COMPOSE) -f docker-compose-dev.yml up -d

.PHONY: docker-prod
docker-prod: ## Démarrer l'environnement Docker de production
	@echo "🐳 Environnement Docker de production..."
	@$(DOCKER_COMPOSE) -f docker-compose.prod.yml up -d

.PHONY: docker-stop
docker-stop: ## Arrêter les services Docker de développement
	@echo "🛑 Arrêt des services Docker (développement)..."
	@$(DOCKER_COMPOSE) down

.PHONY: docker-stop-prod
docker-stop-prod: ## Arrêter les services Docker de production
	@echo "🛑 Arrêt des services Docker (production)..."
	@$(DOCKER_COMPOSE) -f docker-compose.prod.yml down

.PHONY: docker-logs
docker-logs: ## Afficher les logs Docker de développement
	@echo "📋 Logs des services Docker (développement)..."
	@$(DOCKER_COMPOSE) logs -f

.PHONY: docker-logs-prod
docker-logs-prod: ## Afficher les logs Docker de production
	@echo "📋 Logs des services Docker (production)..."
	@$(DOCKER_COMPOSE) -f docker-compose.prod.yml logs -f

# ============================================================================
# DEPLOYMENT COMMANDS
# ============================================================================

.PHONY: dist
dist: clean ## Créer les packages de distribution
	@echo "📦 Création des packages de distribution..."
	@$(POETRY) build
	@make frontend-build

.PHONY: release
release: ## Créer une release
	@echo "🚀 Création d'une release v$(VERSION)..."
	@git tag v$(VERSION)
	@git push origin v$(VERSION)
	@make dist

.PHONY: stage
stage: ## Déployer en staging
	@echo "🚀 Déploiement en staging..."
	@$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.staging.yml up -d

# ============================================================================
# CODE GENERATION COMMANDS
# ============================================================================

.PHONY: generate-api
generate-api: ## Générer le client API frontend depuis OpenAPI
	@echo "🔧 Génération du client API..."
	@$(PYTHON) dev/scripts/generate_openapi_junie.py

.PHONY: generate-types
generate-types: ## Générer les types TypeScript partagés
	@echo "🔧 Génération des types TypeScript..."
	@$(POETRY) run python dev/scripts/generate_types.py

.PHONY: generate-docs
generate-docs: ## Générer la documentation automatique
	@echo "📚 Génération de la documentation..."
	@$(POETRY) run sphinx-build -b html docs/ docs/_build/html/

# ============================================================================
# ALL-IN-ONE COMMANDS
# ============================================================================

.PHONY: all
all: clean install test lint dist ## Pipeline complète de développement

.PHONY: ci
ci: install lint test ## Pipeline d'intégration continue
	@echo "✅ Pipeline CI terminée avec succès"

.PHONY: prepare
prepare: setup dev-deps ## Préparer l'environnement pour un nouveau développeur
	@echo "🎉 Environnement prêt pour le développement WindFlow!"
	@echo ""
	@echo "📍 Commandes utiles:"
	@echo "   make dev     - Démarrer l'environnement de développement"
	@echo "   make test    - Exécuter tous les tests"
	@echo "   make lint    - Vérifier le code"
	@echo "   make help    - Afficher l'aide complète"

# ============================================================================
# DEFAULT TARGET
# ============================================================================

.DEFAULT_GOAL := help
