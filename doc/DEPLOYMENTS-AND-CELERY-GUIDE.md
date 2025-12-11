# Guide Complet : Déploiements et Celery - WindFlow

**Version** : 2.0  
**Dernière mise à jour** : 11 décembre 2024

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Configuration Celery](#configuration-celery)
3. [Worker Celery Intégré](#worker-celery-intégré)
4. [Système de Déploiement](#système-de-déploiement)
5. [Logs Temps Réel](#logs-temps-réel)
6. [Recovery Automatique](#recovery-automatique)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## Vue d'Ensemble

WindFlow implémente un système de déploiement asynchrone robuste avec :

- ✅ **Celery** pour le traitement asynchrone des tâches
- ✅ **Worker intégré** auto-démarré si besoin
- ✅ **PostgreSQL ou Redis** comme broker (PostgreSQL recommandé)
- ✅ **WebSocket** pour les notifications temps réel
- ✅ **Recovery automatique** des déploiements bloqués
- ✅ **Fallback asyncio** si Celery indisponible

### Architecture Triple Sécurité

```
┌──────────────────────────────────────────────────┐
│         SYSTÈME DE DÉPLOIEMENT WINDFLOW          │
├──────────────────────────────────────────────────┤
│                                                  │
│  1. CELERY WORKER (Production recommandé)       │
│     ├─ Workers externes dédiés                   │
│     ├─ Worker intégré auto-start (dev/fallback) │
│     ├─ Retry automatique (3 tentatives)         │
│     └─ Persistence garantie                      │
│                                                  │
│  2. ASYNCIO FALLBACK (Si Celery down)           │
│     ├─ S'exécute dans le backend FastAPI       │
│     ├─ Même logique que Celery                   │
│     └─ Pas de persistence ni retry auto          │
│                                                  │
│  3. RECOVERY SYSTEM (Sécurité ultime)           │
│     ├─ Au démarrage (récupère PENDING)          │
│     ├─ Périodique (toutes les 5min)             │
│     └─ Marque FAILED après timeout (60min)      │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## Configuration Celery

### Option 1 : PostgreSQL (Recommandé)

**Avantages** :
- ✅ Aucun service supplémentaire requis
- ✅ Réutilise PostgreSQL existant
- ✅ Persistence ACID compliant
- ✅ Configuration auto-dérivée

**Configuration `.env`** :
```env
# Base de données
DATABASE_URL=postgresql+asyncpg://windflow:password@postgres:5432/windflow

# Celery avec PostgreSQL
CELERY_ENABLED=true
CELERY_BROKER_TYPE=database

# Worker intégré (optionnel)
CELERY_AUTO_START_WORKER=true
CELERY_WORKER_CONCURRENCY=2
CELERY_WORKER_POOL=solo
CELERY_WORKER_LOGLEVEL=info
```

Le système convertit automatiquement :
```
DATABASE_URL (FastAPI):
  postgresql+asyncpg://windflow:password@localhost:5432/windflow

CELERY_BROKER_URL (auto-généré):
  db+postgresql+psycopg2://windflow:password@localhost:5432/windflow
```

### Option 2 : Redis (Performance légèrement meilleure)

```env
CELERY_ENABLED=true
CELERY_BROKER_TYPE=redis
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Worker intégré
CELERY_AUTO_START_WORKER=true
```

### Tables Celery Créées

Avec PostgreSQL, Celery crée automatiquement :
- `kombu_message` : Messages en file d'attente
- `kombu_queue` : Définition des queues
- `celery_taskmeta` : Métadonnées des tâches
- `celery_tasksetmeta` : Groupes de tâches

---

## Worker Celery Intégré

### Fonctionnement

WindFlow peut **démarrer automatiquement** un worker Celery local si :
1. `CELERY_ENABLED=true`
2. `CELERY_AUTO_START_WORKER=true`
3. Aucun worker externe n'est détecté

**Avantages** :
- ✅ Développement simplifié (un seul processus)
- ✅ Fallback automatique en production
- ✅ Redémarrage automatique (max 3 tentatives)
- ✅ Arrêt graceful (SIGTERM puis SIGKILL)

### Modes d'Utilisation

#### Mode 1 : Développement avec Worker Intégré

```bash
# .env
CELERY_ENABLED=true
CELERY_AUTO_START_WORKER=true

# Lancer WindFlow
python -m backend.app.main

# Logs attendus :
# [INFO] Démarrage du worker Celery intégré...
# [INFO] Worker Celery intégré démarré avec succès
```

#### Mode 2 : Production avec Workers Externes

```bash
# .env
CELERY_ENABLED=true
CELERY_AUTO_START_WORKER=false  # Désactiver auto-start

# Terminal 1 : Backend
python -m backend.app.main

# Terminal 2 : Workers dédiés
celery -A backend.app.celery_app worker --concurrency=4
```

#### Mode 3 : Production avec HA (Fallback)

```bash
# .env
CELERY_ENABLED=true
CELERY_AUTO_START_WORKER=true  # Laissé actif comme fallback

# Comportement :
# - Workers externes présents → utilise les externes
# - Workers externes down → démarre worker intégré automatiquement
# - Worker intégré échoue → fallback asyncio
```

### Configuration du Worker Intégré

| Variable | Défaut | Description |
|----------|--------|-------------|
| `CELERY_AUTO_START_WORKER` | `true` | Active/désactive l'auto-start |
| `CELERY_WORKER_CONCURRENCY` | `2` | Nombre de tâches parallèles |
| `CELERY_WORKER_POOL` | `solo` | Type de pool (solo, prefork, gevent, eventlet) |
| `CELERY_WORKER_LOGLEVEL` | `info` | Niveau de verbosité |

**⚠️ Note** : Le pool `solo` est recommandé avec SQLite (pas de multi-processus).

---

## Système de Déploiement

### Flux Complet

```
1. CRÉATION (API POST /deployments)
   User → DeploymentService.create()
   ↓
   Status: PENDING
   ↓
   Vérification : Celery disponible ?
   ├─ Oui → Tâche Celery (deploy_stack.delay)
   └─ Non → Tâche asyncio (create_background_task)

2. EXÉCUTION
   Worker Celery (ou asyncio)
   ↓
   Status: DEPLOYING
   ↓
   - Valide configuration
   - Génère docker-compose.yml (si applicable)
   - Déploie container(s)
   - Met à jour statut + logs à chaque étape
   ↓
   Status: RUNNING (succès) ou FAILED (échec)

3. ÉVÉNEMENTS TEMPS RÉEL
   À chaque update_status() :
   ↓
   deployment_events.emit_*()
   ↓
   EventBus → WebSocket Plugin
   ↓
   Broadcast aux clients WebSocket connectés
   ↓
   Frontend : Mise à jour automatique (statut, logs, progression)
```

### Événements WebSocket

1. **`DEPLOYMENT_STATUS_CHANGED`**
   - Déclenché : Changement de statut
   - Payload : `new_status`, `old_status`, `name`, `error_message`

2. **`DEPLOYMENT_LOGS_UPDATE`**
   - Déclenché : Nouveaux logs disponibles
   - Payload : `logs`, `append`, `timestamp`

3. **`DEPLOYMENT_PROGRESS`**
   - Déclenché : Progression du déploiement
   - Payload : `progress` (%), `current_step`, `total_steps`

### Démarrage

```bash
# Docker Compose
docker-compose up -d

# Services requis :
# - backend (FastAPI)
# - postgres (Base de données)
# - redis (Broker + PubSub) [si BROKER_TYPE=redis]
# - worker (Celery) [si workers externes]

# Vérification
docker-compose ps
docker-compose logs -f backend
docker-compose logs -f worker
```

---

## Logs Temps Réel

### Interface Utilisateur

**Depuis la Liste des Déploiements** :
1. Cliquez sur le bouton **Logs** (icône document)
2. Un drawer latéral s'ouvre avec :
   - 🟢 Badge "En direct" (connecté) ou ⚫ "Hors ligne"
   - 📊 Compteur de lignes
   - 📈 Barre de progression (si supportée)
   - 🎨 Logs colorisés (rouge=erreur, jaune=warning, vert=info, gris=debug)
   - 🎛️ Boutons : Auto-scroll, Effacer, Copier, Télécharger

### Fonctionnalités

**Auto-Scroll Intelligent** :
- Activé par défaut
- Se désactive si vous scrollez manuellement vers le haut
- Réactivable via le bouton

**Actions sur les Logs** :
- **Copier** : Copie tous les logs dans le presse-papier
- **Télécharger** : Télécharge un fichier `.txt`  
- **Effacer** : Vide l'affichage local (continue à recevoir les nouveaux)

**Reconnexion Automatique** :
- 3 tentatives avec délai exponentiel (1s, 2s, 4s)
- Badge "Hors ligne" si échec
- Logs conservés même pendant déconnexion temporaire

### Configuration Frontend

```bash
# frontend/.env
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_WEBSOCKET_DEBUG=false
VITE_ENABLE_LOGS_DEBUG=false
```

---

## Recovery Automatique

### Mécanisme Triple Protection

WindFlow garantit qu'aucun déploiement ne reste bloqué en `PENDING` :

#### 1. Startup Hook (Au démarrage)

```python
# backend/app/main.py - lifespan()
stats = await DeploymentService.recover_pending_deployments(
    db_session,
    max_age_minutes=0,  # Réessaye TOUS les PENDING
    timeout_minutes=60
)
```

**Effet** : Au démarrage du backend, tous les déploiements `PENDING` sont réessayés.

#### 2. Tâche Périodique (Toutes les 5 minutes)

```python
# Celery Beat Schedule
"retry-pending-deployments": {
    "schedule": crontab(minute="*/5"),
    "kwargs": {
        "max_age_minutes": 2,   # Considérer > 2min comme bloqué
        "timeout_minutes": 60   # Marquer FAILED après 60min
    }
}
```

**Activation** : Automatique si Celery Beat est lancé.

#### 3. Fallback Asyncio

Si Celery n'est pas disponible, la tâche de recovery s'exécute en asyncio dans le backend.

### Algorithme de Recovery

```
1. Marquer comme FAILED les PENDING trop anciens (> 60min)
   │
   ├─> SELECT WHERE status=PENDING AND created_at < (now - 60min)
   ├─> SET status=FAILED, error_message="Timeout"
   └─> Log: "Marqué N déploiements FAILED"

2. Récupérer les PENDING bloqués récents (> 2min mais < 60min)
   │
   └─> SELECT WHERE status=PENDING AND created_at < (now - 2min)

3. Pour chaque déploiement PENDING :
   │
   ├─> Vérifier statut (doit être PENDING)
   ├─> Relancer : Celery ou asyncio selon disponibilité
   ├─> SET status=DEPLOYING
   └─> Ajouter log "[RETRY] Nouvelle tentative..."

4. Retourner statistiques {retried, failed, skipped, errors}
```

### Métriques de Recovery

Chaque exécution retourne :
```json
{
    "status": "completed",
    "timestamp": "2024-12-11T12:00:00Z",
    "statistics": {
        "retried": 5,     // Nombre réessayés
        "failed": 3,      // Nombre marqués FAILED (timeout)
        "skipped": 1,     // Nombre ignorés
        "errors": 0       // Erreurs lors du retry
    }
}
```

---

## Troubleshooting

### Déploiements Bloqués en PENDING

**Symptômes** :
- Statut reste en "pending"
- Aucun log n'apparaît

**Solutions** :
```bash
# 1. Vérifier worker Celery
docker-compose ps worker
docker-compose logs -f worker

# 2. Vérifier Redis/PostgreSQL
docker-compose ps redis postgres
docker-compose exec redis redis-cli ping  # Doit retourner PONG

# 3. Forcer recovery manuel
python -c "
from backend.app.services.deployment_service import DeploymentService
from backend.app.database import AsyncSessionLocal
import asyncio

async def run():
    async with AsyncSessionLocal() as db:
        stats = await DeploymentService.recover_pending_deployments(db)
        print(stats)

asyncio.run(run())
"

# 4. Redémarrer services
docker-compose restart backend worker
```

### Worker Intégré Ne Démarre Pas

**Symptômes** :
- Logs : "Échec du démarrage du worker intégré"
- Utilisation fallback asyncio

**Solutions** :
```bash
# 1. Vérifier que celery est installé
poetry show celery

# 2. Vérifier DATABASE_URL (PostgreSQL uniquement, pas SQLite)
echo $DATABASE_URL

# 3. Tester manuellement
celery -A backend.app.celery_app worker --loglevel=debug

# 4. Vérifier les logs
tail -f logs/backend.log | grep "celery"
```

### WebSocket Déconnecté

**Symptômes** :
- Badge "Hors ligne"
- Statuts ne se mettent pas à jour

**Solutions** :
```bash
# 1. Console navigateur (F12) → Network → WS
# Chercher les erreurs de connexion WebSocket

# 2. Vérifier backend accessible
curl http://localhost:8000/health

# 3. Se reconnecter
# Déconnectez-vous et reconnectez-vous à l'interface

# 4. Vérifier logs backend
docker-compose logs backend | grep -i websocket
```

### Logs Ne S'Affichent Pas

**Symptômes** :
- Drawer vide malgré WebSocket connecté

**Solutions** :
```bash
# 1. Activer mode debug
# Dans DeploymentLogs.vue : :debug="true"

# 2. Vérifier événements dans console
# Console (F12) → Rechercher "DEPLOYMENT_LOGS_UPDATE"

# 3. Vérifier backend génère les logs
docker-compose logs backend | grep "update_status"

# 4. Tester déploiement simple
# Créer un déploiement basique et observer les logs backend
```

---

## Best Practices

### ✅ Configuration Recommandée

#### Développement

```env
# Utiliser worker intégré pour simplifier
CELERY_ENABLED=true
CELERY_AUTO_START_WORKER=true
CELERY_BROKER_TYPE=database
DEBUG=true
```

#### Staging

```env
# Tester la configuration production
CELERY_ENABLED=true
CELERY_AUTO_START_WORKER=false
CELERY_BROKER_TYPE=database
# Lancer workers externes dédiés
```

#### Production

```env
# Workers externes dédiés requis
CELERY_ENABLED=true
CELERY_AUTO_START_WORKER=false  # Ou true comme fallback HA
CELERY_BROKER_TYPE=database  # Ou redis selon besoins
PROMETHEUS_ENABLED=true
```

**Docker Compose Production** :
```yaml
services:
  worker:
    image: windflow-backend:latest
    command: celery -A backend.app.celery_app worker --concurrency=4
    deploy:
      replicas: 3  # Plusieurs workers pour HA
      
  beat:
    image: windflow-backend:latest
    command: celery -A backend.app.celery_app beat
    deploy:
      replicas: 1  # Un seul beat scheduler
```

### ✅ Monitoring

**Métriques à Surveiller** :
- Nombre de déploiements en PENDING
- Taux de recovery (retried/min)
- Nombre de timeouts (failed/day)
- Connexions WebSocket actives
- Latence événements WebSocket

**Logs Importants** :
```bash
# Recovery stats
grep "Recovery terminé" logs/backend.log

# Worker intégré
grep "Worker Celery intégré" logs/backend.log

# Événements WebSocket
grep "emit_" logs/backend.log

# Erreurs déploiement
grep "FAILED" logs/backend.log
```

### ✅ Sécurité

- **Logs** : Ne jamais logger de mots de passe ou tokens
- **WebSocket** : Authentification JWT obligatoire
- **RBAC** : Vérification permissions par organisation
- **Rate limiting** : Limiter création déploiements (100/min par défaut)

### ❌ À Éviter

- ❌ Compter uniquement sur asyncio fallback en production
- ❌ Utiliser SQLite comme broker Celery (non supporté)
- ❌ Lancer >10 workers intégrés simultanément
- ❌ Ignorer les logs de fallback (indiquent un problème)
- ❌ Désactiver le recovery automatique
- ❌ Garder les résultats Celery indéfiniment (expiration 1h par défaut)

---

## Comparaison des Approches

| Caractéristique | Workers Externes | Worker Intégré | Asyncio Fallback |
|-----------------|------------------|----------------|------------------|
| **Setup** | ⚠️ Launch manuel | ✅ Automatique | ✅ Aucun |
| **Performance** | ✅ Optimale | ⚠️ Moyenne | ⚠️ Limitée |
| **Persistence** | ✅ Complète | ⚠️ Partielle* | ❌ Aucune |
| **Retry auto** | ✅ 3 tentatives | ✅ 3 tentatives | ❌ Aucun |
| **Scaling** | ✅ Horizontal | ❌ Non | ❌ Non |
| **Prod ready** | ✅ Recommandé | ⚠️ Acceptable | ❌ Dev only |
| **Redémarrage backend** | ✅ Indépendant | ❌ Affecte worker | ❌ Perd tâches |

*Partielle : Les tâches survivent au restart du worker mais pas au restart backend

---

## Références

### Documentation Technique

- **Code** :
  - [`backend/app/celery_app.py`](../backend/app/celery_app.py) - Configuration Celery
  - [`backend/app/core/celery_manager.py`](../backend/app/core/celery_manager.py) - Worker intégré
  - [`backend/app/services/deployment_service.py`](../backend/app/services/deployment_service.py) - Service déploiements
  - [`backend/app/tasks/deployment_tasks.py`](../backend/app/tasks/deployment_tasks.py) - Tâches Celery
  - [`frontend/src/composables/useDeploymentWebSocket.ts`](../frontend/src/composables/useDeploymentWebSocket.ts) - WebSocket client

### Configuration

- [`.env.prod.example`](../.env.prod.example) - Variables production
- [`backend/app/config.py`](../backend/app/config.py) - Configuration backend

### Ressources Externes

- [Celery Documentation](https://docs.celeryq.dev/)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [Vue.js Composition API](https://vuejs.org/guide/extras/composition-api-faq.html)

---

**🎉 Système Production Ready** : Toutes les phases sont terminées et testées.

**📧 Support** : Pour toute question, créez une issue sur GitHub ou contactez l'équipe WindFlow.
