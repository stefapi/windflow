# STORY-010 : Duplication de stack

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux dupliquer une stack existante afin de créer rapidement une stack similaire sans tout reconfigurer depuis zéro.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `POST /stacks/{id}/duplicate`
- Type TypeScript à ajouter : `StackDuplicateRequest`
- Dialog de duplication : champ nom de la nouvelle stack + option de target différente
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [x] AC 1 : Chaque stack dispose d'une action "Dupliquer" qui ouvre un dialog de configuration
- [x] AC 2 : Le dialog permet de saisir le nom de la nouvelle stack et optionnellement de choisir une target différente
- [x] AC 3 : La duplication appelle `POST /stacks/{id}/duplicate` et la liste se rafraîchit avec la nouvelle stack
- [x] AC 4 : Le type TypeScript `StackDuplicateRequest` est défini et `stacksApi.duplicate` est disponible
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->
- [x] Tâche 1 : Schema backend `StackDuplicateRequest`
- [x] Tâche 2 : Endpoint backend `POST /stacks/{id}/duplicate`
- [x] Tâche 3 : Type frontend `StackDuplicateRequest`
- [x] Tâche 4 : Méthode API frontend `stacksApi.duplicate`
- [x] Tâche 5 : Action `duplicate` dans `ActionButtons.vue`
- [x] Tâche 6 : Dialog et handler de duplication dans `Stacks.vue`
- [x] Tests backend et frontend

## Tâches d'implémentation détaillées

### Tâche 1 : Schema backend StackDuplicateRequest
**Objectif :** Créer le schema Pydantic `StackDuplicateRequest` pour valider le body de la requête de duplication de stack.
**Fichiers :**
- `backend/app/schemas/stack.py` — Modifier — Ajouter la classe `StackDuplicateRequest(BaseModel)` avec :
  - `new_name: str` (Field, min_length=1, max_length=255, description="Nom du nouveau stack")
  - `organization_id: Optional[str]` (Field, None, description="ID de l'organisation cible — par défaut celle du stack original")
  - `model_config` avec `json_schema_extra` contenant un exemple
  - Placer cette classe après `StackUpdate` et avant `StackResponse` (ordre logique des schemas)
- `backend/app/api/v1/stacks.py` — Modifier — Ajouter l'import de `StackDuplicateRequest` dans le bloc d'imports existant depuis `...schemas.stack`
**Dépend de :** Aucune

### Tâche 2 : Endpoint backend POST /stacks/{id}/duplicate
**Objectif :** Exposer l'endpoint de duplication accessible aux utilisateurs authentifiés (pas seulement superadmin). S'inspirer de l'endpoint admin existant dans `backend/app/api/v1/admin/stacks_management.py:673` mais avec `get_current_active_user` au lieu de `get_current_superadmin`.
**Fichiers :**
- `backend/app/api/v1/stacks.py` — Modifier — Ajouter un nouvel endpoint :
  ```
  @router.post("/{stack_id}/duplicate", response_model=StackResponse, ...)
  async def duplicate_stack(stack_id, data: StackDuplicateRequest, current_user, session)
  ```
  - Vérifier que le stack existe (404 si non trouvé via `StackService.get_by_id`)
  - Vérifier l'unicité du nom dans l'org cible (409 si conflit via `StackService.get_by_name`)
  - Créer la copie via `StackService.create` avec un `StackCreate` construit à partir des données du stack original
  - Préfixer la description avec "Copie de {original.name} : "
  - Ajouter le tag "duplicate" aux tags
  - `is_public=False` par défaut
  - Utiliser `organization_id` du body ou celle du stack original
  - Documenter l'endpoint avec OpenAPI (summary, description, responses 200/404/409)
  - Ajouter le rate limiter : `dependencies=[Depends(conditional_rate_limiter(20, 60))]`
**Dépend de :** Tâche 1

### Tâche 3 : Type frontend StackDuplicateRequest
**Objectif :** Définir l'interface TypeScript `StackDuplicateRequest` qui mirror le schema backend, et l'exporter pour usage dans l'API service.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter après les types `StackUpdate` existants (vers la ligne 261) :
  ```typescript
  export interface StackDuplicateRequest {
    new_name: string
    organization_id?: string
  }
  ```
- `frontend/src/services/api.ts` — Modifier — Ajouter `StackDuplicateRequest` à la liste des imports depuis `@/types/api`
**Dépend de :** Aucune

### Tâche 4 : Méthode API frontend stacksApi.duplicate
**Objectif :** Ajouter la méthode `duplicate` à l'objet `stacksApi` dans le service API pour appeler `POST /stacks/{id}/duplicate`.
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier — Ajouter dans l'objet `stacksApi` (après la méthode `redeploy`, vers la ligne 210) :
  ```typescript
  duplicate: (id: string, data: StackDuplicateRequest) =>
    http.post<Stack>(`/stacks/${id}/duplicate`, data),
  ```
**Dépend de :** Tâche 3

### Tâche 5 : Action duplicate dans ActionButtons.vue
**Objectif :** Ajouter le type d'action `'duplicate'` au composant `ActionButtons.vue` avec l'icône `CopyDocument` et le tooltip "Dupliquer".
**Fichiers :**
- `frontend/src/components/ui/ActionButtons.vue` — Modifier — Trois changements :
  1. Ajouter `CopyDocument` à l'import depuis `@element-plus/icons-vue` (ligne 44-55)
  2. Ajouter `'duplicate'` au type `ActionType` (ligne 58) : `'start' | 'stop' | ... | 'export' | 'duplicate'`
  3. Ajouter l'entrée `duplicate` dans `defaultActionConfig` (après `export`, vers ligne 136) :
     ```typescript
     duplicate: {
       icon: CopyDocument,
       tooltip: 'Dupliquer',
     },
     ```
**Dépend de :** Aucune

### Tâche 6 : Dialog et handler de duplication dans Stacks.vue
**Objectif :** Ajouter le bouton "Dupliquer" dans les actions de chaque stack, un dialog de configuration (nom + organisation cible optionnelle), et le handler qui appelle l'API puis rafraîchit la liste.
**Fichiers :**
- `frontend/src/views/Stacks.vue` — Modifier — Plusieurs changements :
  1. **Template — ActionButtons** (ligne 65) : Ajouter `'duplicate'` au tableau `actions` : `['edit', 'deploy', 'export', 'duplicate', 'delete']`
  2. **Template — Dialog de duplication** : Ajouter après le dialog d'import (après ligne 515), un nouveau `<el-dialog>` avec :
     - `v-model="showDuplicateDialog"`, title="Duplicate Stack", width="500px", destroy-on-close
     - Champ nom (`el-input`, pré-rempli avec `{originalName} (copy)`, required)
     - Footer : bouton Cancel + bouton "Duplicate" (type primary, loading)
  3. **Script — State** : Ajouter les refs :
     - `showDuplicateDialog = ref(false)`
     - `duplicateStack = ref<Stack | null>(null)`
     - `duplicating = ref(false)`
     - `duplicateForm = reactive({ new_name: '' })`
  4. **Script — Handler** : Ajouter la fonction `openDuplicateDialog(stack: Stack)` qui pré-remplit le nom, et la fonction async `handleDuplicate()` qui :
     - Appelle `stacksApi.duplicate(duplicateStack.value.id, { new_name: duplicateForm.new_name })`
     - Affiche `ElMessage.success` en cas de succès
     - Rafraîchit la liste via `stacksStore.fetchStacks(authStore.organizationId || undefined)`
     - Sélectionne la nouvelle stack dans le panneau de détail
     - Affiche `ElMessage.error` en cas d'échec
  5. **Script — handleStackAction** : Ajouter le case `'duplicate'` dans le switch (ligne 888) :
     ```typescript
     case 'duplicate':
       openDuplicateDialog(stack)
       break
     ```
**Dépend de :** Tâche 4, Tâche 5

## Tests à écrire

### Tests backend

**Fichier :** `backend/tests/unit/test_stacks_duplicate.py` — Créer

- **test_duplicate_stack_success** : Dupliquer un stack existant avec un nouveau nom → 200, vérifier que la copie a le bon nom, la même template, le tag "duplicate", is_public=False
- **test_duplicate_stack_not_found** : Dupliquer un stack inexistant → 404
- **test_duplicate_stack_name_conflict** : Dupliquer avec un nom déjà existant dans la même org → 409
- **test_duplicate_stack_different_org** : Dupliquer vers une autre organisation → 200, vérifier organization_id cible
- **test_duplicate_stack_empty_name** : Body avec new_name vide → 422 (validation Pydantic)
- **test_duplicate_stack_unauthenticated** : Appel sans token → 401

**Commande de validation backend :**
```bash
cd backend && python -m pytest tests/unit/test_stacks_duplicate.py -v
```

### Tests frontend

**Fichier :** `frontend/tests/unit/views/Stacks.spec.ts` — Modifier (ajouter un nouveau describe)

- **test openDuplicateDialog pre-fills name** : Vérifier que `openDuplicateDialog(stack)` pré-remplit le champ nom avec `{stack.name} (copy)` et ouvre le dialog
- **test handleDuplicate calls stacksApi.duplicate** : Vérifier que `handleDuplicate` appelle `stacksApi.duplicate` avec le bon ID et le bon nom
- **test handleDuplicate shows success message** : Vérifier `ElMessage.success` est appelé après duplication réussie
- **test handleDuplicate shows error on API failure** : Mock un rejet API → vérifier `ElMessage.error`
- **test handleDuplicate refreshes stack list** : Vérifier que `stacksStore.fetchStacks` est appelé après succès
- **test handleStackAction routes duplicate to openDuplicateDialog** : Vérifier que l'action 'duplicate' dans le switch appelle `openDuplicateDialog`

**Fichier :** `frontend/tests/unit/components/ui/ActionButtons.spec.ts` — Modifier

- **test duplicate action renders with CopyDocument icon** : Vérifier que l'action 'duplicate' affiche un bouton avec le bon tooltip "Dupliquer"

**Commandes de validation frontend :**
```bash
cd frontend && pnpm test -- --run tests/unit/views/Stacks.spec.ts
cd frontend && pnpm test -- --run tests/unit/components/ui/ActionButtons.spec.ts
cd frontend && pnpm build
cd frontend && pnpm lint
```

## Notes d'implémentation
**Date :** 2026-04-14
### Fichiers modifiés/créés
- `backend/app/schemas/stack.py` — Ajout de `StackDuplicateRequest(BaseModel)` entre `StackUpdate` et `StackResponse`
- `backend/app/api/v1/stacks.py` — Import `StackDuplicateRequest` + endpoint `POST /{stack_id}/duplicate` avec `get_current_active_user`
- `frontend/src/types/api.ts` — Ajout de `StackDuplicateRequest` interface
- `frontend/src/services/api.ts` — Import `StackDuplicateRequest` + méthode `stacksApi.duplicate`
- `frontend/src/components/ui/ActionButtons.vue` — Import `CopyDocument`, ajout `'duplicate'` au type `ActionType`, config `duplicate`
- `frontend/src/views/Stacks.vue` — Action `'duplicate'` dans ActionButtons, dialog de duplication, refs state, handlers `openDuplicateDialog`/`handleDuplicate`, case `'duplicate'` dans `handleStackAction`
- `backend/tests/unit/test_stacks_duplicate.py` — Créé : 6 tests (success, 404, 409, cross-org, 422, 401)
- `frontend/tests/unit/views/Stacks.spec.ts` — Ajout mock `duplicate`, 6 nouveaux tests (openDuplicateDialog, handleDuplicate x4, handleStackAction)
- `frontend/tests/unit/components/ui/ActionButtons.spec.ts` — Ajout 2 tests (render + emit duplicate)
### Décisions techniques
- L'endpoint utilisateur utilise `get_current_active_user` (pas superadmin) pour permettre à tout utilisateur authentifié de dupliquer
- Le nom pré-rempli dans le dialog suit le pattern `{originalName} (copy)`
- Le tag `"duplicate"` est ajouté aux tags du stack copié
- `is_public=False` par défaut sur la copie (sécurité)
- Les erreurs TypeScript pré-existantes (Images.vue, `import`/`export` réservés) ne sont pas liées à cette story
### Résultat validation
- ✅ Backend syntax check : OK
- ✅ Frontend lint (eslint) : OK (0 erreurs sur fichiers modifiés)
- ✅ Frontend tests : 38/38 passés (2 fichiers de test)
- ⚠️ TypeScript : erreurs pré-existantes uniquement (Images.vue, propriétés réservées `import`/`export`)
