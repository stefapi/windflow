# STORY-027.1 : Cards statiques (Services, Volumes, Réseau, Santé) + Layout

**Statut :** DONE
**Story Parente :** STORY-027 — Frontend — Onglet Aperçu synthétique conforme maquette UI
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
Créer l'onglet "Aperçu" comme premier onglet de la vue ContainerDetail, avec un layout responsive de cards visuelles (Services, Volumes, Réseau, Santé) utilisant `el-card` avec headers colorés. Ces cards affichent les données statiques issues du inspect Docker, sans refresh automatique des métriques (traité dans STORY-027.2).

## Critères d'acceptation (AC)
- [x] AC 1 : Un nouvel onglet **Aperçu** est le premier onglet affiché par défaut (avant Infos/Logs)
- [x] AC 2 : Une card **Services** liste les containers de la même stack (même `com.docker.compose.project`) avec : nom, image, statut (badge coloré), port mapping. Si standalone, affiche uniquement le container courant.
- [x] AC 4 : Une card **Volumes** liste les volumes montés avec : nom du volume, chemin de montage, type, et bouton [📂] pour ouvrir le volume browser (placeholder)
- [x] AC 5 : Une card **Réseau** résume les networks attachés avec : nom du réseau, IP, gateway, type de driver
- [x] AC 6 : Si le container a un **health check**, une card **Santé** affiche le status (healthy/unhealthy/starting) et le failing streak
- [x] AC 7 : Les cards utilisent le composant `el-card` avec des headers colorés et un layout responsive (2 colonnes sur desktop, 1 colonne sur mobile)
- [x] AC 9 : Si le container est arrêté, les cards Santé affiche "Non disponible — container arrêté"

## Contexte technique

### Fichiers existants de référence
- `frontend/src/views/ContainerDetail.vue` — Vue parente avec les onglets, `activeTab = 'infos'` par défaut. Reçoit `containerDetail` du store.
- `frontend/src/components/ContainerStats.vue` — Pattern d'utilisation de `useContainerStats` et `ResourceBar`
- `frontend/src/components/ContainerInfoTab.vue` — Pattern de component onglet recevant `detail` en prop
- `frontend/src/components/compute/helpers.ts` — Fonctions `getContainerStatusType()`, `getContainerStatusLabel()` pour les badges de statut
- `frontend/src/services/api.ts` — `containersApi.list(all)` retourne `Container[]` avec labels (incluant `com.docker.compose.project`)
- `frontend/src/types/api.ts` — Types `ContainerDetail`, `Container`

### Patterns à respecter
- Component dédié par onglet (comme `ContainerInfoTab.vue`)
- Props pour les données (detail + containerId)
- Composition API + TypeScript strict
- Element Plus pour l'UI (`el-card`, `el-tag`, `el-table`, `el-empty`)
- Scoped CSS avec variables CSS du projet (`--color-*`)

### Données disponibles dans `containerDetail`
- `containerDetail.config?.labels` — pour détecter `com.docker.compose.project`
- `containerDetail.mounts` — volumes montés (Type, Source, Destination, Mode, Name)
- `containerDetail.network_settings.Networks` — networks (NetworkID, IPAddress, MacAddress, Gateway)
- `containerDetail.state.health` — health check (status, failing_streak)

## Dépendances
- Aucune (première sous-story)

## Tâches d'implémentation détaillées

### Tâche 1 : Créer ContainerOverviewTab.vue — Layout + Card Services
**Objectif :** Créer le composant avec la structure de base, le layout responsive 2 colonnes, et la card Services qui fetch les containers de la même stack.
**Fichiers :**
- `frontend/src/components/ContainerOverviewTab.vue` — **Créer** — Nouveau composant (pattern: `ContainerInfoTab.vue`). Script setup avec props `detail` (ContainerDetail), `containerId` (string) et `containerState` (string, ex: 'running', 'exited'). Template : grid CSS responsive 2 colonnes (`display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px` avec media query `@media (max-width: 768px)` pour 1 colonne). Card **Services** : fetch via `containersApi.list()` au mount, filtrage client-side par label `com.docker.compose.project` (extrait de `detail.config.labels`), affichage dans `el-table` avec colonnes : Nom, Image, Statut (badge via `getContainerStatusType/Label`), Ports (formatter : `IP:PublicPort→PrivatePort/Type` via le type `ContainerPort[]`). Si standalone (pas de label compose), afficher uniquement le container courant. Utiliser `el-card` avec header slot coloré (bleu). Imports : `containersApi` depuis `@/services/api`, `getContainerStatusType/Label` depuis `@/components/compute/helpers`, type `Container` depuis `@/types/api`. État réactif : `ref<Container[]>([])` pour les services, `ref<boolean>` pour loading, `computed<string|null>` pour `projectName`.
**Dépend de :** Aucune

### Tâche 2 : Implémenter les cards Volumes, Réseau et Santé
**Objectif :** Ajouter les 3 cards restantes qui lisent toutes leurs données des props `detail` (pas de fetch supplémentaire).
**Fichiers :**
- `frontend/src/components/ContainerOverviewTab.vue` — **Modifier** — Ajouter dans le template, dans le même grid layout :
  - Card **Volumes** (header vert) : itérer `detail.mounts`, afficher dans `el-table` colonnes Type (bind/volume avec `el-tag`), Source/Name, Destination, Mode, bouton 📂 `el-button` désactivé (volume browser pas encore implémenté). Si aucun mount, afficher `el-empty`.
  - Card **Réseau** (header violet) : itérer `Object.entries(detail.network_settings.Networks)`, afficher dans `el-descriptions` ou tableau : nom du réseau, IPAddress, Gateway, MacAddress. Si aucun network, afficher `el-empty`.
  - Card **Santé** (header orange) : condition `v-if="detail.state.health"` — afficher statut avec `el-tag` coloré (healthy=success, unhealthy=danger, starting=warning), failing streak. Si `containerState !== 'running'` (via prop), afficher message "Non disponible — container arrêté" à la place des infos de santé. Si pas de health check défini, ne pas afficher la card (`v-if`).
**Dépend de :** Tâche 1

### Tâche 3 : Intégrer l'onglet Aperçu dans ContainerDetail.vue
**Objectif :** Ajouter l'onglet "Aperçu" en première position dans la vue ContainerDetail et le rendre l'onglet par défaut.
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — **Modifier** — Importer `ContainerOverviewTab`, ajouter `<el-tab-pane label="Aperçu" name="apercu">` avant l'onglet Infos, changer `activeTab` par défaut de `'infos'` à `'apercu'`, passer les props `:detail="containerDetail"` et `:container-id="containerId"` et `:container-state="containerState"`.
**Dépend de :** Tâche 2

### Tâche 4 : Écrire les tests unitaires
**Objectif :** Tester le rendu du composant ContainerOverviewTab et l'intégration dans ContainerDetail.
**Fichiers :**
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — **Créer** — Tests (pattern: `ContainerInfoTab.spec.ts`) : montage correct avec mock `detail` complet, card Services affiche containers de la même stack (mock `containersApi.list`), card Services standalone affiche uniquement le container courant, card Volumes affiche les mounts avec type/source/destination, card Réseau affiche networks avec IP/gateway, card Santé affiche statut healthy/unhealthy/starting, card Santé affiche "Non disponible" quand arrêté, layout responsive vérifie classes CSS.
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — **Modifier** — Update le test `activeTab` par défaut de 'infos' à 'apercu'.
**Dépend de :** Tâche 3

## Tests à écrire

### Frontend
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — Tests unitaires :
  - Montage du composant avec des données complètes
  - Card Services : affiche les containers de la même stack, filtre correctement par label
  - Card Services : container standalone affiche uniquement le container courant
  - Card Volumes : affiche les mounts avec bonne info (type, source, destination)
  - Card Réseau : affiche les networks avec IP, gateway
  - Card Santé : affiche le statut health quand défini (healthy/unhealthy/starting)
  - Card Santé : affiche "Non disponible" quand container arrêté
  - Layout responsive : vérifie la présence des classes CSS
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Update test activeTab par défaut à 'apercu'

### Commandes de validation
```bash
cd frontend && pnpm test:unit --run
cd frontend && pnpm type-check
```

## État d'avancement technique
- [x] Tâche 1 : Créer ContainerOverviewTab.vue — Layout + Card Services
- [x] Tâche 2 : Implémenter cards Volumes, Réseau et Santé
- [x] Tâche 3 : Intégrer l'onglet Aperçu dans ContainerDetail.vue
- [x] Tâche 4 : Écrire les tests unitaires

## Notes d'implémentation

### Fichiers créés
- `frontend/src/components/ContainerOverviewTab.vue` — Nouveau composant onglet Aperçu avec layout responsive 2 colonnes, 4 cards (Services, Volumes, Réseau, Santé)

### Fichiers modifiés
- `frontend/src/views/ContainerDetail.vue` — Ajout onglet Aperçu en première position, onglet par défaut changé de 'infos' à 'apercu'
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Mise à jour test activeTab par défaut à 'apercu'

### Fichiers créés (tests)
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — 19 tests unitaires (19/19 pass)

### Décisions techniques
- Card Santé conditionnellement rendue (v-if sur health info) — pas de placeholder quand pas de health check
- Card Santé affiche "Non disponible — container arrêté" quand containerState !== 'running'
- Card Services fetch `containersApi.list(true)` au mount avec filtrage client-side par label compose
- Types volumes/networks castés via `as any` pour gérer les incohérences de casse (Networks vs networks) entre backend et types TS — nettoyage prévu dans un refactoring futur

### Tests
- 19 tests unitaires passants : rendu, cards, computed properties, edge cases (null detail, API error)
- Test ContainerDetail activeTab par défaut mis à jour
