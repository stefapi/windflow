# 06 — Frontend Vue 3 (source de vérité)

> Prime sur toute autre mention du frontend dans ce corpus, sauf `40-security.md`.

## 1. Principes

- Le frontend affiche et saisit ; la logique métier vit dans le backend (API-first, `20`). Seuls sont admis : formatage, tri et filtre de données déjà chargées, validation de saisie (aide), gestion d'état d'interface.
- Tout accès aux données passe par `frontend/src/services/` (Axios) — jamais d'appel HTTP direct dans une vue, un composant ou un store. Le client API est régénéré par `make generate-api` quand le contrat change.
- Interface en français ; composants Element Plus pour tout composant UI générique ; pas de duplication maison d'un composant existant (`ElTable`, `ElDialog`, `ElMessage`/`ElNotification`, `ElMessageBox`, `ElSelect`, `ElDatePicker`, `ElUpload`, `ElDropdown`, `ElPagination`).

## 2. Vue et TypeScript

- Vue 3, `<script setup lang="ts">` pour tout composant. **Interdit** : Options API, mixins, `defineComponent` avec objet d'options, JSX.
- `tsconfig` : `strict` + `noUnusedLocals`, `noUnusedParameters`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `noPropertyAccessFromIndexSignature`.
- **Interdit** : `any` (explicite ou implicite), `@ts-ignore`, `@ts-nocheck`, double conversion `as unknown as T`, assertion non nulle `!` hors tests, `// eslint-disable` sans justification ni référence d'élément de backlog sur la même ligne.
- Props : `defineProps<Props>()` avec interface nommée ; événements : `defineEmits<{…}>()` typé.
- Attention aux auto-imports unplugin (auto-import, composants) : un symbole utilisé sans import n'est pas forcément une erreur, et un symbole non importé n'est pas forcément utilisé.

## 3. État

| Donnée | Outil | Règle |
| --- | --- | --- |
| État serveur (listes, entités) | stores Pinia par domaine + services | Synchronisé avec l'API ; jamais de calcul métier local |
| Session/auth | store `auth` | Token d'accès **en mémoire** — jamais `localStorage`/`sessionStorage` (`40`) |
| État local d'un écran | `ref`, `reactive`, `computed` | Dans le composant |
| Logique réutilisable | composables `useXxx` (`src/composables/`) | Type de retour explicite ; ressources libérées à la destruction |

- Un store Pinia = un domaine (état + actions + getters). Gestion centralisée des erreurs via store + notifications Element Plus.
- **Interdit** : état global maison redondant avec un store ; cache HTTP parallèle au cache unifié backend.

## 4. Composants et style

- Fichiers kebab-case pour les SFC (le composant s'appelle `ContainerDetail`), composants en PascalCase au moins deux mots, un composant par fichier.
- Composant au-delà de ~200 lignes ou 3 responsabilités : découper (`55` §3).
- Styling : UnoCSS (pas de Tailwind, pas de CSS ad hoc non justifié). Stylelint vérifie le CSS.
- États d'écran : distinguer chargement, vide, erreur et données — jamais de tableau vide affiché pour une erreur de chargement.
- Notifications via Element Plus (`ElMessage`, `ElNotification`) ; confirmations destructives via `ElMessageBox`. **Interdit** : `alert()`, `confirm()`, `prompt()` natifs, `console.log` dans le code livré.

## 5. Bibliothèques spécialisées

| Besoin | Bibliothèque | Règle |
| --- | --- | --- |
| Terminal interactif | @xterm/xterm (+ addon-fit, addon-web-links) | Intégré au canal WebSocket terminal (`21`) |
| Éditeur de composition / graphe | @vue-flow/core (+ background, controls, minimap) | Synchronisation avec le YAML compose (round-trip) |
| Formulaires dynamiques pilotés par schéma | @jsonforms/* | Rendus `vanilla` habillés Element Plus/UnoCSS |
| Graphiques | echarts / vue-echarts | Import modulaire ; aucune autre bibliothèque de graphiques |
| Dates | dayjs | — |
| Validation | @vuelidate/core | Aide à la saisie ; la validation serveur fait foi |

## 6. Tests

- Fichiers `*.spec.ts` dans `frontend/tests/unit/{views,components,composables}/`, intégration dans `tests/integration/`, E2E Playwright dans `tests/e2e/` (workflows critiques uniquement).
- Cas obligatoires par composant/vue : rendu initial (vide, chargement, données), interactions, états d'erreur, accès conditionnel selon rôle (`35` §7).

## 7. Interdits récapitulatif

`any` non justifié ; appel Axios hors `services/` ; logique métier dans un composant (utiliser composable/store/service) ; duplication d'un composant Element Plus ; `localStorage`/`sessionStorage` pour un token ou un secret ; modification manuelle du client API généré (régénérer via `make generate-api`).
