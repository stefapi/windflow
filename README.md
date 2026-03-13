# WindFlow

<div align="center">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D" alt="Vue.js">
  <img src="https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/KVM-0047AB?style=for-the-badge&logo=linux&logoColor=white" alt="KVM">
  <img src="https://img.shields.io/badge/Proxmox-FF6C37?style=for-the-badge&logo=proxmox&logoColor=white" alt="Proxmox">
  <img src="https://img.shields.io/badge/Raspberry%20Pi-C51A4A?style=for-the-badge&logo=raspberrypi&logoColor=white" alt="Raspberry Pi">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
</div>

<p align="center">
  <em>Lightweight self-hosted infrastructure manager — Containers & VMs on Raspberry Pi or x86 servers, extensible with plugins</em>
</p>

---

**WindFlow** is a lightweight, self-hosted infrastructure manager for containers and virtual machines. It runs on anything from a Raspberry Pi to a dedicated x86 server. A minimal core handles compute (Docker containers, VMs), while a **plugin marketplace** extends capabilities on demand — reverse proxy, databases, DNS, monitoring, backups, mail, and more.

Install only what you need. Nothing more.

## 🎯 Philosophy

### Minimal Core

WindFlow's core does three things: **manage containers**, **manage VMs**, and **provide a plugin marketplace**. Everything else — reverse proxy, DNS, databases, monitoring, backups, workflows, AI — is a plugin you install if and when you need it.

### Everything is a Plugin

A Raspberry Pi with 2 GB of RAM doesn't need Elasticsearch. A homelab doesn't need a workflow engine. WindFlow never forces complexity on you. Each plugin is installable and removable from the UI, declares its resource requirements, and checks architecture compatibility before installation.

### Runs Everywhere

WindFlow is built multi-arch from the ground up. All core images support **ARM64** (Raspberry Pi 4/5, Orange Pi, etc.) and **x86_64**. Plugins declare their supported architectures, and the UI warns you if your machine doesn't have enough resources.

### Self-Hosted First

No cloud dependency, no vendor lock-in, no mandatory external services. WindFlow runs on your hardware, on your network, under your control.

## ✨ What's in the Core

### Container Management (Docker)

* Containers and Docker Compose stacks
* Image management (pull, build, prune)
* Volume management with built-in file browser
* Network management with environment isolation
* Real-time logs and interactive WebSocket terminal
* Deployment pipeline with retry and rollback
* Stack templates with Jinja2 and versioning

### Virtual Machine Management

* **KVM/QEMU** via libvirt — create, snapshot, clone, migrate VMs
* **Proxmox VE** — full API integration for VMs and LXC containers
* **VirtualBox** — cross-platform VM management (optional)
* Integrated VNC/SPICE console in the web UI
* Disk management (qcow2, raw, vdi, vmdk)
* ISO and cloud-init image management

### Plugin Marketplace

* Browse, search, and install plugins from the UI or CLI
* One-click installation with guided configuration wizard
* Dependency management between plugins
* Architecture and resource compatibility checks
* Plugin updates with changelog
* Support for custom/self-hosted plugin registries

### Modern Interface

* **Web UI:** Vue.js 3 + TypeScript + Element Plus
* **Dashboard** with widgets and metrics
* **CLI:** Rich + Typer for scripting and automation
* **TUI:** Textual for a modern interactive terminal UI

### Multi-Target

* Manage the local machine or remote servers via SSH
* Consolidated view of all machines and services
* Basic per-machine monitoring (CPU, RAM, disk, network)
* Deploy containers and manage VMs across multiple hosts

### Auth & Organizations

* JWT authentication with refresh tokens
* Organizations and environments
* Granular RBAC (role-based access control)

## 🔌 Plugin Ecosystem

Plugins extend WindFlow's capabilities. A plugin can be a **deployable service** (installs a Docker stack), a **functional extension** (adds features to the core UI/API), or **both**.

### Plugin Categories

| Category | Available Plugins |
|----------|-------------------|
| **Reverse Proxy & Access** | Traefik, Caddy, Nginx Proxy Manager, Cloudflare Tunnel |
| **DNS** | Pi-hole, CoreDNS, Cloudflare DNS |
| **TLS Certificates** | Let's Encrypt (ACME) |
| **Databases** | PostgreSQL, MySQL/MariaDB, MongoDB, Redis |
| **Messaging** | MQTT (Mosquitto), RabbitMQ, NATS |
| **Mail** | Mailu, Stalwart |
| **Monitoring** | Uptime Kuma, Netdata, Prometheus + Grafana |
| **Backup** | Restic, Borg |
| **Storage** | MinIO (S3), Samba, NFS |
| **Security** | Authelia (2FA), Vaultwarden, Trivy (vulnerability scanning), Vault (secrets) |
| **Git & CI** | Gitea, webhook auto-deploy |
| **Workflows** | n8n, Node-RED |
| **AI** | Ollama (local LLM), LiteLLM (multi-provider) |
| **SSO** | Keycloak (LDAP/AD, OIDC, SAML) |

### How Plugins Work

**Service plugins** deploy a preconfigured Docker stack. For example, installing the Traefik plugin deploys Traefik and integrates it with WindFlow so you can assign domains to your services from the UI.

**Extension plugins** detect running services and add management capabilities. For example, the PostgreSQL plugin detects any running `postgres` container and lets you create databases, users, and grants directly from the WindFlow UI.

**Hybrid plugins** do both — they deploy a service AND extend the core.

### Plugin Manifest (example)

```yaml
name: traefik
version: 1.0.0
type: hybrid
display_name: "Traefik - Reverse Proxy"
description: "Reverse proxy with automatic TLS via Let's Encrypt"
category: access

architectures:
  - linux/amd64
  - linux/arm64

resources:
  ram_min_mb: 128
  cpu_min_cores: 0.5

provides:
  - reverse_proxy
  - tls_certificates

config:
  - key: acme_email
    label: "Email for Let's Encrypt"
    type: string
    required: true
```

## 🧩 Resource Profiles

WindFlow adapts to your hardware. The core is designed to run light, and plugins add resource consumption only when installed.

| Profile | RAM | CPU | Storage | Example Hardware |
|---------|-----|-----|---------|------------------|
| **Light** (core only, SQLite) | 512 MB | 1 ARM core | 2 GB | Raspberry Pi 4 (2 GB) |
| **Standard** (core + PostgreSQL + Redis) | 1.5 GB | 2 cores | 5 GB | Raspberry Pi 4 (4 GB), mini PC |
| **Full** (core + 5-10 plugins) | 4 GB | 4 cores | 20 GB | NUC, dedicated server |

## 🚀 Quick Start

### Prerequisites

* **Docker** ≥ 20.10 and docker-compose v2
* **Linux** (Debian/Ubuntu, Raspberry Pi OS, or similar)
* **Architecture:** x86_64 or ARM64

### Install (standard mode)

```bash
# Clone the repository
git clone https://gitea.yourdomain.com/yourusername/windflow.git
cd windflow

# Copy environment files
cp .env.example .env

# Start WindFlow
docker compose up --build -d
```

### Install (light mode — Raspberry Pi)

```bash
# Light mode: SQLite instead of PostgreSQL, no Redis
./scripts/install.sh --light
```

**Access:**

* **Web Interface:** [http://localhost:8080](http://localhost:8080)
* **API Documentation:** [http://localhost:8080/api/docs](http://localhost:8080/api/docs)
* **CLI:** `docker exec -it windflow-cli windflow --help`

### Install your first plugin

Once WindFlow is running, open the web UI and go to **Marketplace**. Install the **Traefik** plugin to get a reverse proxy with automatic TLS, then deploy your first stack and assign it a domain — all from the interface.

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

**Dev prerequisites:** Python ≥ 3.11 + Poetry ≥ 1.8, Node.js ≥ 20 + pnpm ≥ 9

## 🔧 Configuration

### Core Environment Variables

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

# Database (standard mode)
DATABASE_URL=postgresql+asyncpg://windflow:password@localhost:5432/windflow
# Database (light mode — Raspberry Pi)
# DATABASE_URL=sqlite+aiosqlite:///data/windflow.db

# Cache (standard mode)
REDIS_URL=redis://localhost:6379/0
# Cache (light mode — disabled, uses in-memory)
# REDIS_URL=

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Logging
LOG_LEVEL=INFO
```

Plugin-specific configuration (reverse proxy, monitoring, AI, etc.) is managed through each plugin's settings in the UI — not in the core `.env` file.

## 📖 Documentation

The complete documentation is in the `doc/` directory:

### Main Documentation

* **[Overview](doc/general_specs/01-overview.md)** — Project vision and goals
* **[Architecture](doc/general_specs/02-architecture.md)** — Design principles
* **[Modular Architecture](doc/ARCHITECTURE-MODULAIRE.md)** — Plugin system and extensions
* **[Technology Stack](doc/general_specs/03-technology-stack.md)** — Technologies used
* **[Deployment Guide](doc/general_specs/15-deployment-guide.md)** — Installation and configuration

### User Guides

* **[Core Features](doc/general_specs/10-core-features.md)** — Detailed features
* **[CLI Interface](doc/general_specs/08-cli-interface.md)** — Using the CLI/TUI
* **[Plugin Development](doc/general_specs/plugin-development.md)** — Creating plugins

### Developer Resources

* **[Data Model](doc/general_specs/04-data-model.md)** — Data structure
* **[API Design](doc/general_specs/07-api-design.md)** — API documentation
* **[Workflows](doc/workflows/README.md)** — Development processes
* **[Development Rules](.clinerules/README.md)** — Standards and conventions

## 📊 Roadmap

### Version 1.0 (March 2026) — Core Platform ✅

* [x] Web UI (Vue.js 3 + TypeScript + Element Plus)
* [x] REST API (FastAPI + SQLAlchemy async)
* [x] CLI/TUI (Rich + Typer + Textual)
* [x] Docker containers + Docker Compose orchestration
* [x] Auth JWT + RBAC + Organizations
* [x] Stacks with versioning + Jinja2 templates
* [x] Interactive WebSocket terminal
* [x] Deployment pipeline with real-time logs
* [x] Targets CRUD + auto-discovery

### Version 1.1 (Q2 2026) — Plugin System & VMs

* [ ] Plugin manager (install, update, remove from UI/CLI)
* [ ] Plugin marketplace with one-click install
* [ ] Light mode for Raspberry Pi (SQLite, no Redis)
* [ ] Multi-arch builds (ARM64 + x86_64)
* [ ] KVM/QEMU VM management via libvirt
* [ ] Proxmox VE integration
* [ ] Volume browser UI
* [ ] Docker networks with environment isolation
* [ ] First plugins: Traefik, PostgreSQL, Redis, Uptime Kuma

### Version 1.2 (Q3 2026) — Plugin Catalog & Multi-Target

* [ ] Multi-target: manage remote machines via SSH
* [ ] Kubernetes support (optional, Helm charts)
* [ ] 15+ plugins: DNS, backup, monitoring, databases, messaging, storage, security
* [ ] 10+ one-click stack templates (Nextcloud, Gitea, Jellyfin, Home Assistant…)

### Version 1.3 (Q4 2026) — Security, Git & Polish

* [ ] Secrets encryption (AES-256-GCM)
* [ ] Git integration with auto-deploy on push
* [ ] Vulnerability scanning plugin (Trivy)
* [ ] SSO plugin (Keycloak)
* [ ] Audit trail
* [ ] Mail plugin (Mailu/Stalwart)
* [ ] Onboarding wizard and i18n (FR/EN)

### Version 2.0 (H1 2027) — Automation & Intelligence

* [ ] Workflow engine plugin (n8n / Node-RED)
* [ ] AI plugins (Ollama, LiteLLM) — config generation, diagnostics
* [ ] Auto-updates with rollback
* [ ] Plugin SDK for community contributions

### Beyond (2027+)

* [ ] Multi-instance federation
* [ ] Mobile app
* [ ] Community plugin marketplace with reviews
* [ ] Lightweight PaaS (git push → deploy)

See the **[Full Roadmap](doc/general_specs/18-roadmap.md)** for detailed phases, priorities, and success criteria.

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

### Creating Plugins

Plugins are the best way to contribute to WindFlow. Check the **[Plugin Development Guide](doc/general_specs/plugin-development.md)** to get started.

### Local Development

```bash
# Full setup
make setup

# Pre-commit tests
make test
make lint

# Conventional commit
git commit -m "feat(api): add plugin lifecycle hooks"
```

## 📄 License

WindFlow is released under the **MIT** license. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgements

WindFlow is built on exceptional open-source technologies:

* **[FastAPI](https://fastapi.tiangolo.com/)** — Modern web framework for Python
* **[Vue.js](https://vuejs.org/)** — Progressive framework for user interfaces
* **[Element Plus](https://element-plus.org/)** — Component library for Vue 3
* **[Rich](https://rich.readthedocs.io/)** — Library for rich CLI interfaces
* **[Docker](https://www.docker.com/)** — Containerization platform
* **[libvirt](https://libvirt.org/)** — Virtualization API
* **[Proxmox](https://www.proxmox.com/)** — Virtualization platform
* **[PostgreSQL](https://www.postgresql.org/)** — Relational database
* **[SQLite](https://www.sqlite.org/)** — Lightweight embedded database

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
