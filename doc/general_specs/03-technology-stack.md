# Stack Technologique - WindFlow

## Vue d'Ensemble

Le stack technologique de WindFlow est guidé par trois contraintes : tourner sur du matériel modeste (Raspberry Pi), rester simple à déployer et maintenir, et permettre l'extension par plugins sans alourdir le core.

### Critères de Sélection

- **Légèreté** : Chaque dépendance core doit justifier son empreinte mémoire. Sur un RPi avec 2 Go de RAM, chaque Mo compte.
- **Multi-arch** : Les technologies choisies doivent supporter ARM64 et x86_64 nativement.
- **Maturité** : Technologies éprouvées avec une communauté active. Pas d'expérimentation dans le core.
- **Optionalité** : Quand une dépendance n'est pas indispensable (Redis, PostgreSQL), elle doit avoir un fallback léger (cache mémoire, SQLite).

### Stack Core vs Stack Plugins

Le core de WindFlow a un nombre limité et fixe de dépendances. Tout le reste est apporté par les plugins.

| | Core | Plugins (exemples) |
|---|------|---------------------|
| **Backend** | FastAPI, Python 3.11+ | — |
| **ORM** | SQLAlchemy 2.0 + Alembic | — |
| **Base de données** | PostgreSQL 15+ **ou** SQLite | — |
| **Cache / Broker** | Redis 7+ **ou** cache mémoire | — |
| **Task queue** | Celery | — |
| **Frontend** | Vue.js 3, TypeScript, Element Plus, UnoCSS | Composants UI injectés par les plugins |
| **CLI/TUI** | Rich, Typer, Textual | — |
| **Containers** | Docker SDK Python, Docker Compose | — |
| **VMs** | libvirt (Python), API Proxmox | — |
| **Reverse Proxy** | — | Traefik, Caddy (plugins) |
| **DNS** | — | Pi-hole, CoreDNS (plugins) |
| **Monitoring** | — | Uptime Kuma, Netdata, Prometheus (plugins) |
| **Secrets avancés** | — | HashiCorp Vault (plugin) |
| **SSO** | — | Keycloak (plugin) |
| **Logging centralisé** | — | Loki, ELK (plugins) |
| **IA** | — | Ollama, LiteLLM (plugins) |

---

## Backend

### FastAPI (Python 3.11+)

Framework principal de l'API REST. Choisi pour ses performances async, la documentation OpenAPI automatique, et la validation Pydantic.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="WindFlow API",
    description="Gestionnaire d'infrastructure self-hosted",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restreint en production via config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Pourquoi FastAPI :**
- Performances async comparables à Node.js et Go
- Documentation OpenAPI/Swagger générée automatiquement
- Validation des données avec Pydantic (utilisé aussi pour les schémas de config des plugins)
- Typage complet avec mypy
- Écosystème Python riche pour Docker SDK, libvirt, SSH (Paramiko/asyncssh)

### Base de Données : PostgreSQL ou SQLite

WindFlow supporte deux backends de base de données selon le profil de déploiement.

**Mode Standard — PostgreSQL 15+**

Pour les installations sur machines avec suffisamment de RAM (≥ 4 Go). PostgreSQL tourne comme un container Docker géré par WindFlow.

```python
# Mode standard
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://windflow:password@localhost:5432/windflow",
    pool_size=10,
    max_overflow=20,
)
```

**Mode Léger — SQLite**

Pour Raspberry Pi et machines contraintes. Pas de service séparé, la base est un fichier local. Supprime le besoin d'un container PostgreSQL (~100-200 Mo de RAM économisés).

```python
# Mode léger
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "sqlite+aiosqlite:///data/windflow.db",
    connect_args={"check_same_thread": False},
)
```

**ORM — SQLAlchemy 2.0 + Alembic**

L'ORM est le même pour les deux backends. Les migrations Alembic sont compatibles PostgreSQL et SQLite.

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, JSON
from uuid import UUID, uuid4
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Target(Base):
    __tablename__ = "targets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), index=True)
    type: Mapped[str] = mapped_column(String(20))  # local, ssh, proxmox
    host: Mapped[str] = mapped_column(String(255), nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**Configuration adaptative :**

```python
# windflow/config.py
import os

DB_MODE = os.getenv("WINDFLOW_DB_MODE", "standard")  # "standard" ou "light"

if DB_MODE == "light":
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/windflow.db")
    REDIS_URL = None  # Pas de Redis en mode léger
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://windflow:password@postgres:5432/windflow")
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
```

### Cache : Redis ou Mémoire

**Mode Standard — Redis 7+ (instance simple)**

Redis sert de cache, de store de sessions, et de broker pour Celery. Une instance unique suffit — pas de cluster.

```python
import redis.asyncio as redis

redis_client = redis.from_url(
    "redis://redis:6379/0",
    decode_responses=True,
)
```

**Mode Léger — Cache en mémoire**

En mode léger, un cache dict en mémoire avec TTL remplace Redis. Les sessions sont stockées en base. Celery utilise le filesystem comme broker au lieu de Redis.

```python
from windflow.cache import MemoryCache

# Interface identique à Redis pour le code applicatif
cache = MemoryCache(default_ttl=900)  # 15 minutes
await cache.set("key", "value")
value = await cache.get("key")
```

### Traitement Asynchrone — Celery

Les opérations longues (déploiement de stacks, pull d'images, snapshots VM, installation de plugins) sont traitées par un ou plusieurs workers Celery.

```python
from celery import Celery

celery_app = Celery("windflow")

celery_app.conf.update(
    # Broker : Redis en standard, filesystem en léger
    broker_url=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "2")),  # 1 sur RPi
    task_routes={
        "windflow.tasks.deployment.*": {"queue": "default"},
        "windflow.tasks.plugins.*": {"queue": "default"},
    },
)
```

En mode léger avec un seul core ARM, la concurrence est réduite à 1 worker.

### Gestion des Secrets (core)

Le core gère les secrets (mots de passe, tokens, clés SSH) avec un chiffrement AES-256-GCM. Pas de dépendance externe — le chiffrement est natif.

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class SecretManager:
    """Chiffrement des secrets en base avec clé dérivée du SECRET_KEY."""

    def __init__(self, master_key: str):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"windflow-secrets",  # Salt fixe par instance
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

Pour une gestion avancée des secrets (rotation dynamique, secrets par service, audit), le plugin Vault est disponible.

---

## Frontend

### Vue.js 3 + TypeScript + Composition API

Le frontend est une SPA (Single Page Application) Vue.js 3 avec TypeScript et la Composition API.

```typescript
// Composable pour la gestion des containers
import { ref, computed } from 'vue'
import type { Container } from '@/types'

export function useContainers() {
  const containers = ref<Container[]>([])
  const loading = ref(false)

  const runningContainers = computed(() =>
    containers.value.filter(c => c.status === 'running')
  )

  const fetchContainers = async (targetId?: string) => {
    loading.value = true
    try {
      const params = targetId ? { target_id: targetId } : {}
      const response = await api.get('/containers', { params })
      containers.value = response.data
    } finally {
      loading.value = false
    }
  }

  return { containers, loading, runningContainers, fetchContainers }
}
```

### Element Plus + UnoCSS

Element Plus fournit les composants UI (tables, formulaires, dialogs, menus). UnoCSS fournit les classes utilitaires pour le layout et les ajustements.

```vue
<template>
  <el-container class="min-h-screen">
    <el-aside width="220px">
      <side-menu />
    </el-aside>
    <el-container>
      <el-header>
        <nav-bar />
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
```

### State Management — Pinia

Pinia gère l'état global (authentification, session, préférences). Chaque store correspond à un domaine fonctionnel.

```typescript
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref('')

  const isAuthenticated = computed(() => !!token.value && !!user.value)

  const login = async (credentials: LoginCredentials) => {
    const response = await authApi.login(credentials)
    user.value = response.user
    token.value = response.token
  }

  return { user, token, isAuthenticated, login }
})
```

### Routing — Vue Router

Routes protégées par rôle avec lazy loading des pages.

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/pages/LoginPage.vue') },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', component: () => import('@/pages/DashboardPage.vue') },
        { path: 'containers', component: () => import('@/pages/ContainersPage.vue') },
        { path: 'vms', component: () => import('@/pages/VMsPage.vue') },
        { path: 'stacks', component: () => import('@/pages/StacksPage.vue') },
        { path: 'marketplace', component: () => import('@/pages/MarketplacePage.vue') },
        { path: 'plugins', component: () => import('@/pages/PluginsPage.vue') },
        { path: 'targets', component: () => import('@/pages/TargetsPage.vue') },
      ],
    },
  ],
})
```

### Injection de Composants Plugin

Les plugins peuvent injecter des pages et des widgets dans l'UI sans modifier le code core. Le système de plugin UI fonctionne par convention :

```typescript
// Le Plugin Manager charge dynamiquement les composants des plugins installés
// Chaque plugin déclare ses pages et widgets dans son manifest

// Exemple : le plugin Traefik ajoute une page "Domains" dans le menu
{
  "ui_routes": [
    { "path": "plugins/traefik/domains", "label": "Domaines & Routage", "icon": "globe" }
  ],
  "ui_widgets": [
    { "id": "traefik-status", "position": "dashboard", "component": "TraefikStatusWidget" }
  ]
}
```

---

## CLI / TUI

### CLI — Rich + Typer

Interface en ligne de commande pour l'automatisation et les scripts.

```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="WindFlow CLI — Gestionnaire d'infrastructure self-hosted")
console = Console()

@app.command()
def containers(target: str = typer.Option("local", help="Machine cible")):
    """Lister les containers."""
    data = api_client.get(f"/containers?target={target}")
    table = Table(title="Containers")
    table.add_column("Nom", style="cyan")
    table.add_column("Image")
    table.add_column("Statut", style="green")
    for c in data:
        table.add_row(c["name"], c["image"], c["status"])
    console.print(table)

@app.command()
def deploy(stack: str = typer.Argument(..., help="Nom du stack")):
    """Déployer un stack."""
    result = api_client.post(f"/stacks/{stack}/deploy")
    console.print(f"[green]Déploiement lancé : {result['deployment_id']}")
```

### TUI — Textual

Interface terminal interactive pour la gestion quotidienne.

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Static

class WindFlowTUI(App):
    """Interface TUI de WindFlow."""

    BINDINGS = [
        ("c", "show_containers", "Containers"),
        ("v", "show_vms", "VMs"),
        ("s", "show_stacks", "Stacks"),
        ("q", "quit", "Quitter"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Vertical(
                Static("Containers", classes="panel-title"),
                DataTable(id="containers"),
            ),
            Vertical(
                Static("VMs", classes="panel-title"),
                DataTable(id="vms"),
            ),
        )
        yield Footer()
```

---

## Gestion des Containers — Docker

### Docker SDK Python

Le core utilise le Docker SDK Python pour communiquer avec le Docker Engine local ou distant.

```python
import docker

class DockerService:
    def __init__(self, base_url: str = "unix:///var/run/docker.sock"):
        self.client = docker.DockerClient(base_url=base_url)

    def list_containers(self, all: bool = False):
        return self.client.containers.list(all=all)

    def deploy_compose(self, project_name: str, compose_content: str, env: dict = None):
        """Déploie une stack Docker Compose."""
        # Utilise docker compose via subprocess pour la compatibilité
        # Le SDK Python ne supporte pas nativement compose v2
        ...

    def get_logs(self, container_id: str, tail: int = 100):
        container = self.client.containers.get(container_id)
        return container.logs(tail=tail, timestamps=True).decode()

    def exec_in_container(self, container_id: str, command: str):
        container = self.client.containers.get(container_id)
        return container.exec_run(command, stream=True)
```

**Docker distant via SSH** : Pour les machines distantes, WindFlow utilise le Docker SDK avec un contexte SSH (`ssh://user@host`). Pas besoin d'exposer le Docker API sur le réseau.

```python
# Connexion Docker sur machine distante
remote_client = docker.DockerClient(
    base_url="ssh://deploy@192.168.1.50",
    use_ssh_client=True,
)
```

---

## Gestion des VMs

### libvirt (KVM/QEMU)

Pour les machines avec un hyperviseur KVM, WindFlow utilise la bibliothèque Python `libvirt` pour piloter les VMs.

```python
import libvirt

class LibvirtService:
    def __init__(self, uri: str = "qemu:///system"):
        self.conn = libvirt.open(uri)

    def list_vms(self):
        domains = self.conn.listAllDomains()
        return [
            {
                "name": d.name(),
                "uuid": d.UUIDString(),
                "state": d.state()[0],
                "vcpus": d.maxVcpus(),
                "memory_mb": d.maxMemory() // 1024,
            }
            for d in domains
        ]

    def create_vm(self, name: str, vcpus: int, memory_mb: int, disk_path: str, iso_path: str = None):
        """Crée une VM KVM avec les paramètres donnés."""
        xml_config = self._generate_domain_xml(name, vcpus, memory_mb, disk_path, iso_path)
        domain = self.conn.defineXML(xml_config)
        domain.create()
        return domain.UUIDString()

    def snapshot(self, vm_name: str, snapshot_name: str):
        domain = self.conn.lookupByName(vm_name)
        xml = f"<domainsnapshot><name>{snapshot_name}</name></domainsnapshot>"
        domain.snapshotCreateXML(xml)
```

**Connexion distante** : libvirt supporte nativement les connexions via SSH.

```python
# KVM sur machine distante
remote_conn = libvirt.open("qemu+ssh://user@192.168.1.50/system")
```

### Proxmox VE (API REST)

Pour les installations Proxmox, WindFlow communique via l'API REST Proxmox.

```python
import httpx

class ProxmoxService:
    def __init__(self, host: str, user: str, token_name: str, token_value: str):
        self.base_url = f"https://{host}:8006/api2/json"
        self.headers = {
            "Authorization": f"PVEAPIToken={user}!{token_name}={token_value}"
        }
        self.http = httpx.AsyncClient(headers=self.headers, verify=False)

    async def list_vms(self, node: str):
        response = await self.http.get(f"{self.base_url}/nodes/{node}/qemu")
        return response.json()["data"]

    async def create_vm(self, node: str, vmid: int, config: dict):
        response = await self.http.post(
            f"{self.base_url}/nodes/{node}/qemu",
            data={"vmid": vmid, **config},
        )
        return response.json()

    async def snapshot(self, node: str, vmid: int, name: str):
        response = await self.http.post(
            f"{self.base_url}/nodes/{node}/qemu/{vmid}/snapshot",
            data={"snapname": name},
        )
        return response.json()
```

### VirtualBox (optionnel)

Support via VBoxWebSVC pour les environnements de développement. Moins prioritaire que KVM/Proxmox.

---

## Système de Plugins — Technologies

### Plugin Manager (Python)

Le Plugin Manager est un module core qui gère le cycle de vie des plugins. Il :
- Parse les manifests YAML (`windflow-plugin.yml`)
- Vérifie la compatibilité architecture et ressources
- Déploie les stacks Docker des service plugins
- Charge dynamiquement les modules Python des extension plugins
- Enregistre les routes API et composants UI des plugins

```python
import importlib
import yaml
from pathlib import Path

class PluginManager:
    def __init__(self, plugins_dir: Path, docker_service, db_session):
        self.plugins_dir = plugins_dir
        self.docker = docker_service
        self.db = db_session
        self.loaded_extensions = {}

    async def install_plugin(self, plugin_name: str, registry_url: str):
        """Installe un plugin depuis le registre."""
        # 1. Télécharger depuis le registre
        manifest, files = await self._download_from_registry(plugin_name, registry_url)

        # 2. Vérifier compatibilité
        self._check_architecture(manifest)
        self._check_resources(manifest)
        self._check_dependencies(manifest)

        # 3. Si service/hybrid : déployer la stack Docker
        if manifest["type"] in ("service", "hybrid"):
            await self.docker.deploy_compose(
                project_name=f"windflow-plugin-{plugin_name}",
                compose_content=files["docker-compose.yml"],
            )

        # 4. Si extension/hybrid : charger le module Python
        if manifest["type"] in ("extension", "hybrid"):
            module = importlib.import_module(f"plugins.{plugin_name}.extensions.api")
            self.loaded_extensions[plugin_name] = module

        # 5. Exécuter le hook on_install
        await self._run_hook(plugin_name, "on_install")

    def _check_architecture(self, manifest: dict):
        """Vérifie que le plugin supporte l'architecture courante."""
        import platform
        arch = "linux/arm64" if platform.machine() == "aarch64" else "linux/amd64"
        if arch not in manifest.get("architectures", []):
            raise IncompatibleArchError(f"Plugin ne supporte pas {arch}")
```

### Registre de Plugins

Le registre est un index JSON statique hébergeable n'importe où (GitHub Pages, serveur web, self-hosted). Pas de service complexe.

```json
{
  "plugins": [
    {
      "name": "traefik",
      "version": "1.0.0",
      "type": "hybrid",
      "category": "access",
      "architectures": ["linux/amd64", "linux/arm64"],
      "download_url": "https://plugins.windflow.io/traefik/1.0.0/traefik.tar.gz",
      "checksum": "sha256:abc123...",
      "resources": {"ram_min_mb": 128}
    },
    {
      "name": "postgresql-manager",
      "version": "1.0.0",
      "type": "extension",
      "category": "database",
      "architectures": ["linux/amd64", "linux/arm64"],
      "download_url": "https://plugins.windflow.io/postgresql-manager/1.0.0/postgresql-manager.tar.gz",
      "checksum": "sha256:def456...",
      "resources": {"ram_min_mb": 32}
    }
  ]
}
```

---

## Outils de Développement

### Tests — pytest

```python
import pytest
from httpx import AsyncClient
from windflow.main import app

@pytest.mark.asyncio
async def test_list_containers():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/containers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_install_plugin():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/plugins/install", json={
            "name": "traefik",
            "registry_url": "https://plugins.windflow.io/index.json",
        })
        assert response.status_code == 201
```

### Qualité de Code

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff          # Linting (remplace flake8 + isort)
      - id: ruff-format   # Formatting (remplace black)

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy]
```

### CI Multi-Arch

Le CI build et teste sur les deux architectures pour garantir la compatibilité ARM.

```yaml
# .github/workflows/ci.yml (extrait)
jobs:
  test:
    strategy:
      matrix:
        arch: [amd64, arm64]
    runs-on: ${{ matrix.arch == 'arm64' && 'self-hosted-arm64' || 'ubuntu-latest' }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install poetry && poetry install
      - run: poetry run pytest

  build-images:
    steps:
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v5
        with:
          platforms: linux/amd64,linux/arm64
          push: true
          tags: windflow/api:latest
```

---

## Récapitulatif des Dépendances

### Core — Dépendances Python

| Package | Usage | Obligatoire |
|---------|-------|-------------|
| `fastapi` | Framework API REST | Oui |
| `uvicorn` | Serveur ASGI | Oui |
| `sqlalchemy[asyncio]` | ORM | Oui |
| `alembic` | Migrations DB | Oui |
| `asyncpg` | Driver PostgreSQL async | Mode standard |
| `aiosqlite` | Driver SQLite async | Mode léger |
| `redis` | Client Redis async | Mode standard |
| `celery` | Task queue | Oui |
| `docker` | Docker SDK Python | Oui |
| `libvirt-python` | API libvirt (KVM) | Si KVM disponible |
| `httpx` | Client HTTP async (Proxmox API) | Oui |
| `paramiko` / `asyncssh` | Connexions SSH | Oui |
| `pydantic` | Validation données + schémas plugin | Oui |
| `python-jose` | JWT tokens | Oui |
| `cryptography` | Chiffrement secrets | Oui |
| `jinja2` | Templates stacks | Oui |
| `pyyaml` | Parsing manifests plugins | Oui |
| `rich` | CLI formatting | Oui |
| `typer` | CLI framework | Oui |
| `textual` | TUI framework | Oui |

### Core — Dépendances Frontend (npm)

| Package | Usage |
|---------|-------|
| `vue` (3.x) | Framework UI |
| `typescript` | Typage |
| `element-plus` | Composants UI |
| `unocss` | Utilitaires CSS |
| `pinia` | State management |
| `vue-router` | Routing |
| `axios` | Client HTTP |
| `xterm.js` | Terminal WebSocket |
| `@novnc/novnc` | Console VNC dans le navigateur |

### Services Docker (core)

| Service | Mode Standard | Mode Léger | Image |
|---------|---------------|------------|-------|
| WindFlow API | Oui | Oui | `windflow/api` (multi-arch) |
| Celery Worker | Oui | Oui (1 process) | `windflow/worker` (multi-arch) |
| PostgreSQL | Oui | Non (SQLite) | `postgres:15` (multi-arch) |
| Redis | Oui | Non (cache mémoire) | `redis:7-alpine` (multi-arch) |
| Frontend (Nginx) | Oui | Oui | `windflow/frontend` (multi-arch) |

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Vision du projet
- [Architecture](02-architecture.md) - Principes architecturaux et système de plugins
- [Modèle de Données](04-data-model.md) - Structure des données
- [API Design](07-api-design.md) - Conception des APIs
- [Guide de Déploiement](15-deployment-guide.md) - Installation et configuration
