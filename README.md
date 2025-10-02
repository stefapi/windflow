# WindFlow

<div align="center">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D" alt="Vue.js">
  <img src="https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" alt="Kubernetes">
  <img src="https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
</div>

<p align="center">
  <em>Outil web intelligent de déploiement de containers Docker — orchestration multi-cible, IA intégrée, expérience utilisateur exceptionnelle</em>
</p>

---

**WindFlow** est un outil web intelligent de déploiement de containers Docker sur des machines cibles. Il combine une interface utilisateur moderne, un système d'échange de données flexible, et une intelligence artificielle pour automatiser et optimiser les déploiements.

## 🎯 Vision et Objectifs

### Simplicité d'Utilisation
- **Interface web intuitive** avec workflows visuels
- **Configuration automatique** générée par IA (LiteLLM)
- **One-click deployment** de stacks préconfigurées
- **CLI/TUI puissants** pour l'automatisation (Rich + Typer + Textual)

### Flexibilité Maximale
- **Support multi-cible** : containers, VMs, serveurs physiques
- **Orchestration adaptative** : Docker, Swarm, Kubernetes
- **Templates personnalisables** et marketplace communautaire
- **Workflows de déploiement** configurables

### Intelligence Intégrée
- **Optimisation automatique** des ressources par IA
- **Résolution intelligente** des conflits et dépendances
- **Suggestions de sécurité** et bonnes pratiques
- **Diagnostic automatique** des erreurs

## ✨ Fonctionnalités Principales

### 🧠 Intelligence Artificielle
- **LiteLLM Integration** : Support multi-provider (OpenAI, Claude, Ollama, etc.)
- **Configuration intelligente** : Génération automatique selon contraintes
- **Optimisation des ressources** : IA pour l'allocation optimale
- **Résolution de conflits** : Détection et correction automatique

### 🔧 Orchestration Multi-Cible
- **Docker Engine** : Containers natifs et Docker Compose
- **Docker Swarm** : Orchestration en cluster
- **Kubernetes + Helm** : Déploiements enterprise
- **VM Management** : Vagrant + Libvirt pour machines virtuelles
- **Physical Servers** : SSH + Ansible pour serveurs physiques

### 🌐 Interface Utilisateur Moderne
- **Interface Web** : Vue.js 3 + TypeScript + Element Plus + UnoCSS
- **Workflows Visuels** : Éditeur drag-and-drop inspiré de n8n
- **CLI Complet** : Rich + Typer pour automatisation
- **TUI Interactif** : Textual pour interface terminal moderne

### 🔐 Sécurité Enterprise
- **SSO Integration** : Keycloak avec LDAP/AD
- **HashiCorp Vault** : Gestion centralisée des secrets
- **RBAC Granulaire** : Contrôle d'accès basé sur les rôles
- **Audit Trail** : Traçabilité complète des actions

### 📊 Monitoring et Observabilité
- **Prometheus + Grafana** : Métriques et dashboards
- **ELK Stack** : Centralisation des logs
- **Alerting Intelligent** : Notifications multi-canal
- **Health Checks** : Surveillance continue des services

## 🧩 Architecture Modulaire

WindFlow adopte une **architecture modulaire extensible** permettant de démarrer avec un système minimal et d'activer progressivement les fonctionnalités avancées selon vos besoins.

### Démarrage Minimal (< 5 minutes)

Le **Core Minimal** inclut uniquement les services essentiels :
- ✅ API Backend (FastAPI)
- ✅ Base de données (PostgreSQL)
- ✅ Cache & Message Broker (Redis)
- ✅ Interface Web (Vue.js 3)
- ✅ Reverse Proxy (Nginx)
- ✅ Worker asynchrone (Celery)

**Ressources** : 1.5 GB RAM, 2 CPU cores

```bash
# Installation minimale ultra-rapide
./scripts/install.sh
# ou
docker compose -f docker-compose.minimal.yml up -d
```

### Extensions Optionnelles

Activez les fonctionnalités avancées uniquement quand vous en avez besoin :

| Extension | Description | Commande |
|-----------|-------------|----------|
| **Monitoring** | Prometheus + Grafana | `./scripts/enable-extension.sh monitoring` |
| **Logging** | ELK Stack (Elasticsearch, Logstash, Kibana) | `./scripts/enable-extension.sh logging` |
| **Secrets** | HashiCorp Vault | `./scripts/enable-extension.sh vault` |
| **SSO** | Keycloak (LDAP/AD) | `./scripts/enable-extension.sh sso` |
| **IA** | LiteLLM + Ollama | `./scripts/enable-extension.sh ai` |
| **Kubernetes** | Orchestration K8s | `./scripts/enable-extension.sh kubernetes` |

### Avantages de l'Approche Modulaire

- 🚀 **Démarrage ultra-rapide** : Installation fonctionnelle en quelques minutes
- 💰 **Économie de ressources** : Seuls les services activés consomment de la RAM/CPU
- 🎯 **Simplicité** : Commencez simple, évoluez selon vos besoins
- 🔧 **Flexibilité** : Activez/désactivez les extensions à la demande
- 📈 **Scalabilité** : Architecture production-ready dès le départ

📚 **Documentation complète** : [Architecture Modulaire](doc/ARCHITECTURE-MODULAIRE.md)

## 🚀 Installation Rapide

### Prérequis

- **Docker** ≥ 20.10 et docker-compose v2
- **Python** ≥ 3.11 et Poetry ≥ 1.8 (pour développement backend)
- **Node.js** ≥ 20 et pnpm ≥ 9 (pour développement frontend)

### Installation avec Docker (Recommandée)

```bash
# Cloner le repository
git clone https://gitea.yourdomain.com/yourusername/windflow.git
cd windflow

# Copier les fichiers d'environnement
cp .env.example .env

# Lancer l'application
docker compose up --build -d
```

**Accès :**
- **Interface Web** : http://localhost:8080
- **API Documentation** : http://localhost:8080/api/docs
- **CLI** : `docker exec -it windflow-cli windflow --help`

### Installation pour Développement

```bash
# Backend (FastAPI)
poetry install --with dev
poetry run uvicorn windflow.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Vue.js 3)
cd frontend
pnpm install
pnpm dev  # http://localhost:5173

# CLI/TUI
pip install -e ./cli
windflow --help
```

## 📖 Documentation

La documentation complète se trouve dans le répertoire `doc/` :

### Documentation Principale
- **[Vue d'Ensemble](doc/spec/01-overview.md)** - Vision et objectifs du projet
- **[Architecture](doc/spec/02-architecture.md)** - Principes de conception
- **[Stack Technologique](doc/spec/03-technology-stack.md)** - Technologies utilisées
- **[Guide de Déploiement](doc/spec/15-deployment-guide.md)** - Installation et configuration

### Guides Utilisateur
- **[Fonctionnalités Principales](doc/spec/10-core-features.md)** - Fonctionnalités détaillées
- **[Interface CLI](doc/spec/08-cli-interface.md)** - Utilisation de la CLI/TUI
- **[Intégration LLM](doc/spec/17-llm-integration.md)** - Intelligence artificielle

### Ressources Développeur
- **[Modèle de Données](doc/spec/04-data-model.md)** - Structure des données
- **[API Design](doc/spec/07-api-design.md)** - Documentation des APIs
- **[Workflows](doc/workflows/README.md)** - Processus de développement
- **[Règles de Développement](.clinerules/README.md)** - Standards et conventions


## 🔧 Configuration

### Variables d'Environnement Principales

```bash
# Application
APP_NAME=WindFlow
APP_VERSION=1.0.0
APP_ENV=development
DEBUG=true

# API Backend
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Base de données
DATABASE_URL=postgresql+asyncpg://windflow:password@localhost:5432/windflow
REDIS_URL=redis://localhost:6379/0

# Sécurité
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Intelligence Artificielle
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=your-openai-key
OLLAMA_BASE_URL=http://localhost:11434

# Monitoring
PROMETHEUS_ENABLED=true
LOG_LEVEL=INFO
```

### Configuration Multi-Environnements

```bash
# Développement
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.override.yml up

# Staging
cp .env.staging .env
docker compose -f docker-compose.yml -f docker-compose.staging.yml up

# Production
cp .env.production .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## 🚢 Déploiement

### Déploiement Docker

```bash
# Build et push des images
make docker-build
docker tag windflow:latest registry.example.com/windflow:v1.0.0
docker push registry.example.com/windflow:v1.0.0

# Déploiement sur serveur
docker compose pull
docker compose up -d --remove-orphans
```

### Déploiement Kubernetes

```bash
# Via Helm (recommandé)
helm repo add windflow https://charts.windflow.io
helm install windflow windflow/windflow \
  --namespace windflow \
  --create-namespace \
  --values values.yaml

# Via manifestes
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### Production Ready

Pour un déploiement en production, assurez-vous de :

- **Reverse Proxy** : Nginx, Traefik ou Caddy pour TLS/HTTP2
- **Monitoring** : Prometheus + Grafana + Alertmanager
- **Backups** : Base de données et volumes persistants
- **Secrets** : HashiCorp Vault en haute disponibilité
- **Logs** : ELK Stack ou solution équivalente
- **Scaling** : Kubernetes HPA ou Docker Swarm

## 🤝 Contribution

WindFlow est un projet open source qui accueille les contributions ! 

### Guides de Contribution
- **[Guide de Contribution](CONTRIBUTING.md)** - Processus de contribution
- **[Workflows de Développement](doc/workflows/development-workflow.md)** - Processus techniques
- **[Règles de Code](.clinerules/README.md)** - Standards et conventions
- **[Code de Conduite](CODE_OF_CONDUCT.md)** - Règles communautaires

### Comment Contribuer
1. **Fork** le repository
2. **Créer** une branche feature (`git checkout -b feature/amazing-feature`)
3. **Commiter** les changements (`git commit -m 'feat: add amazing feature'`)
4. **Push** vers la branche (`git push origin feature/amazing-feature`)
5. **Ouvrir** une Pull Request

### Développement Local
```bash
# Setup complet
make setup

# Tests avant commit
make test
make lint

# Commit avec convention
git commit -m "feat(api): add deployment optimization endpoint"
```

## 📊 Roadmap

### Version 1.0 (Q1 2025)
- [x] Interface web moderne (Vue.js 3 + TypeScript)
- [x] API REST complète (FastAPI + SQLAlchemy)
- [x] CLI/TUI puissants (Rich + Typer + Textual)
- [x] Orchestration Docker + Kubernetes
- [ ] Intelligence artificielle (LiteLLM)
- [ ] Monitoring intégré (Prometheus + Grafana)

### Version 1.1 (Q2 2025)
- [ ] Marketplace de templates communautaires
- [ ] Support VM (Vagrant + Libvirt)
- [ ] Workflows visuels avancés
- [ ] SSO enterprise (Keycloak)
- [ ] Audit trail complet

### Version 1.2 (Q3 2025)
- [ ] Multi-cloud provider (AWS, Azure, GCP)
- [ ] GitOps integration (ArgoCD, Flux)
- [ ] Plugin system extensible
- [ ] Mobile app (React Native)

Voir la **[Roadmap Complète](doc/spec/18-roadmap.md)** pour plus de détails.

## 📄 Licence

WindFlow est publié sous licence **MIT**. Voir [LICENSE](LICENSE) pour les détails.

## 🙏 Remerciements

WindFlow s'appuie sur des technologies exceptionnelles :

- **[FastAPI](https://fastapi.tiangolo.com/)** - Framework web moderne pour Python
- **[Vue.js](https://vuejs.org/)** - Framework progressif pour interfaces utilisateur
- **[Element Plus](https://element-plus.org/)** - Bibliothèque de composants Vue 3
- **[Rich](https://rich.readthedocs.io/)** - Bibliothèque pour interfaces CLI riches
- **[Docker](https://www.docker.com/)** - Plateforme de conteneurisation
- **[Kubernetes](https://kubernetes.io/)** - Orchestrateur de containers
- **[PostgreSQL](https://www.postgresql.org/)** - Base de données relationnelle
- **[Redis](https://redis.io/)** - Store de données en mémoire

Un grand merci à toutes les communautés open source qui rendent WindFlow possible ! 🚀

---

<div align="center">
  <p><em>Créé avec ❤️ par l'équipe WindFlow</em></p>
  <p>
    <a href="https://github.com/yourusername/windflow">GitHub</a> •
    <a href="https://windflow.io">Site Web</a> •
    <a href="https://docs.windflow.io">Documentation</a> •
    <a href="https://community.windflow.io">Communauté</a>
  </p>
</div>
