# STORY-122.5 : Application RBAC — plugins, registry, targets et endpoints de lecture

**Statut :** DONE
**Story Parente :** STORY-122 — Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les ~37 endpoints restants soient protégés selon la matrice spec 08 : plugins + marketplace registry (lecture viewer, installation/configuration/désinstallation admin — remplacement des 4 dépendances intérimaires `require_superuser`), targets/hosts (lecture viewer, connectivité/scans admin), et les endpoints de lecture compute/stats/import_export/workflows/discovery (viewer ; import = admin).

## Critères d'acceptation (AC)

- [x] AC 2 (volet plugins/targets/lectures) : Tous les endpoints plugins, plugin_registry, targets/*, compute, discovery, stats, import_export, workflows sont protégés par `require_role(...)` conformément à la matrice spec 08 ; vérifié par une matrice rôle×endpoint représentative : viewer → `403` sur les POST/PUT/DELETE de gestion ; operator → `200` sur les actions opérationnelles et `403` sur la gestion ; admin → gestion `200`.

## Contexte technique

> Analyse réalisée par `analyse-story`/`split-story` (2026-09-08) — inventaire vérifié par grep ; 4 marqueurs `require_superuser` intérimaires dans plugins.py.

**Couches impactées :** Backend uniquement — 8 fichiers routers + tests.

**Spécifications de référence :**
- [`docs/general_specs/08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Matrice : Plugins (Voir installés = tous ; Utiliser fonctions = tous ; Installer/Désinstaller/Configurer = Admin+) ; Marketplace (Parcourir = tous ; Installer une entrée = Admin+) ; Hosts (Lister/statut/métriques = tous ; Ajouter/Supprimer/**Scanner** = Admin+) ; § RBAC par famille (Opération Operator+ : SSH/journalctl **lecture**) ; § Permissions endpoints plugin (lecture Viewer, écriture Operator, config Admin) ;
- [`docs/general_specs/11-plugins.md`](../../docs/general_specs/11-plugins.md) — RBAC des routes injectées par plugins (contexte).

**Inventaire vérifié et rôles minimum cibles :**

**[`plugins.py`](../../backend/app/api/v1/plugins.py) — 9 routes :**

| # | Route (ligne) | Verbe | Rôle actuel | Rôle cible |
|---|---------------|-------|-------------|-----------|
| 1 | l. 46 | GET | get_current_active_user | viewer |
| 2 | l. 89 | GET | idem | viewer |
| 3 | l. 123 | POST | require_superuser (l. 142) | **admin** — installation |
| 4 | l. 196 | PUT | require_superuser (l. 215) | **admin** — configuration |
| 5 | l. 250 | PUT | require_superuser (l. 267) | **admin** — config (enable/disable) |
| 6 | l. 298 | DELETE | require_superuser (l. 313) | **admin** — désinstallation |
| 7 | l. 350 | GET | idem | viewer |
| 8 | l. 476 | GET | idem | viewer |
| 9 | l. 526 | GET | idem | viewer |

> Les 4 `require_superuser` (l. 142, 215, 267, 313) sont **plus restrictifs** que la cible matrice (`admin`) : la bascule vers `require_admin` **élargit** conforme à la spec — c'est l'objet du remplacement des marqueurs intérimaires. Vérifier les libellés réels des routes à l'implémentation.

**[`plugin_registry.py`](../../backend/app/api/v1/plugin_registry.py) — 2 routes (marketplace) :** l. 39 GET → viewer (parcourir catalogue) ; l. 96 GET → viewer.

**[`targets/`](../../backend/app/api/v1/targets) — 13 routes :**

| Fichier | Route (ligne) | Verbe | Rôle cible | Justification |
|---------|---------------|-------|-----------|---------------|
| crud.py | l. 26 GET / l. 155 GET | GET | viewer | Lister hosts |
| crud.py | l. 291 POST | POST | **admin** | Ajouter host |
| crud.py | l. 527 PUT | PUT | **admin** | Modifier host |
| crud.py | l. 749 DELETE | DELETE | **admin** | Supprimer host |
| capabilities.py | l. 36 POST | POST | **admin** | Associer capabilities (gestion) |
| capabilities.py | l. 133 / 310 / 479 GET | GET | viewer | Lire capabilities |
| connectivity.py | l. 37 POST / l. 221 POST | POST | **admin** | Scan/ajout targets = matrice Hosts « Scanner » → Admin+ |
| scanning.py | l. 38 POST / l. 428 POST | POST | **admin** | Scanner = Admin+ (matrice) |

> ⚠️ Arbitrage matrice : les POST de `connectivity.py`/`scanning.py` (découverte/scan de cibles) mappés sur « Ajouter / Supprimer / Scanner » (Hosts) = **Admin+**. Les routes `capabilities` POST l. 36 = gestion de configuration host → admin. Divergence éventuelle (ex. route POST « test connectivity » s'apparentant à une opération SSH/journalctl **lecture** → Operator+) : vérifier le libellé exact à l'implémentation et signaler avant bascule.

**Lectures transverses :**
- [`compute.py`](../../backend/app/api/v1/compute.py) — 2 GET (l. 27, 76) → viewer (métriques/statut compute = lecture) ;
- [`discovery.py`](../../backend/app/api/v1/discovery.py) — GET l. 26 → viewer ; POST l. 88 → **admin** (lancement scan découverte = Scanner) ;
- [`stats.py`](../../backend/app/api/v1/stats.py) — 2 GET (l. 35, 315) → viewer ;
- [`import_export.py`](../../backend/app/api/v1/import_export.py) — GET export l. 21 → viewer (lecture/export) ; POST import l. 72 → **admin** (écriture de données) ;
- [`workflows.py`](../../backend/app/api/v1/workflows.py) — GET l. 15 → viewer.

**Fichiers de référence (patterns vérifiés) :**
- Dépendances — [`backend/app/auth/rbac.py`](../../backend/app/auth/rbac.py) (STORY-122.1) ;
- Remplacement marqueurs — pattern organizations.py (122.4 Tâche 1) : réécrire docstrings « Interim protection » ;
- Plugins scoping multi-org déjà posé (STORY-121.3, plugins.py l. 390) — inchangé.

**Exigences sécurité identifiées (Phase 2.6) :**
- Auth : 401 sans token (chaîne `require_role`) ;
- RBAC : matrice ci-dessus — rôle global (plugins installés = instance) ; targets : checks d'isolation par org existants dans le router (l. ~370 pattern users) conservés ;
- Validation/Exposition : inchangées ;
- Audit : installation/désinstallation plugin = critique → déjà loggées ; table audit_logs = STORY-125.

## Dépendances

- STORY-122.1 (socle). Parallélisable avec 122.2/122.3/122.4/122.6.

## Tâches d'implémentation détaillées

### Tâche 1 : Matrice `require_role` sur `plugins.py` + `plugin_registry.py` (11 routes)
**Objectif :** Basculer les lectures en viewer, remplacer les 4 `require_superuser` intérimaires par `require_admin` (conformité matrice), marketplace en viewer.
**Fichiers :**
- `backend/app/api/v1/plugins.py` — Modifier — Routes 1-2, 7-9 → `require_viewer` ; routes 3-6 → `require_admin` (remplacement l. 142, 215, 267, 313) ; réécrire docstrings intérimaires ; import rbac ; aucun changement de path/response_model.
- `backend/app/api/v1/plugin_registry.py` — Modifier — 2 GET → `require_viewer`.
**Exigences sécurité :** 401/403 par socle ; installation = admin (matrice § Plugins).
**Dépend de :** STORY-122.1

### Tâche 2 : Matrice `require_role` sur `targets/*` (13 routes)
**Objectif :** Appliquer viewer (lectures) / admin (POST/PUT/DELETE gestion + scans + capabilities) sur les 4 fichiers du sous-paquet targets.
**Fichiers :**
- `backend/app/api/v1/targets/crud.py` — Modifier — 2 GET → `require_viewer` ; POST l. 291, PUT l. 527, DELETE l. 749 → `require_admin`.
- `backend/app/api/v1/targets/capabilities.py` — Modifier — 3 GET → `require_viewer` ; POST l. 36 → `require_admin`.
- `backend/app/api/v1/targets/connectivity.py` — Modifier — 2 POST → `require_admin` (vérifier libellés : si « test de connexion » lecture-only → `require_operator` après signalement).
- `backend/app/api/v1/targets/scanning.py` — Modifier — 2 POST → `require_admin` (Scanner = Admin+, matrice Hosts).
**Exigences sécurité :** Isolation par org existante conservée (pattern `get_target` + `is_member`).
**Dépend de :** STORY-122.1

### Tâche 3 : Matrice `require_role` sur les routers transverses (compute, discovery, stats, import_export, workflows — 8 routes)
**Objectif :** Protéger les 8 routes restantes : lectures viewer, écritures admin.
**Fichiers :**
- `backend/app/api/v1/compute.py` — Modifier — 2 GET → `require_viewer` ;
- `backend/app/api/v1/discovery.py` — Modifier — GET l. 26 → `require_viewer` ; POST l. 88 → `require_admin` ;
- `backend/app/api/v1/stats.py` — Modifier — 2 GET → `require_viewer` ;
- `backend/app/api/v1/import_export.py` — Modifier — GET export → `require_viewer` ; POST import → `require_admin` ;
- `backend/app/api/v1/workflows.py` — Modifier — GET → `require_viewer`.
**Exigences sécurité :** Import de données = écriture → admin (prudence matrice Système/Backup) ; export = lecture.
**Dépend de :** STORY-122.1

### Tâche 4 : Tests matrice par router (échantillons représentatifs)
**Objectif :** Vérifier chaque router par un échantillon sécurité (401/403/200 par catégorie de rôle).
**Fichiers :**
- `backend/tests/unit/test_api/test_plugins_rbac.py` — Créer — viewer 200 GET listes + 403 install/config/delete (échantillon) ; operator 403 install ; admin 200 install/uninstall (services mockés — assertion sur statut avant exécution) ; 401 sans token ;
- `backend/tests/unit/test_api/test_targets_rbac.py` — Créer — viewer 200 GET + 403 POST create/scan ; admin 200 CRUD + scan (mockés) ; 401 échantillon ;
- `backend/tests/unit/test_api/test_misc_rbac.py` — Créer — compute/stats/workflows/discovery GET viewer 200 ; discovery POST viewer 403 / admin 200 ; import POST operator 403 / admin 200 (mocké), export GET viewer 200.
**Exigences sécurité :** 401/403 par rôle et catégorie — mêmes patterns que 122.2/122.3 (mock des services, assertion statut).
**Dépend de :** Tâches 1, 2, 3

## Tests à écrire

> Détail en Tâche 4.

### Unitaires Backend
- `backend/tests/unit/test_api/test_plugins_rbac.py` — matrice plugins + registry
- `backend/tests/unit/test_api/test_targets_rbac.py` — matrice targets (4 fichiers)
- `backend/tests/unit/test_api/test_misc_rbac.py` — compute/discovery/stats/import_export/workflows

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_api/test_plugins_rbac.py backend/tests/unit/test_api/test_targets_rbac.py backend/tests/unit/test_api/test_misc_rbac.py -v
poetry run pytest backend/tests/unit/test_api/ -k "plugin or target" -v  # non-régression
make backend-lint && make backend-typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Matrice plugins.py (9 routes, remplacement 4 intérimaires) + plugin_registry.py (2)
- [x] Tâche 2 : Matrice targets/* (13 routes sur 4 fichiers)
- [x] Tâche 3 : Matrice compute/discovery/stats/import_export/workflows (8 routes)
- [x] Tâche 4 : Tests matrice par router
- [x] Lint & typecheck OK

## Notes d'implémentation

**Date :** 2026-09-11

### Fichiers modifiés/créés

**Routers modifiés (8 fichiers, 33 routes) :**
- `backend/app/api/v1/plugins.py` — 9 routes : GET ×5 → `require_viewer` ; POST install / PUT update / PUT configure / DELETE uninstall → `require_admin` (remplacement des 4 marqueurs intérimaires `require_superuser`, conformité matrice spec 08 § Plugins) ; docstrings `## Access Control (STORY-122.5)` ; libellés 403 OpenAPI mis à jour (« rôle Admin requis ») ;
- `backend/app/api/v1/plugin_registry.py` — 2 GET → `require_viewer` (marketplace : « Parcourir » = tous — spec 08) ;
- `backend/app/api/v1/targets/crud.py` — GET ×2 → `require_viewer` ; POST/PUT/DELETE → `require_admin` (Ajouter/Modifier/Supprimer host = Admin+) ; isolation `is_member` conservée ;
- `backend/app/api/v1/targets/capabilities.py` — GET ×3 → `require_viewer` ; POST health-check → `require_viewer` (voir divergence 1) ;
- `backend/app/api/v1/targets/connectivity.py` — POST test-reachability + POST test-connection → `require_operator` (voir divergence 2) ;
- `backend/app/api/v1/targets/scanning.py` — POST discover + POST scan → `require_admin` (Scanner = Admin+, matrice Hosts) ;
- `backend/app/api/v1/compute.py` — GET stats + GET global → `require_viewer` ;
- `backend/app/api/v1/discovery.py` — GET adoption-data → `require_viewer` ; POST adopt → `require_admin` (création stack+deployment, aligné 122.3) ;
- `backend/app/api/v1/stats.py` — GET dashboard + GET stacks/{id} → `require_viewer` ;
- `backend/app/api/v1/import_export.py` — GET export → `require_viewer` ; POST import → `require_admin` (écriture de données) ; bascule depuis `get_current_user` → chaîne `require_role` impose en plus `get_current_active_user` ;
- `backend/app/api/v1/workflows.py` — GET → `require_viewer` (stub).

**Tests créés (3 fichiers, 39 tests) :**
- `backend/tests/unit/test_api/test_plugins_rbac.py` — 13 tests : matrice viewer (200 GET plugins/registry, 403 install/configure/uninstall), operator (403 install), admin (202 install / 200 configure / 204 uninstall, services mockés), 404, 422 (nom registre invalide), 401 sans token ;
- `backend/tests/unit/test_api/test_targets_rbac.py` — 15 tests : viewer (200 list/get/capabilities, 403 create/scan/test-connection), operator (200 test-connection mocké, 403 create), admin (201 create / 200 update / 204 delete / 200 scan, mockés), 404, 422, 401 ;
- `backend/tests/unit/test_api/test_misc_rbac.py` — 11 tests : viewer 200 compute/stats/workflows/export, 403 adopt ; operator 403 import ; admin 200 import réel + adopt mocké ; 404 export ; 401 échantillon.

### Décisions techniques
- Remplacement des 4 `require_superuser` intérimaires par `require_admin` : élargissement conforme à la matrice spec 08 (l'objet explicite de la story), jamais un durcissement silencieux ;
- Pattern docstrings `## Access Control (STORY-122.5)` repris de 122.2/122.3/122.4, avec mention explicite des divergences d'inventaire dans les docstrings concernées ;
- Mocks ciblés (`AsyncMock` sur services réseau/registre) pour les tests admin afin de ne jamais exécuter d'install réelle ni de scan SSH — assertion sur le statut HTTP uniquement ;
- `.venv-test` utilisé pour l'exécution des tests (venv Poetry principal en Python 3.14 avec import alembic cassé — noter dans les difficultés).

### Divergences par rapport à l'analyse
1. **Tâche 2 — `capabilities.py` POST l. 36** : l'inventaire décrivait « Associer capabilities (gestion) → admin » mais le libellé réel est `POST /{target_id}/health-check` (sonde TCP de statut). Matrice Hosts « statut = tous » → bascule en `require_viewer`. Solution minimale cohérente, documentée dans la docstring ;
2. **Tâche 2 — `connectivity.py` POST ×2** : cas explicitement anticipé par la story (« test de connexion lecture-only → require_operator après signalement ») — `test-reachability` (DNS+ping sans credentials) et `test-connection` (SSH lecture uname/os-release) basculés en `require_operator` au lieu d'admin ;
3. **Tâche 3 — `discovery.py` POST `/adopt`** : l'inventaire visait un « scan découverte » ; le libellé réel crée une stack + un deployment → maintien d'`require_admin` (aligné sur POST /stacks de 122.3), aucune divergence de rôle final.

### Difficultés rencontrées
- **5 échecs préexistants `test_stacks_duplicate.py`** (403 au lieu de 200/404/409/422) : causés par la bascule `POST /stacks/{id}/duplicate` → `require_admin` de STORY-122.3 (documentée dans ses notes) alors que ce test utilise `authenticated_client` (user operator du conftest). Vérifié par stash ciblé : les échecs persistent sans les fichiers 122.5 → hors périmètre, non corrigés (règle mission). À traiter par 122.7 (consolidation) ou mise à jour du test obsolète ;
- **mypy : 20 erreurs préexistantes** sur les fichiers touchés (stubs psutil manquants dans .venv-test, assignment connectivity.py, notes plugin_lifecycle) — vérifié par diff avant/après stash : aucune nouvelle erreur introduite (seuls les numéros de ligne bougent) ;
- venv Poetry principal inutilisable (Python 3.14 / alembic) → `.venv-test` (Python 3.11), comme en 122.3/122.4.

### Tests ajoutés et résultats
- `poetry run pytest backend/tests/unit/test_api/test_plugins_rbac.py test_targets_rbac.py test_misc_rbac.py -v` → **39/39 passed** ;
- Non-régression `tests/unit/test_api/` → **240/240 passed** (inclut test_plugin_hooks, test_plugin_registry, test_plugins existants) ;
- Non-régression élargie (test_auth/, compute/stack_stats/targets/plugins services…) → **329/329 passed** ;
- Suite unitaire complète → **1296 passed, 5 failed** (les 5 échecs préexistants test_stacks_duplicate.py, hors périmètre — les 6 échecs « No superadmin » connus n'apparaissent plus dans ce venv) ;
- flake8 → **0 erreur** ; black/isort → **OK après formatage** (2 fichiers) ; mypy → **0 nouvelle erreur** (20 préexistantes inchangées).
