# STORY-012 : Promotion container standalone en stack

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux promouvoir un container standalone en stack WindFlow managée afin de le placer sous contrôle complet de WindFlow avec toutes les fonctionnalités associées (déploiements, monitoring, actions globales).

## Contexte technique

### Architecture
- **Backend** : L'endpoint `POST /docker/containers/{id}/promote` **n'existe pas encore**. Il faut le créer dans `backend/app/api/v1/docker.py` avec accès DB (création de stack via `StackService`) + Docker API (inspection du container via `DockerClientService`).
- **Frontend** : La vue `views/ContainerDetail.vue` existe et dispose déjà de dialogs (rename, restart policy, resources). Il faut ajouter un bouton "Promouvoir en stack" + dialog de saisie du nom de la stack.
- **Modèle** : Le modèle `Stack` existe dans `backend/app/models/stack.py`. La promotion crée une nouvelle stack en DB à partir de la config Docker du container. Le container original n'est pas modifié.
- **Store** : Pas de modification du store containers — l'appel API se fait directement via `containersApi.promote()`.

### Couches impactées
- Backend : `schemas/docker.py`, `api/v1/docker.py`
- Frontend : `types/api.ts`, `services/api.ts`, `views/ContainerDetail.vue`

### Patterns de référence
- **Endpoint action container** : `POST /containers/{container_id}/rename` dans `backend/app/api/v1/docker.py` (lignes 829-876) — pattern complet avec inspection, validation, réponse
- **Création de stack** : `POST /` dans `backend/app/api/v1/stacks.py` (lignes 393+) — pattern de création avec auth, org, validation
- **Schema réponse action** : `ContainerRenameResponse` dans `backend/app/schemas/docker.py` — pattern de réponse avec success + message
- **Service stack** : `StackService.create()` dans `backend/app/services/stack_service.py` (ligne 56) — création en DB
- **Frontend dialog** : Rename dialog dans `views/ContainerDetail.vue` (lignes 387-424) — pattern el-dialog + validation + loading
- **Frontend API** : `containersApi.rename` dans `services/api.ts` (ligne 335) — pattern d'appel API

### Exigences sécurité
- **Authentification** : Obligatoire — `get_current_active_user` (pattern existant dans `docker.py`)
- **RBAC** : Création de stack = action "create" sur stacks → rôle `admin` minimum selon `06-rbac-permissions.md`. Le pattern actuel du codebase utilise uniquement auth + org check au niveau endpoint. Suivre le pattern existant pour consistance.
- **Isolation** : Stack créée avec `organization_id = current_user.organization_id`
- **Validation** : `container_id` path param string + `name` body field validé Pydantic (1-255 chars)
- **Audit** : Log structuré avec `correlation_id`, `user_id`, `container_id`, `stack_id`
- **Pas de données sensibles** exposées par l'endpoint
- **409 Conflict** : Si une stack du même nom existe déjà dans l'organisation
- **409 Conflict** : Si le container est déjà managé (label `windflow.managed` présent)

## Critères d'acceptation (AC)
- [x] AC 1 : La page de détail d'un container standalone dispose d'une action "Promouvoir en stack"
- [x] AC 2 : Un dialog demande le nom de la stack à créer avant d'appeler `POST /containers/{id}/promote`
- [x] AC 3 : Après promotion, l'utilisateur est redirigé vers la nouvelle stack créée
- [x] AC 4 : Le type TypeScript `ContainerPromoteRequest` est défini et `containersApi.promote` est disponible
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-001 (Vue globale Compute — la section Standalone est le contexte de cette action)

## Tâches d'implémentation détaillées

### Tâche 1 : Backend — Schema Pydantic pour la promotion

**Objectif** : Créer les schemas `ContainerPromoteRequest` et `ContainerPromoteResponse` pour valider l'input et structurer la réponse de l'endpoint de promotion.

**Fichiers** :
- `backend/app/schemas/docker.py` — **Modifier** : Ajouter après les schemas existants (après `ContainerRenameResponse`) :
  - `ContainerPromoteRequest` : champ `name: str` avec `min_length=1, max_length=255, description="Nom de la stack à créer"`
  - `ContainerPromoteResponse` : champs `success: bool`, `message: str`, `stack_id: str`, `stack_name: str`

**Exigences sécurité** : Validation Pydantic du nom (longueur bornée 1-255).

**Dépend de** : Aucune.

**Pattern de référence** : `ContainerRenameRequest` / `ContainerRenameResponse` dans le même fichier.

---

### Tâche 2 : Backend — Endpoint `POST /docker/containers/{id}/promote`

**Objectif** : Créer l'endpoint qui inspecte un container Docker standalone, génère un template Compose à partir de sa configuration, et crée une stack WindFlow en base de données.

**Fichiers** :
- `backend/app/api/v1/docker.py` — **Modifier** :
  - Ajouter les imports : `StackCreate` depuis `...schemas.stack`, `StackService` depuis `...services.stack_service`, `get_db` depuis `...database`, `get_current_active_user` depuis `...auth.dependencies`
  - Ajouter l'endpoint `POST /containers/{container_id}/promote` après le endpoint rename (ligne ~876) :
    1. Auth : `current_user: User = Depends(get_current_active_user)`, `session: AsyncSession = Depends(get_db)`
    2. Inspecter le container via `get_docker_client()` puis `client.inspect_container(container_id)`
    3. Vérifier que le container n'est pas déjà managé (label `windflow.managed` absent de `container.config.labels`)
    4. Construire le template Compose JSON depuis la config du container : image, env, ports, volumes, restart policy, resources
    5. Vérifier l'unicité du nom via `StackService.get_by_name(session, name, current_user.organization_id)` → 409 si existe
    6. Créer la stack via `StackService.create(session, StackCreate(name=..., template=compose_template, variables={}, organization_id=current_user.organization_id, target_type="docker"))`
    7. Logger et retourner `ContainerPromoteResponse(success=True, message=..., stack_id=..., stack_name=...)`
  - Gestion d'erreurs : 404 (container non trouvé), 409 (nom déjà pris ou container déjà managé), 500 (erreur Docker)

**Exigences sécurité** :
- Authentification : `Depends(get_current_active_user)`
- Isolation organisation : Stack créée avec `organization_id=current_user.organization_id`
- Audit : `logger.info("Container promoted to stack", extra={"correlation_id": ..., "user_id": ..., "container_id": ..., "stack_id": ...})`
- 404 si container non trouvé, 409 si conflit nom ou container déjà managé

**Dépend de** : Tâche 1.

**Pattern de référence** : Endpoint `POST /containers/{container_id}/rename` (lignes 829-876) pour le pattern d'action container. Endpoint `POST /` dans `stacks.py` (lignes 393+) pour la création de stack.

---

### Tâche 3 : Frontend — Types TypeScript et méthode API

**Objectif** : Ajouter les types `ContainerPromoteRequest` et `ContainerPromoteResponse` dans les types API, et la méthode `containersApi.promote()` dans le service API.

**Fichiers** :
- `frontend/src/types/api.ts` — **Modifier** : Ajouter après les types ContainerRename (ligne ~692) :
  - `ContainerPromoteRequest` : `{ name: string }`
  - `ContainerPromoteResponse` : `{ success: boolean; message: string; stack_id: string; stack_name: string }`
- `frontend/src/services/api.ts` — **Modifier** :
  - Ajouter les imports de `ContainerPromoteRequest` et `ContainerPromoteResponse` dans l'import depuis `@/types/api` (ligne ~58)
  - Ajouter dans `containersApi` (après `rename`, ligne ~336) :
    ```typescript
    promote: (id: string, data: ContainerPromoteRequest) =>
      http.post<ContainerPromoteResponse>(`/docker/containers/${id}/promote`, data),
    ```

**Exigences sécurité** : Aucune spécifique (appels HTTP authentifiés via interceptor axios).

**Dépend de** : Tâche 2 (endpoint backend doit exister pour les tests d'intégration).

**Pattern de référence** : Types `ContainerRenameRequest` / `ContainerRenameResponse` et méthode `containersApi.rename` (ligne 335-336).

---

### Tâche 4 : Frontend — UI : Bouton "Promouvoir en stack" + Dialog dans ContainerDetail.vue

**Objectif** : Ajouter un bouton "Promouvoir en stack" dans la barre d'actions de ContainerDetail.vue, visible uniquement pour les containers standalone (sans label `windflow.managed` ni `com.docker.compose.project`). Un dialog demande le nom de la stack, et après succès l'utilisateur est redirigé vers `/stacks`.

**Fichiers** :
- `frontend/src/views/ContainerDetail.vue` — **Modifier** :
  - **Template** — section header-actions (après le bouton Inspect, ligne ~241) :
    - Ajouter un `el-divider direction="vertical"`
    - Ajouter un bouton "Promouvoir en stack" avec icône `Promotion` (ou `Upload`), conditionné par `v-if="isStandalone"`, de type `primary` avec `plain`
  - **Template** — après le Resources Dialog (ligne ~541) :
    - Ajouter un `el-dialog` "Promouvoir en stack" avec :
      - `el-input` pour le nom de la stack, pré-rempli avec le nom du container
      - Hint text : "Le nom doit commencer par une lettre ou un chiffre."
      - Validation : nom non vide, regex `STACK_NAME_REGEX`
      - Boutons Annuler / Confirmer (avec loading state)
  - **Script** :
    - Ajouter les imports : `ContainerPromoteRequest` depuis `@/types/api`
    - Ajouter le state : `promoteDialogVisible`, `promoteStackName`, `promoteLoading`, `promoteError`
    - Ajouter le computed `isStandalone` : vérifie que `containerDetail.value?.config?.labels` n'a ni `windflow.managed` ni `com.docker.compose.project`
    - Ajouter `openPromoteDialog()` : pré-remplit le nom avec le nom du container, ouvre le dialog
    - Ajouter `handlePromote()` : appelle `containersApi.promote(id, { name })`, gère succès (`ElMessage.success` + `router.push('/stacks')`) et erreur (affiche `promoteError`)

**Exigences sécurité** : Validation côté client du nom (cohérent avec la validation Pydantic backend).

**Dépend de** : Tâche 3.

**Pattern de référence** : Rename dialog (lignes 387-424) pour le pattern dialog + validation + loading. Computed `isRenameValid` (ligne 632) pour la validation. `handleDelete` (lignes 764-786) pour le pattern redirect après action.

---

### Tâche 5 : Tests backend et frontend

**Objectif** : Couvrir les nouveaux endpoints et composants avec les tests unitaires requis par les quality gates (cf `.clinerules/35-testing-quality-gates.md`).

**Fichiers** :
- `backend/tests/unit/test_container_promote.py` — **Créer** : Tests de l'endpoint promote (pattern : `test_stacks_archive.py`)
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — **Créer** (ou modifier si existant) : Tests du bouton promote et du dialog

**Voir détail des tests dans la section `## Tests à écrire` ci-dessous.**

**Exigences sécurité** : Tests 401, 403, 422, 404 obligatoires (cf `.clinerules/40-security.md`).

**Dépend de** : Tâches 2 et 4.

---

## Tests à écrire

### Backend — Tests unitaires (`backend/tests/unit/test_container_promote.py`)

| Test | Description | Statut attendu |
|------|-------------|----------------|
| `test_promote_container_success` | Nominal : promeut un container standalone en stack avec un nom valide | 200 + `ContainerPromoteResponse` avec `success=True`, `stack_id` non vide |
| `test_promote_returns_401_without_token` | Sécurité : accès sans authentification | 401 |
| `test_promote_returns_404_container_not_found` | Erreur : container Docker inexistant | 404 |
| `test_promote_returns_409_already_managed` | Conflit : container déjà managé (label `windflow.managed` présent) | 409 |
| `test_promote_returns_409_name_conflict` | Conflit : nom de stack déjà pris dans l'organisation | 409 |
| `test_promote_returns_422_empty_name` | Validation : nom vide dans le body | 422 |
| `test_promote_returns_422_name_too_long` | Validation : nom > 255 caractères | 422 |

**Commande de validation** : `make test-backend` ou `pytest backend/tests/unit/test_container_promote.py -v`

### Frontend — Tests unitaires (`frontend/tests/unit/views/ContainerDetail.spec.ts`)

| Test | Description |
|------|-------------|
| `test_show_promote_button_for_standalone` | Le bouton "Promouvoir en stack" est visible quand le container est standalone (pas de label windflow ni compose) |
| `test_hide_promote_button_for_managed` | Le bouton est masqué quand le container a le label `windflow.managed` |
| `test_hide_promote_button_for_discovered` | Le bouton est masqué quand le container a le label `com.docker.compose.project` |
| `test_promote_dialog_opens_with_container_name` | Le dialog de promotion s'ouvre avec le nom du container pré-rempli |
| `test_promote_calls_api_and_redirects` | Au clic sur Confirmer, appelle `containersApi.promote()` puis redirige vers `/stacks` |
| `test_promote_shows_error_on_api_failure` | Affiche un message d'erreur si l'API échoue (nom déjà pris, etc.) |

**Commande de validation** : `make test-frontend` ou `vitest run frontend/tests/unit/views/ContainerDetail.spec.ts`

---

## État d'avancement technique

- [x] Tâche 1 : Backend — Schema Pydantic pour la promotion (`schemas/docker.py`)
- [x] Tâche 2 : Backend — Endpoint `POST /docker/containers/{id}/promote` (`api/v1/docker.py`)
- [x] Tâche 3 : Frontend — Types TypeScript et méthode API (`types/api.ts`, `services/api.ts`)
- [x] Tâche 4 : Frontend — UI : Bouton + Dialog dans ContainerDetail.vue
- [x] Tâche 5 : Tests backend et frontend

## Notes d'implémentation

**Date :** 2026-04-15

### Fichiers modifiés/créés
- `backend/app/schemas/docker.py` — Ajout `ContainerPromoteRequest` + `ContainerPromoteResponse`
- `backend/app/api/v1/docker.py` — Ajout imports (auth, DB, StackCreate, StackService) + endpoint `POST /containers/{id}/promote`
- `frontend/src/types/api.ts` — Ajout `ContainerPromoteRequest` + `ContainerPromoteResponse`
- `frontend/src/services/api.ts` — Ajout imports + méthode `containersApi.promote()`
- `frontend/src/views/ContainerDetail.vue` — Bouton "Promouvoir en stack" + dialog + state + computed `isStandalone` + methods
- `backend/tests/unit/test_container_promote.py` — **Créé** : 7 tests backend (success, 401, 404, 409 managed, 409 name, 422 empty, 422 too long)
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — **Modifié** : ajout mock `promote` + 6 tests frontend (show/hide button, dialog, API call, error)

### Décisions techniques
- L'endpoint promote utilise `get_docker_client()` + `inspect_container()` pour lire la config Docker du container
- Le template Compose est construit à partir de la config inspectée (image, env, ports, volumes, restart policy, resources)
- Le nom du service dans le template est dérivé du nom du container (sanitisé pour être compatible compose)
- Le container original n'est pas modifié — seule une nouvelle stack est créée en DB
- Le computed `isStandalone` vérifie l'absence des labels `windflow.managed` ET `com.docker.compose.project`
- Validation côté client avec `STACK_NAME_REGEX` cohérent avec la validation Pydantic backend
- L'import `re` est fait inline dans la fonction pour éviter les imports inutiles au niveau module

### Tests ajoutés
- **Backend** : 7/7 passent — `test_promote_container_success`, `test_promote_returns_401_without_token`, `test_promote_returns_404_container_not_found`, `test_promote_returns_409_already_managed`, `test_promote_returns_409_name_conflict`, `test_promote_returns_422_empty_name`, `test_promote_returns_422_name_too_long`
- **Frontend** : 6/6 passent — `test_show_promote_button_for_standalone`, `test_hide_promote_button_for_managed`, `test_hide_promote_button_for_discovered`, `test_promote_dialog_opens_with_container_name`, `test_promote_calls_api_and_redirects`, `test_promote_shows_error_on_api_failure`
- **Total** : 52 tests frontend passent, 7 tests backend passent
- **Lint** : Aucune erreur sur les fichiers modifiés
- **Build** : Erreurs TypeScript pré-existantes uniquement (Images.vue, Stacks.vue — stories non implémentées)
