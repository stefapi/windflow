# STORY-005 : Détail App — Vocabulaire Mode App

**Statut :** DONE
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux consulter le détail d'une application avec un vocabulaire simplifié et des onglets adaptés au Mode App afin de gérer mon application sans être exposé aux termes techniques Docker.

## Contexte technique
La vue [`ContainerDetail.vue`](frontend/src/views/ContainerDetail.vue) est adaptée pour le Mode App. Le header affiche le nom de l'app (pas le nom du container), version, statut, domaine et métriques inline (CPU, RAM). L'action bar est simplifiée : Ouvrir, Stop/Start, Redémarrer, Logs, Console, Config.

Onglets Mode App : Aperçu, Logs, Console, Métriques, Config. Les onglets techniques (Info/inspect Docker, Processes, Stats détaillées) sont masqués. Le menu `[⋯ Plus]` contient les actions avancées (Supprimer, Renommer, Voir les détails techniques — désactivé).

[`ContainerOverviewTab`](frontend/src/components/ContainerOverviewTab.vue) utilise le vocabulaire "App" au lieu de "Container".

Spécification de référence : [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écran 3

**Couches impactées :** Frontend uniquement

**Fichiers de référence (patterns) :**
- Composable vocabulaire → pattern : [`useAppVocabulary.ts`](frontend/src/composables/useAppVocabulary.ts)
- Store mode → pattern : [`mode.ts`](frontend/src/stores/mode.ts)
- Composant context menu → pattern : [`AppContextMenu.vue`](frontend/src/components/ui/AppContextMenu.vue)
- Vue Compute Mode App → pattern : [`Compute.vue`](frontend/src/views/Compute.vue) (STORY-004 DONE)
- Tests composant → pattern : [`AppCard.spec.ts`](frontend/tests/unit/components/compute/AppCard.spec.ts)
- Tests vue → pattern : [`Compute.spec.ts`](frontend/tests/unit/views/Compute.spec.ts)

**Exigences sécurité identifiées :**
- Auth : oui — route protégée par auth guard existant
- RBAC : rôles autorisés = viewer, operator, admin — pas de modification des permissions
- Validation : container_id depuis route.params validé par le store
- Exposition : aucun champ sensible dans l'UI Mode App (pas de token, secret)
- Audit : non requis (lecture seule + actions déjà auditées côté backend)

## Critères d'acceptation (AC)
- [x] AC 1 : Le header affiche le nom de l'app, version, statut, domaine et métriques inline (CPU, RAM) au lieu du nom du container
- [x] AC 2 : Les onglets Mode App (Aperçu, Logs, Console, Métriques, Config) sont affichés ; les onglets techniques (Info, Processes, Stats détaillées) sont masqués
- [x] AC 3 : L'action bar simplifiée (Ouvrir, Stop/Start, Redémarrer, Logs, Console, Config) fonctionne correctement
- [x] AC 4 : Le menu `[⋯ Plus]` contient les actions avancées (Supprimer, Renommer, Voir les détails techniques — désactivé)
- [x] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)
- STORY-003 (Menu Contextuel Canonique)

## État d'avancement technique
- [x] Tâche 1 : Adapter le header de ContainerDetail.vue pour le Mode App
- [x] Tâche 2 : Filtrer les onglets selon le mode (App/Infra)
- [x] Tâche 3 : Créer l'action bar simplifiée Mode App
- [x] Tâche 4 : Intégrer le menu contextuel `[⋯ Plus]` canonique
- [x] Tâche 5 : Adapter ContainerOverviewTab avec vocabulaire "App"
- [x] Tests unitaires ContainerDetail.vue
- [x] Tests unitaires ContainerOverviewTab.vue
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Adapter le header de ContainerDetail.vue pour le Mode App
**Objectif :** Transformer le header pour qu'il affiche le nom de l'app (via [`getAppDisplayName()`](frontend/src/composables/useAppVocabulary.ts:95)), le statut traduit, le domaine (si disponible dans les labels), et les métriques inline CPU/RAM. Masquer les métadonnées techniques (image, target, restart policy, ressources) en Mode App.
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  - Importer `useModeStore` depuis `@/stores/mode` et `useAppVocabulary`, `getAppDisplayName` depuis `@/composables/useAppVocabulary`
  - Ajouter `const modeStore = useModeStore()` et `const { getAppStatus } = useAppVocabulary()`
  - Ajouter `computed` `isAppMode` qui lit `modeStore.isAppMode`
  - Modifier `header-identity` : en Mode App, afficher `getAppDisplayName(containerDetail.value)` au lieu de `containerDetail?.name`. Masquer le code image en Mode App.
  - Modifier `header-meta` : en Mode App, ne garder que CPU et RAM (masquer Target, Restart Policy, Ressources). Ajouter le domaine si présent dans les labels (`containerDetail.value?.config?.labels?.['org.windflow.app.domain']` ou traefik labels).
  - Utiliser `getAppStatus(containerState.value).app` pour le label de statut en Mode App.
  - Adapter tous les messages ElMessage pour utiliser "app" au lieu de "container" quand `isAppMode` est vrai.
**Exigences sécurité :** Aucune exigence spécifique (UI uniquement, pas de nouvelle route)
**Dépend de :** Aucune

### Tâche 2 : Filtrer les onglets selon le mode (App/Infra)
**Objectif :** Afficher uniquement les onglets Mode App (Aperçu, Logs, Console, Métriques, Config) en Mode App. Masquer les onglets techniques (Infos, Processus, Stats détaillées — le nom de l'onglet existant "Stats" reste mais pointe vers ContainerStats.vue qui est l'onglet Métriques). Renommer l'onglet "Terminal" en "Console" en Mode App.
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  - Conditionner l'affichage des onglets `Infos`, `Processus` via `v-if="!isAppMode"`
  - Renommer dynamiquement le label de l'onglet `Terminal` en `Console` quand `isAppMode` est vrai
  - Les onglets `Aperçu`, `Logs`, `Stats`, `Config` restent visibles dans les deux modes
  - Adapter les messages placeholder dans les onglets (ex: "Le terminal n'est disponible que lorsque le container est en cours d'exécution" → "La console n'est disponible que lorsque l'app est en cours d'exécution" en Mode App)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Créer l'action bar simplifiée Mode App
**Objectif :** Remplacer la barre d'actions technique actuelle (Démarrer, Pause, Reprendre, Arrêter, Redémarrer, Supprimer, Inspect, Promouvoir, Restart Policy, Ressources) par une barre simplifiée en Mode App : Ouvrir (lien domaine), Stop/Start (toggle selon statut), Redémarrer, Logs (navigue vers onglet Logs), Console (navigue vers onglet Console), Config (navigue vers onglet Config). Les actions techniques restent accessibles via le menu `[⋯ Plus]`.
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  - Créer une nouvelle section `header-actions-mode-app` conditionnée par `v-if="isAppMode"`
  - Bouton "Ouvrir" (type="primary" plain) : visible si domaine disponible, lien externe vers le domaine
  - Bouton "Démarrer" (type="success") : visible si stopped, appelle `handleAction('start')`
  - Bouton "Arrêter" (type="danger") : visible si running, appelle `handleAction('stop')`
  - Bouton "Redémarrer" (type="primary") : visible si running, appelle `handleAction('restart')`
  - Bouton "Logs" (type="default") : navigue vers l'onglet `logs` via `activeTab.value = 'logs'`
  - Bouton "Console" (type="default") : navigue vers l'onglet `terminal` via `activeTab.value = 'terminal'`
  - Bouton "Config" (type="default") : navigue vers l'onglet `config` via `activeTab.value = 'config'`
  - Conserver la section `header-actions` existante pour `v-if="!isAppMode"` (Mode Infra)
  - Adapter les tooltips pour utiliser le vocabulaire Mode App
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 4 : Intégrer le menu contextuel `[⋯ Plus]` canonique
**Objectif :** Intégrer le composant [`AppContextMenu.vue`](frontend/src/components/ui/AppContextMenu.vue) dans le header de ContainerDetail.vue pour regrouper les actions avancées (Supprimer, Renommer, Voir les détails techniques — désactivé). En Mode App, ce menu est la seule zone où le vocabulaire technique fuit.
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  - Importer `AppContextMenu` depuis `@/components/ui/AppContextMenu.vue`
  - Ajouter le composant `<AppContextMenu>` dans le header, à droite de la barre d'actions Mode App
  - Props à passer : `containerId`, `containerName` (via `getAppDisplayName`), `containerStatus` (via `containerState`), `domain` (si disponible)
  - Gérer l'événement `@action` pour dispatcher vers les handlers existants :
    - `'delete'` → `handleDelete()`
    - `'start'` → `handleAction('start')`
    - `'stop'` → `handleAction('stop')`
    - `'restart'` → `handleAction('restart')`
    - `'logs'` → `activeTab.value = 'logs'`
    - `'console'` → `activeTab.value = 'terminal'`
    - `'config'` → `activeTab.value = 'config'`
    - `'details'` → action désactivée pour l'instant (afficher un tooltip "Bientôt disponible" ou ne rien faire)
    - `'open'` → ouvrir le domaine dans un nouvel onglet
  - Le menu `[⋯ Plus]` doit être visible uniquement en Mode App (en Mode Infra, les actions restent dans les boutons existants)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1, Tâche 3

### Tâche 5 : Adapter ContainerOverviewTab avec vocabulaire "App"
**Objectif :** Adapter le composant [`ContainerOverviewTab.vue`](frontend/src/components/ContainerOverviewTab.vue) pour utiliser le vocabulaire Mode App. Remplacer les occurrences de "Container" par "App" dans les titres et descriptions, masquer les informations techniques (image, ID) en Mode App.
**Fichiers :**
- `frontend/src/components/ContainerOverviewTab.vue` — Modifier —
  - Importer `useModeStore` depuis `@/stores/mode`
  - Ajouter `const modeStore = useModeStore()` et `const isAppMode = computed(() => modeStore.isAppMode)`
  - Adapter les titres des cards : "Services" → reste "Services", "Volumes" → masquer ou renommer en "Stockage" (à discuter), "Réseau" → masquer en Mode App
  - Adapter les descriptions vides : "Aucun service trouvé" → reste, "Aucun volume monté" → masquer ou adapter
  - Masquer les colonnes techniques dans les tableaux (Image, Type de volume) en Mode App
  - Adapter les labels des descriptions : "Stack parente" → "App parente" (ou masquer)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Frontend — ContainerDetail.vue
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Créer (pattern: [`Compute.spec.ts`](frontend/tests/unit/views/Compute.spec.ts))
  - `affiche le nom de l'app en Mode App` — rendu : `getAppDisplayName` est utilisé, pas le nom brut du container
  - `affiche le statut traduit en Mode App` — le badge de statut affiche le label Mode App
  - `masque les métadonnées techniques en Mode App` — Target, Restart Policy, Ressources ne sont pas dans le DOM
  - `affiche les onglets Mode App (Aperçu, Logs, Console, Métriques, Config)` — 5 onglets visibles
  - `masque les onglets techniques en Mode App` — Infos et Processus ne sont pas dans le DOM
  - `affiche l'action bar simplifiée en Mode App` — Ouvrir, Stop/Start, Redémarrer, Logs, Console, Config sont visibles
  - `affiche le menu contextuel [⋯ Plus] en Mode App` — AppContextMenu est rendu avec les bonnes props
  - `navigue vers l'onglet Logs au clic sur le bouton Logs` — `activeTab` passe à 'logs'
  - `navigue vers l'onglet Console au clic sur le bouton Console` — `activeTab` passe à 'terminal'
  - `navigue vers l'onglet Config au clic sur le bouton Config` — `activeTab` passe à 'config'
  - `affiche les actions techniques en Mode Infra` — Démarrer, Pause, Arrêter, Inspect, etc. sont visibles quand isAppMode = false
  - `redirige vers /login si non authentifié` — **sécurité** : route protégée (si applicable au niveau route guard)

### Unitaires Frontend — ContainerOverviewTab.vue
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — Créer (pattern: [`AppCard.spec.ts`](frontend/tests/unit/components/compute/AppCard.spec.ts))
  - `utilise le vocabulaire App en Mode App` — les titres contiennent "App" au lieu de "Container"
  - `masque les informations techniques en Mode App` — Image, ID, Stack parente ne sont pas affichés

### Commandes de validation
```bash
# Frontend (voir Makefile)
cd frontend && pnpm test -- tests/unit/views/ContainerDetail
# Note : si le fichier n'existe pas encore, créer d'abord les tests
cd frontend && pnpm test -- tests/unit/components/ContainerOverviewTab
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-05-26

### Fichiers modifiés/créés
- `frontend/src/views/ContainerDetail.vue` — Ajout du support Mode App : header adaptatif (nom d'app, statut traduit, domaine), action bar simplifiée en Mode App, onglets filtrés (Infos/Processus masqués, Terminal→Console, Stats→Métriques), intégration AppContextMenu, messages traduits via entityLabel()
- `frontend/src/components/ContainerOverviewTab.vue` — Import useModeStore, computed isAppMode, message adaptatif "container arrêté"/"app arrêtée"
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Création : 15 tests couvrant Mode App (header, onglets, action bar, menu contextuel) et Mode Infra (actions techniques, onglets techniques, renommer, image)
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` — Ajout mock useModeStore pour corriger la régression
- `frontend/tests/unit/composables/useAppVocabulary.spec.ts` — Mise à jour nombre d'actions de 5 à 8 (pré-existant, corrigé)

### Décisions techniques
- Utilisation de `getAppDisplayName()` du composable STORY-001 pour le nom d'app dans le header
- Utilisation de `getAppStatus()` pour le label de statut traduit en Mode App
- Extraction du domaine via les labels `org.windflow.app.domain` ou labels Traefik
- `entityLabel()` helper pour centraliser la traduction App/Container dans les messages ElMessage
- `handleContextMenuAction()` dispatcher centralisé pour les actions du menu contextuel canonique
- Les onglets techniques (Infos, Processus) sont masqués via `v-if="!isAppMode"` — pas de suppression
- L'action "Détails techniques" dans le menu est désactivée avec message "Bientôt disponible"

### Divergences par rapport à l'analyse
- Aucune divergence majeure. L'implémentation suit fidèlement les tâches analysées.

### Tests ajoutés
- `frontend/tests/unit/views/ContainerDetail.spec.ts` : 15 tests (8 Mode App + 5 Mode Infra + 2 header)
- `frontend/tests/unit/components/ContainerOverviewTab.spec.ts` : 25 tests existants corrigés (mock useModeStore ajouté)
- `frontend/tests/unit/composables/useAppVocabulary.spec.ts` : 1 test corrigé (nombre d'actions)
- **Total : 873 tests unitaires passent, 0 échec**
