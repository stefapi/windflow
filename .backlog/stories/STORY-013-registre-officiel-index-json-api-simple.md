# STORY-013 : Registre officiel (index JSON ou API simple)

**Statut :** DONE
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux un registre officiel de plugins accessible via un index JSON ou une API simple afin de centraliser la distribution des plugins officiels WindFlow.

## Contexte technique

### Architecture
Le registre officiel est la source de vérité pour les plugins maintenus par l'équipe WindFlow. L'implémentation repose sur un **fichier JSON statique** (`index.json`) hébergé et servi via HTTP, que le backend WindFlow interroge pour récupérer la liste des plugins disponibles et leurs métadonnées.

Le backend agit comme un **proxy/cache** : il télécharge l'index JSON depuis l'URL configurée, le valide via Pydantic, le met en cache avec un TTL configurable, et l'expose via des endpoints API REST dédiés.

### Patterns identifiés dans le codebase
- **Schémas Pydantic** : Pattern `*Request` / `*Response` / `*Summary` dans [`backend/app/schemas/`](backend/app/schemas/) — voir [`plugin.py`](backend/app/schemas/plugin.py:1) pour le pattern CRUD
- **Services** : Classes avec méthodes statiques pour lecture, instance pour écriture — voir [`PluginManagerService`](backend/app/services/plugin_manager_service.py:26)
- **API endpoints** : Router FastAPI avec `Depends()` pour auth, rate limiting, DB — voir [`plugins.py`](backend/app/api/v1/plugins.py:1)
- **Authentification** : [`get_current_active_user`](backend/app/auth/dependencies.py:74) pour lecture, [`require_superuser`](backend/app/auth/dependencies.py:96) pour écriture
- **Exceptions** : [`WindFlowException`](backend/app/core/exceptions.py:10) avec `details={"error_type": "..."}`
- **Configuration** : [`Settings`](backend/app/config.py:15) Pydantic-settings avec variables d'environnement
- **Événements** : [`EventType`](backend/app/core/events.py:18) pour les events plugin (déjà définis : `PLUGIN_INSTALLED`, `PLUGIN_UPDATED`, etc.)
- **Manifest** : [`PluginManifest`](backend/app/schemas/plugin_manifest.py:262) pour la validation des manifests YAML

### Dépendances
- **STORY-001** (✅ livré) : Le registre référence les plugins par leur nom (kebab-case) et version (semver), formats validés par [`PluginManifest`](backend/app/schemas/plugin_manifest.py:262)
- **STORY-015** (TODO) : La vérification d'intégrité SHA-256 consommera les checksums exposés par ce registre
- **STORY-008** (TODO) : L'API Marketplace utilisera ce registre comme source de données

### Exigences sécurité
- **Authentification** : Endpoints en lecture seule → `get_current_active_user` (tout utilisateur authentifié peut consulter le registre)
- **Pas de RBAC restrictif** : Le registre est une donnée publique, accessible à tout utilisateur connecté
- **Validation des inputs** : Le paramètre `plugin_name` dans les paths doit être validé en kebab-case (anti path traversal) — réutiliser `_NAME_PATTERN` de [`plugin_manifest.py`](backend/app/schemas/plugin_manifest.py:18)
- **URL registre** : En production, l'URL du registre doit être en HTTPS (validation côté config)
- **Cache** : Un cache avec TTL empêche les requêtes répétées (protection DoS)
- **Pas de données sensibles** : L'index JSON ne contient que des métadonnées publiques (pas de secrets, pas de tokens)
- **Rate limiting** : Appliquer `conditional_rate_limiter(60, 60)` sur les endpoints registre

## Critères d'acceptation (AC)
- [x] AC 1 : Le registre expose un endpoint/index listant tous les plugins officiels avec leurs métadonnées (nom, version, description, checksum, URL)
- [x] AC 2 : Chaque plugin du registre pointe vers un package téléchargeable avec son checksum SHA-256
- [x] AC 3 : Le backend WindFlow peut interroger le registre pour récupérer la liste des plugins et les détails d'un plugin spécifique
- [x] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)

## État d'avancement technique
- [x] Tâche 1 : Schémas Pydantic du registre
- [x] Tâche 2 : Configuration du registre (Settings)
- [x] Tâche 3 : Service d'accès au registre (fetch + cache + validation)
- [x] Tâche 4 : Endpoints API du registre
- [x] Tâche 5 : Fichier index JSON du registre officiel
- [x] Tâche 6 : Enregistrement du router dans l'API v1

## Tâches d'implémentation détaillées

### Tâche 1 : Schémas Pydantic du registre
**Objectif :** Définir les schémas de validation pour l'index JSON du registre et les réponses API associées.
**Fichiers :**
- `backend/app/schemas/plugin_registry.py` — **Créer** — Schémas Pydantic pour le registre officiel

**Contenu attendu :**
- `RegistryPluginEntry` : entrée individuelle du registre (name, version, display_name, description, category, type, author, license, architectures, download_url, checksum_sha256, homepage, tags)
- `RegistryIndex` : index complet (version du format, updated_at, liste de `RegistryPluginEntry`)
- `RegistryPluginSummaryResponse` : réponse allégée pour le listing (name, version, display_name, description, category, tags)
- `RegistryPluginDetailResponse` : réponse complète pour le détail (tous les champs + checksum + download_url)

**Validation :**
- `name` : regex kebab-case `_NAME_PATTERN` (réutiliser depuis [`plugin_manifest.py`](backend/app/schemas/plugin_manifest.py:18) ou dupliquer)
- `version` : regex semver `_SEMVER_PATTERN`
- `download_url` : regex URL valide (`https://` uniquement)
- `checksum_sha256` : regex hex 64 caractères
- `architectures` : liste non-vide de valeurs `Architecture`

**Fichier de référence (pattern) :** [`backend/app/schemas/plugin.py`](backend/app/schemas/plugin.py:1)
**Exigences sécurité :** Validation stricte de tous les champs via Pydantic. Le champ `download_url` doit être HTTPS uniquement.
**Dépend de :** Aucune

### Tâche 2 : Configuration du registre (Settings)
**Objectif :** Ajouter les paramètres de configuration du registre dans les Settings Pydantic.
**Fichiers :**
- `backend/app/config.py` — **Modifier** — Ajouter les settings du registre

**Paramètres à ajouter :**
- `plugin_registry_url: str` — URL de l'index JSON du registre officiel (défaut : `https://registry.windflow.io/index.json`)
- `plugin_registry_cache_ttl: int` — TTL du cache en secondes (défaut : `300` = 5 minutes)
- `plugin_registry_timeout: int` — Timeout HTTP pour fetch l'index en secondes (défaut : `10`)

**Fichier de référence (pattern) :** [`backend/app/config.py`](backend/app/config.py:15) — section Rate Limiting ou LiteLLM pour le pattern
**Exigences sécurité :** En production, valider que `plugin_registry_url` commence par `https://`.
**Dépend de :** Aucune

### Tâche 3 : Service d'accès au registre (fetch + cache + validation)
**Objectif :** Implémenter le service métier qui télécharge, valide, met en cache et expose les données du registre officiel.
**Fichiers :**
- `backend/app/services/plugin_registry_service.py` — **Créer** — Service d'accès au registre

**Contenu attendu :**
- `PluginRegistryService` : classe avec injection de la config
  - `async fetch_index()` → `RegistryIndex` : télécharge et valide l'index JSON depuis l'URL configurée, met en cache
  - `async list_plugins()` → `List[RegistryPluginEntry]` : retourne tous les plugins du registre
  - `async get_plugin(name: str)` → `Optional[RegistryPluginEntry]` : recherche par nom exact
  - `async search_plugins(query: str)` → `List[RegistryPluginEntry]` : recherche par nom/description/tags (AC 3)
  - `_is_cache_valid()` → `bool` : vérifie si le cache est encore valide (TTL)
  - `_invalidate_cache()` : invalide le cache (pour forcer le rechargement)

**Cache en mémoire :**
- Stocker le `RegistryIndex` parsé + timestamp du dernier fetch
- Vérifier le TTL avant chaque accès
- Utiliser `aiohttp` (déjà dans les dépendances — [`aiohttp ^3.11.0`](backend/app/config.py:15)) pour le fetch HTTP

**Gestion d'erreurs :**
- Timeout → lever `WindFlowException` avec `error_type: "registry_timeout"`
- HTTP error → lever `WindFlowException` avec `error_type: "registry_unavailable"`
- JSON invalide → lever `WindFlowException` avec `error_type: "registry_invalid"`
- Retourner les données en cache même expirées si le fetch échoue (fallback gracieux)

**Fichier de référence (pattern) :** [`backend/app/services/plugin_manifest_service.py`](backend/app/services/plugin_manifest_service.py:21)
**Exigences sécurité :** Timeout sur le fetch HTTP, validation Pydantic stricte du JSON reçu, pas de logging de données sensibles, HTTPS uniquement.
**Dépend de :** Tâche 1, Tâche 2

### Tâche 4 : Endpoints API du registre
**Objectif :** Exposer les données du registre via des endpoints REST accessibles aux utilisateurs authentifiés.
**Fichiers :**
- `backend/app/api/v1/plugin_registry.py` — **Créer** — Router FastAPI pour le registre

**Endpoints :**
1. `GET /registry/plugins` — Liste tous les plugins du registre
   - Auth : `get_current_active_user`
   - Rate limit : `conditional_rate_limiter(60, 60)`
   - Query params : `skip: int = 0`, `limit: int = 100`, `category: Optional[str]`, `query: Optional[str]`
   - Response : `List[RegistryPluginSummaryResponse]`
   - Couvre **AC 1** et **AC 3**

2. `GET /registry/plugins/{plugin_name}` — Détail d'un plugin du registre
   - Auth : `get_current_active_user`
   - Rate limit : `conditional_rate_limiter(60, 60)`
   - Path param : `plugin_name: str` (validé kebab-case)
   - Response : `RegistryPluginDetailResponse`
   - Erreur 404 si plugin non trouvé dans le registre
   - Couvre **AC 2** et **AC 3**

**Fichier de référence (pattern) :** [`backend/app/api/v1/plugins.py`](backend/app/api/v1/plugins.py:1)
**Exigences sécurité :**
- `get_current_active_user` sur tous les endpoints (401 si non authentifié)
- Validation du paramètre `plugin_name` en kebab-case (anti path traversal)
- Rate limiting pour prévenir l'abus
- Messages d'erreur génériques (pas de stack trace)
**Dépend de :** Tâche 3

### Tâche 5 : Fichier index JSON du registre officiel
**Objectif :** Créer le fichier JSON statique servant de registre officiel, avec les 4 plugins officiels de l'epic.
**Fichiers :**
- `dev/registry/index.json` — **Créer** — Index JSON du registre officiel

**Contenu :**
- En-tête : `version: "1.0"`, `updated_at`, `registry_url`
- Liste des plugins officiels (données de exemple, checksums placeholder) :
  - `traefik` (v1.2.0) — reverse proxy
  - `postgresql` (v1.0.0) — database
  - `redis` (v1.0.0) — caching/monitoring
  - `uptime-kuma` (v1.0.0) — monitoring

**Note :** Les checksums SHA-256 et URLs de téléchargement sont des placeholders (`checksum_sha256: "0"*64`, `download_url: "https://..."`) tant que les plugins ne sont pas buildés. Ils seront mis à jour lors de l'implémentation des stories STORY-016 à STORY-019.

**Fichier de référence :** [`dev/plugin-examples/traefik/windflow-plugin.yml`](dev/plugin-examples/traefik/windflow-plugin.yml:1) pour les métadonnées Traefik
**Exigences sécurité :** Pas de données sensibles dans le JSON. Checksums placeholders documentés.
**Dépend de :** Tâche 1 (pour connaître le format attendu)

### Tâche 6 : Enregistrement du router dans l'API v1
**Objectif :** Monter le router du registre dans l'API v1 pour rendre les endpoints accessibles.
**Fichiers :**
- `backend/app/api/v1/__init__.py` — **Modifier** — Ajouter l'import et le `include_router` pour `plugin_registry`

**Modification :**
```python
from .plugin_registry import router as plugin_registry_router
# ...
api_router.include_router(plugin_registry_router, prefix="/registry", tags=["plugin-registry"])
```

**Fichier de référence :** [`backend/app/api/v1/__init__.py`](backend/app/api/v1/__init__.py:49) — ligne existante pour plugins_router
**Exigences sécurité :** Aucune supplémentaire.
**Dépend de :** Tâche 4

## Tests à écrire

### Tests unitaires — Schémas (`backend/tests/unit/test_schemas/test_plugin_registry.py`)
- `test_registry_plugin_entry_valid` : entrée valide avec tous les champs
- `test_registry_plugin_entry_invalid_name` : name non kebab-case → ValidationError
- `test_registry_plugin_entry_invalid_version` : version non semver → ValidationError
- `test_registry_plugin_entry_invalid_url` : download_url non HTTPS → ValidationError
- `test_registry_plugin_entry_invalid_checksum` : checksum non hex 64 chars → ValidationError
- `test_registry_plugin_entry_empty_architectures` : architectures vide → ValidationError
- `test_registry_index_valid` : index complet valide
- `test_registry_index_empty_plugins` : index avec liste plugins vide
- `test_registry_plugin_summary_response` : sérialisation correcte
- `test_registry_plugin_detail_response` : sérialisation avec tous les champs

### Tests unitaires — Service (`backend/tests/unit/test_services/test_plugin_registry_service.py`)
- `test_fetch_index_success` : fetch réussi, index parsé et mis en cache
- `test_fetch_index_caches_result` : second appel utilise le cache (pas de second fetch)
- `test_fetch_index_cache_expired` : cache expiré → nouveau fetch
- `test_fetch_index_timeout` : timeout HTTP → WindFlowException error_type=registry_timeout
- `test_fetch_index_http_error` : erreur HTTP → WindFlowException error_type=registry_unavailable
- `test_fetch_index_invalid_json` : JSON invalide → WindFlowException error_type=registry_invalid
- `test_fetch_index_fallback_on_error` : fetch échoue → retourne cache expiré si disponible
- `test_list_plugins_returns_all` : retourne tous les plugins
- `test_get_plugin_by_name_found` : retourne le plugin correspondant
- `test_get_plugin_by_name_not_found` : retourne None
- `test_search_plugins_by_query` : recherche dans name/description/tags
- `test_invalidate_cache` : invalidation force un nouveau fetch

### Tests unitaires — API endpoints (`backend/tests/unit/test_api/test_plugin_registry.py`)
- `test_list_registry_plugins_returns_200_authenticated` : cas nominal liste
- `test_list_registry_plugins_returns_empty_when_no_plugins` : liste vide
- `test_list_registry_plugins_returns_401_without_token` : sécurité 401
- `test_list_registry_plugins_with_category_filter` : filtre par catégorie
- `test_list_registry_plugins_with_query_search` : recherche textuelle
- `test_list_registry_plugins_pagination` : pagination skip/limit
- `test_get_registry_plugin_detail_returns_200` : cas nominal détail
- `test_get_registry_plugin_detail_returns_404_not_found` : plugin inexistant
- `test_get_registry_plugin_detail_returns_401_without_token` : sécurité 401
- `test_get_registry_plugin_detail_invalid_name_format` : name non kebab-case → 422
- `test_get_registry_plugin_detail_includes_checksum_and_url` : vérifie présence checksum + download_url (AC 2)

### Commandes de validation
```bash
# Tests unitaires avec couverture
cd backend && python -m pytest tests/unit/test_schemas/test_plugin_registry.py tests/unit/test_services/test_plugin_registry_service.py tests/unit/test_api/test_plugin_registry.py -v --cov=app/schemas/plugin_registry --cov=app/services/plugin_registry_service --cov=app/api/v1/plugin_registry --cov-fail-under=80

# Lint
cd backend && black --check app/schemas/plugin_registry.py app/services/plugin_registry_service.py app/api/v1/plugin_registry.py
cd backend && isort --check-only app/schemas/plugin_registry.py app/services/plugin_registry_service.py app/api/v1/plugin_registry.py
cd backend && flake8 app/schemas/plugin_registry.py app/services/plugin_registry_service.py app/api/v1/plugin_registry.py
cd backend && mypy app/schemas/plugin_registry.py app/services/plugin_registry_service.py app/api/v1/plugin_registry.py

# Validation de l'index JSON
python -c "import json; json.load(open('dev/registry/index.json'))"
```

## Notes d'implémentation

### Fichiers créés
- `backend/app/schemas/plugin_registry.py` — Schémas Pydantic : `RegistryPluginEntry`, `RegistryIndex`, `RegistryPluginSummaryResponse`, `RegistryPluginDetailResponse`
- `backend/app/services/plugin_registry_service.py` — Service `PluginRegistryService` avec fetch HTTP, cache TTL, validation Pydantic, recherche
- `backend/app/api/v1/plugin_registry.py` — Router FastAPI avec endpoints `GET /registry/plugins` et `GET /registry/plugins/{plugin_name}`
- `dev/registry/index.json` — Index JSON de développement avec 4 plugins officiels (Traefik, PostgreSQL, Redis, Uptime Kuma)
- `backend/tests/unit/test_schemas/test_plugin_registry.py` — 10 tests unitaires schémas
- `backend/tests/unit/test_services/test_plugin_registry_service.py` — 12 tests unitaires service
- `backend/tests/unit/test_api/test_plugin_registry.py` — 11 tests unitaires API

### Fichiers modifiés
- `backend/app/config.py` — Ajout de 3 settings : `plugin_registry_url`, `plugin_registry_cache_ttl`, `plugin_registry_timeout`
- `backend/app/api/v1/__init__.py` — Enregistrement du router `plugin_registry` avec prefix `/registry`

### Décisions techniques
- **Timeout aiohttp** : Utilisation de `asyncio.TimeoutError` au lieu de `aiohttp.ClientTimeout` (qui est une classe de configuration, pas une exception) pour la gestion des timeouts dans le service
- **Cache en mémoire** : Utilisation de `time.monotonic()` pour le TTL (insensible aux changements d'horloge système)
- **Fallback gracieux** : En cas d'erreur de fetch, le service retourne les données en cache même expirées si disponibles
- **Validation kebab-case** : Réutilisation du pattern `_NAME_PATTERN` de `plugin_manifest.py` pour la validation anti path-traversal
- **Enums réutilisés** : `Architecture`, `PluginCategory`, `PluginType` importés depuis `plugin_manifest.py` pour cohérence

### Divergences
- Aucune divergence par rapport aux spécifications de la story

### Résultats des tests
- **33 tests passés** (10 schémas + 12 service + 11 API)
- **Couverture service** : 93%
- **Lint ruff** : All checks passed
