# STORY-021 : Frontend — Vue globale Compute avec bandeau et 3 sections

**Statut :** DONE
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
- [x] AC 1 : Un bandeau en haut de la vue `/compute` affiche les 5 métriques clés (total containers, running, stacks, discovered, standalone) issues de `GET /compute/stats`
- [x] AC 2 : La vue affiche les 3 sections (📦 Stacks WindFlow / 🔍 Discovered / 📍 Standalone) alimentées par `GET /compute/global`
- [x] AC 3 : Des filtres (Type, Technologie, Target, Statut, Recherche) permettent de filtrer les données affichées côté frontend (ou via paramètres API)
- [x] AC 4 : Un toggle "Vue par machine" regroupe les données par target via `?group_by=target` et affiche un collapse par target
- [x] AC 5 : La vue est accessible depuis la sidebar (section INFRASTRUCTURE) et depuis la route `/compute`
- [x] AC 6 : Build, lint et tests frontend passent sans erreur

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
**Objectif :** Centraliser l'état compute (stats + vue globale + vue par target) dans un store Pinia réutilisable.
**Fichiers :**
- `frontend/src/stores/compute.ts` — Créer — Nouveau store Pinia (pattern : `stores/containers.ts`). Définir `useComputeStore` avec :
  - **State** :
    - `stats: Ref<ComputeStatsResponse | null>` — résultat de `/compute/stats`
    - `globalView: Ref<ComputeGlobalView | null>` — résultat de `getGlobal()` (mode normal)
    - `targetGroups: Ref<TargetGroup[]>` — résultat de `getGlobalByTarget()` (mode "Par machine")
    - `loading: Ref<boolean>` — chargement de la vue globale
    - `statsLoading: Ref<boolean>` — chargement des stats bandeau
    - `error: Ref<string | null>` — dernier message d'erreur
  - **Action `fetchStats(organizationId?: string): Promise<void>`** → appelle `computeApi.getStats(organizationId)`, stocke dans `stats`, gère `statsLoading` et `error` (pattern identique à `fetchContainers` dans containers.ts : try/catch/finally)
  - **Action `fetchGlobal(params?: { type?: ControlLevel; technology?: string; target_id?: string; status?: string; search?: string; organization_id?: string }): Promise<void>`** → appelle `computeApi.getGlobal(params)`, stocke dans `globalView`, gère `loading` + `error`, remet `targetGroups` à `[]`
  - **Action `fetchGlobalByTarget(params?: { type?: ControlLevel; technology?: string; target_id?: string; status?: string; search?: string; organization_id?: string }): Promise<void>`** → appelle `computeApi.getGlobalByTarget(params)`, stocke dans `targetGroups`, gère `loading` + `error`, remet `globalView` à `null`
  - **Action `$reset(): void`** → remet tous les états à leurs valeurs initiales (`null`, `[]`, `false`)
  - **Getters (computed)** :
    - `managedStacks` → `globalView.value?.managed_stacks ?? []`
    - `discoveredItems` → `globalView.value?.discovered_items ?? []`
    - `standaloneContainers` → `globalView.value?.standalone_containers ?? []`
  - Retourner tous les state, getters et actions dans le `return {}`
- `frontend/src/stores/index.ts` — Modifier — Ajouter la ligne `export { useComputeStore } from './compute'` à la suite des exports existants
**Dépend de :** Tâche 2

### Tâche 4 : Composant `ComputeStatsBanner.vue`
**Objectif :** Afficher le bandeau de 5 métriques synthétiques avec valeurs et sous-labels en haut de la vue Compute (fidèle au design de référence).
**Fichiers :**
- `frontend/src/components/ComputeStatsBanner.vue` — Créer — Nouveau composant (pattern : `ContainerStats.vue` pour la structure). Template :
  - Grille responsive 5 colonnes desktop / 2-3 mobile via UnoCSS : `class="grid grid-cols-2 md:grid-cols-5 gap-4"`
  - 5 `<el-card shadow="never">` avec label uppercase, valeur principale et sous-label secondaire :
    1. **CONTAINERS TOTAL** → valeur : `stats.total_containers` (noir) — sous-label : `"sur " + stats.targets_count + " machines"`
    2. **RUNNING** → valeur : `stats.running_containers` (vert si > 0, rouge si 0) — sous-label : `"healthy"`
    3. **STACKS WINDFLOW** → valeur : `stats.stacks_count` (bleu) — sous-label : `stats.stacks_services_count + " services total"`
    4. **DISCOVERED** → valeur : `stats.discovered_count` (orange si > 0, gris si 0) — sous-label : `"non managés"`
    5. **STANDALONE** → valeur : `stats.standalone_count` (noir) — sous-label : `"containers isolés"`
  - Structure HTML d'une carte :
    ```html
    <el-card shadow="never">
      <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">LABEL</div>
      <div class="text-3xl font-bold mt-1" :class="colorClass">{{ value }}</div>
      <div class="text-sm text-gray-400 mt-1">{{ subLabel }}</div>
    </el-card>
    ```
  - **Props** : `stats: ComputeStatsResponse | null`, `loading: boolean`
  - Si `loading === true` → afficher `v-loading` directive sur le conteneur de la grille
  - Si `stats === null && !loading` → afficher `<el-skeleton :rows="2" animated />` dans chaque carte (5 skeletons)
  - **Pas de `<script setup>` complexe** : pas de store direct, tout passe via props
**Dépend de :** Tâche 1

### Tâche 5 : Vue principale `Compute.vue`
**Objectif :** Assembler la vue complète fidèle au design de référence : header avec sous-titre + filtres pill-buttons + bandeau 5 métriques + 3 sections (Stacks accordion / Discovered avec Adopter / Standalone flat table) + mode "Par machine" + légende.
**Fichiers :**
- `frontend/src/views/Compute.vue` — Créer — Nouvelle vue (pattern structure : `Stacks.vue`). Structure complète :

  **A. Header de page**
  - Titre H1 : "Containers — vue globale"
  - Sous-titre dynamique : `"{{ stats.targets_count }} targets · {{ techCount }} technologies"` (techCount = nombre de technologies distinctes dans globalView)
  - Zone boutons droite : toggle `Tout` / `Par machine` (deux `el-button` type="primary"/"default" selon état de `groupByTarget`) + bouton `+ Déployer` (désactivé, prévu pour story future)

  **B. Barre de filtres (2 lignes de pills)**
  - Ligne 1 — Filtre Type (boutons radio pill) :
    - `Tout` | `● Stacks WindFlow` | `● Discovered (non managés)` | `● Standalone` (v-model `filterType : ControlLevel | 'all'`)
    - `el-radio-group` avec `el-radio-button` pour chaque option
    - Separator `|` visuel + `el-select` "Technologie" (v-model `filterTechnology`)
  - Ligne 2 — Pills technologie + pills target :
    - Pills technologie dynamiques (issues des données chargées) : `Docker`, `Compose`, `Helm / k8s` — sélection multiple (array `activeTechnologies`)
    - Prefix `Target :` + pills target dynamiques (issues de `targetsStore.targets`) : ex. `localhost`, `vps-ovh`, `pi4-home` — sélection multiple (array `activeTargets`)
    - Implémentation : `v-for` sur les valeurs distinctes + classes conditionnelles `selected` / `unselected`

  **C. Bandeau métriques**
  - `<ComputeStatsBanner :stats="computeStore.stats" :loading="computeStore.statsLoading" />`

  **D. Section "STACKS WINDFLOW" (accordion collapsible)**
  - En-tête section : indicateur bleu ◼ + texte "STACKS WINDFLOW (managées, source of truth dans WindFlow)"
  - Pour chaque stack dans `computeStore.managedStacks` : `<el-collapse-item>` avec :
    - **En-tête** : nom de la stack | `<el-tag type="primary" size="small">stack WindFlow</el-tag>` | `<el-tag>compose</el-tag>` | `<el-tag>● target_name</el-tag>` | `"X/Y running"` (vert si X===Y, orange si X<Y, rouge si X===0) | boutons : 📄 (copier) 🔄 (refresh) `Éditer stack`
    - **Corps déplié** : `<el-table>` avec colonnes :
      - SERVICE : indicateur ● vert/rouge + nom
      - IMAGE : texte
      - STATUT : `<el-tag>` coloré (running=vert, exited=rouge, etc.)
      - CPU : mini barre horizontale (UnoCSS `w-full bg-gray-200 rounded`) + `"X.X%"`
      - MÉMOIRE : `"540M"` (valeur de `service.memory_usage`)
      - ACTIONS : icônes 📄 (copier ID) et `>_` (ouvrir terminal, router vers `/terminal/:id`)
  - Si `managedStacks` vide et non-loading : `<el-empty description="Aucune stack WindFlow détectée" />`

  **E. Section "DISCOVERED — NON MANAGÉS"**
  - En-tête section : indicateur orange ◼ + texte "DISCOVERED — NON MANAGÉS (détectés sur la machine, WindFlow n'en est pas l'auteur)"
  - Pour chaque item dans `computeStore.discoveredItems` : `<el-collapse-item>` avec :
    - **En-tête** : nom | `<el-tag type="warning">discovered</el-tag>` | `<el-tag>tech</el-tag>` | `<el-tag>● target</el-tag>` | `"X/Y running"` | icône 👁 | `<el-button type="warning" size="small">↗ Adopter</el-button>` (si `item.adoptable`)
    - **Bandeau info** (si `item.source_path`) : `<el-alert type="warning" :closable="false">⚠ Détecté via {{ source_path }} — lecture seule. Adoptez pour gérer depuis WindFlow.</el-alert>`
    - **Corps déplié** : `<el-table>` des services (note : données partielles, lecture seule) avec colonnes :
      - NOM : `● vert/rouge` + nom + badge `(read-only)` en gris
      - IMAGE
      - STATUT
      - CPU : valeur en %
      - ACTIONS : icône 👁 uniquement (pas de contrôle)
  - Si `discoveredItems` vide et non-loading : `<el-empty description="Aucun objet découvert" />`

  **F. Section "STANDALONE"**
  - En-tête section : indicateur gris ◼ + texte "STANDALONE (containers individuels sans composition, créés directement)"
  - `<el-table>` plate (pas d'accordion) avec colonnes :
    - NOM : `● vert/rouge` selon statut + nom
    - IMAGE
    - TARGET : `<el-tag size="small">target_name</el-tag>`
    - STATUT : `<el-tag>` coloré
    - CPU / MÉM. : `"0.4% / 80M"` (concaténation de `cpu_percent + "% / " + memory_usage`)
    - ACTIONS : selon statut — si running : 📄 `>_` 🔄 ; si stopped : 🟢 (start) 🗑 (suppr, rouge)
  - Action start → `containersApi.start(id)` puis `fetchGlobal()` ; action remove → confirmation `ElMessageBox.confirm` puis `containersApi.remove(id)` puis `fetchGlobal()`

  **G. Mode "Par machine" (toggle groupByTarget)**
  - Conditionnel `v-if="groupByTarget"` sur tout le bloc D/E/F
  - `<el-collapse>` avec un `<el-collapse-item>` par `TargetGroup` :
    - Header : nom target + badge technologie + métriques agrégées `"CPU: X% | RAM: Y/Z"`
    - Contenu : sous-sections Stacks / Discovered / Standalone du groupe (même structure que D/E/F mais limitée à ce groupe)

  **H. Légende de bas de page**
  - `<div class="flex gap-6 mt-4 text-sm text-gray-500">` avec 3 entrées :
    - `◼ Stack WindFlow — géré, éditable` (carré bleu)
    - `◼ Discovered — observé, adoptable` (carré orange)
    - `◼ Standalone — container individuel géré` (carré gris)

  **I. Script setup**
  ```typescript
  const computeStore = useComputeStore()
  const targetsStore = useTargetsStore()
  const authStore = useAuthStore()

  const groupByTarget = ref(false)
  const filterType = ref<ControlLevel | 'all'>('all')
  const activeTechnologies = ref<string[]>([])
  const activeTargets = ref<string[]>([])
  const filterSearch = ref('')

  // Debounce 300ms sur filterSearch
  const debouncedSearch = useDebounce(filterSearch, 300)

  const filterParams = computed(() => ({
    type: filterType.value !== 'all' ? filterType.value : undefined,
    technology: activeTechnologies.value[0] ?? undefined,
    target_id: activeTargets.value[0] ?? undefined,
    search: debouncedSearch.value || undefined,
  }))

  onMounted(() => {
    computeStore.fetchStats(authStore.organizationId)
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: authStore.organizationId })
    targetsStore.fetchTargets({ organization_id: authStore.organizationId })
  })

  watch(filterParams, () => {
    if (!groupByTarget.value) {
      computeStore.fetchGlobal({ ...filterParams.value, organization_id: authStore.organizationId })
    } else {
      computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: authStore.organizationId })
    }
  })

  watch(groupByTarget, (val) => {
    if (val) {
      computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: authStore.organizationId })
    } else {
      computeStore.fetchGlobal({ ...filterParams.value, organization_id: authStore.organizationId })
    }
  })
  ```
  **Note** : `useDebounce` est importé depuis `@vueuse/core` (à vérifier dans `package.json` — si absent, implémenter manuellement avec `setTimeout`).

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

#### `frontend/tests/unit/stores/compute.spec.ts` — Créer
**Pattern** : `setActivePinia(createPinia())` + `vi.mock('@/services/api', () => ({ computeApi: { ... } }))` (comme le mock dans `Stacks.spec.ts` pour `stacksApi`).
Cas de test :
- `fetchStats()` appelle `computeApi.getStats()` et stocke le résultat dans `stats`
- `fetchStats()` avec rejet API → `error` est renseigné, `statsLoading` repasse à `false`
- `fetchGlobal()` appelle `computeApi.getGlobal()` et stocke dans `globalView`, remet `targetGroups` à `[]`
- `fetchGlobalByTarget()` appelle `computeApi.getGlobalByTarget()` et stocke dans `targetGroups`, remet `globalView` à `null`
- `fetchGlobal()` avec rejet API → `error` renseigné, `loading` repasse à `false`
- `$reset()` remet `stats`, `globalView`, `targetGroups`, `loading`, `error` à leurs valeurs initiales
- Getters `managedStacks`, `discoveredItems`, `standaloneContainers` retournent les bonnes sous-listes depuis `globalView`
- Getters retournent `[]` quand `globalView` est `null`

**Template de mock à utiliser au début du fichier :**
```typescript
vi.mock('@/services/api', () => ({
  computeApi: {
    getStats: vi.fn().mockResolvedValue({ data: { total_containers: 23, running_containers: 18, stacks_count: 3, stacks_services_count: 9, discovered_count: 4, standalone_count: 10, targets_count: 4 } }),
    getGlobal: vi.fn().mockResolvedValue({ data: { managed_stacks: [], discovered_items: [], standalone_containers: [] } }),
    getGlobalByTarget: vi.fn().mockResolvedValue({ data: [] }),
  },
}))
```

#### `frontend/tests/unit/components/ComputeStatsBanner.spec.ts` — Créer
**Pattern** : `mount()` avec stubs Element Plus (comme `Stacks.spec.ts`).
Cas de test :
- Props `stats = null, loading = false` → 5 blocs `el-skeleton` présents
- Props `stats = null, loading = true` → directive `v-loading` présente sur le conteneur
- Props `stats = mockStats, loading = false` → affiche les 5 valeurs numériques correctes (total_containers, running_containers, stacks_count, discovered_count, standalone_count)
- Sous-label "sur 4 machines" affiché quand `stats.targets_count = 4`
- Valeur RUNNING en classe verte si `running_containers > 0`
- Valeur DISCOVERED en classe orange si `discovered_count > 0`

#### `frontend/tests/unit/views/Compute.spec.ts` — Créer
**Pattern** : mock stores + mock API + mock router + mock Element Plus (comme `Stacks.spec.ts`).
Cas de test :
- `onMounted` appelle `fetchStats()` et `fetchGlobal()` du store mocké
- Toggle `groupByTarget` passe à `true` → appelle `fetchGlobalByTarget()` (pas `fetchGlobal()`)
- Toggle `groupByTarget` repasse à `false` → rappelle `fetchGlobal()`
- Section Discovered : affichage `el-empty` quand `discoveredItems = []`
- Header contient le texte "vue globale" et le sous-titre avec targets_count
- Bouton "Éditer stack" présent dans la section Stacks quand `managedStacks` non vide

**Template de mock stores :**
```typescript
vi.mock('@/stores', () => ({
  useComputeStore: () => ({
    stats: null,
    statsLoading: false,
    globalView: null,
    targetGroups: [],
    loading: false,
    managedStacks: [],
    discoveredItems: [],
    standaloneContainers: [],
    fetchStats: vi.fn(),
    fetchGlobal: vi.fn(),
    fetchGlobalByTarget: vi.fn(),
  }),
  useTargetsStore: () => ({
    targets: [],
    fetchTargets: vi.fn(),
  }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ organizationId: 'test-org' }),
}))
```

### Commandes de validation
```bash
# Tests unitaires frontend
cd frontend && pnpm test -- tests/unit/stores/compute
cd frontend && pnpm test -- tests/unit/components/ComputeStatsBanner
cd frontend && pnpm test -- tests/unit/views/Compute
# Vérifier que les tests existants ne régressent pas
cd frontend && pnpm test
# Build & lint
cd frontend && pnpm build
cd frontend && pnpm lint
# TypeScript check
cd frontend && pnpm typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Types TypeScript Compute (types/api.ts)
- [x] Tâche 2 : Service API computeApi (services/api.ts)
- [x] Tâche 3 : Store Pinia useComputeStore (stores/compute.ts + index.ts)
- [x] Tâche 4 : Composant ComputeStatsBanner.vue
- [x] Tâche 5 : Vue Compute.vue (bandeau + filtres + 3 sections + toggle)
- [x] Tâche 6 : Route /compute + Sidebar lien
- [x] Tests frontend (stores + composant + vue) — 34 tests, 3 fichiers
- [x] Build & lint OK

## Notes d'implémentation

### Fichiers créés
- `frontend/src/types/api.ts` — Ajout de 10 types/interfaces Compute à la fin du fichier
- `frontend/src/services/api.ts` — Ajout de `computeApi` (3 méthodes) + `compute: computeApi` dans le default export
- `frontend/src/stores/compute.ts` — Nouveau store Pinia avec state, getters, 4 actions
- `frontend/src/stores/index.ts` — Export `useComputeStore` ajouté
- `frontend/src/components/ComputeStatsBanner.vue` — Nouveau composant bandeau 5 métriques
- `frontend/src/views/Compute.vue` — Nouvelle vue complète avec header, filtres, bandeau, 3 sections, mode par machine, légende
- `frontend/src/router/index.ts` — Route `compute` ajoutée après `stacks`
- `frontend/src/components/SidebarNav.vue` — Item `Compute` avec icône `DataAnalysis` ajouté dans `infrastructureItems`
- `frontend/tests/unit/stores/compute.spec.ts` — 16 tests (store actions, getters, edge cases)
- `frontend/tests/unit/components/ComputeStatsBanner.spec.ts` — 10 tests (skeleton, loading, valeurs, couleurs)
- `frontend/tests/unit/views/Compute.spec.ts` — 9 tests (montage, onMounted, toggle, sections, légende)

### Décisions techniques prises
1. **Deux méthodes API séparées** (`getGlobal` vs `getGlobalByTarget`) au lieu d'une avec union type — évite le type unsafe `ComputeGlobalView | TargetGroup[]` dans le store
2. **Debounce manuel** (ref + watch + window.setTimeout) — `@vueuse/core` absent du projet
3. **`window.setTimeout` / `window.clearTimeout` / `window.navigator`** — globals browser non déclarés dans ESLint config (seuls `console`, `window`, `document` sont listés) ; résolu en préfixant par `window.`
4. **`authStore.organizationId` traité avec `?? undefined`** — `ComputedRef<string | null>` converti en `string | undefined` attendu par l'API
5. **Tests vi.mock hoisting** — mock data inlinée directement dans la factory (pas de variables top-level référencées dans vi.mock)

### Divergences par rapport à l'analyse
- `@vueuse/core` absent → debounce implémenté manuellement
- `targetsStore.fetchTargets(orgId?)` prend une string directe (pas un objet) — adapté en conséquence
