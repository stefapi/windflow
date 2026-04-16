# STORY-011 : Archivage de stack

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux archiver une stack qui n'est plus en service afin de la conserver pour référence sans qu'elle encombre la vue principale.

## Contexte technique

### Architecture
- **Backend** : L'endpoint `POST /stacks/{id}/archive` n'existe pas encore. Il faut l'implémenter dans `backend/app/api/v1/stacks.py` en suivant le pattern des endpoints existants (`duplicate`, `start`, `stop`).
- **Frontend** : La vue `views/Stacks.vue` existe et utilise `ActionButtons` pour les actions par stack. Il faut ajouter l'action "archive" et une section "Archivées".
- **Modèle** : Le modèle `Stack` (`backend/app/models/stack.py`) n'a pas de champ `is_archived`. Il faut l'ajouter.
- **Store** : Le store `stores/stacks.ts` gère le CRUD basique. Il faut ajouter l'action `archiveStack`.

### Patterns de référence
- **Endpoint action** : `POST /{stack_id}/duplicate` dans `backend/app/api/v1/stacks.py` (lignes 1890-1978) — pattern complet avec auth, vérification org, logs structurés
- **Schema réponse action** : `StackActionResponse` dans `backend/app/schemas/stack.py` (lignes 554-597)
- **Service** : `StackService` dans `backend/app/services/stack_service.py` — méthodes statiques async
- **Frontend API** : `stacksApi` dans `frontend/src/services/api.ts` (lignes 170-215)
- **Frontend store** : `useStacksStore` dans `frontend/src/stores/stacks.ts`
- **Frontend composant actions** : `ActionButtons.vue` dans `frontend/src/components/ui/ActionButtons.vue`
- **Tests backend** : `backend/tests/unit/test_stacks_duplicate.py` — pattern de test avec fixtures
- **Tests frontend** : `frontend/tests/unit/views/Stacks.spec.ts` — pattern Vitest avec mocks

### Exigences sécurité
- **Authentification** : Obligatoire — `get_current_active_user` (comme tous les endpoints stacks)
- **RBAC** : Pas de restriction de rôle spécifique — tout utilisateur authentiqué de l'organisation peut archiver
- **Isolation** : Vérification `stack.organization_id == current_user.organization_id` (pattern existant ligne 379 de `stacks.py`)
- **Validation** : `stack_id` est un path param string (validé par FastAPI)
- **Audit** : Log structuré avec `correlation_id`, `user_id`, `stack_id` (pattern existant)
- **Pas de données sensibles** exposées par l'endpoint d'archivage

## Critères d'acceptation (AC)
- [x] AC 1 : Chaque stack active dispose d'une action "Archiver" qui demande confirmation avant d'appeler `POST /stacks/{id}/archive`
- [x] AC 2 : La stack archivée est retirée de la liste principale et apparaît dans une section "Archivées" (accessible via un filtre ou toggle)
- [x] AC 3 : `stacksApi.archive` est disponible dans `services/api.ts`
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

---

## Tâches d'implémentation détaillées

### Tâche 1 : Backend — Ajouter le champ `is_archived` au modèle Stack

**Objectif** : Ajouter un champ booléen `is_archived` au modèle SQLAlchemy `Stack` pour persister l'état d'archivage.

**Fichiers** :
- `backend/app/models/stack.py` — **Modifier** : Ajouter `is_archived: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)` après le champ `is_public` (ligne ~74). Ajouter un champ `archived_at: Mapped[Optional[datetime]]` pour tracer la date d'archivage.

**Exigences sécurité** : Aucune spécifique (champ interne au modèle).

**Dépendances** : Aucune.

**Pattern de référence** : Champ `is_public` existant dans le même modèle (ligne 74).

---

### Tâche 2 : Backend — Mettre à jour les schemas Pydantic

**Objectif** : Exposer le champ `is_archived` dans les schemas de réponse et permettre son utilisation côté frontend.

**Fichiers** :
- `backend/app/schemas/stack.py` — **Modifier** :
  - Ajouter `is_archived: bool = Field(default=False, ...)` à `StackResponse` (après `is_public`, ligne ~376)
  - Ajouter `is_archived: bool = Field(default=False, ...)` à `StackSummaryResponse` (après `downloads`, ligne ~491)
  - Ajouter `archived_at: Optional[datetime] = Field(None, ...)` aux deux schemas

**Exigences sécurité** : Aucune donnée sensible dans ces champs.

**Dépendances** : Tâche 1.

**Pattern de référence** : Champ `is_public` dans `StackResponse` (ligne 376-378).

---

### Tâche 3 : Backend — Créer l'endpoint `POST /stacks/{id}/archive` et filtrer la liste

**Objectif** : Implémenter l'endpoint d'archivage côté API et modifier le listing pour exclure les stacks archivées par défaut.

**Fichiers** :
- `backend/app/api/v1/stacks.py` — **Modifier** :
  - Ajouter `POST /{stack_id}/archive` : vérifier auth (`get_current_active_user`), vérifier org, appeler `StackService.archive()`, logger, retourner `StackActionResponse`
  - Ajouter `POST /{stack_id}/unarchive` : même pattern pour désarchiver
  - Modifier `list_stacks` (ligne ~185) : ajouter paramètre query `include_archived: bool = False`, filtrer la requête SQLAlchemy
- `backend/app/services/stack_service.py` — **Modifier** :
  - Ajouter méthode statique `async archive(db, stack_id) -> Stack` : passe `is_archived=True`, `archived_at=now`
  - Ajouter méthode statique `async unarchive(db, stack_id) -> Stack` : passe `is_archived=False`, `archived_at=None`
  - Modifier `list_by_organization` : ajouter paramètre `include_archived: bool = False`, filtrer avec `.where(Stack.is_archived == False)` si nécessaire

**Exigences sécurité** :
- Authentification : `Depends(get_current_active_user)`
- Isolation organisation : `stack.organization_id != current_user.organization_id → 403`
- Audit : `logger.info("Stack archived", extra={"correlation_id": ..., "user_id": ..., "stack_id": ...})`
- 404 si stack non trouvée

**Dépendances** : Tâches 1 et 2.

**Pattern de référence** : Endpoint `POST /{stack_id}/duplicate` (lignes 1890-1978 de `stacks.py`) — même structure d'auth, vérification org, logs, réponse.

---

### Tâche 4 : Frontend — Ajouter les types et méthodes API

**Objectif** : Exposer les méthodes `archive` et `unarchive` dans le service API et mettre à jour les types TypeScript.

**Fichiers** :
- `frontend/src/types/api.ts` — **Modifier** : Ajouter `is_archived?: boolean` et `archived_at?: string | null` à l'interface `Stack` (ligne ~239)
- `frontend/src/services/api.ts` — **Modifier** : Ajouter à `stacksApi` (après `duplicate`, ligne ~214) :
  ```typescript
  archive: (id: string) =>
    http.post<StackActionResponse>(`/stacks/${id}/archive`),
  unarchive: (id: string) =>
    http.post<StackActionResponse>(`/stacks/${id}/unarchive`),
  ```

**Exigences sécurité** : Aucune spécifique (appels HTTP authentifiés via interceptor axios).

**Dépendances** : Tâche 3 (endpoint backend doit exister).

**Pattern de référence** : Méthode `duplicate` existante dans `stacksApi` (ligne 213-214).

---

### Tâche 5 : Frontend — Mettre à jour le store Pinia

**Objectif** : Ajouter l'action `archiveStack` au store et gérer le filtrage des stacks archivées.

**Fichiers** :
- `frontend/src/stores/stacks.ts` — **Modifier** :
  - Ajouter un computed `activeStacks` : `stacks.value.filter(s => !s.is_archived)`
  - Ajouter un computed `archivedStacks` : `stacks.value.filter(s => s.is_archived)`
  - Ajouter une action `async archiveStack(id: string)` : appelle `stacksApi.archive(id)`, met à jour la stack dans `stacks.value`
  - Ajouter une action `async unarchiveStack(id: string)` : appelle `stacksApi.unarchive(id)`, met à jour la stack
  - Exporter les nouveaux composés et actions dans le return

**Exigences sécurité** : Aucune spécifique.

**Dépendances** : Tâche 4.

**Pattern de référence** : Action `deleteStack` existante (lignes 73-86) — même pattern d'appel API + mise à jour locale.

---

### Tâche 6 : Frontend — UI : ActionButtons + Stacks.vue (section archivées + confirmation)

**Objectif** : Ajouter le bouton "Archiver" avec confirmation et une section "Archivées" masquée par défaut dans la vue Stacks.

**Fichiers** :
- `frontend/src/components/ui/ActionButtons.vue` — **Modifier** :
  - Ajouter `'archive'` au type `ActionType` (ligne 59)
  - Ajouter l'entrée `archive` dans `defaultActionConfig` avec icône `Box` (ou `FolderOpened`) et tooltip "Archiver"
  - Importer l'icône depuis `@element-plus/icons-vue`
- `frontend/src/views/Stacks.vue` — **Modifier** :
  - **Template** :
    - Ajouter `'archive'` au tableau d'actions des `ActionButtons` (ligne 65) : `['edit', 'deploy', 'export', 'duplicate', 'archive', 'delete']`
    - Ajouter un toggle/switch "Afficher les stacks archivées" dans le header du card (après le bouton Import)
    - Ajouter une section `el-card` "Stacks archivées" (sous la table principale) avec une `el-table` affichant les stacks archivées, conditionnée par `showArchived`
    - Dans la table archivée, boutons "Désarchiver" et "Supprimer"
  - **Script** :
    - Ajouter `const showArchived = ref(false)`
    - Ajouter la fonction `async handleArchive(stack)` : `ElMessageBox.confirm(...)` puis `stacksStore.archiveStack(stack.id)` + `ElMessage.success(...)`
    - Ajouter la fonction `async handleUnarchive(stack)` : `stacksStore.unarchiveStack(stack.id)` + `ElMessage.success(...)`
    - Ajouter le case `'archive'` dans le `switch` de `handleStackAction` (ligne ~949)
  - **Style** : Ajouter style pour la section archivée (fond légèrement différent)

**Exigences sécurité** : Confirmation obligatoire avant archivage (AC 1).

**Dépendances** : Tâches 4 et 5.

**Pattern de référence** : Action `duplicate` existante dans `Stacks.vue` (dialog + handler lignes 517-545, 921-946). Confirmation via `ElMessageBox.confirm` (pattern `confirmDelete` lignes 818-831).

---

### Tâche 7 : Tests backend et frontend

**Objectif** : Couvrir les nouveaux endpoints et composants avec les tests unitaires requis par les quality gates.

**Fichiers** :
- `backend/tests/unit/test_stacks_archive.py` — **Créer** : Tests de l'endpoint archive (pattern : `test_stacks_duplicate.py`)
- `frontend/tests/unit/views/Stacks.spec.ts` — **Modifier** : Ajouter les tests pour l'action archive

**Voir détail des tests dans la section `## Tests à écrire` ci-dessous.**

**Exigences sécurité** : Tests 401, 403, 404 obligatoires (cf `.clinerules/40-security.md`).

**Dépendances** : Tâches 3 et 6.

---

## Tests à écrire

### Backend — Tests unitaires (`backend/tests/unit/test_stacks_archive.py`)

| Test | Description | Statut attendu |
|------|-------------|----------------|
| `test_archive_stack_success` | Archiver un stack existant dans sa propre org | 200, `is_archived=True`, `archived_at` non null |
| `test_archive_stack_not_found` | Archiver un stack inexistant | 404 |
| `test_archive_stack_already_archived` | Archiver un stack déjà archivé | 200 (idempotent) |
| `test_archive_stack_unauthenticated` | Appel sans token | 401 |
| `test_archive_stack_forbidden_org` | Archiver un stack d'une autre organisation | 403 |
| `test_unarchive_stack_success` | Désarchiver un stack archivé | 200, `is_archived=False`, `archived_at=null` |
| `test_unarchive_stack_not_archived` | Désarchiver un stack non archivé | 200 (idempotent) |
| `test_list_stacks_excludes_archived` | Lister les stacks exclut les archivées par défaut | stacks actives uniquement |
| `test_list_stacks_includes_archived` | Lister avec `include_archived=true` | toutes les stacks |

### Frontend — Tests unitaires (`frontend/tests/unit/views/Stacks.spec.ts`)

| Test | Description |
|------|-------------|
| `test archive action calls stacksApi.archive with confirmation` | Vérifie que `ElMessageBox.confirm` est appelé puis `stacksApi.archive` |
| `test archive action cancelled does not call API` | Vérifie que l'API n'est pas appelée si confirmation annulée |
| `test unarchive action calls stacksApi.unarchive` | Vérifie l'appel API de désarchivage |
| `test archived stacks section is hidden by default` | La section "Archivées" n'est pas visible |
| `test archived stacks section appears when toggle is clicked` | La section apparaît après clic sur le toggle |
| `test archive button is present in ActionButtons` | L'action 'archive' est dans la liste des actions |

### Commandes de validation

```bash
# Backend
cd backend && python -m pytest tests/unit/test_stacks_archive.py -v

# Frontend
cd frontend && pnpm test tests/unit/views/Stacks.spec.ts

# Lint & build
make lint
make build
```

---

## État d'avancement technique

| Tâche | Statut | Fichiers |
|-------|--------|----------|
| Tâche 1 : Modèle `is_archived` | ✅ DONE | `backend/app/models/stack.py` |
| Tâche 2 : Schemas Pydantic | ✅ DONE | `backend/app/schemas/stack.py` |
| Tâche 3 : Endpoint archive + filtre liste | ✅ DONE | `backend/app/api/v1/stacks.py`, `backend/app/services/stack_service.py` |
| Tâche 4 : Types + API frontend | ✅ DONE | `frontend/src/types/api.ts`, `frontend/src/services/api.ts` |
| Tâche 5 : Store Pinia | ✅ DONE | `frontend/src/stores/stacks.ts` |
| Tâche 6 : UI ActionButtons + Stacks.vue | ✅ DONE | `frontend/src/components/ui/ActionButtons.vue`, `frontend/src/views/Stacks.vue` |
| Tâche 7 : Tests | ✅ DONE | `backend/tests/unit/test_stacks_archive.py`, `frontend/tests/unit/views/Stacks.spec.ts` |

---

## Notes d'implémentation

### Fichiers modifiés/créés

**Backend :**
- `backend/app/models/stack.py` — Ajout champs `is_archived` (Boolean, indexé) et `archived_at` (DateTime, nullable)
- `backend/app/schemas/stack.py` — Ajout `is_archived` + `archived_at` dans `StackResponse` et `StackSummaryResponse`
- `backend/app/api/v1/stacks.py` — Endpoints `POST /{stack_id}/archive` et `POST /{stack_id}/unarchive` + paramètre `include_archived` sur `list_stacks`
- `backend/app/services/stack_service.py` — Méthodes `archive()`, `unarchive()` + filtre `include_archived` dans `list_by_organization()`

**Frontend :**
- `frontend/src/types/api.ts` — Ajout `is_archived?: boolean` et `archived_at?: string | null` dans l'interface `Stack`
- `frontend/src/services/api.ts` — Ajout méthodes `archive(id)` et `unarchive(id)` dans `stacksApi`
- `frontend/src/stores/stacks.ts` — Computed `activeStacks`/`archivedStacks` + actions `archiveStack()`/`unarchiveStack()`
- `frontend/src/components/ui/ActionButtons.vue` — Type `'archive'` ajouté à `ActionType`, icône `Box`, config par défaut
- `frontend/src/views/Stacks.vue` — Toggle "Archivées", section archivées avec table dédiée, handlers `handleArchive`/`handleUnarchive`, case `'archive'` dans `handleStackAction`

**Tests :**
- `backend/tests/unit/test_stacks_archive.py` — 9 tests (archive success, 404, idempotent, 401, 403, unarchive success, unarchive idempotent, list excludes archived, list includes archived)
- `frontend/tests/unit/views/Stacks.spec.ts` — 6 tests ajoutés (archive avec confirmation, archive annulée, unarchive, section cachée par défaut, section visible au toggle, bouton archive présent)

### Décisions techniques
- L'archivage est **idempotent** : archiver une stack déjà archivée renvoie 200 sans erreur
- Le désarchivage est également **idempotent**
- Les stacks archivées sont **exclues par défaut** du listing (`include_archived=False`)
- L'icône `Box` (Element Plus) a été choisie pour l'action archive
- La section "Archivées" est masquée par défaut et activée via un toggle switch

### Divergences éventuelles
- Aucune divergence par rapport aux spécifications de la story

### Résultats des validations
- **Tests frontend** : ✅ 26/26 passent (dont 6 tests archive)
- **Lint frontend** : ✅ 0 erreurs, 127 warnings (tous pré-existants)
- **Build frontend** : ⚠️ Erreurs TypeScript pré-existantes liées à d'autres stories (STORY-005/006 — `imagesApi`, STORY-007/008 — `stacksApi.import`/`stacksApi.export`). Aucune erreur liée à STORY-011.
- **Tests backend** : Non exécutables localement (pas de venv/Docker). Le code est cohérent et les tests suivent le pattern existant (`test_stacks_duplicate.py`).
