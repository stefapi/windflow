# Windflow-sample - Vue d'ensemble du projet

## 📋 Description

**Windflow-sample** est une interface web moderne de gestion Docker, alternative open-source à Portainer. Développé avec Vue3, il offre une solution complète pour gérer des environnements Docker locaux et distants.

## 🎯 Objectif du projet

Fournir une interface web intuitive et performante pour :
- Gérer des conteneurs, images, volumes et réseaux Docker
- Supporter plusieurs environnements Docker simultanément
- Automatiser les mises à jour avec scan de vulnérabilités
- Déployer des stacks depuis Git avec CI/CD
- Offrir une authentification multi-provider sécurisée

## 🏗️ Stack technique

### Backend (Python)
- **Runtime** : Fastapi
- **Framework** : Fastapi
- **ORM** : sqlalchemy ORM (SQLite/PostgreSQL)
- **Auth** : argon2, LDAP, OIDC, MFA (TOTP)
- **Docker** : API native v1.41+ (pas de dockerode)

### Frontend (vue3)
- **Framework** : Vue3
- **UI** : TailwindCSS 4, bits-ui, vue3
- **Charts** : LayerChart (D3-based)
- **Terminal** : xterm.js avec WebSocket
- **Icons** : vue3

### Infrastructure
- **Base de données** : SQLite (défaut) ou PostgreSQL
- **Reverse proxy** : Traefik/Nginx (optionnel)
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
│   Windflow-sample (Interface Web)          │
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
- Auth local (bcrypt) + sessions sécurisées
- LDAP/Active Directory
- OIDC/OAuth2 (Google, GitHub, Keycloak)
- MFA (2FA) avec QR codes TOTP
- RBAC (Role-Based Access Control)
- Audit logs détaillés

### 6. Monitoring
- Métriques CPU/RAM en temps réel
- Événements Docker streamés
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
│                    Windflow-sample Web UI                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │Containers│  │  Images  │  │  Stacks  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
├─────────────────────────────────────────────────────────┤
│              FastAPI API Routes                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Docker  │  │   Auth   │  │    Git   │             │
│  │   API    │  │  Layer   │  │  Sync    │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
├───────┼─────────────┼─────────────┼──────────────────────┤
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐             │
│  │ Docker   │  │ Database │  │  Git     │             │
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
- Variables d'environnement chiffrées
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
Windflow-sample/
├── src/
│   ├── lib/
│   │   ├── server/          # Backend (Python/FastAPI)
│   │   │   ├── docker.py    # API Docker (2800+ lignes)
│   │   │   ├── auth.py      # Auth multi-provider
│   │   │   ├── db.py        # sqlalchemy ORM
│   │   │   ├── git.py       # Git integration
│   │   │   └── hawser.py    # Hawser proxy
│   │   ├── components/      # Composants vue3
│   │   └── stores/          # State management
│   ├── routes/              # Pages et API routes
│   └── hooks.server.py      # Middleware global
├── scripts/                 # Build et maintenance
├── static/                  # Assets statiques
└── docs/                    # Documentation (ce dossier)
```

## 🎓 Prérequis pour reproduire

### Connaissances requises
- TypeScript/JavaScript moderne (ES2022+)
- Python 3.10+ (pour exemples backend alternatifs)
- Vue 3 Composition API (pour frontend alternatif)
- Docker API et concepts
- SQL (SQLite ou PostgreSQL)
- REST API et WebSocket
- Git et CI/CD

### Outils nécessaires
- Docker 20.10+ ou Podman 4.0+
- Git 2.30+
- Python 3.10+ (pour exemples)
- Vue CLI ou Vite (pour exemples frontend)

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
11. **10-BACKGROUND-PROCESSES.md** : Processus métriques/événements
12. **11-ENCRYPTION.md** : Chiffrement des secrets
13. **12-TERMINAL-WEBSOCKET.md** : Terminal web
14. **13-VOLUME-BROWSER.md** : Navigateur de volumes
15. **14-CODE-SNIPPETS.md** : Extraits réutilisables
16. **15-DEPLOYMENT.md** : Guide de déploiement

## 🤝 Contribuer

Les exemples de code sont fournis en :
- **Backend** : Python (FastAPI/Flask) pour reproduction
- **Frontend** : Vue 3 + TypeScript

Le projet original utilise TypeScript, mais les concepts sont transposables à d'autres stacks.

## 📄 Licence

Le projet Windflow-sample est sous licence Apache 2.0 (voir LICENSE.txt dans src/).

---

**Navigation** : [Suivant : Architecture →](01-ARCHITECTURE.md)
