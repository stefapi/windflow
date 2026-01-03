# Migration de Celery vers Asyncio

## Vue d'ensemble

Ce document décrit la migration de Celery vers une solution basée sur asyncio pour la gestion des tâches asynchrones dans WindFlow.

## Motivation

Celery ajoutait une complexité opérationnelle non nécessaire pour WindFlow :
- **Nature des tâches** : Principalement des orchestrations I/O (Docker, API), pas de calcul intensif
- **Overhead** : Broker Redis, workers séparés, configuration complexe
- **Simplicité** : FastAPI + asyncio gère parfaitement ce type de charge

## Changements effectués

### 1. Nouveau système de gestion des tâches

#### DeploymentOrchestrator
Nouveau service d'orchestration basé sur asyncio :
- **Fichier** : `backend/app/services/deployment_orchestrator.py`
- **Fonctionnalités** :
  - Retry automatique avec backoff exponentiel (3 tentatives max)
  - Recovery des déploiements après crash
  - Tracking des tâches actives
  - Persistance en base de données

#### Modèle Deployment enrichi
Nouveaux champs ajoutés au modèle `Deployment` :
- `task_started_at` : DateTime du démarrage de la tâche
- `task_retry_count` : Nombre de tentatives de retry

### 2. Fichiers supprimés

#### Fichiers Celery
- `backend/app/celery_app.py`
- `backend/app/core/celery_manager.py`
- `backend/app/tasks/deployment_tasks.py`
- `backend/app/tasks/monitoring_tasks.py`
- `backend/app/tasks/backup_tasks.py`

#### Spécifications
- `specs/001-celery-management/` (spec complète supprimée)

### 3. Fichiers modifiés

#### Configuration
- **pyproject.toml** : Suppression des dépendances `celery` et `redis`
- **backend/app/config.py** : Suppression des paramètres Celery et Redis
- **backend/app/main.py** : 
  - Suppression de la gestion du worker Celery intégré
  - Remplacement du recovery par `DeploymentOrchestrator.recover_pending_deployments()`

#### Services
- **backend/app/services/deployment_service.py** :
  - Méthode `create()` : Utilise `DeploymentOrchestrator.start_deployment()`
  - Méthode `retry_deployment()` : Utilise `DeploymentOrchestrator.start_deployment()`
  - Suppression de `recover_pending_deployments()` (redondante)

#### Tâches
- **backend/app/tasks/__init__.py** : Simplifié pour exporter uniquement les fonctions asyncio
- **backend/app/tasks/background_tasks.py** : Conservé tel quel (déjà asyncio)

#### Documentation
- **.clinerules/backend.md** : Section "Tâches Asynchrones" mise à jour avec DeploymentOrchestrator

### 4. Modèle de données

```python
# Nouveaux champs dans Deployment
class Deployment(Base):
    # ... champs existants
    
    # Task tracking (pour asyncio orchestrator)
    task_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    task_retry_count: Mapped[int] = mapped_column(nullable=False, default=0)
```

**Note** : Les tables sont créées automatiquement via `db.create_tables()`, pas besoin de migration Alembic.

## Utilisation

### Lancer un déploiement

```python
from backend.app.services.deployment_orchestrator import DeploymentOrchestrator

# Démarrer un déploiement
task = await DeploymentOrchestrator.start_deployment(
    deployment_id=str(deployment.id),
    stack_id=str(stack_id),
    target_id=str(target_id),
    user_id=str(user_id),
    configuration=variables
)
```

### Recovery au démarrage

Le recovery est automatique au démarrage de l'application (voir `main.py`) :

```python
stats = await DeploymentOrchestrator.recover_pending_deployments(
    max_age_minutes=0,  # Réessayer tous les PENDING
    timeout_minutes=60  # Marquer FAILED ceux > 60min
)
```

### Monitoring des tâches

```python
# Obtenir une tâche active
task = DeploymentOrchestrator.get_active_task(deployment_id)

# Annuler une tâche
success = DeploymentOrchestrator.cancel_task(deployment_id)

# Nombre de tâches actives
count = DeploymentOrchestrator.get_active_tasks_count()

# Toutes les tâches actives
tasks = DeploymentOrchestrator.get_all_active_tasks()
```

## Configuration Retry

Les paramètres de retry sont configurables dans `DeploymentOrchestrator` :

```python
class DeploymentOrchestrator:
    MAX_RETRIES = 3                # Nombre maximum de tentatives
    INITIAL_RETRY_DELAY = 60       # Délai initial (secondes)
    MAX_RETRY_DELAY = 600          # Délai maximum (10 minutes)
```

Le backoff est exponentiel : 60s, 120s, 240s, puis plafonné à 600s.

## Avantages de la nouvelle architecture

### Simplicité
- ✅ Un seul service backend (pas de worker séparé)
- ✅ Pas de broker Redis à maintenir
- ✅ Configuration minimale
- ✅ Débogage plus simple

### Performance
- ✅ Overhead minimal
- ✅ Parfait pour les tâches I/O
- ✅ Gestion native par FastAPI

### Fiabilité
- ✅ Persistance en base de données
- ✅ Recovery automatique au démarrage
- ✅ Retry avec backoff exponentiel
- ✅ Tracking des tâches actives

### Déploiement
- ✅ Un seul conteneur à déployer
- ✅ Moins de dépendances
- ✅ Configuration simplifiée

## Migration pour les développeurs

### Avant (Celery)
```python
from backend.app.tasks.deployment_tasks import deploy_stack

# Lancer une tâche
task = deploy_stack.delay(
    deployment_id=str(deployment.id),
    stack_id=str(stack_id),
    target_id=str(target_id),
    user_id=str(user_id),
    configuration=variables
)
```

### Après (Asyncio)
```python
from backend.app.services.deployment_orchestrator import DeploymentOrchestrator

# Lancer une tâche
task = await DeploymentOrchestrator.start_deployment(
    deployment_id=str(deployment.id),
    stack_id=str(stack_id),
    target_id=str(target_id),
    user_id=str(user_id),
    configuration=variables
)
```

## Tests

Aucun test n'utilisait Celery, donc aucune modification nécessaire.

## Compatibilité

- ✅ Tous les endpoints API restent identiques
- ✅ Le frontend n'a pas besoin de modifications
- ✅ Les déploiements existants continuent de fonctionner
- ✅ Le recovery gère les déploiements en cours

## Prochaines étapes

Si besoin à l'avenir, Celery peut être réintroduit si :
- Distribution sur plusieurs machines physiques nécessaire
- Isolation des workers requise (sécurité multi-tenant)
- Monitoring avancé avec Flower souhaité
- Priorités de tâches complexes nécessaires

Mais pour 90% des cas d'usage de WindFlow, asyncio est suffisant.

## Date de migration

**3 janvier 2026**

## Auteur

Migration effectuée dans le cadre de la simplification de l'architecture WindFlow.
