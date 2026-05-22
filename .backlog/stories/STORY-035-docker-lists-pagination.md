# STORY-035 : Pagination des listes Docker

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration
**Priorité :** Moyenne

## Description
Ajouter la pagination (paramètres `skip` et `limit`) sur les endpoints de listage Docker : containers, images, volumes et réseaux.

## Contexte technique

**Couches impactées :** Backend uniquement (les paramètres ont des valeurs par défaut, le frontend existant continue de fonctionner sans modification)

### Comportement actuel
- Les endpoints de listage Docker retournent l'intégralité des résultats sans pagination
- Cela peut causer des problèmes de performance avec un grand nombre d'objets Docker

### Comportement attendu
- Les endpoints de listage acceptent des paramètres de pagination `skip` et `limit`
- Les réponses sont paginées correctement
- Des valeurs par défaut raisonnables sont appliquées

### Fichiers de référence (patterns)
- Pagination existante : `backend/app/api/v1/admin/stacks_management.py` (lignes 327-329) — pattern `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=1000)`
- Pattern de test endpoint Docker : `backend/tests/unit/test_docker/test_images_list_in_use.py` — fixtures `app`, `_make_mock_user`, mock `get_docker_client`

### Endpoints impactés
| Endpoint | Fichier:Ligne | Paramètres actuels |
|----------|---------------|--------------------|
| `GET /docker/containers` | `docker.py:77` | `all: bool = True` |
| `GET /docker/images` | `docker.py:1478` | `all: bool = False` |
| `GET /docker/volumes` | `docker.py:1822` | Aucun param query |
| `GET /docker/networks` | `docker.py:1967` | Aucun param query |

### Exigences sécurité identifiées
- Auth : oui — `get_current_active_user` déjà en place sur les 4 endpoints
- RBAC : aucun rôle spécifique requis (lecture seule, tous utilisateurs authentifiés)
- Validation : paramètres entiers bornés par FastAPI `Query(ge=, le=)` — pas de risque d'injection
- Exposition : aucun champ sensible dans les réponses
- Audit : non requis (lecture seule)

## Critères d'acceptation (AC)
- [x] AC 1 : `GET /docker/containers` accepte les paramètres `skip` (défaut 0) et `limit` (défaut 50)
- [x] AC 2 : `GET /docker/images` accepte les paramètres `skip` et `limit`
- [x] AC 3 : `GET /docker/volumes` accepte les paramètres `skip` et `limit`
- [x] AC 4 : `GET /docker/networks` accepte les paramètres `skip` et `limit`
- [x] AC 5 : Les réponses sont paginées correctement
- [x] AC 6 : Tests unitaires pour la pagination
- [x] AC 7 : Build, lint et tests passent

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter les paramètres `skip`/`limit` aux 4 endpoints de listage Docker
**Objectif :** Ajouter les paramètres de pagination `skip` (défaut 0) et `limit` (défaut 50) aux endpoints `list_containers`, `list_images`, `list_volumes` et `list_networks`, et appliquer le slicing sur les résultats.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Pour chaque endpoint de listage :
  1. Ajouter l'import `Query` depuis `fastapi` (déjà présent via `APIRouter, Depends, ...` — vérifier et ajouter `Query` si manquant)
  2. **`list_containers` (ligne 77)** : ajouter les paramètres `skip: int = Query(0, ge=0, description="Nombre d'éléments à sauter")` et `limit: int = Query(50, ge=1, le=100, description="Nombre maximal d'éléments à retourner")` dans la signature. Appliquer `return [...][skip : skip + limit]` sur la liste construite.
  3. **`list_images` (ligne 1478)** : même ajout de `skip`/`limit`. Appliquer le slicing sur la liste finale `[img for img in images]` → `[...][skip : skip + limit]`.
  4. **`list_volumes` (ligne 1822)** : même ajout de `skip`/`limit`. Appliquer le slicing sur la liste `[VolumeResponse(...) for v in volumes]` → `[...][skip : skip + limit]`.
  5. **`list_networks` (ligne 1967)** : même ajout de `skip`/`limit`. Appliquer le slicing sur la liste `[NetworkResponse(...) for n in networks]` → `[...][skip : skip + limit]`.
  6. Mettre à jour les `description` des endpoints pour documenter les paramètres de pagination.
**Pattern de référence :** `backend/app/api/v1/admin/stacks_management.py` lignes 327-329
**Exigences sécurité :** Aucune exigence spécifique — `get_current_active_user` déjà en place, paramètres bornés par FastAPI Query
**Dépend de :** Aucune

### Tâche 2 : Écrire les tests de pagination
**Objectif :** Créer un fichier de test dédié validant la pagination sur les 4 endpoints (cas nominaux, edge cases, sécurité).
**Fichiers :**
- `backend/tests/unit/test_docker/test_docker_pagination.py` — Créer — Nouveau fichier de test (pattern : `backend/tests/unit/test_docker/test_images_list_in_use.py`). Créer une classe de test par endpoint avec :
  - Fixtures : `app` (FastAPI de test avec router et override `get_current_active_user`), mock client Docker (`AsyncMock`)
  - Helper : fonction pour générer N mocks d'items (containers, images, volumes, networks)
  - **Classe `TestContainerPagination`** :
    - `test_default_pagination_returns_50_max` — 60 containers mockés, `GET /docker/containers` sans params → 50 résultats
    - `test_skip_parameter_works` — `GET /docker/containers?skip=10` → 50 résultats à partir du 11ème
    - `test_limit_parameter_works` — `GET /docker/containers?limit=5` → 5 résultats
    - `test_skip_and_limit_combined` — `GET /docker/containers?skip=5&limit=10` → 10 résultats à partir du 6ème
    - `test_skip_beyond_list_returns_empty` — `GET /docker/containers?skip=999` → liste vide
    - `test_limit_1_returns_single` — `GET /docker/containers?limit=1` → 1 résultat
    - `test_pagination_returns_401_without_token` — **sécurité** : sans auth → 401
    - `test_invalid_skip_negative_returns_422` — `GET /docker/containers?skip=-1` → 422
    - `test_invalid_limit_zero_returns_422` — `GET /docker/containers?limit=0` → 422
    - `test_invalid_limit_over_100_returns_422` — `GET /docker/containers?limit=101` → 422
  - **Classe `TestImagePagination`** :
    - `test_default_pagination_returns_50_max` — même pattern avec images
    - `test_skip_and_limit_combined` — même pattern
    - `test_pagination_returns_401_without_token` — **sécurité**
  - **Classe `TestVolumePagination`** :
    - `test_default_pagination_returns_50_max` — même pattern avec volumes
    - `test_skip_and_limit_combined` — même pattern
    - `test_pagination_returns_401_without_token` — **sécurité**
  - **Classe `TestNetworkPagination`** :
    - `test_default_pagination_returns_50_max` — même pattern avec networks
    - `test_skip_and_limit_combined` — même pattern
    - `test_pagination_returns_401_without_token` — **sécurité**
**Exigences sécurité :** Tests 401 obligatoires pour chaque endpoint
**Dépend de :** Tâche 1

### Tâche 3 : Vérifier build, lint et tests
**Objectif :** S'assurer que l'ensemble du backend passe les checks de qualité (lint, type checking, tests).
**Fichiers :**
- Aucun fichier à modifier — validation uniquement
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend
- `backend/tests/unit/test_docker/test_docker_pagination.py`
  - `test_default_pagination_returns_50_max` — cas nominal : sans paramètres, retourne max 50 éléments (TestContainerPagination)
  - `test_skip_parameter_works` — cas nominal : skip=10 saute les 10 premiers (TestContainerPagination)
  - `test_limit_parameter_works` — cas nominal : limit=5 retourne exactement 5 éléments (TestContainerPagination)
  - `test_skip_and_limit_combined` — cas nominal : skip+limit combinés correctement (TestContainerPagination)
  - `test_skip_beyond_list_returns_empty` — cas d'erreur : skip > nombre total → liste vide (TestContainerPagination)
  - `test_limit_1_returns_single` — cas nominal : limit=1 retourne exactement 1 élément (TestContainerPagination)
  - `test_pagination_returns_401_without_token` — **sécurité** : accès sans token → 401 (TestContainerPagination)
  - `test_invalid_skip_negative_returns_422` — validation : skip=-1 → 422 (TestContainerPagination)
  - `test_invalid_limit_zero_returns_422` — validation : limit=0 → 422 (TestContainerPagination)
  - `test_invalid_limit_over_100_returns_422` — validation : limit=101 → 422 (TestContainerPagination)
  - `test_default_pagination_returns_50_max` — cas nominal images (TestImagePagination)
  - `test_skip_and_limit_combined` — cas nominal images (TestImagePagination)
  - `test_pagination_returns_401_without_token` — **sécurité** images (TestImagePagination)
  - `test_default_pagination_returns_50_max` — cas nominal volumes (TestVolumePagination)
  - `test_skip_and_limit_combined` — cas nominal volumes (TestVolumePagination)
  - `test_pagination_returns_401_without_token` — **sécurité** volumes (TestVolumePagination)
  - `test_default_pagination_returns_50_max` — cas nominal networks (TestNetworkPagination)
  - `test_skip_and_limit_combined` — cas nominal networks (TestNetworkPagination)
  - `test_pagination_returns_401_without_token` — **sécurité** networks (TestNetworkPagination)

### Commandes de validation
```bash
# Tests unitaires — pagination
poetry run pytest backend/tests/unit/test_docker/test_docker_pagination.py -v

# Tests unitaires — tous les tests Docker
poetry run pytest backend/tests/unit/test_docker/ -v

# Lint backend
make lint-backend

# Type checking
make typecheck-backend
```

---

## État d'avancement technique
- [x] Tâche 1 : Ajouter les paramètres `skip`/`limit` aux 4 endpoints de listage Docker
- [x] Tâche 2 : Écrire les tests de pagination
- [x] Tâche 3 : Vérifier build, lint et tests

---

## Notes d'implémentation

### Fichiers modifiés
- `backend/app/api/v1/docker.py` — Ajout de l'import `Query`, ajout des paramètres `skip` et `limit` aux 4 endpoints (`list_containers`, `list_images`, `list_volumes`, `list_networks`), slicing `[skip:skip+limit]` sur les retours, mise à jour des descriptions d'endpoints

### Fichiers créés
- `backend/tests/unit/test_docker/test_docker_pagination.py` — 19 tests unitaires couvrant la pagination des 4 endpoints

### Décisions techniques
- Paramètres `skip` (défaut 0, ge=0) et `limit` (défaut 50, ge=1, le=100) conformes au pattern existant dans `stacks_management.py`
- Slicing Python natif `[skip:skip+limit]` appliqué après construction de la liste de réponse — simple et efficace
- Les tests 401 utilisent le pattern `_raise_401()` avec un `unauth_app` dédié (conforme au pattern de `test_docker_auth_security.py`)

### Divergences par rapport à l'analyse
- Aucune divergence : implémentation strictement conforme aux tâches pré-analysées

### Tests ajoutés
- **TestContainerPagination** (10 tests) : default 50 max, skip, limit, skip+limit combinés, skip au-delà, limit=1, 401 sécurité, 422 skip négatif, 422 limit=0, 422 limit>100
- **TestImagePagination** (3 tests) : default 50 max, skip+limit combinés, 401 sécurité
- **TestVolumePagination** (3 tests) : default 50 max, skip+limit combinés, 401 sécurité
- **TestNetworkPagination** (3 tests) : default 50 max, skip+limit combinés, 401 sécurité

### Résultats de validation
- **Tests** : 19/19 passés ✅
- **Lint ruff** : All checks passed ✅
- **Mypy** : Success, no issues found ✅
