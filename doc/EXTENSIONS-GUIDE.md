# Guide des Extensions WindFlow

**Version :** 1.0  
**Date :** 10/01/2025  
**Auteur :** Équipe WindFlow

---

## 📋 Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Installation Minimale](#installation-minimale)
3. [Extensions Disponibles](#extensions-disponibles)
4. [Gestion des Extensions](#gestion-des-extensions)
5. [Cas d'Usage](#cas-dusage)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Vue d'Ensemble

WindFlow adopte une **architecture modulaire** qui permet de démarrer avec un système minimal et d'ajouter des fonctionnalités au fur et à mesure des besoins.

### Philosophie

- **Start Simple** : Installation en < 2 minutes avec < 512 MB de RAM
- **Scale Progressively** : Ajout d'extensions selon les besoins
- **Zero Downtime** : Activation/désactivation à chaud des extensions
- **Configuration Dynamique** : Reconfiguration automatique des services

### Architecture

[ditaa]
```
┌────────────────────────────────────────────────────────────┐
│                   WINDFLOW ARCHITECTURE                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  CORE MINIMAL (< 512MB RAM, < 2 min)                       │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐         │
│  │ Traefik  │──│ windflow-api  │──│  frontend    │         │
│  │ (Proxy)  │  │   (SQLite)    │  │  (Vue.js 3)  │         │
│  └──────────┘  └───────────────┘  └──────────────┘         │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  EXTENSIONS OPTIONNELLES                                   │
│                                                            │
│  🗄️  Database:     PostgreSQL 15                           │
│  🔄  Cache:        Redis 7                                 │
│  🔐  Secrets:      HashiCorp Vault                         │
│  🔑  Auth:         Keycloak SSO/SAML                       │
│  📊  Monitoring:   Prometheus + Grafana                    │
│  ⚙️  Workers:       Celery + Flower                         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation Minimale

### Prérequis

- **Docker** 20.10+
- **Docker Compose** v2.0+
- **2 GB RAM** disponible (512 MB pour minimal, 1.5 GB de marge)
- **5 GB disque** disponible

### Installation Rapide

```bash
# 1. Cloner le repository
git clone https://github.com/windflow/windflow.git
cd windflow

# 2. Installer WindFlow minimal
make minimal

# OU directement avec Docker Compose
docker compose -f docker-compose.minimal.yml up -d
```

**Temps d'installation :** < 2 minutes  
**Mémoire utilisée :** < 512 MB

### Vérification

```bash
# Vérifier l'état des services
make status

# Vérifier les logs
make logs

# Tester l'accès
curl http://localhost/api/health
```

### Accès aux Services

Une fois démarré, vous pouvez accéder à :

- **Application Web** : http://localhost
- **API Backend** : http://localhost/api
- **Documentation API** : http://localhost/api/docs
- **Traefik Dashboard** : http://localhost:8080

---

## 📦 Extensions Disponibles

### 🗄️ Extension 1 : PostgreSQL Database

**Quand l'utiliser ?**
- Production avec haute disponibilité
- Volume de données > 1 GB
- Besoin de réplication et backup
- Conformité nécessitant une base externe

**Installation :**
```bash
make enable-database
# OU
docker compose -f docker-compose.minimal.yml \
  -f docker-compose.extensions.yml \
  --profile database up -d
```

**Configuration :**
```bash
# Variables d'environnement (.env)
POSTGRES_PASSWORD=windflow123
POSTGRES_PORT=5432
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://windflow:windflow123@windflow-postgres:5432/windflow
```

**Accès :**
- **Host** : localhost:5432
- **Database** : windflow
- **User** : windflow
- **Password** : windflow123 (défaut)

**Migration depuis SQLite :**
```bash
# Script de migration automatique (à venir)
python scripts/migrate-sqlite-to-postgres.py
```

---

### 🔄 Extension 2 : Redis Cache

**Quand l'utiliser ?**
- > 100 requêtes/seconde
- Sessions utilisateur distribuées
- Rate limiting avancé
- Pub/Sub messaging

**Installation :**
```bash
make enable-cache
```

**Configuration :**
```bash
# Variables d'environnement (.env)
REDIS_PASSWORD=redis123
REDIS_PORT=6379
CACHE_TYPE=redis
REDIS_URL=redis://:redis123@windflow-redis:6379/0
```

**Accès :**
```bash
# Connexion Redis CLI
docker exec -it windflow-redis redis-cli -a redis123

# Test
127.0.0.1:6379> PING
PONG
```

**Performance :**
- **Latence** : < 1ms
- **Throughput** : 100K+ ops/sec
- **Mémoire** : 256 MB max (configurable)

---

### 🔐 Extension 3 : HashiCorp Vault

**Quand l'utiliser ?**
- Environnement sécurisé (production)
- Rotation automatique des secrets
- Audit trail requis
- Conformité (PCI-DSS, HIPAA)

**Installation :**
```bash
make enable-secrets
```

**Configuration :**
```bash
# Variables d'environnement (.env)
VAULT_TOKEN=vault-dev-token
VAULT_URL=http://windflow-vault:8200
SECRETS_TYPE=vault
```

**Accès :**
- **URL** : http://vault.localhost
- **Token** : vault-dev-token (dev mode)

**Premiers pas :**
```bash
# Se connecter au Vault
docker exec -it windflow-vault sh

# Créer un secret
vault kv put secret/windflow/database password=supersecret

# Lire un secret
vault kv get secret/windflow/database
```

---

### 🔑 Extension 4 : Keycloak SSO

**Quand l'utiliser ?**
- Entreprise avec LDAP/Active Directory
- SAML 2.0 requis
- Single Sign-On multi-applications
- Gestion centralisée des utilisateurs

**Installation :**
```bash
make enable-sso
```

**Configuration :**
```bash
# Variables d'environnement (.env)
KEYCLOAK_ADMIN=admin
KEYCLOAK_PASSWORD=admin123
AUTH_TYPE=keycloak
KEYCLOAK_URL=http://windflow-keycloak:8080
```

**Accès :**
- **URL** : http://keycloak.localhost
- **Admin** : admin
- **Password** : admin123 (défaut)

**Configuration Realm WindFlow :**

1. Se connecter à l'admin console
2. Créer realm "windflow"
3. Créer client "windflow-api" (confidential)
4. Créer client "windflow-frontend" (public)
5. Configurer les rôles : admin, user, viewer

**Intégration :**
```python
# Backend configuration
AUTH_TYPE=keycloak
KEYCLOAK_REALM=windflow
KEYCLOAK_CLIENT_ID=windflow-api
KEYCLOAK_CLIENT_SECRET=<secret>
```

---

### 📊 Extension 5 : Monitoring (Prometheus + Grafana)

**Quand l'utiliser ?**
- Production
- Besoin d'alerting
- Analyse de performance
- Métriques business

**Installation :**
```bash
make enable-monitoring
# OU
make enable-mon  # raccourci
```

**Accès :**
- **Prometheus** : http://prometheus.localhost
- **Grafana** : http://grafana.localhost
  - User : admin
  - Password : admin123

**Métriques disponibles :**
- API response time (p50, p95, p99)
- Request rate par endpoint
- Error rate
- Database connections
- Cache hit rate
- Déploiements réussis/échoués

**Dashboards préconfigurés :**
1. **WindFlow Overview** : Vue d'ensemble système
2. **API Performance** : Métriques API détaillées
3. **Deployment Tracking** : Suivi des déploiements
4. **Infrastructure** : CPU, RAM, Network

**Alerting :**
```yaml
# Exemples d'alertes (prometheus-rules/)
- Alert: HighErrorRate
  Expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
  For: 5m
  
- Alert: SlowAPI
  Expr: histogram_quantile(0.95, http_request_duration_seconds) > 1.0
  For: 10m
```

---

### ⚙️ Extension 6 : Celery Workers

**Quand l'utiliser ?**
- Déploiements longs (> 30 secondes)
- Jobs planifiés (cron-like)
- Traitement asynchrone de masse
- Background tasks

**Installation :**
```bash
make enable-workers
# OU
make enable-work  # raccourci
```

**Note :** Cette extension nécessite Redis (activé automatiquement)

**Accès :**
- **Flower** (monitoring Celery) : http://flower.localhost
  - User : admin
  - Password : flower123

**Configuration :**
```bash
# Variables d'environnement (.env)
WORKER_CONCURRENCY=4  # Nombre de workers parallèles
CELERY_BROKER_URL=redis://:redis123@windflow-redis:6379/0
CELERY_RESULT_BACKEND=redis://:redis123@windflow-redis:6379/1
```

**Tâches disponibles :**
- `deploy_stack` : Déploiement de stack
- `health_check` : Vérification santé des déploiements
- `backup_database` : Sauvegarde automatique
- `cleanup_old_deployments` : Nettoyage

---

## 🔧 Gestion des Extensions

### Activer une Extension

```bash
# Via Makefile (recommandé)
make enable-<extension>

# Exemples
make enable-database
make enable-cache
make enable-monitoring

# Via Docker Compose directement
docker compose -f docker-compose.minimal.yml \
  -f docker-compose.extensions.yml \
  --profile <extension> up -d
```

### Désactiver une Extension

```bash
# Via Makefile
make disable-<extension>

# Exemples
make disable-database
make disable-monitoring

# Via Docker Compose
docker compose -f docker-compose.extensions.yml \
  --profile <extension> down
```

### Voir l'État des Services

```bash
# Statut de tous les services
make status

# Logs en temps réel
make logs

# Logs d'un service spécifique
docker compose logs -f windflow-api
docker compose logs -f windflow-postgres
```

### Modes d'Exécution

**Mode Minimal** (par défaut)
```bash
make minimal
```
Services : windflow-api, windflow-frontend, traefik

**Mode Développement Complet**
```bash
make dev-full
```
Services : minimal + postgres + redis + monitoring

**Mode Production**
```bash
make prod
```
Configuration optimisée pour production

---

## 💼 Cas d'Usage

### Cas 1 : Startup - Prototype Rapide

**Besoin :** Tester rapidement WindFlow, coûts minimaux

**Solution :**
```bash
# Installation minimale uniquement
make minimal
```

**Ressources :**
- RAM : < 512 MB
- CPU : 1 core
- Coût : ~$5/mois (VPS minimal)

---

### Cas 2 : PME - Production Simple

**Besoin :** 10-50 déploiements/jour, données < 10 GB

**Solution :**
```bash
make minimal
make enable-database
make enable-monitoring
```

**Ressources :**
- RAM : 2 GB
- CPU : 2 cores
- Coût : ~$20/mois

---

### Cas 3 : Entreprise - Production Complète

**Besoin :** 100+ déploiements/jour, SSO, haute disponibilité

**Solution :**
```bash
make minimal
make enable-database
make enable-cache
make enable-sso
make enable-monitoring
make enable-workers
make enable-secrets
```

**Ressources :**
- RAM : 8 GB
- CPU : 4 cores
- Coût : ~$80/mois

---

## 🔍 Troubleshooting

### Problème : Service ne démarre pas

```bash
# Vérifier les logs
docker compose logs windflow-<service>

# Vérifier la configuration
docker compose config

# Redémarrer proprement
make stop
make minimal
```

### Problème : Erreur de connexion base de données

```bash
# Vérifier que PostgreSQL est actif
docker compose ps windflow-postgres

# Tester la connexion
docker exec -it windflow-postgres psql -U windflow -d windflow

# Reconfigurer l'API
# Dans .env :
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://windflow:windflow123@windflow-postgres:5432/windflow

# Redémarrer
docker compose restart windflow-api
```

### Problème : Ports déjà utilisés

```bash
# Trouver le processus utilisant le port
sudo lsof -i :80
sudo lsof -i :5432

# Changer les ports dans .env
POSTGRES_PORT=5433
REDIS_PORT=6380

# Ou arrêter le service conflictuel
sudo systemctl stop postgresql
```

### Problème : Manque de ressources

```bash
# Vérifier l'utilisation
docker stats

# Libérer de la mémoire
docker system prune -a

# Désactiver extensions non utilisées
make disable-monitoring
make disable-workers
```

---

## 📚 Ressources Complémentaires

- [Architecture Modulaire](ARCHITECTURE-MODULAIRE.md) - Détails techniques
- [Guide de Déploiement](../PRODUCTION-DEPLOYMENT.md) - Production
- [Documentation API](../README.md) - Guide général
- [Troubleshooting Avancé](../SECURITY.md) - Sécurité

---

## 🆘 Support

**Questions :** Ouvrir une issue sur GitHub  
**Bugs :** Utiliser le template de bug report  
**Contributions :** Voir [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**Document maintenu par :** Équipe WindFlow  
**Dernière mise à jour :** 10/01/2025  
**Version :** 1.0
