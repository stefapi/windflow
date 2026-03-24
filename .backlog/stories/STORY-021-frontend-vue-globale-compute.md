# STORY-021 : Frontend — Vue globale Compute avec bandeau et 3 sections

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux accéder à une vue `/compute` qui affiche un bandeau de métriques synthétiques et les 3 sections (Stacks WindFlow / Discovered / Standalone) avec filtres et toggle "Par machine", afin d'avoir une vision unifiée de l'ensemble des ressources compute sur toutes mes machines cibles.

## Contexte technique
- Couche **frontend uniquement**. Les endpoints backend sont créés dans STORY-001.
- APIs consommées : `GET /compute/stats`, `GET /compute/global`
- Types TypeScript à ajouter dans `frontend/src/types/api.ts`
- Nouveau service `computeApi` à ajouter dans `frontend/src/services/api.ts`
- Nouveau store Pinia `useComputeStore` dans `frontend/src/stores/compute.ts`
- Nouveau composant `ComputeStatsBanner.vue` (bandeau 5 métriques)
- Nouvelle vue `Compute.vue` (3 sections + filtres + toggle par machine)
- Fichiers de référence pour patterns :
  - Store : `frontend/src/stores/containers.ts` (Pinia Composition API)
  - Vue : `frontend/src/views/Stacks.vue` (el-card, el-table, el-dialog)
  - Composant stats : `frontend/src/components/ContainerStats.vue`
  - Service API : `frontend/src/services/api.ts` (pattern `containersApi`)

## Critères d'acceptation (AC)
- [ ] AC 1 : Un bandeau en haut de la vue `/compute` affiche les 5 métriques clés (total containers, running, stacks, discovered, standalone) issues de `GET /compute/stats`
- [ ] AC 2 : La vue affiche les 3 sections (📦 Stacks WindFlow / 🔍 Discovered / 📍 Standalone) alimentées par `GET /compute/global`
- [ ] AC 3 : Des filtres (Type, Technologie, Target, Statut, Recherche) permettent de filtrer les données affichées côté frontend (ou via paramètres API)
- [ ] AC 4 : Un toggle "Vue par machine" regroupe les données par target via `?group_by=target` et affiche un collapse par target
- [ ] AC 5 : La vue est accessible depuis la sidebar (section INFRASTRUCTURE) et depuis la route `/compute`
- [ ] AC 6 : Build, lint et tests frontend passent sans erreur

## Dépendances
- **STORY-001** : Endpoints backend `/compute/stats` et `/compute/global` (pré-requis)

## Tâches d'implémentation détaillées

### Tâche 1 : Types TypeScript Compute
**Objectif :** Ajouter les interfaces TypeScript qui reflètent les schemas Pydantic backend du module compute.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter à la fin du fichier les interfaces suivantes (issues de EPIC-008 section "Types TypeScript à Ajouter") :
  - `export type ControlLevel = 'managed' | 'discovered' | 'standalone'`
  - `export type ComputeTechnology = 'docker' | 'compose' | 'helm' | 'kvm' | 'proxmox' | 'lxc'`
  - `export interface ServiceWithMetrics { id: string; name: string; image: string; status: string; cpu_percent: number; memory_usage: string; memory_limit?: string }`
  - `export interface StackWithServices { id: string; name: string; technology: ComputeTechnology; target_id: string; target_name: string; services_total: number; services_running: number; status: 'running' | 'partial' | 'stopped' | 'archived'; services: ServiceWithMetrics[] }`
  - `export interface StandaloneContainer { id: string; name: string; image: string; target_id: string; target_name: string; status: string; cpu_percent: number; memory_usage: string }`
  - `export interface DiscoveredItem { id: string; name: string; type: 'container' | 'composition' | 'helm_release'; technology: ComputeTechnology; source_path?: string; target_id: string; target_name: string; services_total: number; services_running: number; detected_at: string; adoptable: boolean }`
  - `export interface ComputeGlobalView { managed_stacks: StackWithServices[]; discovered_items: DiscoveredItem[]; standalone_containers: StandaloneContainer[] }`
  - `export interface TargetMetrics { cpu_total_percent: number; memory_used: string; memory_total: string }`
  - `export interface TargetGroup { target_id: string; target_name: string; technology: string; stacks: StackWithServices[]; discovered: DiscoveredItem[]; standalone: StandaloneContainer[]; metrics: TargetMetrics }`
  - `export interface ComputeStatsResponse { total_containers: number; running_containers: number; stacks_count: number; stacks_services_count: number; discovered_count: number; standalone_count: number; targets_count: number }`
**Dépend de :** Aucune

### Tâche 2 : Service API frontend `computeApi`
**Objectif :** Exposer les appels HTTP vers les endpoints compute dans la couche service API, avec un typage clair pour chaque mode de réponse.
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier — Ajouter les imports des nouveaux types (`ComputeStatsResponse`, `ComputeGlobalView`, `TargetGroup`, `ComputeTechnology`) dans le bloc d'imports depuis `@/types/api`. Puis ajouter l'objet `computeApi` juste avant le `export default` (après `containersApi`) :
  ```typescript
  export const computeApi = {
    getStats: (organizationId?: string) =>
      http.get<ComputeStatsResponse>('/compute/stats', {
        params: organizationId ? { organization_id: organizationId } : {},
      }),

    // Retourne ComputeGlobalView quand group_by est absent ou 'stack'
    getGlobal: (params?: {
      type?: ControlLevel
      technology?: string
      target_id?: string
      status?: string
      search?: string
      organization_id?: string
    }) =>
      http.get<ComputeGlobalView>('/compute/global', { params }),

    // Retourne TargetGroup[] quand group_by='target'
    getGlobalByTarget: (params?: {
      type?: ControlLevel
      technology?: string
      target_id?: string
      status?: string
      search?: string
      organization_id?: string
    }) =>
      http.get<TargetGroup[]>('/compute/global', {
        params: { ...params, group_by: 'target' },
      }),
  }
  ```
  **Note** : Deux méthodes séparées (`getGlobal` et `getGlobalByTarget`) évitent le type union ambigu `ComputeGlobalView | TargetGroup[]` — le store appellera l'une ou l'autre selon le toggle "Par machine".

  Ajouter également `import type { ControlLevel } from '@/types/api'` à la liste des imports existants.  
  Ajouter `compute: computeApi` dans le `export default {}` final.
**Dépend de :** Tâche 1

### Tâche 3 : Store Pinia `useComputeStore`
**Objectif :** Centraliser l'état compute (stats + vue globale) dans un store Pinia réutilisable.
**Fichiers :**
- `frontend/src/stores/compute.ts` — Créer — Nouveau store Pinia (pattern : `stores/containers.ts`). Définir `useComputeStore` avec :
  - State : `stats: Ref<ComputeStatsResponse | null>`, `globalView: Ref<ComputeGlobalView | null>`, `targetGroups: Ref<TargetGroup[]>`, `loading: Ref<boolean>`, `statsLoading: Ref<boolean>`, `error: Ref<string | null>`
  - Action `fetchStats(organizationId?: string): Promise<void>` → appelle `computeApi.getStats()`, stocke dans `stats`, gère `statsLoading` + `error`
  - Action `fetchGlobal(params?: parameters de computeApi.getGlobal): Promise<void>` → appelle `computeApi.getGlobal(params)`, si `group_by=target` stocke dans `targetGroups`, sinon stocke dans `globalView`, gère `loading` + `error`
  - Action `$reset(): void` → remet tous les états à leurs valeurs initiales
  - Getters `managedStacks` (computed depuis `globalView`), `discoveredItems`, `standaloneContainers`
- `frontend/src/stores/index.ts` — Modifier — Ajouter `export { useComputeStore } from './compute'`
**Dépend de :** Tâche 2

### Tâche 4 : Composant `ComputeStatsBanner.vue`
**Objectif :** Afficher le bandeau de 5 métriques synthétiques en haut de la vue Compute.
**Fichiers :**
- `frontend/src/components/ComputeStatsBanner.vue` — Créer — Nouveau composant (pattern : `ContainerStats.vue` pour la structure, `el-statistic` d'Element Plus pour les métriques). Template :
  - Grille responsive (5 colonnes sur desktop, 2-3 sur mobile) via UnoCSS (`grid grid-cols-2 md:grid-cols-5 gap-4`)
  - 5 `<el-card>` avec `<el-statistic>` chacune :
    1. "Total Containers" → `stats.total_containers`
    2. "Running" → `stats.running_containers` (couleur verte si > 0)
    3. "Stacks" → `stats.stacks_count` avec sous-titre `stats.stacks_services_count + " services"`
    4. "Discovered" → `stats.discovered_count` (couleur orange si > 0)
    5. "Standalone" → `stats.standalone_count`
  - Afficher `span` "sur N machines" sous "Total Containers" via `stats.targets_count`
  - Props: `stats: ComputeStatsResponse | null`, `loading: boolean`
  - Si `loading === true`, afficher `v-loading` sur la grille
  - Si `stats === null`, afficher `el-skeleton` (5 blocs)
**Dépend de :** Tâche 1

### Tâche 5 : Vue principale `Compute.vue`
**Objectif :** Assembler la vue complète : bandeau + barre de filtres + 3 sections (stacks managées / discovered / standalone) + toggle par machine.
**Fichiers :**
- `frontend/src/views/Compute.vue` — Créer — Nouvelle vue (pattern structure : `Stacks.vue`). Sections :
  1. **Bandeau** : `<ComputeStatsBanner :stats="computeStore.stats" :loading="computeStore.statsLoading" />`
  2. **Barre de filtres** : `el-row` avec :
     - `el-select` "Type" → options : Tous / Stacks managées / Discovered / Standalone ; v-model `filterType`
     - `el-select` "Technologie" → options : Toutes / docker / compose / helm ; v-model `filterTechnology`
     - `el-select` "Target" → options issues de `targetsStore.targets` ; v-model `filterTargetId`
     - `el-select` "Statut" → options : Tous / running / stopped / partial / archived ; v-model `filterStatus`
     - `el-input` placeholder "Rechercher..." v-model `filterSearch` avec debounce 300ms
     - `el-switch` label "Par machine" v-model `groupByTarget`
  3. **Mode "Par machine"** (si `groupByTarget === true`) : `el-collapse` avec un `el-collapse-item` par `TargetGroup` :
     - Header : nom de la target + badge technologie + métriques CPU/RAM
     - Contenu : `el-table` des stacks + discovered + standalone du groupe
  4. **Mode normal** (3 sections) :
     - Section "📦 Stacks WindFlow" : `el-card` + `el-table` avec colonnes : Nom, Technologie (badge), Target, Services (X/Y), Statut (`StatusBadge`)
     - Section "🔍 Discovered" : `el-card` + `el-empty` description "Chargé par STORY-002" (stub pour STORY-021)
     - Section "📍 Standalone" : `el-card` + `el-table` avec colonnes : Nom, Image, Target, Statut, CPU%, Mémoire
  - Script setup :
    - `useComputeStore()`, `useTargetsStore()`, `useAuthStore()`
    - `onMounted` → appelle `computeStore.fetchStats()` + `computeStore.fetchGlobal(filtersReactifs)`
    - `watch` sur les filtres (debounced) → rappelle `computeStore.fetchGlobal(...)` avec les nouveaux filtres
    - `watch` sur `groupByTarget` → appelle `fetchGlobal({ group_by: groupByTarget ? 'target' : 'stack', ... })`
    - Computed `filteredStacks`, `filteredStandalone` (filtres appliqués localement aussi pour réactivité immédiate)
**Dépend de :** Tâche 3, Tâche 4

### Tâche 6 : Route et Sidebar
**Objectif :** Rendre la vue accessible depuis l'URL `/compute` et depuis la navigation latérale.
**Fichiers :**
- `frontend/src/router/index.ts` — Modifier — Dans le tableau `children` de la route principale (`/`), ajouter après la route `stacks` :
  ```
  {
    path: 'compute',
    name: 'Compute',
    component: () => import('@/views/Compute.vue'),
  },
  ```
- `frontend/src/components/SidebarNav.vue` — Modifier — Dans le `<script setup>` :
  - Ajouter `DataAnalysis` à la liste des imports depuis `@element-plus/icons-vue`
  - Dans le tableau `infrastructureItems`, ajouter après l'item `Stacks` : `{ icon: DataAnalysis, label: 'Compute', path: '/compute' }`
**Dépend de :** Tâche 5

## Tests à écrire

### Frontend
- `frontend/tests/unit/stores/compute.spec.ts` — Créer — Tester :
  - `fetchStats()` appelle `computeApi.getStats()` et stocke le résultat dans `stats`
  - `fetchStats()` gère une erreur API → `error` est renseigné
  - `fetchGlobal({ group_by: 'stack' })` stocke dans `globalView`
  - `fetchGlobal({ group_by: 'target' })` stocke dans `targetGroups`
  - `$reset()` remet tous les états à vide
- `frontend/tests/unit/components/ComputeStatsBanner.spec.ts` — Créer — Tester :
  - Rendu avec `stats = null` → affiche 5 skeletons
  - Rendu avec `loading = true` → directive `v-loading` présente
  - Rendu avec stats valides → affiche les 5 valeurs correctes
  - Le sous-titre "sur N machines" affiche `stats.targets_count`
- `frontend/tests/unit/views/Compute.spec.ts` — Créer — Tester :
  - `onMounted` appelle `fetchStats()` et `fetchGlobal()`
  - Le toggle "Par machine" déclenche `fetchGlobal({ group_by: 'target' })`
  - La section "🔍 Discovered" affiche `el-empty` (stub)
  - Le filtre de recherche déclenche `fetchGlobal` avec `search` param (debounce)

### Commandes de validation
```bash
# Tests unitaires frontend
cd frontend && pnpm test -- tests/unit/stores/compute
cd frontend && pnpm test -- tests/unit/components/ComputeStatsBanner
cd frontend && pnpm test -- tests/unit/views/Compute
# Build & lint
cd frontend && pnpm build
cd frontend && pnpm lint
# TypeScript check
cd frontend && pnpm typecheck
```

## État d'avancement technique
- [ ] Tâche 1 : Types TypeScript Compute (types/api.ts)
- [ ] Tâche 2 : Service API computeApi (services/api.ts)
- [ ] Tâche 3 : Store Pinia useComputeStore (stores/compute.ts + index.ts)
- [ ] Tâche 4 : Composant ComputeStatsBanner.vue
- [ ] Tâche 5 : Vue Compute.vue (bandeau + filtres + 3 sections + toggle)
- [ ] Tâche 6 : Route /compute + Sidebar lien
- [ ] Tests frontend (stores + composant + vue)
- [ ] Build & lint OK
