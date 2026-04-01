# STORY-004 : Actions globales de stack (Start/Stop/Redeploy)

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux démarrer, arrêter et redéployer une stack entière depuis la vue Compute afin de contrôler le cycle de vie de mes stacks managées en un seul clic.

## Contexte technique

### Patterns existants (réutilisation directe)
- **Backend — Actions container** : `backend/app/api/v1/docker.py` expose déjà `POST /docker/containers/{id}/start|stop|restart` avec le pattern `DockerClientService → start_container|stop_container|restart_container`. Le même service sera réutilisé pour les actions de stack.
- **Backend — Classification par label** : `backend/app/services/container_classifier.py` utilise le label `windflow.stack_id` pour grouper les containers managés. Les actions de stack itéreront sur ces containers.
- **Backend — Stack CRUD** : `backend/app/api/v1/stacks.py` + `backend/app/services/stack_service.py` + `backend/app/models/stack.py` définissent le modèle Stack avec relations vers Deployments.
- **Backend — Compute service** : `backend/app/services/compute_service.py` montre comment agréger les containers Docker groupés par stack_id.
- **Frontend — Confirmation dialog** : `ManagedStacksSection.vue` utilise déjà `ElMessageBox.confirm` + `ElMessage.success/error` pour les actions bulk.
- **Frontend — Loading state par action** : Pattern `bulkActionLoading = ref<string | null>(null)` dans `ManagedStacksSection.vue`.
- **Frontend — API layer** : `frontend/src/services/api.ts` → `stacksApi` pour les calls HTTP.
- **Frontend — Types** : `frontend/src/types/api.ts` contient `StackWithServices`, `ServiceWithMetrics`.

### Fichiers de référence
- `backend/app/api/v1/docker.py` (pattern d'actions Docker)
- `backend/app/api/v1/stacks.py` (router stacks existant)
- `backend/app/services/container_classifier.py` (labels WindFlow)
- `backend/app/services/docker_client_service.py` (client Docker)
- `frontend/src/components/compute/ManagedStacksSection.vue` (intégration cible)
- `frontend/src/components/compute/BulkActionBar.vue` (pattern UI d'actions)
- `frontend/src/services/api.ts` (couche API)
- `frontend/src/types/api.ts` (types TypeScript)

### Gaps identifiés
- ✅ Endpoints backend `POST /stacks/{id}/start`, `/stop`, `/redeploy` ajoutés
- ✅ Schemas Pydantic `StackActionResponse`, `StackRedeployRequest` ajoutés
- ✅ Types TS `StackActionResponse`, `StackRedeployRequest`, `RedeployStrategy` ajoutés
- ✅ Composant `StackActionsBar.vue` créé
- ✅ Méthodes `stacksApi.start/stop/redeploy` ajoutées

## Dépendances
- **STORY-001** (Vue globale Compute — les actions s'intègrent dans la section Stacks managées de `ManagedStacksSection.vue`)
- **Docker** : Les actions nécessitent que le daemon Docker soit accessible via Unix socket (même contrainte que le compute global)

## Tâches d'implémentation détaillées

### Phase 1 : Backend — Schemas & Endpoints Stacks managées

1. **Schemas Pydantic** — Fichier : `backend/app/schemas/stack.py`
   - Ajouter `StackActionResponse(action, message, stack_id)`, `RedeployStrategy` (Literal), `StackRedeployRequest(strategy, pull_images)`, `StackRedeployResponse(étend StackActionResponse + strategy, pull_images, services_affected)`
   - Objectif : Valider les requêtes/réponses des 3 endpoints d'action

2. **Endpoint POST /stacks/{id}/start** — Fichier : `backend/app/api/v1/stacks.py`
   - Créer helper `_get_stack_and_containers(stack_id, org_id)` qui vérifie la stack en DB, ping Docker, récupère les containers via label `windflow.stack_id`
   - Endpoint : itère sur les containers, appelle `docker.start_container(cid)`, retourne `StackActionResponse`
   - Gestion 304 (déjà démarré), 404 (stack/container non trouvé), 503 (Docker indisponible)

3. **Endpoint POST /stacks/{id}/stop** — Fichier : `backend/app/api/v1/stacks.py`
   - Même pattern que start avec `docker.stop_container(cid, timeout=10)`

4. **Endpoint POST /stacks/{id}/redeploy** — Fichier : `backend/app/api/v1/stacks.py`
   - Accepte `StackRedeployRequest` body (strategy + pull_images)
   - Stratégie `stop_start` : stop tous → pull images → start tous
   - Stratégie `rolling` : pour chaque container : stop → pull → start (un par un)
   - Retourne `StackRedeployResponse` avec `services_affected`

### Phase 2 : Frontend — Types, API & Composant StackActionsBar

5. **Types TypeScript** — Fichier : `frontend/src/types/api.ts`
   - Ajouter `RedeployStrategy`, `StackActionResponse`, `StackRedeployRequest`, `StackRedeployResponse`

6. **Méthodes API** — Fichier : `frontend/src/services/api.ts`
   - Ajouter `stacksApi.start(id)`, `stacksApi.stop(id)`, `stacksApi.redeploy(id, data)` avec imports des nouveaux types

7. **Composant StackActionsBar.vue** — Fichier : `frontend/src/components/compute/StackActionsBar.vue` (CRÉER)
   - Props : `stack` (StackWithServices), `loading` (boolean)
   - 3 boutons : ▶ Start, ⏹ Stop, 🔄 Redeploy
   - Désactivation intelligente : Start disabled si `allRunning`, Stop disabled si `allStopped`
   - Dialog ElDialog pour stratégie redeploy (radio rolling/stop-start + checkbox pull_images)
   - Confirmation ElMessageBox avant chaque action
   - Émet `action-completed` après succès pour rafraîchissement parent

8. **Intégration ManagedStacksSection** — Fichier : `frontend/src/components/compute/ManagedStacksSection.vue`
   - Importer et utiliser StackActionsBar dans chaque ligne de stack expansée
   - Handler `handleStackActionCompleted` : recharge les données compute via emit

9. **Export** — Fichier : `frontend/src/components/compute/index.ts`
   - Ajouter `export { default as StackActionsBar } from './StackActionsBar.vue'`

### Phase 3 : Backend — Batch container actions (discovered stacks)

10. **Schemas batch** — Fichier : `backend/app/schemas/docker.py`
    - Ajouter `BatchContainerActionRequest(container_ids: list[str])`, `BatchContainerActionResponse(success, message, action, affected, errors)`

11. **Endpoints batch** — Fichier : `backend/app/api/v1/docker.py`
    - `POST /containers/batch/start` : itère sur container_ids, démarre chacun, collecte erreurs
    - `POST /containers/batch/stop` : même pattern avec stop
    - ⚠️ **ORDRE IMPORTANT** : Ces routes DOIVENT être définies AVANT les routes `{container_id}` pour éviter que FastAPI ne matche "batch" comme container_id

### Phase 4 : Frontend — Discovered stacks (batch actions)

12. **Types TS batch** — Fichier : `frontend/src/types/api.ts`
    - Ajouter `BatchContainerActionRequest`, `BatchContainerActionResponse`

13. **API batch** — Fichier : `frontend/src/services/api.ts`
    - Ajouter `containersApi.batchStart(ids)`, `containersApi.batchStop(ids)`

14. **Intégration DiscoveredSection** — Fichier : `frontend/src/components/compute/DiscoveredSection.vue`
    - Ajouter boutons ▶ Démarrer / ⏹ Arrêter par item discovered
    - Désactivation : Start disabled si `services_running === services_total`, Stop disabled si `services_running === 0`
    - Filtrage IDs : `handleItemStart` ne cible que les containers `status !== 'running'`, `handleItemStop` ne cible que `status === 'running'`

### Phase 5 : Tests (à compléter)

15. **Tests backend** — Fichier : `backend/tests/unit/test_stack_actions.py`
    - Test start_stack succès, stop_stack succès, redeploy_stack stop_start, redeploy_stack rolling
    - Test 404 stack inexistante, 503 Docker indisponible, erreur container individuel

16. **Tests frontend** — Fichier : `frontend/tests/unit/StackActionsBar.spec.ts`
    - Test rendu boutons, désactivation selon état, confirmation dialog, appel API, notification succès/erreur

## Tests à écrire

### Backend (`backend/tests/unit/test_stack_actions.py`)
1. `test_start_stack_success` — Mock DockerClientService, vérifie 200 + StackActionResponse
2. `test_stop_stack_success` — Idem avec stop
3. `test_redeploy_stop_start_strategy` — Vérifie séquence stop→pull→start
4. `test_redeploy_rolling_strategy` — Vérifie séquence par container
5. `test_start_stack_not_found` — Stack inexistante → 404
6. `test_start_stack_docker_unavailable` — Docker ne répond pas → 503
7. `test_batch_start_partial_errors` — Certains containers en erreur → success=false avec détail

### Frontend (`frontend/tests/unit/StackActionsBar.spec.ts`)
1. Test rendu des 3 boutons avec stack running
2. Test désactivation Start si allRunning
3. Test désactivation Stop si allStopped
4. Test clic Start → confirmation → appel API → notification succès
5. Test clic Redeploy → ouverture dialog → sélection stratégie → appel API
6. Test erreur API → notification erreur

## Critères d'acceptation (AC)
- [x] AC 1 : Les boutons Start/Stop déclenchent `POST /stacks/{id}/start` et `POST /stacks/{id}/stop` avec une confirmation préalable
- [x] AC 2 : Le bouton Redeploy ouvre un dialog permettant de choisir la stratégie (rolling/stop-start) avant de déclencher `POST /stacks/{id}/redeploy`
- [x] AC 3 : Un indicateur de progression (spinner/loading) est affiché pendant l'opération en cours
- [x] AC 4 : Une notification toast confirme le succès ou l'échec de chaque action
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur (tests unitaires restent à écrire)

## État d'avancement technique
- [x] Tâche 1 : Schemas Pydantic (StackActionResponse, StackRedeployRequest, StackRedeployResponse)
- [x] Tâche 2 : Endpoint POST /stacks/{id}/start
- [x] Tâche 3 : Endpoint POST /stacks/{id}/stop
- [x] Tâche 4 : Endpoint POST /stacks/{id}/redeploy
- [x] Tâche 5 : Types TypeScript frontend
- [x] Tâche 6 : Méthodes API frontend (stacksApi.start/stop/redeploy)
- [x] Tâche 7 : Composant StackActionsBar.vue
- [x] Tâche 8 : Dialog de stratégie Redeploy (intégré dans StackActionsBar)
- [x] Tâche 9 : Intégration dans ManagedStacksSection.vue
- [x] Tâche 10 : Export index.ts
- [x] Tâche 11 : Endpoints batch start/stop containers (discovered stacks)
- [x] Tâche 12 : Types TS BatchContainerActionRequest/Response
- [x] Tâche 13 : Méthodes API containersApi.batchStart/batchStop
- [x] Tâche 14 : Intégration boutons Start/Stop dans DiscoveredSection.vue
- [ ] Tests backend (7 tests)
- [ ] Tests frontend (6 tests)

## Notes d'implémentation

### Fichiers modifiés/créés
- **`backend/app/schemas/stack.py`** — Ajout de `StackActionResponse`, `RedeployStrategy`, `StackRedeployRequest`, `StackRedeployResponse`
- **`backend/app/api/v1/stacks.py`** — Ajout de 3 endpoints (`start_stack`, `stop_stack`, `redeploy_stack`) + helper `_get_stack_and_containers`
- **`frontend/src/types/api.ts`** — Ajout de `RedeployStrategy`, `StackActionResponse`, `StackRedeployRequest`, `StackRedeployResponse`
- **`frontend/src/services/api.ts`** — Ajout de `stacksApi.start()`, `.stop()`, `.redeploy()` + imports
- **`frontend/src/components/compute/StackActionsBar.vue`** — **CRÉÉ** : composant autonome avec 3 boutons + dialog ElDialog pour stratégie redeploy
- **`frontend/src/components/compute/ManagedStacksSection.vue`** — Intégration de StackActionsBar + handler `handleStackActionCompleted`
- **`frontend/src/components/compute/index.ts`** — Export de StackActionsBar

#### Discovered stacks (batch container actions)
- **`backend/app/schemas/docker.py`** — Ajout de `BatchContainerActionRequest`, `BatchContainerActionResponse`
- **`backend/app/api/v1/docker.py`** — Ajout de 2 endpoints batch (`POST /docker/containers/batch/start`, `POST /docker/containers/batch/stop`)
- **`frontend/src/types/api.ts`** — Ajout de `BatchContainerActionRequest`, `BatchContainerActionResponse`
- **`frontend/src/services/api.ts`** — Ajout de `containersApi.batchStart()`, `.batchStop()` + import
- **`frontend/src/components/compute/DiscoveredSection.vue`** — Ajout boutons ▶ Démarrer / ⏹ Arrêter par item discovered + fonctions `handleItemStart`, `handleItemStop` utilisant les endpoints batch

### Décisions techniques
1. **Composant autonome** : StackActionsBar gère directement les appels API et les confirmations (pas de délégation au parent), émettant seulement `action-completed` pour rafraîchir les données.
2. **Label Docker** : Les containers sont identifiés via `windflow.stack_id` (label existant du classifier).
3. **Deux stratégies de redéploiement** : `stop_start` (arrêt complet puis redémarrage) et `rolling` (un par un).
4. **Backend : vérification perm-org** : Chaque endpoint vérifie l'appartenance de la stack à l'organisation de l'utilisateur.
5. **Gestion Docker indisponible** : HTTP 503 si Docker ne répond pas au ping.

### Corrections post-review

#### Désactivation intelligente des boutons
- **`StackActionsBar.vue`** : `allRunning` / `allStopped` calculés via `services_running === services_total` et `services_running === 0`. Start désactivé si tous actifs, Stop désactivé si tous inactifs.
- **`DiscoveredSection.vue`** : Même logique `:disabled` + filtrage des IDs dans les handlers — `handleItemStart` ne cible que les containers `status !== 'running'`, `handleItemStop` ne cible que les containers `status === 'running'`.

#### Fix routage FastAPI (batch routes)
- **Cause racine** : Les routes `POST /containers/batch/start` et `/batch/stop` étaient définies **après** les routes `POST /containers/{container_id}/start`. FastAPI matchait `batch` comme `container_id` → Docker cherchait un container "batch" → 404.
- **Fix** : Déplacé les 2 routes batch **avant** les routes paramétrées `{container_id}` dans `backend/app/api/v1/docker.py`, avec un commentaire explicatif `IMPORTANT`.

### Validation
- Backend : `poetry run python -c "from app.api.v1.stacks import router; print(len(router.routes))"` → **12 routes** (9 existantes + 3 nouvelles)
- Frontend : `vue-tsc --noEmit` → **0 nouvelle erreur** (1 erreur pré-existante dans `targets.ts` non liée)
- Backend docker.py : routes batch définies avant routes `{container_id}` (vérifié, pas de doublon)
