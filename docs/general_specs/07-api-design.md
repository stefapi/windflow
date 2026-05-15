# Design de l'API - WindFlow

## Vue d'Ensemble

L'API WindFlow est une API REST construite avec FastAPI. Elle couvre les fonctionnalités du core (containers, VMs, stacks, targets, plugins, marketplace, auth, admin) et est étendue dynamiquement par les plugins installés.

### Principes

- **REST** : Conventions HTTP strictes (GET pour lire, POST pour créer, PUT pour modifier, DELETE pour supprimer)
- **OpenAPI 3.0** : Documentation automatique sur `/api/docs` (Swagger) et `/api/redoc`
- **Auth JWT** : Tous les endpoints (sauf `/auth/login` et `/health`) nécessitent un token Bearer
- **Pagination** : Toutes les listes sont paginées avec `?page=1&per_page=20`
- **JSON** : Entrée et sortie en JSON
- **Plugins** : Les plugins ajoutent des routes sous `/api/v1/plugins/{name}/` — elles apparaissent dans la documentation OpenAPI

---

## Structure des Endpoints

```
/api/v1/
├── auth/                          # Authentification (core)
├── containers/                    # Containers Docker (core)
├── vms/                           # Machines virtuelles (core)
├── stacks/                        # Stacks Docker Compose (core)
├── targets/                       # Machines cibles (core)
├── volumes/                       # Volumes Docker (core)
├── networks/                      # Networks Docker (core)
├── images/                        # Images Docker (core)
├── plugins/                       # Gestion des plugins (core)
├── marketplace/                   # Catalogue (core)
├── organizations/                 # Organisations (core)
├── environments/                  # Environnements (core)
├── admin/                         # Administration système (core)
├── system/                        # Health, info (core)
│
└── plugins/                       # Routes dynamiques (ajoutées par les plugins)
    ├── traefik/                   #   → domaines, routes, certificats
    ├── postgresql/                #   → databases, users, grants
    ├── ai/                        #   → generate, diagnose, chat
    └── ...
```

---

## Format de Réponse

### Réponse Standard

```json
{
    "data": { ... },
    "message": "Container created successfully"
}
```

### Réponse Liste (paginée)

```json
{
    "data": [ ... ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 87,
        "pages": 5
    }
}
```

### Réponse Erreur

```json
{
    "error": {
        "code": "NOT_FOUND",
        "message": "Container not found: abc123"
    }
}
```

### Modèles Pydantic

```python
from pydantic import BaseModel
from typing import Optional, List, Any

class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int

class APIResponse(BaseModel):
    data: Any = None
    message: Optional[str] = None

class PaginatedResponse(BaseModel):
    data: List[Any]
    pagination: PaginationMeta

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
```

---

## Endpoints Core

### Authentification — `/api/v1/auth/`

```
POST   /login                  # Login (username + password) → tokens
POST   /refresh                # Renouveler l'access token
POST   /logout                 # Invalider le refresh token
GET    /me                     # Infos utilisateur courant
PUT    /password               # Changer son mot de passe
POST   /api-keys               # Créer une API key
GET    /api-keys               # Lister ses API keys
DELETE /api-keys/{id}          # Révoquer une API key
```

Détails : voir [Authentification](05-authentication.md).

### Containers — `/api/v1/containers/`

```
GET    /                       # Lister les containers (filtres: target_id, status, name)
GET    /{id}                   # Détails d'un container
POST   /                       # Créer un container
POST   /{id}/start             # Démarrer
POST   /{id}/stop              # Arrêter
POST   /{id}/restart           # Redémarrer
DELETE /{id}                   # Supprimer
GET    /{id}/logs              # Logs (query: tail, since, timestamps)
GET    /{id}/stats             # Stats temps réel (CPU, RAM, réseau, I/O)
POST   /{id}/exec              # Exécuter une commande
```

**WebSocket :**
```
WS     /ws/terminal/{id}       # Terminal interactif (xterm.js)
WS     /ws/logs/{id}           # Streaming de logs
```

**Modèles :**

```python
class ContainerResponse(BaseModel):
    id: str
    name: str
    image: str
    status: str                # running, stopped, exited, created
    ports: list[dict]
    volumes: list[str]
    networks: list[str]
    created_at: str
    target_id: str

class ContainerCreateRequest(BaseModel):
    name: str
    image: str
    target_id: str
    ports: Optional[dict] = None           # {"8080/tcp": 8080}
    environment: Optional[dict] = None     # {"KEY": "value"}
    volumes: Optional[list[str]] = None    # ["vol:/data"]
    network: Optional[str] = None
    restart_policy: Optional[str] = "unless-stopped"
```

### Machines Virtuelles — `/api/v1/vms/`

```
GET    /                       # Lister les VMs (filtres: target_id, status, hypervisor)
GET    /{id}                   # Détails d'une VM
POST   /                       # Créer une VM
POST   /{id}/start             # Démarrer
POST   /{id}/stop              # Arrêter (graceful)
POST   /{id}/force-stop        # Forcer l'arrêt
POST   /{id}/restart           # Redémarrer
DELETE /{id}                   # Supprimer
POST   /{id}/snapshot          # Créer un snapshot
GET    /{id}/snapshots         # Lister les snapshots
POST   /{id}/snapshot/{name}/restore  # Restaurer un snapshot
DELETE /{id}/snapshot/{name}   # Supprimer un snapshot
```

**WebSocket :**
```
WS     /ws/console/{id}        # Console VNC/SPICE (noVNC)
```

**Modèles :**

```python
class VMCreateRequest(BaseModel):
    name: str
    target_id: str
    vcpus: int = 2
    memory_mb: int = 2048
    disk_size_gb: int = 20
    iso_path: Optional[str] = None
    cloud_init: Optional[dict] = None

class VMResponse(BaseModel):
    id: str
    name: str
    status: str               # running, stopped, paused, creating
    hypervisor: str            # kvm, LXD, Incus
    vcpus: int
    memory_mb: int
    disks: list[dict]
    target_id: str
```

### Stacks — `/api/v1/stacks/`

```
GET    /                       # Lister les stacks
GET    /{id}                   # Détails d'une stack (config, status, versions)
POST   /                       # Créer une stack
PUT    /{id}                   # Modifier une stack (crée une nouvelle version)
DELETE /{id}                   # Supprimer une stack
POST   /{id}/deploy            # Déployer
POST   /{id}/stop              # Arrêter tous les services
POST   /{id}/rollback          # Rollback à la version précédente
GET    /{id}/versions          # Historique des versions
GET    /{id}/deployments       # Historique des déploiements
POST   /{id}/validate          # Valider le compose sans déployer
```

**WebSocket :**
```
WS     /ws/deploy/{deployment_id}  # Événements de déploiement en temps réel
```

**Modèles :**

```python
class StackCreateRequest(BaseModel):
    name: str
    target_id: str
    compose_content: Optional[str] = None      # docker-compose.yml brut
    template_id: Optional[str] = None          # ID template marketplace
    configuration: Optional[dict] = None       # Variables pour le template
    env_vars: Optional[dict] = None            # Variables d'environnement (chiffrées en base)

class StackResponse(BaseModel):
    id: str
    name: str
    target_id: str
    template_id: Optional[str]
    version: int
    status: str                # created, deploying, deployed, stopped, error
    services: list[dict]       # Services extraits du compose
    created_at: str
    updated_at: str
```

### Targets — `/api/v1/targets/`

```
GET    /                       # Lister les targets
GET    /{id}                   # Détails (capabilities, ressources, status)
POST   /                       # Ajouter un target
PUT    /{id}                   # Modifier un target
DELETE /{id}                   # Supprimer un target
POST   /{id}/discover          # Lancer la détection des capabilities
GET    /{id}/resources         # Ressources système (CPU, RAM, disque)
```

**Modèles :**

```python
class TargetCreateRequest(BaseModel):
    name: str
    type: str                  # local, ssh
    environment_id: str
    host: Optional[str] = None
    connection_config: Optional[dict] = None  # SSH key, Socket token, etc.

class TargetResponse(BaseModel):
    id: str
    name: str
    type: str
    host: Optional[str]
    status: str                # online, offline, unknown, error
    capabilities: dict         # docker, Podman, K8s, K3s, libvirt, LXD, Incus, system info
    environment_id: str
    last_seen: Optional[str]
```

### Volumes — `/api/v1/volumes/`

```
GET    /                       # Lister les volumes (filtre: target_id)
GET    /{id}                   # Détails d'un volume
POST   /                       # Créer un volume
DELETE /{id}                   # Supprimer un volume
POST   /prune                  # Supprimer les volumes orphelins
GET    /{id}/browse            # Lister le contenu (file browser)
GET    /{id}/browse/{path}     # Contenu d'un fichier/dossier
PUT    /{id}/browse/{path}     # Modifier un fichier
POST   /{id}/upload            # Upload un fichier dans le volume
GET    /{id}/download/{path}   # Télécharger un fichier
```

### Networks — `/api/v1/networks/`

```
GET    /                       # Lister les networks (filtre: target_id)
POST   /                       # Créer un network
DELETE /{id}                   # Supprimer un network
GET    /{id}                   # Détails (containers connectés, config)
```

### Images — `/api/v1/images/`

```
GET    /                       # Lister les images (filtre: target_id)
POST   /pull                   # Pull une image
DELETE /{id}                   # Supprimer une image
POST   /prune                  # Supprimer les images non utilisées
```

### Plugins — `/api/v1/plugins/`

```
GET    /                       # Lister les plugins installés
GET    /{name}                 # Détails d'un plugin (config, status, resources)
POST   /install                # Installer un plugin
DELETE /{name}                 # Désinstaller un plugin
PUT    /{name}/config          # Modifier la configuration
POST   /{name}/start           # Démarrer un plugin arrêté
POST   /{name}/stop            # Arrêter un plugin
POST   /{name}/update          # Mettre à jour un plugin
```

**Modèles :**

```python
class PluginInstallRequest(BaseModel):
    name: str
    registry_url: Optional[str] = None  # Défaut: registre officiel
    config: Optional[dict] = None       # Configuration initiale

class PluginResponse(BaseModel):
    name: str
    version: str
    type: str                  # service, extension, hybrid
    category: str
    status: str                # installed, running, stopped, error
    resource_usage: dict       # ram_mb, cpu_percent
    installed_at: str
    config: dict               # Configuration actuelle (secrets masqués)
```

### Marketplace — `/api/v1/marketplace/`

```
GET    /catalog                # Catalogue complet
GET    /search                 # Recherche (query: q, category, arch)
GET    /plugins/{name}         # Fiche détaillée d'un plugin
GET    /stacks                 # Templates de stacks disponibles
GET    /stacks/{id}            # Détails d'un template de stack
POST   /refresh                # Rafraîchir le catalogue depuis les registres
```

### Organisations — `/api/v1/organizations/`

```
GET    /                       # Lister ses organisations
POST   /                       # Créer une organisation (Super Admin)
GET    /{id}                   # Détails
PUT    /{id}                   # Modifier
DELETE /{id}                   # Supprimer (Super Admin)
GET    /{id}/users             # Lister les membres
POST   /{id}/users             # Ajouter un membre
PUT    /{id}/users/{user_id}   # Modifier le rôle d'un membre
DELETE /{id}/users/{user_id}   # Retirer un membre
```

### Environnements — `/api/v1/environments/`

```
GET    /                       # Lister les environnements (filtre: org_id)
POST   /                       # Créer un environnement
GET    /{id}                   # Détails
PUT    /{id}                   # Modifier
DELETE /{id}                   # Supprimer
```

### Administration — `/api/v1/admin/`

```
GET    /users                  # Lister tous les utilisateurs (Super Admin)
POST   /users                  # Créer un utilisateur
PUT    /users/{id}             # Modifier un utilisateur
DELETE /users/{id}             # Supprimer un utilisateur
GET    /audit                  # Journal d'audit (filtres: user, action, date)
GET    /system/info            # Infos système (version, arch, mode, uptime)
POST   /backup                 # Lancer un backup
POST   /registries             # Ajouter un registre de plugins
GET    /registries             # Lister les registres
DELETE /registries/{id}        # Supprimer un registre
```

### Système — `/api/v1/system/`

```
GET    /health                 # Health check (pas d'auth requise)
GET    /ready                  # Readiness check (pas d'auth requise)
GET    /info                   # Version, mode (léger/standard), arch
```

---

## Routes Dynamiques des Plugins

Les plugins ajoutent des routes sous `/api/v1/plugins/{name}/`. Ces routes sont enregistrées dynamiquement par le Plugin Manager au chargement du plugin et apparaissent dans la documentation OpenAPI.

**Exemples :**

```
# Plugin Traefik
GET    /api/v1/plugins/traefik/domains
POST   /api/v1/plugins/traefik/domains
DELETE /api/v1/plugins/traefik/domains/{domain}
GET    /api/v1/plugins/traefik/status

# Plugin PostgreSQL Manager
GET    /api/v1/plugins/postgresql/databases
POST   /api/v1/plugins/postgresql/databases
POST   /api/v1/plugins/postgresql/users
GET    /api/v1/plugins/postgresql/stats

# Plugin AI (Ollama / LiteLLM)
POST   /api/v1/plugins/ai/generate
POST   /api/v1/plugins/ai/diagnose
POST   /api/v1/plugins/ai/chat
GET    /api/v1/plugins/ai/models

# Plugin Restic
GET    /api/v1/plugins/restic/backups
POST   /api/v1/plugins/restic/backups
POST   /api/v1/plugins/restic/restore
GET    /api/v1/plugins/restic/schedule
```

Les routes plugin héritent de l'authentification JWT et du RBAC du core. Voir [Architecture Modulaire](../ARCHITECTURE-MODULAIRE.md) pour les détails de l'injection de routes.

---

## WebSocket

Toutes les connexions WebSocket nécessitent un token JWT passé en query parameter.

```
WS /ws/terminal/{container_id}?token=<jwt>     # Terminal container
WS /ws/console/{vm_id}?token=<jwt>             # Console VNC/SPICE VM
WS /ws/logs/{container_id}?token=<jwt>         # Streaming logs container
WS /ws/deploy/{deployment_id}?token=<jwt>      # Événements déploiement
WS /ws/events?token=<jwt>                      # Événements système globaux
```

**Format des messages WebSocket :**

```json
{
    "type": "log",
    "data": {
        "timestamp": "2026-04-01T14:30:00Z",
        "message": "Pulling image postgres:15...",
        "level": "info"
    }
}
```

**Types d'événements système** (`/ws/events`) :

```json
{"type": "container.started", "data": {"id": "abc123", "name": "my-app"}}
{"type": "deployment.success", "data": {"id": "def456", "stack": "web"}}
{"type": "plugin.installed", "data": {"name": "traefik", "version": "1.0.0"}}
{"type": "target.offline", "data": {"id": "ghi789", "name": "remote-server"}}
```

---

## Gestion des Erreurs

### Codes HTTP Utilisés

| Code | Usage |
|------|-------|
| 200 | Succès (GET, PUT) |
| 201 | Créé (POST) |
| 204 | Supprimé (DELETE) |
| 400 | Requête invalide (validation) |
| 401 | Non authentifié |
| 403 | Permission refusée (RBAC) |
| 404 | Ressource non trouvée |
| 409 | Conflit (nom déjà pris, port déjà utilisé) |
| 422 | Erreur de validation Pydantic |
| 429 | Rate limited |
| 500 | Erreur serveur |

### Classes d'Erreur

```python
class APIError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: dict = None):
        super().__init__(
            status_code=status_code,
            detail={"error": {"code": code, "message": message, "details": details or {}}}
        )

class NotFoundError(APIError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(404, "NOT_FOUND", f"{resource} not found: {identifier}")

class PermissionDeniedError(APIError):
    def __init__(self, action: str = None):
        msg = f"Permission denied for: {action}" if action else "Permission denied"
        super().__init__(403, "PERMISSION_DENIED", msg)

class ConflictError(APIError):
    def __init__(self, message: str):
        super().__init__(409, "CONFLICT", message)
```

---

## Sécurité

### Authentification

Tous les endpoints (sauf `/api/v1/system/health`, `/api/v1/system/ready`, et `/api/v1/auth/login`) nécessitent un header `Authorization: Bearer <token>`.

Le token peut être un JWT (access token) ou une API key (préfixée `wf_ak_`).

### RBAC

Les permissions sont vérifiées par le middleware RBAC après l'authentification. Voir [RBAC et Permissions](06-rbac-permissions.md) pour la matrice des rôles.

### Rate Limiting

Le rate limiting protège les endpoints sensibles :

| Endpoint | Limite |
|----------|--------|
| `POST /auth/login` | 5 / minute par IP |
| `POST /stacks/*/deploy` | 10 / minute par utilisateur |
| `POST /plugins/install` | 5 / minute par utilisateur |
| Autres POST/PUT/DELETE | 60 / minute par utilisateur |
| GET | 120 / minute par utilisateur |

---

## Documentation OpenAPI

Accessible sur l'instance WindFlow :

- **Swagger UI** : `http://<host>:8080/api/docs`
- **ReDoc** : `http://<host>:8080/api/redoc`
- **JSON schema** : `http://<host>:8080/api/openapi.json`

Les routes ajoutées par les plugins apparaissent automatiquement dans la documentation avec leur propre tag.

```python
app = FastAPI(
    title="WindFlow API",
    description="API de gestion d'infrastructure self-hosted",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
```

---

**Références :**
- [Authentification](05-authentication.md) — Détails auth JWT et API keys
- [RBAC et Permissions](06-rbac-permissions.md) — Matrice des rôles
- [Fonctionnalités Principales](10-core-features.md) — Fonctionnalités derrière chaque endpoint
- [CLI Interface](08-cli-interface.md) — CLI qui consomme cette API
