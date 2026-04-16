# STORY-017 : Détection des shells disponibles dans le terminal

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux que le terminal container détecte automatiquement les shells disponibles afin de me connecter avec le shell le plus adapté plutôt qu'une sélection statique prédéfinie.

## Contexte technique

### Couches impactées
- **Backend** : Endpoint existant à sécuriser (ajout authentification + schéma Pydantic)
- **Frontend** : Type, service API, composant ContainerTerminal.vue

### État actuel du backend
L'endpoint `GET /docker/containers/{container_id}/shells` existe déjà dans [`docker.py`](backend/app/api/v1/docker.py:1064) :
- Service [`TerminalService.detect_shells()`](backend/app/services/terminal_service.py:355) teste 6 shells via `docker exec test -f <path>`
- Dataclass [`ShellInfo`](backend/app/services/terminal_service.py:29) : `path`, `label`, `available`
- Tests backend existants dans [`test_terminal_service.py`](backend/tests/unit/test_docker/test_terminal_service.py:317)
- **⚠️ Faille de sécurité** : L'endpoint n'a PAS de dépendance `get_current_active_user` — accessible sans authentification
- **⚠️ Pas de schéma Pydantic** : Retourne `List[dict]` brut au lieu d'un modèle validé (non conforme `.clinerules/20-architecture-and-api.md`)

### État actuel du frontend
- [`ContainerTerminal.vue`](frontend/src/components/ContainerTerminal.vue:56) : liste statique `PREDEFINED_SHELLS` codée en dur (sh, bash, ash uniquement)
- [`containersApi`](frontend/src/services/api.ts:313) : aucune méthode `getShells`
- [`api.ts`](frontend/src/types/api.ts) : aucun type `ContainerShell`

### Fichiers de référence (patterns)
- Pattern type TypeScript : [`VolumeResponse`](frontend/src/types/api.ts:279) dans `api.ts`
- Pattern service API : [`containersApi.getLogs`](frontend/src/services/api.ts:344) dans `api.ts`
- Pattern schéma Pydantic : [`ContainerProcess`](backend/app/schemas/docker.py) dans `docker.py`
- Pattern endpoint authentifié : [`list_containers`](backend/app/api/v1/docker.py:65) avec `get_current_active_user`
- Pattern test composant : [`ContainerTerminal.spec.ts`](frontend/tests/unit/components/ContainerTerminal.spec.ts)

### Exigences sécurité
- **Authentification** : L'endpoint backend DOIT exiger `get_current_active_user` (actuellement absent)
- **RBAC** : Aucun rôle spécifique requis au-delà de l'authentification (tout utilisateur authentifié peut détecter les shells)
- **Validation des inputs** : Le `container_id` est un paramètre de path utilisé tel quel avec Docker — pas de risque d'injection (Docker API gère la validation)
- **Champs sensibles** : Aucun champ sensible dans la réponse (path, label, available)
- **Logging** : Déjà présent avec correlation_id dans l'endpoint existant
- **Audit** : Pas d'action critique (lecture seule), pas d'audit trail nécessaire

## Critères d'acceptation (AC)
- [x] AC 1 : À l'ouverture du terminal, les shells disponibles sont chargés via `GET /docker/containers/{id}/shells`
- [x] AC 2 : Un dropdown permet de sélectionner le shell parmi ceux détectés (ex: /bin/bash, /bin/sh, /bin/zsh)
- [x] AC 3 : Si aucun shell n'est disponible ou si l'appel échoue, un fallback sur `/bin/sh` est appliqué
- [x] AC 4 : Le type TypeScript `ContainerShell` est défini et `containersApi.getShells` est disponible
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Backend — Ajouter le schéma Pydantic ContainerShellResponse
**Objectif :** Remplacer le retour `List[dict]` brut par un schéma Pydantic validé, conforme aux règles API-first.

| Fichier | Action | Description |
|---------|--------|-------------|
| `backend/app/schemas/docker.py` | Modifier | Ajouter la classe `ContainerShellResponse(BaseModel)` avec champs `path: str`, `label: str`, `available: bool`, descriptions et `ConfigDict` |

**Exigences sécurité :** Aucune (schéma de validation uniquement)
**Dépendances :** Aucune

---

### Tâche 2 : Backend — Sécuriser l'endpoint get_container_shells
**Objectif :** Ajouter l'authentification obligatoire et utiliser le schéma Pydantic dédié.

| Fichier | Action | Description |
|---------|--------|-------------|
| `backend/app/api/v1/docker.py` | Modifier | 1) Ajouter `get_current_active_user` en paramètre de `get_container_shells` 2) Changer `response_model` de `List[dict]` vers `List[ContainerShellResponse]` 3) Importer `ContainerShellResponse` depuis schemas 4) Construire les objets `ContainerShellResponse` au lieu de dicts bruts |

**Exigences sécurité :** `get_current_active_user` obligatoire — cf. `.clinerules/40-security.md`
**Dépendances :** Tâche 1

---

### Tâche 3 : Frontend — Ajouter le type ContainerShell
**Objectif :** Définir le type TypeScript miroir du schéma backend.

| Fichier | Action | Description |
|---------|--------|-------------|
| `frontend/src/types/api.ts` | Modifier | Ajouter `export interface ContainerShell { path: string; label: string; available: boolean }` dans la section Docker Container types |

**Exigences sécurité :** Aucune
**Dépendances :** Aucune

---

### Tâche 4 : Frontend — Ajouter containersApi.getShells
**Objectif :** Exposer la méthode d'appel API pour récupérer les shells d'un container.

| Fichier | Action | Description |
|---------|--------|-------------|
| `frontend/src/services/api.ts` | Modifier | 1) Ajouter `ContainerShell` aux imports depuis `@/types/api` 2) Ajouter `getShells: (id: string) => http.get<ContainerShell[]>(`/docker/containers/${id}/shells`)` dans `containersApi` |

**Exigences sécurité :** Aucune (le token JWT est envoyé automatiquement via l'intercepteur http)
**Dépendances :** Tâche 3

---

### Tâche 5 : Frontend — Modifier ContainerTerminal.vue pour le chargement dynamique
**Objectif :** Remplacer la liste statique `PREDEFINED_SHELLS` par un dropdown alimenté dynamiquement via l'API, avec fallback sur `/bin/sh`.

| Fichier | Action | Description |
|---------|--------|-------------|
| `frontend/src/components/ContainerTerminal.vue` | Modifier | 1) Supprimer la constante `PREDEFINED_SHELLS` 2) Ajouter un ref réactif `availableShells: ref<ContainerShell[]>([])` et `shellsLoading: ref(false)` 3) Créer une fonction `loadShells()` async qui appelle `containersApi.getShells(props.containerId)`, filtre les shells `available === true`, et met à jour `availableShells` 4) En cas d'erreur ou liste vide, fallback sur `[{ path: '/bin/sh', label: 'sh', available: true }]` 5) Appeler `loadShells()` dans `onMounted` 6) Définir `selectedShell` par défaut au premier shell disponible (ou `/bin/sh`) 7) Modifier le template du `<el-select>` pour itérer sur `availableShells` au lieu de `PREDEFINED_SHELLS` 8) Afficher un état loading dans le sélecteur pendant le chargement 9) Importer `ContainerShell` depuis `@/types/api` et `containersApi` depuis `@/services/api` |

**Exigences sécurité :** Aucune
**Dépendances :** Tâche 4

---

### Tâche 6 : Tests — Backend et Frontend
**Objectif :** Couvrir les exigences de sécurité backend et le comportement du composant frontend.

Voir section `## Tests à écrire` ci-dessous pour le détail complet.

**Dépendances :** Tâches 1-5

## Tests à écrire

### Backend — Tests unitaires endpoint shells

| Test | Description | Fichier |
|------|-------------|---------|
| `test_get_container_shells_authenticated` | Cas nominal : retourne la liste des shells avec authentification valide | `backend/tests/unit/test_docker/test_terminal_service.py` (existant, à compléter) |
| `test_get_container_shells_returns_401_without_token` | **Sécurité** : L'endpoint doit refuser l'accès sans token JWT | `backend/tests/unit/test_docker/test_terminal_service.py` |
| `test_get_container_shells_returns_404_for_unknown_container` | Cas d'erreur : container inexistant retourne 404 | `backend/tests/unit/test_docker/test_terminal_service.py` |
| `test_get_container_shells_response_schema` | Validation : la réponse respecte le schéma `ContainerShellResponse` | `backend/tests/unit/test_docker/test_terminal_service.py` |

> **Note :** Les tests `test_detect_shells` et `test_detect_shells_exception_marks_unavailable` existent déjà pour le service. Seuls les tests d'endpoint API (authentification + schéma) sont à ajouter.

### Frontend — Tests unitaires composant ContainerTerminal

| Test | Description | Fichier |
|------|-------------|---------|
| `should load shells on mount` | Cas nominal : `containersApi.getShells` est appelé au montage avec le bon containerId | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |
| `should populate shell dropdown with available shells` | Rendu : le dropdown affiche uniquement les shells où `available === true` | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |
| `should fallback to /bin/sh when API fails` | Cas d'erreur : en cas d'erreur API, le shell par défaut est `/bin/sh` | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |
| `should fallback to /bin/sh when no shells available` | Cas d'erreur : si tous les shells sont indisponibles, fallback `/bin/sh` | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |
| `should auto-select first available shell` | Comportement : le premier shell disponible est pré-sélectionné | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |
| `should show loading state while fetching shells` | Rendu : état loading pendant l'appel API | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |
| `should not expose tokens in DOM` | **Sécurité** : aucun token/secret visible dans le rendu du composant | `frontend/tests/unit/components/ContainerTerminal.spec.ts` |

### Frontend — Tests unitaires service API

| Test | Description | Fichier |
|------|-------------|---------|
| `containersApi.getShells should call correct endpoint` | Vérifie que l'URL appelée est `/docker/containers/{id}/shells` | `frontend/tests/unit/services/api.spec.ts` (ou fichier dédié) |

### Commandes de validation

```bash
# Backend
make test-backend
# ou: pytest backend/tests/unit/test_docker/test_terminal_service.py -v

# Frontend
make test-frontend
# ou: pnpm --filter frontend test

# Lint + typecheck
make lint
make typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Schéma Pydantic `ContainerShellResponse` ajouté dans `backend/app/schemas/docker.py`
- [x] Tâche 2 : Endpoint `get_container_shells` sécurisé avec authentification + schéma Pydantic
- [x] Tâche 3 : Type `ContainerShell` ajouté dans `frontend/src/types/api.ts`
- [x] Tâche 4 : Méthode `containersApi.getShells` ajoutée dans `frontend/src/services/api.ts`
- [x] Tâche 5 : Composant `ContainerTerminal.vue` modifié pour chargement dynamique des shells
- [x] Tâche 6 : Tests backend (auth + schéma) et frontend (chargement, fallback, sécurité) écrits et passent

## Notes d'implémentation

### Fichiers modifiés
- `backend/app/schemas/docker.py` — Ajout de `ContainerShellResponse(BaseModel)` avec champs `path`, `label`, `available`
- `backend/app/api/v1/docker.py` — Import de `ContainerShellResponse`, ajout de `get_current_active_user` sur l'endpoint, remplacement du retour `List[dict]` par `List[ContainerShellResponse]`, ajout de `user_id` dans les logs
- `frontend/src/types/api.ts` — Ajout de `ContainerShell` interface
- `frontend/src/services/api.ts` — Import de `ContainerShell`, ajout de `containersApi.getShells(id)`
- `frontend/src/components/ContainerTerminal.vue` — Suppression de `PREDEFINED_SHELLS`, ajout de `availableShells`, `shellsLoading`, `loadShells()`, template dynamique avec loading state

### Fichiers créés
- `backend/tests/unit/test_docker/test_container_shells.py` — 4 tests endpoint (401, 200 nominal, 404, validation schéma)
- `frontend/tests/unit/components/ContainerTerminalShellLoading.spec.ts` — 7 tests composant (load on mount, available only, fallback error, fallback empty, auto-select, loading state, no tokens in DOM)

### Décisions techniques
- Utilisation de `app.dependency_overrides[get_current_active_user]` pour les tests backend (au lieu de `patch`)
- Polyfill `ResizeObserver` dans les tests frontend (non disponible en jsdom)
- Optional chaining `shells[0]?.path ?? '/bin/sh'` pour satisfaire le strict mode TypeScript

### Résultats de validation
- **Tests backend** : 4/4 passent
- **Tests frontend** : 7/7 passent
- **Build frontend** : Succès (vue-tsc + vite build)
- **Lint frontend** : 0 erreurs, 128 warnings (pré-existants)
