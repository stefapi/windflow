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
  <em>Intelligent web tool for deploying Docker containers — multi-target orchestration, built-in AI, outstanding user experience</em>
</p>

---

**WindFlow** is an intelligent web tool for deploying Docker containers to target machines. It combines a modern user interface, a flexible data exchange system, and artificial intelligence to automate and optimize deployments.

## 🎯 Vision & Goals

### Ease of Use

* **Intuitive web interface** with visual workflows
* **AI-generated configuration** (LiteLLM)
* **One-click deployment** of preconfigured stacks
* **Powerful CLI/TUI** for automation (Rich + Typer + Textual)

### Maximum Flexibility

* **Multi-target support:** containers, VMs, physical servers
* **Adaptive orchestration:** Docker, Swarm, Kubernetes
* **Customizable templates** and a community marketplace
* **Configurable deployment workflows**

### Built-in Intelligence

* **Automatic resource optimization** via AI
* **Smart resolution** of conflicts and dependencies
* **Security suggestions** and best practices
* **Automatic error diagnostics**

## ✨ Key Features

### 🧠 Artificial Intelligence

* **LiteLLM Integration:** Multi-provider support (OpenAI, Claude, Ollama, etc.)
* **Smart configuration:** Auto-generated based on constraints
* **Resource optimization:** AI-driven optimal allocation
* **Conflict resolution:** Automatic detection and correction

### 🔧 Multi-Target Orchestration

* **Docker Engine:** Native containers and Docker Compose
* **Docker Swarm:** Cluster orchestration
* **Kubernetes + Helm:** Enterprise deployments
* **VM Management:** Vagrant + Libvirt for virtual machines
* **Physical Servers:** SSH + Ansible for bare metal

### 🌐 Modern User Interface

* **Web UI:** Vue.js 3 + TypeScript + Element Plus + UnoCSS
* **Visual Workflows:** Drag-and-drop editor inspired by n8n
* **Full CLI:** Rich + Typer for automation
* **Interactive TUI:** Textual for a modern terminal UI

### 🔐 Enterprise Security

* **SSO Integration:** Keycloak with LDAP/AD
* **HashiCorp Vault:** Centralized secrets management
* **Granular RBAC:** Role-based access control
* **Audit Trail:** Full action traceability

### 📊 Monitoring & Observability

* **Prometheus + Grafana:** Metrics and dashboards
* **ELK Stack:** Centralized logging
* **Intelligent Alerting:** Multi-channel notifications
* **Health Checks:** Continuous service monitoring

## 🧩 Modular Architecture

WindFlow adopts an **extensible modular architecture** that lets you start with a minimal system and progressively enable advanced features as needed.

### Minimal Start (< 5 minutes)

The **Minimal Core** includes only the essential services:

* ✅ Backend API (FastAPI)
* ✅ Database (PostgreSQL)
* ✅ Cache & Message Broker (Redis)
* ✅ Web Interface (Vue.js 3)
* ✅ Reverse Proxy (Nginx)
* ✅ Asynchronous worker (Celery)

**Resources:** 1.5 GB RAM, 2 CPU cores

```bash
# Ultra-fast minimal installation
./scripts/install.sh
# or
docker compose -f docker-compose.minimal.yml up -d
```

### Optional Extensions

Enable advanced features only when you need them:

| Extension      | Description                                 | Command                                    |
| -------------- | ------------------------------------------- | ------------------------------------------ |
| **Monitoring** | Prometheus + Grafana                        | `./scripts/enable-extension.sh monitoring` |
| **Logging**    | ELK Stack (Elasticsearch, Logstash, Kibana) | `./scripts/enable-extension.sh logging`    |
| **Secrets**    | HashiCorp Vault                             | `./scripts/enable-extension.sh vault`      |
| **SSO**        | Keycloak (LDAP/AD)                          | `./scripts/enable-extension.sh sso`        |
| **AI**         | LiteLLM + Ollama                            | `./scripts/enable-extension.sh ai`         |
| **Kubernetes** | K8s orchestration                           | `./scripts/enable-extension.sh kubernetes` |

### Benefits of the Modular Approach

* 🚀 **Ultra-fast start:** Working setup in minutes
* 💰 **Resource savings:** Only enabled services consume RAM/CPU
* 🎯 **Simplicity:** Start simple, evolve as you go
* 🔧 **Flexibility:** Enable/disable extensions on demand
* 📈 **Scalability:** Production-ready architecture from day one

📚 **Full documentation:** [Modular Architecture](doc/ARCHITECTURE-MODULAIRE.md)

## 🚀 Quick Start

### Prerequisites

* **Docker** ≥ 20.10 and docker-compose v2
* **Python** ≥ 3.11 and Poetry ≥ 1.8 (for backend development)
* **Node.js** ≥ 20 and pnpm ≥ 9 (for frontend development)

### Install with Docker (Recommended)

```bash
# Clone the repository
git clone https://gitea.yourdomain.com/yourusername/windflow.git
cd windflow

# Copy environment files
cp .env.example .env

# Start the application
docker compose up --build -d
```

**Access:**

* **Web Interface:** [http://localhost:8080](http://localhost:8080)
* **API Documentation:** [http://localhost:8080/api/docs](http://localhost:8080/api/docs)
* **CLI:** `docker exec -it windflow-cli windflow --help`

### Development Setup

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

## 🎯 Deployment Examples

WindFlow includes ready-to-use examples to deploy popular applications:

### 📦 Available Applications

#### Baserow — Open Source Airtable Alternative

No-code database with a modern interface (PostgreSQL + Redis)

```bash
# Create data directories
mkdir -p data/baserow/{postgres,redis,app,media}

# Start Baserow
docker compose -f examples/docker-compose.baserow.yml up -d

# Access the UI
# http://baserow.localhost
```

#### WordPress — Popular CMS

Full-featured content management system (MySQL + Redis + WP-CLI)

```bash
# Create data directories
mkdir -p data/wordpress/{mysql,redis,html,uploads,themes,plugins}

# Start WordPress
docker compose -f examples/docker-compose.wordpress.yml up -d

# Access the UI
# http://wordpress.localhost
```

### 🔧 WindFlow Integration

The examples are configured for seamless integration:

* ✅ **Shared network** with WindFlow (windflow-network)
* ✅ **Auto-discovery** via Traefik labels
* ✅ **Health checks** for monitoring
* ✅ **WindFlow labels** for management in the UI

📚 **Full documentation:** [examples/README.md](examples/README.md)

## 📖 Documentation

The complete documentation is in the `doc/` directory:

### Main Documentation

* **[Overview](doc/general_specs/01-overview.md)** — Project vision and goals
* **[Architecture](doc/general_specs/02-architecture.md)** — Design principles
* **[Technology Stack](doc/general_specs/03-technology-stack.md)** — Technologies used
* **[Deployment Guide](doc/general_specs/15-deployment-guide.md)** — Installation and configuration

### User Guides

* **[Core Features](doc/general_specs/10-core-features.md)** — Detailed features
* **[CLI Interface](doc/general_specs/08-cli-interface.md)** — Using the CLI/TUI
* **[LLM Integration](doc/general_specs/17-llm-integration.md)** — Artificial intelligence

### Developer Resources

* **[Data Model](doc/general_specs/04-data-model.md)** — Data structure
* **[API Design](doc/general_specs/07-api-design.md)** — API documentation
* **[Workflows](doc/workflows/README.md)** — Development processes
* **[Development Rules](.clinerules/README.md)** — Standards and conventions

## 🔧 Configuration

### Main Environment Variables

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

# Database
DATABASE_URL=postgresql+asyncpg://windflow:password@localhost:5432/windflow
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
VAULT_URL=http://localhost:8200
VAULT_TOKEN=your-vault-token

# Artificial Intelligence
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo-preview
OPENAI_API_KEY=your-openai-key
OLLAMA_BASE_URL=http://localhost:11434

# Monitoring
PROMETHEUS_ENABLED=true
LOG_LEVEL=INFO
```

### Multi-Environment Configuration

```bash
# Development
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.override.yml up

# Staging
cp .env.staging .env
docker compose -f docker-compose.yml -f docker-compose.staging.yml up

# Production
cp .env.production .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

## 🚢 Deployment

### Docker Deployment

```bash
# Build and push images
make docker-build
docker tag windflow:latest registry.example.com/windflow:v1.0.0
docker push registry.example.com/windflow:v1.0.0

# Deploy to server
docker compose pull
docker compose up -d --remove-orphans
```

### Kubernetes Deployment

```bash
# Via Helm (recommended)
helm repo add windflow https://charts.windflow.io
helm install windflow windflow/windflow \
  --namespace windflow \
  --create-namespace \
  --values values.yaml

# Via manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

### Production Ready

For a production deployment, make sure you have:

* **Reverse Proxy:** Nginx, Traefik, or Caddy for TLS/HTTP2
* **Monitoring:** Prometheus + Grafana + Alertmanager
* **Backups:** Database and persistent volumes
* **Secrets:** HashiCorp Vault in high availability
* **Logs:** ELK Stack or equivalent solution
* **Scaling:** Kubernetes HPA or Docker Swarm

## 🤝 Contributing

WindFlow is an open-source project and welcomes contributions!

### Contribution Guides

* **[Contributing Guide](CONTRIBUTING.md)** — Contribution process
* **[Development Workflows](doc/workflows/development-workflow.md)** — Technical processes
* **[Code Rules](.clinerules/README.md)** — Standards and conventions
* **[Code of Conduct](CODE_OF_CONDUCT.md)** — Community rules

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'feat: add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Local Development

```bash
# Full setup
make setup

# Pre-commit tests
make test
make lint

# Conventional commit
git commit -m "feat(api): add deployment optimization endpoint"
```

## 📊 Roadmap

### Version 1.0 (Q1 2025)

* [x] Modern web interface (Vue.js 3 + TypeScript)
* [x] Full REST API (FastAPI + SQLAlchemy)
* [x] Powerful CLI/TUI (Rich + Typer + Textual)
* [x] Docker + Kubernetes orchestration
* [ ] Artificial intelligence (LiteLLM)
* [ ] Integrated monitoring (Prometheus + Grafana)

### Version 1.1 (Q2 2025)

* [ ] Community template marketplace
* [ ] VM support (Vagrant + Libvirt)
* [ ] Advanced visual workflows
* [ ] Enterprise SSO (Keycloak)
* [ ] Full audit trail

### Version 1.2 (Q3 2025)

* [ ] Multi-cloud provider (AWS, Azure, GCP)
* [ ] GitOps integration (ArgoCD, Flux)
* [ ] Extensible plugin system
* [ ] Mobile app (React Native)

See the **[Full Roadmap](doc/general_specs/18-roadmap.md)** for more details.

## 📄 License

WindFlow is released under the **MIT** license. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgements

WindFlow is built on exceptional technologies:

* **[FastAPI](https://fastapi.tiangolo.com/)** — Modern web framework for Python
* **[Vue.js](https://vuejs.org/)** — Progressive framework for user interfaces
* **[Element Plus](https://element-plus.org/)** — Component library for Vue 3
* **[Rich](https://rich.readthedocs.io/)** — Library for rich CLI interfaces
* **[Docker](https://www.docker.com/)** — Containerization platform
* **[Kubernetes](https://kubernetes.io/)** — Container orchestrator
* **[PostgreSQL](https://www.postgresql.org/)** — Relational database
* **[Redis](https://redis.io/)** — In-memory data store

A big thank you to all the open-source communities that make WindFlow possible! 🚀

---

<div align="center">
  <p><em>Made with ❤️ by the WindFlow team</em></p>
  <p>
    <a href="https://github.com/yourusername/windflow">GitHub</a> •
    <a href="https://windflow.io">Website</a> •
    <a href="https://docs.windflow.io">Documentation</a> •
    <a href="https://community.windflow.io">Community</a>
  </p>
</div>
