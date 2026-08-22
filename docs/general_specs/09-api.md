# Chapitre 09 — API

> **Statut** : Spec cible · **Public** : Développeurs backend/frontend, CLI, intégrateurs · **Lié à** : [02-familles-workloads.md](02-familles-workloads.md), [03-modele-compute.md](03-modele-compute.md), [07-authentification.md](07-authentification.md), [11-plugins.md](11-plugins.md)

## Vue d'ensemble

Ce chapitre spécifie l'API REST et WebSocket de WindFlow. La surface principale est organisée **par famille de workloads** (`/apps`, `/machines`, `/hosts`) plus l'entité **Cluster** (`/clusters`), conformément au modèle directeur du chapitre 02. La vue Compute (`/compute/*`), organisée par technologie, est une surface secondaire réservée au Mode Infra. Les endpoints transverses (auth, organisations, environnements, plugins, marketplace, admin, système) complètent l'API. Ce chapitre couvre les conventions, les endpoints et le protocole WebSocket ; les comportements métier sont aux chapitres 02 et 03.

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
├── clusters/                      # Entité Cluster (surface principale)
├── compute/                       # Vue Compute par technologie (Mode Infra)
│   ├── containers/
│   ├── vms/
│   ├── stacks/
│   ├── snapshots/
│   ├── volumes/
│   ├── networks/
│   ├── images/
│   └── graph/
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

**Cohabitation des deux surfaces** : les endpoints `/apps`, `/machines`, `/hosts`, `/clusters` exposent les workloads et l'entité Cluster **par famille** avec leurs verbes universels (chapitre 02). Les endpoints `/compute/*` exposent les **objets techniques par technologie** (containers individuels, instances VM, stacks, snapshots, volumes, networks, images) : c'est la surface consommée par la vue Compute du Mode Infra (chapitre 03). Un même container géré apparaît donc comme une App dans `/apps` et comme un container dans `/compute/containers` ; les identifiants techniques sont partagés.

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
GET    /                       # Lister les Apps (filtres: host_id, machine_id, cluster_id, status, profile, origin, name)
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
GET    /{id}/graph             # Graphe de dépendances de l'App (nodes/edges normalisés)
POST   /batch-update           # Mettre à jour un groupe d'Apps (séquentiel, progression WebSocket)
```

Exemple illustratif — modèles de requête/réponse :

```python
class AppCreateRequest(BaseModel):
    name: str                          # ex. nextcloud
    profile: str                       # docker_container, docker_compose, helm_release, k8s_manifest
    host_id: Optional[str]             # hébergement direct sur un Host…
    machine_id: Optional[str]          # …ou App tournant dans une Machine…
    cluster_id: Optional[str]          # …ou App hébergée par un Cluster (helm_release, k8s_manifest)
                                       # (triple XOR — exactement un des trois, règle d'hébergement chapitre 02)
    marketplace_entry_id: Optional[str] = None
    configuration: Optional[dict] = None

class AppResponse(BaseModel):
    id: str
    name: str
    profile: str
    status: str                # running, stopped, starting, stopping, updating, degraded, error, unknown
    host_id: Optional[str]     # triple XOR host_id / machine_id / cluster_id
    machine_id: Optional[str]  # (règle d'hébergement, chapitre 02)
    cluster_id: Optional[str]
    domain: Optional[str]
    current_version: Optional[str]
    available_version: Optional[str]
    backup_enabled: bool
    origin: str                # managed | adopted | external (matrice profil × origine, chapitre 03)
    created_at: str
```

#### Mise à jour groupée (batch update)

Applique le verbe **Mettre à jour** (recreate à configuration préservée, chapitre [02-familles-workloads.md](02-familles-workloads.md)) à un ensemble d'Apps **séquentiellement**, avec suivi de progression **par WebSocket** :

**Requête :**

```json
{
    "app_ids": ["app_nextcloud", "app_pihole", "app_baserow"]
}
```

**Réponse :** un job groupé — `{"data": {"batch_id": "batch_7f2a", "total": 3}}` — dont la progression est diffusée sur `WS /ws/batch/{batch_id}` (section [WebSocket](#websocket)).

**Déroulement :**

- **séquentiel** : les Apps sont traitées une à une (pas de tempête d'appels Docker) ; **un échec n'interrompt pas la suite** — l'App en échec est rapportée et la file continue ;
- **sauts de sûreté** par App : container porteur du label `windflow.update=false`, image à digest épinglé → `skipped`, sans appel registre ;
- par App : **pull** de la nouvelle image (étape `pulling`), puis recreate sécurisé (`stopping` → `removing` → `creating` → `starting`) avec **rollback automatique** en cas d'échec (chapitre 02) ;
- chaque App réussie voit sa « mise à jour en attente » **effacée** (chapitre [03-modele-compute.md](03-modele-compute.md)) ;
- événement terminal `complete` avec résumé `{total, succeeded, failed, skipped}`.

**Messages du flux** (même enveloppe `type`/`data` que les autres canaux WebSocket) :

```json
{"type": "start", "data": {"batch_id": "batch_7f2a", "total": 3}}
{"type": "progress", "data": {"batch_id": "batch_7f2a", "app_id": "app_nextcloud", "step": "pulling", "current": 1, "total": 3}}
{"type": "progress", "data": {"batch_id": "batch_7f2a", "app_id": "app_nextcloud", "step": "done", "current": 1, "total": 3}}
{"type": "progress", "data": {"batch_id": "batch_7f2a", "app_id": "app_pihole", "step": "failed", "message": "pull: tag introuvable", "current": 2, "total": 3}}
{"type": "complete", "data": {"batch_id": "batch_7f2a", "total": 3, "succeeded": 2, "failed": 1, "skipped": 0}}
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

La famille Hosts remplace l'ancienne ressource `/targets` (alias historique : *target*). `/hosts` ne liste **plus de clusters** — les grappes multi-nœuds (kubernetes, proxmox, swarm) sont des Clusters exposés par `/clusters`.

```
GET    /                       # Lister les Hosts (filtres: environment_id, status, profile)
POST   /                       # Ajouter un Host (adoption d'un substrat individuel)
GET    /{id}                   # Détails (hardware, moteurs installés, statut)
PUT    /{id}                   # Modifier un Host
DELETE /{id}                   # Retirer du suivi WindFlow (ne supprime pas la machine)
POST   /{id}/scan              # Rescanner les moteurs et le hardware
GET    /{id}/metrics           # Métriques système (CPU, RAM, disque, réseau, température)
GET    /{id}/services          # Services système (systemd…)
GET    /{id}/apps              # Apps déployées sur ce Host
GET    /{id}/machines          # Machines hébergées sur ce Host
GET    /{id}/cluster           # Cluster dont ce Host est membre (si applicable)
POST   /{id}/actions/{action_id}  # Exécuter une ContextualAction (reboot, update OS…)
GET    /{id}/ssh               # Session SSH (WebSocket)
GET    /{id}/journal           # Journal système (WebSocket)
```

Exemple illustratif — modèles de requête/réponse :

```python
class HostCreateRequest(BaseModel):
    name: str                          # ex. nas-server
    profile: str                       # host_baremetal, host_proxmox, host_remote_docker
    environment_id: str
    connection_config: dict            # SSH config, API endpoint (chiffré en base)

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

### Entité Cluster — `/api/v1/clusters/`

Les grappes multi-nœuds du chapitre 02 (types `kubernetes`, `proxmox`, `docker_swarm`) — surface principale, au même rang que les familles. L'ajout d'un Cluster suit le wizard dédié (chapitre 14, Écran 13) : l'utilisateur choisit le type, fournit la connexion (kubeconfig, API endpoint, socket) et le test résout les membres.

```
GET    /                       # Lister les Clusters (filtres: environment_id, type, status, origin)
POST   /                       # Ajouter un Cluster (kubernetes: kubeconfig, proxmox: API, docker_swarm: socket/API)
GET    /{id}                   # Détails (type, membres, métriques agrégées, statut)
PUT    /{id}                   # Modifier un Cluster (connexion, description)
DELETE /{id}                   # Retirer du suivi WindFlow (ne supprime pas la grappe)
POST   /{id}/scan              # Rescanner les membres et les workloads (API du cluster)
GET    /{id}/health            # Santé : quorum, membres down/notReady, versions
GET    /{id}/members           # Membres (host_id/machine_id, rôle, labels/taints, santé)
POST   /{id}/members           # Rattacher un membre (host_id ou machine_id, rôle) — nœud non résolu automatiquement
DELETE /{id}/members/{member_id}  # Détacher un membre (retire l'appartenance, jamais l'entité Host/Machine)
GET    /{id}/apps              # Apps hébergées par ce Cluster (helm_release, k8s_manifest…)
POST   /{id}/actions/{action_id}  # Exécuter une ContextualAction (drain, promote/demote…)
GET    /{id}/events            # Événements du Cluster (events k8s, tâches Proxmox) — WebSocket
```

Exemple illustratif — modèles de requête/réponse :

```python
class ClusterCreateRequest(BaseModel):
    name: str                          # ex. k3s-cluster
    type: str                          # kubernetes | proxmox | docker_swarm
    environment_id: str
    connection_config: dict            # kubeconfig (kubernetes), API endpoint + tokens (proxmox),
                                       # socket/API + TLS (docker_swarm) — chiffré en base

class ClusterMemberResponse(BaseModel):
    id: str
    cluster_id: str
    host_id: Optional[str]     # le membre est un Host…
    machine_id: Optional[str]  # …ou une Machine (XOR host_id/machine_id, chapitre 06)
    role: str                  # control-plane | worker | member
    k8s_metadata: dict         # labels, taints (kubernetes)
    joined_at: str
```

**Rattachement des membres.** Le scan d'un Cluster résout automatiquement les nœuds qu'il reconnaît (rapprochement par nom/IP avec des Hosts/Machines existants → création de lignes `cluster_members`). Les nœuds non reconnus sont listés en lecture seule dans `/clusters/{id}/members` (sans `host_id` ni `machine_id` tant qu'aucune entité ne les représente — le rattachement manuel crée ou réutilise l'entité).

## API Mode Infra — vue Compute

La vue Compute expose les objets bas niveau **par technologie** (chapitre 03). Elle complète les familles, sans les remplacer : les opérations par famille passent par `/apps`, `/machines`, `/hosts`, `/clusters`.

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

#### Validation Compose — `POST /{id}/validate`

Valide une stack Compose **sans la déployer** : analyse du YAML parsé + confrontation à l'**état réel du Host**. Le moteur de règles est **auto-déclaré** — chaque règle porte un code, une description, un groupe et une sévérité par défaut ; une règle qui échoue à l'exécution est **isolée** sans faire échouer les autres, et chaque violation est complétée par la sévérité effective (par défaut ou personnalisée).

**Catalogue des règles (20) :**

| Code | Vérification | Sévérité par défaut | Catégorie |
|---|---|---|---|
| `NO_SERVICES` | Le fichier ne définit aucun service | `error` | Structure |
| `DUPLICATE_HOST_PORT` | Deux services de la stack publient le même port hôte | `error` | Réseau |
| `CROSS_STACK_PORT_COLLISION` | Un port hôte déjà utilisé par un autre container du Host (collision cross-stack) | `error` | État réel |
| `DB_PORT_ON_ALL_INTERFACES` | Un service de base de données/cache publie sur toutes les interfaces | `warning` | Réseau |
| `DEPENDS_ON_UNDEFINED` | `depends_on` référence un service non défini | `error` | Structure |
| `UNDEFINED_NETWORK_REF` | Un service utilise un réseau non déclaré au niveau supérieur | `error` | Structure |
| `UNDEFINED_VOLUME_REF` | Montage d'un volume nommé non déclaré au niveau supérieur | `error` | Structure |
| `CONTAINER_NAME_COLLISION` | `container_name` déjà utilisé par un container du Host | `error` | État réel |
| `MISSING_EXTERNAL_RESOURCE` | Un réseau/volume externe n'existe pas sur le Host | `error` | État réel |
| `LATEST_TAG` | Image avec `:latest` ou sans tag (reproductibilité) | `warning` | Bonnes pratiques |
| `PRIVILEGED_CONTAINER` | Service en mode privilégié (accès Host complet) | `warning` | Sécurité |
| `DOCKER_SOCKET_MOUNT` | Montage du socket Docker | `warning` | Sécurité |
| `OBSOLETE_VERSION_KEY` | Clé `version:` obsolète en tête de fichier | `info` | Bonnes pratiques |
| `UNKNOWN_SERVICE_KEY` | Clé de service ressemblant à une faute de frappe d'une vraie clé Compose | `warning` | Structure |
| `UNKNOWN_TOP_LEVEL_KEY` | Clé de premier niveau ressemblant à une faute de frappe | `warning` | Structure |
| `SECRET_IN_ENVIRONMENT` | Valeur d'aspect secret codée en dur dans `environment:` au lieu d'un secret/variable | `warning` | Sécurité |
| `HOST_NETWORK_MODE` | `network_mode: host` (pas d'isolation réseau) | `warning` | Sécurité |
| `WRITABLE_ROOT_MOUNT` | Chemin hôte sensible monté en écriture (compromission potentielle du Host) | `error` | Sécurité |
| `CAP_ADD_DANGEROUS` | Capacité Linux quasi-privilégiée ajoutée (`SYS_ADMIN`, `NET_ADMIN`…) | `warning` | Sécurité |
| `MISSING_RESTART_POLICY` | Absence de politique de redémarrage (ne reviendra pas après un reboot du Host) | `info` | Bonnes pratiques |

**Confrontation à l'état réel du Host :** les règles de catégorie « État réel » croisent le Compose avec l'inventaire runtime du Host cible — ports hôte déjà publiés par d'autres containers (**collisions cross-stack** : deux stacks différentes ne peuvent pas réserver le même port), `container_name` déjà pris, ressources `external:` (réseaux, volumes) existantes ou non. Une collision avec un container **arrêté** compte : le nom et le port restent réservés.

**Réponse :** la validation est **informative** — elle ne bloque pas le déploiement (les bloqueurs effectifs restent les erreurs Docker/Compose elles-mêmes). La réponse est une liste de violations avec leur sévérité effective :

```json
{
    "data": {
        "valid": false,
        "violations": [
            {
                "rule": "LATEST_TAG",
                "severity": "warning",
                "service": "api",
                "message": "Image 'api:latest' sans version épinglée",
                "location": {"line": 14, "key": "services.api.image"}
            },
            {
                "rule": "CROSS_STACK_PORT_COLLISION",
                "severity": "error",
                "service": "web",
                "message": "Le port hôte 8080 est déjà publié par le container 'traefik' (stack web)"
            }
        ]
    }
}
```

Chaque violation porte la sévérité (`info` | `warning` | `error`), le service concerné, un message explicatif et sa position dans le fichier quand elle est déterminable. `valid` est un résumé pratique (aucune violation de sévérité `error`).

**Personnalisation des sévérités :** chaque règle peut être **désactivée** ou voir sa sévérité modifiée dans les réglages de validation ; ces préférences sont persistées et appliquées à chaque validation — la sévérité rapportée est toujours la **sévérité effective** (personnalisée si définie, sinon celle par défaut du catalogue).

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

#### Prune des volumes — sémantique protégée

`POST /prune` supprime les volumes **inutilisés et non protégés** d'un Host :

- **« Inutilisé » = sans aucun utilisateur, y compris un container arrêté** — un volume monté par un container arrêté reste **utilisé** (sémantique alignée sur Docker) ; seuls les volumes qu'aucun container, actif ou arrêté, ne monte sont éligibles ;
- **liste protégée par convention de nommage** : les volumes dont le nom commence par **`windflow-plugin-*`** sont **épargnés** (caches des plugins — bases de vulnérabilités des scanners, state des helpers). Ces volumes nommés sont inutilisés entre deux exécutions : un prune non filtré les détruirait et forcerait un re-téléchargement coûteux à chaque cycle ;
- **suppression unitaire, sans force** : chaque volume éligible est supprimé individuellement ; un volume devenu utilisé entre la liste et la suppression échoue et est **passé** — un volume récalcitrant n'interrompt jamais la file ;
- **rapport explicite** : la réponse rapporte les volumes **supprimés**, les volumes **épargnés** (protégés) et les **échecs** passés ; l'espace libéré n'est **pas fabriqué** (l'API Docker ne fournit pas la taille par volume — aucune valeur inventée).

La même sémantique protégée s'applique au prune d'images (section Images ci-dessous).

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
POST   /prune                  # Supprimer les images non utilisées (voir Prune des images)
POST   /check-updates          # Vérifier les mises à jour disponibles (digest/semver, sans pull)
GET    /check-updates          # Lire le dernier résultat de vérification (cache, sans effet de bord)
GET    /pending-updates        # Lister les mises à jour en attente (filtres: host_id, stack_id, type, status)
POST   /pending-updates/{id}/skip  # Marquer une suggestion semver comme ignorée (statut skipped)
```

#### Détection de mises à jour d'images

- `POST /check-updates` déclenche la vérification **sans pull** (comparaison de digest + suggestion semver — mécanisme détaillé au chapitre [03-modele-compute.md](03-modele-compute.md)) pour les containers éligibles d'un Host (`?host_id=`) ou de tous les Hosts. L'opération est un job : la réponse retourne un `batch_id` et la progression par container est diffusée sur `WS /ws/batch/{batch_id}` (étapes `checking` → `done` / `failed` / `skipped` par container). À l'issue, les lignes « mise à jour en attente » sont **réinitialisées puis reconstruites** en fusionnant les deux signaux.
- `GET /check-updates` retourne le **dernier résultat connu** (cache), sans relancer de vérification.
- `GET /pending-updates` liste les mises à jour en attente — **source des colonnes `current_version`/`available_version`** du modèle de données (chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)) et du badge ⬆ des cartes Apps (chapitre [14-ui-maquettes.md](14-ui-maquettes.md), Écran 2) :

```json
{
    "data": [
        {
            "id": "pu_012",
            "host_id": "host_nas",
            "container": {"id": "c_ab12", "name": "nextcloud-app"},
            "image": "nextcloud:29",
            "current": "sha256:6f3a…",
            "available": "sha256:c81e…",
            "type": "digest",
            "status": "pending",
            "checked_at": "2026-08-22T08:00:00Z"
        }
    ]
}
```

- `POST /pending-updates/{id}/skip` marque une suggestion semver `skipped` — une suggestion semver est **purement indicative et jamais auto-appliquée**. L'application d'une mise à jour passe par le verbe **Mettre à jour** (recreate à configuration préservée, chapitre [02-familles-workloads.md](02-familles-workloads.md)) — unitaire ou groupée ([Mise à jour groupée (batch update)](#mise-à-jour-groupée-batch-update)).

#### Prune des images

`POST /prune` supprime les images inutilisées (`?dangling=true` par défaut — images sans tag uniquement ; `dangling=false` — toutes les images inutilisées) :

- **« Inutilisé » = non référencée par un container, y compris arrêté** — même sémantique que les volumes (section [Volumes](#volumes--apiv1computevolumes)) ;
- les images des **plugins** (helpers, scanners) sont **épargnées** — convention de nommage `windflow-plugin-*` (identique à la liste protégée des volumes) ;
- la réponse rapporte les images **supprimées**, les images **épargnées** (protégées) et l'**espace réellement libéré** tel que rapporté par le daemon — aucune valeur fabriquée.

### Graphe de dépendances — `/api/v1/compute/graph`

Source de données de l'Écran 20 (chapitre [14-ui-maquettes.md](14-ui-maquettes.md)). Le backend dérive le graphe du parsing des compose (`depends_on`, condition `service_started` / `service_healthy`) et de l'inspection runtime ; pour Kubernetes/Helm, les arêtes relient les workloads du même namespace (généralisation profil × origine, chapitre [03-modele-compute.md](03-modele-compute.md)). Le graphe peut en outre afficher la **topologie des membres** d'un Cluster (filtre `cluster_id` : sous-graphe par membre, arêtes membre → Cluster — hôte de l'App) quand elle est pertinente pour la lecture des dépendances.

```
GET    /                       # Graphe global (filtres: host_id, app_id, origin, status)
POST   /from-compose           # Graphe normalisé depuis un compose fourni (round-trip éditeur)
```

Exemple illustratif — réponse normalisée (contrat `nodes`/`edges` de Vue Flow) :

```json
{
    "data": {
        "nodes": [
            {"id": "baserow-db", "type": "service", "app_id": "app_baserow",
             "data": {"image": "postgres:15", "profile": "docker_compose",
                      "origin": "managed", "status": "running"}}
        ],
        "edges": [
            {"id": "e1", "source": "baserow-backend", "target": "baserow-db",
             "data": {"condition": "service_healthy"}}
        ],
        "cycles": []
    }
}
```

La clé `cycles` liste les cycles détectés (avertissement d'affichage) — la détection réutilise le pattern de résolution transitive du moteur de dépendances plugins.

### Génération compose — `/api/v1/compute/stacks/`

L'Éditeur de composition (Écran 21) sérialise le graphe et délègue la génération et la validation au backend :

```
POST   /from-graph             # Générer un compose depuis un graphe nodes/edges
POST   /validate               # Valider un compose sans déployer (existant, réutilisé)
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
WS /ws/batch/{batch_id}?token=<jwt>            # Progression des opérations groupées (batch update, check-updates)
WS /ws/events?token=<jwt>                      # Événements système globaux
```

Le canal `/ws/terminal` est réservé aux containers ; les consoles de Machines passent par `/ws/console` et les sessions Hosts par `/ws/ssh`.

Le canal `/ws/batch` diffuse la progression des **opérations groupées** (mise à jour groupée multi-Apps, vérification de mises à jour) : messages `start` (total), `progress` (étape courante par élément), `complete` (résumé) et `error` en échec global — même enveloppe `type`/`data` que les autres canaux.

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
