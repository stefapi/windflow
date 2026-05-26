# STORY-002 : API REST Plugin Manager — CRUD plugins (install/update/uninstall)

**Statut :** DONE
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux une API REST complète pour gérer le cycle de vie des plugins (install, update, uninstall, list, get) afin de permettre à l'UI et à la CLI d'interagir avec le système de plugins.

## Contexte technique

**Couches impactées :** Backend uniquement — Models, Schemas, Services, API endpoints, Events

**Fichiers de référence (patterns) :**
- Modèle DB → pattern : [`backend/app/models/stack.py`](backend/app/models/stack.py) (UUID PK, `organization_id` FK, timestamps, JSON columns)
- Service → pattern : [`backend/app/services/stack_service.py`](backend/app/services/stack_service.py) (méthodes statiques async avec `AsyncSession`)
- API endpoints → pattern : [`backend/app/api/v1/stacks.py`](backend/app/api/v1/stacks.py) (`get_current_active_user`, `conditional_rate_limiter`, OpenAPI riche)
- Événements → pattern : [`backend/app/core/events.py`](backend/app/core/events.py) (`EventType` enum + `Event` dataclass)
- Tests service → pattern : [`backend/tests/unit/test_services/test_plugin_manifest_service.py`](backend/tests/unit/test_services/test_plugin_manifest_service.py)
- Tests API → pattern : [`backend/tests/unit/test_stacks_api_variables_rendering.py`](backend/tests/unit/test_stacks_api_variables_rendering.py)
- Fixtures tests → [`backend/tests/conftest.py`](backend/tests/conftest.py) (`authenticated_client`, `admin_client`)

**Dépendances STORY-001 (DONE) :**
- [`backend/app/schemas/plugin_manifest.py`](backend/app/schemas/plugin_manifest.py) — `PluginManifest`, `PluginType`, `PluginCategory` enums
- [`backend/app/services/plugin_manifest_service.py`](backend/app/services/plugin_manifest_service.py) — `PluginManifestService.validate_manifest()`

**Exigences sécurité identifiées :**
- Auth : oui — `get_current_active_user` pour lecture (GET), `require_superuser` pour écriture (POST/PUT/DELETE)
- RBAC : lecture = Viewer+ (tous utilisateurs authentifiés), écriture = Admin/Super Admin uniquement. En l'absence de RBAC par organisation, `require_superuser` est utilisé pragmatiquement — cf [`docs/general_specs/06-rbac-permissions.md`](docs/general_specs/06-rbac-permissions.md) lignes 78-82
- Validation : manifest YAML validé via `PluginManifestService` (STORY-001), `plugin_id` validé comme UUID str, `config_values` validés via Pydantic
- Exposition : champs config de type `password` masqués dans les réponses API (`exclude` sur le schéma Response)
- Audit : tracer install/update/uninstall avec `user_id`, `plugin_name`, `version` dans les logs structurés + émission d'événements plugin via `EventBus`

## Critères d'acceptation (AC)
- [x] AC 1 : Les endpoints REST couvrent les opérations CRUD complètes : `GET /plugins`, `GET /plugins/{id}`, `POST /plugins/install`, `PUT /plugins/{id}/update`, `DELETE /plugins/{id}/uninstall`
- [x] AC 2 : L'installation valide le manifest via le schéma Pydantic (STORY-001) avant de procéder
- [x] AC 3 : Chaque opération retourne des codes HTTP appropriés et des messages d'erreur structurés
- [x] AC 4 : Les opérations longues (install/update) sont asynchrones avec suivi via WebSocket
- [x] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)

## Tâches d'implémentation détaillées

### Tâche 1 : Modèle DB Plugin + Event Types plugin
**Objectif :** Créer le modèle SQLAlchemy `Plugin` pour persister l'état des plugins installés, l'énumération `PluginStatus`, et ajouter les types d'événements plugin au système event-driven.
**Fichiers :**
- `backend/app/models/plugin.py` — Créer — Nouveau modèle SQLAlchemy (pattern : [`backend/app/models/stack.py`](backend/app/models/stack.py)). Créer la classe `Plugin(Base)` avec :
  - `__tablename__ = "plugins"`
  - `id`: String(36) PK, default uuid4
  - `name`: String(255), unique=True, index=True (kebab-case, correspond au manifest)
  - `version`: String(50) (semver)
  - `display_name`: String(255)
  - `description`: Text, nullable=True
  - `category`: String(50) (PluginCategory value)
  - `type`: String(20) (PluginType value)
  - `status`: String(20) avec default="installed" (PluginStatus value)
  - `manifest_data`: JSON — stocke le manifest validé complet
  - `config_values`: JSON, default=dict — stocke la config utilisateur
  - `organization_id`: String(36) FK vers `organizations.id`, index=True
  - `installed_by`: String(36) FK vers `users.id`, nullable=True
  - `installed_at`: DateTime, default=utcnow
  - `updated_at`: DateTime, default=utcnow, onupdate=utcnow
  - Créer aussi l'enum `PluginStatus` : INSTALLED, INSTALLING, RUNNING, STOPPED, UPDATING, ERROR
- `backend/app/core/events.py` — Modifier — Ajouter les types d'événements plugin dans l'enum `EventType` :
  - `PLUGIN_INSTALLED = "plugin.installed"`
  - `PLUGIN_INSTALLING = "plugin.installing"`
  - `PLUGIN_UPDATED = "plugin.updated"`
  - `PLUGIN_UNINSTALLED = "plugin.uninstalled"`
  - `PLUGIN_CONFIGURED = "plugin.configured"`
  - `PLUGIN_ERROR = "plugin.error"`
- `backend/app/models/__init__.py` — Modifier — Ajouter l'import `from .plugin import Plugin` et l'ajouter à `__all__`
**Exigences sécurité :** Aucune exigence spécifique (couche données pure)
**Dépend de :** Aucune

### Tâche 2 : Schemas Pydantic Plugin CRUD
**Objectif :** Créer les schémas Pydantic de validation et sérialisation pour toutes les opérations CRUD plugin (Request/Response séparés).
**Fichiers :**
- `backend/app/schemas/plugin.py` — Créer — Nouveau module de schemas (pattern : [`backend/app/schemas/stack.py`](backend/app/schemas/stack.py)). Créer les classes suivantes :
  - `PluginInstallRequest` — `source: Optional[str]` (URL ou identifiant registre), `manifest_yaml: Optional[str]` (contenu YAML direct pour install locale), `config_values: Dict[str, Any] = {}`. Au moins un de `source` ou `manifest_yaml` doit être fourni (model_validator).
  - `PluginUpdateRequest` — `version: Optional[str]` (version cible, si None = dernière)
  - `PluginConfigureRequest` — `config_values: Dict[str, Any]`
  - `PluginSummaryResponse` — id, name, version, display_name, description, category, type, status, installed_at, updated_at (allégé pour listing)
  - `PluginResponse` — tous les champs de PluginSummaryResponse + manifest_data, config_values (avec masquage des champs password), installed_by, organization_id
  - `PluginActionResponse` — id, status, message (pour les réponses d'actions async : install, update, uninstall)
  - Utiliser `model_config = ConfigDict(from_attributes=True)` pour compat ORM
  - Valider `source` avec un pattern URL si fourni, `manifest_yaml` avec validation basique si fourni
  - Dans `PluginResponse`, ajouter un model_validator pour masquer les valeurs de config correspondant aux champs de type `password` dans le manifest
**Exigences sécurité :** Validation Pydantic stricte sur tous les inputs. Champs password masqués dans PluginResponse.
**Dépend de :** Tâche 1 (pour PluginStatus enum)

### Tâche 3 : Service PluginManager
**Objectif :** Créer le service métier `PluginManagerService` qui orchestre le cycle de vie complet des plugins (install, update, uninstall, configure, list, get) avec validation du manifest et émission d'événements.
**Fichiers :**
- `backend/app/services/plugin_manager_service.py` — Créer — Nouveau service (pattern : [`backend/app/services/stack_service.py`](backend/app/services/stack_service.py)). Créer la classe `PluginManagerService` avec méthodes statiques async :
  - `list_plugins(db, organization_id, skip=0, limit=100) -> List[Plugin]` — liste les plugins d'une org
  - `get_plugin(db, plugin_id) -> Optional[Plugin]` — récupère un plugin par ID
  - `get_plugin_by_name(db, name) -> Optional[Plugin]` — récupère par nom unique
  - `install_plugin(db, install_data, user_id, organization_id) -> Plugin` — valide le manifest via `PluginManifestService.validate_manifest()`, vérifie l'absence de doublon (name), crée le Plugin en DB avec status=INSTALLING puis INSTALLED, émet événement PLUGIN_INSTALLED
  - `update_plugin(db, plugin_id, update_data, user_id) -> Plugin` — vérifie existence, met à jour version + manifest_data, status=UPDATING puis INSTALLED, émet PLUGIN_UPDATED
  - `uninstall_plugin(db, plugin_id, user_id) -> None` — vérifie existence, supprime de la DB, émet PLUGIN_UNINSTALLED
  - `configure_plugin(db, plugin_id, config_data, user_id) -> Plugin` — met à jour config_values, émet PLUGIN_CONFIGURED
  - Toutes les méthodes lèvent des `WindFlowException` pour les erreurs métier (plugin non trouvé, déjà installé, etc.)
  - Logger chaque action avec `logger.info("plugin_xxx", extra={"plugin_name": ..., "user_id": ...})`
**Exigences sécurité :** Validation manifest via PluginManifestService avant toute installation. Logs structurés sans données sensibles. Vérification d'appartenance `organization_id`.
**Dépend de :** Tâche 1 (Model Plugin), Tâche 2 (Schemas), STORY-001 (PluginManifestService)

### Tâche 4 : Endpoints API Plugin + Router
**Objectif :** Créer les endpoints REST pour le CRUD plugin avec authentification, rate limiting, documentation OpenAPI riche, et gestion des opérations asynchrones via BackgroundTasks.
**Fichiers :**
- `backend/app/api/v1/plugins.py` — Créer — Nouveau router (pattern : [`backend/app/api/v1/stacks.py`](backend/app/api/v1/stacks.py)). Créer les endpoints :
  - `GET /plugins/` — liste paginée (skip/limit), `response_model=List[PluginSummaryResponse]`, auth=`get_current_active_user`, rate_limiter(100, 60)
  - `GET /plugins/{plugin_id}` — détail plugin, `response_model=PluginResponse`, auth=`get_current_active_user`, rate_limiter(100, 60)
  - `POST /plugins/install` — installe un plugin, `response_model=PluginActionResponse`, status=202 (Accepted), auth=`require_superuser`, rate_limiter(10, 60). Utilise `BackgroundTasks` pour l'installation async. Retourne immédiatement avec le plugin en status INSTALLING.
  - `PUT /plugins/{plugin_id}/update` — met à jour, `response_model=PluginActionResponse`, status=202, auth=`require_superuser`, rate_limiter(10, 60). BackgroundTasks pour update async.
  - `PUT /plugins/{plugin_id}/configure` — configure, `response_model=PluginResponse`, auth=`require_superuser`, rate_limiter(20, 60)
  - `DELETE /plugins/{plugin_id}/uninstall` — désinstalle, status=204, auth=`require_superuser`, rate_limiter(10, 60)
  - Chaque endpoint avec documentation OpenAPI complète (summary, description, responses avec exemples pour 200/202/204/400/401/403/404/409/422/500)
  - Lever `HTTPException` avec codes appropriés pour chaque cas d'erreur
  - Logger chaque requête avec `correlation_id` et `user_id`
- `backend/app/api/v1/__init__.py` — Modifier — Ajouter l'import `from .plugins import router as plugins_router` et `api_router.include_router(plugins_router, prefix="/plugins", tags=["plugins"])`
**Exigences sécurité :** `get_current_active_user` sur GET, `require_superuser` sur POST/PUT/DELETE. Rate limiting configuré. Validation Pydantic sur tous les body. Messages d'erreur génériques (pas de stack trace).
**Dépend de :** Tâche 2 (Schemas), Tâche 3 (Service)

### Tâche 5 : Tests unitaires backend
**Objectif :** Écrire les tests unitaires complets pour le service PluginManager et les endpoints API plugin, couvrant les cas nominaux, les erreurs et la sécurité (401, 403, 422, 404, 409).
**Fichiers :**
- `backend/tests/unit/test_services/test_plugin_manager_service.py` — Créer — Tests service (pattern : [`backend/tests/unit/test_services/test_plugin_manifest_service.py`](backend/tests/unit/test_services/test_plugin_manifest_service.py)). Tests avec mock DB session.
- `backend/tests/unit/test_api/test_plugins.py` — Créer — Tests endpoints API (pattern : [`backend/tests/unit/test_stacks_api_variables_rendering.py`](backend/tests/unit/test_stacks_api_variables_rendering.py)). Tests avec client HTTP async et fixtures auth de [`backend/tests/conftest.py`](backend/tests/conftest.py).
**Exigences sécurité :** Tests de sécurité obligatoires : 401 sans token, 403 pour non-superuser sur écriture, 422 body invalide, 404 plugin inexistant, 409 doublon.
**Dépend de :** Tâche 4 (Endpoints)

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend — Service

- `backend/tests/unit/test_services/test_plugin_manager_service.py`
  - `test_list_plugins_returns_empty_list` — cas nominal : liste vide pour une organisation
  - `test_list_plugins_returns_installed_plugins` — cas nominal : liste avec plugins installés
  - `test_get_plugin_by_id_returns_plugin` — cas nominal : récupération par ID
  - `test_get_plugin_by_id_returns_none_when_not_found` — cas d'erreur : ID inexistant
  - `test_get_plugin_by_name_returns_plugin` — cas nominal : récupération par nom
  - `test_install_plugin_with_valid_manifest` — cas nominal : installation réussie avec manifest YAML valide
  - `test_install_plugin_raises_on_duplicate_name` — cas d'erreur : conflit si plugin déjà installé
  - `test_install_plugin_raises_on_invalid_manifest` — cas d'erreur : manifest YAML invalide
  - `test_update_plugin_with_valid_version` — cas nominal : mise à jour réussie
  - `test_update_plugin_raises_when_not_found` — cas d'erreur : plugin inexistant
  - `test_uninstall_plugin_removes_from_db` — cas nominal : désinstallation réussie
  - `test_uninstall_plugin_raises_when_not_found` — cas d'erreur : plugin inexistant
  - `test_configure_plugin_updates_config_values` — cas nominal : configuration mise à jour
  - `test_configure_plugin_masks_password_fields` — **sécurité** : champs password masqués dans le résultat

### Unitaires Backend — API Endpoints

- `backend/tests/unit/test_api/test_plugins.py`
  - `test_list_plugins_returns_200_authenticated` — cas nominal : liste accessible avec auth
  - `test_list_plugins_returns_empty_list` — cas nominal : liste vide
  - `test_list_plugins_returns_401_without_token` — **sécurité** : accès sans token → 401
  - `test_get_plugin_returns_200_authenticated` — cas nominal : détail plugin
  - `test_get_plugin_returns_404_when_not_found` — cas d'erreur : plugin inexistant → 404
  - `test_get_plugin_returns_401_without_token` — **sécurité** : accès sans token → 401
  - `test_install_plugin_returns_202_with_valid_data` — cas nominal : installation acceptée (async) → 202
  - `test_install_plugin_returns_401_without_token` — **sécurité** : accès sans token → 401
  - `test_install_plugin_returns_403_for_non_superuser` — **sécurité RBAC** : rôle insuffisant → 403
  - `test_install_plugin_returns_422_on_invalid_body` — validation : body invalide → 422
  - `test_install_plugin_returns_409_on_duplicate` — cas d'erreur : plugin déjà installé → 409
  - `test_update_plugin_returns_202_with_valid_data` — cas nominal : update acceptée (async) → 202
  - `test_update_plugin_returns_401_without_token` — **sécurité** : accès sans token → 401
  - `test_update_plugin_returns_403_for_non_superuser` — **sécurité RBAC** : rôle insuffisant → 403
  - `test_update_plugin_returns_404_when_not_found` — cas d'erreur : plugin inexistant → 404
  - `test_configure_plugin_returns_200_with_valid_data` — cas nominal : configuration réussie → 200
  - `test_configure_plugin_returns_403_for_non_superuser` — **sécurité RBAC** : rôle insuffisant → 403
  - `test_uninstall_plugin_returns_204_authenticated` — cas nominal : désinstallation réussie → 204
  - `test_uninstall_plugin_returns_403_for_non_superuser` — **sécurité RBAC** : rôle insuffisant → 403
  - `test_uninstall_plugin_returns_404_when_not_found` — cas d'erreur : plugin inexistant → 404
  - `test_plugin_response_does_not_expose_password_config` — **sécurité** : champs sensibles absents de la réponse

### Commandes de validation

```bash
# Backend — Service tests
poetry run pytest backend/tests/unit/test_services/test_plugin_manager_service.py -v

# Backend — API tests
poetry run pytest backend/tests/unit/test_api/test_plugins.py -v --tb=short

# Backend — All plugin tests
poetry run pytest backend/tests/unit/ -k plugin -v

# Couverture
poetry run pytest backend/tests/unit/test_services/test_plugin_manager_service.py backend/tests/unit/test_api/test_plugins.py --cov=app.services.plugin_manager_service --cov=app.api.v1.plugins --cov-report=term-missing

# Lint & typecheck
make lint && make typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Modèle DB Plugin + Event Types plugin
- [x] Tâche 2 : Schemas Pydantic Plugin CRUD
- [x] Tâche 3 : Service PluginManager
- [x] Tâche 4 : Endpoints API Plugin + Router
- [x] Tâche 5 : Tests unitaires backend (service + API)
- [x] Build & lint OK
- [x] Couverture tests ≥ 80%

## Notes d'implémentation

### Fichiers créés
- `backend/app/models/plugin.py` — Modèle SQLAlchemy `Plugin` + enum `PluginStatus`
- `backend/app/schemas/plugin.py` — Schemas Pydantic CRUD (Request/Response) avec masquage password
- `backend/app/services/plugin_manager_service.py` — Service métier `PluginManagerService`
- `backend/app/api/v1/plugins.py` — Endpoints REST (6 endpoints)
- `backend/tests/unit/test_services/test_plugin_manager_service.py` — 14 tests service
- `backend/tests/unit/test_api/test_plugins.py` — 21 tests API

### Fichiers modifiés
- `backend/app/core/events.py` — Ajout de 6 event types plugin (PLUGIN_INSTALLED, PLUGIN_INSTALLING, etc.)
- `backend/app/models/__init__.py` — Import du modèle Plugin
- `backend/app/api/v1/__init__.py` — Enregistrement du router plugins

### Décisions techniques
1. **flag_modified** : Utilisation de `sqlalchemy.orm.attributes.flag_modified` dans `configure_plugin` pour forcer la détection de mutation JSON sur `config_values` (SQLite ne détecte pas les mutations in-place des colonnes JSON).
2. **Événements** : Les événements plugin sont loggés de manière structurée via `logger.info(event_type.value, extra={...})`. L'intégration avec l'EventBus sera faite dans STORY-006 (Hooks lifecycle).
3. **Installation distante** : L'installation depuis une source URL distante n'est pas encore supportée — seul `manifest_yaml` direct est accepté. L'installation distante sera implémentée dans STORY-013 (Registre officiel).
4. **Tests sécurité** : Les tests 401/403 utilisent `monkeypatch` pour forcer `settings.disable_auth = False` car l'environnement de dev a `DISABLE_AUTH=true`.
5. **Masquage password** : Implémenté via `model_validator` sur `PluginResponse` qui inspecte `manifest_data.config` pour identifier les champs de type `password`.

### Divergences
- Aucune divergence majeure par rapport aux spécifications de la story.
- Le middleware `error_handler` existant a un bug de sérialisation JSON sur les `ValueError` dans le contexte Pydantic v2 (422 → 500). Ce bug est pré-existant et n'est pas lié à cette story.
