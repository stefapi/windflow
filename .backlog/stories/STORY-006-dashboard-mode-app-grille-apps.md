# STORY-006 : Dashboard Mode App — Grille Apps

**Statut :** DONE
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux accéder rapidement à mes applications depuis le dashboard via une grille d'icônes cliquables de type Umbrel afin d'avoir une vue d'ensemble visuelle et intuitive de mes apps.

## Contexte technique

La vue [`Dashboard.vue`](frontend/src/views/Dashboard.vue) est enrichie avec une section "Mes Apps" contenant une grille d'icônes cliquables (type Umbrel). Chaque icône affiche : icône de l'app, nom, statut (dot coloré), domaine. Le clic sur une app navigue vers le Détail App.

Les widgets existants (métriques, activité, alertes) sont conservés mais repositionnés sous la grille Apps. Une salutation personnalisée ("Bonjour, {username}") est ajoutée en haut du dashboard.

Spécification de référence : [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écran 1

**Couches impactées :** Frontend uniquement (composants, vue, tests)

**Fichiers de référence (patterns) :**
- Composant grille item → pattern : [`AppCard.vue`](frontend/src/components/compute/AppCard.vue) (structure script setup, props, status dot, navigation)
- Composant grille container → pattern : [`Compute.vue`](frontend/src/views/Compute.vue) (utilisation de computeStore, helpers de conversion)
- Vue Dashboard → [`Dashboard.vue`](frontend/src/views/Dashboard.vue) (structure existante à enrichir)
- Tests composant → pattern : [`AppCard.spec.ts`](frontend/tests/unit/components/compute/AppCard.spec.ts)
- Tests vue → pattern : [`Compute.spec.ts`](frontend/tests/unit/views/Compute.spec.ts) (mocks stores, mounting)

**Exigences sécurité identifiées :**
- Auth : non — lecture seule, pas d'endpoint backend
- RBAC : non concerné — dashboard accessible à tout utilisateur authentifié
- Validation : aucune donnée utilisateur saisie
- Exposition : aucune donnée sensible affichée
- Audit : non requis (lecture seule)

## Critères d'acceptation (AC)
- [x] AC 1 : Une section "Mes Apps" avec grille d'icônes cliquables est affichée sur le dashboard, chaque icône montrant le nom de l'app et un indicateur de statut (dot coloré)
- [x] AC 2 : Le clic sur une icône app navigue vers le Détail App correspondant
- [x] AC 3 : Les widgets existants (métriques, activité, alertes) sont conservés et repositionnés sous la grille Apps
- [x] AC 4 : Une salutation personnalisée ("Bonjour, {username}") est affichée en haut du dashboard
- [x] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)

## État d'avancement technique
- [x] Tâche 1 : Composant AppGridTile — tuile cliquable pour la grille Apps
- [x] Tâche 2 : Composable useDashboardApps — agrégation des apps pour le dashboard
- [x] Tâche 3 : Refonte Dashboard.vue — grille Apps + salutation + repositionnement widgets
- [x] Tâche 4 : Export du composant AppGridTile depuis l'index
- [x] Tests unitaires composant AppGridTile
- [x] Tests unitaires composable useDashboardApps
- [x] Tests unitaires vue Dashboard
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Composant AppGridTile — tuile cliquable pour la grille Apps
**Objectif :** Créer un composant `AppGridTile.vue` représentant une seule tuile d'app dans la grille du dashboard. Chaque tuile affiche l'icône de l'app, son nom, un indicateur de statut (dot coloré), et le domaine. Le clic navigue vers le Détail App.
**Fichiers :**
- `frontend/src/components/dashboard/AppGridTile.vue` — Créer — Nouveau composant (pattern: [`AppCard.vue`](frontend/src/components/compute/AppCard.vue)). Script setup avec :
  - Props : `app: AppCardData` (type importé depuis [`helpers.ts`](frontend/src/components/compute/helpers.ts))
  - Computed `statusDotClass` : classe CSS du dot selon `app.statusColor` (success→bg-green-500, danger→bg-red-500, warning→bg-yellow-500, default→bg-blue-400)
  - Computed `isRunning` : basé sur `app.status`
  - Méthode `navigateToDetail()` : `router.push(\`/containers/${props.app.containerId}\`)`
  - Template : div cliquable `.app-grid-tile` avec :
    - Icône emoji `.app-grid-tile__icon` (text-3xl)
    - Nom de l'app `.app-grid-tile__name` (truncate si long)
    - Ligne statut : dot coloré + label statut
    - Domaine (si disponible) en petit texte
  - Scoped styles : cursor pointer, hover effect (scale + shadow), transition
- `frontend/src/components/dashboard/index.ts` — Créer — Barrel export pour les composants dashboard (export AppGridTile)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune (utilise `AppCardData` existant de STORY-004)

### Tâche 2 : Composable useDashboardApps — agrégation des apps pour le dashboard
**Objectif :** Créer un composable qui agrège toutes les apps (managed stacks, standalone, discovered) en une liste plate d'`AppCardData[]` prête à être affichée dans la grille du dashboard. Utilise le computeStore existant.
**Fichiers :**
- `frontend/src/composables/useDashboardApps.ts` — Créer — Nouveau composable. Exporte `useDashboardApps()` qui retourne :
  - `apps: ComputedRef<AppCardData[]>` — liste agrégée de toutes les apps (managed + standalone + discovered), triée par nom
  - `loading: ComputedRef<boolean>` — état de chargement du computeStore
  - `error: ComputedRef<string | null>` — erreur éventuelle
  - `fetchApps(orgId?: string): Promise<void>` — appelle `computeStore.fetchGlobal({ organization_id: orgId })` puis agrège
  - Logique d'agrégation : utilise les helpers existants `stackToAppCards`, `discoveredToAppCards`, `standaloneToAppCard` depuis [`helpers.ts`](frontend/src/components/compute/helpers.ts) pour convertir les données du computeStore en `AppCardData[]`
  - Tri : par `displayName` en ordre alphabétique
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune (utilise computeStore et helpers existants)

### Tâche 3 : Refonte Dashboard.vue — grille Apps + salutation + repositionnement widgets
**Objectif :** Enrichir la vue Dashboard existante avec la salutation personnalisée, la grille Apps en position prominente, et repositionner les widgets existants sous la grille.
**Fichiers :**
- `frontend/src/views/Dashboard.vue` — Modifier — Ajouter dans l'ordre :
  1. **Salutation** : `<h2 class="dashboard-greeting">Bonjour, {{ username }}</h2>` en haut, où `username` = `authStore.user?.full_name || authStore.user?.username || ''`
  2. **Section "Mes Apps"** : titre `<h3>Mes Apps</h3>` + grille responsive d'`AppGridTile` (grid CSS : `grid-template-columns: repeat(auto-fill, minmax(120px, 1fr))`, gap 16px)
  3. **State loading** : skeleton ou spinner pendant le chargement des apps
  4. **State vide** : message "Aucune app installée" avec lien vers `/compute` si la liste est vide
  5. **Widgets existants** : conserver tous les widgets existants (CounterCards, RecentDeployments, ResourceMetrics, DockerInfo, DeploymentMetrics, Alerts, TargetHealth, ActivityFeed, QuickActions, PluginWidgetZone) mais les repositionner sous la section "Mes Apps"
  6. **Script** : importer `useDashboardApps`, `useModeStore`, `AppGridTile` ; appeler `fetchApps()` dans le `onMounted` existant ; ajouter computed `username`
  7. **Styles** : ajouter `.dashboard-greeting` (font-size, margin-bottom), `.app-grid-section` (margin-bottom), `.app-grid` (display grid)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1, Tâche 2

### Tâche 4 : Export du composant AppGridTile depuis l'index
**Objectif :** S'assurer que le composant AppGridTile est correctement exporté pour réutilisation éventuelle.
**Fichiers :**
- `frontend/src/components/dashboard/index.ts` — Modifier (si déjà existant, sinon créé en Tâche 1) — Ajouter l'export barrel : `export { default as AppGridTile } from './AppGridTile.vue'`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

## Tests à écrire

### Unitaires Frontend — Composant AppGridTile
- `frontend/tests/unit/components/dashboard/AppGridTile.spec.ts`
  - `affiche l'icône, le nom et le statut de l'app` — rendu nominal avec une app running
  - `affiche le domaine quand disponible` — rendu conditionnel du domaine
  - `n'affiche pas le domaine quand absent` — domaine null masqué
  - `applique la classe de couleur verte pour le statut running` — dot coloré
  - `applique la classe de couleur rouge pour le statut stopped` — dot coloré
  - `navigue vers le détail app au clic` — interaction clic → router.push
  - `applique la classe de couleur jaune pour le statut paused` — dot coloré
  - `affiche le label de statut Mode App` — utilise statusLabel du vocabulaire

### Unitaires Frontend — Composable useDashboardApps
- `frontend/tests/unit/composables/useDashboardApps.spec.ts`
  - `retourne une liste vide quand le store est vide` — cas nominal sans données
  - `agrège les managed stacks en AppCardData` — conversion stacks
  - `agrège les standalone containers en AppCardData` — conversion standalone
  - `agrège les discovered items en AppCardData` — conversion discovered
  - `trie les apps par displayName` — ordre alphabétique
  - `expose le loading du computeStore` — réactivité loading
  - `expose l'erreur du computeStore` — réactivité error
  - `fetchApps appelle computeStore.fetchGlobal` — appel API

### Unitaires Frontend — Vue Dashboard
- `frontend/tests/unit/views/Dashboard.spec.ts`
  - `affiche la salutation avec le nom de l'utilisateur` — "Bonjour, {username}"
  - `affiche la salutation avec le username si pas de full_name` — fallback
  - `affiche la section Mes Apps avec la grille` — structure grille présente
  - `affiche les tuiles AppGridTile pour chaque app` — rendu des tuiles
  - `affiche le message vide quand aucune app` — état sans données
  - `conserve les widgets existants sous la grille` — CounterCards, ResourceMetrics, etc. toujours présents
  - `affiche le skeleton pendant le chargement` — état loading

### Commandes de validation
```bash
# Frontend
cd frontend && pnpm test -- tests/unit/components/dashboard/AppGridTile
cd frontend && pnpm test -- tests/unit/composables/useDashboardApps
cd frontend && pnpm test -- tests/unit/views/Dashboard
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-05-26

### Fichiers modifiés/créés
- `frontend/src/components/dashboard/AppGridTile.vue` : Créé — Composant tuile cliquable pour la grille Apps (icône, nom, statut dot, domaine, navigation)
- `frontend/src/components/dashboard/index.ts` : Créé — Barrel export des composants dashboard
- `frontend/src/composables/useDashboardApps.ts` : Créé — Composable d'agrégation des apps depuis le computeStore
- `frontend/src/views/Dashboard.vue` : Modifié — Ajout salutation, grille Apps, repositionnement widgets
- `frontend/tests/unit/components/dashboard/AppGridTile.spec.ts` : Créé — 9 tests
- `frontend/tests/unit/composables/useDashboardApps.spec.ts` : Créé — 8 tests
- `frontend/tests/unit/views/Dashboard.spec.ts` : Créé — 7 tests

### Décisions techniques
- Utilisation du type `AppCardData` existant (STORY-004) pour les tuiles de la grille, garantissant la cohérence avec la vue Compute
- Le composable `useDashboardApps` agrège les 3 sources (managed, standalone, discovered) en une seule liste triée
- La grille utilise CSS Grid avec `auto-fill` et `minmax(120px, 1fr)` pour un responsive naturel
- La salutation utilise `full_name` en priorité, avec fallback sur `username`

### Divergences par rapport à l'analyse
- Aucune divergence

### Difficultés rencontrées
- Variable `isRunning` non utilisée dans AppGridTile.vue → supprimée pour passer le build TypeScript strict

### Tests ajoutés
- `AppGridTile.spec.ts` : 9 tests (rendu, statut, navigation, conditions)
- `useDashboardApps.spec.ts` : 8 tests (agrégation, tri, loading, error, fetch)
- `Dashboard.spec.ts` : 7 tests (salutation, grille, widgets, états)
- **Total : 24 tests — tous passants ✅**
