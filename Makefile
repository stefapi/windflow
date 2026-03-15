# ============================================================================
# VARIABLES
# ============================================================================

# Core tools
PYTHON ?= python3
POETRY ?= poetry
PNPM ?= pnpm
NODE ?= node
DOCKER ?= docker
DOCKER_COMPOSE ?= docker compose
ALEMBIC ?= alembic

# Project paths
BACKEND_DIR = backend
FRONTEND_DIR = frontend
CLI_DIR = cli
INFRASTRUCTURE_DIR = infrastructure

# Python paths
PYTHON_VERSION = $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_version; print(get_python_version())")
SITELIB = $(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
VENV_BASE ?= ./venv

# Git and versioning
GIT_BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
VERSION = $(shell git describe --long --first-parent 2>/dev/null || echo "0.1.0-dev")
RELEASE_VERSION = $(shell git describe --long --first-parent 2>/dev/null | sed 's@\([0-9.]\{1,\}\).*@\1@' || echo "0.1.0")

# Docker settings
DOCKER_REGISTRY ?= windflow
API_IMAGE = $(DOCKER_REGISTRY)/api:$(VERSION)
FRONTEND_IMAGE = $(DOCKER_REGISTRY)/frontend:$(VERSION)
WORKER_IMAGE = $(DOCKER_REGISTRY)/worker:$(VERSION)
COMPOSE_TAG ?= $(GIT_BRANCH)
COMPOSE_HOST ?= $(shell hostname)

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

define APP_PYSCRIPT
from $(BACKEND_DIR) import main
app = main.app
app.run()
endef
export APP_PYSCRIPT

BROWSER := $(PYTHON) -c "$$BROWSER_PYSCRIPT"

.ONESHELL:

# ============================================================================
# COMMON COMMANDS
# ============================================================================

help: ## 📖 Display help information about available commands
	@$(PYTHON) -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

outdated: ## 🚧 Check for outdated dependencies in both backend and frontend
	@echo "Checking backend dependencies..."
	$(POETRY) show --outdated
	@echo "\nChecking frontend dependencies..."
	cd $(FRONTEND_DIR) && $(PNPM) exec taze

setup: ## 🏗 Setup complete development environment
	$(POETRY) install --with dev
	cd $(FRONTEND_DIR) && $(PNPM) install
	cp -n .env.example .env || true
	@echo "🏗  Development Setup Complete "
	@echo "❗️ Tips"
	@echo "    1. run 'make backend' to start the API server"
	@echo "    2. run 'make frontend' to start the frontend development server"
	@echo "    3. run 'make dev' to start both servers"

install: ## 📦 Install development version
	$(POETRY) install

# ============================================================================
# CLEANING COMMANDS
# ============================================================================

clean-data: ## ⚠️ Remove all developer data for a fresh start
	rm -rf ./dev/data/users/ 2>/dev/null || true
	rm -f ./dev/data/*.db 2>/dev/null || true
	rm -f ./dev/data/*.log 2>/dev/null || true
	rm -f ./dev/data/.secret 2>/dev/null || true

clean-build: ## 🧹 Clean Python build files
	rm -rf build dist .eggs
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-docs: ## 🧹 Clean documentation build
	rm -rf docs/_build

clean-tests: ## 🧹 Remove test and coverage artifacts
	rm -f .coverage
	rm -rf .tox
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf test-results

clean-pyc: ## 🧹 Remove Python file artifacts
	find ./$(BACKEND_DIR) -type f -name '*.pyc' -delete
	find ./$(BACKEND_DIR) -type f -name '*.log' -delete
	find ./$(BACKEND_DIR) -type f -name '*~' -delete
	find ./$(BACKEND_DIR) -name '__pycache__' -exec rm -fr {} +

clean-frontend: ## 🧹 Remove frontend build artifacts
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(FRONTEND_DIR)/node_modules/.vite

clean: clean-data clean-pyc clean-tests clean-frontend ## 🧹 Clean all build artifacts and temporary files

# ============================================================================
# BACKEND COMMANDS
# ============================================================================

backend-clean: clean-pyc clean-tests clean-frontend ## 🧹 Clean backend-specific artifacts
	rm -fr .mypy_cache

backend-typecheck: ## 🔍 Type check the backend code
	$(POETRY) run mypy $(BACKEND_DIR)

backend-build: ## 🏗 Build backend package
	$(POETRY) build

backend-test-unit: ## 🧪 Run backend unit tests only
	$(POETRY) run pytest $(BACKEND_DIR)/tests/unit/ -v --cov=$(BACKEND_DIR) --cov-report=html --cov-report=term

backend-test-integration: ## 🧪 Run backend integration tests only
	$(POETRY) run pytest $(BACKEND_DIR)/tests/integration/ -v --cov=$(BACKEND_DIR) --cov-report=html --cov-report=term

backend-test-coverage: ## ☂️ Run backend tests with coverage report
	$(POETRY) run pytest $(BACKEND_DIR)/tests/ --cov=$(BACKEND_DIR) --cov-report=html --cov-report=term
	$(BROWSER) htmlcov/index.html

backend-test-all: backend-test-unit backend-test-integration ## 🧪 Run all backend tests (unit + integration)

backend-format: ## 🧺 Format backend code
	$(POETRY) run isort $(BACKEND_DIR)
	$(POETRY) run black $(BACKEND_DIR)

backend-lint: ## 🧹 Lint backend code
	$(POETRY) run isort --check-only $(BACKEND_DIR)
	$(POETRY) run black --check $(BACKEND_DIR)
	$(POETRY) run flake8 $(BACKEND_DIR)
	$(POETRY) run mypy $(BACKEND_DIR)
	$(POETRY) run bandit -r $(BACKEND_DIR)

backend-all: backend-format backend-lint backend-typecheck backend-test ## 🧪 Run all backend checks and tests

backend-coverage: ## ☂️ Generate and view test coverage report
	$(POETRY) run pytest $(BACKEND_DIR)/tests/
	$(POETRY) run coverage report -m
	$(POETRY) run coverage html
	$(BROWSER) htmlcov/index.html

.PHONY: backend
backend: ## 🎬 Start backend development server
	$(POETRY) run uvicorn $(BACKEND_DIR).main:app --reload --host 0.0.0.0 --port 8000

# ============================================================================
# FRONTEND COMMANDS
# ============================================================================

frontend-clean: ## 🧹 Clean frontend build artifacts
	rm -rf $(FRONTEND_DIR)/dist
	rm -rf $(FRONTEND_DIR)/node_modules/.vite

frontend-install: ## 📦 Install frontend dependencies
	cd $(FRONTEND_DIR) && $(PNPM) install

frontend-build: ## 🏗 Build frontend for production
	cd $(FRONTEND_DIR) && $(PNPM) build

frontend-build-prod: ## 🏗 Build frontend and copy to app directory
	cd $(FRONTEND_DIR) && $(PNPM) build-prod

frontend-dev: ## 🎬 Start frontend development server
	cd $(FRONTEND_DIR) && $(PNPM) dev

frontend-start: ## 🎬 Start frontend server from output directory
	cd $(FRONTEND_DIR) && $(PNPM) start

frontend-preview: ## 🔍 Preview production build locally
	cd $(FRONTEND_DIR) && $(PNPM) preview

frontend-preview-local: ## 🔍 Preview local build with serve
	cd $(FRONTEND_DIR) && $(PNPM) preview:local

frontend-preview-dist: ## 🔍 Preview app directory build with serve
	cd $(FRONTEND_DIR) && $(PNPM) preview:dist

frontend-lint: ## 🧹 Lint frontend code
	cd $(FRONTEND_DIR) && $(PNPM) lint

frontend-lint-check: ## 🧹 Check frontend code for linting issues
	cd $(FRONTEND_DIR) && $(PNPM) lint-check

frontend-lint-fix: ## 🧹 Fix frontend linting issues
	cd $(FRONTEND_DIR) && $(PNPM) lint-fix

frontend-css-check: ## 🧹 Check frontend CSS for style issues
	cd $(FRONTEND_DIR) && $(PNPM) css-check

frontend-css-fix: ## 🧹 Fix frontend CSS style issues
	cd $(FRONTEND_DIR) && $(PNPM) css-fix

frontend-format: ## 🧺 Format frontend code
	cd $(FRONTEND_DIR) && $(PNPM) format

frontend-test: ## 🧪 Run frontend unit tests
	cd $(FRONTEND_DIR) && $(PNPM) test:ci

frontend-test-unit: ## 🧪 Run frontend unit tests only
	cd $(FRONTEND_DIR) && $(PNPM) test:unit

frontend-test-unit-watch: ## 🧪 Run frontend unit tests in watch mode
	cd $(FRONTEND_DIR) && $(PNPM) test:unit:watch

frontend-test-integration: ## 🧪 Run frontend integration tests
	cd $(FRONTEND_DIR) && $(PNPM) test:integration

frontend-test-coverage: ## ☂️ Run frontend tests with coverage report
	cd $(FRONTEND_DIR) && $(PNPM) test:coverage

frontend-test-e2e: ## 🧪 Run frontend end-to-end tests
	cd $(FRONTEND_DIR) && $(PNPM) test:e2e

frontend-test-e2e-dev: ## 🧪 Run frontend end-to-end tests with dev server
	cd $(FRONTEND_DIR) && $(PNPM) test:e2e:dev

frontend-test-e2e-ui: ## 🧪 Run frontend end-to-end tests with UI
	cd $(FRONTEND_DIR) && $(PNPM) test:e2eui:dev

frontend-test-record: ## 🎥 Record frontend end-to-end tests
	cd $(FRONTEND_DIR) && $(PNPM) test:record:dev

frontend-test-all: ## 🧪 Run all frontend tests (unit, integration, e2e)
	cd $(FRONTEND_DIR) && $(PNPM) test:all

frontend-typecheck: ## 🔍 Type check frontend code
	cd $(FRONTEND_DIR) && $(PNPM) typecheck

frontend-sizecheck: ## 📊 Analyze frontend bundle size
	cd $(FRONTEND_DIR) && $(PNPM) sizecheck

frontend-unlighthouse: ## 🔍 Run Unlighthouse for performance testing
	cd $(FRONTEND_DIR) && $(PNPM) unlighthouse

frontend-generate: ## 🏗 Generate code for frontend
	$(POETRY) run python dev/scripts/generate_types.py

frontend-all: frontend-format frontend-lint frontend-css-check frontend-typecheck frontend-test ## 🧪 Run all frontend checks and tests

.PHONY: frontend
frontend: ## 🎬 Start frontend development server
	cd $(FRONTEND_DIR) && $(PNPM) dev --open

# ============================================================================
# CLI COMMANDS
# ============================================================================

cli-clean: ## 🧹 Clean CLI build artifacts
	rm -rf $(CLI_DIR)/dist
	rm -rf $(CLI_DIR)/build

cli-test: ## 🧪 Run CLI tests
	$(POETRY) run pytest $(CLI_DIR)/tests/ -v

cli-lint: ## 🧹 Lint CLI code
	$(POETRY) run flake8 $(CLI_DIR)/
	$(POETRY) run mypy $(CLI_DIR)/

cli-format: ## 🧺 Format CLI code
	$(POETRY) run black $(CLI_DIR)/
	$(POETRY) run isort $(CLI_DIR)/

cli-build: ## 🏗 Build CLI executable
	$(POETRY) run pyinstaller --onefile $(CLI_DIR)/main.py -n windflow

cli-install: ## 📦 Install CLI globally
	$(POETRY) build
	pip install dist/windflow-*.whl --force-reinstall

cli-all: cli-format cli-lint cli-test ## 🧪 Run all CLI checks and tests

.PHONY: cli
cli: ## 🖥️ Start WindFlow CLI interface
	$(POETRY) run python -m $(CLI_DIR).main

# ============================================================================
# DEVELOPMENT COMMANDS
# ============================================================================

purge: clean ## 🧹 Remove everything for a fresh environment
	rm -rf ./dev/data 2>/dev/null || true
	$(POETRY) env remove --all

migrate: ## 🗃️ Generate database migration
	$(POETRY) run $(ALEMBIC) revision --autogenerate -m "migration_to_be_named"

format: backend-format frontend-format cli-format ## 🧺 Format all code (backend, frontend and CLI)

lint: backend-lint frontend-lint cli-lint ## 🧹 Lint all code (backend, frontend and CLI)

test: backend-test frontend-test cli-test ## 🧪 Run all tests (backend, frontend and CLI)

serve: ## 🎬 Serve client and server separately
	$(POETRY) run $(PYTHON) -c "$$APP_PYSCRIPT"

run: ## 🎬 Run server in production mode
	$(POETRY) run uvicorn $(BACKEND_DIR).main:app --host 0.0.0.0 --port 8000

.PHONY: dev
dev: ## 🎬 Start both backend and frontend development servers
	@echo "Starting backend and frontend servers..."
	@(trap 'kill 0' SIGINT; \
		$(MAKE) backend & \
		$(MAKE) frontend & \
		wait)

# ============================================================================
# DOCKER COMMANDS
# ============================================================================

docker-build-backend: ## 🐳 Build backend Docker image
	$(DOCKER) build -t $(API_IMAGE) -f $(INFRASTRUCTURE_DIR)/docker/Dockerfile.api .

docker-build-frontend: ## 🐳 Build frontend Docker image
	$(DOCKER) build -t $(FRONTEND_IMAGE) -f $(INFRASTRUCTURE_DIR)/docker/Dockerfile.frontend .

docker-build-worker: ## 🐳 Build worker Docker image
	$(DOCKER) build -t $(WORKER_IMAGE) -f $(INFRASTRUCTURE_DIR)/docker/Dockerfile.worker .

docker-build: docker-build-backend docker-build-frontend docker-build-worker ## 🐳 Build all Docker images

docker-up: ## 🐳 Start Docker containers
	$(DOCKER_COMPOSE) up -d

docker-down: ## 🐳 Stop Docker containers
	$(DOCKER_COMPOSE) down

docker-logs: ## 🐳 View Docker logs
	$(DOCKER_COMPOSE) logs -f

docker-dev: ## 🐳 Start Docker development stack
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose-dev.yml -p dev-windflow down && \
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose-dev.yml -p dev-windflow up --build

docker-prod: ## 🐳 Start Docker production stack
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml -p windflow up --build

# ============================================================================
# WINDFLOW MODULAR ARCHITECTURE COMMANDS
# ============================================================================

.PHONY: minimal dev-full prod

minimal: ## 📦 Start WindFlow in minimal mode (core only: <512MB, <2min)
	@echo "📦 Starting WindFlow in minimal mode..."
	@$(DOCKER) network create windflow-network 2>/dev/null || true
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml up -d
	@echo "✅ WindFlow minimal started successfully!"
	@echo ""
	@echo "🌐 Access:"
	@echo "   - Application:        http://localhost"
	@echo "   - API:                http://localhost/api"
	@echo "   - Traefik Dashboard:  http://localhost:8080"
	@echo ""
	@echo "📦 Extensions available:"
	@echo "   make enable-database    # PostgreSQL"
	@echo "   make enable-cache       # Redis"
	@echo "   make enable-monitoring  # Prometheus + Grafana"
	@echo "   make enable-workers     # Celery workers"
	@echo "   make enable-secrets     # HashiCorp Vault"
	@echo "   make enable-sso         # Keycloak SSO"

dev-full: ## 🔧 Start WindFlow in development mode (all extensions enabled)
	@echo "🔧 Starting WindFlow in development mode (all extensions)..."
	@$(DOCKER) network create windflow-network 2>/dev/null || true
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile database \
		--profile cache \
		--profile monitoring up -d
	@echo "✅ WindFlow development environment started!"
	@echo ""
	@echo "🌐 Services available:"
	@echo "   - Application:        http://localhost"
	@echo "   - API:                http://localhost/api"
	@echo "   - Traefik Dashboard:  http://localhost:8080"
	@echo "   - Prometheus:         http://prometheus.localhost"
	@echo "   - Grafana:            http://grafana.localhost (admin/admin123)"
	@echo "   - PostgreSQL:         localhost:5432 (windflow/windflow123)"
	@echo "   - Redis:              localhost:6379"

prod: ## 🚀 Start WindFlow in production mode
	@echo "🚀 Starting WindFlow in production mode..."
	@$(DOCKER_COMPOSE) -f docker-compose.prod.yml up -d
	@echo "✅ WindFlow production environment started!"

# Extension management commands
enable-database: ## 🗄️ Enable PostgreSQL database extension
	@echo "📦 Enabling PostgreSQL database..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile database up -d
	@echo "✅ PostgreSQL enabled: localhost:5432 (windflow/windflow123)"

enable-cache: ## 🔄 Enable Redis cache extension
	@echo "📦 Enabling Redis cache..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile cache up -d
	@echo "✅ Redis enabled: localhost:6379"

enable-secrets: ## 🔐 Enable HashiCorp Vault secrets extension
	@echo "📦 Enabling HashiCorp Vault..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile secrets up -d
	@echo "✅ Vault enabled: http://vault.localhost"

enable-sso: ## 🔑 Enable Keycloak SSO extension
	@echo "📦 Enabling Keycloak SSO..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile sso up -d
	@echo "✅ Keycloak enabled: http://keycloak.localhost (admin/admin123)"

enable-monitoring: ## 📊 Enable Prometheus + Grafana monitoring extension
	@echo "📦 Enabling monitoring stack..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile monitoring up -d
	@echo "✅ Monitoring enabled:"
	@echo "   - Prometheus: http://prometheus.localhost"
	@echo "   - Grafana:    http://grafana.localhost (admin/admin123)"

enable-workers: ## ⚙️ Enable Celery workers extension (requires Redis)
	@echo "📦 Enabling Celery workers..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml \
		--profile cache \
		--profile workers up -d
	@echo "✅ Workers enabled:"
	@echo "   - Flower: http://flower.localhost (admin/flower123)"

# Extension disable commands
disable-database: ## 🗑️ Disable PostgreSQL database extension
	@echo "🗑️  Disabling PostgreSQL..."
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml --profile database down
	@echo "✅ PostgreSQL disabled"

disable-cache: ## 🗑️ Disable Redis cache extension
	@echo "🗑️  Disabling Redis..."
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml --profile cache down
	@echo "✅ Redis disabled"

disable-secrets: ## 🗑️ Disable HashiCorp Vault extension
	@echo "🗑️  Disabling Vault..."
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml --profile secrets down
	@echo "✅ Vault disabled"

disable-sso: ## 🗑️ Disable Keycloak SSO extension
	@echo "🗑️  Disabling Keycloak..."
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml --profile sso down
	@echo "✅ Keycloak disabled"

disable-monitoring: ## 🗑️ Disable monitoring extension
	@echo "🗑️  Disabling monitoring..."
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml --profile monitoring down
	@echo "✅ Monitoring disabled"

disable-workers: ## 🗑️ Disable workers extension
	@echo "🗑️  Disabling workers..."
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml --profile workers down
	@echo "✅ Workers disabled"

# Utility commands
status: ## 📊 Show status of all WindFlow services
	@echo "📊 WindFlow Services Status:"
	@echo "=================================================="
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml ps

logs: ## 📋 View logs from all services
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml \
		-f docker-compose.extensions.yml logs -f

stop: ## ⏹️ Stop all WindFlow services
	@echo "⏹️  Stopping WindFlow services..."
	@$(DOCKER_COMPOSE) -f docker-compose.minimal.yml down
	@$(DOCKER_COMPOSE) -f docker-compose.extensions.yml down
	@echo "✅ WindFlow stopped"

restart: stop minimal ## 🔄 Restart WindFlow (minimal mode)

# Shortcuts
enable-db: enable-database ## 🗄️ Shortcut for enable-database
enable-mon: enable-monitoring ## 📊 Shortcut for enable-monitoring
enable-work: enable-workers ## ⚙️ Shortcut for enable-workers

# ============================================================================
# DEPLOYMENT COMMANDS
# ============================================================================

prepare: ## 🏗 Prepare for deployment
	$(POETRY) export --output requirements.txt

.PHONY: dist
dist: clean prepare backend-build frontend-build ## 📦 Create distribution files

release: clean dist ## 🚀 Build and publish to PyPI
	$(POETRY) publish

release-install: ## 📥 Install production version from PyPI
	pip install windflow --break-system-packages

stage: clean dist ## 🧪 Build and publish to TestPyPI
	$(POETRY) config repositories.testpypi https://test.pypi.org/legacy/
	$(POETRY) publish -r testpypi

stage-install: ## 📥 Install testing version from TestPyPI
	pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ windflow --break-system-packages

# ============================================================================
# CODE GENERATION COMMANDS
# ============================================================================

code-gen: ## 🤖 Generate API routes
	$(POETRY) run dev/scripts/daemon_routes_gen.py

generate-api: ## 🔄 Regenerate TypeScript API client from backend routes
	$(POETRY) run python dev/scripts/daemon_routes_gen.py && \
	cd $(FRONTEND_DIR) && $(PNPM) format:api

generate-types: ## 🔧 Generate shared TypeScript types
	$(POETRY) run python dev/scripts/generate_types.py

generate-docs: ## 📚 Generate automatic documentation
	$(POETRY) run sphinx-build -b html docs/ docs/_build/html/

generate-openapi-docs: ## 📋 Generate comprehensive OpenAPI specification in .junie directory
	$(POETRY) run python dev/scripts/generate_openapi_junie.py

# ============================================================================
# CI/CD COMMANDS (Local execution)
# ============================================================================

ci-lint-backend: ## 🔍 CI: Lint backend (local execution)
	@echo "🔍 Running backend linting..."
	$(POETRY) run black --check $(BACKEND_DIR)/
	$(POETRY) run isort --check-only $(BACKEND_DIR)/
	$(POETRY) run flake8 $(BACKEND_DIR)/
	$(POETRY) run pylint $(BACKEND_DIR)/ --fail-under=8.0 || true
	@echo "✅ Backend linting complete"

ci-lint-frontend: ## 🔍 CI: Lint frontend (local execution)
	@echo "🔍 Running frontend linting..."
	cd $(FRONTEND_DIR) && $(PNPM) lint-check
	cd $(FRONTEND_DIR) && $(PNPM) css-check
	cd $(FRONTEND_DIR) && $(PNPM) typecheck
	@echo "✅ Frontend linting complete"

ci-test-backend: ## 🧪 CI: Test backend with coverage (local execution)
	@echo "🧪 Running backend tests..."
	$(POETRY) run pytest $(BACKEND_DIR)/tests/ \
		--cov=$(BACKEND_DIR) \
		--cov-report=xml \
		--cov-report=html \
		--cov-report=term \
		--cov-fail-under=80 \
		-v
	@echo "✅ Backend tests complete"

ci-test-frontend: ## 🧪 CI: Test frontend (local execution)
	@echo "🧪 Running frontend tests..."
	cd $(FRONTEND_DIR) && $(PNPM) test:ci
	@echo "✅ Frontend tests complete"

ci-security-backend: ## 🔒 CI: Security audit backend (local execution)
	@echo "🔒 Running backend security audit..."
	$(POETRY) run bandit -r $(BACKEND_DIR)/ -f json -o bandit-report.json || true
	$(POETRY) run safety check --json || true
	@echo "✅ Backend security audit complete"

ci-security-frontend: ## 🔒 CI: Security audit frontend (local execution)
	@echo "🔒 Running frontend security audit..."
	cd $(FRONTEND_DIR) && $(PNPM) audit --audit-level=moderate || true
	@echo "✅ Frontend security audit complete"

ci-build-docker: ## 🐳 CI: Build Docker images (local execution)
	@echo "🐳 Building Docker images..."
	$(DOCKER) build -t windflow/api:local -f $(INFRASTRUCTURE_DIR)/docker/Dockerfile.api .
	$(DOCKER) build -t windflow/worker:local -f $(INFRASTRUCTURE_DIR)/docker/Dockerfile.worker .
	$(DOCKER) build -t windflow/frontend:local -f $(INFRASTRUCTURE_DIR)/docker/Dockerfile.frontend ./$(FRONTEND_DIR)
	@echo "✅ Docker images built"

ci-full: ci-lint-backend ci-lint-frontend ci-test-backend ci-test-frontend ci-security-backend ci-security-frontend ## ✅ CI: Run full CI pipeline locally

ci-quick: ci-lint-backend ci-lint-frontend ## ⚡ CI: Quick checks (lint only)

# ============================================================================
# ALL-IN-ONE COMMANDS
# ============================================================================

.PHONY: docs
docs: ## 📄 Generate and serve documentation
	cd docs && $(POETRY) run $(PYTHON) -m mkdocs serve

all: clean setup format lint test dev ## 🚀 Complete setup, format, lint, test, and run

ci: install lint test ## ✅ Continuous integration pipeline (legacy)

dev-prepare: setup ## 🎉 Prepare environment for new developer
	@echo "🎉 Environment ready for WindFlow development!"
	@echo ""
	@echo "📍 Useful commands:"
	@echo "   make dev     - Start development environment"
	@echo "   make test    - Run all tests"
	@echo "   make lint    - Check code quality"
	@echo "   make help    - Display complete help"

# ============================================================================
# DEFAULT TARGET
# ============================================================================

.DEFAULT_GOAL := help
