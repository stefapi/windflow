# STORY-001 : Format manifest YAML (spécification + validation Pydantic)

**Statut :** DONE
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux définir un format manifest YAML standardisé avec validation Pydantic afin de garantir que chaque plugin déclare correctement ses métadonnées, dépendances, ressources et configuration.

## Contexte technique

Le manifest YAML est la brique fondatrice du système de plugins. Chaque plugin déclare : nom, version, type, dépendances, architectures supportées, ressources minimales, ports et configuration. La validation côté serveur via Pydantic est obligatoire avant toute installation.

**Couches impactées :** Backend uniquement (schemas + service + exemple YAML)

**Fichiers de référence (patterns à suivre) :**
- Schema Pydantic → `backend/app/schemas/stack_definition.py` (pattern : enums, sous-modèles imbriqués, validators, `BaseModel`)
- Service YAML loader → `backend/app/services/stack_definitions_loader.py` (pattern : `yaml.safe_load()`, validation Pydantic, logging structuré)
- Spec manifest complète → `docs/general_specs/09-plugins.md` section "Manifest Plugin — Spécification Complète"
- YAML exemple style → `stacks_definitions/postgresql.yaml`

**Exigences sécurité identifiées :**
- Auth : non — Pas d'endpoint API dans cette story (les endpoints seront dans STORY-002)
- RBAC : non applicable — Pas d'endpoint
- Validation : oui — `yaml.safe_load()` obligatoire (pas `yaml.load()`), validation Pydantic stricte sur tous les champs (regex pour name, semver pour version, enum pour type)
- Exposition données sensibles : non applicable
- Audit : non

## Critères d'acceptation (AC)
- [x] AC 1 : Un schéma Pydantic `PluginManifest` valide tous les champs requis (nom, version, type, architectures, ressources) avec messages d'erreur clairs
- [x] AC 2 : Un fichier YAML exemple de manifest est fourni et passe la validation avec succès
- [x] AC 3 : Les types de plugins supportés (service, extension, hybrid) sont énumérés et validés dans le schéma
- [x] AC 4 : La section `config` du manifest supporte les types de champs nécessaires pour la génération dynamique de formulaires
- [x] AC 5 : Build/lint/tests passent avec une couverture ≥ 80% sur le module de validation

## Dépendances
- Aucune

## État d'avancement technique
- [x] Tâche 1 : Créer les enums et sous-modèles Pydantic du manifest plugin
- [x] Tâche 2 : Créer le modèle principal `PluginManifest`
- [x] Tâche 3 : Créer le service `PluginManifestService`
- [x] Tâche 4 : Créer le manifest YAML exemple Traefik
- [x] Tâche 5 : Tests unitaires du schéma et du service
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Créer les enums et sous-modèles Pydantic du manifest plugin
**Objectif :** Définir les enums (`PluginType`, `PluginCategory`, `ConfigFieldType`, `PortProtocol`, `Architecture`) et les sous-modèles Pydantic imbriqués qui composent le manifest plugin, en suivant le pattern de `backend/app/schemas/stack_definition.py`.
**Fichiers :**
- `backend/app/schemas/plugin_manifest.py` — Créer — Nouveau module de schemas (pattern : `backend/app/schemas/stack_definition.py`). Créer les éléments suivants :
  - Enum `PluginType` : valeurs `service`, `extension`, `hybrid`
  - Enum `PluginCategory` : valeurs `access`, `dns`, `database`, `monitoring`, `security`, `backup`, `mail`, `messaging`, `storage`, `git`, `workflow`, `ai`, `web`, `collaboration`, `analytics`, `other`
  - Enum `ConfigFieldType` : valeurs `string`, `password`, `boolean`, `integer`, `select`, `multiline`
  - Enum `PortProtocol` : valeurs `tcp`, `udp`
  - Enum `Architecture` : valeurs `linux/amd64`, `linux/arm64`
  - Sous-modèle `PluginResourceRequirements` : champs `ram_min_mb: int`, `cpu_min_cores: float`, `disk_min_mb: int` (tous avec `ge=0`)
  - Sous-modèle `PluginPort` : champs `port: int` (`ge=1, le=65535`), `protocol: PortProtocol`, `description: str`, `optional: bool = False`
  - Sous-modèle `PluginConfigField` : champs `key: str`, `label: str`, `description: Optional[str]`, `type: ConfigFieldType`, `required: bool = False`, `default: Optional[Any]`, `validation: Optional[str]` (regex), `options: Optional[List[Dict[str, str]]]` (pour select), `generate: bool = False`, `visible_if: Optional[str]`
  - Sous-modèle `PluginDependency` : champs `requires: List[str] = []`, `optional: List[str] = []`, `conflicts: List[str] = []`
  - Sous-modèle `PluginExtension` : champs `api_module: Optional[str]`, `hooks_module: Optional[str]`, `ui_routes: Optional[str]`, `ui_components: Optional[str]`
  - Sous-modèle `PluginHook` : champs `on_install: Optional[str]`, `on_configure: Optional[str]`, `on_start: Optional[str]`, `on_stop: Optional[str]`, `on_update: Optional[str]`, `on_uninstall: Optional[str]`
  - Sous-modèle `PluginAutoDetect` : champs `docker_images: List[str] = []`
  - Valider avec des `@validator` que `name` matche `^[a-z0-9][a-z0-9-]*$`, que `version` est en format semver, que `options` n'est renseigné que si `type == select`
**Exigences sécurité :** Validation stricte de tous les champs via Pydantic — regex sur `name` pour éviter l'injection de chemin, validation semver sur `version`
**Dépend de :** Aucune

### Tâche 2 : Créer le modèle principal `PluginManifest`
**Objectif :** Assembler les sous-modèles de la Tâche 1 dans le modèle racine `PluginManifest` qui représente la totalité d'un fichier `windflow-plugin.yml`.
**Fichiers :**
- `backend/app/schemas/plugin_manifest.py` — Modifier — Ajouter le modèle principal `PluginManifest(BaseModel)` avec les champs :
  - `name: str` (validé regex `^[a-z0-9][a-z0-9-]*$`)
  - `version: str` (validé format semver via validator)
  - `display_name: str`
  - `description: str`
  - `long_description: Optional[str]`
  - `category: PluginCategory`
  - `tags: List[str] = []`
  - `icon: Optional[str]`
  - `author: str`
  - `license: str`
  - `homepage: Optional[str]`
  - `type: PluginType`
  - `architectures: List[Architecture]` (min 1 élément)
  - `windflow_version: Optional[str]` (format semver constraint, ex : `>=1.1.0`)
  - `resources: Optional[PluginResourceRequirements]`
  - `dependencies: Optional[PluginDependency]`
  - `provides: List[str] = []`
  - `ports: List[PluginPort] = []`
  - `config: List[PluginConfigField] = []`
  - `compose_file: Optional[str]` (obligatoire si type `service` ou `hybrid` — ajouter un `@model_validator`)
  - `config_schema: Optional[str]`
  - `extensions: Optional[PluginExtension]` (obligatoire si type `extension` ou `hybrid` — ajouter un `@model_validator`)
  - `hooks: Optional[PluginHook]`
  - `auto_detect: Optional[PluginAutoDetect]`
  - Ajouter un `@model_validator` nommé `validate_type_consistency` qui vérifie :
    - Si `type` est `service` ou `hybrid` → `compose_file` doit être renseigné
    - Si `type` est `extension` ou `hybrid` → `extensions` doit être renseigné
  - Ajouter un `@validator("windflow_version")` pour valider le format de contrainte de version
  - Ajouter la méthode de classe `from_yaml(cls, yaml_content: str) -> "PluginManifest"` qui parse le YAML avec `yaml.safe_load()` et instancie le modèle
**Exigences sécurité :** `yaml.safe_load()` obligatoire (pas `yaml.load()`), validation croisée type/fichiers via model_validator
**Dépend de :** Tâche 1

### Tâche 3 : Créer le service `PluginManifestService`
**Objectif :** Créer le service métier responsable du parsing et de la validation des manifests plugin depuis des fichiers ou des contenus YAML bruts.
**Fichiers :**
- `backend/app/services/plugin_manifest_service.py` — Créer — Nouveau service (pattern : `backend/app/services/stack_definitions_loader.py`). Créer la classe `PluginManifestService` avec :
  - Méthode `validate_manifest(yaml_content: str) -> PluginManifest` : parse le YAML via `PluginManifest.from_yaml()`, retourne le manifest validé ou lève une `WindFlowException` avec message clair
  - Méthode `validate_manifest_file(file_path: Path) -> PluginManifest` : lit le fichier, appelle `validate_manifest()`, log le résultat
  - Méthode `validate_manifest_batch(directory: Path) -> Tuple[List[PluginManifest], List[str]]` : scanne tous les `windflow-plugin.yml` d'un répertoire, retourne les manifests valides et les erreurs
  - Logging structuré : `logger.info("manifest_validated", extra={"plugin_name": manifest.name, "version": manifest.version})`
  - Gestion d'erreurs : attraper `yaml.YAMLError`, `ValidationError` de Pydantic, et `ValueError`, les wrapper dans des `WindFlowException` avec messages explicites
  - Importer `WindFlowException` depuis `backend/app/core/exceptions.py`
**Exigences sécurité :** `yaml.safe_load()` via `PluginManifest.from_yaml()`, messages d'erreur génériques ne révélant pas la structure interne
**Dépend de :** Tâche 2

### Tâche 4 : Créer le manifest YAML exemple Traefik
**Objectif :** Fournir un fichier `windflow-plugin.yml` complet et réaliste pour le plugin Traefik, qui servira de référence et de cas de test nominal.
**Fichiers :**
- `dev/plugin-examples/traefik/windflow-plugin.yml` — Créer — Manifest YAML complet basé sur la spec `docs/general_specs/09-plugins.md` section "Manifest Plugin". Contient :
  - Identité : `name: traefik`, `version: 1.2.0`, `display_name`, `description`, `long_description`, `category: access`, `tags`, `icon`, `author`, `license`, `homepage`
  - Type : `type: hybrid`
  - Compatibilité : `architectures: [linux/amd64, linux/arm64]`, `windflow_version: ">=1.1.0"`
  - Ressources : `ram_min_mb: 128`, `cpu_min_cores: 0.5`, `disk_min_mb: 100`
  - Dépendances : `requires: [docker]`, `optional: [cloudflare-dns]`, `conflicts: [nginx-proxy-manager]`
  - Capabilities : `provides: [reverse_proxy, tls_certificates]`
  - Ports : 80/HTTP, 443/HTTPS, 8080/Dashboard (optional)
  - Config : `acme_email` (string, required, regex email), `dashboard_enabled` (boolean, default true), `log_level` (select avec options), `custom_entrypoints` (string, optional)
  - Fichiers : `compose_file`, `extensions`
  - Hooks : `on_install`, `on_configure`, `on_uninstall`
  - Auto-detect : `docker_images: [traefik]`
**Exigences sécurité :** Aucune exigence spécifique (fichier de données statique)
**Dépend de :** Tâche 2 (pour validation que le YAML passe le schéma)

### Tâche 5 : Tests unitaires du schéma et du service
**Objectif :** Couvrir l'ensemble du module de validation avec des tests unitaires nominaux, d'erreur et de edge cases, atteignant ≥ 80% de couverture.
**Fichiers :**
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — Créer — Tests du schéma Pydantic (pattern : tests existants dans `backend/tests/unit/`). Contient :
  - Fixtures : `valid_minimal_manifest_data`, `valid_full_manifest_data`, `valid_traefik_yaml`
  - Tests nominaux : `test_valid_minimal_manifest`, `test_valid_full_manifest`, `test_from_yaml_valid`, `test_from_yaml_with_traefik_example`
  - Tests validation champs : `test_name_rejects_uppercase`, `test_name_rejects_spaces`, `test_version_rejects_invalid_semver`, `test_type_must_be_enum_value`, `test_architectures_must_not_be_empty`, `test_port_range_validation`
  - Tests model_validator : `test_service_type_requires_compose_file`, `test_extension_type_requires_extensions`, `test_hybrid_requires_both`
  - Tests config : `test_config_select_requires_options`, `test_config_string_with_validation_regex`
- `backend/tests/unit/test_services/test_plugin_manifest_service.py` — Créer — Tests du service (pattern : `backend/tests/unit/test_services/`). Contient :
  - Tests nominaux : `test_validate_manifest_valid_yaml`, `test_validate_manifest_file_valid`, `test_validate_manifest_batch_valid`
  - Tests erreurs : `test_validate_manifest_invalid_yaml_syntax`, `test_validate_manifest_missing_required_fields`, `test_validate_manifest_file_not_found`, `test_validate_manifest_batch_with_errors`
  - Tests edge cases : `test_validate_manifest_empty_yaml`, `test_validate_manifest_extra_fields_ignored`
**Exigences sécurité :** Tests de validation d'injection : `test_name_rejects_path_traversal`, `test_yaml_safe_load_no_code_execution`
**Dépend de :** Tâche 3, Tâche 4

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend — Schéma Pydantic
- `backend/tests/unit/test_schemas/test_plugin_manifest.py`
  - `test_valid_minimal_manifest` — cas nominal : manifest avec champs requis uniquement
  - `test_valid_full_manifest` — cas nominal : manifest complet avec tous les champs optionnels
  - `test_from_yaml_valid` — cas nominal : parsing YAML → PluginManifest
  - `test_from_yaml_with_traefik_example` — cas nominal : le fichier exemple Traefik passe la validation
  - `test_name_rejects_uppercase` — validation : name doit être kebab-case
  - `test_name_rejects_spaces` — validation : pas d'espaces dans name
  - `test_name_rejects_path_traversal` — **sécurité** : name avec `../` rejeté
  - `test_version_rejects_invalid_semver` — validation : version non-semver rejetée
  - `test_type_must_be_enum_value` — validation : type invalide rejeté
  - `test_architectures_must_not_be_empty` — validation : au moins une architecture requise
  - `test_port_range_validation` — validation : port hors bornes rejeté
  - `test_service_type_requires_compose_file` — model_validator : service sans compose_file rejeté
  - `test_extension_type_requires_extensions` — model_validator : extension sans extensions rejeté
  - `test_hybrid_requires_both` — model_validator : hybrid sans compose_file ET extensions rejeté
  - `test_config_select_requires_options` — validation : select sans options rejeté
  - `test_config_string_with_validation_regex` — cas nominal : regex de validation acceptée

### Unitaires Backend — Service
- `backend/tests/unit/test_services/test_plugin_manifest_service.py`
  - `test_validate_manifest_valid_yaml` — cas nominal : YAML valide → PluginManifest
  - `test_validate_manifest_file_valid` — cas nominal : fichier YAML valide → PluginManifest
  - `test_validate_manifest_batch_valid` — cas nominal : répertoire avec manifests valides
  - `test_validate_manifest_invalid_yaml_syntax` — cas d'erreur : YAML malformé → WindFlowException
  - `test_validate_manifest_missing_required_fields` — cas d'erreur : champs manquants → WindFlowException
  - `test_validate_manifest_file_not_found` — cas d'erreur : fichier inexistant → WindFlowException
  - `test_validate_manifest_batch_with_errors` — cas d'erreur : mix valides/invalides → liste erreurs
  - `test_validate_manifest_empty_yaml` — edge case : YAML vide → WindFlowException
  - `test_validate_manifest_extra_fields_ignored` — edge case : champs supplémentaires ignorés
  - `test_yaml_safe_load_no_code_execution` — **sécurité** : YAML avec tags Python rejeté

### Commandes de validation
```bash
# Backend — Tests schéma
poetry run pytest backend/tests/unit/test_schemas/test_plugin_manifest.py -v

# Backend — Tests service
poetry run pytest backend/tests/unit/test_services/test_plugin_manifest_service.py -v

# Backend — Couverture du module
poetry run pytest backend/tests/unit/test_schemas/test_plugin_manifest.py backend/tests/unit/test_services/test_plugin_manifest_service.py -v --cov=backend/app/schemas/plugin_manifest --cov=backend/app/services/plugin_manifest_service --cov-fail-under=80

# Backend — Lint + type check
poetry run black --check backend/app/schemas/plugin_manifest.py backend/app/services/plugin_manifest_service.py
poetry run flake8 backend/app/schemas/plugin_manifest.py backend/app/services/plugin_manifest_service.py
poetry run mypy backend/app/schemas/plugin_manifest.py backend/app/services/plugin_manifest_service.py
```

---

## Notes d'implémentation

**Date de fin :** 2026-05-26

### Fichiers créés
- `backend/app/schemas/plugin_manifest.py` — Schéma Pydantic complet : 5 enums, 7 sous-modèles, modèle principal `PluginManifest` avec validators
- `backend/app/services/plugin_manifest_service.py` — Service `PluginManifestService` avec validation YAML, fichier et batch
- `dev/plugin-examples/traefik/windflow-plugin.yml` — Manifest YAML exemple complet du plugin Traefik (type hybrid)
- `backend/tests/unit/test_schemas/__init__.py` — Package Python pour les tests de schémas
- `backend/tests/unit/test_schemas/test_plugin_manifest.py` — 20 tests unitaires du schéma Pydantic
- `backend/tests/unit/test_services/test_plugin_manifest_service.py` — 11 tests unitaires du service

### Décisions techniques
1. **Pydantic v2 API** : Utilisation de `field_validator` et `model_validator` (mode `after`) au lieu de l'API v1 `@validator` mentionnée dans l'analyse, car le projet utilise Pydantic ^2.12.0
2. **`model_config = {"extra": "ignore"}`** : Les champs YAML inconnus sont silencieusement ignorés pour la forward-compatibility
3. **Regex semver stricte** : Le pattern regex suit la spécification semver.org complète (incluant pre-release et build metadata)
4. **`from_yaml()` comme classmethod** : Placée sur le modèle plutôt que dans le service, pour réutilisation directe et testabilité

### Divergences par rapport à l'analyse
- Aucune divergence majeure. L'implémentation suit fidèlement les tâches décrites.

### Tests ajoutés
- **20 tests schéma** : nominaux (4), validation champs (6), model validators (3), config (4), sécurité (2), edge case (1)
- **11 tests service** : nominaux (3), erreurs (4), edge cases (2), sécurité (2)
- **Total : 31 tests passant à 100%**
- **Couverture :** `plugin_manifest.py` = 99%, `plugin_manifest_service.py` = 96%

### Résultats validation
- ✅ 31/31 tests passent
- ✅ Black : 2 fichiers conformes
- ✅ Flake8 : 0 erreur
- ✅ Couverture ≥ 80% (99% et 96%)
