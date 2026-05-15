# Architecture Modulaire WindFlow

## 📋 Vue d'Ensemble

WindFlow adopte une **architecture modulaire extensible** permettant de démarrer avec un système minimal et d'activer progressivement les fonctionnalités avancées selon les besoins.

### Philosophie

- **Démarrage ultra-rapide** : Installation minimale fonctionnelle en < 5 minutes
- **Extensions optionnelles** : Activation à la demande des fonctionnalités avancées
- **Zéro overhead** : Seuls les services activés consomment des ressources
- **Production-ready** : Architecture scalable dès le départ

---

## 🏗️ Architecture Globale

```
┌─────────────────────────────────────────────────────────────────┐
│                        WINDFLOW PLATFORM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐ │
│  │   CORE MINIMAL  │  │      EXTENSIONS OPTIONNELLES         │ │
│  │   (Obligatoire) │  │         (À la demande)               │ │
│  ├─────────────────┤  ├──────────────────────────────────────┤ │
│  │ • API FastAPI   │  │ • Monitoring (Prometheus + Grafana)  │ │
│  │ • PostgreSQL    │  │ • Logging (ELK Stack)                │ │
│  │ • Redis         │  │ • Secrets (HashiCorp Vault)          │ │
│  │ • Nginx         │  │ • SSO (Keycloak)                     │ │
│  │ • Frontend      │  │ • IA (LiteLLM + Ollama)              │ │
│  │              │  │ • Orchestration (Kubernetes/Swarm)   │ │
│  └─────────────────┘  └──────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Core Minimal (docker-compose.minimal.yml)

### Services Inclus

#### 1. **API Backend (FastAPI)**
- **Port** : 8000
- **Rôle** : API REST principale
- **Dépendances** : PostgreSQL, Redis
- **Configuration** : `infrastructure/docker/Dockerfile.api`

#### 2. **PostgreSQL**
- **Port** : 5432
- **Rôle** : Base de données relationnelle
- **Volumes** : `postgres-data`
- **Configuration** : Migrations Alembic automatiques

#### 3. **Redis**
- **Port** : 6379
- **Rôle** : Cache, sessions, message broker
- **Volumes** : `redis-data`
- **Persistance** : AOF + RDB

#### 4. **Frontend (Vue.js 3)**
- **Port** : 80 (via Nginx)
- **Rôle** : Interface utilisateur web
- **Build** : Production optimisée
- **Configuration** : `infrastructure/docker/Dockerfile.frontend`

#### 5. **Nginx (Reverse Proxy)**
- **Port** : 8080 → Frontend, 8080/api → Backend
- **Rôle** : Load balancer, SSL termination
- **Configuration** : `infrastructure/docker/nginx.conf`

### Caractéristiques

- **RAM requise** : ~1.5 GB
- **CPU requis** : 2 cores
- **Temps de démarrage** : ~30 secondes
- **Taille images** : ~800 MB total

### Installation

```bash
# Démarrage minimal
docker compose -f docker-compose.minimal.yml up -d

# Accès
# Frontend: http://localhost:8080
# API: http://localhost:8080/api
# API Docs: http://localhost:8080/api/docs
```

---

## 🧩 Extensions Disponibles

### Extension : Monitoring (Prometheus + Grafana)

**Activation** :
```bash
./scripts/enable-extension.sh monitoring
```

**Services ajoutés** :
- **Prometheus** (9090) : Collecte de métriques
- **Grafana** (3000) : Visualisation et dashboards
- **Node Exporter** : Métriques système
- **cAdvisor** : Métriques containers

**Dashboards inclus** :
- `windflow-system-overview.json` : Vue d'ensemble système
- `windflow-deployments.json` : Métriques de déploiements

**Ressources** :
- RAM : +500 MB
- CPU : +0.5 core

---

### Extension : Logging (ELK Stack)

**Activation** :
```bash
./scripts/enable-extension.sh logging
```

**Services ajoutés** :
- **Elasticsearch** (9200) : Stockage des logs
- **Logstash** (5000) : Ingestion et transformation
- **Kibana** (5601) : Interface de visualisation
- **Filebeat** : Collecteur de logs

**Fonctionnalités** :
- Centralisation de tous les logs applicatifs
- Recherche full-text
- Alerting sur patterns
- Retention configurable

**Ressources** :
- RAM : +2 GB
- CPU : +1 core
- Disque : ~10 GB/jour (selon verbosité)

---

### Extension : Secrets Management (HashiCorp Vault)

**Activation** :
```bash
./scripts/enable-extension.sh vault
```

**Services ajoutés** :
- **Vault** (8200) : Gestion centralisée des secrets

**Fonctionnalités** :
- Rotation automatique des secrets
- Audit trail complet
- Intégration avec Kubernetes/Docker Swarm
- Chiffrement des secrets au repos

**Configuration** :
```bash
# Initialisation
vault operator init
vault operator unseal

# Configuration policies
vault policy write windflow-api /vault-config/policies/api.hcl
```

**Ressources** :
- RAM : +256 MB
- CPU : +0.2 core

---

### Extension : SSO (Keycloak)

**Activation** :
```bash
./scripts/enable-extension.sh sso
```

**Services ajoutés** :
- **Keycloak** (8180) : Identity Provider
- **PostgreSQL Keycloak** : Base de données dédiée

**Fonctionnalités** :
- Single Sign-On (SSO)
- Intégration LDAP/Active Directory
- OAuth2 / OpenID Connect
- Multi-tenancy

**Ressources** :
- RAM : +800 MB
- CPU : +0.5 core

---

### Extension : Intelligence Artificielle (LiteLLM + Ollama)

**Activation** :
```bash
./scripts/enable-extension.sh ai
```

**Services ajoutés** :
- **LiteLLM** (4000) : Proxy multi-provider
- **Ollama** (11434) : LLM local (optionnel)

**Fonctionnalités** :
- Génération intelligente de configurations
- Optimisation automatique des déploiements
- Résolution de conflits
- Suggestions de sécurité

**Providers supportés** :
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Ollama (Llama 2, Mistral, etc.)
- Cohere, Hugging Face, etc.

**Ressources** :
- LiteLLM : +128 MB RAM
- Ollama (avec modèle 7B) : +8 GB RAM, GPU recommandé

---

### Extension : Orchestration Kubernetes

**Activation** :
```bash
./scripts/enable-extension.sh kubernetes
```

**Composants ajoutés** :
- Helm charts pour déploiement K8s
- Opérateur WindFlow (CRD)
- Service Mesh (Istio - optionnel)
- Horizontal Pod Autoscaler

**Fonctionnalités** :
- Déploiement multi-cluster
- Auto-scaling avancé
- Rolling updates
- Blue-green deployments

---

### Extension : Docker Swarm

**Activation** :
```bash
./scripts/enable-extension.sh swarm
```

**Fonctionnalités** :
- Orchestration en cluster
- Load balancing natif
- Service discovery
- Rolling updates

---

## 📁 Structure des Fichiers

```
windflow/
├── docker-compose.minimal.yml      # Core minimal
├── docker-compose.yml              # Core + Extensions courantes
├── docker-compose.extensions.yml   # Définitions extensions
├── docker-compose.dev.yml          # Surcharges développement
├── docker-compose.prod.yml         # Configuration production
│
├── scripts/
│   ├── install.sh                  # Installation minimale
│   └── enable-extension.sh         # Activation extensions
│
├── infrastructure/
│   ├── docker/                     # Dockerfiles et configs
│   ├── kubernetes/                 # Manifests K8s
│   ├── helm/                       # Charts Helm
│   └── terraform/                  # Infrastructure as Code
│
├── backend/
│   └── app/
│       ├── core/                   # Code core obligatoire
│       └── extensions/             # Code extensions optionnelles
│           ├── monitoring/
│           ├── ai/
│           └── ...
│
└── doc/
    ├── ARCHITECTURE-MODULAIRE.md   # Ce document
    ├── EXTENSIONS-GUIDE.md         # Guide extensions détaillé
    └── ...
```

---

## 🔧 Gestion des Extensions

### Script enable-extension.sh

```bash
#!/bin/bash
# Usage: ./scripts/enable-extension.sh <extension> [--remove]

EXTENSION=$1
ACTION=${2:---add}

case $EXTENSION in
    monitoring)
        docker compose -f docker-compose.yml -f docker-compose.extensions.yml \
            --profile monitoring up -d
        ;;
    logging)
        docker compose -f docker-compose.yml -f docker-compose.extensions.yml \
            --profile logging up -d
        ;;
    vault)
        docker compose -f docker-compose.yml -f docker-compose.extensions.yml \
            --profile vault up -d
        ;;
    # ... autres extensions
esac
```

### Fichier .env pour Extensions

```bash
# Extensions activées
WINDFLOW_EXTENSIONS=monitoring,vault

# Monitoring
ENABLE_PROMETHEUS=true
ENABLE_GRAFANA=true
GRAFANA_ADMIN_PASSWORD=changeme

# Logging
ENABLE_ELK=false
ELASTICSEARCH_MEMORY=2g

# IA
ENABLE_AI=true
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama2:7b

# Secrets
ENABLE_VAULT=true
VAULT_TOKEN=changeme
```

---

## 🔄 Migration d'un Déploiement

### De Minimal vers Full

```bash
# 1. Backup de la configuration actuelle
docker compose ps > running_services.txt
cp .env .env.backup

# 2. Mise à jour de .env
echo "WINDFLOW_EXTENSIONS=monitoring,logging,ai" >> .env

# 3. Activation progressive
./scripts/enable-extension.sh monitoring
./scripts/enable-extension.sh logging
./scripts/enable-extension.sh ai

# 4. Vérification
docker compose ps
```

### De Full vers Minimal

```bash
# Désactivation des extensions
docker compose --profile monitoring down
docker compose --profile logging down

# Retour au minimal
docker compose -f docker-compose.minimal.yml up -d
```

---

## 🎯 Cas d'Usage Recommandés

### 1. Développement Local
```bash
# Minimal + hot-reload
docker-compose.minimal.yml + docker-compose.dev.yml
Extensions: monitoring (optionnel)
```

### 2. Staging/Tests
```bash
# Complet sans IA
docker-compose.yml
Extensions: monitoring, logging, vault
```

### 3. Production PME
```bash
# Complet avec IA
docker-compose.yml + docker-compose.prod.yml
Extensions: monitoring, logging, vault, ai
Orchestration: Docker Swarm
```

### 4. Production Enterprise
```bash
# Kubernetes avec toutes extensions
Helm charts + Istio
Extensions: monitoring, logging, vault, sso, ai
Orchestration: Kubernetes multi-cluster
```

---

## 📊 Comparaison des Configurations

| Configuration | RAM | CPU | Temps Démarrage | Services | Coût Cloud/Mois |
|---------------|-----|-----|-----------------|----------|-----------------|
| **Minimal** | 1.5 GB | 2 cores | 30s | 6 | ~$30 |
| **Standard** | 3 GB | 4 cores | 60s | 10 | ~$60 |
| **Full** | 8 GB | 8 cores | 120s | 18 | ~$150 |
| **Enterprise** | 16+ GB | 16+ cores | Variable | 25+ | ~$500+ |

---

## 🔐 Sécurité par Extension

### Core Minimal
- ✅ HTTPS (Let's Encrypt)
- ✅ JWT Authentication
- ✅ RBAC basique
- ✅ Rate limiting
- ✅ Input validation

### + Vault
- ✅ Secrets rotation automatique
- ✅ Chiffrement au repos
- ✅ Audit trail secrets

### + SSO
- ✅ Multi-factor authentication
- ✅ Session management avancé
- ✅ Intégration LDAP/AD

### + Monitoring
- ✅ Détection d'anomalies
- ✅ Alerting proactif
- ✅ Audit trail complet

---

## 📚 Ressources Complémentaires

- [Guide d'Installation Rapide](../README.md#installation-rapide)
- [Guide des Extensions](./EXTENSIONS-GUIDE.md)
- [Guide CI/CD](./CI-CD-GUIDE.md)
- [Spécifications Techniques](general_specs/README.md)

---

**Dernière mise à jour** : 02/10/2025  
**Version** : 1.0  
**Auteur** : Équipe WindFlow
