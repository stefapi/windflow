# STORY-036 : Tests manquants — STORY-004 StackActionsBar

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Tests
**Priorité :** Moyenne

## Description
Écrire les tests unitaires manquants pour la STORY-004 (StackActionsBar) : tests backend (`test_stack_actions.py`) et tests frontend (`StackActionsBar.spec.ts`).

## Contexte technique

### Comportement actuel
- La STORY-004 (Actions globales de stack) a été implémentée sans tests dédiés
- Le critère d'acceptation AC 5 (tests) n'est pas satisfait
- `backend/tests/unit/test_stack_actions.py` n'existe pas
- `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` n'existe pas

### Couches impactées
- **Backend** : Tests unitaires des endpoints `POST /stacks/{id}/start`, `POST /stacks/{id}/stop`, `POST /stacks/{id}/redeploy`
- **Frontend** : Tests unitaires du composant `StackActionsBar.vue`

### Fichiers de référence (patterns)
- **Backend** : `backend/tests/unit/test_stacks_archive.py` — pattern de tests d'endpoint stack avec classes (`TestArchiveStack`), fixtures `authenticated_client`, `test_stack`, `second_organization`, vérifications 401/403/404
- **Frontend** : `frontend/tests/unit/views/ContainerDetail.spec.ts` — pattern de mock des stores Pinia, API services, Element Plus, `vi.mock()` des composables

### Endpoints testés
| Endpoint | Méthode | Handler | Schéma réponse |
|----------|---------|---------|----------------|
| `/api/v1/stacks/{id}/start` | POST | `start_stack()` | `StackActionResponse` |
| `/api/v1/stacks/{id}/stop` | POST | `stop_stack()` | `StackActionResponse` |
| `/api/v1/stacks/{id}/redeploy` | POST | `redeploy_stack()` | `StackRedeployResponse` |

### Points d'attention technique
- Les 3 endpoints utilisent le helper `_get_stack_and_containers()` qui instancie `DockerClientService()` — **nécessite un mock** de `DockerClientService` pour les tests unitaires
- Le helper vérifie : existence stack (404), appartenance org (403), disponibilité Docker (503)
- `StackRedeployRequest` accepte `strategy` : `"stop_start"` (défaut) ou `"rolling"`
- Le composant frontend utilise `ElMessageBox.confirm` pour les confirmations et `ElMessage` pour les notifications — **nécessite un mock**

### Exigences sécurité identifiées
- **Auth** : oui — `get_current_active_user` requis sur les 3 endpoints
- **RBAC** : vérification `stack.organization_id != current_user.organization_id` → 403
- **Validation** : `strategy` du `StackRedeployRequest` (valeurs acceptées : `stop_start`, `rolling`)
- **Exposition données sensibles** : aucune — `StackActionResponse` ne contient que `success`, `message`, `stack_id`, `stack_name`, `affected_services`, `action`
- **Audit** : déjà loggé avec `correlation_id` + `stack_id` dans chaque endpoint

## Critères d'acceptation (AC)
- [x] AC 1 : `backend/tests/unit/test_stack_actions.py` créé avec au moins 7 tests couvrant les actions start/stop/redeploy
- [x] AC 2 : `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` créé avec au moins 6 tests
- [x] AC 3 : Tous les nouveaux tests passent
- [x] AC 4 : La STORY-004 AC 5 est satisfaite

## Tâches d'implémentation détaillées

### Tâche 1 : Tests backend — Stack Actions (start/stop/redeploy)
**Objectif :** Créer le fichier de tests unitaires backend couvrant les 3 endpoints d'actions de stack avec cas nominaux, erreurs et sécurité.
**Fichiers :**
- `backend/tests/unit/test_stack_actions.py` — Créer — Nouveau fichier de tests (pattern : `test_stacks_archive.py`). Structurer en 3 classes :
  - `TestStartStack` — tests pour `POST /api/v1/stacks/{id}/start`
  - `TestStopStack` — tests pour `POST /api/v1/stacks/{id}/stop`
  - `TestRedeployStack` — tests pour `POST /api/v1/stacks/{id}/redeploy`
  
  Fixtures nécessaires :
  - Réutiliser `authenticated_client`, `test_stack`, `db_session`, `client` du `conftest.py`
  - Créer une fixture `second_organization` (pattern : `test_stacks_archive.py` ligne 44)
  - Créer un mock `patch("backend.app.api.v1.stacks.DockerClientService")` pour simuler Docker (retourner des containers avec labels `windflow.stack_id`)
  
  Dépendances à mocker :
  - `DockerClientService` → `AsyncMock` avec méthodes `ping()`, `list_containers()`, `start_container()`, `stop_container()`, `close()`
  - Container mock : objet avec attributs `id`, `name`, `state`, `labels` (dont `windflow.stack_id`)

**Exigences sécurité :** Tests 401 (sans token) et 403 (stack d'une autre org) obligatoires pour chaque endpoint.
**Dépend de :** Aucune

### Tâche 2 : Tests frontend — Composant StackActionsBar
**Objectif :** Créer le fichier de tests unitaires frontend couvrant le rendu, les interactions et les états du composant `StackActionsBar.vue`.
**Fichiers :**
- `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` — Créer — Nouveau fichier de tests (pattern : `ContainerDetail.spec.ts`). Structurer en `describe('StackActionsBar')` avec sous-blocs :
  - `describe('rendu')` — affichage des boutons, status tag, services count
  - `describe('interactions')` — clics start/stop/redeploy, confirmation dialog
  - `describe('états')` — loading, disabled, allRunning, allStopped
  - `describe('dialog redeploy')` — ouverture, sélection strategy, exécution
  
  Mocks nécessaires :
  - `vi.mock('@/services/api')` → `stacksApi.start/stop/redeploy` en `vi.fn()`
  - `vi.mock('element-plus')` → `ElMessageBox.confirm` (résoudre pour OK, rejeter pour Annuler), `ElMessage.success/warning/error`
  - Props type `StackWithServices` : créer un mock avec `{ id, name, status, services_running, services_total }`

**Exigences sécurité :** Aucune exigence spécifique (composant de présentation, pas d'accès direct aux données sensibles).
**Dépend de :** Aucune

### Tâche 3 : Validation — Exécuter les tests et vérifier le passage
**Objectif :** Lancer les tests backend et frontend pour vérifier que tous passent, et s'assurer que le build/lint est OK.
**Fichiers :**
- Aucun fichier à créer/modifier — exécution uniquement
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1, Tâche 2

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend — `backend/tests/unit/test_stack_actions.py`

**Classe `TestStartStack` :**
- `test_start_stack_success` — cas nominal : démarre les containers d'une stack existante → 200, `success=True`, `action="start"`, `affected_services > 0`
- `test_start_stack_no_containers` — cas nominal : stack sans containers Docker → 200, `success=True`, `affected_services=0`, message "Aucun container trouvé"
- `test_start_stack_partial_error` — cas d'erreur : un container échoue au démarrage → 200, `success=False`, message contient l'erreur
- `test_start_stack_not_found` — cas d'erreur : stack inexistante → 404
- `test_start_stack_unauthenticated` — **sécurité** : appel sans token → 401
- `test_start_stack_forbidden_org` — **sécurité** : stack d'une autre organisation → 403
- `test_start_stack_docker_unavailable` — cas d'erreur : Docker indisponible → 503

**Classe `TestStopStack` :**
- `test_stop_stack_success` — cas nominal : arrête les containers running → 200, `success=True`, `action="stop"`
- `test_stop_stack_no_containers` — cas nominal : stack sans containers → 200, `affected_services=0`
- `test_stop_stack_partial_error` — cas d'erreur : un container échoue à l'arrêt → 200, `success=False`
- `test_stop_stack_not_found` — cas d'erreur : stack inexistante → 404
- `test_stop_stack_unauthenticated` — **sécurité** : appel sans token → 401
- `test_stop_stack_forbidden_org` — **sécurité** : stack d'une autre org → 403

**Classe `TestRedeployStack` :**
- `test_redeploy_stack_stop_start` — cas nominal : stratégie `stop_start` (défaut) → 200, `success=True`, `action="redeploy"`, `strategy="stop_start"`
- `test_redeploy_stack_rolling` — cas nominal : stratégie `rolling` → 200, `affected_services` correct
- `test_redeploy_stack_no_containers` — cas nominal : stack sans containers → 200, `affected_services=0`
- `test_redeploy_stack_not_found` — cas d'erreur : stack inexistante → 404
- `test_redeploy_stack_unauthenticated` — **sécurité** : appel sans token → 401
- `test_redeploy_stack_forbidden_org` — **sécurité** : stack d'une autre org → 403

### Unitaires Frontend — `frontend/tests/unit/components/compute/StackActionsBar.spec.ts`

**`describe('rendu')` :**
- `affiche le nom de la stack` — vérifie `stack.name` présent dans le texte
- `affiche le tag de status avec la bonne couleur` — vérifie `el-tag` avec type `success`/`warning`/`danger` selon `stack.status`
- `affiche le compteur de services` — vérifie "X/Y services" présent
- `affiche les 3 boutons d'action` — vérifie présence des boutons "Démarrer", "Arrêter", "Redéployer"

**`describe('états des boutons')` :**
- `désactive le bouton Démarrer si tous les services sont running` — `allRunning=true` → bouton Start disabled
- `désactive le bouton Arrêter si tous les services sont stopped` — `allStopped=true` → bouton Stop disabled
- `désactive tous les boutons pendant le loading` — `loading=true` → tous en état loading

**`describe('interactions')` :**
- `handleStart appelle stacksApi.start et émet action-completed` — mock `ElMessageBox.confirm` résolu, vérifie appel API + emit
- `handleStart annule si l'utilisateur refuse la confirmation` — mock `ElMessageBox.confirm` rejeté, vérifie aucun appel API
- `handleStop appelle stacksApi.stop et émet action-completed` — même pattern que start
- `handleRedeploy ouvre le dialog puis appelle stacksApi.redeploy` — vérifie ouverture dialog, sélection strategy, appel API

**`describe('dialog de redéploiement')` :**
- `affiche les 2 options de stratégie (stop_start et rolling)` — vérifie les radio buttons
- `appelle stacksApi.redeploy avec la stratégie sélectionnée` — sélectionne "rolling", vérifie l'appel avec `{ strategy: 'rolling' }`

### Commandes de validation
```bash
# Backend
poetry run pytest backend/tests/unit/test_stack_actions.py -v

# Frontend
cd frontend && pnpm test -- tests/unit/components/compute/StackActionsBar

# Build & lint
cd frontend && pnpm build && pnpm lint
```

## État d'avancement technique
- [x] Tâche 1 : Tests backend — Stack Actions (start/stop/redeploy)
- [x] Tâche 2 : Tests frontend — Composant StackActionsBar
- [x] Tâche 3 : Validation — Exécuter les tests et vérifier le passage
- [x] Build & lint OK

## Notes d'implémentation

### Fichiers créés
- `backend/tests/unit/test_stack_actions.py` — 19 tests (3 classes : TestStartStack 7 tests, TestStopStack 6 tests, TestRedeployStack 6 tests)
- `frontend/tests/unit/components/compute/StackActionsBar.spec.ts` — 15 tests (4 describe blocks : rendu 6, états des boutons 3, interactions 4, dialog redéploiement 2)

### Décisions techniques
- **Backend** : Mock de `DockerClientService` via `patch("app.api.v1.stacks.DockerClientService")` avec `AsyncMock`. Helper `_make_docker_mock()` pour configurer facilement les retours (containers, ping, start/stop side effects). Classe `MockContainer` pour simuler les containers Docker avec labels `windflow.stack_id`.
- **Frontend** : Mock de `element-plus` (ElMessageBox.confirm, ElMessage.success/warning/error) et `@/services/api` (stacksApi.start/stop/redeploy). Stubs minimaux pour les composants Element Plus (el-button, el-tag, el-dialog, el-radio-group, el-radio).
- **Correction** : Les assertions `disabled="true"` ont été corrigées en `toBeDefined()` car Vue rend les attributs booléens comme `disabled=""` (chaîne vide) et non `disabled="true"`.

### Résultats des tests
- **Backend** : 19/19 passed (3.26s)
- **Frontend** : 15/15 passed (854ms)
- **Lint backend** (`ruff check`) : All checks passed sur le fichier de test (29 erreurs préexistantes dans `app/`, non liées)
- **Lint frontend** (`pnpm lint`) : 0 errors, 128 warnings (tous préexistants, aucun dans le fichier de test)

### Divergences
- Aucune divergence par rapport aux spécifications de la story.
