# STORY-122.2 : Application RBAC au module Docker — 35 endpoints

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les 35 endpoints du module Docker ([`docker.py`](../../backend/app/api/v1/docker.py)) soient protégés par `require_role(...)` conformément à la matrice spec 08, afin qu'un Viewer ne puisse plus exécuter les actions destructrices (suppression de conteneurs, prune volumes/images, etc.) aujourd'hui ouvertes à tout utilisateur authentifié. **Aucune suppression d'endpoint** (garde-fou §2.G du plan : le RBAC s'applique par-dessus le module existant).

## Critères d'acceptation (AC)

- [x] AC 2 (volet Docker) : Tous les endpoints Docker sont protégés par `require_role(...)` conformément à la matrice spec 08 ; vérifié par une matrice rôle×endpoint représentative : viewer → `403` sur `DELETE /docker/containers/{id}` et sur les POST/PUT/DELETE de gestion ; operator → `200` sur les actions opérationnelles et `403` sur la gestion ; admin → gestion `200` dans son organisation.
- [x] AC 5 (échantillon Docker) : Tests de sécurité obligatoires écrits et passants : `401` sans token, `403` rôle insuffisant — sur un échantillon du router ; non-régression : aucun endpoint Docker supprimé (count inchangé = 35).

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — inventaire des 35 routes vérifié par grep.

**Couches impactées :** Backend uniquement — router Docker + tests. Aucun schéma/service.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice : Apps (Lister/Logs = tous ; Start/Stop/Restart/Console = Operator+ ; Créer/Supprimer/Configurer = Admin+), Volumes & networks (Lister/Inspecter + Volume Browser lecture = tous ; Volume Browser écriture = Operator+ ; Créer/Supprimer/Prune = Admin+), Machines (Console = Operator+), Système (paramètres = Super Admin) ;
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité du Docker socket : « un Viewer ne peut pas démarrer un container ».

**Inventaire vérifié des 35 routes de [`docker.py`](../../backend/app/api/v1/docker.py) et rôles minimum cibles (matrice spec 08) :**

| # | Route (lignes @router) | Verbe | Rôle min | Catégorie matrice |
|---|------------------------|-------|----------|-------------------|
| 1 | `/containers` (l. 80) | GET | viewer | Lister Apps |
| 2 | `/containers/{id}` (l. 143) | GET | viewer | Inspecter |
| 3 | `/containers` (l. 204) | POST | admin | Créer App |
| 4 | `/containers/batch/start` (l. 288) | POST | operator | Start |
| 5 | `/containers/batch/stop` (l. 348) | POST | operator | Stop |
| 6 | `/containers/{id}/start` (l. 408) | POST | operator | Start |
| 7 | `/containers/{id}/stop` (l. 455) | POST | operator | Stop |
| 8 | `/containers/{id}/restart` (l. 503) | POST | operator | Restart |
| 9 | `/containers/{id}/pause` (l. 547) | POST | operator | Opération |
| 10 | `/containers/{id}/unpause` (l. 590) | POST | operator | Opération |
| 11 | `/containers/{id}` (l. 633) | DELETE | admin | Supprimer App |
| 12 | `/containers/{id}/recreate` (l. 678) | POST | admin | Configurer (recréation) |
| 13 | `/containers/{id}/restart-policy` (l. 779) | PATCH | admin | Configurer |
| 14 | `/containers/{id}/resources` (l. 831) | PATCH | admin | Configurer (hardware) |
| 15 | `/containers/{id}/rename` (l. 887) | POST | admin | Configurer |
| 16 | `/containers/{id}/networks/connect` (l. 938) | POST | admin | Networks créer/rattacher |
| 17 | `/containers/{id}/networks/disconnect` (l. 994) | POST | admin | Networks détacher |
| 18 | `/containers/{id}/promote` (l. 1050) | POST | admin | Créer (stack depuis container) |
| 19 | `/containers/{id}/shells` (l. 1248) | GET | operator | Console (prérequis exec) |
| 20 | `/containers/{id}/stats` (l. 1305) | GET | viewer | Inspecter/métriques |
| 21 | `/containers/{id}/top` (l. 1358) | GET | viewer | Inspecter |
| 22 | `/containers/{id}/logs` (l. 1461) | GET | viewer | Logs |
| 23 | `/images` (l. 1526) | GET | viewer | Lister |
| 24 | `/images/{id}` (l. 1590) | GET | viewer | Inspecter |
| 25 | `/images/pull` (l. 1665) | POST | admin | Gestion images (téléchargement) |
| 26 | `/images/{id}` (l. 1716) | DELETE | admin | Supprimer |
| 27 | `/images/load` (l. 1762) | POST | admin | Import (écriture disque) |
| 28 | `/images/{id}/save` (l. 1817) | GET | viewer | Lecture/export |
| 29 | `/volumes` (l. 1880) | GET | viewer | Lister volumes |
| 30 | `/volumes` (l. 1929) | POST | admin | Créer volume |
| 31 | `/volumes/{name}` (l. 1986) | DELETE | admin | Supprimer volume (prune-like) |
| 32 | `/networks` (l. 2036) | GET | viewer | Lister networks |
| 33 | `/system/info` (l. 2094) | GET | viewer | Lecture système |
| 34 | `/system/version` (l. 2142) | GET | viewer | Lecture système |
| 35 | `/system/ping` (l. 2183) | GET | viewer | Lecture système |

> Arbitrage matrice : `shells` (l. 1248) listé Operator+ car préalable à la console/exec (spec 08 : Console = Operator) ; `promote` = création de stack → Admin ; `images/save` = lecture/export → Viewer. Toute divergence doit être signalée avant implémentation (règle 01 §5.3).

**Fichiers de référence (patterns vérifiés) :**
- Router Docker — [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) : toutes les routes utilisent déjà `current_user: User = Depends(get_current_active_user)` (l. 95, 154, 216…) + `conditional_rate_limiter` ;
- Dépendances à consommer — [`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py) (créé par STORY-122.1) : `require_operator`, `require_admin` (prédéfinies) ou `require_role("...")` ;
- Tests API sécurité — pattern [`backend/tests/unit/test_api/test_deployments.py`](../../backend/tests/unit/test_api/test_deployments.py) + fixtures conftest.

**Exigences sécurité identifiées (Phase 2.6) :**
- Auth : oui — 401 sans token (déjà effectif via la chaîne `get_current_active_user` sous-jacente à `require_role`) ;
- RBAC : mapping ci-dessus — Docker local = ressources hors organisation : le rôle **global** s'applique (docker socket partagé de l'instance) ;
- Validation : inchangée (aucun input nouveau) ;
- Exposition : aucune modification des schémas de réponse ;
- Audit : non requis en plus (spec 08 : audit des modifications de **permissions** ; l'audit des actions Docker critiques = STORY-125).

## Dépendances

- STORY-122.1 (socle `require_role` + `AuthorizationService`) — prérequis absolu.
- Indépendante de 122.3-122.7 (peut être menée en parallèle).

## Tâches d'implémentation détaillées

### Tâche 1 : Protéger les 35 routes de `docker.py` selon la matrice
**Objectif :** Remplacer systématiquement `Depends(get_current_active_user)` par la dépendance `require_role` correspondant au rôle minimum de la matrice ci-dessus.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Pour chacune des 35 routes (cf. inventaire ligne par ligne) :
  - Routes viewer (n° 1, 2, 20, 21, 22, 23, 24, 28, 29, 32, 33, 34, 35) : conserver `Depends(get_current_active_user)` (sémantiquement équivalent à `require_role("viewer")` — documenté dans `auth/rbac.py`) **ou** remplacer par `require_viewer` pour l'uniformité — choisir l'option remplacée systématiquement par `require_viewer` pour la lisibilité de l'audit ;
  - Routes operator (n° 4-10, 19) : `current_user: User = Depends(require_operator)` ;
  - Routes admin (n° 3, 11-18, 25, 26, 27, 30, 31) : `current_user: User = Depends(require_admin)` ;
  - Import à ajouter : `from ...auth.rbac import require_admin, require_operator, require_viewer` (retirer `get_current_active_user` de l'import s'il n'est plus utilisé) ;
  - Mettre à jour les docstrings/descriptions OpenAPI : section `## Access Control` mentionnant le rôle minimum requis (pattern descriptions organizations.py) ;
  - **Interdits absolus** : supprimer/renommer une route, modifier un path, un response_model ou un status code (garde-fou §2.G + non-régression frontend/CLI).
**Exigences sécurité :** Chaque modification est exactement la dépendance — aucun autre changement comportemental ; 401/403 gérés par le socle.
**Dépend de :** STORY-122.1

### Tâche 2 : Tests matrice Docker (sécurité + non-régression)
**Objectif :** Vérifier le mapping par un échantillon représentatif par catégorie + l'intégrité du router (35 routes inchangées).
**Fichiers :**
- `backend/tests/unit/test_api/test_docker_rbac.py` — Créer — Fixture : clients par rôle (viewer, operator, admin — cf. Tâche 3 de STORY-122.7 pour les fixtures conftest réutilisables ; en attendant, construire localement via login + association `UserOrganization` du rôle voulu, pattern `test_user`). Docker client mocké (patch `get_docker_client` — les assertions portent sur le **statut HTTP avant** l'appel Docker : 403 court-circuite avant toute E/S Docker). Tests :
  - `test_viewer_403_delete_container` — **AC critique** : `DELETE /api/v1/docker/containers/{id}` avec viewer → 403 ;
  - `test_viewer_403_create_container` / `test_viewer_403_pull_image` / `test_viewer_403_delete_volume` — POST/DELETE gestion → 403 ;
  - `test_viewer_200_list_containers` / `test_viewer_200_container_logs` / `test_viewer_200_system_ping` — lectures → 200 (Docker mocké) ;
  - `test_operator_200_start_stop_restart` — actions opérationnelles → 200 (échantillon : start l. 408, batch/start l. 288) ;
  - `test_operator_403_create_container` / `test_operator_403_delete_container` / `test_operator_403_patch_resources` — gestion → 403 ;
  - `test_admin_200_create_container` / `test_admin_200_delete_container` / `test_admin_200_delete_volume` — gestion → 200/204 (Docker mocké) ;
  - `test_no_token_401_sample` — sans Authorization : 401 sur `GET /docker/containers`, `POST /docker/containers/{id}/start`, `DELETE /docker/containers/{id}` ;
  - `test_superuser_passes_all_categories` — superuser → 200 partout (bypass) ;
  - `test_docker_router_route_count_unchanged` — **non-régression §2.G** : introspection `app.routes` → compter les routes préfixe `/api/v1/docker/` == 35 ;
  - `test_no_endpoint_removed_paths_stable` — l'ensemble des paths Docker correspond à la liste attendue (comparaison frozenset).
**Exigences sécurité :** 401/403 par rôle et par catégorie — échantillon par famille matricielle (lecture/opération/gestion).
**Dépend de :** Tâche 1

## Tests à écrire

> Détail exhaustif en Tâche 2. Récapitulatif :

### Unitaires Backend
- `backend/tests/unit/test_api/test_docker_rbac.py`
  - Matrice viewer/operator/admin × {lecture, opération, gestion} (échantillon par catégorie)
  - `test_viewer_403_delete_container` — **AC 2 littéral** (viewer 403 sur `DELETE /docker/containers/{id}`)
  - 401 sans token (échantillon 3 routes)
  - Non-régression : nombre de routes == 35, paths stables

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_docker_rbac.py -v
poetry run pytest backend/tests/unit/test_api/ -k docker -v  # non-régression tests Docker existants
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Matrice `require_role` sur les 35 routes docker.py
- [x] Tâche 2 : Tests matrice Docker (RBAC + non-régression 35 routes)
- [x] Réparation non-régression : 110 tests Docker existants cassés par la bascule `require_*` (délégation dans les mini-apps)
- [x] Lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-09

### Fichiers modifiés/créés
- `backend/tests/unit/test_api/test_docker_rbac.py` : **créé** — 18 tests matrice RBAC Docker (viewer/operator/admin × lecture/opération/gestion, superuser bypass, 401 échantillon 3 catégories, non-régression 35 opérations via introspection OpenAPI + frozenset des paths)
- `backend/tests/unit/test_container_promote.py` : `promote` = Admin désormais → bascule `authenticated_client` → `admin_client` + fixture `_jwt_mode` (neutralise `DISABLE_AUTH=true` du `.env` local pour le test 401)
- 13 fichiers `backend/tests/unit/test_docker/test_*.py` : réparation de la régression induite par la Tâche 1 — les mini-apps surchargeaient `get_current_active_user` mais les routes consomment désormais `require_viewer/operator/admin` (résolution rôle via `get_db` → `RuntimeError: Database not initialized` sur le singleton). Correctif : override des aliases `require_*` déléguant à `get_current_active_user` (helper `_delegate_rbac_deps` dans les fichiers à tests 401 inline, lambda directe ailleurs) — le RBAC reste couvert de bout en bout par `test_docker_rbac.py`
- `backend/tests/unit/test_docker/test_container_processes.py` : suppression d'une définition dupliquée `_make_mock_user` (F811 pré-existant)

### Décisions techniques
- **Non-régression 35 routes via `app.openapi()`** plutôt que `app.routes` : sur cette version de FastAPI, `app.routes` expose un `_IncludedRouter` lazy (routes imbriquées non aplaties à l'import) — le schéma OpenAPI force la résolution complète des paths
- **Test admin create 201** : le bug pré-existant `response_model=ContainerResponse` vs `ContainerDetailResponse` retourné (documenté dans `test_container_create.py`) impose de ponctuellement neutraliser `route.response_model` **sur le router source avant montage** (`include_router` clone les routes) — mini-app dédiée avec override `get_db` vers la session de test, chaîne JWT → `require_admin` → `AuthorizationService` réelle préservée
- **Délégation `require_*` plutôt que mock DB dans les mini-apps** : conserve la sémantique des tests existants (override mock user pour les nominaux, lambda levante pour les 401) sans introduire une fausse couche de résolution de rôle
- **`_jwt_mode` dans test_docker_rbac.py et test_container_promote.py** : le `.env` de dev local porte `DISABLE_AUTH=true` (auto-login superadmin → 500 sans superadmin en base de test) ; la fixture force `disable_auth=False` pour que les tests 401/403 soient déterministes local comme CI (pattern établi par STORY-122.1)

### Divergences par rapport à l'analyse
- **Tâche 2 (périmètre élargi)** : l'analyse prévoyait uniquement la création de `test_docker_rbac.py`. La bascule `require_*` (Tâche 1, réalisée avant cette session) avait cassé **110 tests existants** (13 fichiers mini-apps `test_docker/` + 7 tests promote) — la DoD « pas de régression sur les tests existants » imposait leur réparation dans cette story (cause racine : `require_role` résout le rôle via `Depends(get_db)`, absente des mini-apps sans DB)

### Difficultés rencontrées
- Échec initial du test `admin create` : la mutation `route.response_model = None` sur `app` réelle ne prend pas effet (routes clonées au montage) → contourné par mini-app assemblée après mutation
- FastAPI de `.venv-test` n'expose pas `APIRoute` à la racine (`ImportError`) → import via `fastapi.routing`
- 24 erreurs mypy pré-existantes sur `app/` (baseline inchangée avant/après — vérifié par stash) : hors périmètre, non corrigées

### Tests ajoutés
- `backend/tests/unit/test_api/test_docker_rbac.py` : 18 tests — matrice complète {viewer, operator, admin, superuser} × {lecture, opération, gestion} avec Docker mocké (assertions sur le statut HTTP **avant** toute E/S Docker pour les 403), 401 sur échantillon 3 catégories, garde-fou §2.G (35 opérations, frozenset paths stables)
- Validation : `pytest backend/tests/unit/` → **1172/1172 passent** (dont 387 Docker/promote/RBAC) ; black/isort/flake8 propres sur les fichiers touchés ; mypy `test_docker_rbac.py` Success, `app/` baseline 24 erreurs inchangée
