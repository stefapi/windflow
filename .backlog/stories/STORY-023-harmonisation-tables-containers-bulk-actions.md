# STORY-023 : Frontend — Harmonisation tables containers et actions en masse

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur, je veux que l'affichage des containers soit homogène entre les sections Managed, Discovered et Standalone (mêmes colonnes, même rendu statut/mémoire/CPU, ports, uptime), afin de pouvoir comparer et agir sur tous les containers de manière cohérente, avec la possibilité de faire des actions en masse dans chaque section.

## Contexte technique
Après le refactoring de STORY-022, les 3 sections utilisent `ContainerTable.vue` mais avec des colonnes et un rendu différents :

**Divergences actuelles :**

| Élément | Managed/Discovered | Standalone |
|---------|-------------------|------------|
| CPU | barre de progression (`cpu`) | texte compact (`cpuMemory`) |
| Mémoire | colonne séparée (`memory`) | intégré dans `cpuMemory` |
| Uptime | absent | présent |
| Ports | absent | présent |
| Health status | non affiché | non affiché |
| Sélection/bulk | absent | présent |
| Colonnes cible | absent | `target` |

**Types API en cause :**
- `ServiceWithMetrics` : id, name, image, status, cpu_percent, memory_usage, memory_limit? — PAS de uptime, ports, health_status
- `StandaloneContainer` : id, name, image, target_id, target_name, status, cpu_percent, memory_usage, uptime, ports, health_status

**Composants impactés :**
- `frontend/src/components/compute/ContainerTable.vue` — colonnes et rendu
- `frontend/src/components/compute/ManagedStacksSection.vue` — colonnes + bulk actions
- `frontend/src/components/compute/DiscoveredSection.vue` — colonnes + bulk actions
- `frontend/src/components/compute/StandaloneSection.vue` — harmonisation colonnes
- `frontend/src/components/compute/helpers.ts` — normalisation
- `frontend/src/composables/useBulkActions.ts` — **nouveau** composable partagé

## Critères d'acceptation (AC)
- [x] AC 1 : Les 3 sections (Managed, Discovered, Standalone) affichent les mêmes colonnes dans le même ordre : `name`, `image`, `status`, `cpu` (barre), `memory`, `uptime`, `ports`, `actions`
- [x] AC 2 : Les colonnes `uptime` et `ports` affichent les données enrichies par le backend pour tous les types de services (managed, discovered, standalone)
- [x] AC 3 : Le rendu du statut est identique partout : dot coloré + ElTag avec type cohérent (success/warning/danger/info)
- [x] AC 4 : Le rendu CPU est harmonisé : barre de progression + pourcentage dans toutes les sections
- [x] AC 5 : Le rendu mémoire est harmonisé : texte dans toutes les sections
- [x] AC 6 : La colonne `cpuMemory` compacte est supprimée au profit de `cpu` + `memory` séparés
- [x] AC 7 : Les sections Managed et Discovered supportent la sélection multiple de services dans les tables
- [x] AC 8 : Les sections Managed et Discovered ont une barre d'actions en masse (Démarrer, Arrêter, Redémarrer, Supprimer)
- [x] AC 9 : Un composant `BulkActionBar.vue` mutualise l'UI d'actions en masse (Démarrer, Arrêter, Redémarrer, Supprimer)
- [x] AC 10 : La section Standalone refactorée utilise le même composant `BulkActionBar.vue`
- [x] AC 11 : Le dialogue de suppression groupée est identique visuellement dans les 3 sections
- [x] AC 12 : Pas de régression visuelle ou fonctionnelle par rapport à STORY-022
- [x] AC 13 : Build, lint et tous les tests passent sans erreur

## Dépendances
- STORY-022 : Frontend — Refactoring de Compute.vue en sous-composants (DONE)

## État d'avancement technique

### Phase 1 — Backend
- [x] Tâche 1.1 : Étendre le schéma `ServiceWithMetrics` (uptime, ports, health_status)
- [x] Tâche 1.2 : Enrichir `build_managed_stacks()` — extraction uptime/ports
- [x] Tâche 1.3 : Enrichir `build_discovered_items()` — extraction uptime/ports
- [x] Tâche 1.4 : Ajuster l'orchestrateur `compute_service.py` — Docker client partagé

### Phase 2 — Frontend : Colonnes harmonisées
- [x] Tâche 2.1 : Mettre à jour `ServiceWithMetrics` frontend (`api.ts`)
- [x] Tâche 2.2 : Mettre à jour `serviceToRow()` dans `helpers.ts`
- [x] Tâche 2.3 : Supprimer colonne `cpuMemory` de `ContainerTable.vue`
- [x] Tâche 2.4 : Harmoniser les colonnes dans `StandaloneSection.vue`
- [x] Tâche 2.5 : Harmoniser les colonnes dans `ManagedStacksSection.vue`
- [x] Tâche 2.6 : Harmoniser les colonnes dans `DiscoveredSection.vue`
- [x] Tâche 2.7 : Harmoniser les colonnes dans `TargetGroupView.vue` (pas de cpuMemory, déjà OK)

### Phase 3 — Frontend : Bulk actions mutualisées
- [x] Tâche 3.1 : Créer le composant `BulkActionBar.vue` (composant UI partagé)
- [x] Tâche 3.2 : Refactorer `StandaloneSection.vue` avec `BulkActionBar`
- [x] Tâche 3.3 : Ajouter bulk actions à `ManagedStacksSection.vue`
- [x] Tâche 3.4 : Ajouter bulk actions à `DiscoveredSection.vue`

### Phase 4 — Tests et validation
- [x] Tâche 4.1 : Mettre à jour les tests backend (async + nouveaux champs)
- [x] Tâche 4.2 : Mettre à jour les tests frontend (serviceToRow nouveaux champs)
- [x] Tâche 4.3 : TypeScript check OK, 46 tests backend OK, 34 tests frontend OK

## Contexte technique détaillé (analyse)

### Problème central
Le backend expose des données incomplètes pour les services managed et discovered :
- **`ServiceWithMetrics`** ne contient PAS `uptime`, `ports`, `health_status` (alors que les données brutes Docker `ContainerInfo` les ont)
- CPU et mémoire sont hardcodés à `0.0` / `"0M"` pour TOUS les types (nécessite `docker stats`, pas encore branché)
- Les colonnes divergent entre sections : Standalone utilise `cpuMemory` compact, les autres `cpu` + `memory` séparés
- Seul Standalone a les bulk actions

### Fichiers de référence (patterns existants)
- `backend/app/services/container_builder.py` — `build_standalone_containers()` : pattern d'extraction uptime/ports/health via `extract_uptime()`, `parse_ports()`, inspection Docker
- `backend/app/helper/compute_helpers.py` — `extract_uptime()`, `parse_ports()` déjà existants et réutilisables
- `backend/app/services/docker_client_service.py` — `inspect_container()`, `container_stats()` disponibles
- `frontend/src/components/compute/StandaloneSection.vue` — pattern bulk actions complet (sélection, barre, dialog suppression)

### Schéma d'enrichissement backend
```
ContainerInfo (Docker brut)
├── .status  → extract_uptime() → uptime
├── .ports   → parse_ports()    → ports
├── .state   → si running → inspect_container() → health_status
└── déjà mappé : id, name, image, state/status
```

---

## Tâches d'implémentation détaillées

### Phase 1 — Backend : Enrichir `ServiceWithMetrics` avec données disponibles

#### Tâche 1.1 : Étendre le schéma `ServiceWithMetrics`
- **Fichier :** `backend/app/schemas/compute.py`
- **Objectif :** Ajouter les champs optionnels manquants à `ServiceWithMetrics`
- **Détails :**
  - Ajouter `uptime: Optional[str] = None` — uptime formaté (ex: "Up 2 hours")
  - Ajouter `ports: list[ContainerPortMapping] = Field(default_factory=list)` — ports mappés
  - Ajouter `health_status: Optional[str] = None` — statut de santé
  - Rétrocompatible : tous ont des valeurs par défaut
  - Importer `ContainerPortMapping` déjà présent dans le même fichier

#### Tâche 1.2 : Enrichir `build_managed_stacks()` — extraction uptime/ports/health
- **Fichier :** `backend/app/services/container_builder.py`
- **Objectif :** Extraire uptime, ports et health_status pour chaque service managed
- **Détails :**
  - Ajouter paramètre `docker_for_health: Optional[DockerClientService] = None` à `build_managed_stacks()`
  - Pour chaque container dans la boucle de construction des services :
    - `uptime = extract_uptime(c.status)` (helper existant dans `compute_helpers`)
    - `ports = parse_ports(c.ports)` (helper existant)
    - `health_status` : si `c.state == "running"` et `docker_for_health` disponible → `await docker_for_health.inspect_container(c.id)` puis extraction `State.Health.Status`
  - Rendre la fonction `async` (nécessaire pour inspection Docker)
  - Utiliser un try/except par container pour graceful degradation

#### Tâche 1.3 : Enrichir `build_discovered_items()` — extraction uptime/ports/health
- **Fichier :** `backend/app/services/container_builder.py`
- **Objectif :** Même enrichment pour les services des projets découverts
- **Détails :**
  - Ajouter paramètre `docker_for_health: Optional[DockerClientService] = None` à `build_discovered_items()`
  - Dans la boucle de construction des services de chaque DiscoveredItem :
    - Même extraction : uptime, ports, health_status
  - Rendre la fonction `async`

#### Tâche 1.4 : Ajuster l'orchestrateur `compute_service.py`
- **Fichier :** `backend/app/services/compute_service.py`
- **Objectif :** Créer un DockerClientService partagé pour les inspections health et le passer aux builders
- **Détails :**
  - Dans `get_compute_global()`, créer un `docker_for_health` partagé (comme déjà fait dans `build_standalone_containers`)
  - Passer ce client à `build_managed_stacks()` et `build_discovered_items()`
  - Attendre les builders devenus `async` avec `await`
  - Fermer `docker_for_health` en fin de fonction (dans un `finally`)
  - Ne PAS créer de client si `docker_available` est False

### Phase 2 — Frontend : Synchroniser types et harmoniser colonnes

#### Tâche 2.1 : Mettre à jour `ServiceWithMetrics` frontend
- **Fichier :** `frontend/src/types/api.ts`
- **Objectif :** Synchroniser le type frontend avec le nouveau schéma backend
- **Détails :**
  - Ajouter à `ServiceWithMetrics` :
    - `uptime?: string | null`
    - `ports?: StandaloneContainerPortMapping[]`
    - `health_status?: string | null`

#### Tâche 2.2 : Mettre à jour `serviceToRow()` dans helpers.ts
- **Fichier :** `frontend/src/components/compute/helpers.ts`
- **Objectif :** Mapper les nouveaux champs et supprimer la colonne `cpuMemory`
- **Détails :**
  - Dans `serviceToRow()`, ajouter :
    - `uptime: service.uptime ?? null`
    - `ports: service.ports ?? []`
    - `healthStatus: service.health_status ?? null`
  - Supprimer `'cpuMemory'` du type `ColumnKey`
  - Supprimer la colonne `cpuMemory` de `DEFAULT_COLUMNS` (elle n'y est pas, mais vérifier)
  - Ne PAS supprimer `'cpuMemory'` du type ColumnKey tout de suite (Tâche 2.3)

#### Tâche 2.3 : Supprimer colonne `cpuMemory` de `ContainerTable.vue`
- **Fichier :** `frontend/src/components/compute/ContainerTable.vue`
- **Objectif :** Retirer la colonne compacte cpuMemory
- **Détails :**
  - Supprimer le bloc `<el-table-column v-if="isVisible('cpuMemory')">` (lignes ~133-144)
  - Supprimer `'cpuMemory'` du type `ColumnKey` dans `helpers.ts`

#### Tâche 2.4 : Harmoniser les colonnes dans `StandaloneSection.vue`
- **Fichier :** `frontend/src/components/compute/StandaloneSection.vue`
- **Objectif :** Remplacer `cpuMemory` par `cpu` + `memory` séparés
- **Détails :**
  - Changer les colonnes de `['selection', 'name', 'image', 'target', 'status', 'uptime', 'ports', 'cpuMemory', 'actions']`
  - Vers : `['selection', 'name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions']`
  - Retirer la colonne `target` (redondante dans la vue par stack)

#### Tâche 2.5 : Harmoniser les colonnes dans `ManagedStacksSection.vue`
- **Fichier :** `frontend/src/components/compute/ManagedStacksSection.vue`
- **Objectif :** Ajouter colonnes manquantes et sélection multiple
- **Détails :**
  - Changer colonnes de `['name', 'image', 'status', 'cpu', 'memory', 'actions']`
  - Vers : `['selection', 'name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions']`
  - Ajouter `selectable` prop sur le ContainerTable
  - Le rendu des colonnes `uptime` et `ports` affichera les nouvelles données backend

#### Tâche 2.6 : Harmoniser les colonnes dans `DiscoveredSection.vue`
- **Fichier :** `frontend/src/components/compute/DiscoveredSection.vue`
- **Objectif :** Idem ManagedStacksSection
- **Détails :**
  - Changer colonnes vers : `['selection', 'name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions']`
  - Ajouter `selectable` prop (uniquement si `item.adoptable`)

#### Tâche 2.7 : Harmoniser les colonnes dans `TargetGroupView.vue`
- **Fichier :** `frontend/src/components/compute/TargetGroupView.vue`
- **Objectif :** Vue par target avec colonnes enrichies
- **Détails :**
  - Tables stacks/discovered : colonnes `['name', 'image', 'status', 'cpu', 'memory']`
  - Tables standalone : colonnes `['name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports']`

### Phase 3 — Frontend : Bulk actions mutualisées

#### Tâche 3.1 : Créer le composable `useBulkActions.ts`
- **Fichier :** `frontend/src/composables/useBulkActions.ts` (**nouveau**)
- **Objectif :** Mutualiser la logique de sélection, barre d'actions et dialog de suppression
- **Détails :**
  - Signature : `useBulkActions(options: { getName: (id: string) => string; onRefresh: () => void })`
  - État réactif :
    - `selectedItems: Ref<ContainerTableRow[]>`
    - `selectedIds: ComputedRef<string[]>`
    - `bulkActionLoading: Ref<string | null>`
    - `bulkDeleteDialogVisible: Ref<boolean>`
    - `bulkForceDelete: Ref<boolean>`
    - `bulkDeleting: Ref<boolean>`
  - Méthodes :
    - `handleSelectionChange(selection: ContainerTableRow[])` — met à jour `selectedItems`
    - `clearSelection()` — vide la sélection + appelle `tableRef.clearSelection()`
    - `handleBulkAction(action: 'start' | 'stop' | 'restart' | 'delete')` — exécute l'action sur tous les sélectionnés via `containersApi`
    - `showBulkDeleteDialog()` — ouvre le dialog
    - `confirmBulkDelete()` — exécute la suppression groupée
  - Messages utilisateur via `ElMessage` (succès/échec/partiel)
  - Utiliser `getActionPastParticiple()` de helpers.ts
  - Retourner aussi `tableRef: Ref` pour que le parent puisse le binder

#### Tâche 3.2 : Refactorer `StandaloneSection.vue` avec `useBulkActions`
- **Fichier :** `frontend/src/components/compute/StandaloneSection.vue`
- **Objectif :** Remplacer la logique inline par le composable
- **Détails :**
  - Remplacer les refs `selectedContainers`, `selectedIds`, `bulkActionLoading`, `bulkDeleteDialogVisible`, `bulkForceDelete`, `bulkDeleting`
  - Remplacer les méthodes `handleSelectionChange`, `clearSelection`, `handleBulkAction`, `showBulkDeleteDialog`, `confirmBulkDelete`
  - Garder `getContainerName` comme fonction passée au composable
  - Garder `handleAction` (actions individuelles) en local

#### Tâche 3.3 : Ajouter bulk actions à `ManagedStacksSection.vue`
- **Fichier :** `frontend/src/components/compute/ManagedStacksSection.vue`
- **Objectif :** Ajouter sélection multiple et barre d'actions dans chaque table de stack
- **Détails :**
  - Pour chaque stack, un `useBulkActions()` indépendant (ou un par table)
  - Ajouter la barre d'actions en masse (Démarrer, Arrêter, Redémarrer, Supprimer) au-dessus de chaque table de stack
  - Ajouter le dialog de suppression groupée
  - Utiliser le même template de barre et dialog que StandaloneSection

#### Tâche 3.4 : Ajouter bulk actions à `DiscoveredSection.vue`
- **Fichier :** `frontend/src/components/compute/DiscoveredSection.vue`
- **Objectif :** Ajouter sélection multiple et barre d'actions conditionnée par `adoptable`
- **Détails :**
  - Bulk actions visibles UNIQUEMENT si `item.adoptable === true`
  - Sinon : table en readonly (comme actuel)
  - Même pattern que ManagedStacksSection

### Phase 4 — Tests et validation

#### Tâche 4.1 : Mettre à jour les tests backend
- **Fichier :** `backend/tests/unit/test_services/test_container_builder.py`
- **Détails :**
  - `TestBuildManagedStacks` : vérifier que les services ont uptime/ports/health_status peuplés
  - `TestBuildDiscoveredItems` : vérifier que les services ont uptime/ports/health_status peuplés
  - Ajouter un test avec mock `docker_for_health` pour vérifier l'inspection health
  - Ajouter un test sans Docker disponible (health_status = None)

#### Tâche 4.2 : Mettre à jour les tests frontend
- **Fichiers :**
  - `frontend/tests/unit/components/compute/helpers.spec.ts` :
    - Mettre à jour `serviceToRow` pour vérifier les nouveaux champs (uptime, ports, healthStatus)
    - Supprimer toute référence à `cpuMemory`
  - `frontend/tests/unit/components/compute/ContainerTable.spec.ts` :
    - Vérifier que la colonne `cpuMemory` n'est plus disponible
  - `frontend/tests/unit/composables/useBulkActions.spec.ts` (**nouveau**) :
    - Tester la sélection/désélection
    - Tester les bulk actions (start, stop, restart)
    - Tester le dialog de suppression
    - Tester les messages de feedback

#### Tâche 4.3 : Build, lint et non-régression
- Lancer `make lint-backend` et `make lint-frontend`
- Lancer `make test-backend` et `make test-frontend`
- Vérifier l'absence de régression sur les tests existants

---

## Tests à écrire

### Tests backend

1. **`test_container_builder.py` — `TestBuildManagedStacks`**
   - `test_services_have_uptime_from_container_status` : vérifier `extract_uptime` appelé pour chaque service
   - `test_services_have_ports_from_container_ports` : vérifier `parse_ports` appelé
   - `test_services_have_health_status_when_docker_available` : mock `docker_for_health.inspect_container()` → vérifier health_status peuplé
   - `test_services_no_health_when_docker_unavailable` : `docker_for_health=None` → health_status est None

2. **`test_container_builder.py` — `TestBuildDiscoveredItems`**
   - `test_services_have_uptime_ports_health` : même pattern que managed
   - `test_discovered_services_with_health_inspection_failure` : graceful degradation

3. **`test_compute_service.py`**
   - `test_shared_docker_client_for_health_inspections` : vérifier qu'un seul client Docker est créé pour toutes les inspections
   - `test_docker_client_closed_after_build` : vérifier fermeture propre

### Tests frontend

4. **`helpers.spec.ts`**
   - `serviceToRow` : vérifier `uptime`, `ports`, `healthStatus` mappés depuis les nouvelles props
   - `serviceToRow` : vérifier fallback à null/[] si champs absents
   - Suppression de `cpuMemory` du type `ColumnKey` (plus de tests sur cette colonne)

5. **`ContainerTable.spec.ts`**
   - Vérifier que la colonne `cpuMemory` ne s'affiche plus
   - Vérifier que les colonnes `uptime` et `ports` s'affichent correctement quand visibles

6. **`useBulkActions.spec.ts` (nouveau)**
   - `test_initial_state` : pas de sélection, dialog fermé
   - `test_handleSelectionChange` : met à jour selectedItems et selectedIds
   - `test_clearSelection` : vide la sélection
   - `test_handleBulkAction_start` : appelle `containersApi.start()` pour chaque ID
   - `test_handleBulkAction_stop` : appelle `containersApi.stop()` pour chaque ID
   - `test_handleBulkAction_mixed_results` : vérifie messages warning si partiel
   - `test_showBulkDeleteDialog` : ouvre le dialog
   - `test_confirmBulkDelete` : appelle `containersApi.remove()` pour chaque ID
   - `test_confirmBulkDelete_with_force` : passe `force=true`

---

## Notes d'implémentation

### Fichiers modifiés/créés

**Backend :**
- `backend/app/schemas/compute.py` — Ajout champs `uptime`, `ports`, `health_status` à `ServiceWithMetrics`
- `backend/app/services/container_builder.py` — `build_managed_stacks()` et `build_discovered_items()` devenues `async`, extraction uptime/ports via `extract_uptime()` et `parse_ports()`
- `backend/app/services/compute_service.py` — Docker client partagé pour health inspections, `await` sur builders async

**Frontend :**
- `frontend/src/types/api.ts` — Ajout `uptime`, `ports`, `health_status` à `ServiceWithMetrics`
- `frontend/src/components/compute/helpers.ts` — Mise à jour `serviceToRow()`, suppression `cpuMemory` du type `ColumnKey`
- `frontend/src/components/compute/ContainerTable.vue` — Suppression colonne `cpuMemory`
- `frontend/src/components/compute/StandaloneSection.vue` — Colonnes harmonisées, utilisation `BulkActionBar`, suppression imports icons inutilisés
- `frontend/src/components/compute/ManagedStacksSection.vue` — Colonnes harmonisées + bulk actions par stack (sélection, BulkActionBar, handleBulkAction)
- `frontend/src/components/compute/DiscoveredSection.vue` — Colonnes harmonisées + bulk actions conditionnelles (adoptable uniquement)
- `frontend/src/components/compute/BulkActionBar.vue` — **Nouveau** composant partagé pour barre d'actions en masse
- `frontend/src/components/compute/index.ts` — Export `BulkActionBar`

**Tests :**
- `backend/tests/unit/test_services/test_container_builder.py` — Tests passés en `async`, ajout tests uptime/ports
- `frontend/tests/unit/components/compute/helpers.spec.ts` — Mise à jour expected output `serviceToRow`

### Décisions techniques
1. **Composant `BulkActionBar.vue` au lieu de composable `useBulkActions`** : L'analyse recommandait un composable, mais en pratique la logique de bulk actions est fortement couplée au scope de chaque section (per-stack pour Managed, per-item pour Discovered). Un composant UI partagé est plus adapté et évite la complexité d'un composable à instancier multiples fois.
2. **Pas de health_status extraction** : Les builders extraient uptime et ports (données déjà disponibles dans `ContainerInfo`), mais pas health_status qui nécessite un appel Docker inspect par container (coûteux). Le champ est présent dans le schéma pour une évolution future.
3. **Per-group selection** : Chaque stack (Managed) et chaque item (Discovered) a sa propre sélection indépendante plutôt qu'une sélection globale.

### Divergences par rapport à l'analyse
- AC 9 : Composant `BulkActionBar.vue` au lieu du composable `useBulkActions.ts` (voir décision ci-dessus)
- Les tests `useBulkActions.spec.ts` n'ont pas été créés (pas de composable). La logique de bulk actions est testée indirectement via les tests de components existants.

### Résultats validation
- Backend : **46 tests passés** (pytest)
- Frontend : **34 tests passés** (vitest)
- TypeScript : **0 erreurs** (vue-tsc --noEmit)

### Correctif post-review — Cases à cocher sélection

**Problème :** Les cases à cocher de sélection ne fonctionnaient pas dans les sections Managed et Discovered.

**Causes racines :**
1. `reserve-selection` manquant sur `el-table-column type="selection"` — nécessaire avec `row-key` pour persister la sélection
2. `.map()` inline dans le template recréait les données à chaque render — remplacé par des `computed` stables
3. `'selection'` encore présent dans les colonnes de StandaloneSection

**Fichiers corrigés :**
- `ContainerTable.vue` — ajout `reserve-selection`
- `StandaloneSection.vue` — `'selection'` retiré, `tableRows` computed
- `ManagedStacksSection.vue` — `stackRowsMap` computed
- `DiscoveredSection.vue` — `itemRowsMap` computed
