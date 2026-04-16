 # EPIC-008 : Couverture Frontend des APIs Backend

**Statut :** IN_PROGRESS
**Priorité :** Haute

## Vision
Combler le fossé entre les APIs backend disponibles et leur utilisation dans le frontend WindFlow. Actuellement, **23 endpoints API backend ne sont pas exploités** par l'interface utilisateur, limitant les fonctionnalités accessibles aux utilisateurs.

Cette epic intègre également les concepts du **Modèle Compute** (cf. `doc/general_specs/12-compute-model.md`) pour les stacks :
- **3 niveaux de contrôle** : Managed (stack WindFlow), Discovered (observé, adoptable), Standalone (individuel)
- **Actions de stack** : start/stop globaux, duplication, archivage, synchronisation Git
- **Discovery & Adoption** : détection des containers/compositions orphelins, wizard d'adoption

---

## Analyse Détaillée API Backend vs Frontend

### 📊 Matrice de Couverture API

#### APIs Compute Global (nouvelles — `backend/app/api/v1/compute.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/compute/stats` | GET | Statistiques globales compute (totaux, running, discovered…) | ❌ Absent | 🔴 À implémenter |
| `/compute/global` | GET | Vue unifiée 3 sections (managed/discovered/standalone) avec filtres | ❌ Absent | 🔴 À implémenter |

#### Docker Containers (`backend/app/api/v1/docker.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/docker/containers` | GET | Liste des containers (+ params `control_level`, `stack_id`, `target_id`) | `containersApi.list` | ✅ Couvert (filtres manquants) |
| `/docker/containers/{id}` | GET | Détails container | `containersApi.inspect` | ✅ Couvert |
| `/docker/containers` | POST | Créer container | ❌ Absent | 🔴 À implémenter |
| `/docker/containers/{id}/start` | POST | Démarrer | `containersApi.start` | ✅ Couvert |
| `/docker/containers/{id}/stop` | POST | Arrêter | `containersApi.stop` | ✅ Couvert |
| `/docker/containers/{id}/restart` | POST | Redémarrer | `containersApi.restart` | ✅ Couvert |
| `/docker/containers/{id}` | DELETE | Supprimer | `containersApi.remove` | ✅ Couvert |
| `/docker/containers/{id}/shells` | GET | Shells disponibles | ❌ Absent | 🟡 À implémenter |
| `/docker/containers/{id}/stats` | GET | Stats snapshot | ❌ Absent (WebSocket utilisé) | ⚪ Optionnel |
| `/docker/containers/{id}/top` | GET | Processus container | ❌ Absent (WebSocket utilisé) | ⚪ Optionnel |
| `/docker/containers/{id}/logs` | GET | Logs container | `containersApi.getLogs` | ✅ Couvert |
| `/docker/containers/stats-batch` | POST | Stats CPU/MEM multi-containers en un appel | ❌ Absent | 🔴 À implémenter |

#### Docker Images (`backend/app/api/v1/docker.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/docker/images` | GET | Liste des images | ✅ `imagesApi.list` | ✅ Couvert (STORY-005) |
| `/docker/images/pull` | POST | Pull image | ❌ Absent | 🔴 À implémenter |
| `/docker/images/{id}` | DELETE | Supprimer image | ❌ Absent | 🔴 À implémenter |

#### Docker Volumes (`backend/app/api/v1/docker.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/docker/volumes` | GET | Liste des volumes | ❌ Absent | 🟡 À implémenter |
| `/docker/volumes` | POST | Créer volume | ❌ Absent | 🟡 À implémenter |
| `/docker/volumes/{name}` | DELETE | Supprimer volume | ❌ Absent | 🟡 À implémenter |

#### Docker Networks (`backend/app/api/v1/docker.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/docker/networks` | GET | Liste des réseaux | ❌ Absent | 🟡 À implémenter |

#### Docker System (`backend/app/api/v1/docker.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/docker/system/info` | GET | Infos système Docker | ❌ Absent | 🟢 Nice-to-have |
| `/docker/system/version` | GET | Version Docker | ❌ Absent | 🟢 Nice-to-have |
| `/docker/system/ping` | GET | Test connectivité | ❌ Absent | 🟢 Nice-to-have |

#### Import/Export Stacks (`backend/app/api/v1/import_export.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/stacks/{id}/export` | GET | Export stack JSON | ❌ Absent | 🔴 À implémenter |
| `/stacks/import` | POST | Import stack JSON | ❌ Absent | 🔴 À implémenter |

#### Deployments (`backend/app/api/v1/deployments.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/deployments/` | GET | Liste déploiements | `deploymentsApi.list` | ✅ Couvert |
| `/deployments/{id}` | GET | Détails déploiement | `deploymentsApi.get` | ✅ Couvert |
| `/deployments/` | POST | Créer déploiement | `deploymentsApi.create` | ✅ Couvert |
| `/deployments/{id}` | PUT | **Mettre à jour** | ❌ Absent | 🔴 À implémenter |
| `/deployments/{id}/retry` | POST | Retenter | `deploymentsApi.retry` | ✅ Couvert |
| `/deployments/{id}/cancel` | POST | Annuler | `deploymentsApi.cancel` | ✅ Couvert |
| `/deployments/{id}` | DELETE | Supprimer | `deploymentsApi.delete` | ✅ Couvert |
| `/deployments/{id}/logs` | GET | Logs déploiement | `deploymentsApi.getLogs` | ✅ Couvert |

#### Stats (`backend/app/api/v1/stats.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/stats/dashboard` | GET | Stats dashboard | `dashboardApi.getStats` | ✅ Couvert |
| `/stats/stacks/{id}` | GET | Stats détaillées stack | ❌ Absent | 🟡 À implémenter |

#### Stack Actions (Modèle Compute - `backend/app/api/v1/stacks.py`)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/stacks/{id}/start` | POST | Démarrer toute la stack | ❌ Absent | 🔴 À implémenter |
| `/stacks/{id}/stop` | POST | Arrêter toute la stack | ❌ Absent | 🔴 À implémenter |
| `/stacks/{id}/redeploy` | POST | Redéployer (pull images + recréation rolling/stop-start) | ❌ Absent | 🔴 À implémenter |
| `/stacks/{id}/duplicate` | POST | Dupliquer la stack | ❌ Absent | 🟡 À implémenter |
| `/stacks/{id}/archive` | POST | Archiver la stack | ✅ `stacksApi.archive` | ✅ Couvert (STORY-011) |
| `/stacks/{id}/sync-git` | POST | Mettre à jour depuis Git | ❌ Absent | 🟢 Nice-to-have |

#### Discovery & Adoption (Modèle Compute - `backend/app/api/v1/discovery.py`)

> **⚠️ Refactoring par rapport à la conception initiale** : Les endpoints `/discovery/containers` et `/discovery/compositions` sont remplacés par un endpoint unifié `/discovery/items` qui gère les 3 types (container, composition, helm_release). L'UI traite tous les objets découverts de façon homogène avec un simple badge technologie.

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| ~~`/discovery/containers`~~ | ~~GET~~ | ~~Remplacé par `/discovery/items`~~ | ~~❌ Absent~~ | ⛔ Remplacé |
| ~~`/discovery/compositions`~~ | ~~GET~~ | ~~Remplacé par `/discovery/items`~~ | ~~❌ Absent~~ | ⛔ Remplacé |
| `/discovery/items` | GET | Items découverts unifiés (container/compose/helm) avec filtres `?type=&target_id=` | ❌ Absent | 🔴 À implémenter |
| `/discovery/{type}/{id}/adoption-data` | GET | Données wizard adoption (type: container/composition/helm_release) | ❌ Absent | 🔴 À implémenter |
| `/discovery/adopt` | POST | Adopter un objet découvert (supporte helm_release + options Helm) | ❌ Absent | 🔴 À implémenter |

#### Container Promotion (Modèle Compute)

| Endpoint | Méthode | Description | Frontend | Statut |
|----------|---------|-------------|----------|--------|
| `/containers/{id}/promote` | POST | Promouvoir standalone en stack | ❌ Absent | 🟡 À implémenter |

---

### 📈 Résumé de la Couverture

| Catégorie | Total Endpoints | Couverts | À implémenter | Couverture |
|-----------|-----------------|----------|---------------|------------|
| **Compute Global** | **2** | **0** | **2** | **0%** |
| Containers | 12 | 7 | 5 | 58% |
| Images | 3 | 0 | 3 | 0% |
| Volumes | 3 | 0 | 3 | 0% |
| Networks | 1 | 0 | 1 | 0% |
| System | 3 | 0 | 3 | 0% |
| Import/Export | 2 | 0 | 2 | 0% |
| Deployments | 8 | 7 | 1 | 88% |
| Stats | 2 | 1 | 1 | 50% |
| **Stack Actions** | 6 | 0 | 6 | 0% |
| **Discovery & Adoption** | 3 | 0 | 3 | 0% |
| **Container Promotion** | 1 | 0 | 1 | 0% |
| **TOTAL** | **46** | **15** | **31** | **33%** |

> **Note** : L'intégration UI (image mockup `doc/screenshots/image1.png`) a conduit à :
> - +2 endpoints Compute Global (`/compute/stats`, `/compute/global`)
> - +1 endpoint stats batch containers (`/docker/containers/stats-batch`)
> - +1 endpoint stack redeploy (`/stacks/{id}/redeploy`)
> - Fusion des 2 endpoints discovery séparés en 1 endpoint unifié (`/discovery/items`)
> → Total passe de 43 à 46 endpoints, couverture de 35% à 33%

---

### 🖼️ État actuel des vues Frontend

| Vue | Fichier | État | API connectée |
|-----|---------|------|---------------|
| Containers | `views/Containers.vue` | ✅ Fonctionnel | `containersApi` |
| ContainerDetail | `views/ContainerDetail.vue` | ✅ Fonctionnel | `containersApi` |
| Images | `views/Images.vue` | ⚠️ **StubPage** | Aucune |
| Volumes | `views/Volumes.vue` | ⚠️ **StubPage** | Aucune |
| Networks | `views/Networks.vue` | ⚠️ **StubPage** | Aucune |
| Terminal | `views/Terminal.vue` | ✅ Fonctionnel | WebSocket |
| Deployments | `views/Deployments.vue` | ✅ Fonctionnel | `deploymentsApi` |
| Stacks | `views/Stacks.vue` | ✅ Fonctionnel | `stacksApi` |

**Note :** Les vues `Images.vue`, `Volumes.vue`, `Networks.vue` sont des `StubPage` (pages vides d'attente).

---

## Description
Cette epic vise à implémenter progressivement les interfaces frontend pour les APIs backend existantes, en priorisant les fonctionnalités les plus utiles pour les utilisateurs finaux. Les travaux sont classés en 3 vagues de priorité :

### 🔴 Priorité Haute (Core)
Fonctionnalités essentielles pour les opérations quotidiennes :
- **Gestion des images Docker** (liste, pull, suppression) - Vue `Images.vue` à implémenter
- **Export/Import de stacks** (partage et sauvegarde) - Intégration dans `Stacks.vue`
- **Édition à chaud des containers Compute** - Restart policy et limites ressources (les modifications avec recréation sont dans EPIC-009)

### 🟡 Priorité Moyenne (UX)
Améliorations de l'expérience utilisateur :
- **Gestion des volumes Docker** - Vue `Volumes.vue` à implémenter
- **Visualisation des réseaux Docker** - Vue `Networks.vue` à implémenter
- **Statistiques détaillées des stacks** - Nouvelle section dans détail stack
- **Détection des shells disponibles** - Amélioration du terminal
- **Informations système Docker** - Nouveau widget dashboard

### 🟢 Priorité Basse (Nice-to-have)
Fonctionnalités avancées :
- **Création manuelle de containers** - Formulaire avancé
- **Informations de version/ping Docker** - Page admin/système

---

## Liste des Stories liées

### 🔴 Priorité Haute

#### Modèle Compute - Vue Globale

- [x] STORY-001 : Backend — Endpoints Compute Stats et Global
- [x] STORY-021 : Frontend — Vue globale Compute avec bandeau et 3 sections
- [x] STORY-002 : Backend — Refactoring des services de listage Docker
- [x] STORY-022 : Frontend — Refactoring de Compute.vue en sous-composants
- [x] STORY-023 : Frontend — Harmonisation tables containers et actions en masse
- [x] STORY-003 : Wizard d'adoption d'objets découverts
- [x] STORY-004 : Actions globales de stack (Start/Stop/Redeploy)

#### Images Docker
- [x] STORY-005 : Gestion des images Docker - Liste et visualisation
- [x] STORY-006 : Gestion des images Docker - Pull et suppression
- [ ] STORY-031 : Images Docker — Sélection, actions en lot, usage et détail

#### Export/Import Stacks
- [x] STORY-007 : Export de stacks au format JSON
- [x] STORY-008 : Import de stacks depuis fichier JSON

#### Compute - Containers
- [x] STORY-009 : Édition à chaud des containers — Restart policy et limites ressources

### 🟡 Priorité Moyenne

#### Modèle Compute - Stack Management
- [x] STORY-010 : Duplication de stack
- [x] STORY-011 : Archivage de stack
- [x] STORY-012 : Promotion container standalone en stack

#### Volumes Docker
- [x] STORY-013 : Gestion des volumes Docker - Liste et création
- [x] STORY-014 : Gestion des volumes Docker - Suppression

#### Networks Docker
- [x] STORY-015 : Visualisation des réseaux Docker

#### Stats & Terminal
- [x] STORY-016 : Statistiques détaillées par stack
- [x] STORY-017 : Détection des shells disponibles dans le terminal
- [x] STORY-018 : Widget informations système Docker

### 🟢 Priorité Basse

- [ ] STORY-019 : Création manuelle de containers Docker
- [ ] STORY-020 : Page informations système Docker

---

## Types TypeScript à Ajouter

```typescript
// frontend/src/types/api.ts

// Docker Images
export interface ImageResponse {
  id: string
  repo_tags: string[]
  repo_digests: string[]
  created: string
  size: number
  virtual_size: number
  labels: Record<string, string>
}

export interface ImagePullRequest {
  name: string
  tag?: string
}

export interface ImagePullResponse {
  status: string
  id?: string
}

// Docker Volumes
export interface VolumeResponse {
  name: string
  driver: string
  mountpoint: string
  created_at: string
  labels: Record<string, string>
  scope: string
}

export interface VolumeCreateRequest {
  name: string
  driver?: string
  labels?: Record<string, string>
}

// Docker Networks
export interface NetworkResponse {
  id: string
  name: string
  driver: string
  scope: string
  internal: boolean
  attachable: boolean
  ingress: boolean
  created: string
  subnet?: string
  gateway?: string
}

// Docker System
export interface SystemInfoResponse {
  id: string
  name: string
  server_version: string
  containers: number
  containers_running: number
  containers_paused: number
  containers_stopped: number
  images: number
  driver: string
  docker_root_dir: string
  kernel_version: string
  operating_system: string
  os_type: string
  architecture: string
  cpus: number
  memory: number
}

export interface SystemVersionResponse {
  version: string
  api_version: string
  min_api_version: string
  git_commit: string
  go_version: string
  os: string
  arch: string
  kernel_version: string
  build_time: string
}

export interface PingResponse {
  available: boolean
  message: string
}

// Container Shells
export interface ContainerShell {
  path: string
  label: string
  available: boolean
}

// Stack Export/Import
export interface StackExportData {
  version: string
  stack: {
    name: string
    description?: string
    version: string
    category?: string
    tags: string[]
    template: string
    variables: Record<string, unknown>
    icon_url?: string
    screenshots: string[]
    documentation_url?: string
    author?: string
    license: string
  }
}

// Deployment Update
export interface DeploymentUpdate {
  name?: string
  configuration?: Record<string, unknown>
  environment_id?: string
}

// Stack Stats
export interface StackStatsResponse {
  deployments_by_status: Record<string, number>
  deployments_last_30_days: number
}

// ====== Modèle Compute ======

// Niveau de contrôle
export type ControlLevel = 'managed' | 'discovered' | 'standalone'

// Technologie compute
export type ComputeTechnology = 'docker' | 'compose' | 'helm' | 'kvm' | 'proxmox' | 'lxc'

// Container étendu (avec niveau de contrôle)
export interface ContainerWithControl {
  id: string
  name: string
  image: string
  status: string
  target_id: string
  target_name: string
  control_level: ControlLevel
  stack_id?: string
  stack_name?: string
}

// ------ Vue Globale Compute (/compute/global + /compute/stats) ------

// Statistiques globales affichées dans le bandeau header de la vue globale
export interface ComputeStatsResponse {
  total_containers: number       // "23 sur 4 machines"
  running_containers: number     // "18 healthy"
  stacks_count: number           // "3"
  stacks_services_count: number  // "9 services total"
  discovered_count: number       // "4 non managés"
  standalone_count: number       // "10 containers isolés"
  targets_count: number          // "sur 4 machines"
}

// Service individuel avec métriques inline (affiché dans les stacks expandées)
export interface ServiceWithMetrics {
  id: string
  name: string
  image: string
  status: string
  cpu_percent: number
  memory_usage: string    // ex: "540M"
  memory_limit?: string
}

// Stack avec services et métriques (utilisé par /compute/global)
export interface StackWithServices {
  id: string
  name: string
  technology: ComputeTechnology
  target_id: string
  target_name: string
  services_total: number       // ex: "3/3 running" → total
  services_running: number     // ex: "3/3 running" → running
  status: 'running' | 'partial' | 'stopped' | 'archived'
  services: ServiceWithMetrics[]
}

// Container standalone avec métriques (section Standalone de la vue globale)
export interface StandaloneContainer {
  id: string
  name: string
  image: string
  target_id: string
  target_name: string
  status: string
  cpu_percent: number
  memory_usage: string    // ex: "80M"
}

// Réponse de la vue globale unifiée
// group_by=stack : retourne les 3 sections (managed / discovered / standalone)
// group_by=target : retourne une liste de TargetGroup
export interface ComputeGlobalView {
  managed_stacks: StackWithServices[]
  discovered_items: DiscoveredItem[]
  standalone_containers: StandaloneContainer[]
}

// Vue groupée par machine (toggle "Par machine")
export interface TargetGroup {
  target_id: string
  target_name: string
  technology: string          // ex : "Docker Engine 26.1"
  stacks: StackWithServices[]
  discovered: DiscoveredItem[]
  standalone: StandaloneContainer[]
  metrics: {
    cpu_total_percent: number
    memory_used: string
    memory_total: string
  }
}

// ------ Stats batch containers (/docker/containers/stats-batch) ------

export interface ContainerStatSnapshot {
  container_id: string
  cpu_percent: number
  memory_usage: number     // en bytes
  memory_limit: number
  memory_percent: number
  timestamp: string
}

export type ContainerStatsBatchResponse = Record<string, ContainerStatSnapshot>

// ------ Stack étendue (avec statut agrégé) — utilisée dans d'autres vues ------
export interface StackWithStatus {
  id: string
  name: string
  description?: string
  status: 'running' | 'partial' | 'stopped' | 'archived'
  components_count: number
  components_running: number
  target_id: string
  target_name: string
}

// ------ Discovery - type unifié (/discovery/items) ------

// Service individuel dans un objet découvert (read-only)
export interface DiscoveredService {
  name: string
  image: string
  status: string
  cpu_percent?: number
  memory_usage?: string
}

// Item découvert unifié — remplace DiscoveredContainer + DiscoveredComposition
// L'UI les affiche de façon homogène avec un badge technologie
export interface DiscoveredItem {
  id: string
  name: string
  type: 'container' | 'composition' | 'helm_release'
  technology: ComputeTechnology
  source_path?: string           // ex: "/home/user/monitoring/docker-compose.yml"
  target_id: string
  target_name: string
  services_total: number         // ex: "2/2 running" → total
  services_running: number       // ex: "2/2 running" → running
  detected_at: string
  adoptable: boolean
  services: DiscoveredService[]  // Services individuels (read-only)
}

// Adoption - Requête (supporte container, composition ET helm_release)
export interface AdoptionRequest {
  discovered_id: string
  discovered_type: 'container' | 'composition' | 'helm_release'
  stack_name?: string             // nouvelle stack à créer
  stack_id?: string               // stack existante
  preserve_volumes: boolean
  preserve_networks: boolean
  // Spécifique Helm
  helm_namespace?: string
  helm_values_override?: Record<string, unknown>
}

// Adoption - Données du wizard
export interface AdoptionWizardData {
  // Étape 1 - Inventaire
  components: {
    name: string
    image: string
    env: Record<string, string>
    volumes: string[]
    networks: string[]
    ports: string[]
  }[]
  // Étape 2 - Mapping suggéré
  suggested_stack_name: string
  volume_strategy: 'preserve' | 'redeclare'
  network_strategy: 'preserve' | 'recreate'
  // Étape 3 - Preview
  generated_compose: string
}

// Stack Actions - Duplication
export interface StackDuplicateRequest {
  new_name: string
  target_id?: string  // optionnel: déployer sur autre target
}

// Stack Actions - Redéploiement
export interface StackRedeployRequest {
  strategy: 'rolling' | 'stop-start'
  pull_images: boolean
}

// Stack Actions - Réponse
export interface StackActionResponse {
  message: string
  stack_id: string
  action: 'started' | 'stopped' | 'redeployed' | 'duplicated' | 'archived'
}

// Container Promotion
export interface ContainerPromoteRequest {
  stack_name: string
}
```

---

## API Service à Étendre

```typescript
// frontend/src/services/api.ts - Ajouts nécessaires

// Docker Images API
export const imagesApi = {
  list: (all: boolean = false) =>
    http.get<ImageResponse[]>('/docker/images', { params: { all } }),

  pull: (data: ImagePullRequest) =>
    http.post<ImagePullResponse>('/docker/images/pull', data),

  remove: (imageId: string, force: boolean = false) =>
    http.delete<void>(`/docker/images/${imageId}`, { params: { force } }),
}

// Docker Volumes API
export const volumesApi = {
  list: () =>
    http.get<VolumeResponse[]>('/docker/volumes'),

  create: (data: VolumeCreateRequest) =>
    http.post<VolumeResponse>('/docker/volumes', data),

  remove: (name: string, force: boolean = false) =>
    http.delete<void>(`/docker/volumes/${name}`, { params: { force } }),
}

// Docker Networks API
export const networksApi = {
  list: () =>
    http.get<NetworkResponse[]>('/docker/networks'),
}

// Docker System API
export const dockerSystemApi = {
  info: () =>
    http.get<SystemInfoResponse>('/docker/system/info'),

  version: () =>
    http.get<SystemVersionResponse>('/docker/system/version'),

  ping: () =>
    http.get<PingResponse>('/docker/system/ping'),
}

// Container Shells API (extension containersApi)
export const containersApi = {
  // ... existing methods ...

  getShells: (id: string) =>
    http.get<ContainerShell[]>(`/docker/containers/${id}/shells`),
}

// Stack Export/Import API (extension stacksApi)
export const stacksApi = {
  // ... existing methods ...

  export: (id: string) =>
    http.get<StackExportData>(`/stacks/${id}/export`),

  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.post<{ message: string; stack_id: string; name: string }>(
      '/stacks/import',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
  },
}

// Deployment Update API (extension deploymentsApi)
export const deploymentsApi = {
  // ... existing methods ...

  update: (id: string, data: DeploymentUpdate) =>
    http.put<Deployment>(`/deployments/${id}`, data),
}

// Stats API (extension dashboardApi)
export const dashboardApi = {
  // ... existing methods ...

  getStackStats: (stackId: string) =>
    http.get<StackStatsResponse>(`/stats/stacks/${stackId}`),
}

// ====== Modèle Compute - Vue Globale ======
export const computeApi = {
  // Bandeau de stats header (total, running, stacks, discovered, standalone)
  getStats: () =>
    http.get<ComputeStatsResponse>('/compute/stats'),

  // Vue unifiée 3 sections avec filtres combinables
  // group_by='stack' (défaut) → ComputeGlobalView
  // group_by='target' → TargetGroup[]
  getGlobal: (params?: {
    type?: 'managed' | 'discovered' | 'standalone'
    technology?: ComputeTechnology
    target_id?: string
    status?: string
    search?: string
    group_by?: 'stack' | 'target'
  }) =>
    http.get<ComputeGlobalView | TargetGroup[]>('/compute/global', { params }),
}

// ====== Modèle Compute - Discovery API (endpoint unifié) ======
export const discoveryApi = {
  // Items découverts unifiés : containers orphelins + compositions + releases Helm
  getItems: (params?: {
    type?: 'container' | 'composition' | 'helm_release'
    target_id?: string
  }) =>
    http.get<DiscoveredItem[]>('/discovery/items', { params }),

  // Données du wizard d'adoption pour un item spécifique
  getAdoptionData: (
    discoveredId: string,
    type: 'container' | 'composition' | 'helm_release'
  ) =>
    http.get<AdoptionWizardData>(`/discovery/${type}/${discoveredId}/adoption-data`),

  // Adopter un objet découvert (container, composition ou release Helm)
  adopt: (data: AdoptionRequest) =>
    http.post<{ stack_id: string; message: string }>('/discovery/adopt', data),
}

// ====== Modèle Compute - Stack Actions API ======
export const stacksApi = {
  // ... existing methods (export, import) ...

  // Actions globales de stack
  start: (id: string) =>
    http.post<StackActionResponse>(`/stacks/${id}/start`),

  stop: (id: string) =>
    http.post<StackActionResponse>(`/stacks/${id}/stop`),

  // Redéploiement : pull images + recréation rolling ou stop-start
  redeploy: (id: string, data: StackRedeployRequest) =>
    http.post<StackActionResponse>(`/stacks/${id}/redeploy`, data),

  duplicate: (id: string, data: StackDuplicateRequest) =>
    http.post<{ stack_id: string; name: string }>(`/stacks/${id}/duplicate`, data),

  archive: (id: string) =>
    http.post<StackActionResponse>(`/stacks/${id}/archive`),

  syncGit: (id: string) =>
    http.post<{ message: string; changes: boolean }>(`/stacks/${id}/sync-git`),
}

// ====== Modèle Compute - Container Promotion API ======
export const containersApi = {
  // ... existing methods ...

  // Filtres étendus sur la liste
  list: (params?: {
    control_level?: 'standalone' | 'stack'
    stack_id?: string
    target_id?: string
  }) =>
    http.get<ContainerWithControl[]>('/docker/containers', { params }),

  // Stats batch pour plusieurs containers en un appel (évite N+1 requêtes)
  getStatsBatch: (containerIds: string[]) =>
    http.post<ContainerStatsBatchResponse>('/docker/containers/stats-batch', {
      container_ids: containerIds,
    }),

  promote: (id: string, data: ContainerPromoteRequest) =>
    http.post<{ stack_id: string }>(`/containers/${id}/promote`, data),
}
```

---

## Critères de succès (Definition of Done)
- [ ] Toutes les APIs backend documentées sont accessibles via le frontend
- [ ] Types TypeScript complets pour toutes les nouvelles entités
- [ ] Tests E2E couvrant les nouveaux flux utilisateur
- [ ] Documentation utilisateur mise à jour
- [ ] Pas de régression sur les fonctionnalités existantes
- [ ] Couverture de code frontend ≥ 80% pour les nouveaux composants

---

## Notes de conception

### Patterns à respecter
- Réutiliser les composants existants (tables `el-table`, formulaires `el-form`, dialogues `el-dialog`)
- Suivre les patterns établis dans `frontend/src/services/api.ts`
- Utiliser les WebSockets pour les données temps réel quand disponible
- Respecter le design system défini dans `doc/DESIGN-SYSTEM.md`

### Gestion d'erreurs
- Toast notifications via Element Plus pour les opérations
- Messages d'erreur contextualisés en français
- Retry automatique pour les erreurs transitoires

### Performance
- Pagination pour les listes longues (images, volumes)
- Debounce pour les recherches
- Cache pour les données statiques (networks, system info)

### Modèle Compute - Architecture Frontend

#### Structure de la vue Stacks (proposée)
```
┌─────────────────────────────────────────────────────────────┐
│  STACKS & COMPUTE                                           │
├─────────────────────────────────────────────────────────────┤
│  [Filtres: Type ▼] [Target ▼] [Statut ▼] [Recherche...]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📦 STACKS WINDFLOW (managées)                              │
│  ├── stack-a (compose · localhost) — 3/3 running           │
│  │   └── [Start] [Stop] [Export] [Duplicate] [Archive]     │
│  └── stack-b (helm · k8s-prod) — 5/5 running               │
│                                                             │
│  🔍 DISCOVERED (non managés, adoptables)                    │
│  ├── monitoring (compose · vps-ovh) — observé              │
│  │   └── [Adopter]                                         │
│  └── orphan-db (container · localhost)                     │
│      └── [Adopter]                                         │
│                                                             │
│  📍 STANDALONE (individuels)                                │
│  ├── traefik (container · localhost · running)             │
│  │   └── [Promouvoir en stack]                             │
│  └── pihole (container · pi4-home · running)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Composants à créer
- `AdoptionWizard.vue` : Wizard 3 étapes pour l'adoption d'objets découverts
- `StackActionsBar.vue` : Barre d'actions globales pour une stack
- `DiscoveredSection.vue` : Section d'affichage des objets découverts
- `StandaloneSection.vue` : Section d'affichage des containers standalone

#### Indicateurs visuels (badges)
- `managed` : Badge vert "Managé"
- `discovered` : Badge orange "Découvert" + badge "Adoptable"
- `standalone` : Badge bleu "Standalone"

---

## Risques et dépendances

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Volume de travail important | Moyen | Découper en stories fines et indépendantes |
| Breaking changes API | Faible | Versionner les types TypeScript |
| Duplication avec WebSocket | Moyen | Documenter ce qui est couvert par WS |
| Complexité UI images | Moyen | Commencer par liste simple, itérer |

### Dépendances
- **EPIC-002** (VM Management) : Pas de blocage, fonctionnalités indépendantes
- **Design System** : Respecter les guidelines existantes

---

## Historique des modifications

| Date | Modification | Auteur |
|------|--------------|--------|
| 2026-03-24 | Analyse UI mockup (`doc/screenshots/image1.png`) → +4 endpoints, refactoring discovery | Claude |
| 2026-03-24 | Intégration Modèle Compute : Discovery, Stack Actions, Promotion | Claude |
| 2026-03-24 | Analyse détaillée API Backend vs Frontend | Claude |
| 2026-03-23 | Création initiale de l'epic | Claude |

---

## Synthèse des modifications issues de l'analyse UI (`doc/screenshots/image1.png`)

L'image montre la **"Containers — vue globale"** avec 3 sections (Stacks WindFlow / Discovered / Standalone), un bandeau de statistiques et des filtres combinables. Cette UI a motivé les changements suivants :

| # | Changement | Justification UI |
|---|------------|-----------------|
| **+** `GET /compute/stats` | Bandeau de 5 métriques en haut (total/running/stacks/discovered/standalone/targets) |
| **+** `GET /compute/global` | Vue 3 sections unifiée ; toggle "Par machine" via `?group_by=target` |
| **+** `POST /docker/containers/stats-batch` | CPU% et mémoire affichés inline dans chaque ligne de la table (Standalone) et dans les services expandés (Stacks) — évite N+1 requêtes |
| **+** `POST /stacks/{id}/redeploy` | Icône refresh visible sur chaque stack Wind Flow dans la section managée |
| **↔** `/discovery/items` remplace `/discovery/containers` + `/discovery/compositions` | La section Discovered affiche de façon homogène : compose (monitoring), helm (app-backend) — même card, même interface |
| **↔** `AdoptionRequest.discovered_type` + `helm_release` | Le bouton "↗ Adopter" est présent sur app-backend (helm) — le type Helm doit être supporté |
| **↔** `GET /docker/containers` + filtres | La section Standalone nécessite de filtrer par `control_level=standalone` pour ne pas mélanger avec les containers de stacks |
| **+** `DiscoveredItem.source_path` | Message "Détecté via /home/user/monitoring/docker-compose.yml" affiché dans la card découverte |
| **+** `DiscoveredItem.services_total/running` | Compteur "2/2 running" dans le header de chaque card discovered |
| **+** `StackWithServices.services[]` | Services expandés avec IMAGE, STATUT, CPU (barre), MÉMOIRE directement dans la liste |
| **+** `TargetGroup` | Structure de réponse pour la vue "Par machine" (toggle en haut à droite) |
