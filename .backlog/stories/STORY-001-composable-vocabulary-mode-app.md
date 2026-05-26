# STORY-001 : Composable de Vocabulaire Mode App

**Statut :** DONE
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant que Développeur, je veux créer un composable `useAppVocabulary` centralisant la traduction des termes techniques en termes Mode App afin de garantir la cohérence du vocabulaire dans toute l'interface sans duplication.

## Contexte technique

Le Mode App est une couche de présentation frontend qui masque le vocabulaire technique (container, compose, stack, volume, network, image) derrière des termes grand public. Ce composable est la fondation utilisée par tous les composants de l'epic.

**Mapping de termes :**
| Terme technique | Terme Mode App | Visibilité |
|-----------------|----------------|------------|
| container | app | Remplacé |
| stack | app | Remplacé |
| target | serveur | Remplacé |
| compose | (masqué) | Non affiché |
| image | (masqué) | Non affiché |
| volume | (masqué) | Non affiché |
| network | (masqué) | Non affiché |
| deployment | (masqué) | Non affiché |

Le composable expose les fonctions `getAppStatus()`, `getAppActions()`, `getAppDisplayName()` et le mapping centralisé des termes.

Spécification de référence : [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md)

**Couches impactées :** Frontend uniquement (composable + types + tests)

**Fichiers de référence (patterns) :**
- Composable → pattern : [`useSecretMasker.ts`](frontend/src/composables/useSecretMasker.ts) (fonctions pures exportées + composable)
- Types → pattern : [`frontend/src/types/api.ts`](frontend/src/types/api.ts)
- Tests composable → pattern : [`frontend/tests/unit/stores/compute.spec.ts`](frontend/tests/unit/stores/compute.spec.ts) (structure describe/it vitest)

**Exigences sécurité identifiées :**
- Auth : non — composable pur, aucun appel API
- RBAC : non applicable
- Validation : aucune donnée utilisateur entrante
- Exposition : aucune donnée sensible
- Audit : non requis

## Critères d'acceptation (AC)
- [x] AC 1 : Le composable `useAppVocabulary` expose les fonctions `getAppStatus()`, `getAppActions()`, `getAppDisplayName()` et le mapping de termes techniques → Mode App
- [x] AC 2 : Le mapping container→app, stack→app, target→serveur est centralisé et les termes masqués (compose, image, volume, network, deployment) ne sont jamais affichés en Mode App
- [x] AC 3 : Le composable est utilisable par tout composant Vue via import standard et facilitera le futur Mode Infra (il suffira de ne pas appliquer le vocabulaire)
- [x] AC 4 : Build, lint et tests unitaires passent

## Dépendances
- Aucune (story fondationnelle)

## État d'avancement technique
- [x] Tâche 1 : Créer le fichier types `vocabulary.ts`
- [x] Tâche 2 : Créer le composable `useAppVocabulary.ts`
- [x] Tâche 3 : Créer les tests unitaires `useAppVocabulary.spec.ts`
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Créer le fichier types `vocabulary.ts`
**Objectif :** Définir les types TypeScript pour le mapping de vocabulaire et les statuts/actions Mode App, centralisés dans un fichier dédié.
**Fichiers :**
- `frontend/src/types/vocabulary.ts` — Créer — Nouveau fichier de types (pattern: [`api.ts`](frontend/src/types/api.ts)). Définir :
  - `TechnicalTerm` : type union des termes techniques (`'container' | 'stack' | 'target' | 'compose' | 'image' | 'volume' | 'network' | 'deployment'`)
  - `AppVocabularyTerm` : interface `{ technical: TechnicalTerm; app: string; visible: boolean }`
  - `AppStatusMapping` : interface `{ technical: string; app: string; color: string }`
  - `AppActionMapping` : interface `{ technical: string; app: string; icon: string }`
  - `HIDDEN_TERMS` : `const TechnicalTerm[]` — liste des termes masqués en Mode App
  - `VOCABULARY_MAP` : `Record<TechnicalTerm, AppVocabularyTerm>` — mapping complet
  - `APP_STATUS_MAP` : `AppStatusMapping[]` — mapping des statuts techniques → Mode App (running→En cours, stopped→Arrêté, paused→En pause, restarting→Redémarrage, created→Créé, exited→Terminé, dead→Erreur)
  - `APP_ACTIONS` : `AppActionMapping[]` — actions canoniques Mode App (Ouvrir, Start/Stop, Redémarrer, Logs, Console, Config)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Créer le composable `useAppVocabulary.ts`
**Objectif :** Créer le composable Vue 3 qui expose les fonctions de traduction du vocabulaire technique vers le Mode App, utilisable par tout composant via import standard.
**Fichiers :**
- `frontend/src/composables/useAppVocabulary.ts` — Créer — Nouveau composable (pattern: [`useSecretMasker.ts`](frontend/src/composables/useSecretMasker.ts)). Exporter :
  - `translateTerm(technicalTerm: TechnicalTerm): string` — fonction pure : retourne le terme Mode App si visible, chaîne vide si masqué
  - `translateLabel(label: string): string` — fonction pure : remplace toutes les occurrences de termes techniques dans un label par leur équivalent Mode App (ex: "Container Status" → "Statut de l'app")
  - `getAppStatus(technicalStatus: string): AppStatusMapping` — fonction pure : retourne le mapping de statut Mode App correspondant (label + couleur), fallback sur le statut technique si non trouvé
  - `getAppActions(): AppActionMapping[]` — fonction pure : retourne la liste des actions canoniques Mode App
  - `getAppDisplayName(container: { name?: string; labels?: Record<string, string> }): string` — fonction pure : retourne le nom d'affichage Mode App (priorité : label `com.docker.compose.service` ou `org.windflow.app.name`, sinon nom du container nettoyé des préfixes techniques)
  - `isHiddenTerm(term: TechnicalTerm): boolean` — fonction pure : vérifie si un terme est masqué en Mode App
  - `useAppVocabulary()` — composable : retourne les fonctions ci-dessus enveloppées (identiques, pour usage dans `<script setup>`)
  - Importer les types et constantes depuis `@/types/vocabulary`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Créer les tests unitaires `useAppVocabulary.spec.ts`
**Objectif :** Couvrir toutes les fonctions du composable avec des tests unitaires Vitest : cas nominaux, cas limites, mapping complet.
**Fichiers :**
- `frontend/tests/unit/composables/useAppVocabulary.spec.ts` — Créer — Nouveau fichier de tests (pattern: [`compute.spec.ts`](frontend/tests/unit/stores/compute.spec.ts)). Structure :
  - `describe('useAppVocabulary')` avec `import { useAppVocabulary, translateTerm, translateLabel, getAppStatus, getAppActions, getAppDisplayName, isHiddenTerm } from '@/composables/useAppVocabulary'`
  - `describe('translateTerm')` :
    - `it('translates container to app')` — cas nominal
    - `it('translates stack to app')` — cas nominal
    - `it('translates target to serveur')` — cas nominal
    - `it('returns empty string for hidden terms (compose, image, volume, network, deployment)')` — termes masqués
    - `it('returns empty string for unknown term')` — cas limite
  - `describe('translateLabel')` :
    - `it('replaces technical terms in a label')` — "Container Status" → "Statut de l'app"
    - `it('replaces multiple occurrences')` — "Container network" → "App "
    - `it('returns label unchanged if no technical terms')` — cas nominal sans remplacement
  - `describe('getAppStatus')` :
    - `it('maps running to En cours with success color')` — cas nominal
    - `it('maps stopped to Arrêté with danger color')` — cas nominal
    - `it('maps paused to En pause with warning color')` — cas nominal
    - `it('returns technical status as fallback for unknown status')` — cas limite
  - `describe('getAppActions')` :
    - `it('returns the list of canonical App actions')` — vérifie la présence de Ouvrir, Start/Stop, Redémarrer, Logs, Console, Config
  - `describe('getAppDisplayName')` :
    - `it('returns compose service label when available')` — priorité label
    - `it('returns windflow app name label when available')` — priorité label
    - `it('returns cleaned container name as fallback')` — fallback nom
    - `it('returns unknown when no name available')` — cas limite
  - `describe('isHiddenTerm')` :
    - `it('returns true for compose, image, volume, network, deployment')` — termes masqués
    - `it('returns false for container, stack, target')` — termes visibles
  - `describe('useAppVocabulary composable')` :
    - `it('exposes all translation functions')` — vérifie que le composable retourne toutes les fonctions
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Frontend
- `frontend/tests/unit/composables/useAppVocabulary.spec.ts`
  - `translateTerm` — 5 tests (3 nominaux, 1 masqués, 1 limite)
  - `translateLabel` — 3 tests (1 remplacement simple, 1 remplacements multiples, 1 sans remplacement)
  - `getAppStatus` — 4 tests (3 nominaux, 1 fallback)
  - `getAppActions` — 1 test (présence des 6 actions canoniques)
  - `getAppDisplayName` — 4 tests (2 priorité label, 1 fallback nom, 1 cas limite)
  - `isHiddenTerm` — 2 tests (1 masqués, 1 visibles)
  - `useAppVocabulary composable` — 1 test (exposition des fonctions)
  - **Total : 20 tests**

### Commandes de validation
```bash
# Frontend
cd frontend && pnpm test -- tests/unit/composables/useAppVocabulary
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-05-26

### Fichiers modifiés/créés
- `frontend/src/types/vocabulary.ts` : Création — Types TypeScript (`TechnicalTerm`, `AppVocabularyTerm`, `AppStatusMapping`, `AppActionMapping`) + constantes (`VOCABULARY_MAP`, `APP_STATUS_MAP`, `APP_ACTIONS`, `HIDDEN_TERMS`)
- `frontend/src/composables/useAppVocabulary.ts` : Création — Composable avec 6 fonctions pures exportées (`translateTerm`, `translateLabel`, `getAppStatus`, `getAppActions`, `getAppDisplayName`, `isHiddenTerm`) + composable `useAppVocabulary()`
- `frontend/tests/unit/composables/useAppVocabulary.spec.ts` : Création — 23 tests unitaires couvrant toutes les fonctions

### Décisions techniques
- Fonctions pures exportées en plus du composable : permet l'import direct sans instanciation, utile pour les utilitaires et futurs stores
- `translateLabel` préserve la casse du terme original (Container → App, container → app)
- `getAppDisplayName` utilise 3 niveaux de priorité : label compose > label windflow > nom nettoyé
- Types centralisés dans `types/vocabulary.ts` (pas dans le composable) pour réutilisation

### Divergences par rapport à l'analyse
- Aucune divergence

### Tests ajoutés
- `frontend/tests/unit/composables/useAppVocabulary.spec.ts` : 23 tests (23 passent)
  - translateTerm : 5 tests
  - translateLabel : 3 tests
  - getAppStatus : 4 tests
  - getAppActions : 1 test
  - getAppDisplayName : 6 tests
  - isHiddenTerm : 2 tests
  - useAppVocabulary composable : 2 tests

### Validation
- `pnpm test` : ✅ 23/23 tests passent
- `pnpm build` : ✅ Build réussi (vue-tsc + vite build)
- `pnpm lint` : ✅ 0 errors (130 warnings préexistants)
