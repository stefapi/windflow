# Guide CI/CD WindFlow - Gitea Actions

**Date de création :** 10/01/2025  
**Dernière mise à jour :** 10/01/2025

## Vue d'Ensemble

WindFlow utilise **Gitea Actions** pour l'intégration continue et le déploiement automatisé. Ce guide explique comment utiliser le pipeline CI/CD à la fois dans Gitea et en local via Makefile.

## Architecture CI/CD

### Pipeline Gitea Actions

Le pipeline est défini dans `.gitea/workflows/ci.yml` et s'exécute automatiquement sur :
- **Push** sur les branches `main` et `develop`
- **Pull Requests** vers les branches `main` et `develop`

### Jobs du Pipeline

```
┌─────────────────┐     ┌─────────────────┐
│  Lint Backend   │     │  Lint Frontend  │
│   (Python)      │     │  (TypeScript)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ├───────────┬───────────┤
         │           │           │
         ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │  Test   │ │  Test   │ │Security │
   │ Backend │ │Frontend │ │  Audit  │
   └────┬────┘ └────┬────┘ └─────────┘
        │           │
        └─────┬─────┘
              ▼
      ┌───────────────┐
      │  Build Docker │
      │    Images     │
      └───────┬───────┘
              │
              ▼
      ┌───────────────┐
      │    Deploy     │
      │  (Dev/Stage)  │
      └───────────────┘
```

## Configuration Gitea

### 1. Activer Gitea Actions

Dans votre instance Gitea, assurez-vous que les Actions sont activées :

```ini
# app.ini
[actions]
ENABLED = true
DEFAULT_ACTIONS_URL = https://github.com
```

### 2. Configurer un Runner

Installer et démarrer un Gitea Actions runner :

```bash
# Télécharger le runner
wget -O act_runner https://dl.gitea.com/act_runner/0.2.6/act_runner-0.2.6-linux-amd64
chmod +x act_runner

# Enregistrer le runner
./act_runner register --no-interactive \
  --instance https://votre-gitea.com \
  --token VOTRE_RUNNER_TOKEN \
  --name windflow-runner

# Démarrer le runner
./act_runner daemon
```

### 3. Secrets Gitea

Configurez les secrets dans les paramètres du repository :

| Secret | Description | Requis |
|--------|-------------|--------|
| `DOCKER_USERNAME` | Username Docker Hub | Optionnel |
| `DOCKER_PASSWORD` | Password Docker Hub | Optionnel |
| `DEPLOY_KEY` | Clé SSH déploiement | Optionnel |

## Utilisation du Pipeline

### Push sur Branches

Le pipeline s'exécute automatiquement :

```bash
# Sur develop (tests + build)
git checkout develop
git add .
git commit -m "feat: nouvelle fonctionnalité"
git push origin develop

# Sur main (tests + build + deploy staging)
git checkout main
git merge develop
git push origin main
```

### Pull Requests

Lors de la création d'une PR, le pipeline vérifie :
- ✅ Qualité du code (lint)
- ✅ Tests unitaires et d'intégration
- ✅ Sécurité (audits)
- ✅ Build Docker

## Exécution Locale avec Makefile

Pour exécuter les mêmes vérifications en local **avant de pusher** :

### Commandes Rapides

```bash
# Vérification rapide (lint uniquement)
make ci-quick

# Pipeline complet local
make ci-full
```

### Commandes Individuelles

#### Lint

```bash
# Lint backend (Black, isort, Flake8, Pylint)
make ci-lint-backend

# Lint frontend (ESLint, CSS, TypeScript)
make ci-lint-frontend
```

#### Tests

```bash
# Tests backend avec coverage
make ci-test-backend

# Tests frontend
make ci-test-frontend
```

#### Sécurité

```bash
# Audit sécurité backend (Bandit, Safety)
make ci-security-backend

# Audit sécurité frontend (npm audit)
make ci-security-frontend
```

#### Build Docker

```bash
# Build toutes les images Docker
make ci-build-docker
```

### Workflow de Développement Recommandé

```bash
# 1. Avant de commencer à coder
git checkout -b feature/ma-nouvelle-feature
make setup

# 2. Pendant le développement (itératif)
# ... modifications de code ...
make ci-quick  # Vérification rapide

# 3. Avant de commit
make ci-full   # Vérification complète

# 4. Commit et push
git add .
git commit -m "feat: ma nouvelle feature"
git push origin feature/ma-nouvelle-feature

# 5. Créer la Pull Request dans Gitea
# Le pipeline automatique s'exécute
```

## Détails des Jobs

### Job: Lint Backend

**Durée :** ~2 minutes  
**Services :** Aucun

Vérifie la qualité du code Python :

- **Black** : Formatage automatique du code
- **isort** : Organisation des imports
- **Flake8** : Analyse statique (PEP 8)
- **Pylint** : Qualité de code (score minimum 8.0/10)
- **Bandit** : Détection vulnérabilités sécurité

**Échec si :** Code mal formaté, erreurs Flake8, score Pylint < 8.0

### Job: Lint Frontend

**Durée :** ~1-2 minutes  
**Services :** Aucun

Vérifie la qualité du code TypeScript/Vue :

- **ESLint** : Linting JavaScript/TypeScript
- **Stylelint** : Linting CSS/SCSS
- **TypeScript** : Vérification des types

**Échec si :** Erreurs ESLint, erreurs CSS, erreurs TypeScript

### Job: Test Backend

**Durée :** ~3-5 minutes  
**Services :** PostgreSQL 15, Redis 7

Exécute les tests backend avec coverage :

- Tests unitaires (`pytest`)
- Coverage minimum 80% requis
- Génération rapports HTML et XML

**Artifacts :**
- `coverage.xml` - Rapport coverage
- `htmlcov/` - Rapport HTML interactif

**Échec si :** Tests échouent, coverage < 80%

### Job: Test Frontend

**Durée :** ~2-3 minutes  
**Services :** Aucun

Exécute les tests frontend :

- Tests unitaires Vitest
- Tests composants Vue
- Coverage automatique

**Artifacts :**
- `frontend/coverage/` - Rapports coverage

**Échec si :** Tests échouent

### Job: Build Docker

**Durée :** ~5-10 minutes  
**Services :** Aucun

Build des images Docker :

- `windflow/api` - Backend FastAPI
- `windflow/worker` - Celery workers
- `windflow/frontend` - Interface Vue.js

**Tags créés :**
- `:latest` - Dernière version
- `:<commit-sha>` - Version spécifique

**Échec si :** Build Docker échoue

### Job: Security Audit

**Durée :** ~2 minutes  
**Services :** Aucun

Audits de sécurité :

- **Safety** : Vulnérabilités dépendances Python
- **npm audit** : Vulnérabilités dépendances NPM

**Échec si :** Vulnérabilités critiques détectées (optionnel)

### Job: Deploy

**Durée :** Variable  
**Services :** Variables

Déploiement automatique :

- **develop** → Environnement de développement
- **main** → Environnement de staging

## Monitoring et Rapports

### Visualisation dans Gitea

1. Accédez à l'onglet **Actions** du repository
2. Sélectionnez un workflow run
3. Consultez les logs de chaque job
4. Téléchargez les artifacts (rapports coverage, sécurité)

### Rapports de Coverage

Les rapports de coverage sont générés à chaque exécution :

```bash
# Backend - Afficher le rapport local
make backend-coverage

# Frontend - Ouvrir dans navigateur
open frontend/coverage/index.html
```

### Notifications

Configurez les notifications Gitea pour être alerté :
- ✅ Pipeline réussi
- ❌ Pipeline échoué
- ⚠️ Avertissements sécurité

## Optimisation et Performance

### Cache des Dépendances

Le pipeline utilise le cache pour accélérer les builds :

- **Poetry** : Cache des packages Python
- **pnpm** : Cache des packages Node.js
- **Docker layers** : Cache des layers Docker

### Parallélisation

Les jobs s'exécutent en parallèle quand possible :
- Lint backend et frontend en parallèle
- Tests backend et frontend en parallèle

### Durées Moyennes

| Job | Durée Moyenne | Durée Maximum |
|-----|---------------|---------------|
| Lint Backend | 2 min | 3 min |
| Lint Frontend | 1 min | 2 min |
| Test Backend | 4 min | 6 min |
| Test Frontend | 2 min | 3 min |
| Security Audit | 1 min | 2 min |
| Build Docker | 8 min | 15 min |
| **TOTAL** | **18 min** | **31 min** |

## Dépannage

### Pipeline Bloqué

```bash
# Vérifier les runners actifs
./act_runner list

# Redémarrer un runner
./act_runner daemon &
```

### Tests qui Échouent

```bash
# Reproduire localement
make ci-test-backend  # ou ci-test-frontend

# Voir les logs détaillés
make backend-test -- -vv  # Mode très verbose
```

### Build Docker Échoue

```bash
# Tester le build localement
make docker-build-backend

# Nettoyer le cache Docker
docker system prune -a
```

### Coverage Insuffisant

```bash
# Générer rapport détaillé
make backend-coverage

# Identifier les fichiers non couverts
coverage report --show-missing
```

## Bonnes Pratiques

### 1. Exécuter CI en Local Avant de Pusher

```bash
# TOUJOURS exécuter avant un push
make ci-full
```

### 2. Commits Atomiques

Respectez la convention Conventional Commits :

```bash
# ✅ Bon
git commit -m "feat(api): add user authentication endpoint"
git commit -m "fix(frontend): resolve button alignment issue"
git commit -m "docs: update API documentation"

# ❌ Mauvais
git commit -m "changes"
git commit -m "work in progress"
```

### 3. Pull Requests de Qualité

- Description claire des changements
- Tests ajoutés pour les nouvelles fonctionnalités
- Coverage maintenu > 80%
- Documentation mise à jour

### 4. Gestion des Échecs

Si le pipeline échoue :

1. **Consulter les logs** dans Gitea Actions
2. **Reproduire localement** avec `make ci-*`
3. **Corriger le problème**
4. **Re-tester localement**
5. **Pusher la correction**

## Commandes Makefile Complètes

### Vue d'Ensemble

```bash
# Afficher toutes les commandes disponibles
make help

# Afficher uniquement les commandes CI
make help | grep "CI:"
```

### Commandes CI Disponibles

| Commande | Description |
|----------|-------------|
| `make ci-quick` | Lint rapide (backend + frontend) |
| `make ci-full` | Pipeline complet (lint + test + security) |
| `make ci-lint-backend` | Lint backend uniquement |
| `make ci-lint-frontend` | Lint frontend uniquement |
| `make ci-test-backend` | Tests backend avec coverage |
| `make ci-test-frontend` | Tests frontend |
| `make ci-security-backend` | Audit sécurité backend |
| `make ci-security-frontend` | Audit sécurité frontend |
| `make ci-build-docker` | Build images Docker localement |

## Intégration avec les Outils de Développement

### Pre-commit Hooks

Les hooks pre-commit exécutent automatiquement le lint :

```bash
# Installer les hooks
make setup

# Les hooks s'exécutent automatiquement à chaque commit
git commit -m "feat: nouvelle feature"
# → Lint automatique avant commit
```

### IDE Integration

#### PyCharm

1. Ouvrir **Settings → Tools → External Tools**
2. Ajouter un outil externe :
   - Name: `WindFlow CI Quick`
   - Program: `make`
   - Arguments: `ci-quick`
   - Working directory: `$ProjectFileDir$`

#### VS Code

Ajouter dans `.vscode/tasks.json` :

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "WindFlow: CI Quick Check",
      "type": "shell",
      "command": "make ci-quick",
      "group": "test",
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    },
    {
      "label": "WindFlow: Full CI Pipeline",
      "type": "shell",
      "command": "make ci-full",
      "group": "test",
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    }
  ]
}
```

## Évolution et Maintenance

### Mise à Jour du Pipeline

Pour modifier le pipeline :

1. Éditer `.gitea/workflows/ci.yml`
2. Tester localement avec les commandes `make ci-*`
3. Commiter et pusher
4. Vérifier l'exécution dans Gitea Actions

### Ajout de Nouveaux Jobs

Template pour ajouter un nouveau job :

```yaml
new-job:
  name: 🎯 Nouveau Job
  runs-on: ubuntu-latest
  needs: [job-prerequis]  # Optionnel
  steps:
    - name: 📥 Checkout code
      uses: actions/checkout@v4
    
    - name: 🔧 Votre étape
      run: |
        echo "Commandes à exécuter"
```

### Maintenance Régulière

- **Hebdomadaire** : Vérifier les mises à jour des actions Gitea
- **Mensuel** : Mettre à jour les dépendances de sécurité
- **Trimestriel** : Optimiser les temps d'exécution du pipeline

---

**Document maintenu par :** Équipe DevOps WindFlow  
**Support :** devops@windflow.dev  
**Documentation Gitea Actions :** https://docs.gitea.com/usage/actions/overview
