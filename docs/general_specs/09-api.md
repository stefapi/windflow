# Chapitre 09 — API

> **Statut** : Spec cible · **Public** : Développeurs backend/frontend, CLI, intégrateurs · **Lié à** : [02-familles-workloads.md](02-familles-workloads.md), [03-modele-compute.md](03-modele-compute.md), [07-authentification.md](07-authentification.md), [11-plugins.md](11-plugins.md)

## Vue d'ensemble

Ce chapitre spécifie l'API REST et WebSocket de WindFlow. La surface principale est organisée **par famille de workloads** (`/apps`, `/machines`, `/hosts`), conformément au modèle directeur du chapitre 02. La vue Compute (`/compute/*`), organisée par technologie, est une surface secondaire réservée au Mode Infra. Les endpoints transverses (auth, organisations, environnements, plugins, marketplace, admin, système) complètent l'API. Ce chapitre couvre les conventions, les endpoints et le protocole WebSocket ; les comportements métier sont aux chapitres 02 et 03.

## Conventions générales

### Principes

- **REST** : conventions HTTP strictes (GET pour lire, POST pour créer, PUT pour modifier, DELETE pour supprimer).
- **OpenAPI 3.0** : documentation automatique sur `/api/docs` (Swagger) et `/api/redoc`.
- **Auth JWT** : tous les endpoints (sauf `/auth/login` et `/system/health|ready`) nécessitent un token Bearer (JWT ou clé API préfixée `wf_ak_`).
- **Pagination** : toutes les listes sont paginées avec `?page=1&per_page=20`.
- **JSON** : entrée et sortie en JSON.
- **Plugins** : les plugins ajoutent des routes sous `/api/v1/plugins/{name}/` — elles apparaissent dans la documentation OpenAPI.

### Structure des endpoints

```
/api/v1/
├── auth/                          # Authentification (core)
├── apps/                          # Famille Apps (surface principale)
├── machines/                      # Famille Machines (surface principale)
├── hosts/                         # Famille Hosts (surface principale)
├── compute/                       # Vue Compute par technologie (Mode Infra)
│   ├── containers/
│   ├── vms/
│   ├── stacks/
│   ├── snapshots/
│   ├── volumes/
│   ├── networks/
│   └── images/
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

**Cohabitation des deux surfaces** : les endpoints `/apps`, `/machines`, `/hosts` exposent les workloads **par famille** avec leurs verbes universels (chapitre 02). Les endpoints `/compute/*` exposent les **objets techniques par technologie** (containers individuels, instances VM, stacks, snapshots, volumes, networks, images) : c'est la surface consommée par la vue Compute du Mode Infra (chapitre 03). Un même container géré apparaît donc comme une App dans `/apps` et comme un container dans `/compute/containers` ; les identifiants techniques sont partagés.

### Format de réponse

**Réponse standard :**

```json
{
    "data": { ... },
    "message": "App created successfully"
}
```

**Réponse liste (paginée) :**

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

**Réponse erreur :**

```json
{
    "error": {
        "code": "NOT_FOUND",
        "message": "App not found: abc123"
    }
}
```

Exemple illustratif — modèles Pydantic des enveloppes :

```python
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

## API par famille

### Famille Apps — `/api/v1/apps/`

```
GET    /                       # Lister les Apps (filtres: host_id, status, profile, name)
POST   /                       # Créer une App (deploy depuis la marketplace ou manuel)
GET    /{id}                   # Détails d'une App
PUT    /{id}/config            # Modifier la configuration (formulaire)
DELETE /{id}                   # Supprimer l'App
POST   /{id}/start             # Démarrer
POST   /{id}/stop              # Arrêter
POST   /{id}/restart           # Redémarrer
POST   /{id}/update            # Mettre à jour (avec rollback automatique)
POST   /{id}/backup            # Sauvegarder (volumes, values, config)
POST   /{id}/restore           # Restaurer une sauvegarde
GET    /{id}/actions           # Lister les ContextualActions disponibles
POST   /{id}/actions/{action_id}  # Exécuter une ContextualAction
GET    /{id}/logs              # Logs (WebSocket)
GET    /{id}/console           # Console interactive (WebSocket)
```

Exemple illustratif — modèles de requête/réponse :

```python
class AppCreateRequest(BaseModel):
    name: str                          # ex. nextcloud
    profile: str                       # docker_container, docker_compose, helm_release, k8s_manifest
    host_id: str
    marketplace_entry_id: Optional[str] = None
    configuration: Optional[dict] = None

class AppResponse(BaseModel):
    id: str
    name: str
    profile: str
    status: str                # running, stopped, starting, stopping, updating, degraded, error, unknown
    host_id: str
    domain: Optional[str]
    current_version: Optional[str]
    available_version: Optional[str]
    backup_enabled: bool
    adopted_from_discovered: bool
    created_at: str
```

### Famille Machines — `/api/v1/machines/`

```
GET    /                       # Lister les Machines (filtres: host_id, power_state, profile)
POST   /                       # Créer une Machine (depuis un template ou manuel)
GET    /{id}                   # Détails d'une Machine
DELETE /{id}                   # Supprimer
POST   /{id}/power-on          # Démarrer
POST   /{id}/power-off         # Arrêt graceful (shutdown ACPI)
POST   /{id}/power-off?force=true  # Arrêt forcé
POST   /{id}/reboot            # Redémarrer
PUT    /{id}/hardware          # Modifier le hardware (CPU, RAM, disques, NICs)
POST   /{id}/snapshot          # Créer un snapshot
GET    /{id}/snapshots         # Lister les snapshots
POST   /{id}/snapshots/{snap_id}/restore  # Restaurer un snapshot
DELETE /{id}/snapshots/{snap_id}          # Supprimer un snapshot
POST   /{id}/backup            # Export du disque
GET    /{id}/actions           # Lister les ContextualActions
POST   /{id}/actions/{action_id}  # Exécuter une ContextualAction
GET    /{id}/vnc               # Console VNC/SPICE (WebSocket noVNC)
GET    /{id}/serial            # Console série (WebSocket xterm.js)
```

Exemple illustratif — modèle de création :

```python
class MachineCreateRequest(BaseModel):
    name: str                          # ex. ubuntu-dev
    profile: str                       # vm_kvm, vm_lxd, vm_incus, vm_lxc, vm_virtualbox
    host_id: str
    template_id: Optional[str] = None  # template marketplace d'origine
    vcpus: int = 2
    memory_mb: int = 2048
    disk_size_gb: int = 20
    iso_path: Optional[str] = None
    cloud_init: Optional[dict] = None
```

### Famille Hosts — `/api/v1/hosts/`

La famille Hosts remplace l'ancienne ressource `/targets` (alias historique : *target*).

```
GET    /                       # Lister les Hosts (filtres: environment_id, status, profile)
POST   /                       # Ajouter un Host (adoption d'un substrat)
GET    /{id}                   # Détails (hardware, moteurs installés, statut)
PUT    /{id}                   # Modifier un Host
DELETE /{id}                   # Retirer du suivi WindFlow (ne supprime pas la machine)
POST   /{id}/scan              # Rescanner les moteurs et le hardware
GET    /{id}/metrics           # Métriques système (CPU, RAM, disque, réseau, température)
GET    /{id}/services          # Services système (systemd…)
GET    /{id}/apps              # Apps déployées sur ce Host
GET    /{id}/machines          # Machines hébergées sur ce Host
POST   /{id}/actions/{action_id}  # Exécuter une ContextualAction (reboot, update OS…)
GET    /{id}/ssh               # Session SSH (WebSocket)
GET    /{id}/journal           # Journal système (WebSocket)
```

Exemple illustratif — modèles de requête/réponse :

```python
class HostCreateRequest(BaseModel):
    name: str                          # ex. nas-server
    profile: str                       # host_baremetal, host_proxmox, host_kubernetes, host_remote_docker
    environment_id: str
    connection_config: dict            # SSH config, API endpoint, kubeconfig (chiffré en base)

class HostResponse(BaseModel):
    id: str
    name: str
    profile: str
    status: str                # online, offline, unreachable, scanning
    hardware_info: dict
    installed_engines: list    # docker, libvirt, kubernetes…
    environment_id: str
    last_scan_at: Optional[str]
```

## API Mode Infra — vue Compute

La vue Compute expose les objets bas niveau **par technologie** (chapitre 03). Elle complète les familles, sans les remplacer : les opérations par famille passent par `/apps`, `/machines`, `/hosts`.

### Containers — `/api/v1/compute/containers/`

```
GET    /                       # Lister les containers (filtres: host_id, status, name)
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

### VMs — `/api/v1/compute/vms/`

```
GET    /                       # Lister les instances VM (filtres: host_id, status, hypervisor)
GET    /{id}                   # Détails d'une instance VM
POST   /{id}/start             # Démarrer
POST   /{id}/stop              # Arrêt graceful
POST   /{id}/force-stop        # Arrêt forcé
POST   /{id}/restart           # Redémarrer
DELETE /{id}                   # Supprimer
```

### Stacks — `/api/v1/compute/stacks/`

```
GET    /                       # Lister les stacks
GET    /{id}                   # Détails d'une stack (config, status, versions)
POST   /                       # Créer une stack
PUT    /{id}                   # Modifier (crée une nouvelle version)
DELETE /{id}                   # Supprimer
POST   /{id}/deploy            # Déployer
POST   /{id}/stop              # Arrêter tous les services
POST   /{id}/rollback          # Rollback à la version précédente
POST   /{id}/validate          # Valider le compose sans déployer
GET    /{id}/versions          # Historique des versions
GET    /{id}/deployments       # Historique des déploiements
```

### Snapshots — `/api/v1/compute/snapshots/`

```
GET    /                       # Lister les snapshots (filtres: host_id, vm_id, date)
GET    /{id}                   # Détails d'un snapshot
DELETE /{id}                   # Supprimer un snapshot
```

### Volumes — `/api/v1/compute/volumes/`

```
GET    /                       # Lister les volumes (filtre: host_id)
GET    /{id}                   # Détails d'un volume
POST   /                       # Créer un volume
DELETE /{id}                   # Supprimer un volume
POST   /prune                  # Supprimer les volumes orphelins
GET    /{id}/browse            # Lister le contenu (volume browser)
GET    /{id}/browse/{path}     # Contenu d'un fichier/dossier
PUT    /{id}/browse/{path}     # Modifier un fichier
POST   /{id}/upload            # Uploader un fichier dans le volume
GET    /{id}/download/{path}   # Télécharger un fichier
```

### Networks — `/api/v1/compute/networks/`

```
GET    /                       # Lister les networks (filtre: host_id)
GET    /{id}                   # Détails (containers connectés, config)
POST   /                       # Créer un network
DELETE /{id}                   # Supprimer un network
```

### Images — `/api/v1/compute/images/`

```
GET    /                       # Lister les images (filtre: host_id)
POST   /pull                   # Pull une image
DELETE /{id}                   # Supprimer une image
POST   /prune                  # Supprimer les images non utilisées
```

## Endpoints transverses

### Authentification — `/api/v1/auth/`

```
POST   /login                  # Login (username + password) → tokens
POST   /refresh                # Renouveler l'access token
POST   /logout                 # Invalider le refresh token
GET    /me                     # Infos utilisateur courant
PUT    /password               # Changer son mot de passe
POST   /api-keys               # Créer une clé API
GET    /api-keys               # Lister ses clés API
DELETE /api-keys/{id}          # Révoquer une clé API
```

Détails : chapitre [07-authentification.md](07-authentification.md).

### Plugins — `/api/v1/plugins/`

```
GET    /                       # Lister les plugins installés
GET    /{name}                 # Détails d'un plugin (config, status, resources)
POST   /install                # Installer un plugin
DELETE /{name}                 # Désinstaller
PUT    /{name}/config          # Modifier la configuration
POST   /{name}/start           # Démarrer un plugin arrêté
POST   /{name}/stop            # Arrêter un plugin
POST   /{name}/update          # Mettre à jour
```

Détails : chapitre [11-plugins.md](11-plugins.md).

### Marketplace — `/api/v1/marketplace/`

```
GET    /catalog                # Catalogue complet (3 onglets)
GET    /search                 # Recherche (query: q, category, arch)
GET    /apps/{name}            # Fiche d'une entrée App multi-backends
GET    /machine-templates      # Templates de Machines disponibles
GET    /machine-templates/{id} # Détails d'un template
GET    /plugins/{name}         # Fiche détaillée d'un plugin
POST   /refresh                # Rafraîchir le catalogue depuis les registres
```

Détails : chapitre [12-marketplace.md](12-marketplace.md).

### Organisations — `/api/v1/organizations/`

```
GET    /                       # Lister ses organisations
POST   /                       # Créer (Super Admin)
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
GET    /                       # Lister (filtre: org_id)
POST   /                       # Créer
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

## Routes dynamiques des plugins

Les plugins ajoutent des routes sous `/api/v1/plugins/{name}/`. Ces routes sont enregistrées dynamiquement par le Plugin Manager au chargement du plugin et apparaissent dans la documentation OpenAPI.

Exemples :

```
# Plugin Traefik
GET    /api/v1/plugins/traefik/domains
POST   /api/v1/plugins/traefik/domains
DELETE /api/v1/plugins/traefik/domains/{domain}
GET    /api/v1/plugins/traefik/status

# Plugin PostgreSQL
GET    /api/v1/plugins/postgresql/databases
POST   /api/v1/plugins/postgresql/databases
POST   /api/v1/plugins/postgresql/users
GET    /api/v1/plugins/postgresql/stats

# Plugin IA (Ollama / LiteLLM)
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

Les routes plugin héritent de l'authentification JWT et du RBAC du core. Voir [11-plugins.md](11-plugins.md) et [../technical_specs/ARCHITECTURE-MODULAIRE.md](../technical_specs/ARCHITECTURE-MODULAIRE.md) pour les détails de l'injection de routes.

## WebSocket

Toutes les connexions WebSocket nécessitent un token JWT passé en query parameter. Les chemins ci-dessous sont la **référence unique** des canaux WS :

```
WS /ws/terminal/{container_id}?token=<jwt>     # Terminal container
WS /ws/console/{machine_id}?token=<jwt>        # Console VNC/SPICE Machine (noVNC)
WS /ws/ssh/{host_id}?token=<jwt>               # Session SSH Host
WS /ws/logs/{app_id}?token=<jwt>               # Streaming logs App
WS /ws/journal/{host_id}?token=<jwt>           # Journal système Host
WS /ws/deploy/{deployment_id}?token=<jwt>      # Événements de déploiement
WS /ws/events?token=<jwt>                      # Événements système globaux
```

Le canal `/ws/terminal` est réservé aux containers ; les consoles de Machines passent par `/ws/console` et les sessions Hosts par `/ws/ssh`.

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

**Événements système** (`/ws/events`) — le nommage suit la convention `domaine.action_passé` de la liste canonique définie au chapitre [11-plugins.md](11-plugins.md) :

```json
{"type": "container.started", "data": {"id": "abc123", "name": "nextcloud"}}
{"type": "deployment.succeeded", "data": {"id": "def456", "stack": "web"}}
{"type": "plugin.installed", "data": {"name": "traefik", "version": "1.0.0"}}
{"type": "host.offline", "data": {"id": "ghi789", "name": "nas-server"}}
```

Le protocole détaillé (reconnexion, heartbeats, acknowledgment) est spécifié dans [../technical_specs/WEBSOCKET-REAL-TIME.md](../technical_specs/WEBSOCKET-REAL-TIME.md).

## Gestion des erreurs

### Codes HTTP utilisés

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

### Classes d'erreur

Exemple illustratif — hiérarchie des exceptions API :

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

## Sécurité

### Authentification

Tous les endpoints (sauf `/api/v1/system/health`, `/api/v1/system/ready` et `/api/v1/auth/login`) nécessitent un header `Authorization: Bearer <token>`. Le token peut être un JWT (access token) ou une clé API (préfixée `wf_ak_`).

### RBAC

Les permissions sont vérifiées par le middleware RBAC après l'authentification, par famille de workload. Voir [08-rbac-permissions.md](08-rbac-permissions.md) pour la matrice des rôles.

### Rate limiting

Le rate limiting protège les endpoints sensibles :

| Endpoint | Limite |
|----------|--------|
| `POST /auth/login` | 5 / minute par IP |
| `POST /compute/stacks/*/deploy` | 10 / minute par utilisateur |
| `POST /plugins/install` | 5 / minute par utilisateur |
| Autres POST/PUT/DELETE | 60 / minute par utilisateur |
| GET | 120 / minute par utilisateur |

## Documentation OpenAPI

Accessible sur l'instance WindFlow :

- **Swagger UI** : `http://<host>:8080/api/docs`
- **ReDoc** : `http://<host>:8080/api/redoc`
- **JSON schema** : `http://<host>:8080/api/openapi.json`

Les routes ajoutées par les plugins apparaissent automatiquement dans la documentation avec leur propre tag.

## Voir aussi

- [02-familles-workloads.md](02-familles-workloads.md) — verbes universels et ContextualActions exposés par cette API
- [03-modele-compute.md](03-modele-compute.md) — taxonomie des objets exposés par `/compute/*`
- [07-authentification.md](07-authentification.md) — JWT, clés API et protection brute-force
- [08-rbac-permissions.md](08-rbac-permissions.md) — matrice des rôles appliquée aux endpoints
- [11-plugins.md](11-plugins.md) — liste canonique des événements et injection de routes
- [../technical_specs/WEBSOCKET-REAL-TIME.md](../technical_specs/WEBSOCKET-REAL-TIME.md) — protocole temps réel détaillé
