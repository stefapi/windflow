# STORY-004 : Vue Liste Apps — Refonte Compute

**Statut :** DONE
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux voir mes applications sous forme de cards avec un vocabulaire non-technique ("Mes Apps", "Apps autonomes", "Apps détectées") afin de gérer mes applications sans connaissance infrastructure.

## Contexte technique

La vue [`Compute.vue`](frontend/src/views/Compute.vue) est transformée en vue "Apps" en Mode App. Les composants existants ([`ManagedStacksSection`](frontend/src/components/compute/ManagedStacksSection.vue), [`DiscoveredSection`](frontend/src/components/compute/DiscoveredSection.vue), [`StandaloneSection`](frontend/src/components/compute/StandaloneSection.vue)) sont conservés intact pour le Mode Infra. En Mode App, un nouveau composant `AppCard.vue` affiche chaque app sous forme de card avec actions inline.

Chaque app est présentée en card avec : icône (du stack), nom, version, domaine (si disponible), statut, RAM. Actions inline : Ouvrir, Logs, Terminal, Stop, menu contextuel `[⋯ Plus]`. Badge de mise à jour disponible `[⬆]`. Les sections ComputeStatsBanner et filtres avancés sont masquées en Mode App.

Spécification de référence : [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écran 2

**Couches impactées :** Frontend uniquement (vue, composant, helpers, tests)

**Fichiers de référence (patterns) :**
- Composant card → pattern : [`ContainerTable.vue`](frontend/src/components/compute/ContainerTable.vue) (structure props/emits/actions)
- Composable vocabulaire → [`useAppVocabulary.ts`](frontend/src/composables/useAppVocabulary.ts) (déjà existant, STORY-001)
- Menu contextuel → [`AppContextMenu.vue`](frontend/src/components/ui/AppContextMenu.vue) (déjà existant, STORY-003)
- Store mode → [`mode.ts`](frontend/src/stores/mode.ts) (déjà existant, STORY-002)
- Helpers compute → [`helpers.ts`](frontend/src/components/compute/helpers.ts) (types et normalisation existants)
- Tests vue → [`Compute.spec.ts`](frontend/tests/unit/views/Compute.spec.ts) (pattern de mock stores/stubs)
- Tests composant → [`AppContextMenu.spec.ts`](frontend/tests/unit/components/AppContextMenu.spec.ts) (pattern de test composant UI)

**Exigences sécurité identifiées :**
- Auth : non — couche présentation uniquement, pas de nouvel endpoint
- RBAC : non — les actions utilisent les APIs existantes
- Validation : non — pas de nouvel input utilisateur
- Exposition : non — données existantes affichées différemment
- Audit : non requis

## Critères d'acceptation (AC)
- [x] AC 1 : Les sections affichent "Mes Apps", "Apps autonomes", "Apps détectées" au lieu des termes techniques "Managed Stacks", "Standalone", "Discovered"
- [x] AC 2 : Chaque app est présentée en card avec icône, nom, version, domaine, statut et RAM
- [x] AC 3 : Les actions inline (Ouvrir, Logs, Terminal, Stop, menu contextuel `[⋯ Plus]`) fonctionnent sur chaque card
- [x] AC 4 : La recherche et le filtre par nom/statut fonctionnent ; les filtres avancés (type, technologie, target) et ComputeStatsBanner sont masqués en Mode App
- [x] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)
- STORY-003 (Menu Contextuel Canonique)

## État d'avancement technique
- [x] Tâche 1 : Type `AppCardData` et helper `toAppCardData()` dans `helpers.ts`
- [x] Tâche 2 : Composant `AppCard.vue` avec actions inline et menu contextuel
- [x] Tâche 3 : Refonte conditionnelle de `Compute.vue` pour le Mode App
- [x] Tâche 4 : Export `AppCard` depuis `index.ts`
- [x] Tests unitaires `AppCard.spec.ts`
- [x] Tests unitaires `Compute.spec.ts` (Mode App)
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Type `AppCardData` et helper `toAppCardData()` dans `helpers.ts`
**Objectif :** Créer un type unifié `AppCardData` et des fonctions de normalisation permettant de convertir n'importe quel objet compute (StackWithServices, DiscoveredItem, StandaloneContainer, ServiceWithMetrics) en données de card exploitables par `AppCard.vue`.
**Fichiers :**
- `frontend/src/components/compute/helpers.ts` — Modifier — Ajouter :
  - Interface `AppCardData` avec champs : `id`, `name`, `displayName` (via `getAppDisplayName`), `version` (extrait de l'image), `icon` (emoji ou icône du stack), `domain` (déduit des ports si HTTP exposé), `status` (statut technique Docker), `statusLabel` (via `getAppStatus`), `statusColor` (via `getAppStatus`), `ram` (memory_usage), `cpuPercent`, `category` (`'managed'` | `'standalone'` | `'discovered'`), `servicesTotal`, `servicesRunning`, `targetName`, `updateAvailable` (booléen, false par défaut), `containerId` (pour les actions API), `labels` (Record<string, string> pour le menu contextuel)
  - Fonction `stackToAppCards(stack: StackWithServices): AppCardData[]` — convertit chaque service d'une stack en card
  - Fonction `discoveredToAppCards(item: DiscoveredItem): AppCardData[]` — convertit chaque service découvert en card
  - Fonction `standaloneToAppCard(container: StandaloneContainer): AppCardData` — convertit un container standalone en card
  - Utiliser `getAppDisplayName()` de `useAppVocabulary` pour le nom affiché
  - Utiliser `getAppStatus()` de `useAppVocabulary` pour le statut Mode App
  - Extraire la version du tag image (ex: `nginx:1.26` → `1.26`, `nextcloud:28` → `28`)
  - Déduire le domaine des ports si un port 80/443 est exposé (format `http://host:port`)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune (utilise les types existants et `useAppVocabulary` de STORY-001)

### Tâche 2 : Composant `AppCard.vue` avec actions inline et menu contextuel
**Objectif :** Créer le composant card Mode App affichant une application avec ses informations (icône, nom, version, domaine, statut, RAM) et ses actions inline (Ouvrir, Logs, Terminal, Stop) + menu contextuel `[⋯ Plus]`.
**Fichiers :**
- `frontend/src/components/compute/AppCard.vue` — Créer — Nouveau composant (pattern: `ContainerTable.vue` pour la structure props/emits, `AppContextMenu.vue` pour le menu contextuel). Template avec :
  - Props : `app: AppCardData` (données de la card)
  - Header de card : icône (emoji du stack ou icône par défaut `📦`), `displayName`, `version` (el-tag small), indicateur de statut (dot coloré + label `statusLabel`)
  - Corps : `domain` (lien cliquable si présent), `targetName` (el-tag info), `servicesRunning/servicesTotal` si multi-services, `ram` (mémoire formatée)
  - Actions inline (footer) : boutons `Ouvrir` (lien externe si domain), `Logs` (router push vers `/containers/:id`), `Terminal` (router push), `Stop/Start` (selon statut) — utiliser `containersApi` pour les actions lifecycle
  - Menu contextuel `AppContextMenu` (de STORY-003) : props `containerId`, `containerName`, `containerStatus`, `domain`, `labels`
  - Badge `⬆` si `updateAvailable` est true
  - Émettre événements : `refresh` (après action lifecycle), `action(actionType, appId)`
  - Importer `useAppVocabulary` pour les labels d'actions
  - Importer `containersApi` pour les actions start/stop/restart
  - Utiliser `el-card` avec `shadow="hover"` pour l'effet de survol
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1 (type `AppCardData`)

### Tâche 3 : Refonte conditionnelle de `Compute.vue` pour le Mode App
**Objectif :** Modifier `Compute.vue` pour détecter le mode (App/Infra) via `useModeStore` et afficher conditionnellement soit la vue cards Mode App, soit la vue technique existante. En Mode App : masquer ComputeStatsBanner, les filtres avancés (technologie, target), le bouton "Par machine", la légende technique ; afficher les sections avec vocabulaire Mode App et les cards.
**Fichiers :**
- `frontend/src/views/Compute.vue` — Modifier — Changements :
  - Importer `useModeStore` depuis `@/stores/mode`
  - Importer `AppCard` depuis `@/components/compute`
  - Importer `toAppCards` helpers depuis `@/components/compute`
  - Importer `useAppVocabulary` depuis `@/composables/useAppVocabulary`
  - Ajouter `const modeStore = useModeStore()` et `const { translateTerm, getAppStatus } = useAppVocabulary()`
  - Header conditionnel : en Mode App afficher "Mes Apps" au lieu de "Containers — vue globale", sous-titre avec nombre d'apps au lieu de "targets / technologies"
  - Barre de filtres conditionnelle : en Mode App, masquer les pills technologie/target, ne garder que la recherche et le filtre par type avec labels Mode App ("Mes Apps", "Apps autonomes", "Apps détectées" au lieu de "Stacks WindFlow", "Standalone", "Discovered")
  - Masquer `ComputeStatsBanner` en Mode App (`v-if="modeStore.isInfraMode"`)
  - Masquer le bouton "Par machine" en Mode App
  - Masquer la légende technique en Mode App
  - En Mode App, pour chaque section (managed/standalone/discovered), itérer sur les `AppCardData` et rendre `AppCard` au lieu des sections techniques existantes
  - Conserver les sections techniques existantes intactes pour le Mode Infra (elles restent rendues quand `modeStore.isInfraMode`)
  - Conserver `ContainerCreateDialog` et `AdoptionWizard` dans les deux modes
  - Le bouton "+ Créer un container" devient "+ Nouvelle App" en Mode App
  - Ajouter des computed pour les listes de cards : `managedAppCards`, `standaloneAppCards`, `discoveredAppCards`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1, Tâche 2

### Tâche 4 : Export `AppCard` depuis `index.ts`
**Objectif :** Rendre le composant `AppCard` et les helpers associés disponibles via l'index du module compute.
**Fichiers :**
- `frontend/src/components/compute/index.ts` — Modifier — Ajouter :
  - `export { default as AppCard } from './AppCard.vue'`
  - Exporter les nouveaux helpers : `export { stackToAppCards, discoveredToAppCards, standaloneToAppCard } from './helpers'`
  - Exporter le type : `export type { AppCardData } from './helpers'`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1, Tâche 2

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Frontend

- `frontend/tests/unit/components/compute/AppCard.spec.ts`
  - `affiche le nom affiché, la version et le statut de l'app` — rendu nominal avec AppCardData complet
  - `affiche le domaine comme lien cliquable quand présent` — cas avec domain
  - `n'affiche pas le lien domaine quand absent` — cas sans domain
  - `affiche le badge de mise à jour quand updateAvailable est true` — badge ⬆ visible
  - `masque le badge de mise à jour quand updateAvailable est false` — badge absent
  - `affiche les actions inline Ouvrir, Logs, Terminal, Stop pour une app running` — actions visibles
  - `affiche l'action Start pour une app arrêtée` — action conditionnelle
  - `déclenche l'action stop au clic sur le bouton Stop` — interaction API
  - `émet l'événement refresh après une action lifecycle` — vérification emit
  - `rend le menu contextuel AppContextMenu avec les bonnes props` — intégration menu
  - `affiche la RAM et les informations de services` — rendu métriques

- `frontend/tests/unit/views/Compute.spec.ts` (ajouts Mode App)
  - `affiche le titre "Mes Apps" en Mode App` — rendu conditionnel header
  - `affiche "Containers — vue globale" en Mode Infra` — rendu conditionnel header
  - `masque ComputeStatsBanner en Mode App` — visibilité conditionnelle
  - `affiche ComputeStatsBanner en Mode Infra` — visibilité conditionnelle
  - `masque les filtres technologie et target en Mode App` — filtres avancés cachés
  - `affiche les filtres avancés en Mode Infra` — filtres visibles
  - `affiche les labels Mode App dans les filtres de type` — "Mes Apps", "Apps autonomes", "Apps détectées"
  - `masque la légende technique en Mode App` — légende cachée
  - `masque le bouton "Par machine" en Mode App` — bouton caché
  - `affiche les cards AppCard en Mode App au lieu des sections techniques` — rendu cards
  - `affiche les sections techniques en Mode Infra` — rendu tables
  - `la recherche filtre les apps en Mode App` — filtrage fonctionnel

- `frontend/tests/unit/components/compute/helpers.spec.ts` (ajouts)
  - `stackToAppCards convertit une stack avec services en cards` — cas nominal
  - `discoveredToAppCards convertit un discovered item en cards` — cas nominal
  - `standaloneToAppCard convertit un standalone container en card` — cas nominal
  - `toAppCardData extrait la version du tag image` — extraction version
  - `toAppCardData utilise getAppDisplayName pour le nom` — vocabulaire Mode App
  - `toAppCardData déduit le domaine des ports HTTP exposés` — déduction domaine
  - `toAppCardData gère le cas sans port exposé` — pas de domaine

### Commandes de validation
```bash
# Frontend
cd frontend && pnpm test -- tests/unit/components/compute/AppCard
cd frontend && pnpm test -- tests/unit/views/Compute
cd frontend && pnpm test -- tests/unit/components/compute/helpers
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

### Fichiers créés
- `frontend/src/components/compute/AppCard.vue` — Composant card Mode App avec actions inline (Ouvrir, Logs, Terminal, Stop/Start) et menu contextuel `[⋯ Plus]`
- `frontend/tests/unit/components/compute/AppCard.spec.ts` — 12 tests unitaires

### Fichiers modifiés
- `frontend/src/components/compute/helpers.ts` — Ajout de `AppCardData`, `AppCardCategory`, `extractVersion()`, `getAppIcon()`, `deduceDomain()`, `stackToAppCards()`, `discoveredToAppCards()`, `standaloneToAppCard()`
- `frontend/src/components/compute/index.ts` — Export de `AppCard` et des nouveaux helpers/types
- `frontend/src/views/Compute.vue` — Rendu conditionnel Mode App (cards) / Mode Infra (tables existantes)
- `frontend/tests/unit/components/compute/helpers.spec.ts` — 20 tests ajoutés (total : 48)
- `frontend/tests/unit/views/Compute.spec.ts` — 9 tests Mode App ajoutés (total : 23)

### Décisions techniques
- `extractVersion()` gère le format digest `@sha256:...` en retournant `''` (pas de version exploitable)
- `deduceDomain()` retourne une URL HTTPS pour le port 443, HTTP pour tout autre port public, `null` pour les ports loopback uniquement
- `getAppIcon()` utilise un mapping d'icônes emoji par nom d'app avec fallback `📦`
- Les tests utilisent `vi.hoisted()` pour les mocks mutables (pattern pour basculer entre Mode App/Infra dans les tests)
- Aucun TODO/FIXME/console.log/debugger laissé dans le code

### Résultat de validation
- Tests : 83/83 passants (48 helpers + 12 AppCard + 23 Compute)
- Build : ✅ passe
- Lint : 0 erreurs, 140 warnings (tous pré-existants `@typescript-eslint/no-explicit-any`)
