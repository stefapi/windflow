# Stack Definitions — Format YAML du catalogue interne

> **Statut** : Spécification technique · Implémenté (catalogue interne) — **refondu (vague 2) — 2026-08-23**
> **Périmètre** : Guide du développeur du format YAML des stacks du catalogue interne : schéma Pydantic, chargement/seeding, stratégies de mise à jour, versions, API de consommation.
> **Référence de fond** : [general_specs — 03 Modèle compute](../general_specs/03-modele-compute.md) · [09 API](../general_specs/09-api.md) · [12 Marketplace](../general_specs/12-marketplace.md) · [19 Glossaire](../general_specs/19-glossaire.md)
> **Dernière mise à jour** : 2026-08-23 — refonte pilotée par [PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md)

> **Terminologie** : ce document emploie le vocabulaire canonique du glossaire
> ([19-glossaire.md](../general_specs/19-glossaire.md)) : Host (ex-*Target*), Machine (ex-*VM*), App, Cluster, profil.
> Les identifiants du code historique (`target_id`, `TargetType`, `target_type`) sont cités entre backticks
> et mis en correspondance à la première occurrence.

## Vue d'ensemble

Le système de **Stack Definitions** permet de définir des templates de déploiement réutilisables dans des fichiers YAML (`stacks_definitions/*.yaml`). Ces définitions sont validées par Pydantic puis chargées dans la table `stacks` au démarrage du backend, constituant le **catalogue interne de stacks**. Ce catalogue alimente la sélection de stacks lors d'un déploiement ; il ne doit pas être confondu avec la **Marketplace** (interface d'installation en 3 onglets : Apps, Machine Templates, Plugins — [ch. 12](../general_specs/12-marketplace.md)).

Le fonctionnel (stacks WindFlow, matrice profil × origine, adoption) est spécifié au [ch. 03](../general_specs/03-modele-compute.md) ; ce document décrit le COMMENT : format des fichiers, validation, chargement, versions.

## État actuel vs cible — création depuis un stack

*État actuel (implémenté)* : la création passe par `POST /api/v1/deployments` avec `stack_id` + `target_id` (identifiant du Host, ex-*Target*), `name` optionnel et `variables`. La ressource créée est un « deployment ».

*Cible (general_specs ch. 09)* : la ressource devient une **App**, créée via `POST /apps` avec triple XOR `host_id` / `machine_id` / `cluster_id` ([09-api.md](../general_specs/09-api.md)), et le déploiement d'une stack passe par `POST /compute/stacks/{id}/deploy` ([09-api.md](../general_specs/09-api.md)) — ⚠️ **Non implémenté**. La table de correspondance complète figure dans le [README du corpus](README.md).

## Architecture

### Composants

1. **Fichiers YAML** — `stacks_definitions/*.yaml` : définitions des stacks (métadonnées, template, variables).
2. **Schémas de validation** — `backend/app/schemas/stack_definition.py` : `StackDefinition` (racine), `StackDefinitionMetadata`, `StackDefinitionVariable`.
3. **Loader de démarrage** — `backend/app/services/stack_definitions_loader.py` : `StackDefinitionsLoader` scanne, valide (Pydantic strict) et charge en base.
4. **Seeding** — `backend/app/database_seed.py` : `seed_stack_definitions()` appelé au premier démarrage.
5. **Modèle** — `backend/app/models/stack.py` : table `stacks` (template JSON, variables JSON, `target_type`, etc.).
6. **Loader d'administration** — `backend/app/services/stack_loader_service.py` : `StackLoaderService`, utilisé par les endpoints superadmin (`backend/app/api/v1/admin/stacks_management.py`).

### Flux de chargement (démarrage)

```
Démarrage backend
    ↓
database_seed.py — seed_stack_definitions()
    ↓ (si settings.auto_load_stack_definitions)
StackDefinitionsLoader (stack_definitions_loader.py)
    ↓
Scan stacks_definitions/*.yaml
    ↓
Validation Pydantic StackDefinition (schemas/stack_definition.py)
    ↓
load_into_database(strategy=settings.stack_update_strategy)
    ↓
Insertion / mise à jour — table `stacks`
```

Un fichier YAML invalide est journalisé et **sauté** — le chargement des autres fichiers continue (`scan_definitions` collecte les erreurs sans interrompre).

### Deux chargeurs, deux validations ⚠️ (écart connu)

Le dépôt contient deux chemins de validation qui divergent :

| | Seed au démarrage (`stack_definitions_loader.py`) | Administration (`stack_loader_service.py`) |
|---|---|---|
| Validation | `StackDefinition` Pydantic **strict** | Vérification manuelle **allégée** |
| Métadonnées exigées | name, version, category, **author, license**, description, target_type | name, version, description uniquement |
| Types de variables | string, number, integer, boolean, password, textarea, group | string, number, boolean, password, enum, textarea (sans `integer` ni `group`) |

Conséquence concrète : `stacks_definitions/postgresql.yaml` (qui utilise `integer` et `group`) se charge correctement au démarrage, mais ressort **invalide** via `GET /api/v1/admin/stacks-management/definitions`. La convergence des deux validations est un écart connu à inscrire au backlog ; le schéma Pydantic (`stack_definition.py`) fait foi pour la rédaction des YAML.

## Configuration

Extrait réel — `backend/app/config.py` :

```python
# Stack Definitions Auto-loading
stack_definitions_path: str = "stacks_definitions"
auto_load_stack_definitions: bool = True
stack_update_strategy: str = (
    "update_if_newer"  # skip_existing | update_if_newer | force_update
)
```

Variables d'environnement correspondantes (Pydantic BaseSettings) :

| Variable | Défaut | Rôle |
|---|---|---|
| `STACK_DEFINITIONS_PATH` | `stacks_definitions` | Répertoire des YAML |
| `AUTO_LOAD_STACK_DEFINITIONS` | `true` | Chargement automatique au seeding |
| `STACK_UPDATE_STRATEGY` | `update_if_newer` | Stratégie de mise à jour (voir ci-dessous) |

## Format des fichiers YAML

### Squelette

```yaml
metadata:
  name: "…"            # requis
  version: "1.0.0"     # requis (semver — voir § Gestion des versions)
  category: "…"        # requis
  author: "…"          # requis
  license: "…"         # requis
  description: |       # requis
    …
  target_type: "docker"  # requis — voir § target_type
  # optionnels : icon_url, documentation_url, screenshots,
  #             tags ([]), is_public (true), deployment_name

template: {}           # requis, non vide — config Docker / Compose,
                       # variables Jinja2 {{ nom_variable }}

variables: {}          # optionnel (défaut {}) — voir § Variables

# optionnels à la racine : target_parameters, deployment_notes
```

### Métadonnées (`metadata`)

`author` et `license` sont **requis** par le schéma Pydantic — un YAML qui les omet est rejeté au chargement (les exemples de l'ancienne version de ce document, qui les omettaient, étaient inexécutables).

| Champ | Requis | Type | Défaut | Rôle |
|---|---|---|---|---|
| `name` | ✅ | str | — | Nom affiché (unicité par org. + version) |
| `version` | ✅ | str | — | Version d'édition, semver recommandée |
| `category` | ✅ | str | — | Catégorie (ex. `Database`) |
| `author` | ✅ | str | — | Auteur du stack |
| `license` | ✅ | str | — | Licence (ex. `MIT`) |
| `description` | ✅ | str | — | Description détaillée (multi-lignes) |
| `target_type` | ✅ | str | — | Type de déploiement (voir ci-dessous) |
| `icon_url` | — | str | `None` | Icône |
| `documentation_url` | — | str | `None` | Lien documentation |
| `screenshots` | — | list | `[]` | Captures d'écran |
| `tags` | — | list | `[]` | Tags de recherche |
| `is_public` | — | bool | `true` | Partagé entre organisations (⚠️ le modèle SQL defaulte à `false` côté création API) |
| `deployment_name` | — | str | `None` | Template du nom par défaut (peut contenir des macros Jinja2) |

Extrait réel — `stacks_definitions/postgresql.yaml` :

```yaml
metadata:
  name: "PostgreSQL Database Server"
  version: "1.0.0"
  category: "Database"
  author: "PostgreSQL Global Development Group"
  license: "PostgreSQL License"
  deployment_name: "{{ container_name }}"
  description: |
```

### `target_type` — valeurs réelles et correspondance profils

Extrait réel — validateur `validate_target_type` de `backend/app/schemas/stack_definition.py` :

```python
    @validator("target_type")
    def validate_target_type(cls, v):
        """Valide que le target_type est valide."""
        valid_types = {
            "docker",
            "docker_compose",
            "docker_swarm",
            "kubernetes",
            "vm",
            "physical",
        }
        if v not in valid_types:
            raise ValueError(
                f"target_type invalide: {v}. "
                f"Valeurs valides: {', '.join(valid_types)}"
            )
        return v
```

⚠️ Les valeurs `lxd` et `kvm` — citées par les versions antérieures de ce document — sont **invalides** et font échouer le chargement. L'enum Python `TargetType` (`backend/app/enums/target.py`) porte exactement les six valeurs ci-dessus.

Correspondance avec les **profils canoniques** du glossaire ([19-glossaire.md](../general_specs/19-glossaire.md)) :

| `target_type` (code actuel) | Équivalent canonique general_specs |
|---|---|
| `docker` | profil `docker_container` (famille Apps) |
| `docker_compose` | profil `docker_compose` (famille Apps) |
| `docker_swarm` | entité **Cluster** de type `docker_swarm` |
| `kubernetes` | Apps `helm_release` / `k8s_manifest` hébergées par un **Cluster** `kubernetes` |
| `vm` | profils Machines : `vm_kvm`, `vm_lxd`, `vm_incus`, `vm_virtualbox`, `vm_lxc` |
| `physical` | Host `host_baremetal` (famille Hosts) |

La valeur `vm` est donc un type de déploiement générique ; le profil Machine précis (KVM, LXD…) est un concept canonique de general_specs, pas une valeur de ce champ aujourd'hui.

### Variables (`variables`)

Types acceptés — extrait réel, `backend/app/schemas/stack_definition.py` :

```python
class VariableType(str, Enum):
    """Types de variables configurables."""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    GROUP = "group"
```

Champs d'une variable (`StackDefinitionVariable`) :

| Champ | Requis | Défaut | Rôle |
|---|---|---|---|
| `type` / `label` | ✅ | — | Type (7 valeurs ci-dessus) ; label affiché |
| `description` | — | `None` | Description contextuelle |
| `default` | — | `None` | Valeur par défaut (peut être une macro Jinja2) |
| `required` | — | `false` | Champ obligatoire |
| `visible` | — | `true` | Masquage dans l'interface (variable technique) |
| `group` | — | `None` | Groupe d'affichage |
| `help` | — | `None` | Aide (tooltip) |
| `pattern` | — | `None` | Regex de validation (string/password) |
| `enum` | — | `None` | Liste de choix |
| `enum_labels` | — | `None` | Libellés des choix — clés ⊆ `enum` (validé) |
| `minimum` / `maximum` | — | `None` | Bornes numériques (number/integer) |
| `min_length` / `max_length` | — | `None` | Bornes de longueur (string/password) |
| `has_macro` / `macro_template` | — | `false` / `None` | Métadonnées de macro (remplies au rendu) |
| `depends_on` | — | `None` | Conditions d'affichage basées sur d'autres variables |
| `variables` | — | `None` | Sous-variables (**récursives**, `type: group` uniquement) |

**Contraintes numériques** : le schéma utilise `minimum`/`maximum`. Écrire `min:`/`max:` est silencieusement ignoré (voir § Validation). Extrait réel — `stacks_definitions/postgresql.yaml` :

```yaml
  host_port:
    type: integer
    label: "Port hôte"
    description: "Port exposé sur l'hôte Docker pour accéder à PostgreSQL"
    default: "{{get_valid_port(5432)}}"
    minimum: 1
    maximum: 65535
    required: true
    group: "Configuration réseau"
    help: "Port standard PostgreSQL : 5432"
```

**`enum_labels`** : le validateur Pydantic exige (a) que `enum` soit défini, (b) que chaque clé de `enum_labels` soit une valeur de `enum`. Extrait réel — `stacks_definitions/postgresql.yaml` :

```yaml
  locale:
    type: string
    label: "Locale système"
    description: "Locale pour l'encodage et le tri des données"
    default: "en_US.UTF-8"
    enum:
      - "en_US.UTF-8"
      - "fr_FR.UTF-8"
      - "de_DE.UTF-8"
      - "es_ES.UTF-8"
      - "C"
    enum_labels:
      "en_US.UTF-8": "English (United States)"
      "fr_FR.UTF-8": "Français (France)"
      "de_DE.UTF-8": "Deutsch (Deutschland)"
      "es_ES.UTF-8": "Español (España)"
      "C": "C (Default POSIX)"
```

**Groupes récursifs** : une variable `type: group` porte ses sous-variables dans `variables` ; la structure est récursive (groupes imbriqués) et le loader conserve la hiérarchie pour l'UI. Extrait réel — `stacks_definitions/postgresql.yaml` :

```yaml
  performance:
    type: group
    label: "Paramètres de performance"
    variables:
      shared_buffers:
        type: string
        label: "Shared Buffers"
        description: "Mémoire partagée pour le cache PostgreSQL"
        default: "256MB"
        enum:
          - "128MB"
          - "256MB"
          - "512MB"
          - "1GB"
          - "2GB"
          - "4GB"
        required: false
        group: "Performance"
        help: "Recommandé: 25% de la RAM disponible"
```

**Variables invisibles** (`visible: false`) : techniques mais nécessaires au rendu (ex. nom du container généré par macro) — extrait réel, `stacks_definitions/postgresql.yaml` :

```yaml
  container_name:
    type: string
    label: "Nom du container"
    description: "Nom unique du container Docker"
    default: "{{generate_animalname('postgres')}}"
    required: true
    visible: false
    pattern: "^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"
    group: "Configuration générale"
    help: "Le nom doit être unique sur l'hôte Docker"
```

### Champs racine complémentaires

- **`target_parameters`** (optionnel, dict) — paramètres spécifiques à la cible de déploiement. Extrait réel — `stacks_definitions/postgresql.yaml` :

  ```yaml
  target_parameters:
    # volume that needs to be destroyed
    #
    volumes:
      - "{{ volume_name }}"
  ```

- **`deployment_notes`** (optionnel, str) — notes de déploiement en **markdown**, rendues avec les variables (sauvegarde/restauration, avertissements…). Voir `stacks_definitions/postgresql.yaml`.
- **`deployment_name`** (dans `metadata`) — template du nom par défaut ; rendu par le backend et exposé comme `default_name` par `GET /api/v1/stacks/{id}`.

### Validation Pydantic — comportement réel

- **Champs inconnus ignorés silencieusement** : `min:`, `max:`, `label:` mal orthographiés, etc. sont perdus sans erreur. Les contraintes numériques s'écrivent `minimum`/`maximum`.
- **`version`** : le validateur Pydantic ne rejette que les valeurs **vides** — le format semver n'est pas vérifié à la validation ; il est requis de facto par la comparaison de versions de la stratégie `update_if_newer` (voir § Stratégies).
- **`target_type`** : les six valeurs de l'enum, sinon `ValueError`.
- **`template`** : requis et non vide.
- **`enum_labels`** : contraint par le validateur dédié (voir ci-dessus).
- **`variables`** : optionnel côté schéma strict (défaut `{}`) ; le loader admin exige lui les trois sections `metadata`/`template`/`variables` (voir § Deux chargeurs).

## Exemples du dépôt

Le dépôt sert de référence exécutable — chaque YAML ci-dessous passe la validation Pydantic du démarrage :

- **`stacks_definitions/postgresql.yaml`** — `target_type: docker` (container simple) : macros dans les défauts (`generate_animalname`, `get_valid_port`, `generate_cosmicname`), groupe `performance` récursif, `enum_labels`, `target_parameters`, `deployment_notes` complet.
- **`stacks_definitions/baserow.yaml`** — `target_type: docker_compose` (multi-services) : services `db`/`redis`/`backend`… avec healthchecks et réseau interne, métadonnées complètes. Extrait réel :

  ```yaml
  metadata:
    name: "Baserow - No-Code Database Platform"
    version: "1.0.0"
    category: "Database & No-Code"
    author: "Baserow Team"
    license: "MIT"

    description: |
      Baserow est une alternative open-source à Airtable. Créez des bases de données
      collaboratives sans code avec une interface intuitive de type tableur.
  ```

## Workflow de développement

1. **Créer** le fichier : `stacks_definitions/mon-stack.yaml` (ne pas préfixer par `_` — le loader admin ignore ces fichiers ; le scan du démarrage prend tous les `*.yaml`).
2. **Valider** : `POST /api/v1/admin/stacks-management/validate` (superadmin — ⚠️ validation allégée, voir § Deux chargeurs), ou localement :

   ```python
   from backend.app.schemas.stack_definition import StackDefinition
   import yaml

   with open('stacks_definitions/mon-stack.yaml') as f:
       data = yaml.safe_load(f)
   definition = StackDefinition(**data)
   print(f"✓ Définition valide: {definition.metadata.name}")
   ```

3. **Tester le chargement** : supprimer la base en dev (`rm -f data/windflow/windflow.db`) et redémarrer le backend (`make backend`) — les logs affichent créations / mises à jour / erreurs par fichier.
4. **Vérifier en base** : `sqlite3 data/windflow/windflow.db` puis `SELECT name, version, category, target_type FROM stacks;`.
5. **Itérer** : en développement, `STACK_UPDATE_STRATEGY=force_update` recharge les modifications sans incrémenter la version.

## Stratégies de mise à jour

Appliquées par `StackDefinitionsLoader.load_into_database()`, sur la clé (name, version, organisation) :

| Stratégie | Comportement | Cas d'usage |
|---|---|---|
| `skip_existing` | Ignore tout stack déjà présent (même name+version) | Production stable |
| `update_if_newer` *(défaut)* | Met à jour si la version YAML est **plus récente** | Développement actif |
| `force_update` | Écrase toujours | Dev / correction de template |

**Comparaison de versions** : `packaging.version.Version` (semver, pre/post-releases, dev, local). En cas de version non parsable (ex. `v1.0.0`), fallback sur une comparaison **textuelle** avec avertissement — d'où la recommandation forte d'une semver stricte `MAJOR.MINOR.PATCH` sans préfixe. ⚠️ `force_update` peut écraser des modifications faites via l'API.

## Gestion des versions — deux niveaux articulés

1. **Version d'édition (semver, string)** : `metadata.version` du YAML → colonne `stacks.version`. Elle régit le chargement et la stratégie `update_if_newer`. Incrément MAJOR (structure du template incompatible) / MINOR (nouvelles variables) / PATCH (corrections).
2. **Révisions (entier séquentiel)** : chaque modification via l'API crée une entrée dans `stack_versions` avec `version_number` **int** croissant (modèle `StackVersion`, relation `Stack.versions` ordonnée par `version_number` décroissant) — historique des révisions consultable indépendamment de la semver d'édition.

Les deux coexistent à des niveaux différents : la semver identifie l'édition YAML, l'entier séquence les révisions d'une même entrée `stacks`.

## Variables Jinja2 (macros)

Les templates **et les valeurs par défaut** des variables acceptent des macros Jinja2, exécutées côté backend au rendu (deux exemples réels de `stacks_definitions/postgresql.yaml`) :

```yaml
  postgres_password:
    default: "{{ generate_password(24) }}"
```

```yaml
  host_port:
    default: "{{get_valid_port(5432)}}"
```

Le catalogue complet des 16 fonctions disponibles (signatures, sorties exactes, pièges) est spécifié dans [JINJA2-FUNCTIONS.md](JINJA2-FUNCTIONS.md) — ce document n'en duplique pas le détail. Les valeurs par défaut macro sont pré-rendues au chargement du stack, exposées avec `has_macro`/`macro_template` et régénérables via `POST /api/v1/stacks/{id}/regenerate-variable/{name}` (voir [DYNAMIC-FORMS.md](DYNAMIC-FORMS.md) pour la mécanique côté formulaire).

## Bonnes pratiques

1. Toujours fournir les 7 métadonnées requises (`author`/`license` compris) — tester le chargement avant commit.
2. Versionner en semver stricte et incrémenter à chaque modification (sinon `update_if_newer` ignore).
3. Contraintes numériques en `minimum`/`maximum` (jamais `min`/`max`), `pattern` sur les strings, `enum` + `enum_labels` pour les choix.
4. Secrets en `type: password` avec macro génératrice — jamais de valeur en dur.
5. Variables techniques en `visible: false` ; regrouper la configuration utilisateur (`group` ou groupes récursifs).
6. `target_type` doit refléter le template réel (docker = container simple, docker_compose = multi-services).

## Dépannage

| Symptôme | Cause probable / remède |
|---|---|
| `Le répertoire stacks_definitions n'existe pas` | `StackDefinitionsLoader.__init__` lève `ValueError` — vérifier `STACK_DEFINITIONS_PATH` / créer le répertoire |
| `target_type invalide: lxd` (ou `kvm`, …) | Valeurs valides : `docker`, `docker_compose`, `docker_swarm`, `kubernetes`, `vm`, `physical` — la technologie VM précise est un profil canonique, pas une valeur du champ |
| `Champs requis manquants` (author, license, category…) | Compléter `metadata` — les 7 champs requis sont listés au § Métadonnées |
| Les stacks ne se chargent pas | Vérifier `AUTO_LOAD_STACK_DEFINITIONS=true`, les logs de démarrage (fichiers sautés avec motif), et valider le YAML localement (§ Workflow) |
| Les mises à jour ne s'appliquent pas | Version YAML ≤ version en base (`update_if_newer`) — incrémenter, ou `STACK_UPDATE_STRATEGY=force_update` temporairement |
| `enum_labels` rejeté | `enum` absent, ou clés de `enum_labels` hors de `enum` (validateur dédié) |

## API & références

- `GET /api/v1/stacks` — lister les stacks de l'organisation.
- `GET /api/v1/stacks/{id}` — détails : `variables` sérialisées, `template`, et `default_name` (rendu de `metadata.deployment_name`) si défini.
- `POST /api/v1/stacks/{id}/regenerate-variable/{variable_name}` — régénère la valeur d'une variable macro (mot de passe, port…).
- `POST /api/v1/deployments` — créer un déploiement depuis un stack. Payload réel (`DeploymentCreate`) :

  ```json
  {
    "stack_id": "uuid-du-stack",
    "target_id": "uuid-du-host",
    "name": "optionnel (auto-généré si absent)",
    "variables": { "postgres_version": "16", "host_port": 5432 }
  }
  ```

  ⚠️ État actuel — la cible est `POST /apps` + triple XOR (voir § État actuel vs cible).
- Admin (superadmin) : `GET /api/v1/admin/stacks-management/definitions` (inventaire des YAML + validité), `POST /api/v1/admin/stacks-management/validate`.

Code de référence : `backend/app/schemas/stack_definition.py`, `backend/app/services/stack_definitions_loader.py`, `backend/app/services/stack_loader_service.py`, `backend/app/database_seed.py`, `backend/app/models/stack.py`, `backend/app/enums/target.py`, `stacks_definitions/README.md`.

## Voir aussi

- [03-modele-compute.md](../general_specs/03-modele-compute.md) — fonctionnel des stacks WindFlow, origines managed/adopted/external
- [09-api.md](../general_specs/09-api.md) — cible App (`POST /apps`, triple XOR) et `/compute/stacks`
- [12-marketplace.md](../general_specs/12-marketplace.md) — Marketplace (3 onglets) vs catalogue interne
- [19-glossaire.md](../general_specs/19-glossaire.md) — profils canoniques, alias interdits
- [JINJA2-FUNCTIONS.md](JINJA2-FUNCTIONS.md) — catalogue des fonctions Jinja2 · [DYNAMIC-FORMS.md](DYNAMIC-FORMS.md) — mécanique des formulaires générés
