# STORY-250.1 : Purge du code mort backend — permissions legacy, HealthCheck, DatabaseManager, stub workflows, print debug (statuts conditionnels E3/E7 vérifiés)

**Statut :** DONE
**Story Parente :** STORY-250 — Purge du code mort et résidus + dépréciation `/auth/me` (P3-1 + P3-3)
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-1 (axes E1, E3, E4, E6, E7, E8, E2 partiel) — ampleur **M** (partie 1/2)

## Description

En tant que développeur WindFlow, je veux purger le code mort backend identifié par le plan de remédiation (permissions legacy, abstractions non consommées, stub trompeur, print de debug, health checks orphelins) — en **statuant par item avec l'état réel du code post-P2** (croniter et litellm ont des statuts conditionnels que les stories P2 ont tranchés par les faits) — afin que le dépôt ne contienne plus **aucun symbole orphelin** et que l'OpenAPI ne présente plus le stub `/workflows`.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.1, §9, §12, §17) : modules importés nulle part — [`helper/permissions.py`](../../backend/app/helper/permissions.py) (RBAC legacy), `HealthCheck`/`HealthCheckRegistry` de [`core/resilience.py`](../../backend/app/core/resilience.py) (l.340-534 + instance globale), `DatabaseManager` de [`core/abstractions.py`](../../backend/app/core/abstractions.py), stub [`api/v1/workflows.py`](../../backend/app/api/v1/workflows.py) (retourne `[]`), print de debug [`main.py:12`](../../backend/app/main.py).

## Critères d'acceptation (AC)

- [x] AC 1 : `grep`/import-check sur le dépôt → **aucun symbole orphelin** : les fichiers/membres supprimés (E1, E6, E8, `HealthCheck`, `DatabaseManager`) n'ont plus aucune référence (imports, tests, docs générées) ; OpenAPI ne référence plus `/workflows` ; CI et tests verts.
- [x] AC 2 : Chaque décision purger/ressusciter est **argumentée par item** (tableau E1/E3/E4/E6/E7/E8/E2 dans les notes d'implémentation) — y compris le statut conditionnel de `croniter.py` selon ce que STORY-160 a livré (conservé comme dépendance du scheduler, ou supprimé).
- [x] AC 4 : Aucune régression des points forts §2.G ; les tests existants passent ; les tests référençant les éléments purgés sont nettoyés.
- [x] AC 5 : Build + lint + tests passent (`make lint`, `make backend-test`).

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31 — post P0-P2)

- **E1 — [`helper/permissions.py`](../../backend/app/helper/permissions.py) (167 lignes) : ORPHELIN confirmé.** Contenu : `is_in_cron_interval()` (l.10), `is_rule_accessible_now()` (l.33), `has_permission()` (l.64) — modèle RBAC legacy (policies/groups/cron) divergent du RBAC endpoint-based `require_role(...)` livré en P1 (STORY-121/122). Grep : **zéro import** dans `backend/app` + `backend/tests` ; seule trace : mention docstring « pattern fichier : helper/permissions.py » dans [`helper/pagination.py:15`](../../backend/app/helper/pagination.py) (à remplacer par une autre référence de pattern). ⚠️ Ce fichier est le **seul importeur de `helper/croniter`** (l.7) — sa suppression renforce le statut de croniter (E3).
- **E3 — [`helper/croniter.py`](../../backend/app/helper/croniter.py) : CONSERVER (condition tranchée par STORY-160).** Le moteur scheduler valide les expressions cron via `from ..helper.croniter import CroniterBadCronError, croniter` dans [`schemas/scheduled_task.py:35`](../../backend/app/schemas/scheduled_task.py) (Pydantic → 422 si invalide, docstring l.52) et le moteur runtime l'exécute (commentaire `main.py:446` « croniter vendored »). La dépendance croisée exigée par le plan est **documentée explicitement** : croniter est la dépendance de validation du scheduler core (STORY-160.1/160.2) — ne pas supprimer.
- **E4 — [`core/abstractions.py`](../../backend/app/core/abstractions.py) : purge `DatabaseManager` SEULEMENT.** `CacheManager` est **consommé** par [`core/cache.py`](../../backend/app/core/cache.py) (`class MemoryCache(CacheManager)` l.158, `class RedisCache(CacheManager)` l.254 — STORY-168) → conservé. `DatabaseManager` : grep zéro consommateur hors du module → purger la classe + retirer l'export de [`core/__init__.py:5-7`](../../backend/app/core/__init__.py) (`from .abstractions import CacheManager, DatabaseManager` + `__all__`) → ne laisser que `CacheManager`.
- **E6 — [`api/v1/workflows.py`](../../backend/app/api/v1/workflows.py) (57 lignes) : PURGER (stub trompeur).** Unique route `GET /workflows/` → `data == []` constant. Démontage : import + `include_router(workflows_router, prefix="/workflows")` dans [`api/v1/__init__.py:29,52`](../../backend/app/api/v1/__init__.py) ; garde-fou `"workflows": 1` dans [`test_rbac_exhaustivite.py:76`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py) ; tests à nettoyer : `test_viewer_200_workflows` ([`test_misc_rbac.py:170`](../../backend/tests/unit/test_api/test_misc_rbac.py)), classe §7 workflows ([`test_api_contract.py:237-244`](../../backend/tests/integration/test_api_contract.py) + ligne paramétrée l.402), lignes workflows ([`test_rbac_matrix_consolidated.py`](../../backend/tests/unit/test_api/test_rbac_matrix_consolidated.py)). Justification plan : workflows = plugins n8n (spec), pas du core — le stub trompe le contrat API.
- **E7 — [`services/litellm_service.py`](../../backend/app/services/litellm_service.py) : CONSERVER (décision du plan RENVERSÉE par les faits).** Le plan §2.E (rédigé avant la P2) disait « purger du core », mais **STORY-168 a ressuscité ce service** : cache unifié `core/cache.get_cache()` (clé `llm:{sha256(provider:prompt)}`, prompt jamais en clair, TTL 300 s) + suite de tests dédiée ([`test_litellm_service.py`](../../backend/tests/unit/test_services/test_litellm_service.py), couverture 97 % documentée kanban STORY-168). Le purger détruirait du travail P2 testé. Il reste néanmoins **non exposé par API** (aucun router ne l'importe ; seul [`config.py:467`](../../backend/app/config.py) `litellm_enabled: bool = False` le référence) : décision d'analyse = **conserver** (depend du cache P2, prêt pour le futur plugin IA spec 18), noter l'écart d'exposition pour la Roadmap Phase 5 (plugin IA) — traçabilité STORY-254.
- **E8 — print de debug [`main.py:12`](../../backend/app/main.py:12) : PURGER** (`print("=== LOADING backend.app.main MODULE ===")`). Les autres prints du dépôt ne sont PAS dans le périmètre : `database_seed.py:98-106` = sortie CLI légitime du seed, `helper/email.py:45` = fallback error path (could become logger.error mais hors story).
- **E2 partiel — `HealthCheck` (l.340) + `HealthCheckRegistry` (l.434) + instance globale (l.534) de [`core/resilience.py`](../../backend/app/core/resilience.py) : PURGER ces ~200 lignes.** Grep zéro consommateur hors module (`HostHealthCheckResponse` de `schemas/host.py` est un **autre** symbole, actif côté hosts). ⚠️ Ne pas toucher : `CircuitState`, `HealthStatus` (enum resilience), `CircuitBreaker` (l.36), `RetryPolicy` (l.209) — périmètre STORY-251. Vérifier les imports du module (`__init__` exports éventuels) avant suppression.

### Décisions d'analyse (250.1)

- **D1 — Ordre de purge** : supprimer d'abord `workflows.py` + son router (impact OpenAPI immédiat), puis les membres resilience, puis `DatabaseManager`/exports, puis `permissions.py`, puis le print — chaque étape vérifiée par import-check (`python -c "from app.main import app"`) avant la suivante.
- **D2 — Docstring pagination.py** : remplacer la référence « pattern : helper/permissions.py » par une référence vivante (`helper/compute_helpers.py` ou mention du pattern lui-même) — pas de doc pointant un fichier supprimé.
- **D3 — `resilience.py` post-purge** : docstring module mise à jour (le module documente désormais CircuitBreaker + RetryPolicy ; note renvoi HealthCheck → STORY-251/253 selon décision CircuitBreaker) ; si `__init__` de core exportait les classes purgées, nettoyer.
- **Sécurité (checklist règle 40)** : aucune route nouvelle ; E6 **retire** une surface (réduction attaque) ; les suppressions ne touchent aucun secret ; aucun log modifié.

## Dépendances

- **Pré-requis P2 tous livrés et vérifiés** : STORY-160.x (croniter consommé — vérifié), STORY-168 (CacheManager consommé — vérifié), STORY-130.2 (déjà purgé côté Celery — la mission ne purge rien de Celery ici).
- **STORY-250.2 dépend de cette story** (ordre logique purge → dépréciation).

## Tâches d'implémentation détaillées

### Tâche 1 : Purge E6 — stub `workflows.py` + router + garde-fous + tests
**Objectif :** Retirer la surface `/workflows` du contrat API et nettoyer toutes ses références (AC 1).
**Fichiers :**
- `backend/app/api/v1/workflows.py` — **Supprimer** (fichier entier, 57 lignes).
- `backend/app/api/v1/__init__.py` — **Modifier** — retirer `from .workflows import router as workflows_router` (l.29) et `api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])` (l.52).
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — **Modifier** — retirer `"workflows": 1` de `EXPECTED_ROUTE_COUNTS` (l.76) avec commentaire `# STORY-250.1 : router workflows supprimé (stub trompeur — arbitrage plugins n8n)`.
- `backend/tests/unit/test_api/test_misc_rbac.py` — **Modifier** — supprimer `test_viewer_200_workflows` (l.170) et sa ligne docstring.
- `backend/tests/integration/test_api_contract.py` — **Modifier** — supprimer la classe `TestWorkflowsRouterContract` (§7, l.~237-244) et la ligne paramétrée `("GET", "/api/v1/workflows/")` (l.402).
- `backend/tests/unit/test_api/test_rbac_matrix_consolidated.py` — **Modifier** — retirer les lignes/cas workflows du header docstring et des paramétrages.
**Exigences sécurité :** Retrait de surface = réduction (aucun ajout).
**Dépend de :** Aucune

### Tâche 2 : Purge E2 — `HealthCheck`/`HealthCheckRegistry` de resilience.py
**Objectif :** Supprimer les ~200 lignes orphelines (l.340→fin instance globale) sans toucher CircuitBreaker/RetryPolicy.
**Fichiers :**
- `backend/app/core/resilience.py` — **Modifier** — supprimer `class HealthCheck` (l.340), `class HealthCheckRegistry` (l.434), l'instance globale (l.534) ; mettre à jour la docstring du module (contenu restant : CircuitBreaker + RetryPolicy ; note « HealthCheck purgé STORY-250.1 (redondant check_all_health hosts) — CircuitBreaker arbitré STORY-251 ») ; vérifier/ajuster les imports internes devenus inutiles.
- `backend/app/core/__init__.py` — **Modifier (si export)** — retirer tout export de `HealthCheck`/`HealthCheckRegistry`.
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Aucune (parallèle à Tâche 1)

### Tâche 3 : Purge E4 — `DatabaseManager` + exports core
**Objectif :** Purger l'abstraction non consommée, garder `CacheManager` (consommé par cache STORY-168).
**Fichiers :**
- `backend/app/core/abstractions.py` — **Modifier** — supprimer `class DatabaseManager` ; docstring module ajustée (`CacheManager` seul contrat vivant, consommé par `core/cache.py`).
- `backend/app/core/__init__.py` — **Modifier** — `from .abstractions import CacheManager` seul + `__all__ = ["CacheManager"]`.
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 2 (même fichier `core/__init__.py` touché — appliquer ensemble).

### Tâche 4 : Purge E1 — `helper/permissions.py` + référence docstring
**Objectif :** Supprimer le modèle RBAC legacy divergent.
**Fichiers :**
- `backend/app/helper/permissions.py` — **Supprimer** (fichier entier, 167 lignes).
- `backend/app/helper/pagination.py` — **Modifier** — remplacer la mention docstring « pattern fichier : ``helper/permissions.py`` » (l.15) par une référence vivante (ex. « fonctions pures, type hints complets — pattern ``helper/compute_helpers.py`` »).
**Exigences sécurité :** Suppression d'un modèle de permissions **non câblé** — le RBAC actif (`require_role`/`require_superuser`) est inchangé (garde-fous §2.G).
**Dépend de :** Aucune

### Tâche 5 : Purge E8 — print debug main.py
**Objectif :** Retirer le bruit de chargement.
**Fichiers :**
- `backend/app/main.py` — **Modifier** — supprimer la ligne 12 `print("=== LOADING backend.app.main MODULE ===", flush=True)`.
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Aucune

### Tâche 6 : Statuts conditionnels E3/E7 — documentation in-code + story
**Objectif :** Tracer les deux décisions « conserver » argumentées (AC 2).
**Fichiers :**
- `backend/app/helper/croniter.py` — **Modifier** — enrichir la docstring module : « consommé par `schemas/scheduled_task.py` (validation cron 422 — STORY-160.1) et le moteur scheduler (STORY-160.2) ; décision P3-1 : conservé (STORY-250.1) ».
- `backend/app/services/litellm_service.py` — **Modifier** — note docstring : « service non exposé par API à date (aucun router) — conservé (STORY-250.1) car consommateur du cache unifié STORY-168 + tests dédiés ; exposition = plugin IA Roadmap Phase 5 (spec 18) ».
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Aucune

### Tâche 7 : Écran de contrôle final + validations
**Objectif :** Prouver AC 1/4/5 — zéro référence résiduelle, OpenAPI propre, CI verte.
**Fichiers :** aucun nouveau (exécution + éventuelles retouches).
**Actions :**
- `grep -rn "helper.permissions\|has_permission\|is_rule_accessible_now" backend/ --include="*.py"` (hors __pycache__) → **0 résultat** ;
- `grep -rn "DatabaseManager\|HealthCheckRegistry" backend/app backend/tests --include="*.py"` → 0 (hors `HostHealthCheckResponse` qui est un autre symbole actif) ;
- `grep -rn "workflows_router\|/workflows" backend/app --include="*.py"` → 0 ; vérifier OpenAPI généré : aucune route `/workflows` ;
- `grep -n "print(" backend/app/main.py` → 0 ;
- Import-check `python -c "from app.main import app"` ;
- `make backend-lint` + `make backend-test-unit` complets (non-régression §2.G : docker 35, compute 7, WS, hosts…).
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâches 1-6

## Tests à écrire

### Backend
- `backend/tests/unit/test_api/test_deprecation_auth_me.py` — **créé en 250.2** (rien ici : cette story est une **purge**, elle retire des tests).
- Nettoyages (pas des ajouts) : retraits listés en Tâche 1 — vérifier par exécution que les fichiers modifiés collectent/passent.
- **Test de non-régression structurel** : `test_rbac_exhaustivite.py` (compteurs à jour sans workflows) passe tel quel après retrait de l'entrée.

### Commandes de validation
```bash
cd backend
poetry run pytest tests/unit/test_api/test_rbac_exhaustivite.py tests/unit/test_api/test_misc_rbac.py tests/unit/test_api/test_rbac_matrix_consolidated.py -q
poetry run pytest tests/integration/test_api_contract.py -q
poetry run python -c "from app.main import app; spec=app.openapi(); assert not any('/workflows' in p for p in spec['paths']); print('OpenAPI OK')"
make backend-lint && make backend-test-unit
# Écran de contrôle (grep zéro) : voir Tâche 7
```

## État d'avancement technique

- [x] T1. Purge E6 — `workflows.py` + router + garde-fous + 3 fichiers de tests
- [x] T2. Purge E2 — `HealthCheck`/`HealthCheckRegistry` (resilience.py, CircuitBreaker/RetryPolicy intacts)
- [x] T3. Purge E4 — `DatabaseManager` + exports `core/__init__.py` (`CacheManager` conservé)
- [x] T4. Purge E1 — `helper/permissions.py` + docstring pagination.py
- [x] T5. Purge E8 — print debug `main.py:12`
- [x] T6. Statuts E3/E7 — docstrings croniter/litellm (décisions conservées argumentées)
- [x] T7. Écran de contrôle (grep zéro, OpenAPI sans /workflows) + validations complètes

## Notes d'implémentation

<!-- Ajoutées à la clôture par treat-story -->

## Notes d'implémentation (treat-story — 2026-10-31)

### Tableau des décisions E (AC 2) — argumenté item par item

| Item | Décision appliquée | Justification vérifiée dans le code |
|------|--------------------|-------------------------------------|
| E1 `helper/permissions.py` | **Purgé** (fichier supprimé, 167 l.) | Zéro import dans app+tests ; modèle RBAC legacy divergent du `require_role` P1 (STORY-121/122) ; seule trace = docstring pagination.py (remplacée) |
| E2 `HealthCheck`/`HealthCheckRegistry` | **Purgés** (~200 l. de resilience.py) | Zéro consommateur hors module ; redondant avec le health-check hosts ; `CircuitBreaker`/`RetryPolicy` intacts (STORY-251) ; 2 imports morts nettoyés (time, List) |
| E3 `helper/croniter.py` | **Conservé** | Consommé par `schemas/scheduled_task.py` (validation cron 422) + moteur scheduler (STORY-160) — docstring de traçabilité posée |
| E4 `DatabaseManager` | **Purgé** | Zéro consommateur ; `CacheManager` **conservé** (core/cache.py STORY-168) ; export core/__init__ réduit |
| E6 `api/v1/workflows.py` | **Purgé** (57 l.) + router + garde-fou `"workflows": 1` + 5 nettoyages tests (misc_rbac ×2, contract §7, matrix, ligne 401) | Stub trompeur — workflows = plugins n8n (arbitrage specs) ; OpenAPI 147 paths sans `/workflows` |
| E7 `litellm_service.py` | **Conservé** (décision plan RENVERSÉE) | STORY-168 l'a ressuscité (cache unifié + tests 97 %) ; non exposé par API — docstring posée, traçabilité plugin IA Roadmap Phase 5 (STORY-254) |
| E8 print `main.py:12` | **Purgé** | Trivial ; les prints de database_seed.py (sortie CLI du seed) et email.py:45 (fallback) restent hors périmètre |

### Fichiers modifiés/supprimés
**Supprimés** : `helper/permissions.py`, `api/v1/workflows.py` · **Modifiés** : `core/resilience.py` (coupe + docstring + 2 imports), `core/abstractions.py` (DatabaseManager −, docstring, imports), `core/__init__.py` (export CacheManager seul), `api/v1/__init__.py` (déltage workflows), `main.py` (print −), `helper/pagination.py` (docstring), `helper/croniter.py` + `services/litellm_service.py` (docstrings statut), tests : `test_rbac_exhaustivite.py`, `test_misc_rbac.py` (×2 blocs), `test_api_contract.py` (§7), `test_rbac_matrix_consolidated.py`.

### Résultats
| Contrôle | Résultat |
|---|---|
| grep E1/E4/E6/E8 | **0 référence** (hors docstrings de traçabilité STORY-250.1) |
| OpenAPI | 147 paths, aucune route `/workflows` |
| Tests ciblés (rbac_exhaustivite, misc_rbac, matrix, contract) | **86 passed** — unique échec `/api/v1/metrics` **préexistant** (résidu STORY-172, prouvé HEAD) |
| lint (flake8/black/isort) fichiers story | 0 erreur |
| mypy core/ | 0 erreur fichiers touchés |
| Non-régression `tests/unit` | **3216 passed / 1 préexistant** |
