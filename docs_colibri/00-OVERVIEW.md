# Colibri - Vue d'ensemble du projet

## 📋 Description

**Colibri** est une interface web moderne de gestion Docker, alternative open-source à Portainer. Développé avec Vue 3 + TypeScript et FastAPI, il offre une solution complète pour gérer des environnements Docker locaux et distants.

## 🎯 Objectif du projet

Fournir une interface web intuitive et performante pour :
- Gérer des conteneurs, images, volumes et réseaux Docker
- Supporter plusieurs environnements Docker simultanément
- Automatiser les mises à jour avec scan de vulnérabilités
- Déployer des stacks depuis Git avec CI/CD
- Offrir une authentification multi-provider sécurisée

## 🏗️ Stack technique

### Backend (Python / FastAPI)
- **Framework** : FastAPI (async, OpenAPI auto-généré)
- **ORM** : SQLAlchemy 2.0 (async) avec support SQLite / PostgreSQL
- **Auth** : argon2-cffi (hashing), python-ldap3 (LDAP), authlib (OIDC), pyotp (TOTP)
- **Docker** : API native v1.41+ via httpx (pas de dockerode ni de SDK officiel)
- **Serveur** : Uvicorn (dev) / Gunicorn + Uvicorn workers (prod)

### Frontend (Vue 3 / TypeScript / Vite)
- **Framework** : Vue 3 (Composition API, `<script setup>`)
- **Build** : Vite
- **Langage** : TypeScript strict
- **UI** : TailwindCSS 4, composants personnalisés
- **Charts** : D3.js ou équivalent
- **Terminal** : xterm.js avec WebSocket
- **State** : Pinia

### Infrastructure
- **Base de données** : SQLite (défaut) ou PostgreSQL
- **Reverse proxy** : Traefik / Nginx (optionnel)
- **Docker** : 20.10+ ou Podman 4.0+
- **Agents** : Hawser (Go) pour environnements distants

## 📦 Fonctionnalités principales

### 1. Gestion Docker complète
- ✅ Conteneurs : CRUD, logs, stats, terminal interactif
- ✅ Images : pull/push, scan vulnérabilités, historique
- ✅ Volumes : navigation fichiers, import/export tar
- ✅ Réseaux : création, inspection, connexion
- ✅ Stacks Compose : deploy, update, rollback

### 2. Multi-environnements
```
┌─────────────────────────────────────┐
│   Colibri (Interface Web)   │
├─────────────────────────────────────┤
│  ┌──────┐  ┌──────┐  ┌──────┐      │
│  │ Env1 │  │ Env2 │  │ Env3 │      │
│  │Local │  │ TCP  │  │Hawser│      │
│  └──┬───┘  └──┬───┘  └──┬───┘      │
│     │         │         │           │
└─────┼─────────┼─────────┼───────────┘
      │         │         │
   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐
   │Unix │   │HTTP │   │ WS  │
   │Sock │   │TLS  │   │Edge │
   └─────┘   └─────┘   └─────┘
```

### 3. Auto-updates intelligentes
- Scan de vulnérabilités avant mise à jour (Grype/Trivy)
- Critères configurables (never/critical/high/medium/low)
- Rollback automatique en cas d'échec
- Planification avec expressions cron
- Notifications (email, webhook, Slack, Discord)

### 4. Intégration Git
- Clone et deploy depuis GitHub/GitLab/Bitbucket
- Support SSH et HTTPS avec credentials chiffrés
- Webhooks pour auto-deploy
- Variables d'environnement par stack
- Historique des déploiements

### 5. Sécurité avancée
- Auth local (Argon2id) + sessions sécurisées (cookies HttpOnly)
- LDAP/Active Directory (via `ldap3`)
- OIDC/OAuth2 (Google, GitHub, Keycloak) avec PKCE
- MFA (2FA) avec QR codes TOTP (via `pyotp`)
- RBAC (Role-Based Access Control)
- Audit logs détaillés

### 6. Monitoring
- Métriques CPU/RAM en temps réel
- Événements Docker streamés (SSE)
- Dashboard d'activité
- Alertes configurables
- Historique 30 jours (configurable)

## 🚀 Cas d'usage

### Scénario 1 : Homelab
```
Configuration : Socket Unix local
Environnements : 1 (machine locale)
Utilisateurs : 1-5 (famille/équipe)
Auth : Local ou LDAP
```

### Scénario 2 : Entreprise PME
```
Configuration : TCP + TLS multi-hôtes
Environnements : 3-10 (dev/staging/prod)
Utilisateurs : 10-50
Auth : OIDC (Keycloak) + RBAC
Monitoring : Métriques + alertes
```

### Scénario 3 : Edge Computing
```
Configuration : Hawser Edge (WebSocket)
Environnements : 50-500 (sites distants)
Réseau : NAT/Firewall (pas de port ouvert)
Auth : OIDC + MFA
```

## 📊 Architecture globale

```
┌─────────────────────────────────────────────────────────┐
│                    Colibri Web UI               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │Containers│  │  Images  │  │  Stacks  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│        Vue 3 + TypeScript + Vite                        │
├─────────────────────────────────────────────────────────┤
│              FastAPI API Routes (/api/v1/*)             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Docker  │  │   Auth   │  │    Git   │             │
│  │   API    │  │  Layer   │  │  Sync    │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
├───────┼─────────────┼─────────────┼──────────────────────┤
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐             │
│  │ Docker   │  │ SQLAlch. │  │  Git     │             │
│  │ Socket   │  │SQLite/PG │  │  Repos   │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
       │                                    │
   ┌───▼────────┐                      ┌───▼────┐
   │  Docker    │                      │  Git   │
   │  Daemon    │                      │ Remote │
   └────────────┘                      └────────┘
```

## 🔑 Concepts clés

### Environnement Docker
Un environnement représente une connexion à un daemon Docker :
- **Local** : Socket Unix `/var/run/docker.sock`
- **Remote** : TCP avec TLS (certificats client/serveur)
- **Hawser** : Agent proxy (standard ou edge via WebSocket)

### Stack Docker Compose
Un ensemble de conteneurs déployés ensemble :
- Fichier `docker-compose.yml`
- Variables d'environnement chiffrées (AES-256-GCM)
- Source : Git ou interne (créé via UI)
- Versioning et rollback

### Auto-update
Mise à jour automatique d'un conteneur :
1. Pull nouvelle image
2. Scan vulnérabilités
3. Comparaison avec critères
4. Recreation conteneur si OK
5. Rollback si échec

### Hawser Agent
Proxy Docker pour environnements NAT/Firewall :
- **Standard** : HTTP avec token auth
- **Edge** : WebSocket bidirectionnel
- Heartbeat toutes les 30s
- Auto-reconnexion

## 📁 Structure du projet

```
colibri/
├── backend/                 # Backend Python / FastAPI
│   ├── app/
│   │   ├── api/            # Routers FastAPI (/api/v1/*)
│   │   ├── auth/           # Authentification (local, LDAP, OIDC, MFA)
│   │   ├── core/           # Config, DB, securité
│   │   ├── models/         # Modèles SQLAlchemy
│   │   ├── schemas/        # Schémas Pydantic
│   │   ├── services/       # Logique métier (docker, git, etc.)
│   │   ├── tasks/          # Tâches asyncio background
│   │   └── main.py         # Point d'entrée FastAPI
│   └── tests/
├── frontend/                # Frontend Vue 3 / TypeScript / Vite
│   ├── src/
│   │   ├── components/     # Composants Vue 3
│   │   ├── composables/    # Composables TypeScript
│   │   ├── stores/         # State Pinia
│   │   ├── services/       # Appels API TypeScript
│   │   ├── views/          # Pages principales
│   │   └── main.ts         # Point d'entrée
│   ├── vite.config.ts
│   └── tsconfig.json
├── docker-compose.yml
└── docs/                   # Documentation (ce dossier)
```

## 🎓 Prérequis pour reproduire

### Connaissances requises
- Python 3.11+ (FastAPI, SQLAlchemy 2.0, async/await)
- TypeScript moderne (ES2022+, Vue 3 Composition API)
- Docker API et concepts
- SQL (SQLite ou PostgreSQL)
- REST API et WebSocket
- Git et CI/CD

### Outils nécessaires
- Docker 20.10+ ou Podman 4.0+
- Python 3.11+
- Node.js 20+ avec pnpm (ou npm)
- Git 2.30+

## 📚 Comment utiliser cette documentation

1. **00-OVERVIEW.md** (ce fichier) : Vue d'ensemble
2. **01-ARCHITECTURE.md** : Architecture détaillée avec diagrammes
3. **02-DOCKER-API-MODULE.md** : API Docker native (cœur du projet)
4. **03-DATABASE-SCHEMA.md** : Base de données et migrations
5. **04-AUTHENTICATION.md** : Authentification multi-provider
6. **05-GIT-INTEGRATION.md** : Intégration Git et webhooks
7. **06-AUTO-UPDATES.md** : Mises à jour automatiques
8. **07-VULNERABILITY-SCANNING.md** : Scanner de vulnérabilités
9. **08-HAWSER-PROXY.md** : Système Hawser pour NAT
10. **09-SCHEDULER.md** : Tâches programmées (cron)
11. **10-ENCRYPTION.md** : Chiffrement des secrets
12. **11-TERMINAL-WEBSOCKET.md** : Terminal web
13. **12-VOLUME-BROWSER.md** : Navigateur de volumes
14. **13-BACKGROUND-PROCESSES.md** : Processus métriques/événements
15. **14-DEPLOYMENT.md** : Guide de déploiement
16. **15-CODE-SNIPPETS.md** : Extraits réutilisables

## 🤝 Contribuer

Les exemples de code sont fournis en :
- **Backend** : Python (FastAPI, SQLAlchemy 2.0)
- **Frontend** : Vue 3 + TypeScript (Composition API, `<script setup>`)

## 📄 Licence

Le projet Colibri est sous licence Apache 2.0 (voir LICENSE.txt).

---

**Navigation** : [Suivant : Architecture →](01-ARCHITECTURE.md)
