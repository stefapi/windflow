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
	$(POETRY) run pre-commit install
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

backend-test: ## 🧪 Run backend tests
	$(POETRY) run pytest $(BACKEND_DIR)/tests/ -v --cov=$(BACKEND_DIR) --cov-report=html --cov-report=term

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

frontend-test-e2e: ## 🧪 Run frontend end-to-end tests
	cd $(FRONTEND_DIR) && $(PNPM) test:e2e:dev

frontend-test-e2e-ui: ## 🧪 Run frontend end-to-end tests with UI
	cd $(FRONTEND_DIR) && $(PNPM) test:e2eui:dev

frontend-test-record: ## 🎥 Record frontend end-to-end tests
	cd $(FRONTEND_DIR) && $(PNPM) test:record:dev

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
# ALL-IN-ONE COMMANDS
# ============================================================================

.PHONY: docs
docs: ## 📄 Generate and serve documentation
	cd docs && $(POETRY) run $(PYTHON) -m mkdocs serve

all: clean setup format lint test dev ## 🚀 Complete setup, format, lint, test, and run

ci: install lint test ## ✅ Continuous integration pipeline

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
