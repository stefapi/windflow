# STORY-002 : Refonte Sidebar — Navigation Mode App

**Statut :** DONE
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux une sidebar simplifiée en Mode App (Dashboard, Apps, Marketplace, Plugins, Settings) afin de naviguer dans l'interface avec un vocabulaire non-technique adapté à une expérience grand public.

## Contexte technique

La sidebar actuelle ([`SidebarNav.vue`](frontend/src/components/SidebarNav.vue)) affiche les entrées Infrastructure, Stockage & Réseau, Marketplace, Administration. En Mode App, elle doit afficher : Dashboard, Apps (remplace Compute), Marketplace, Plugins, Settings.

Les entrées techniques (Volumes, Networks, Images, Compute, Targets, Stacks, Deployments, Workflows, Schedules) sont masquées mais restent accessibles via URL directe. Un store Pinia `modeStore` gère l'état du mode (App/Infra) persisté dans `localStorage`.

Le toggle `[🔧 Mode Infra]` en bas de sidebar est présent mais désactivé (grisé) avec tooltip "Bientôt disponible".

Spécification de référence : [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md)

**Couches impactées :** Frontend uniquement (Store Pinia, Composant Sidebar, Types)

**Fichiers de référence :**
- Store Pinia → pattern : [`frontend/src/stores/theme.ts`](frontend/src/stores/theme.ts) (localStorage persistence, ref + watch)
- Composant Sidebar → existant : [`frontend/src/components/SidebarNav.vue`](frontend/src/components/SidebarNav.vue)
- Types navigation → existant : [`frontend/src/types/navigation.ts`](frontend/src/types/navigation.ts) (NavItem, NavSection)
- Composable sidebar → existant : [`frontend/src/composables/useSidebar.ts`](frontend/src/composables/useSidebar.ts)
- Tests composant → pattern : [`frontend/tests/unit/components/SidebarNav.spec.ts`](frontend/tests/unit/components/SidebarNav.spec.ts)
- Tests composable → pattern : [`frontend/tests/unit/composables/useAppVocabulary.spec.ts`](frontend/tests/unit/composables/useAppVocabulary.spec.ts)

**Exigences sécurité identifiées :**
- Auth : non — couche présentation uniquement, pas d'endpoint
- RBAC : non concerné
- Validation : non — pas d'input utilisateur
- Exposition : aucune donnée sensible
- Audit : non requis

## Critères d'acceptation (AC)
- [x] AC 1 : La sidebar affiche la navigation Mode App (Dashboard, Apps, Marketplace, Plugins, Settings) quand le mode est "App"
- [x] AC 2 : Les entrées techniques (Volumes, Networks, Images, Targets, Stacks, Deployments, Workflows, Schedules) sont masquées de la sidebar en Mode App mais restent accessibles via URL directe
- [x] AC 3 : Le toggle Mode Infra est visible mais désactivé avec tooltip "Bientôt disponible"
- [x] AC 4 : Un store Pinia `modeStore` gère l'état du mode (App/Infra) persisté dans `localStorage`
- [x] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)

## État d'avancement technique
- [x] Tâche 1 : Créer le store Pinia `modeStore`
- [x] Tâche 2 : Ajouter le type `UIMode` et les constantes de navigation Mode App
- [x] Tâche 3 : Modifier `SidebarNav.vue` pour afficher la navigation conditionnelle
- [x] Tâche 4 : Ajouter le toggle Mode Infra désactivé dans le footer
- [x] Tests unitaires — store `modeStore`
- [x] Tests unitaires — composant `SidebarNav.vue` (Mode App)
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Créer le store Pinia `modeStore`
**Objectif :** Créer un store Pinia qui gère l'état du mode UI (App/Infra), persisté dans `localStorage`, avec "app" comme valeur par défaut.
**Fichiers :**
- `frontend/src/stores/mode.ts` — Créer — Nouveau store Pinia (pattern : [`theme.ts`](frontend/src/stores/theme.ts)). Utiliser la syntaxe Setup Store (`defineStore('mode', () => {...})`). Contenu :
  - Type `UIMode = 'app' | 'infra'`
  - Constante `STORAGE_KEY = 'windflow-ui-mode'`
  - `ref<UIMode>` initialisé depuis `localStorage` (défaut : `'app'`)
  - `watch` pour persister dans `localStorage` au changement
  - Computed : `isAppMode`, `isInfraMode`
  - Méthode `setMode(mode: UIMode)` — ne fait rien si mode identique
  - Méthode `toggleMode()` — switch app↔infra
- `frontend/src/stores/index.ts` — Modifier — Ajouter l'export `export { useModeStore } from './mode'`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Ajouter le type `UIMode` et les constantes de navigation Mode App
**Objectif :** Définir le type `UIMode` et les tableaux `NavItem[]` pour la navigation Mode App, réutilisables par `SidebarNav.vue`.
**Fichiers :**
- `frontend/src/types/navigation.ts` — Modifier — Ajouter :
  - Type `UIMode = 'app' | 'infra'`
  - Export du type
- `frontend/src/composables/useSidebarNav.ts` — Créer — Nouveau composable qui centralise les items de navigation selon le mode. Contenu :
  - Import `useModeStore`
  - Import les icônes Element Plus nécessaires
  - Tableau `appModeItems` : Dashboard (`Odometer`, `/`), Apps (`Connection`, `/compute`), Marketplace (`ShoppingCart`, `/marketplace`, badge `'Bientôt'`), Plugins (`Grid`, `/plugins`, badge `'Bientôt'`), Settings (`Setting`, `/settings`)
  - Tableau `infraModeItems` : les sections existantes (Infrastructure, Stockage & Réseau, Marketplace, Administration) — refactor des tableaux actuels de `SidebarNav.vue`
  - Computed `navSections` qui retourne les sections selon le mode actif
  - Computed `isAppMode` raccourci vers le store
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Modifier `SidebarNav.vue` pour afficher la navigation conditionnelle
**Objectif :** Rendre la sidebar conditionnelle au mode (App/Infra) en utilisant le composable `useSidebarNav`. En Mode App, afficher uniquement : Dashboard, Apps, Marketplace, Plugins, Settings. Masquer les sections Infrastructure, Stockage & Réseau, Administration.
**Fichiers :**
- `frontend/src/components/SidebarNav.vue` — Modifier — Refactor significatif :
  - Importer `useModeStore` et le composable `useSidebarNav`
  - Remplacer les tableaux statiques (`infrastructureItems`, `storageNetworkItems`, `marketplaceItems`, `administrationItems`) par les données du composable
  - Le template doit itérer sur `navSections` du composable au lieu des sections codées en dur
  - En Mode App : afficher uniquement les sections "Dashboard" (sans titre), "Workloads" (Apps, Marketplace, Plugins), et "Settings"
  - En Mode Infra : conserver le comportement actuel (Infrastructure, Stockage & Réseau, Marketplace, Administration)
  - La section Plugins dynamiques (`pluginNavStore`) reste visible dans les deux modes
  - Conserver le footer existant (target selector, user info)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

### Tâche 4 : Ajouter le toggle Mode Infra désactivé dans le footer de la sidebar
**Objectif :** Ajouter un bouton toggle "🔧 Mode Infra" en bas de la sidebar, visible mais désactivé (grisé) avec un tooltip "Bientôt disponible". Ce toggle préfigure la bascule future entre modes.
**Fichiers :**
- `frontend/src/components/SidebarNav.vue` — Modifier — Ajouter dans le footer (avant le target-selector) :
  - Un `<div class="mode-toggle">` contenant un `<el-tooltip content="Bientôt disponible">` et un `<button disabled>` avec l'icône `Setting` et le label "Mode Infra"
  - Style : opacité réduite, curseur `not-allowed`, couleur grisée
  - Le bouton est `disabled` et ne déclenche aucune action
  - Visible uniquement si `!isCollapsed` (pas en mode rétracté)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 3

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`

### Unitaires Frontend — Store `modeStore`
- `frontend/tests/unit/stores/mode.spec.ts`
  - `initialise en mode App par défaut` — cas nominal : pas de valeur dans localStorage
  - `restaure le mode depuis localStorage` — cas nominal : valeur 'infra' stockée
  - `persiste le mode dans localStorage au changement` — vérification du watch
  - `setMode ne fait rien si mode identique` — cas limite
  - `toggleMode bascule de app à infra` — interaction
  - `toggleMode bascule de infra à app` — interaction
  - `isAppMode retourne true en mode app` — computed
  - `isInfraMode retourne true en mode infra` — computed

### Unitaires Frontend — Composant `SidebarNav.vue` (Mode App)
- `frontend/tests/unit/components/SidebarNav.spec.ts` — Ajouter un nouveau `describe('STORY-002: Mode App', ...)` dans le fichier existant :
  - `affiche la navigation Mode App quand le mode est App` — vérifier présence de Dashboard, Apps, Marketplace, Plugins, Settings
  - `masque les entrées techniques en Mode App` — vérifier absence de Volumes, Networks, Images, Targets, Stacks, Compute
  - `affiche la navigation Mode Infra quand le mode est Infra` — vérifier présence des sections Infrastructure, Stockage & Réseau
  - `affiche le toggle Mode Infra désactivé` — vérifier présence du bouton disabled
  - `le toggle Mode Infra a le tooltip Bientôt disponible` — vérifier le tooltip
  - `le toggle Mode Infra est grisé et disabled` — vérifier les attributs

### Commandes de validation
```bash
# Frontend — tests ciblés
cd frontend && pnpm test -- tests/unit/stores/mode
cd frontend && pnpm test -- tests/unit/components/SidebarNav

# Build & lint
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-05-26

### Fichiers modifiés/créés
- `frontend/src/stores/mode.ts` : Création du store Pinia `modeStore` avec persistance localStorage
- `frontend/src/stores/index.ts` : Ajout de l'export `useModeStore`
- `frontend/src/types/navigation.ts` : Ajout du type `UIMode`
- `frontend/src/composables/useSidebarNav.ts` : Création du composable centralisant les items de navigation par mode
- `frontend/src/components/SidebarNav.vue` : Refactor complet — navigation conditionnelle via composable, ajout toggle Mode Infra désactivé
- `frontend/tests/unit/stores/mode.spec.ts` : 13 tests unitaires du store modeStore
- `frontend/tests/unit/components/SidebarNav.spec.ts` : 8 tests STORY-002 ajoutés (navigation Mode App + toggle)

### Décisions techniques
- `watch` avec `flush: 'sync'` dans le store pour persistance localStorage immédiate (nécessaire pour les tests synchrones)
- Mock `modeStore` par défaut en mode Infra dans les tests existants pour backward compatibility
- Utilisation de `vi.hoisted()` pour partager le mock entre les blocs de tests
- Navigation items définis dans le composable `useSidebarNav` et non dans le composant, pour séparation des responsabilités

### Divergences par rapport à l'analyse
- Aucune divergence significative

### Tests ajoutés
- `frontend/tests/unit/stores/mode.spec.ts` : 13 tests (initialisation, persistance, setMode, toggleMode, computed)
- `frontend/tests/unit/components/SidebarNav.spec.ts` : 8 tests STORY-002 (navigation Mode App, masquage entrées techniques, toggle Mode Infra)
