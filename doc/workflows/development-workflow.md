# Workflow de Développement - WindFlow

## Vue d'Ensemble

Ce document décrit le processus de développement quotidien pour les contributeurs WindFlow, basé sur les meilleures pratiques observées et les spécificités du projet.

## Setup Initial

### Prérequis Système
- **Python** 3.11+
- **Node.js** 20+ avec pnpm 9+
- **Docker** & Docker Compose
- **Git** avec configuration SSH
- **Poetry** pour la gestion des dépendances Python

### Installation Rapide
```bash
# 1. Clone du projet
git clone git@github.com:windflow/windflow.git
cd windflow

# 2. Installation automatique
./install.sh

# 3. Configuration environnement
cp .env.example .env
# Éditer .env avec vos paramètres locaux

# 4. Démarrage services de développement
make setup
make dev
```

### Configuration IDE

#### PyCharm (Backend)
1. **Ouvrir le projet** : File → Open → windflow/
2. **Interpéteur Python** : Settings → Project → Python Interpreter → Poetry Environment
3. **Plugins requis** :
   - Python Type Checker (mypy)
   - Pre-commit Hook Plugin
4. **Configuration** :
   - Code Style → Python → Set from predefined style → Black
   - Tools → pytest → Use pytest as default test runner

#### VS Code (Frontend)
1. **Extensions requises** :
   ```json
   {
     "recommendations": [
       "Vue.volar",
       "Vue.vscode-typescript-vue-plugin",
       "bradlc.vscode-tailwindcss",
       "esbenp.prettier-vscode",
       "ms-playwright.playwright"
     ]
   }
   ```
2. **Settings** :
   ```json
   {
     "editor.formatOnSave": true,
     "editor.defaultFormatter": "esbenp.prettier-vscode",
     "vue.server.petiteVue.supportHtmlFile": true
   }
   ```

## Feature Development

### 1. Analyse et Planification
```bash
# Synchronisation avec la branche principale
git checkout main
git pull origin main

# Création de la branche feature
git checkout -b feature/nom-fonctionnalite

# Mise à jour des dépendances si nécessaire
make outdated
```

### 2. Développement Backend
```bash
# Démarrage du backend en mode dev
make backend

# Tests en continu
make backend-test --watch

# Vérification qualité
make backend-lint
make backend-typecheck
make backend-format
```

**Cycle de développement backend :**
1. **Modèle** : Créer/modifier les modèles SQLAlchemy dans `windflow/models/`
2. **Schema** : Définir les schémas Pydantic dans `windflow/schemas/`
3. **Service** : Implémenter la logique métier dans `windflow/services/`
4. **Router** : Exposer l'API dans `windflow/api/`
5. **Tests** : Écrire les tests dans `tests/`

### 3. Développement Frontend
```bash
# Démarrage du frontend en mode dev
make frontend

# Tests en continu
cd frontend && pnpm test

# Vérification qualité
make frontend-lint
make frontend-typecheck
make frontend-format
```

**Cycle de développement frontend :**
1. **Types** : Définir les types TypeScript dans `src/types/`
2. **Service** : Créer les services API dans `src/services/`
3. **Store** : Gérer l'état avec Pinia dans `src/stores/`
4. **Composant** : Développer les composants Vue dans `src/components/`
5. **Page** : Assembler les pages dans `src/views/`
6. **Tests** : Écrire les tests dans `tests/`

### 4. Tests et Validation

#### Tests Unitaires
```bash
# Backend
make backend-test
make backend-coverage

# Frontend
make frontend-test
```

#### Tests d'Intégration
```bash
# Tests API complets
make test-integration

# Tests avec base de données
make test-db
```

#### Tests E2E
```bash
# Tests end-to-end avec Playwright
make frontend-test-e2e

# Mode interactif pour debug
make frontend-test-e2e-ui
```

## Git Workflow

### Stratégie de Branches
```
main                 ← Production stable
├── develop          ← Intégration continue
├── feature/xxx      ← Nouvelles fonctionnalités
├── bugfix/xxx       ← Corrections de bugs
├── hotfix/xxx       ← Corrections urgentes
└── release/v1.x.x   ← Préparation releases
```

### Cycle de Développement
1. **Feature Start**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/nom-fonctionnalite
   ```

2. **Development Loop**
   ```bash
   # Développement...
   git add .
   git commit -m "feat(scope): description"
   
   # Push régulier
   git push origin feature/nom-fonctionnalite
   ```

3. **Feature Complete**
   ```bash
   # Rebase pour historique propre
   git rebase develop
   
   # Tests finaux
   make test-all
   
   # Push final
   git push origin feature/nom-fonctionnalite
   ```

### Convention de Commits
```
type(scope): description

[optional body]

[optional footer]
```

**Types courants :**
- `feat`: Nouvelle fonctionnalité
- `fix`: Correction de bug
- `docs`: Documentation
- `style`: Formatage code
- `refactor`: Refactoring sans changement fonctionnel
- `test`: Ajout/modification de tests
- `chore`: Tâches de maintenance

**Exemples :**
```bash
feat(api): add deployment optimization endpoint
fix(ui): correct responsive layout on mobile
docs(readme): update installation instructions
refactor(service): simplify deployment logic
test(backend): add integration tests for auth
```

## Code Review Process

### Avant la PR
1. **Auto-validation**
   ```bash
   # Vérification complète
   make all
   
   # Formatage final
   make format
   
   # Tests complets
   make test
   ```

2. **Préparation**
   ```bash
   # Rebase sur develop
   git rebase develop
   
   # Squash si nécessaire
   git rebase -i HEAD~3
   ```

### Création de la PR
1. **Template PR**
   - Utiliser le template GitHub PR
   - Description claire des changements
   - Référencer les issues liées
   - Screenshots pour les changements UI
   - Checklist de validation complétée

2. **Assignation**
   - Auto-assignation de l'auteur
   - Demande de review à 2+ reviewers
   - Labels appropriés (feature, bug, docs, etc.)
   - Milestone si applicable

### Process de Review
1. **Automated Checks**
   - Tests CI/CD passent
   - Coverage maintenue (85%+)
   - Linting sans erreur
   - Type checking validé

2. **Human Review**
   - **Functionalité** : La feature fonctionne comme attendu
   - **Code Quality** : Respect des règles `.clinerules/`
   - **Tests** : Couverture et qualité des tests
   - **Documentation** : README, docstrings, changelog mis à jour
   - **Performance** : Pas de régression de performance
   - **Security** : Audit sécurité pour changements sensibles

3. **Feedback Loop**
   ```bash
   # Corrections après review
   git checkout feature/nom-fonctionnalite
   
   # Modifications...
   git add .
   git commit -m "fix(review): address reviewer comments"
   
   # Re-request review
   git push origin feature/nom-fonctionnalite
   ```

## Intégration Continue

### Pipeline CI/CD
**Déclencheurs :**
- Push sur toute branche
- Pull Request vers `develop`/`main`
- Schedule nightly pour `develop`

**Stages :**
1. **Validation Code**
   ```yaml
   - name: Backend Validation
     run: |
       make backend-lint
       make backend-typecheck
       make backend-test
       
   - name: Frontend Validation
     run: |
       make frontend-lint
       make frontend-typecheck
       make frontend-test
   ```

2. **Tests Intégration**
   ```yaml
   - name: Integration Tests
     run: |
       docker-compose up -d
       make test-integration
       make test-e2e
   ```

3. **Security & Quality**
   ```yaml
   - name: Security Scan
     run: |
       make security-scan
       make dependency-check
   ```

4. **Build & Deploy**
   ```yaml
   - name: Build Images
     run: |
       make docker-build
       
   - name: Deploy Staging
     if: branch == 'develop'
     run: |
       make deploy-staging
   ```

### Quality Gates
- **Coverage** : 85% minimum
- **Performance** : Pas de régression > 10%
- **Security** : Aucune vulnérabilité critique
- **Documentation** : README et API docs à jour

## Debugging et Troubleshooting

### Debugging Local
```bash
# Backend debugging
make backend-debug  # Lance avec debugger intégré

# Frontend debugging
make frontend-debug  # Lance avec Vue devtools

# Database debugging
make db-shell  # Console PostgreSQL

# Logs en temps réel
make logs  # Tous les services
make logs-backend  # Backend seulement
make logs-frontend  # Frontend seulement
```

### Troubleshooting Commun

#### 1. Problèmes de Dépendances
```bash
# Reset environnement
make clean
make setup

# Mise à jour forcée
poetry lock --no-update
cd frontend && pnpm install --force
```

#### 2. Problèmes de Base de Données
```bash
# Reset DB
make clean-data
make backend  # Auto-création des tables

# Migration manuelle
poetry run alembic upgrade head
```

#### 3. Problèmes Docker
```bash
# Reset containers
make docker-down
make docker-build
make docker-up

# Nettoyage complet
docker system prune -af
```

#### 4. Problèmes de Tests
```bash
# Tests isolés
make backend-test-unit
make frontend-test-unit

# Tests en mode verbose
make backend-test -- -v
make frontend-test -- --reporter=verbose
```

## Performance et Optimisation

### Monitoring Développement
```bash
# Profiling backend
make backend-profile

# Analyse bundle frontend
make frontend-analyze

# Métriques de performance
make performance-test
```

### Bonnes Pratiques
1. **Backend Performance**
   - Utiliser async/await systématiquement
   - Indexer les requêtes DB fréquentes
   - Mettre en cache les résultats coûteux
   - Limiter les requêtes N+1

2. **Frontend Performance**
   - Lazy loading des composants
   - Tree shaking des dépendances
   - Optimisation des images
   - Code splitting par route

3. **Database Performance**
   - Pagination pour les listes
   - Requêtes optimisées SQLAlchemy
   - Connection pooling
   - Éviter SELECT *

## Hot Reload et Live Development

### Configuration Hot Reload
```bash
# Backend - Auto-restart sur changement
make backend  # uvicorn --reload activé

# Frontend - HMR activé
make frontend  # Vite HMR

# Full stack avec proxy
make dev  # Backend + Frontend + Proxy
```

### Sync Multi-Device
```bash
# Exposition réseau local
make dev-network  # Accessible depuis mobile/autres devices

# HTTPS local
make dev-https  # Certificats locaux pour HTTPS
```

## Scripts et Outils Utiles

### Scripts de Développement
```bash
# Génération automatique
make generate-api-client  # Client TypeScript depuis OpenAPI
make generate-types  # Types partagés
make generate-docs  # Documentation

# Validation et format
make format-all  # Format backend + frontend
make lint-all    # Lint complet
make test-all    # Tests complets

# Base de données
make db-migrate  # Nouvelle migration
make db-seed     # Données de test
make db-backup   # Sauvegarde locale
```

### Aliases Utiles
```bash
# Ajouter à ~/.bashrc ou ~/.zshrc
alias wf-dev="cd ~/windflow && make dev"
alias wf-test="cd ~/windflow && make test-all"
alias wf-clean="cd ~/windflow && make clean && make setup"
alias wf-logs="cd ~/windflow && make logs"
```

## Ressources et Documentation

### Liens Internes
- [Règles de Développement](../../.clinerules/README.md)
- [Architecture](../general_specs/02-architecture.md)
- [Stack Technologique](../general_specs/03-technology-stack.md)
- [Testing Guidelines](testing-workflow.md)

### Outils Externes
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Vue.js 3 Guide](https://vuejs.org/guide/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Playwright Testing](https://playwright.dev/)

### Community
- [GitHub Discussions](https://github.com/windflow/windflow/discussions)
- [Stack Overflow Tag](https://stackoverflow.com/questions/tagged/windflow)
- [Discord Server](https://discord.gg/windflow)

---

**Note** : Ce workflow est un document vivant qui évolue avec le projet. Les suggestions d'amélioration sont les bienvenues via GitHub Issues ou Discussions.
