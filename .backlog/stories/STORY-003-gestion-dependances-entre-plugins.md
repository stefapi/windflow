# STORY-003 : Gestion des dépendances entre plugins

**Statut :** DONE
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que le système de plugins gère les dépendances déclarées entre plugins afin de garantir qu'un plugin ne peut être installé que si ses dépendances sont satisfaites, et qu'un plugin ne peut être désinstallé si d'autres en dépendent.

## Contexte technique

**Couches impactées :** Backend uniquement (services, schemas, API)

**Fichiers de référence (patterns) :**
- Service → pattern : `backend/app/services/plugin_manager_service.py` (classe avec méthodes statiques + instance)
- Schema manifest → pattern : `backend/app/schemas/plugin_manifest.py` (modèles Pydantic avec validators)
- Schema API → pattern : `backend/app/schemas/plugin.py` (Request/Response séparés)
- API endpoint → pattern : `backend/app/api/v1/plugins.py` (endpoints avec `require_superuser`)
- Tests service → pattern : `backend/tests/unit/test_services/test_plugin_manager_service.py`
- Tests API → pattern : `backend/tests/unit/test_api/test_plugins.py`
- Tests schemas → pattern : `backend/tests/unit/test_schemas/test_plugin_manifest.py`

**Existant clé à étendre :**
- `PluginDependency` (plugin_manifest.py:135) — actuellement `requires: List[str]`, `optional: List[str]`, `conflicts: List[str]` sans version
- `PluginManagerService.install_plugin()` (plugin_manager_service.py:90) — aucune vérification de dépendances
- `PluginManagerService.uninstall_plugin()` (plugin_manager_service.py:260) — suppression directe sans vérification
- `_VERSION_CONSTRAINT_PATTERN` (plugin_manifest.py:25) — regex réutilisable pour les contraintes de version
- Manifest traefik (dev/plugin-examples/traefik/windflow-plugin.yml:53) — exemple avec `requires: [docker]`

**Approche technique :**
- Garder le format `List[str]` dans le manifest YAML pour rétrocompatibilité (ex: `requires: ["docker"]`)
- Supporter les contraintes de version inline : `"docker>=1.0.0"` parsé en `(name, version_constraint)`
- Ajouter un schema `PluginDependencyRef` pour les réponses API structurées
- Créer un service dédié `PluginDependencyService` séparé de `PluginManagerService` (SRP)
- L'auto-install (AC 3) se limite aux manifests locaux disponibles (le registre STORY-013 n'est pas encore implémenté)

**Exigences sécurité identifiées :**
- Auth : oui — les endpoints existants utilisent déjà `require_superuser` pour install/uninstall
- RBAC : superuser uniquement pour les opérations d'écriture, `get_current_active_user` pour lecture
- Validation : noms de plugins validés via kebab-case regex `_NAME_PATTERN`, contraintes de version via `_VERSION_CONSTRAINT_PATTERN`
- Exposition : aucune donnée sensible — les dépendances sont des métadonnées publiques
- Audit : opérations install/uninstall déjà loggées avec `user_id` et `plugin_name`

## Critères d'acceptation (AC)
- [x] AC 1 : À l'installation, le système vérifie que toutes les dépendances déclarées sont présentes et dans une version compatible
- [x] AC 2 : À la désinstallation, le système bloque l'opération si d'autres plugins installés dépendent du plugin ciblé
- [x] AC 3 : L'installation automatique des dépendances manquantes est supportée (résolution transitive)
- [x] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-002 : API REST Plugin Manager — CRUD plugins

## État d'avancement technique
- [x] Tâche 1 : Enrichir PluginDependency avec support contraintes de version
- [x] Tâche 2 : Créer PluginDependencyService (résolution, validation, cycles)
- [x] Tâche 3 : Intégrer la vérification dans PluginManagerService (install + uninstall)
- [x] Tâche 4 : Ajouter endpoint dépendances + response schemas
- [x] Tâche 5 : Tests unitaires backend (service + API + schemas)
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Enrichir PluginDependency avec support contraintes de version
**Objectif :** Ajouter un modèle `PluginDependencyRef` pour représenter une dépendance avec nom + contrainte de version optionnelle, et une fonction utilitaire `parse_dependency_string()` pour parser les formats `"plugin-name"` et `"plugin-name>=1.0.0"`.
**Fichiers :**
- `backend/app/schemas/plugin_manifest.py` — Modifier — Ajouter après la classe `PluginDependency` (ligne ~143) :
  - Nouveau modèle `PluginDependencyRef(BaseModel)` avec champs `name: str` (validé kebab-case) et `version_constraint: Optional[str] = None` (validé via `_VERSION_CONSTRAINT_PATTERN`)
  - Fonction `parse_dependency_string(dep: str) -> PluginDependencyRef` qui sépare le nom de la contrainte de version (ex: `"docker>=1.0.0"` → `PluginDependencyRef(name="docker", version_constraint=">=1.0.0")`)
  - Méthode `PluginDependency.get_resolved_requires() -> List[PluginDependencyRef]` qui parse chaque élément de `self.requires` via `parse_dependency_string()`
  - Même pattern pour `get_resolved_optional()` et `get_resolved_conflicts()`
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — Modifier — Ajouter une classe `TestPluginDependencyRef` avec tests :
  - `test_parse_simple_name` — `"docker"` → `PluginDependencyRef(name="docker", version_constraint=None)`
  - `test_parse_name_with_version` — `"docker>=1.0.0"` → `PluginDependencyRef(name="docker", version_constraint=">=1.0.0")`
  - `test_parse_invalid_name_raises` — `"INVALID!"` → `ValueError`
  - `test_parse_invalid_version_raises` — `"docker=bad"` → `ValueError`
  - `test_get_resolved_requires_returns_refs` — vérifie que `PluginDependency(requires=["docker>=1.0.0"]).get_resolved_requires()` retourne les bons `PluginDependencyRef`
**Exigences sécurité :** Validation kebab-case via `_NAME_PATTERN` sur le nom du plugin dépendance (anti path traversal)
**Dépend de :** Aucune

### Tâche 2 : Créer PluginDependencyService (résolution, validation, cycles)
**Objectif :** Créer un service dédié responsable de la résolution des dépendances, de la validation des versions, de la détection de cycles, et de la vérification des conflits.
**Fichiers :**
- `backend/app/services/plugin_dependency_service.py` — Créer — Nouveau service (pattern : `plugin_manager_service.py`). Classe `PluginDependencyService` avec méthodes :
  - `async check_install_dependencies(db: AsyncSession, manifest: PluginManifest, organization_id: str) -> DependencyCheckResult` — vérifie que toutes les dépendances `requires` sont satisfaites (plugin installé + version compatible). Retourne un résultat avec `satisfied: List[PluginDependencyRef]`, `missing: List[PluginDependencyRef]`, `version_mismatches: List[VersionMismatch]`, `conflicts: List[str]`
  - `async check_uninstall_dependents(db: AsyncSession, plugin_name: str, organization_id: str) -> List[str]` — retourne la liste des noms de plugins installés qui dépendent du plugin à désinstaller
  - `async resolve_transitive_dependencies(db: AsyncSession, manifest: PluginManifest, organization_id: str) -> List[PluginManifest]` — résolution transitive : pour chaque dépendance manquante, cherche un manifest local dans le répertoire configuré (ex: `dev/plugin-examples/*/windflow-plugin.yml`) et retourne les manifests à installer. Lève `WindFlowException` si un manifest est introuvable localement.
  - `detect_circular_dependencies(manifests: List[PluginManifest]) -> List[List[str]]` — statique, détecte les cycles dans le graphe de dépendances (algorithme DFS). Retourne la liste des cycles trouvés.
  - `validate_version_constraint(installed_version: str, constraint: str) -> bool` — statique, évalue une contrainte de version (ex: `">=1.0.0"`) contre la version installée. Utilise `packaging.version` ou une implémentation simple de comparaison semver.
  - Modèle interne `DependencyCheckResult` (dataclass ou BaseModel) avec champs `can_proceed: bool`, `satisfied`, `missing`, `version_mismatches`, `conflicts`
  - Modèle interne `VersionMismatch` avec champs `dependency_name`, `required_constraint`, `installed_version`
- `backend/app/core/exceptions.py` — Aucune modification nécessaire — utiliser `WindFlowException` existante avec `details={"error_type": "dependency_error"}` etc.
**Exigences sécurité :** Validation des noms de plugins via les schémas Pydantic (kebab-case). Pas d'exécution de code externe. Logging structuré avec `logger.info("dependency_check", extra={...})`.
**Dépend de :** Tâche 1

### Tâche 3 : Intégrer la vérification dans PluginManagerService (install + uninstall)
**Objectif :** Modifier les méthodes `install_plugin()` et `uninstall_plugin()` de `PluginManagerService` pour appeler `PluginDependencyService` et bloquer les opérations invalides.
**Fichiers :**
- `backend/app/services/plugin_manager_service.py` — Modifier —
  - Ajouter `from .plugin_dependency_service import PluginDependencyService` dans les imports
  - Dans `__init__()` : ajouter `self._dependency_service = PluginDependencyService()`
  - Dans `install_plugin()` (après validation manifest, avant création DB ~ligne 122) : appeler `self._dependency_service.check_install_dependencies(db, manifest, organization_id)`. Si `can_proceed == False`, lever `WindFlowException` avec `error_type: "dependency_unsatisfied"` et détails des manquantes/conflits. Si des dépendances manquantes peuvent être résolues (AC 3), appeler `resolve_transitive_dependencies()` puis installer chaque dépendance manquante récursivement avant le plugin principal.
  - Dans `uninstall_plugin()` (après vérification existence plugin ~ligne 281, avant suppression DB) : appeler `self._dependency_service.check_uninstall_dependents(db, plugin.name, plugin.organization_id)`. Si la liste n'est pas vide, lever `WindFlowException` avec `error_type: "has_dependents"` et la liste des plugins dépendants.
  - Ajouter logging structuré pour chaque vérification : `logger.info("dependency_check_passed", extra={...})` et `logger.warning("dependency_check_failed", extra={...})`
**Exigences sécurité :** Les vérifications sont effectuées côté serveur (source de vérité). L'isolation organisation est respectée (filtrage par `organization_id`).
**Dépend de :** Tâche 2

### Tâche 4 : Ajouter endpoint dépendances + response schemas
**Objectif :** Ajouter un endpoint GET pour consulter l'arbre de dépendances d'un plugin, et enrichir les schemas de réponse pour inclure les informations de dépendances.
**Fichiers :**
- `backend/app/schemas/plugin.py` — Modifier — Ajouter après les schemas existants :
  - `PluginDependencyRefResponse(BaseModel)` avec `name: str`, `version_constraint: Optional[str]`, `installed: bool`, `installed_version: Optional[str]`
  - `PluginDependencyTreeResponse(BaseModel)` avec `plugin_id: str`, `plugin_name: str`, `requires: List[PluginDependencyRefResponse]`, `optional: List[PluginDependencyRefResponse]`, `conflicts: List[str]`, `dependents: List[str]` (plugins qui dépendent de celui-ci)
- `backend/app/api/v1/plugins.py` — Modifier — Ajouter un nouvel endpoint :
  - `GET /{plugin_id}/dependencies` → `PluginDependencyTreeResponse` — retourne l'arbre de dépendances complet d'un plugin installé. Dépendance : `get_current_active_user` (lecture seule, pas besoin de superuser). Utilise `PluginDependencyService.check_install_dependencies()` et `check_uninstall_dependents()` pour construire la réponse.
  - Ajouter `from ...schemas.plugin import PluginDependencyTreeResponse` dans les imports
  - Ajouter documentation OpenAPI complète (summary, description, responses 200/401/404)
**Exigences sécurité :** `get_current_active_user` requis (authentification). Pas de données sensibles exposées.
**Dépend de :** Tâche 2, Tâche 3

### Tâche 5 : Tests unitaires backend (service + API + schemas)
**Objectif :** Écrire les tests complets couvrant tous les cas nominaux, d'erreur et de sécurité pour le service de dépendances, les endpoints API et les schemas.
**Fichiers :**
- `backend/tests/unit/test_services/test_plugin_dependency_service.py` — Créer — (pattern : `test_plugin_manager_service.py`). Classes de test :
  - `TestCheckInstallDependencies` — tests de vérification à l'installation
  - `TestCheckUninstallDependents` — tests de vérification à la désinstallation
  - `TestResolveTransitiveDependencies` — tests de résolution transitive
  - `TestDetectCircularDependencies` — tests de détection de cycles
  - `TestValidateVersionConstraint` — tests de validation de contraintes de version
- `backend/tests/unit/test_api/test_plugins.py` — Modifier — Ajouter dans les classes existantes ou nouvelles :
  - `TestGetPluginDependencies` — tests du nouvel endpoint GET dependencies
  - Ajouter tests install avec dépendances manquantes dans `TestInstallPlugin`
  - Ajouter tests uninstall avec dépendants dans `TestUninstallPlugin`
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — Modifier — Ajouter `TestPluginDependencyRef` (déjà couvert en Tâche 1)
**Exigences sécurité :** Tests 401/403 obligatoires pour le nouvel endpoint GET dependencies
**Dépend de :** Tâche 1, Tâche 2, Tâche 3, Tâche 4

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend — Schemas

- `backend/tests/unit/test_schemas/test_plugin_manifest.py`
  - `test_parse_dependency_string_simple_name` — `"docker"` → name only, no constraint
  - `test_parse_dependency_string_with_version` — `"docker>=1.0.0"` → name + constraint
  - `test_parse_dependency_string_invalid_name` — `"INVALID!"` → ValueError
  - `test_parse_dependency_string_invalid_version` — `"docker=bad"` → ValueError
  - `test_get_resolved_requires_returns_refs` — vérifie le parsing de la liste requires
  - `test_dependency_ref_validates_kebab_case_name` — **sécurité** : validation nom

### Unitaires Backend — Service PluginDependencyService

- `backend/tests/unit/test_services/test_plugin_dependency_service.py`
  - **TestCheckInstallDependencies**
    - `test_all_dependencies_satisfied` — cas nominal : toutes les dépendances sont installées avec version compatible
    - `test_missing_required_dependency` — cas d'erreur : dépendance requise non installée → `can_proceed=False`, missing list non vide
    - `test_version_mismatch` — cas d'erreur : dépendance installée mais version incompatible → `can_proceed=False`, version_mismatches non vide
    - `test_conflict_detected` — cas d'erreur : plugin en conflit déjà installé → `can_proceed=False`, conflicts non vide
    - `test_no_dependencies` — cas nominal : manifest sans dépendances → `can_proceed=True`
    - `test_optional_dependency_missing` — cas nominal : dépendance optionnelle absente → `can_proceed=True`
  - **TestCheckUninstallDependents**
    - `test_no_dependents` — cas nominal : aucun plugin ne dépend du plugin ciblé → liste vide
    - `test_has_dependents` — cas d'erreur : des plugins dépendent du plugin ciblé → liste non vide
    - `test_transitive_dependents` — cas d'erreur : dépendance transitive A→B→C, tentative uninstall B
  - **TestResolveTransitiveDependencies**
    - `test_resolve_missing_from_local_manifests` — cas nominal : dépendance manquante trouvée localement
    - `test_resolve_missing_not_found` — cas d'erreur : dépendance introuvable → WindFlowException
    - `test_resolve_with_nested_dependencies` — cas nominal : résolution transitive multi-niveau
  - **TestDetectCircularDependencies**
    - `test_no_cycle` — cas nominal : graphe acyclique → liste vide
    - `test_simple_cycle` — cas d'erreur : A→B→A → cycle détecté
    - `test_three_node_cycle` — cas d'erreur : A→B→C→A → cycle détecté
  - **TestValidateVersionConstraint**
    - `test_gte_constraint_satisfied` — `"1.2.0"` >= `"1.0.0"` → True
    - `test_gte_constraint_not_satisfied` — `"0.9.0"` >= `"1.0.0"` → False
    - `test_eq_constraint` — `"1.0.0"` == `"1.0.0"` → True
    - `test_tilde_constraint` — `"1.1.5"` ~= `"1.1.0"` → True

### Unitaires Backend — API Endpoints

- `backend/tests/unit/test_api/test_plugins.py` (ajouts)
  - **TestInstallPlugin** (ajouts)
    - `test_install_plugin_returns_409_on_missing_dependency` — dépendance requise absente → 409 avec détail des manquantes
    - `test_install_plugin_returns_409_on_conflict` — plugin en conflit déjà installé → 409
    - `test_install_plugin_succeeds_with_satisfied_dependencies` — cas nominal : toutes dépendances satisfaites
  - **TestUninstallPlugin** (ajouts)
    - `test_uninstall_plugin_returns_409_on_dependents` — plugins dépendants présents → 409 avec liste des dépendants
    - `test_uninstall_plugin_succeeds_when_no_dependents` — cas nominal : aucun dépendant
  - **TestGetPluginDependencies** (nouveau)
    - `test_get_dependencies_returns_200_authenticated` — cas nominal : arbre de dépendances retourné
    - `test_get_dependencies_returns_401_without_token` — **sécurité** : accès sans token → 401
    - `test_get_dependencies_returns_404_when_not_found` — plugin inexistant → 404

### Commandes de validation
```bash
# Backend — Schemas
poetry run pytest backend/tests/unit/test_schemas/test_plugin_manifest.py -v

# Backend — Service
poetry run pytest backend/tests/unit/test_services/test_plugin_dependency_service.py -v

# Backend — API
poetry run pytest backend/tests/unit/test_api/test_plugins.py -v --tb=short

# Backend — Couverture
poetry run pytest backend/tests/unit/test_services/test_plugin_dependency_service.py backend/tests/unit/test_api/test_plugins.py --cov=app.services.plugin_dependency_service --cov=app.services.plugin_manager_service --cov-fail-under=80

# Lint & typecheck
make lint && make typecheck
```

## Notes d'implémentation

### Fichiers créés
- `backend/app/services/plugin_dependency_service.py` — Nouveau service dédié à la gestion des dépendances (vérification install/uninstall, résolution transitive, détection de cycles, validation de contraintes de version)
- `backend/tests/unit/test_services/test_plugin_dependency_service.py` — 23 tests unitaires couvrant les 5 classes de test (CheckInstallDependencies, CheckUninstallDependents, ResolveTransitiveDependencies, DetectCircularDependencies, ValidateVersionConstraint)

### Fichiers modifiés
- `backend/app/schemas/plugin_manifest.py` — Ajout de `PluginDependencyRef`, `parse_dependency_string()`, et méthodes `get_resolved_requires()`, `get_resolved_optional()`, `get_resolved_conflicts()` sur `PluginDependency`
- `backend/app/schemas/plugin.py` — Ajout de `PluginDependencyRefResponse` et `PluginDependencyTreeResponse`
- `backend/app/services/plugin_manager_service.py` — Intégration de `PluginDependencyService` dans `install_plugin()` et `uninstall_plugin()` avec vérifications de dépendances et auto-install transitive
- `backend/app/api/v1/plugins.py` — Ajout endpoint `GET /{plugin_id}/dependencies`, gestion erreurs `dependency_unsatisfied` (409) et `has_dependents` (409)
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — Ajout de `TestPluginDependencyRef` (13 tests)
- `backend/tests/unit/test_api/test_plugins.py` — Ajout de `TestInstallPluginDependencies`, `TestUninstallPluginDependencies`, `TestGetPluginDependencies` (8 tests)

### Décisions techniques
- Utilisation de `packaging.version.Version` pour la comparaison de versions semver (déjà disponible dans le projet)
- Format `List[str]` conservé dans le manifest YAML pour rétrocompatibilité (ex: `requires: ["docker>=1.0.0"]`)
- `PluginDependencyService` séparé de `PluginManagerService` (principe SRP)
- Résolution transitive limitée aux manifests locaux (`dev/plugin-examples/*/windflow-plugin.yml`)
- L'opérateur `~=` (compatible release) est implémenté manuellement (ex: `~=1.1.0` → `>=1.1.0, <1.2.0`)

### Divergences
- Aucune divergence majeure par rapport au plan d'implémentation
- Correction d'un bug : `manifest_data.get("dependencies", {})` retourne `None` quand la clé existe mais vaut `None` → corrigé avec `manifest_data.get("dependencies") or {}` dans le service et l'endpoint

### Tests ajoutés
- **Schemas** : 13 nouveaux tests (total 33 → tous passent)
- **Service** : 23 nouveaux tests (total 23 → tous passent, couverture 85%)
- **API** : 8 nouveaux tests (total 29 → tous passent)
- **Total** : 85 tests passent, 0 échouent, lint OK
