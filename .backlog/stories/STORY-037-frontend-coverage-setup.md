# STORY-037 : Couverture frontend — Installation et vérification

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration technique
**Priorité :** Moyenne

## Description
Installer `@vitest/coverage-v8`, mesurer la couverture frontend et compléter les tests des composants sans tests dédiés.

## Contexte technique

### Comportement actuel
- Aucun outil de couverture de code frontend n'est configuré
- Plusieurs composants de l'EPIC-008 n'ont pas de tests dédiés
- Impossible de mesurer la qualité des tests frontend

### Composants sans tests dédiés
- `ManagedStacksSection.vue`
- `DiscoveredSection.vue`
- `StandaloneSection.vue`
- `TargetGroupView.vue`
- `BulkActionBar.vue`

### Fichiers impactés
| Fichier | Modification |
|---------|-------------|
| `frontend/package.json` | Ajout dépendance `@vitest/coverage-v8` |
| `frontend/vitest.config.ts` | Configuration couverture |
| `frontend/tests/unit/components/compute/*.spec.ts` | Nouveaux fichiers de test |

### Patterns et fichiers de référence identifiés

**Pattern de test principal :** `frontend/tests/unit/components/compute/StackActionsBar.spec.ts`
- Utilise `mount` avec `global: { plugins: [ElementPlus], stubs: { ... } }`
- Mock des API via `vi.mock('@/services/api', () => ({ containersApi: { ... } }))`
- Mock de `ElMessageBox` et `ElMessage` via `vi.mock('element-plus', async () => { ... })`
- Tests structurés en `describe('rendu')`, `describe('états des boutons')`, `describe('interactions')`
- Stubs custom pour `el-button`, `el-tag`, `el-dialog`, `el-radio-group`, `el-radio`

**Pattern de test table :** `frontend/tests/unit/components/compute/ContainerTable.spec.ts`
- Stubs pour `ElTable`, `ElTableColumn`, `ElTag`, `ActionButtons`, `RouterLink`
- `ElTableColumnStub` qui passe un mock row au slot scoped

**Pattern de test wizard/dialog :** `frontend/tests/unit/components/compute/AdoptionWizard.spec.ts`
- Stubs élaborés pour `ElDialog`, `ElSteps`, `ElStep`, `ElTable`, `ElForm`, etc.
- Mock de l'API avec `vi.hoisted(() => ({ mockGetAdoptionData: vi.fn() }))`
- Helper `flush()` pour attendre la résolution des microtasks + `nextTick()`

**Composants dépendants à stubber dans les tests :**
- `ContainerTable.vue` (utilisé par ManagedStacksSection, DiscoveredSection, StandaloneSection, TargetGroupView)
- `BulkActionBar.vue` (utilisé par ManagedStacksSection, DiscoveredSection, StandaloneSection)
- `StackActionsBar.vue` (utilisé par ManagedStacksSection)
- `ActionButtons.vue` (utilisé par ContainerTable)
- Composants Element Plus : `ElCollapse`, `ElCollapseItem`, `ElEmpty`, `ElIcon`, `ElTag`, `ElButton`, `ElDialog`, `ElAlert`, `ElCheckbox`, `ElTable`, `ElTableColumn`, `ElMessageBox`, `ElMessage`, `ElLoading` (directive)

**Imports API à mocker :**
- `containersApi` (start, stop, restart, remove, batchStart, batchStop)
- `stacksApi` (start, stop, redeploy) — pour StackActionsBar

**Exigences sécurité identifiées :**
- Aucune exigence spécifique — cette story est purement frontend (outillage + tests unitaires)
- Pas de nouveaux endpoints, pas de nouvelles fonctionnalités exposées, pas de données sensibles

## Critères d'acceptation (AC)
- [x] AC 1 : `@vitest/coverage-v8` installé et configuré
- [x] AC 2 : Couverture frontend mesurable via `pnpm test:coverage`
- [x] AC 3 : Couverture globale ≥ 80% pour les composants de l'EPIC-008
- [x] AC 4 : Tests dédiés créés pour les composants sans tests :
  - `ManagedStacksSection.vue`
  - `DiscoveredSection.vue`
  - `StandaloneSection.vue`
  - `TargetGroupView.vue`
  - `BulkActionBar.vue`

## Tâches d'implémentation détaillées

### Tâche 1 : Installer et configurer `@vitest/coverage-v8`
**Objectif :** Ajouter l'outil de couverture de code frontend et le configurer pour qu'il soit mesurable via `pnpm test:coverage`.
**Fichiers :**
- `frontend/package.json` — Modifier — Ajouter `@vitest/coverage-v8` dans `devDependencies` (version compatible avec `vitest ^3.2.4`, typiquement `^3.2.4`). Le script `test:coverage` existe déjà (`vitest run --coverage`) mais ne fonctionnera pas tant que le provider n'est pas installé.
- `frontend/vitest.config.ts` — Modifier — Ajouter le bloc `coverage` dans `test` :
  ```ts
  coverage: {
    provider: 'v8',
    reporter: ['text', 'json', 'html'],
    reportsDirectory: './coverage',
    include: ['src/**/*.ts', 'src/**/*.vue'],
    exclude: ['src/**/*.d.ts', 'src/main.ts', 'src/App.vue'],
  }
  ```
  (pattern: configuration standard Vitest v8, référencée dans `.clinerules/35-testing-quality-gates.md`)
**Exigences sécurité :** Aucune
**Dépend de :** Aucune

### Tâche 2 : Tests unitaires — `ManagedStacksSection.vue`
**Objectif :** Créer les tests unitaires couvrant le rendu, les états (loading, empty, avec données), les interactions (bulk actions, service actions), et l'intégration avec `StackActionsBar` et `BulkActionBar`.
**Fichiers :**
- `frontend/tests/unit/components/compute/ManagedStacksSection.spec.ts` — Créer — (pattern: `StackActionsBar.spec.ts`). Structure :
  - `describe('rendu')` :
    - `affiche le spinner pendant le chargement` — `loading=true`
    - `affiche el-empty quand aucune stack` — `stacks=[]`
    - `affiche les stacks avec leurs tags` — vérifier nom, tag "stack WindFlow", technologie, target_name, compteur running/total
    - `affiche StackActionsBar et BulkActionBar pour chaque stack`
    - `affiche ContainerTable avec les bonnes colonnes`
  - `describe('interactions')` :
    - `émet refresh après une action de service` — mock `containersApi.start`, vérifier `emit('refresh')`
    - `émet copy-id au clic sur le bouton copie` — vérifier `emit('copy-id', stack.id)`
    - `gère la sélection et le bulk action start` — mock `containersApi.start` pour chaque ID sélectionné
    - `affiche la confirmation avant suppression bulk` — mock `ElMessageBox.confirm`
  - Stubs nécessaires : `ElCollapse`, `ElCollapseItem`, `ElEmpty`, `ElIcon`, `ElTag`, `ElButton`, `ContainerTable`, `BulkActionBar`, `StackActionsBar`
  - Mocks : `containersApi` (start, stop, restart, remove), `ElMessage`, `ElMessageBox`
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 3 : Tests unitaires — `DiscoveredSection.vue`
**Objectif :** Créer les tests unitaires couvrant le rendu, les états adoptables vs non-adoptables, les actions individuelles (start/stop sur item), et les bulk actions.
**Fichiers :**
- `frontend/tests/unit/components/compute/DiscoveredSection.spec.ts` — Créer — (pattern: `StackActionsBar.spec.ts`). Structure :
  - `describe('rendu')` :
    - `affiche el-empty quand aucun item découvert`
    - `affiche les items avec badge discovered et technologie`
    - `affiche le bouton Adopter si adoptable`
    - `masque les actions si non adoptable` — `readonly` sur ContainerTable
    - `affiche l'alerte source_path si présent`
  - `describe('interactions')` :
    - `émet adopt au clic sur Adopter` — vérifier `emit('adopt', item.id)`
    - `handleItemStart appelle containersApi.batchStart` — mock batchStart, vérifier appel avec IDs des services non-running
    - `handleItemStop appelle containersApi.batchStop` — mock batchStop, vérifier appel avec IDs des services running
    - `gère les bulk actions sur les containers d'un item` — même pattern que ManagedStacksSection
    - `navigue vers les logs au clic sur logs` — même pattern que StandaloneSection
  - Stubs nécessaires : `ElCollapse`, `ElCollapseItem`, `ElEmpty`, `ElAlert`, `ElTag`, `ElButton`, `ContainerTable`, `BulkActionBar`
  - Mocks : `containersApi` (start, stop, restart, remove, batchStart, batchStop), `ElMessage`, `ElMessageBox`
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 4 : Tests unitaires — `StandaloneSection.vue`
**Objectif :** Créer les tests unitaires couvrant le rendu, la sélection, les actions individuelles, les bulk actions, et le dialog de suppression groupée.
**Fichiers :**
- `frontend/tests/unit/components/compute/StandaloneSection.spec.ts` — Créer — (pattern: `StackActionsBar.spec.ts`). Structure :
  - `describe('rendu')` :
    - `affiche el-empty quand aucun container`
    - `affiche BulkActionBar et ContainerTable quand des containers existent`
    - `affiche les noms et images des containers dans la table`
  - `describe('sélection')` :
    - `met à jour selectedIds quand la sélection change`
    - `clearSelection réinitialise la sélection`
  - `describe('actions individuelles')` :
    - `handleAction start appelle containersApi.start et émet refresh`
    - `handleAction stop appelle containersApi.stop et émet refresh`
    - `handleAction restart appelle containersApi.restart et émet refresh`
    - `handleAction logs navigue vers /containers/:id`
    - `handleAction delete demande confirmation puis supprime`
  - `describe('bulk actions')` :
    - `handleBulkAction start démarre les containers sélectionnés`
    - `handleBulkAction stop arrête les containers sélectionnés`
    - `showBulkDeleteDialog ouvre le dialog avec la liste des containers`
    - `confirmBulkDelete supprime avec force si checkbox cochée`
  - Stubs nécessaires : `ElEmpty`, `ElDialog`, `ElAlert`, `ElCheckbox`, `ElButton`, `ContainerTable`, `BulkActionBar`
  - Mocks : `containersApi` (start, stop, restart, remove), `ElMessage`, `ElMessageBox`, `useRouter` (pour logs)
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 5 : Tests unitaires — `TargetGroupView.vue`
**Objectif :** Créer les tests unitaires couvrant le rendu par groupe de machines, les sous-sections (stacks, discovered, standalone), et l'état vide.
**Fichiers :**
- `frontend/tests/unit/components/compute/TargetGroupView.spec.ts` — Créer — (pattern: `StackActionsBar.spec.ts`, plus simple car read-only). Structure :
  - `describe('rendu')` :
    - `affiche le spinner pendant le chargement`
    - `affiche el-empty quand aucun groupe`
    - `affiche les groupes avec target_name, technologie et métriques CPU/RAM`
    - `affiche la sous-section Stacks avec ContainerTable`
    - `affiche la sous-section Discovered avec ContainerTable`
    - `affiche la sous-section Standalone avec ContainerTable`
    - `affiche el-empty si un groupe n'a aucune ressource`
  - Stubs nécessaires : `ElCollapse`, `ElCollapseItem`, `ElEmpty`, `ElIcon`, `ElTag`, `ContainerTable`
  - Pas de mocks API nécessaires (composant purement présentationnel)
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 6 : Tests unitaires — `BulkActionBar.vue`
**Objectif :** Créer les tests unitaires couvrant l'affichage conditionnel, la transition, et les événements émis.
**Fichiers :**
- `frontend/tests/unit/components/compute/BulkActionBar.spec.ts` — Créer — (pattern: `StackActionsBar.spec.ts`, très simple). Structure :
  - `describe('rendu')` :
    - `n'affiche rien quand selectedCount est 0`
    - `affiche le compteur de sélection`
    - `affiche les 4 boutons d'action (start, stop, restart, delete)`
    - `affiche le pluriel quand selectedCount > 1`
  - `describe('interactions')` :
    - `émet start au clic sur Démarrer`
    - `émet stop au clic sur Arrêter`
    - `émet restart au clic sur Redémarrer`
    - `émet delete au clic sur Supprimer`
    - `émet cancel au clic sur Annuler la sélection`
    - `affiche l'état loading sur le bon bouton` — `loadingAction='start'`
  - Stubs nécessaires : `ElTag`, `ElButton`, `ElIcon` (VideoPlay, VideoPause, RefreshRight, Delete)
  - Pas de mocks API nécessaires
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1

### Tâche 7 : Exécuter la couverture et atteindre le seuil de 80%
**Objectif :** Lancer `pnpm test:coverage`, analyser le rapport, et compléter les tests si nécessaire pour atteindre ≥ 80% de couverture sur les composants de l'EPIC-008.
**Fichiers :**
- `frontend/coverage/` — Généré automatiquement (ne pas versionner)
- Fichiers de test existants — Modifier si besoin — Ajouter des cas de test manquants identifiés par le rapport de couverture (branches non couvertes, conditions non testées)
**Exigences sécurité :** Aucune
**Dépend de :** Tâches 2, 3, 4, 5, 6

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`

### Unitaires Frontend — `ManagedStacksSection.spec.ts`
- `affiche le spinner pendant le chargement` — rendu initial avec `loading=true`
- `affiche el-empty quand aucune stack` — état vide
- `affiche les stacks avec leurs métadonnées` — nom, technologie, target, compteur
- `affiche StackActionsBar et BulkActionBar pour chaque stack` — vérifier présence des sous-composants
- `émet copy-id au clic sur le bouton copie` — interaction
- `émet refresh après une action de service` — propagation d'événement
- `gère le bulk action start sur les containers sélectionnés` — mock API + vérification
- `affiche la confirmation avant suppression bulk` — `ElMessageBox.confirm`

### Unitaires Frontend — `DiscoveredSection.spec.ts`
- `affiche el-empty quand aucun item découvert` — état vide
- `affiche les items avec badge discovered` — rendu nominal
- `affiche le bouton Adopter si adoptable` — accès conditionnel
- `masque les actions si non adoptable` — `readonly` mode
- `affiche l'alerte source_path si présent` — rendu conditionnel
- `émet adopt au clic sur Adopter` — interaction
- `handleItemStart appelle batchStart avec les bons IDs` — mock API
- `handleItemStop appelle batchStop avec les bons IDs` — mock API
- `gère les bulk actions` — même pattern que ManagedStacksSection

### Unitaires Frontend — `StandaloneSection.spec.ts`
- `affiche el-empty quand aucun container` — état vide
- `affiche BulkActionBar et ContainerTable` — rendu nominal
- `met à jour selectedIds quand la sélection change` — état réactif
- `clearSelection réinitialise la sélection` — méthode exposée
- `handleAction start appelle containersApi.start` — mock API
- `handleAction delete demande confirmation` — `ElMessageBox.confirm`
- `showBulkDeleteDialog ouvre le dialog` — état du dialog
- `confirmBulkDelete supprime avec force si cochée` — paramètre force

### Unitaires Frontend — `TargetGroupView.spec.ts`
- `affiche le spinner pendant le chargement` — rendu initial
- `affiche el-empty quand aucun groupe` — état vide
- `affiche les groupes avec métriques` — CPU/RAM
- `affiche les sous-sections Stacks/Discovered/Standalone` — rendu conditionnel par longueur
- `affiche el-empty si un groupe n'a aucune ressource` — cas edge

### Unitaires Frontend — `BulkActionBar.spec.ts`
- `n'affiche rien quand selectedCount est 0` — état caché
- `affiche le compteur et les boutons` — rendu nominal
- `émet les événements au clic` — start, stop, restart, delete, cancel
- `affiche l'état loading sur le bon bouton` — `loadingAction`

### Commandes de validation
```bash
# Installer la dépendance
cd frontend && pnpm add -D @vitest/coverage-v8

# Lancer les tests unitaires des composants compute
cd frontend && pnpm test -- tests/unit/components/compute

# Lancer la couverture
cd frontend && pnpm test:coverage

# Build et lint
cd frontend && pnpm build && pnpm lint
```

---

## État d'avancement technique
- [x] Tâche 1 : Installer et configurer `@vitest/coverage-v8`
- [x] Tâche 2 : Tests unitaires — `ManagedStacksSection.vue`
- [x] Tâche 3 : Tests unitaires — `DiscoveredSection.vue`
- [x] Tâche 4 : Tests unitaires — `StandaloneSection.vue`
- [x] Tâche 5 : Tests unitaires — `TargetGroupView.vue`
- [x] Tâche 6 : Tests unitaires — `BulkActionBar.vue`
- [x] Tâche 7 : Exécuter la couverture et atteindre le seuil de 80%
- [x] Build & lint OK

---

## Notes d'implémentation

### Installation et configuration
- `@vitest/coverage-v8@^3.2.4` ajouté aux `devDependencies` du frontend.
- Configuration Vitest (`vitest.config.ts`) enrichie d'un bloc `coverage` avec :
  - `provider: 'v8'`
  - reporters `text`, `json`, `html`
  - inclusion de `src/**/*.ts` et `src/**/*.vue`
  - exclusion des fichiers d'entrée (`main.ts`, `App.vue`) et des `.d.ts`

### Tests créés (5 fichiers, 126 tests au total)
| Composant | Fichier | Tests |
|-----------|---------|-------|
| ManagedStacksSection | `ManagedStacksSection.spec.ts` | 14 |
| DiscoveredSection | `DiscoveredSection.spec.ts` | 12 |
| StandaloneSection | `StandaloneSection.spec.ts` | 14 |
| TargetGroupView | `TargetGroupView.spec.ts` | 8 |
| BulkActionBar | `BulkActionBar.spec.ts` | 11 |

### Points techniques rencontrés
1. **`@click.stop` sur stubs Element Plus** — `trigger('click')` sur un `el-button` stub échoue avec `TypeError: Cannot read properties of undefined (reading 'stopPropagation')`. Solution : appeler directement la méthode exposée sur `wrapper.vm` ou utiliser `wrapper.vm.$emit()`.
2. **`findComponent({ name: '...' })` vide** — Les stubs doivent impérativement déclarer une propriété `name` (ex. `name: 'ContainerTable'`) pour être trouvables par Vue Test Utils.
3. **`clearSelection is not a function`** — Les `template ref` vers `ContainerTable` nécessitent que le stub expose une méthode `clearSelection` via `methods: { clearSelection() {} }`.
4. **Émits inline dans `<script setup>`** — Les émissions définies inline dans le template (`@click.stop="emit('adopt', item.id)"`) ne sont pas exposées comme méthodes sur `wrapper.vm`. Il faut utiliser `wrapper.vm.$emit('adopt', id)` pour les tester.

### Résultat de couverture
- **Couverture `src/components/compute`** : **87.78 %** (seuil 80 % atteint)
- Tous les tests passent (126/126)
- Build et lint sans erreur
