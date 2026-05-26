# STORY-003 : Menu Contextuel `[⋯ Plus]` Canonique

**Statut :** DONE
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux un menu contextuel standardisé `[⋯ Plus]` pour chaque app afin d'avoir une expérience cohérente et intuitive pour accéder aux actions disponibles sur mes applications.

## Contexte technique

Le composant réutilisable `AppContextMenu` remplace les boutons d'action dispersés. Il affiche un menu déroulant avec 3 sections : Actions principales (Ouvrir, Start/Stop, Redémarrer), Outils (Logs, Console, Config), Avancé (Détails techniques, Supprimer). La section Avancé est la seule zone où le vocabulaire technique peut apparaître en Mode App.

Ce composant est utilisé depuis la liste Apps, le dashboard et le détail App.

Spécification de référence : [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md)

**Couches impactées :** Frontend uniquement (composant UI, composable, types)

**Fichiers de référence (patterns) :**
- Composant UI → pattern : [`ActionButtons.vue`](frontend/src/components/ui/ActionButtons.vue) (props, emits, icônes Element Plus)
- Composable → pattern : [`useAppVocabulary.ts`](frontend/src/composables/useAppVocabulary.ts) (fonctions pures + composable wrapper)
- Types → pattern : [`vocabulary.ts`](frontend/src/types/vocabulary.ts) (interfaces, consts, types exportés)
- Export barrel → pattern : [`ui/index.ts`](frontend/src/components/ui/index.ts)
- Tests composant → pattern : [`SidebarNav.spec.ts`](frontend/tests/unit/components/SidebarNav.spec.ts) (mount, mocks stores, assertions template)
- Tests composable → pattern : [`useAppVocabulary.spec.ts`](frontend/tests/unit/composables/useAppVocabulary.spec.ts)

**Dépendances déjà complétées :**
- STORY-001 ✅ : [`useAppVocabulary`](frontend/src/composables/useAppVocabulary.ts), [`vocabulary.ts`](frontend/src/types/vocabulary.ts) (APP_ACTIONS, VOCABULARY_MAP, HIDDEN_TERMS)
- STORY-002 ✅ : [`modeStore`](frontend/src/stores/mode.ts) (isAppMode, isInfraMode)

**Exigences sécurité identifiées :**
- Auth : non (composant UI pur, pas d'appel API)
- RBAC : non applicable
- Validation : non (pas d'input utilisateur)
- Exposition : non (pas de données sensibles)
- Audit : non requis

## Critères d'acceptation (AC)
- [x] AC 1 : Le composant `AppContextMenu` affiche les 3 sections (Actions principales, Outils, Avancé) avec un séparateur entre Outils et Avancé
- [x] AC 2 : Le menu est utilisable et cohérent depuis la liste Apps, le dashboard et le détail App
- [x] AC 3 : Le vocabulaire technique n'apparaît que dans la section Avancé du menu en Mode App
- [x] AC 4 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)

## État d'avancement technique
- [x] Tâche 1 : Types et constantes du menu contextuel
- [x] Tâche 2 : Composable useAppContextMenu
- [x] Tâche 3 : Composant AppContextMenu.vue
- [x] Tâche 4 : Export barrel et intégration
- [x] Tests unitaires composable
- [x] Tests unitaires composant
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Types et constantes du menu contextuel
**Objectif :** Définir les interfaces TypeScript et les constantes qui décrivent la structure canonique du menu contextuel (3 sections ordonnées : Actions principales, Outils, Avancé).
**Fichiers :**
- `frontend/src/types/context-menu.ts` — Créer — Nouveau fichier de types (pattern: `vocabulary.ts`). Définir :
  - `ContextMenuItem` : `{ action: string, label: string, icon: string, disabled?: boolean, danger?: boolean, visible?: boolean }`
  - `ContextMenuSection` : `{ key: string, label: string, items: ContextMenuItem[] }`
  - `AppContextMenuProps` : `{ containerId: string, containerName: string, containerStatus: string, domain?: string, labels?: Record<string, string> }`
  - Constante `CONTEXT_MENU_SECTIONS` : les 3 sections canoniques avec leurs clés (`'primary'`, `'tools'`, `'advanced'`) et labels
- `frontend/src/types/vocabulary.ts` — Modifier — Étendre `APP_ACTIONS` pour ajouter les actions manquantes du menu contextuel : `restart` (Redémarrer, icon RefreshRight), `delete` (Supprimer, icon Delete), `details` (Détails techniques, icon InfoFilled). Ce sont des actions qui apparaissent dans le menu `[⋯ Plus]` mais pas dans l'action bar inline.
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Composable useAppContextMenu
**Objectif :** Créer le composable qui génère les sections du menu contextuel en fonction du statut du container et du mode (App/Infra). En Mode App, le vocabulaire technique n'apparaît que dans la section Avancé.
**Fichiers :**
- `frontend/src/composables/useAppContextMenu.ts` — Créer — Nouveau composable (pattern: `useAppVocabulary.ts`). Exporter `useAppContextMenu(props: AppContextMenuProps)` retournant :
  - `sections: ComputedRef<ContextMenuSection[]>` — les 3 sections calculées dynamiquement
  - `isMenuVisible: ComputedRef<boolean>` — au moins une action disponible
  - `getActionHandler(action: string): () => void` — mappe une action à un handler qui émet l'événement correspondant
  - Logique :
    - Section "Actions principales" : Ouvrir (si domain), Start/Stop (selon status), Redémarrer (si running)
    - Section "Outils" : Logs, Console, Config
    - Section "Avancé" : Détails techniques (vocabulaire technique autorisé ici), Supprimer (danger=true)
    - Utiliser `useModeStore()` pour vérifier `isAppMode` et adapter les labels via `useAppVocabulary()`
    - En Mode App : labels traduits (app, démarrer, etc.), section Avancé garde vocabulaire technique
    - En Mode Infra : labels techniques (container, start, etc.)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Composant AppContextMenu.vue
**Objectif :** Créer le composant Vue réutilisable qui affiche le menu déroulant `[⋯ Plus]` avec les 3 sections canoniques, utilisable depuis la liste Apps, le dashboard et le détail App.
**Fichiers :**
- `frontend/src/components/ui/AppContextMenu.vue` — Créer — Nouveau composant (pattern: `ActionButtons.vue`). Template avec :
  - `<el-dropdown trigger="click">` contenant un bouton icône `⋯` (MoreFilled)
  - `<el-dropdown-menu>` avec les sections rendues dynamiquement
  - Chaque section a un titre (`<el-dropdown-item divided disabled>`) et ses items cliquables
  - Séparateur `divided` entre Outils et Avancé
  - Items `danger` en rouge (classe CSS)
  - Props : `containerId`, `containerName`, `containerStatus`, `domain?`, `labels?`, `size?` ('small' | 'default')
  - Emits : `(e: 'action', action: string, containerId: string)` pour chaque action du menu
  - Utilise le composable `useAppContextMenu` pour générer les sections
  - `data-testid="app-context-menu"` sur le dropdown, `data-testid="menu-item-{action}"` sur chaque item
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

### Tâche 4 : Export barrel et intégration dans l'écosystème UI
**Objectif :** Rendre le composant disponible via le barrel export et vérifier qu'il s'intègre correctement avec les composants existants.
**Fichiers :**
- `frontend/src/components/ui/index.ts` — Modifier — Ajouter `export { default as AppContextMenu } from './AppContextMenu.vue'` et `export type { AppContextMenuProps } from '@/types/context-menu'`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 3

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`

### Unitaires Frontend — Composable
- `frontend/tests/unit/composables/useAppContextMenu.spec.ts`
  - `retourne 3 sections (primary, tools, advanced)` — cas nominal : structure canonique
  - `section primary contient Ouvrir quand domain est fourni` — cas nominal
  - `section primary ne contient pas Ouvrir sans domain` — cas conditionnel
  - `section primary contient Start quand status est stopped` — cas nominal
  - `section primary contient Stop quand status est running` — cas nominal
  - `section tools contient Logs, Console, Config` — cas nominal
  - `section advanced contient Détails techniques et Supprimer` — cas nominal
  - `Supprimer est marqué danger=true` — vérification propriété
  - `en Mode App, les labels utilisent le vocabulaire non-technique` — vérification vocabulaire
  - `en Mode App, la section Avancé utilise le vocabulaire technique` — vérification fuite contrôlée
  - `en Mode Infra, les labels utilisent le vocabulaire technique` — vérification Mode Infra
  - `isMenuVisible retourne false si aucune action disponible` — cas limite
  - `getActionHandler retourne une fonction pour chaque action` — cas nominal

### Unitaires Frontend — Composant
- `frontend/tests/unit/components/AppContextMenu.spec.ts`
  - `affiche le bouton ⋯ Plus` — rendu initial
  - `au clic sur ⋯, ouvre le dropdown avec 3 sections` — interaction
  - `chaque section a son titre` — vérification structure
  - `les items cliquables émettent l'événement action avec le bon type et containerId` — interaction
  - `l'item Supprimer a la classe danger` — vérification styling
  - `un séparateur divise la section Outils et Avancé` — vérification structure
  - `les items désactivés ne sont pas cliquables` — cas conditionnel
  - `applique data-testid sur le dropdown et chaque item` — testabilité
  - `en Mode App, les labels sont traduits` — vérification vocabulaire
  - `en Mode Infra, les labels sont techniques` — vérification Mode Infra

### Commandes de validation
```bash
# Frontend
cd frontend && pnpm test -- tests/unit/composables/useAppContextMenu
cd frontend && pnpm test -- tests/unit/components/AppContextMenu
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-05-26

### Fichiers créés
- `frontend/src/types/context-menu.ts` — Types, interfaces et constantes du menu contextuel (3 sections, 9 actions, labels App/Infra)
- `frontend/src/composables/useAppContextMenu.ts` — Composable générant les sections dynamiquement selon le statut container et le mode UI
- `frontend/src/components/ui/AppContextMenu.vue` — Composant Vue réutilisable avec el-dropdown, 3 sections canoniques, séparateur, styling danger
- `frontend/tests/unit/composables/useAppContextMenu.spec.ts` — 19 tests couvrant structure, conditions d'affichage, vocabulaire App/Infra
- `frontend/tests/unit/components/AppContextMenu.spec.ts` — 14 tests couvrant rendu, structure, styling, événements, modes

### Fichiers modifiés
- `frontend/src/types/vocabulary.ts` — Ajout de 3 actions (restart, delete, details) à APP_ACTIONS
- `frontend/src/components/ui/index.ts` — Export barrel mis à jour avec AppContextMenu et types context-menu

### Décisions techniques
- Les labels du menu sont gérés par des constantes séparées (CONTEXT_MENU_ACTION_LABELS_APP / _INFRA) plutôt que par le composable useAppVocabulary, car le menu a son propre vocabulaire spécifique (actions contextuelles vs traduction de termes)
- Le composable est une fonction pure (pas de state local) qui utilise le modeStore en lecture seule
- Le composant utilise el-dropdown avec trigger="click" pour une meilleure UX sur mobile

### Tests ajoutés
- `useAppContextMenu.spec.ts` : 19 tests (structure canonique, conditions d'affichage, vocabulaire Mode App/Infra, utilitaires)
- `AppContextMenu.spec.ts` : 14 tests (rendu, structure 3 sections, styling danger, événements, modes, conditions)
- Total : 33 tests passants

### Validation
- Build : ✅ (pnpm build — exit 0)
- Lint : ✅ (0 errors, 140 warnings pré-existants)
- Tests : ✅ (33/33 passants)
