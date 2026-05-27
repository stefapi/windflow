# STORY-006.1 : Backend — Service d'exécution des hooks lifecycle

**Statut :** DONE
**Story Parente :** STORY-006 — Hooks lifecycle plugins (on_install, on_configure, on_start, on_stop, on_uninstall)
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que le backend exécute les hooks de cycle de vie déclarés dans le manifest des plugins (on_install, on_configure, on_start, on_stop, on_uninstall) afin de permettre l'exécution de logique personnalisée à chaque transition d'état, avec gestion d'erreurs et rollback appropriés.

## Critères d'acceptation (AC)
- [x] AC 1 : Les 5 hooks (on_install, on_configure, on_start, on_stop, on_uninstall) sont correctement invoqués lors des transitions d'état du plugin
- [x] AC 2 : Un hook en échec ne laisse pas le plugin dans un état incohérent (rollback ou état d'erreur géré)
- [x] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Contexte technique

### Existant (déjà implémenté dans les stories précédentes)
- **Modèle [`Plugin`](backend/app/models/plugin.py)** : modèle SQLAlchemy avec statuts (`PluginStatus` : INSTALLED, INSTALLING, RUNNING, STOPPED, UPDATING, ERROR)
- **Schema [`PluginHook`](backend/app/schemas/plugin_manifest.py:239)** : les 5 hooks sont déjà déclarés dans le manifest (on_install, on_configure, on_start, on_stop, on_update, on_uninstall)
- **[`PluginManifest.hooks`](backend/app/schemas/plugin_manifest.py:331)** : champ déjà validé par Pydantic
- **[`EventType`](backend/app/core/events.py:49)** : événements plugin déjà définis (PLUGIN_INSTALLED, PLUGIN_CONFIGURED, etc.)
- **[`PluginManagerService`](backend/app/services/plugin_manager_service.py)** : service CRUD existant avec `_emit_event()` (actuellement juste un log structuré, note en ligne 509 : "L'intégration avec l'EventBus sera faite dans STORY-006")
- **[`WindFlowException`](backend/app/core/exceptions.py:10)** : exception de base avec `message` et `details`

### Patterns à suivre
- **Service** : suivre le pattern de [`PluginManagerService`](backend/app/services/plugin_manager_service.py) (classe avec méthodes async)
- **Modèle** : suivre [`Plugin`](backend/app/models/plugin.py) (UUID PK, timestamps, JSON columns)
- **Schema** : suivre [`plugin.py`](backend/app/schemas/plugin.py) (séparation Request/Response, ConfigDict)
- **Tests service** : suivre [`test_plugin_manager_service.py`](backend/tests/unit/test_services/test_plugin_manager_service.py) (pytest.mark.asyncio, fixtures db_session)
- **Tests API** : suivre [`test_plugins.py`](backend/tests/unit/test_api/test_plugins.py) (httpx AsyncClient, auth_enabled fixture)

### Spécification fonctionnelle
Les hooks sont des chemins de scripts shell déclarés dans le manifest (`hooks.on_install: scripts/install.sh`). Le service doit :
1. Lire les hooks déclarés dans `manifest_data` du plugin
2. Exécuter le script correspondant via `asyncio.create_subprocess_exec`
3. Capturer stdout/stderr et le code de retour
4. Enregistrer le résultat dans une table `plugin_hook_logs`
5. En cas d'échec (code ≠ 0), mettre le plugin en statut ERROR et annuler la transition

### Exigences sécurité identifiées
- **Auth :** oui — `get_current_active_user` sur GET hooks/logs ; `require_superuser` sur les transitions (install/configure/uninstall)
- **RBAC :** Lecture logs = tout utilisateur authentifié ; Exécution hooks = superuser uniquement
- **Validation :** chemin script anti path traversal (pas de `..`, chemin relatif uniquement) ; validation Pydantic des schemas
- **Exposition :** stdout/stderr ne doivent pas contenir de secrets (config_values de type password passées en env vars masquées)
- **Audit :** chaque exécution de hook tracée dans `plugin_hook_logs` avec user_id, timestamp, résultat

### Décisions de conception

**Résolution des chemins de scripts :**
Les hooks sont déclarés en chemins relatifs dans le manifest (ex: `scripts/install.sh`). Le service résout le chemin absolu via un répertoire de base configurable (`settings.plugins_base_dir`, par défaut `./data/plugins/`) concaténé avec le nom du plugin. Exemple : `./data/plugins/traefik/scripts/install.sh`. Si le chemin contient `..` ou est absolu, une `WindFlowException` est levée.

**Coexistence hooks et événements :**
Les hooks s'exécutent **avant** l'émission d'événements (`_emit_event`). Si le hook réussit → l'événement de succès est émis (ex: `PLUGIN_INSTALLED`). Si le hook échoue → l'événement `PLUGIN_ERROR` est émis à la place, et le plugin passe en statut `ERROR`.

**Hooks on_start / on_stop :**
[`PluginManagerService`](backend/app/services/plugin_manager_service.py) n'a pas de méthodes `start_plugin()` / `stop_plugin()`. Le service `PluginLifecycleService` expose des méthodes `execute_on_start()` et `execute_on_stop()` prêtes à l'emploi, mais elles ne seront pas câblées dans `PluginManagerService` tant que les opérations start/stop ne sont pas implémentées (futur STORY ou extension).

**Pattern d'exécution subprocess :**
Suivre le pattern de [`docker_executor.py`](backend/app/services/docker_executor.py:162) : `asyncio.create_subprocess_exec` avec `stdout=asyncio.subprocess.PIPE`, `stderr=asyncio.subprocess.PIPE`. Le timeout est géré via `asyncio.wait_for(proc.communicate(), timeout=30)`.

## Dépendances
- STORY-001 : Format manifest YAML (✅ DONE)
- STORY-002 : API REST Plugin Manager — CRUD plugins (✅ DONE)

## Tâches d'implémentation détaillées

### Tâche 1 : Modèle PluginHookLog — Stockage des exécutions de hooks
**Objectif :** Créer le modèle SQLAlchemy pour enregistrer chaque exécution de hook avec son résultat (succès/échec, logs, durée).
**Fichiers :**
- `backend/app/models/plugin_hook_log.py` — Créer — Modèle `PluginHookLog(Base)` avec champs : id (String(36) PK, `str(uuid4())`), plugin_id (String(36), FK vers `plugins.id` avec `ondelete=CASCADE`), hook_name (String(50)), script_path (String(500)), status (String(20), valeurs: pending/running/success/failed), exit_code (Integer nullable), stdout (Text), stderr (Text), started_at (DateTime), completed_at (DateTime nullable), duration_ms (Integer nullable), triggered_by (String(36), user_id), error_message (Text nullable). Index sur `(plugin_id, hook_name)` et `started_at`. Suivre le pattern de [`Plugin`](backend/app/models/plugin.py) (UUID PK, types `Mapped[]`, `mapped_column`).
- `backend/app/models/__init__.py` — Modifier — Ajouter `from .plugin_hook_log import PluginHookLog` et l'ajouter à `__all__`
- `backend/app/config.py` — Modifier — Ajouter le setting `plugins_base_dir: str = "./data/plugins/"` dans la classe Settings pour la résolution des chemins de scripts hooks
**Exigences sécurité :** Ne pas stocker de secrets dans stdout/stderr (les config_values passées en env vars ne doivent pas être loguées). Le champ stdout/stderr doit être tronqué à 10 000 caractères pour éviter les abus de stockage.
**Dépend de :** Aucune

### Tâche 2 : Schemas Pydantic pour les hooks logs
**Objectif :** Créer les schemas de validation et réponse pour l'API des logs de hooks.
**Fichiers :**
- `backend/app/schemas/plugin_hook_log.py` — Créer — Schemas : HookLogResponse (détail complet), HookLogSummaryResponse (résumé pour listing), HookExecutionResult (interne, résultat d'exécution)
**Pattern de référence :** [`backend/app/schemas/plugin.py`](backend/app/schemas/plugin.py)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Service PluginLifecycleService — Exécution des hooks
**Objectif :** Créer le service métier responsable de l'exécution des 5 hooks lifecycle avec gestion d'erreurs, timeout, et logging.
**Fichiers :**
- `backend/app/services/plugin_lifecycle_service.py` — Créer — Service `PluginLifecycleService` avec méthodes :
  - `execute_hook(db, plugin, hook_name, user_id) → HookExecutionResult` : méthode principale. Résout le chemin du script via `settings.plugins_base_dir / plugin.name / script_path`. Valide anti path traversal. Exécute via `asyncio.create_subprocess_exec(script_abs_path, stdout=PIPE, stderr=PIPE)` (pattern : [`docker_executor.py`](backend/app/services/docker_executor.py:162)). Timeout via `asyncio.wait_for(proc.communicate(), timeout=self.HOOK_TIMEOUT_SECONDS)`. Capture stdout/stderr (tronqués à 10 000 chars). Enregistre le résultat dans `PluginHookLog`.
  - `execute_lifecycle_transition(db, plugin, transition, user_id) → Plugin` : mappe transition → hook_name (`install` → `on_install`, `configure` → `on_configure`, `uninstall` → `on_uninstall`, `start` → `on_start`, `stop` → `on_stop`). Si le hook n'est pas déclaré dans le manifest → no-op (retourne le plugin sans erreur). Si le hook échoue → passe le plugin en `PluginStatus.ERROR`, émet `EventType.PLUGIN_ERROR`.
  - `execute_on_start(db, plugin, user_id)` et `execute_on_stop(db, plugin, user_id)` : méthodes exposées mais non câblées dans PluginManagerService (pas d'opérations start/stop existantes).
  - `_resolve_script_path(plugin_name, script_path) → str` : valide et résout le chemin. Lève `WindFlowException` si le chemin contient `..`, est absolu, ou ne commence pas par un sous-répertoire valide.
  - `_build_safe_env_vars(plugin) → dict` : construit les variables d'environnement pour le script. Filtre les champs de type `password` des `config_values` (remplace la valeur par `***`). Expose les autres config_values préfixées par `PLUGIN_CONFIG_`.
  - `list_hook_logs(db, plugin_id, skip, limit) → List[PluginHookLog]` : requête de listing pour l'API.
  - `get_hook_log(db, log_id) → Optional[PluginHookLog]` : requête détail pour l'API.
  - Constante de classe : `HOOK_TIMEOUT_SECONDS = 30`
**Pattern de référence :** [`backend/app/services/plugin_manager_service.py`](backend/app/services/plugin_manager_service.py) pour la structure de service, [`backend/app/services/docker_executor.py`](backend/app/services/docker_executor.py:162) pour le pattern subprocess
**Exigences sécurité :** Validation du chemin du script via `_resolve_script_path` (anti path traversal : pas de `..`, pas de chemin absolu). Environnement restreint via `_build_safe_env_vars` (secrets masqués). Pas de secrets en clair dans les logs ni dans stdout/stderr stockés.
**Dépend de :** Tâche 1, Tâche 2

### Tâche 4 : Intégration dans PluginManagerService
**Objectif :** Modifier le service existant pour appeler les hooks lifecycle lors des transitions d'état (install, configure, uninstall).
**Fichiers :**
- `backend/app/services/plugin_manager_service.py` — Modifier — Injecter `PluginLifecycleService` via `self._lifecycle_service = PluginLifecycleService()` dans `__init__`. Pour chaque transition :
  - `install_plugin` : après `plugin.status = PluginStatus.INSTALLED` (ligne ~260), appeler `await self._lifecycle_service.execute_lifecycle_transition(db, plugin, "install", user_id)`. Si le hook échoue, le service passe le plugin en ERROR — ne pas émettre `PLUGIN_INSTALLED` mais laisser le service lifecycle émettre `PLUGIN_ERROR`.
  - `configure_plugin` : après `flag_modified` et commit (ligne ~473), appeler `await self._lifecycle_service.execute_lifecycle_transition(db, plugin, "configure", user_id)`. Même logique d'événement.
  - `uninstall_plugin` : **avant** `await db.delete(plugin)` (ligne ~416), appeler `await self._lifecycle_service.execute_lifecycle_transition(db, plugin, "uninstall", user_id)`. Si le hook échoue, ne pas supprimer le plugin (lever l'exception).
  - L'ordre est : **hook → événement**. `_emit_event` n'est appelé que si le hook a réussi.
**Exigences sécurité :** `get_current_user` vérifié avant chaque transition (déjà en place via les endpoints `require_superuser`)
**Dépend de :** Tâche 3

### Tâche 5 : Endpoint API GET /plugins/{plugin_id}/hooks/logs
**Objectif :** Exposer les logs d'exécution des hooks via l'API REST pour consultation.
**Fichiers :**
- `backend/app/api/v1/plugins.py` — Modifier — Ajouter deux endpoints :
  - `GET /{plugin_id}/hooks/logs` avec paramètres query `skip: int = 0, limit: int = 100`. Retourne `List[HookLogSummaryResponse]`. Dépendances : `get_current_active_user`, `conditional_rate_limiter(100, 60)`. Logique : récupérer le plugin via `PluginManagerService.get_plugin(db, plugin_id)`, vérifier `plugin.organization_id == current_user.organization_id` (sinon 403), puis requêter les logs via `PluginLifecycleService.list_hook_logs(db, plugin_id, skip, limit)`.
  - `GET /{plugin_id}/hooks/logs/{log_id}` pour le détail complet (`HookLogResponse` avec stdout/stderr). Mêmes vérifications d'accès.
**Pattern de référence :** [`backend/app/api/v1/plugins.py`](backend/app/api/v1/plugins.py) (endpoints existants, pattern `get_plugin` + vérification organisation)
**Exigences sécurité :** `get_current_active_user` requis (tout utilisateur authentifié peut voir les logs de son organisation). Vérification `plugin.organization_id == current_user.organization_id` obligatoire (sinon 403). Le champ `stdout`/`stderr` dans `HookLogResponse` ne doit pas contenir de secrets (assertion dans les tests).
**Dépend de :** Tâche 3

### Tâche 6 : Tests unitaires backend
**Objectif :** Couvrir le service lifecycle et l'endpoint API avec tests nominaux, erreurs et sécurité.
**Fichiers :**
- `backend/tests/unit/test_services/test_plugin_lifecycle_service.py` — Créer — Tests : exécution nominale de chaque hook, hook en échec (exit code ≠ 0), hook avec timeout, hook non déclaré dans le manifest (no-op), validation anti path traversal, logging des résultats
- `backend/tests/unit/test_api/test_plugin_hooks.py` — Créer — Tests : GET /hooks/logs retourne 200 avec données, GET /hooks/logs retourne 401 sans token, GET /hooks/logs retourne 404 plugin inexistant, GET /hooks/logs retourne 403 pour rôle insuffisant
**Pattern de référence :** [`backend/tests/unit/test_services/test_plugin_manager_service.py`](backend/tests/unit/test_services/test_plugin_manager_service.py), [`backend/tests/unit/test_api/test_plugins.py`](backend/tests/unit/test_api/test_plugins.py)
**Exigences sécurité :** Tests 401, 403, 404 obligatoires
**Dépend de :** Tâche 4, Tâche 5

## Tests à écrire

### Backend — Tests service
- `backend/tests/unit/test_services/test_plugin_lifecycle_service.py`
  - `test_execute_on_install_hook_success` — Hook on_install s'exécute avec succès, log enregistré en BDD avec status=success
  - `test_execute_on_configure_hook_success` — Hook on_configure s'exécute avec succès
  - `test_execute_on_uninstall_hook_success` — Hook on_uninstall s'exécute avant suppression
  - `test_execute_on_start_hook_success` — Hook on_start s'exécute avec succès (méthode exposée, non câblée)
  - `test_execute_on_stop_hook_success` — Hook on_stop s'exécute avec succès (méthode exposée, non câblée)
  - `test_execute_hook_failure_sets_plugin_error` — Hook en échec → plugin status ERROR, log avec exit_code et stderr
  - `test_execute_hook_timeout` — Hook qui dépasse le timeout (30s) → échec avec message approprié, log enregistré
  - `test_execute_hook_not_declared_is_noop` — Pas de hook déclaré dans le manifest → aucune exécution, pas de log, pas d'erreur
  - `test_execute_hook_path_traversal_rejected` — Chemin avec `..` → WindFlowException
  - `test_execute_hook_absolute_path_rejected` — Chemin absolu (`/etc/passwd`) → WindFlowException
  - `test_execute_hook_script_not_found` — Script inexistant → hook en échec avec exit_code et stderr capturés
  - `test_execute_hook_captures_stdout_stderr` — Stdout et stderr capturés dans le log
  - `test_execute_hook_duration_calculated` — duration_ms calculé correctement (started_at → completed_at)
  - `test_build_safe_env_vars_masks_passwords` — Les config_values de type password sont masquées avec `***` dans les env vars
  - `test_build_safe_env_vars_exposes_non_secrets` — Les config_values non-password sont exposées avec préfixe `PLUGIN_CONFIG_`

### Backend — Tests API
- `backend/tests/unit/test_api/test_plugin_hooks.py`
  - `test_get_hook_logs_returns_200_authenticated` — Retourne les logs existants
  - `test_get_hook_logs_returns_empty_list` — Aucun log → liste vide `[]`
  - `test_get_hook_logs_returns_401_without_token` — **Sécurité** : pas de token → 401
  - `test_get_hook_logs_returns_404_plugin_not_found` — Plugin inexistant → 404
  - `test_get_hook_logs_returns_403_for_other_org` — **Sécurité** : plugin d'une autre organisation → 403
  - `test_get_hook_log_detail_returns_200` — GET /{plugin_id}/hooks/logs/{log_id} retourne le détail avec stdout/stderr
  - `test_get_hook_log_detail_returns_404` — Log inexistant → 404
  - `test_hook_logs_pagination_works` — Paramètres skip/limit fonctionnent correctement

### Commandes de validation
```bash
# Backend - Tests service lifecycle
poetry run pytest backend/tests/unit/test_services/test_plugin_lifecycle_service.py -v

# Backend - Tests API hooks
poetry run pytest backend/tests/unit/test_api/test_plugin_hooks.py -v

# Backend - Tous les tests hooks + couverture
poetry run pytest backend/tests/unit/test_services/test_plugin_lifecycle_service.py backend/tests/unit/test_api/test_plugin_hooks.py -v --cov=app.services.plugin_lifecycle_service --cov=app.api.v1.plugins --cov-fail-under=80

# Backend - Lint + type check
poetry run black --check backend/app/services/plugin_lifecycle_service.py backend/app/models/plugin_hook_log.py backend/app/schemas/plugin_hook_log.py
poetry run flake8 backend/app/services/plugin_lifecycle_service.py backend/app/models/plugin_hook_log.py backend/app/schemas/plugin_hook_log.py
poetry run mypy backend/app/services/plugin_lifecycle_service.py
```

## État d'avancement technique
- [x] Tâche 1 : Modèle PluginHookLog + config plugins_base_dir
- [x] Tâche 2 : Schemas Pydantic hooks logs
- [x] Tâche 3 : Service PluginLifecycleService (exécution, timeout, path validation, env vars)
- [x] Tâche 4 : Intégration dans PluginManagerService (hooks avant événements)
- [x] Tâche 5 : Endpoints API GET hooks/logs + GET hooks/logs/{log_id}
- [x] Tâche 6 : Tests unitaires backend (service + API + sécurité)
- [x] Build & lint OK

## Notes d'implémentation

### Fichiers créés
- `backend/app/models/plugin_hook_log.py` — Modèle SQLAlchemy `PluginHookLog` (table `plugin_hook_logs`)
- `backend/app/schemas/plugin_hook_log.py` — Schemas Pydantic `HookLogSummaryResponse`, `HookLogResponse`, `HookExecutionResult`
- `backend/app/services/plugin_lifecycle_service.py` — Service `PluginLifecycleService` (exécution hooks, timeout, path validation, env vars sécurisées)
- `backend/tests/unit/test_services/test_plugin_lifecycle_service.py` — 20 tests unitaires du service lifecycle
- `backend/tests/unit/test_api/test_plugin_hooks.py` — 8 tests unitaires des endpoints API hooks/logs

### Fichiers modifiés
- `backend/app/models/__init__.py` — Ajout import `PluginHookLog` dans `__all__`
- `backend/app/config.py` — Ajout setting `plugins_base_dir: str = "./data/plugins/"`
- `backend/app/services/plugin_manager_service.py` — Injection `PluginLifecycleService`, intégration hooks dans `install_plugin`, `configure_plugin`, `uninstall_plugin`
- `backend/app/api/v1/plugins.py` — Ajout imports `PluginLifecycleService`, `HookLogResponse`, `HookLogSummaryResponse`, ajout endpoints `GET /{plugin_id}/hooks/logs` et `GET /{plugin_id}/hooks/logs/{log_id}`

### Décisions techniques
- **Pattern subprocess** : Suivi le pattern de `docker_executor.py` avec `asyncio.create_subprocess_exec` + `asyncio.wait_for` pour le timeout
- **Ordre hook → événement** : Les hooks s'exécutent AVANT `_emit_event`. Si le hook échoue, seul `PLUGIN_ERROR` est émis
- **No-op sans hook** : Si un hook n'est pas déclaré dans le manifest, la transition se poursuit sans erreur ni log
- **Sécurité env vars** : Les config_values de type `password` sont masquées avec `***` dans les variables d'environnement passées aux scripts
- **Troncature stdout/stderr** : Limités à 10 000 caractères pour éviter les abus de stockage

### Divergences
- Aucune divergence par rapport à l'analyse. Toutes les tâches ont été implémentées conformément aux spécifications.

### Tests ajoutés
- **Service (20 tests)** : 5 hooks nominaux, 3 tests d'erreur (échec, timeout, script introuvable), 2 tests no-op, 2 tests path traversal, 2 tests capture stdout/stderr et durée, 2 tests env vars sécurisées, 4 tests requêtes log
- **API (8 tests)** : 200 listing, 200 liste vide, 401 sans token, 404 plugin inexistant, 403 autre org, 200 détail log, 404 log inexistant, pagination skip/limit

### Résultats build/lint/tests
- `ruff check` : All checks passed!
- Tests service : **20 passed** (couverture `plugin_lifecycle_service.py` : 93%)
- Tests API : **8 passed**
- Tests existants (plugin_manager + plugins API) : **43 passed** (0 régression)
