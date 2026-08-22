# Chapitre 05 — Stack technologique

> **Statut** : Spec cible · **Public** : Développeurs backend/frontend, contributeurs · **Lié à** : [04-architecture.md](04-architecture.md), [11-plugins.md](11-plugins.md), [../technical_specs/CI-CD-GUIDE.md](../technical_specs/CI-CD-GUIDE.md)

## Vue d'ensemble

Ce chapitre décrit les choix technologiques de WindFlow : critères de sélection, stack backend, frontend, CLI/TUI, backends de virtualisation, outils de développement et CI. C'est un chapitre de choix et de justifications ; l'architecture des modules (chapitre 04), le système de plugins (chapitre 11) et le format du registre (chapitre 12) sont spécifiés ailleurs. Les extraits de code sont illustratifs — le détail d'implémentation vit dans [`../technical_specs/`](../technical_specs).

## Critères de sélection

- **Légèreté** : chaque dépendance core doit justifier son empreinte mémoire. Sur un RPi avec 2 Go de RAM, chaque Mo compte.
- **Multi-arch** : les technologies choisies doivent supporter ARM64 et x86_64 nativement.
- **Maturité** : technologies éprouvées avec une communauté active. Pas d'expérimentation dans le core.
- **Optionalité** : quand une dépendance n'est pas indispensable (Redis, PostgreSQL), elle doit avoir un fallback léger (cache mémoire, SQLite).

## Stack core vs stack plugins

Le tableau de frontière core/plugins est la **référence unique** au chapitre [04-architecture.md](04-architecture.md). Vue par les dépendances :

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
| **VMs** | libvirt (Python), LXD/Incus (API) | — |
| **Reverse proxy** | — | Traefik, Caddy (plugins) |
| **DNS** | — | Pi-hole, CoreDNS (plugins) |
| **Monitoring** | — | Uptime Kuma, Netdata, Prometheus (plugins) |
| **Secrets avancés** | — | HashiCorp Vault (plugin) |
| **SSO** | — | Keycloak (plugin) |
| **IA** | — | Ollama, LiteLLM (plugins) |

## Backend

### FastAPI (Python 3.11+)

Framework principal de l'API REST. Choisi pour :

- ses performances async comparables à Node.js et Go ;
- la documentation OpenAPI/Swagger générée automatiquement ;
- la validation Pydantic (utilisée aussi pour les schémas de configuration des plugins) ;
- le typage complet avec mypy ;
- l'écosystème Python riche pour Docker SDK, libvirt, SSH (paramiko/asyncssh).

Exemple illustratif — configuration de l'application :

```python
app = FastAPI(
    title="WindFlow API",
    description="Gestionnaire d'infrastructure self-hosted",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
```

### Base de données : PostgreSQL ou SQLite

WindFlow supporte deux backends selon le profil de déploiement (chapitre 04) :

- **Mode standard — PostgreSQL 15+** : pour les machines avec suffisamment de RAM (≥ 4 Go). Tourne comme un container géré par WindFlow.
- **Mode léger — SQLite** : pour Raspberry Pi et machines contraintes. Pas de service séparé, la base est un fichier local (~100-200 Mo de RAM économisés vs container PostgreSQL).

L'ORM est le même pour les deux backends ; les migrations Alembic sont compatibles PostgreSQL et SQLite (règles de compatibilité au chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)).

Exemple illustratif — configuration adaptative :

```python
# windflow/config.py
DB_MODE = os.getenv("WINDFLOW_DB_MODE", "standard")  # "standard" ou "light"

if DB_MODE == "light":
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/windflow.db")
    REDIS_URL = None  # Pas de Redis en mode léger
else:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://windflow:password@postgres:5432/windflow",
    )
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
```

### Cache : Redis ou mémoire

- **Mode standard** : Redis 7+ sert de cache, de store de sessions et de broker pour Celery. Une instance unique suffit — pas de cluster.
- **Mode léger** : un cache dict en mémoire avec TTL remplace Redis, avec la même interface pour le code applicatif. Les sessions sont stockées en base ; Celery utilise le filesystem comme broker.

Exemple illustratif — cache mémoire :

```python
from windflow.cache import MemoryCache

# Interface identique à Redis pour le code applicatif
cache = MemoryCache(default_ttl=900)  # 15 minutes
await cache.set("key", "value")
value = await cache.get("key")
```

### Traitement asynchrone — Celery

Les opérations longues (déploiement de stacks, pull d'images, snapshots de Machines, installation de plugins) sont traitées par un ou plusieurs workers Celery. En mode léger sur un seul core ARM, la concurrence est réduite à 1 worker.

### Chiffrement des secrets (core)

Le core chiffre les secrets (mots de passe, tokens, clés SSH) en AES-256 via Fernet, avec clé dérivée du `SECRET_KEY`. Le `SecretManager` est spécifié au chapitre [15-securite.md](15-securite.md) — une seule version, salt `windflow-secrets-v1`. Pour une gestion avancée (rotation, secrets dynamiques), le plugin Vault est disponible.

## Frontend

### Vue.js 3 + TypeScript + Composition API

SPA (Single Page Application) avec TypeScript et la Composition API. Les composables encapsulent les appels API par domaine.

Exemple illustratif — composable de listing :

```typescript
export function useApps() {
  const apps = ref<App[]>([])
  const loading = ref(false)

  const fetchApps = async (hostId?: string) => {
    loading.value = true
    try {
      const params = hostId ? { host_id: hostId } : {}
      apps.value = (await api.get('/apps', { params })).data
    } finally {
      loading.value = false
    }
  }

  return { apps, loading, fetchApps }
}
```

### Element Plus + UnoCSS

Element Plus fournit les composants UI (tables, formulaires, dialogs, menus) ; UnoCSS les classes utilitaires pour le layout. Le design system détaillé (typographie, palettes, composants) est spécifié au chapitre [13-ui-principes.md](13-ui-principes.md) et dans [../technical_specs/DESIGN-SYSTEM.md](../technical_specs/DESIGN-SYSTEM.md).

### Pinia + Vue Router

Pinia gère l'état global (authentification, session, préférences), un store par domaine fonctionnel. Vue Router gère les routes protégées par rôle avec lazy loading, y compris les routes injectées dynamiquement par les plugins (chapitre 11).

### Vue Flow + dagre — vues graphe et flow

Les vues graphe — **Graphe de dépendances** et **Éditeur de composition** (chapitre [14-ui-maquettes.md](14-ui-maquettes.md), Écrans 20 et 21) — reposent sur **Vue Flow** : `@vue-flow/core` et les plugins officiels `@vue-flow/background`, `@vue-flow/controls`, `@vue-flow/minimap`. **`@dagrejs/dagre`** complète la stack pour le layout automatique (placement des nœuds) des graphes en lecture seule. Choix retenu pour :

- un rendu **natif Vue 3 + TypeScript** (Composition API, aucun wrapper) ;
- les **plugins officiels** Background, Controls (zoom/pan) et MiniMap (vue d'ensemble) ;
- la **sérialisation** `toObject()` / `fromObject()`, alignée sur le contrat `nodes`/`edges` de l'API graphe (chapitre [09-api.md](09-api.md)) ;
- le hook **`isValidConnection`** pour imposer les contraintes de connexion à la volée (pas d'auto-boucle, pas de cycle).

Alternatives écartées : **Rete.js** et **AntV X6** — complexité et couche d'abstraction supplémentaires, intégration Vue non native.

### Injection de composants plugin

Les plugins injectent pages et widgets dans l'UI sans modifier le code core : le Plugin Manager charge dynamiquement les composants des plugins installés, chaque plugin déclarant ses pages et widgets dans son manifest (chapitre [11-plugins.md](11-plugins.md)).

## CLI / TUI

- **CLI — Rich + Typer** : interface en ligne de commande pour l'automatisation et les scripts (chapitre [10-cli-tui.md](10-cli-tui.md)).
- **TUI — Textual** : interface terminal interactive pour la gestion quotidienne, utilisable via SSH sur des machines sans interface graphique.

Exemple illustratif — esprit de la CLI :

```python
@app.command()
def apps(host: str = typer.Option("local", help="Host cible")):
    """Lister les Apps."""
    data = api_client.get(f"/apps?host_id={host}")
    table = Table(title="Apps")
    table.add_column("Nom", style="cyan")
    table.add_column("Statut", style="green")
    for a in data:
        table.add_row(a["name"], a["status"])
    console.print(table)
```

## Backends de virtualisation

La gestion des Machines et des Hosts repose sur les **WorkloadAdapter** du chapitre [02-familles-workloads.md](02-familles-workloads.md) — pas sur des services de VM monolithiques :

- **KVM/QEMU via libvirt** : bibliothèque Python `libvirt`, connexion locale (`qemu:///system`) ou distante via SSH (`qemu+ssh://user@host/system`).
- **LXD / Incus** : API REST native de chaque outil, pour les VMs et les system containers.
- **VirtualBox** : support optionnel via VBoxManage pour les environnements de test.
- **Proxmox VE** : consommé via l'API REST du Host `host_proxmox` (`ProxmoxHostAdapter`) — les VMs Proxmox sont des Machines standard. Il n'y a **pas** de `ProxmoxService` dans le core.
- **Kubernetes** : client kubeconfig via le Host `host_kubernetes`, pour les Apps `helm_release` et `k8s_manifest`.

Exemple illustratif — listing libvirt derrière `KVMAdapter` :

```python
class KVMAdapter(MachineAdapter):
    """Profil vm_kvm — VMs KVM/QEMU via libvirt."""

    def __init__(self, uri: str = "qemu:///system"):
        self.conn = libvirt.open(uri)

    def list_machines(self):
        return [
            {"name": d.name(), "uuid": d.UUIDString(), "state": d.state()[0]}
            for d in self.conn.listAllDomains()
        ]
```

La taxonomie complète des moteurs et services Engine est décrite dans [../technical_specs/VIRTUALIZATION-SYSTEMS.md](../technical_specs/VIRTUALIZATION-SYSTEMS.md).

### Containers — Docker SDK

Le core utilise le Docker SDK Python pour le daemon local ou distant. Pour les machines distantes, WindFlow utilise un contexte SSH (`ssh://deploy@192.168.1.50`) — l'API Docker n'est jamais exposée sur le réseau (chapitre [15-securite.md](15-securite.md)).

## Outils de développement

### Tests et qualité

- **Tests** : pytest avec marqueurs async (`pytest.mark.asyncio`), tests API via `httpx.AsyncClient`. Couverture cible > 85 % (chapitre [01-vision.md](01-vision.md)).
- **Linting et formatage** : ruff (remplace flake8 + isort) et ruff-format via pre-commit.
- **Typage** : mypy avec les stubs pydantic et sqlalchemy.
- **Frontend** : Vitest pour les tests unitaires, ESLint pour le lint.

### CI multi-arch — Gitea Actions

Le CI build et teste sur les deux architectures pour garantir la compatibilité ARM. Le projet utilise **Gitea Actions** (répertoire `.gitea/workflows/`) — pas GitHub Actions.

Exemple illustratif — matrice multi-arch du workflow CI :

```yaml
jobs:
  test:
    strategy:
      matrix:
        arch: [amd64, arm64]
    runs-on: ${{ matrix.arch == 'arm64' && 'ubuntu-latest-arm64' || 'ubuntu-latest' }}
    steps:
      - uses: actions/checkout@v4
      - run: poetry install
      - run: poetry run pytest
```

Le détail des pipelines (lint, tests, build des images multi-arch, publication) est spécifié dans [../technical_specs/CI-CD-GUIDE.md](../technical_specs/CI-CD-GUIDE.md).

## Récapitulatif des dépendances

### Core — dépendances Python

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
| `httpx` | Client HTTP async | Oui |
| `paramiko` / `asyncssh` | Connexions SSH | Oui |
| `pydantic` | Validation + schémas plugin | Oui |
| `python-jose` | JWT tokens | Oui |
| `cryptography` | Chiffrement secrets | Oui |
| `jinja2` | Templates stacks | Oui |
| `pyyaml` | Parsing manifests plugins | Oui |
| `rich` / `typer` / `textual` | CLI et TUI | Oui |

### Core — dépendances frontend (npm)

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
| `@vue-flow/core` (+ `background`, `controls`, `minimap`) | Vues graphe/flow — Graphe de dépendances, Éditeur de composition |
| `@dagrejs/dagre` | Layout automatique des graphes |

### Services Docker (core)

| Service | Mode standard | Mode léger | Image |
|---------|---------------|------------|-------|
| WindFlow API | Oui | Oui | `windflow/api` (multi-arch) |
| Celery Worker | Oui | Oui (1 process) | `windflow/worker` (multi-arch) |
| PostgreSQL | Oui | Non (SQLite) | `postgres:15` (multi-arch) |
| Redis | Oui | Non (cache mémoire) | `redis:7-alpine` (multi-arch) |
| Frontend (Nginx) | Oui | Oui | `windflow/frontend` (multi-arch) |

## Correspondance spec ↔ technical_specs

| Sujet de ce chapitre | Spécification technique détaillée |
|---|---|
| Architecture modulaire, plugins | [../technical_specs/ARCHITECTURE-MODULAIRE.md](../technical_specs/ARCHITECTURE-MODULAIRE.md) |
| Moteurs de virtualisation, services Engine | [../technical_specs/VIRTUALIZATION-SYSTEMS.md](../technical_specs/VIRTUALIZATION-SYSTEMS.md) |
| Design system, composants frontend | [../technical_specs/DESIGN-SYSTEM.md](../technical_specs/DESIGN-SYSTEM.md) |
| Formulaires dynamiques (schémas de config) | [../technical_specs/DYNAMIC-FORMS.md](../technical_specs/DYNAMIC-FORMS.md) |
| Templates de stacks, fonctions Jinja2 | [../technical_specs/STACK-DEFINITIONS.md](../technical_specs/STACK-DEFINITIONS.md), [../technical_specs/JINJA2-FUNCTIONS.md](../technical_specs/JINJA2-FUNCTIONS.md) |
| Pipelines CI/CD | [../technical_specs/CI-CD-GUIDE.md](../technical_specs/CI-CD-GUIDE.md) |

## Voir aussi

- [04-architecture.md](04-architecture.md) — architecture des modules et profils de déploiement
- [02-familles-workloads.md](02-familles-workloads.md) — interface WorkloadAdapter implémentée avec ces technologies
- [11-plugins.md](11-plugins.md) — Plugin Manager et chargement dynamique
- [06-modele-de-donnees.md](06-modele-de-donnees.md) — ORM et compatibilité PostgreSQL/SQLite
- [../technical_specs/CI-CD-GUIDE.md](../technical_specs/CI-CD-GUIDE.md) — pipelines Gitea Actions détaillés
