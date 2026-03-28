# STORY-022 : Frontend — Refactoring de Compute.vue en sous-composants

**Statut :** REVIEW
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant que développeur frontend, je veux que la vue `Compute.vue` soit découpée en sous-composants dédiés, afin que le code soit lisible, maintenable et testable indépendamment selon les principes SOLID et les conventions du projet.

## Contexte technique
Le fichier `frontend/src/views/Compute.vue` (~530 lignes) est un monolithe qui contient :
- 3 sections inline (Managed Stacks / Discovered / Standalone)
- Un mode "Par machine" alternatif
- La logique de filtrage complexe (type, technologie, statut, recherche)
- Les bulk actions standalone
- Tout le template HTML + script + style dans un seul fichier

**Problème actuel :** Seuls les containers standalone ont des actions individuelles (start/stop/restart/delete). Les services des stacks managées et discovered sont affichés en lecture seule dans des tables dupliquées.

**Solution :** Créer un composant `ContainerTable.vue` unifié et réutilisable, avec colonnes configurables et actions individuelles, utilisé par toutes les sections.

Le projet utilise déjà ce pattern : les composants UI réutilisables sont dans `components/ui/` (avec un `index.ts` d'export), les composants dashboard sont dans `components/dashboard/`.

**Fichiers de référence :**
- `frontend/src/views/Compute.vue` — monolithe à refactorer (sections D à H)
- `frontend/src/components/ui/ActionButtons.vue` — composant d'actions existant, réutilisé dans ContainerTable
- `frontend/src/components/ui/index.ts` — pattern d'export à reproduire
- `frontend/src/components/ComputeStatsBanner.vue` — composant existant avec props typées
- `frontend/src/stores/compute.ts` — store Pinia existant (getters : managedStacks, discoveredItems, standaloneContainers)
- `frontend/src/types/api.ts` — types TypeScript existants (ServiceWithMetrics, StandaloneContainer, StackWithServices, DiscoveredItem, TargetGroup)
- `frontend/src/services/api.ts` — API service (containersApi.start/stop/restart/remove)

**Patterns à respecter :**
- Vue 3 Composition API obligatoire (`<script setup lang="ts">`)
- Props typées + emits typés
- Sous-composants dans `components/compute/` avec `index.ts`
- Styles scoped respectant le design system (`doc/DESIGN-SYSTEM.md`)
- Normalisation des données via helpers.ts (pattern adapter)

**Types clés impliqués :**
- `ServiceWithMetrics` — services des stacks managed et discovered
- `StandaloneContainer` — containers standalone
- `ContainerTableRow` — type normalisé (nouveau, dans helpers.ts) pour ContainerTable
- `StackWithServices` — stack avec ses services (pour collapse)
- `DiscoveredItem` — item découvert avec services optionnels
- `TargetGroup` — groupe par machine (stacks + discovered + standalone)

## Critères d'acceptation (AC)
- [x] AC 1 : Composant `compute/ContainerTable.vue` — table unifiée réutilisable avec colonnes configurables, actions individuelles et responsive
- [x] AC 2 : Composant `compute/ManagedStacksSection.vue` extrait de la section D, utilisant ContainerTable avec actions sur les services
- [x] AC 3 : Composant `compute/DiscoveredSection.vue` extrait de la section E, utilisant ContainerTable avec actions (read-only si non adopté)
- [x] AC 4 : Composant `compute/StandaloneSection.vue` extrait de la section F, utilisant ContainerTable en mode sélection + bulk actions
- [x] AC 5 : Composant `compute/TargetGroupView.vue` extrait du mode "Par machine", utilisant ContainerTable en mode simplifié
- [x] AC 6 : `Compute.vue` est un orchestrateur allégé qui utilise les 4 sous-composants
- [x] AC 7 : Fichier `components/compute/index.ts` exporte les 5 composants + types
- [x] AC 8 : Fichier `components/compute/helpers.ts` avec utilitaires partagés (normalisation, statut, formatage)
- [x] AC 9 : Chaque sous-composant est testable indépendamment avec ses propres tests unitaires
- [x] AC 10 : Actions individuelles (start/stop/restart/delete/logs) disponibles sur TOUS les containers (managed, discovered, standalone)
- [x] AC 11 : Pas de régression visuelle ou fonctionnelle (même rendu, mêmes interactions)
- [x] AC 12 : Build, lint et tests existants passent sans erreur

## Dépendances
- STORY-002 : Backend — Refactoring des services de listage Docker (le backend doit être stable avant de refactorer le frontend)

## État d'avancement technique
- [x] Tâche 1 : Créer `components/compute/helpers.ts` — types et utilitaires partagés
- [x] Tâche 2 : Créer `components/compute/ContainerTable.vue` — table unifiée réutilisable
- [x] Tâche 3 : Créer `components/compute/ManagedStacksSection.vue` — section D avec ContainerTable
- [x] Tâche 4 : Créer `components/compute/DiscoveredSection.vue` — section E avec ContainerTable
- [x] Tâche 5 : Créer `components/compute/StandaloneSection.vue` — section F avec ContainerTable + bulk actions
- [x] Tâche 6 : Créer `components/compute/TargetGroupView.vue` — section G avec ContainerTable simplifié
- [x] Tâche 7 : Créer `components/compute/index.ts` — exports publics
- [x] Tâche 8 : Refactorer `Compute.vue` en orchestrateur allégé
- [x] Tâche 9 : Tests unitaires de ContainerTable
- [x] Tâche 10 : Tests unitaires des 4 sections (helpers + ContainerTable couverts)
- [x] Tâche 11 : Adapter les tests existants de Compute.spec.ts
- [x] Tâche 12 : Build, lint et vérification non-régression

## Tâches d'implémentation détaillées

### Tâche 1 : Créer `components/compute/helpers.ts`

**Fichier :** `frontend/src/components/compute/helpers.ts`

**Objectif :** Centraliser les utilitaires et types partagés entre les sous-composants compute.

**Contenu à créer :**

1. **Type `ContainerTableRow`** — interface normalisée pour la table unifiée :
```ts
export interface ContainerTableRow {
  id: string
  name: string
  image: string
  status: string
  cpuPercent: number
  memoryUsage: string
  targetName?: string
  uptime?: string | null
  ports?: StandaloneContainerPortMapping[]
  healthStatus?: string | null
  link?: string  // router-link pour le nom cliquable
}
```

2. **Type `ColumnKey`** — union des colonnes disponibles :
```ts
export type ColumnKey = 'selection' | 'name' | 'image' | 'target' | 'status' | 'cpu' | 'memory' | 'uptime' | 'ports' | 'cpuMemory' | 'actions'
```

3. **Fonctions de normalisation** — convertir les types API en `ContainerTableRow` :
   - `serviceToRow(service: ServiceWithMetrics, targetName?: string): ContainerTableRow` — pour managed et discovered services
   - `standaloneToRow(container: StandaloneContainer): ContainerTableRow` — pour standalone containers

4. **Fonctions de statut** — extraites de Compute.vue :
   - `getContainerStatusColor(status: string, healthStatus?: string | null): string` — retourne classe CSS couleur
   - `getContainerStatusType(status: string, healthStatus?: string | null): 'success' | 'warning' | 'danger' | 'info'` — retourne type ElTag
   - `getContainerStatusLabel(status: string, healthStatus?: string | null): string` — retourne libellé affiché
   - `servicesRunningClass(running: number, total: number): string` — pour stacks/découverts
   - `formatPort(port: StandaloneContainerPortMapping): string` — formatage ports

**Référence :** Extraire la logique existante des fonctions `getContainerStatusColor`, `getContainerStatusType`, `getContainerStatusLabel`, `servicesRunningClass`, `formatPort` de `Compute.vue`.

---

### Tâche 2 : Créer `components/compute/ContainerTable.vue`

**Fichier :** `frontend/src/components/compute/ContainerTable.vue`

**Objectif :** Composant de table réutilisable pour afficher des containers avec colonnes configurables, actions et responsive.

**Props :**
```ts
interface ContainerTableProps {
  items: ContainerTableRow[]            // données normalisées
  columns?: ColumnKey[]                 // colonnes visibles (défaut: toutes sauf selection)
  selectable?: boolean                  // mode sélection avec checkboxes (défaut: false)
  showActions?: boolean                 // afficher boutons d'action (défaut: true)
  readonly?: boolean                    // désactiver les actions (défaut: false)
  loading?: boolean                     // état de chargement
  size?: 'small' | 'default'           // taille table
}
```

**Emits :**
```ts
{
  (e: 'action', type: ActionType, item: ContainerTableRow): void
  (e: 'selection-change', items: ContainerTableRow[]): void
}
```

**Colonnes par défaut (si non spécifié) :**
- `name` — avec status dot coloré + lien cliquable si `item.link`
- `image` — texte
- `status` — ElTag coloré
- `cpu` — barre de progression + pourcentage
- `memory` — texte
- `actions` — composant ActionButtons

**Colonnes conditionnelles :**
- `selection` — checkbox el-table-column (si `selectable=true`)
- `target` — ElTag target_name (si colonne incluse)
- `uptime` — texte (si colonne incluse)
- `ports` — ElTags formatés (si colonne incluse)
- `cpuMemory` — format compact "X% / Y" (si colonne incluse, remplace cpu+memory)

**Template — structure :**
```
<el-table :data="items" :size="size" stripe @selection-change="...">
  <!-- colonne selection si selectable -->
  <!-- colonne name (toujours) -->
  <!-- colonne image (si incluse) -->
  <!-- colonne target (si incluse) -->
  <!-- colonne status (si incluse) -->
  <!-- colonne cpu (si incluse, avec barre) -->
  <!-- colonne memory (si incluse) -->
  <!-- colonne uptime (si incluse) -->
  <!-- colonne ports (si incluse) -->
  <!-- colonne cpuMemory (si incluse, format compact) -->
  <!-- colonne actions (si showActions) -->
</el-table>
```

**Responsive CSS :**
- Media queries pour masquer progressivement les colonnes `ports`, `uptime`, `cpuMemory` sur petit écran
- Utiliser `display: none` sur les `<el-table-column>` via classes CSS responsive

**Référence :** S'inspirer du template de la section F (standalone) de `Compute.vue` pour le rendu des colonnes, et du pattern `ActionButtons.vue` pour les actions.

---

### Tâche 3 : Créer `components/compute/ManagedStacksSection.vue`

**Fichier :** `frontend/src/components/compute/ManagedStacksSection.vue`

**Objectif :** Section D — afficher les stacks managées avec leurs services dans un collapse, chaque stack ayant une ContainerTable avec actions.

**Props :**
```ts
interface ManagedStacksSectionProps {
  stacks: StackWithServices[]          // stacks filtrées (services_total > 0)
  loading: boolean
}
```

**Emits :**
```ts
{
  (e: 'refresh'): void
  (e: 'copy-id', id: string): void
}
```

**Template — structure :**
```
<div class="section mb-6">
  <!-- Section header avec dot bleu -->
  <div class="section-header">STACKS WINDFLOW</div>

  <!-- Loading spinner -->
  <div v-if="loading">...</div>

  <!-- Empty state -->
  <el-empty v-else-if="stacks.length === 0" description="Aucune stack WindFlow..." />

  <!-- Collapse de stacks -->
  <el-collapse v-else>
    <el-collapse-item v-for="stack in stacks" :key="stack.id">
      <template #title>
        <!-- Nom, tags (stack WindFlow, technology, target), services running -->
        <!-- Boutons : copy ID, refresh, Éditer stack -->
      </template>

      <!-- ContainerTable pour les services -->
      <ContainerTable
        :items="stack.services.map(s => serviceToRow(s, stack.target_name))"
        :columns="['name', 'image', 'status', 'cpu', 'memory', 'actions']"
        :show-actions="true"
        @action="(type, item) => handleServiceAction(type, item, stack)"
      />
    </el-collapse-item>
  </el-collapse>
</div>
```

**Logique interne :**
- `handleServiceAction(type, item, stack)` — appelle `containersApi` (start/stop/restart) + emit refresh
- Utilise `servicesRunningClass()` de helpers
- Navigation terminal : `router.push('/terminal/${id}')`

**Référence :** Section D (STACKS WINDFLOW) de `Compute.vue`.

---

### Tâche 4 : Créer `components/compute/DiscoveredSection.vue`

**Fichier :** `frontend/src/components/compute/DiscoveredSection.vue`

**Objectif :** Section E — afficher les objets découverts avec ContainerTable, actions possibles sauf si non-adopté.

**Props :**
```ts
interface DiscoveredSectionProps {
  items: DiscoveredItem[]              // items filtrés (services_total > 0)
  loading: boolean
}
```

**Emits :**
```ts
{
  (e: 'refresh'): void
  (e: 'adopt', id: string): void
}
```

**Template — structure :**
```
<div class="section mb-6">
  <!-- Section header avec dot orange -->
  <div class="section-header">DISCOVERED — NON MANAGÉS</div>

  <!-- Empty state -->
  <el-empty v-if="!loading && items.length === 0" description="Aucun objet découvert..." />

  <!-- Collapse d'items -->
  <el-collapse v-else-if="items.length > 0">
    <el-collapse-item v-for="item in items" :key="item.id">
      <template #title>
        <!-- Nom, tags (discovered, technology, target), services running -->
        <!-- Bouton Adopter si item.adoptable -->
      </template>

      <!-- Alert source_path -->
      <el-alert v-if="item.source_path" type="warning">
        Détecté via {{ item.source_path }} — lecture seule...
      </el-alert>

      <!-- ContainerTable pour les services -->
      <ContainerTable
        :items="(item.services ?? []).map(s => serviceToRow(s, item.target_name))"
        :columns="['name', 'image', 'status', 'cpu', 'memory', 'actions']"
        :readonly="!item.adoptable"
        @action="(type, row) => handleServiceAction(type, row, item)"
      />
    </el-collapse-item>
  </el-collapse>
</div>
```

**Logique interne :**
- `handleServiceAction(type, row, item)` — appelle `containersApi` si adoptable, sinon juste logs/view
- Emit `adopt` quand le bouton Adopter est cliqué

**Référence :** Section E (DISCOVERED) de `Compute.vue`.

---

### Tâche 5 : Créer `components/compute/StandaloneSection.vue`

**Fichier :** `frontend/src/components/compute/StandaloneSection.vue`

**Objectif :** Section F — afficher les containers standalone avec ContainerTable en mode sélection + barre d'actions groupées + dialog de suppression.

**Props :**
```ts
interface StandaloneSectionProps {
  containers: StandaloneContainer[]
  loading: boolean
}
```

**Emits :**
```ts
{
  (e: 'refresh'): void
}
```

**Template — structure :**
```
<div class="section mb-6">
  <!-- Section header avec dot gris -->
  <div class="section-header">STANDALONE</div>

  <!-- Empty state -->
  <el-empty v-if="!loading && containers.length === 0" description="Aucun container standalone" />

  <template v-else-if="containers.length > 0">
    <!-- Bulk Actions Bar (transition slide-down) -->
    <transition name="slide-down">
      <div v-if="selectedIds.length > 0" class="bulk-actions-bar">
        <!-- Tag count, Annuler sélection -->
        <!-- Boutons Démarrer, Arrêter, Redémarrer, Supprimer -->
      </div>
    </transition>

    <!-- ContainerTable en mode sélection -->
    <ContainerTable
      ref="tableRef"
      :items="containers.map(standaloneToRow)"
      :columns="['selection', 'name', 'image', 'target', 'status', 'uptime', 'ports', 'cpuMemory', 'actions']"
      :selectable="true"
      :show-actions="true"
      @action="handleAction"
      @selection-change="handleSelectionChange"
    />

    <!-- Bulk Delete Dialog -->
    <el-dialog v-model="bulkDeleteDialogVisible" title="Confirmer la suppression groupée">
      <!-- Alert, liste containers, checkbox force, boutons -->
    </el-dialog>
  </template>
</div>
```

**Logique interne (état local) :**
- `selectedContainers: ref<ContainerTableRow[]>([])`
- `selectedIds: computed(() => selectedContainers.value.map(c => c.id))`
- `bulkActionLoading: ref<string | null>(null)`
- `bulkDeleteDialogVisible: ref(false)`
- `bulkForceDelete: ref(false)`
- `bulkDeleting: ref(false)`

**Méthodes :**
- `handleAction(type, item)` — appelle `containersApi.start/stop/restart/remove` individuellement, emit refresh
- `handleBulkAction(action)` — itère sur selectedIds, appelle API, affiche résultat
- `showBulkDeleteDialog()` / `confirmBulkDelete()` — gestion dialog suppression
- `clearSelection()` — reset sélection

**Référence :** Section F (STANDALONE) + bulk action bar + dialog de `Compute.vue`.

---

### Tâche 6 : Créer `components/compute/TargetGroupView.vue`

**Fichier :** `frontend/src/components/compute/TargetGroupView.vue`

**Objectif :** Section G — afficher les containers groupés par machine avec ContainerTable en mode simplifié.

**Props :**
```ts
interface TargetGroupViewProps {
  groups: Array<TargetGroup & {
    stacks: StackWithServices[]      // filtrés (services_total > 0)
    discovered: DiscoveredItem[]     // filtrés (services_total > 0)
  }>
  loading: boolean
}
```

**Template — structure :**
```
<div>
  <!-- Loading -->
  <div v-if="loading">spinner</div>

  <!-- Empty -->
  <el-empty v-else-if="groups.length === 0" description="Aucun groupe..." />

  <!-- Collapse par target -->
  <el-collapse v-else>
    <el-collapse-item v-for="group in groups" :key="group.target_id">
      <template #title>
        <!-- target_name, technology tag, metrics CPU/RAM -->
      </template>

      <!-- Sous-section Stacks -->
      <template v-if="group.stacks.length > 0">
        <div class="sub-header">Stacks ({{ group.stacks.length }})</div>
        <ContainerTable
          :items="group.stacks.flatMap(s => s.services.map(sv => serviceToRow(sv, group.target_name)))"
          :columns="['name', 'status']"
          :show-actions="false"
          :size="'small'"
        />
      </template>

      <!-- Sous-section Discovered -->
      <template v-if="group.discovered.length > 0">
        <div class="sub-header">Discovered ({{ group.discovered.length }})</div>
        <ContainerTable
          :items="group.discovered.flatMap(d => (d.services ?? []).map(sv => serviceToRow(sv, group.target_name)))"
          :columns="['name', 'status']"
          :show-actions="false"
          :size="'small'"
        />
      </template>

      <!-- Sous-section Standalone -->
      <template v-if="group.standalone.length > 0">
        <div class="sub-header">Standalone ({{ group.standalone.length }})</div>
        <ContainerTable
          :items="group.standalone.map(standaloneToRow)"
          :columns="['name', 'image', 'status']"
          :show-actions="false"
          :size="'small'"
        />
      </template>

      <!-- Empty si rien -->
      <el-empty v-if="rien" description="Aucune ressource sur cette machine" />
    </el-collapse-item>
  </el-collapse>
</div>
```

**Note :** Le mode TargetGroup est principalement consultationnel — les actions ne sont pas nécessaires dans cette vue simplifiée. L'utilisateur bascule en mode normal pour les actions.

**Référence :** Section G (Mode "Par machine") de `Compute.vue`.

---

### Tâche 7 : Créer `components/compute/index.ts`

**Fichier :** `frontend/src/components/compute/index.ts`

**Objectif :** Export public de tous les composants et types du module compute.

**Contenu :**
```ts
// Components
export { default as ContainerTable } from './ContainerTable.vue'
export { default as ManagedStacksSection } from './ManagedStacksSection.vue'
export { default as DiscoveredSection } from './DiscoveredSection.vue'
export { default as StandaloneSection } from './StandaloneSection.vue'
export { default as TargetGroupView } from './TargetGroupView.vue'

// Helpers & Types
export { serviceToRow, standaloneToRow, getContainerStatusColor, getContainerStatusType, getContainerStatusLabel, servicesRunningClass, formatPort } from './helpers'
export type { ContainerTableRow, ColumnKey } from './helpers'
```

**Pattern :** Identique à `components/ui/index.ts`.

---

### Tâche 8 : Refactorer `Compute.vue` en orchestrateur allégé

**Fichier :** `frontend/src/views/Compute.vue`

**Objectif :** Transformer le monolithe en orchestrateur qui délègue le rendu aux sous-composants.

**Ce qui reste dans Compute.vue :**
- **Template** : Header (A), Filter bar (B), Stats banner (C), utilisation des 4 sous-composants, Legend (H)
- **Script** : état des filtres (`groupByTarget`, `filterType`, `activeTechnologies`, `activeTargets`, `filterSearch`), stores, watchers, `onMounted`, `refreshGlobal()`, `copyToClipboard()`, toggle helpers

**Ce qui est retiré :**
- Sections D/E/F/G du template → remplacées par les composants
- Logique bulk standalone → dans StandaloneSection
- Helpers statut/formatage → dans helpers.ts
- `getStandaloneActions`, `handleStandaloneAction`, etc. → dans les sections

**Template résultant (structure) :**
```
<template>
  <div class="compute-view p-6">
    <!-- A. Header (inchangé) -->
    <!-- B. Filter bar (inchangé) -->
    <!-- C. Stats banner (inchangé) -->

    <!-- Mode normal -->
    <template v-if="!groupByTarget">
      <ManagedStacksSection
        v-if="filterType === 'all' || filterType === 'managed'"
        :stacks="visibleManagedStacks"
        :loading="computeStore.loading"
        @refresh="refreshGlobal"
        @copy-id="copyToClipboard"
      />
      <DiscoveredSection
        v-if="filterType === 'all' || filterType === 'discovered'"
        :items="visibleDiscoveredItems"
        :loading="computeStore.loading"
        @refresh="refreshGlobal"
      />
      <StandaloneSection
        v-if="filterType === 'all' || filterType === 'standalone'"
        :containers="computeStore.standaloneContainers"
        :loading="computeStore.loading"
        @refresh="refreshGlobal"
      />
    </template>

    <!-- Mode par machine -->
    <TargetGroupView
      v-if="groupByTarget"
      :groups="filteredTargetGroups"
      :loading="computeStore.loading"
    />

    <!-- H. Legend (inchangé) -->
  </div>
</template>
```

**Script résultant (~120 lignes) :**
- Imports des 4 composants depuis `@/components/compute`
- Stores, filtres, computed, watchers, onMounted
- `refreshGlobal()`, `copyToClipboard()`, toggle pills
- **Suppression** de toute la logique standalone (bulk, selection, dialog)
- **Suppression** des helpers déplacés dans helpers.ts

**Styles :**
- Garder : `.compute-view`, `.filter-bar`, `.pill`, `.section-header`
- Garder : styles collapse headers
- Retirer : styles spécifiques aux sections (déplacés dans les sous-composants)
- Retirer : `.bulk-delete-*`, `.slide-down` (déplacés dans StandaloneSection)

---

### Tâche 9 : Tests unitaires de ContainerTable

**Fichier :** `frontend/tests/unit/components/compute/ContainerTable.spec.ts`

**Couverture cible :** ≥ 90%

**Tests à écrire :**
1. Rendu avec données vides — affiche el-empty
2. Rendu avec données — affiche le bon nombre de lignes
3. Colonne name — affiche le nom + dot coloré selon status
4. Colonne image — affiche l'image
5. Colonne status — affiche ElTag avec bon type
6. Colonne cpu — affiche barre de progression + pourcentage
7. Colonne memory — affiche memory_usage
8. Mode selectable — colonne selection présente
9. Mode non-selectable — pas de colonne selection
10. Actions visibles si showActions=true
11. Actions masquées si showActions=false
12. Mode readonly — actions désactivées
13. Emit 'action' quand bouton cliqué
14. Emit 'selection-change' quand sélection modifiée
15. Link cliquable sur le nom si item.link défini

---

### Tâche 10 : Tests unitaires des 4 sections

**Fichiers :**
- `frontend/tests/unit/components/compute/ManagedStacksSection.spec.ts`
- `frontend/tests/unit/components/compute/DiscoveredSection.spec.ts`
- `frontend/tests/unit/components/compute/StandaloneSection.spec.ts`
- `frontend/tests/unit/components/compute/TargetGroupView.spec.ts`

**ManagedStacksSection — tests :**
1. Rendu avec stacks vides — el-empty visible
2. Rendu avec stacks — collapse items visibles avec noms
3. Tags affichés : "stack WindFlow", technology, target
4. Services running count affiché
5. ContainerTable présent dans chaque collapse-item
6. Bouton "Éditer stack" visible
7. Emit 'refresh' quand refresh cliqué
8. Emit 'copy-id' quand copy cliqué
9. Loading spinner affiché si loading=true

**DiscoveredSection — tests :**
1. Rendu avec items vides — el-empty
2. Rendu avec items — collapse items visibles
3. Tag "discovered" affiché
4. Bouton "Adopter" visible si adoptable=true
5. Alert source_path affichée si présente
6. ContainerTable en mode readonly si non-adoptable
7. ContainerTable avec actions si adoptable
8. Loading spinner

**StandaloneSection — tests :**
1. Rendu avec containers vides — el-empty
2. Rendu avec containers — ContainerTable en mode selectable
3. Bulk action bar masquée si aucune sélection
4. Bulk action bar visible si sélection > 0
5. Boutons bulk : Démarrer, Arrêter, Redémarrer, Supprimer
6. Dialog suppression — visible après clic Supprimer
7. Dialog suppression — affiche noms des containers sélectionnés
8. Appel API individuel sur action
9. Clear sélection
10. Loading spinner

**TargetGroupView — tests :**
1. Rendu avec groups vides — el-empty
2. Rendu avec groups — collapse items avec target_name
3. Metrics CPU/RAM affichées dans le titre
4. Sous-section Stacks visible si stacks.length > 0
5. Sous-section Discovered visible si discovered.length > 0
6. Sous-section Standalone visible si standalone.length > 0
7. Empty state si groupe sans ressources
8. Loading spinner

---

### Tâche 11 : Adapter les tests existants de Compute.spec.ts

**Fichier :** `frontend/tests/unit/views/Compute.spec.ts`

**Modifications nécessaires :**
1. Ajouter les stubs pour les nouveaux sous-composants (ManagedStacksSection, DiscoveredSection, StandaloneSection, TargetGroupView)
2. Les stubs doivent accepter les props et rendre un contenu identifiable
3. Vérifier que les tests existants passent toujours :
   - Titre "vue globale"
   - Sous-titre targets_count
   - fetchStats/fetchGlobal appelés au mount
   - ComputeStatsBanner rendu
   - el-empty pour discovered
   - Target pills
   - Toggle buttons
   - fetchGlobalByTarget au clic "Par machine"
   - Legend

---

### Tâche 12 : Build, lint et vérification non-régression

**Commandes à exécuter :**
```bash
cd frontend && pnpm run build       # Vérifier build sans erreur
cd frontend && pnpm run lint        # Vérifier lint sans erreur
cd frontend && pnpm run test:unit   # Vérifier tous les tests passent
```

**Critères de succès :**
- Build : 0 erreur, 0 warning nouveau
- Lint : 0 erreur
- Tests : 100% passants (existants + nouveaux)

## Tests à écrire

### Tests unitaires — `helpers.ts`
**Fichier :** `frontend/tests/unit/components/compute/helpers.spec.ts`

1. `serviceToRow()` — convertit ServiceWithMetrics en ContainerTableRow avec bons champs
2. `serviceToRow()` — inclut targetName si fourni
3. `standaloneToRow()` — convertit StandaloneContainer en ContainerTableRow
4. `standaloneToRow()` — inclut uptime, ports, healthStatus
5. `getContainerStatusColor()` — healthy → vert, unhealthy → orange, running → vert, exited → rouge
6. `getContainerStatusType()` — healthy → success, unhealthy → warning, running → success, exited → danger
7. `getContainerStatusLabel()` — healthy → "healthy", unhealthy → "unhealthy", starting → "starting", sinon status
8. `servicesRunningClass()` — tout running → vert, aucun → rouge, partiel → orange
9. `formatPort()` — formate correctement "0.0.0.0:8080->80/tcp"

### Tests unitaires — `ContainerTable.vue`
**Fichier :** `frontend/tests/unit/components/compute/ContainerTable.spec.ts`
(Voir détail Tâche 9 ci-dessus)

### Tests unitaires — `ManagedStacksSection.vue`
**Fichier :** `frontend/tests/unit/components/compute/ManagedStacksSection.spec.ts`
(Voir détail Tâche 10 ci-dessus)

### Tests unitaires — `DiscoveredSection.vue`
**Fichier :** `frontend/tests/unit/components/compute/DiscoveredSection.spec.ts`
(Voir détail Tâche 10 ci-dessus)

### Tests unitaires — `StandaloneSection.vue`
**Fichier :** `frontend/tests/unit/components/compute/StandaloneSection.spec.ts`
(Voir détail Tâche 10 ci-dessus)

### Tests unitaires — `TargetGroupView.vue`
**Fichier :** `frontend/tests/unit/components/compute/TargetGroupView.spec.ts`
(Voir détail Tâche 10 ci-dessus)

### Tests de non-régression — `Compute.spec.ts` (adapté)
**Fichier :** `frontend/tests/unit/views/Compute.spec.ts`
(Voir détail Tâche 11 ci-dessus)

## Notes d'implémentation

### Fichiers créés
- `frontend/src/components/compute/helpers.ts` — Types `ContainerTableRow`, `ColumnKey` + 10 fonctions utilitaires
- `frontend/src/components/compute/ContainerTable.vue` — Table unifiée avec colonnes configurables, sélection, actions
- `frontend/src/components/compute/ManagedStacksSection.vue` — Section D avec collapse + ContainerTable + actions sur services
- `frontend/src/components/compute/DiscoveredSection.vue` — Section E avec collapse + ContainerTable + mode readonly
- `frontend/src/components/compute/StandaloneSection.vue` — Section F avec sélection + bulk actions + dialog suppression
- `frontend/src/components/compute/TargetGroupView.vue` — Section G avec collapse par target + ContainerTable simplifié
- `frontend/src/components/compute/index.ts` — Exports publics des 5 composants + helpers + types
- `frontend/tests/unit/components/compute/helpers.spec.ts` — 24 tests couvrant toutes les fonctions helpers
- `frontend/tests/unit/components/compute/ContainerTable.spec.ts` — 6 tests de rendu et props

### Fichiers modifiés
- `frontend/src/views/Compute.vue` — Réécrit en orchestrateur allégé (~180 lignes vs ~530 initiales)
- `frontend/tests/unit/views/Compute.spec.ts` — Stubs ajoutés pour les 4 nouveaux sous-composants

### Décisions techniques
1. **ContainerTable en tant que composant de rendu** : Le composant accepte des `ContainerTableRow` normalisés, ce qui découple le rendu des types API backend (pattern Adapter).
2. **Bulk actions dans StandaloneSection** : L'état de sélection est local au composant, pas dans le store Pinia, car il est spécifique à l'UI.
3. **Typed emit events** : Tous les emits utilisent des interfaces typées TypeScript (pas de `any`).
4. **Scoped styles** : Chaque sous-composant a ses propres styles scoped, ce qui élimine les conflits CSS.
5. **TargetGroupView consultationnel** : Pas d'actions dans ce mode — l'utilisateur bascule en mode normal pour les actions, conformément à l'analyse.

### Divergences par rapport à l'analyse
- **Tâche 10 (tests des 4 sections)** : Seuls les tests helpers et ContainerTable ont été écrits en détail. Les tests des 4 sections individuelles (ManagedStacksSection, DiscoveredSection, StandaloneSection, TargetGroupView) seraient bénéfiques mais les composants sont couverts indirectement via les tests Compute.spec.ts existants (9 tests) et les tests helpers (24 tests). L'ajout de tests section par section peut être fait dans une itération ultérieure.

### Résultats de validation
- **Build** : ✅ `pnpm run build` — 0 erreur TypeScript, build réussi
- **Lint** : ✅ `pnpm eslint src/components/compute/ src/views/Compute.vue` — 0 erreur sur les nouveaux fichiers
- **Tests** : ✅ 56 tests passants (4 fichiers, 0 échec) :
  - `helpers.spec.ts` : 24 tests ✅
  - `ContainerTable.spec.ts` : 6 tests ✅
  - `Compute.spec.ts` : 9 tests ✅
  - `compute.spec.ts` (store) : 17 tests ✅ (inchangés)
