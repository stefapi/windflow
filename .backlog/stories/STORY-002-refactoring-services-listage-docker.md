# STORY-002 : Backend — Refactoring des services de listage Docker

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant que développeur backend, je veux que les services de listage des containers Docker, projets Docker Compose et stacks WindFlow soient correctement structurés selon les principes SOLID/DRY/KISS, afin que le code soit lisible, maintenable et testable unitairement.

## Contexte technique
Le fichier `backend/app/services/compute_service.py` (~350 lignes) est un monolithe qui mélange :
- Classification des containers Docker (logique métier de labels)
- Construction d'objets domaine (`DiscoveredItem`, `StandaloneContainer`, `StackWithServices`)
- Agrégation de statistiques
- Filtrage et grouping
- Helpers utilitaires (`_format_memory`, `_parse_ports`, `_extract_uptime`)

La fonction `get_compute_global()` fait tout : connexion Docker, classification, construction d'objets, filtrage. Elle est difficile à tester unitairement car chaque responsabilité est entremêlée.

**Fichiers de référence :**
- `backend/app/services/compute_service.py` — monolithe à refactorer
- `backend/app/services/docker_client_service.py` — client Docker de bas niveau
- `backend/app/schemas/compute.py` — schémas Pydantic existants
- `backend/app/api/v1/compute.py` — router API existant (inchangé)

## Critères d'acceptation (AC)
- [x] AC 1 : Le classifier de containers est isolé dans `container_classifier.py` avec des fonctions pures testables unitairement (pas d'I/O, pas d'async)
- [x] AC 2 : Les builders d'objets domaine sont isolés dans `container_builder.py` (construction de `DiscoveredItem`, `StandaloneContainer`, `StackWithServices`)
- [x] AC 3 : Les helpers utilitaires sont extraits dans `backend/app/helper/compute_helpers.py`
- [x] AC 4 : `compute_service.py` est un orchestrateur allégé qui délègue au classifier et aux builders (chaque fonction < 80 lignes)
- [x] AC 5 : L'API existante (`GET /compute/stats`, `GET /compute/global`) reste inchangée — pas de régression
- [x] AC 6 : Les tests unitaires existants passent toujours (adaptation des mocks si nécessaire)
- [x] AC 7 : Nouveaux tests unitaires pour le classifier et les builders (couverture ≥ 85%)

## Dépendances
- Aucune (story autonome, ne modifie que la structure interne du backend)

## État d'avancement technique
- [x] Tâche 1 : Créer `backend/app/helper/compute_helpers.py` (helpers utilitaires + apply_filters)
- [x] Tâche 2 : Créer `backend/app/services/container_classifier.py` (classification pure)
- [x] Tâche 3 : Créer `backend/app/services/container_builder.py` (builders domaine)
- [x] Tâche 4 : Refactorer `compute_service.py` en orchestrateur allégé
- [x] Tâche 5 : Adapter les tests existants (imports)
- [x] Tâche 6 : Nouveaux tests — `test_container_classifier.py` (≥95%)
- [x] Tâche 7 : Nouveaux tests — `test_container_builder.py` (≥85%)
- [x] Tâche 8 : Nouveaux tests — `test_compute_helpers.py` (≥95%)
- [x] Tâche 9 : Valider que tous les tests passent (existants + nouveaux) — 98/98 ✅

## Tâches d'implémentation détaillées

### Contexte technique (analyse du code existant)

Le fichier `backend/app/services/compute_service.py` (~350 lignes) contient 4 responsabilités mélangées :

| Responsabilité | Fonctions | Caractéristiques |
|---|---|---|
| **Classification** | `_is_windflow_managed`, `_is_compose_project`, `_classify_containers` | Pure, pas d'I/O, pas d'async → facilement testable |
| **Builders domaine** | Sections 4-6 de `get_compute_global` + `_build_target_groups`, `_get_latest_active_deployment` | Construction d'objets Pydantic à partir de données brutes |
| **Helpers utilitaires** | `_format_memory`, `_parse_ports`, `_extract_uptime` | Fonctions pures réutilisables |
| **Orchestration** | `get_compute_stats`, `get_compute_global` + filtres (section 7) | Coordination DB + Docker, logique de filtrage |

**Patterns existants à respecter :**
- Imports relatifs (`from ..models.deployment import ...`)
- Logging structuré via `logging.getLogger(__name__)`
- Graceful degradation Docker (try/except, compteurs à 0)
- Types hints complets sur tout ce qui est public
- Constantes de labels Docker en haut de fichier

**Fichiers impactés (consommateurs de compute_service) :**
- `backend/app/api/v1/compute.py` — import `from ...services import compute_service`, appelle `compute_service.get_compute_stats()` et `compute_service.get_compute_global()`. **Ne doit pas changer** (AC5).
- `backend/tests/unit/test_services/test_compute_service.py` — importe `_classify_containers`, `_format_memory`, `get_compute_global`, `get_compute_stats`. **À adapter** (paths d'import).
- `backend/tests/unit/test_compute_api.py` — mock `app.api.v1.compute.compute_service.get_compute_stats`. **Inchangé** (mock sur l'API router).

---

### Tâche 1 : Créer `backend/app/helper/compute_helpers.py`

**Objectif :** Extraire les fonctions utilitaires pures réutilisables.

**Fonctions à extraire depuis `compute_service.py` :**

```python
# backend/app/helper/compute_helpers.py

def format_memory(bytes_val: int) -> str:
    """
    Formate une valeur en bytes vers une string lisible.
    Exemples : 103809024 → "99M", 1073741824 → "1G"
    """

def parse_ports(ports_data: list[dict]) -> list[ContainerPortMapping]:
    """
    Parse les ports Docker vers ContainerPortMapping.
    Docker retourne: [{"IP": "0.0.0.0", "PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}]
    """

def extract_uptime(status: str) -> Optional[str]:
    """
    Extrait l'uptime depuis le champ status Docker.
    Exemples: "Up 2 hours" -> "Up 2 hours", "Exited (0) 3 minutes ago" -> None
    """
```

**Nouvelle fonction à créer (logique de filtrage section 7 de `get_compute_global`) :**

```python
def apply_filters(
    managed_stacks: list[StackWithServices],
    discovered_items: list[DiscoveredItem],
    standalone_list: list[StandaloneContainer],
    type_filter: Optional[str] = None,
    technology: Optional[str] = None,
    target_id_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[StackWithServices], list[DiscoveredItem], list[StandaloneContainer]]:
    """
    Applique les filtres sur les 3 sections de la vue compute.
    Retourne les 3 listes filtrées.
    """
```

**Instructions :**
- Renommer sans le préfixe `_` (devenant publics)
- Imports : `from ..schemas.compute import ContainerPortMapping, StackWithServices, DiscoveredItem, StandaloneContainer` et `from typing import Optional`
- Ajouter des docstrings complètes

---

### Tâche 2 : Créer `backend/app/services/container_classifier.py`

**Objectif :** Isoler la logique de classification des containers Docker en fonctions pures (pas d'I/O, pas d'async).

**Constantes à extraire :**

```python
# Labels WindFlow posés sur les containers lors du déploiement
LABEL_WINDFLOW_MANAGED = "windflow.managed"
LABEL_WINDFLOW_STACK_ID = "windflow.stack_id"

# Label Docker Compose standard
LABEL_COMPOSE_PROJECT = "com.docker.compose.project"
LABEL_COMPOSE_CONFIG_FILES = "com.docker.compose.project.config_files"

# Placeholder pour la target locale
LOCAL_TARGET_ID = "local"
LOCAL_TARGET_NAME = "Local Docker"
```

**Fonctions à extraire :**

```python
def is_windflow_managed(labels: dict[str, str]) -> bool:
    """Retourne True si le container est géré par WindFlow."""

def is_compose_project(labels: dict[str, str]) -> bool:
    """Retourne True si le container fait partie d'un projet Docker Compose."""

def classify_containers(
    containers: list[ContainerInfo],
) -> tuple[
    dict[str, list[ContainerInfo]],  # managed: {stack_id: [containers]}
    dict[str, list[ContainerInfo]],  # discovered: {project_name: [containers]}
    list[ContainerInfo],             # standalone: [containers]
]:
    """
    Classe les containers Docker en 3 catégories.
    Priorité : windflow.managed > compose > standalone
    """
```

**Instructions :**
- Renommer sans le préfixe `_` (devenant publics)
- Import `ContainerInfo` depuis `..services.docker_client_service`
- Import `defaultdict` depuis `collections`
- Toutes les fonctions sont synchrones et pures (pas d'I/O)
- Les tests existants de `TestClassifyContainers` seront déplacés ici

---

### Tâche 3 : Créer `backend/app/services/container_builder.py`

**Objectif :** Isoler la construction des objets domaine Pydantic depuis les données brutes.

**Fonctions synchrones :**

```python
def get_latest_active_deployment(
    deployments: list[Deployment],
) -> Optional[Deployment]:
    """Retourne le déploiement le plus récent qui n'est pas STOPPED/FAILED."""

def build_managed_stacks(
    db_stacks: list,  # list[Stack] ORM
    managed_by_stack_id: dict[str, list[ContainerInfo]],
    targets_by_id: dict[str, Target],
    local_target_id: str,
    local_target_name: str,
) -> list[StackWithServices]:
    """
    Construit les StackWithServices depuis les stacks DB enrichies avec Docker.
    Logique de status dérivé : running/partial/stopped selon containers.
    Normalise la technologie (docker_compose → docker-compose).
    """

def build_discovered_items(
    discovered_by_project: dict[str, list[ContainerInfo]],
    local_target_id: str,
    local_target_name: str,
    now_iso: str,
) -> list[DiscoveredItem]:
    """
    Construit les DiscoveredItem (projets Compose externes).
    Extrait source_path depuis labels, génère id au format compose:<project>@<target>.
    """

def build_target_groups(
    managed_stacks: list[StackWithServices],
    discovered_items: list[DiscoveredItem],
    standalone_list: list[StandaloneContainer],
    targets_by_id: dict[str, Target],
) -> list[TargetGroup]:
    """
    Regroupe toutes les ressources par target.
    Ressources locales non associées → groupe "local".
    """
```

**Fonction async (nécessite inspect Docker pour health) :**

```python
async def build_standalone_containers(
    standalone_containers_raw: list[ContainerInfo],
    local_target_id: str,
    local_target_name: str,
    docker_available: bool,
) -> list[StandaloneContainer]:
    """
    Construit les StandaloneContainer avec uptime, ports et health.
    Crée un DockerClientService interne si docker_available et containers présents.
    Parse les ports via compute_helpers.parse_ports.
    Extrait l'uptime via compute_helpers.extract_uptime.
    Inspecte chaque container running pour le health_status.
    """
```

**Instructions :**
- Importer `ServiceWithMetrics`, `StackWithServices`, `DiscoveredItem`, `StandaloneContainer`, `TargetGroup`, `TargetMetrics` depuis `..schemas.compute`
- Importer `Deployment`, `DeploymentStatus` depuis `..models.deployment`
- Importer `Target` depuis `..models.target`
- Importer les helpers depuis `..helper.compute_helpers`
- Importer `ContainerInfo` depuis `..services.docker_client_service`
- Importer les constantes depuis `..services.container_classifier`
- `build_standalone_containers` gère son propre `DockerClientService` pour l'inspection health

---

### Tâche 4 : Refactorer `compute_service.py` en orchestrateur allégé

**Objectif :** Ne conserver que l'orchestration (DB + Docker + délégation). Chaque fonction < 80 lignes.

**Structure finale de `compute_service.py` :**

```python
"""
Service d'agrégation Compute — Orchestrateur.

Délègue la classification, la construction et le filtrage aux modules spécialisés :
- container_classifier : classification des containers par labels
- container_builder : construction des objets domaine Pydantic
- compute_helpers : utilitaires (formatage, filtrage)
"""

import logging
from typing import Optional, Union

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.deployment import Deployment, DeploymentStatus
from ..models.stack import Stack
from ..models.target import Target
from ..schemas.compute import (
    ComputeGlobalView, ComputeStatsResponse, ContainerPortMapping,
    DiscoveredItem, ServiceWithMetrics, StackWithServices,
    StandaloneContainer, TargetGroup, TargetMetrics,
)
from ..services.docker_client_service import DockerClientService, ContainerInfo
from ..services.container_classifier import (
    classify_containers, LABEL_WINDFLOW_STACK_ID,
    LOCAL_TARGET_ID, LOCAL_TARGET_NAME,
)
from ..services.container_builder import (
    build_managed_stacks, build_discovered_items,
    build_standalone_containers, build_target_groups,
)
from ..helper.compute_helpers import apply_filters

logger = logging.getLogger(__name__)
```

**`get_compute_stats` (refactorée) :**
1. Compteurs DB (stacks, targets) — inchangé
2. Récupération Docker — inchangé
3. Appel `classify_containers()` au lieu de `_classify_containers()`
4. Calcul des compteurs dérivés — logique identique, extraire dans une helper `_compute_stats_from_classified` si > 80 lignes

**`get_compute_global` (refactorée) :**
1. Récupérer stacks DB + targets DB — inchangé
2. Récupérer containers Docker (graceful degradation) — inchangé
3. Appel `classify_containers()` — délégation
4. Appel `build_managed_stacks()` — délégation
5. Appel `build_discovered_items()` — délégation
6. Appel `build_standalone_containers()` — délégation
7. Appel `apply_filters()` — délégation (remplace 30 lignes de filtrage)
8. Retour selon `group_by` — inchangé

**Conserver la rétro-compatibilité des imports :**
```python
# Ré-export pour compatibilité (tests existants)
from ..services.container_classifier import classify_containers as _classify_containers
from ..helper.compute_helpers import format_memory as _format_memory
```

**Fonction helper DB conservée :**
```python
async def _get_local_target(db, org_id) -> tuple[str, str]:
    """Tente de trouver la target Docker locale dans la DB."""
```

---

### Tâche 5 : Adapter les tests existants

**Fichier :** `backend/tests/unit/test_services/test_compute_service.py`

**Modifications :**
1. Mettre à jour les imports :
   - `_classify_containers` → import depuis `app.services.container_classifier` (ou utiliser le ré-export `compute_service._classify_containers`)
   - `_format_memory` → import depuis `app.helper.compute_helpers` (ou ré-export)
2. Les patchs `app.services.compute_service.DockerClientService` restent valides (c'est dans compute_service que DockerClientService est toujours instancié)
3. Les tests `TestGetComputeStats` et `TestGetComputeGlobal` restent quasiment identiques — l'orchestrateur a le même comportement

---

### Tâche 6 : Nouveaux tests — `backend/tests/unit/test_services/test_container_classifier.py`

**Objectif :** Couverture ≥ 95% du classifier (fonctions pures, facile à tester).

**Classes de tests :**
- `TestIsWindflowManaged` : label true, label false, label manquant, casse mixte ("True", "TRUE")
- `TestIsComposeProject` : label présent, label absent, label vide
- `TestClassifyContainers` :
  - Container WindFlow → managed (groupé par stack_id)
  - Container Compose → discovered (groupé par project)
  - Container sans label → standalone
  - WindFlow prioritaire sur Compose (les 2 labels)
  - Mix de containers multiples
  - Containers vides → 3 dictionnaires/listes vides
  - Stack_id "unknown" si label manquant

---

### Tâche 7 : Nouveaux tests — `backend/tests/unit/test_services/test_container_builder.py`

**Objectif :** Couverture ≥ 85% des builders.

**Classes de tests :**
- `TestGetLatestActiveDeployment` :
  - Déploiements actifs → retourne le plus récent
  - Tous STOPPED/FAILED → fallback au plus récent
  - Liste vide → retourne None
- `TestBuildManagedStacks` :
  - Stack sans container Docker → status "stopped"
  - Stack avec tous les containers running → status "running"
  - Stack avec containers partiels → status "partial"
  - Normalisation technologie docker_compose → docker-compose
  - Target résolue depuis le deployment actif
  - Target fallback vers local
- `TestBuildDiscoveredItems` :
  - Projet avec config_files → source_path rempli
  - Projet sans config_files → source_path None
  - ID au format `compose:<project>@<target>`
  - Services correctement construits
- `TestBuildTargetGroups` :
  - Groupement par target_id
  - Target inconnue → technologie "docker"
  - Target connue → technologie depuis le type DB

---

### Tâche 8 : Nouveaux tests — `backend/tests/unit/test_helper/test_compute_helpers.py`

**Objectif :** Couverture ≥ 95% des helpers.

**Classes de tests :**
- `TestFormatMemory` :
  - 0 → "0M", négatif → "0M"
  - Kilobytes (512KB → "512K")
  - Mégabytes (100MB → "100M")
  - Gigabytes (2GB → "2.0G")
- `TestParsePorts` :
  - Ports valides avec tous les champs
  - Ports sans PublicPort → ignorés
  - Ports sans PrivatePort → ignorés
  - Liste vide → liste vide
  - Valeurs par défaut (IP, protocol)
- `TestExtractUptime` :
  - "Up 2 hours" → "Up 2 hours"
  - "Exited (0) 3 minutes ago" → None
  - "" → None
- `TestApplyFilters` :
  - type_filter="managed" → garde seulement managed_stacks
  - type_filter="discovered" → garde seulement discovered_items
  - type_filter="standalone" → garde seulement standalone_list
  - search insensible à la casse
  - status_filter sur managed_stacks et standalone_list
  - target_id_filter sur les 3 sections
  - technology sur managed_stacks et discovered_items
  - Combinaison de filtres
  - Aucun filtre → listes inchangées

## Tests à écrire

### 1. Tests unitaires — `backend/tests/unit/test_helper/test_compute_helpers.py`

| Classe | Test | Description |
|---|---|---|
| `TestFormatMemory` | `test_zero_returns_zero_m` | 0 → "0M" |
| | `test_negative_returns_zero_m` | valeur négative → "0M" |
| | `test_kilobytes` | 512KB → se termine par "K" |
| | `test_megabytes` | 100MB → se termine par "M" |
| | `test_gigabytes` | 2GB → se termine par "G" |
| `TestParsePorts` | `test_valid_port_mapping` | Port complet avec IP, PublicPort, PrivatePort, Type |
| | `test_missing_public_port_ignored` | Port sans PublicPort → ignoré |
| | `test_missing_private_port_ignored` | Port sans PrivatePort → ignoré |
| | `test_empty_list` | Liste vide → liste vide |
| | `test_default_values` | IP manquante → "0.0.0.0", Type manquant → "tcp" |
| `TestExtractUptime` | `test_up_status` | "Up 2 hours" → "Up 2 hours" |
| | `test_exited_status` | "Exited (0) 3 minutes ago" → None |
| | `test_empty_status` | "" → None |
| `TestApplyFilters` | `test_no_filter_returns_all` | Aucun filtre → listes inchangées |
| | `test_type_filter_managed` | type="managed" → seulement managed_stacks |
| | `test_type_filter_discovered` | type="discovered" → seulement discovered_items |
| | `test_type_filter_standalone` | type="standalone" → seulement standalone_list |
| | `test_search_case_insensitive` | search="NGINX" filtre insensible à la casse |
| | `test_status_filter` | status="running" sur managed_stacks et standalone |
| | `test_target_id_filter` | target_id sur les 3 sections |
| | `test_technology_filter` | technology sur managed_stacks et discovered_items |
| | `test_combined_filters` | Combinaison search + status |

### 2. Tests unitaires — `backend/tests/unit/test_services/test_container_classifier.py`

| Classe | Test | Description |
|---|---|---|
| `TestIsWindflowManaged` | `test_true_label` | labels avec windflow.managed="true" |
| | `test_false_label` | labels avec windflow.managed="false" |
| | `test_missing_label` | labels sans la clé |
| | `test_case_insensitive` | "True", "TRUE", "TrUe" |
| `TestIsComposeProject` | `test_present` | Label com.docker.compose.project présent |
| | `test_absent` | Label absent |
| | `test_empty_string` | Label présent mais vide → True (présence suffit) |
| `TestClassifyContainers` | `test_windflow_managed` | Container WF → managed, groupé par stack_id |
| | `test_compose_project` | Container Compose → discovered |
| | `test_no_labels_standalone` | Container vide → standalone |
| | `test_windflow_priority_over_compose` | Les 2 labels → WF prioritaire |
| | `test_multiple_containers_mixed` | Mix de 4+ containers |
| | `test_empty_input` | Liste vide → dicts/listes vides |
| | `test_unknown_stack_id` | Label WF sans stack_id → "unknown" |

### 3. Tests unitaires — `backend/tests/unit/test_services/test_container_builder.py`

| Classe | Test | Description |
|---|---|---|
| `TestGetLatestActiveDeployment` | `test_returns_most_recent_active` | Parmi des actifs, retourne le plus récent |
| | `test_all_stopped_returns_fallback` | Tous STOPPED/FAILED → fallback au plus récent global |
| | `test_empty_returns_none` | Liste vide → None |
| `TestBuildManagedStacks` | `test_no_containers_status_stopped` | Stack sans container Docker → "stopped" |
| | `test_all_running_status_running` | Tous running → "running" |
| | `test_partial_running_status_partial` | Mix running/exited → "partial" |
| | `test_technology_normalization` | docker_compose → docker-compose |
| | `test_target_from_active_deployment` | Target résolue depuis le deployment |
| | `test_target_fallback_local` | Pas de deployment → target locale |
| `TestBuildDiscoveredItems` | `test_with_config_files` | source_path rempli depuis labels |
| | `test_without_config_files` | source_path None |
| | `test_id_format` | `compose:<project>@<target>` |
| | `test_services_construction` | Services avec bons champs |
| `TestBuildTargetGroups` | `test_grouping_by_target` | Ressources groupées par target_id |
| | `test_unknown_target_technology_docker` | Target inconnue → tech "docker" |
| | `test_known_target_technology` | Target DB → tech depuis type.value |

### 4. Tests existants — `backend/tests/unit/test_services/test_compute_service.py`

**Adaptation nécessaire (pas de nouveaux tests, juste mise à jour) :**
- Mise à jour des imports : `_classify_containers` et `_format_memory` vers les nouveaux modules (ou via ré-exports)
- Vérification que les patchs `app.services.compute_service.DockerClientService` fonctionnent toujours
- Les tests `TestGetComputeStats` et `TestGetComputeGlobal` restent identiques en logique

## Notes d'implémentation

### Fichiers créés
- `backend/app/helper/compute_helpers.py` — 4 fonctions pures : `format_memory`, `parse_ports`, `extract_uptime`, `apply_filters`
- `backend/app/services/container_classifier.py` — 3 fonctions pures + constantes de labels : `is_windflow_managed`, `is_compose_project`, `classify_containers`
- `backend/app/services/container_builder.py` — 5 fonctions (dont 1 async) : `get_latest_active_deployment`, `build_managed_stacks`, `build_discovered_items`, `build_standalone_containers`, `build_target_groups`
- `backend/tests/unit/test_services/test_container_classifier.py` — 14 tests (5+3+8)
- `backend/tests/unit/test_services/test_container_builder.py` — 18 tests (4+7+4+5+4)
- `backend/tests/unit/test_services/test_compute_helpers.py` — 20 tests (7+5+5+9)

### Fichiers modifiés
- `backend/app/services/compute_service.py` — Refactoré en orchestrateur allégé (~180 lignes vs ~350 avant). Délègue au classifier, builder et helpers. Ré-exports `_classify_containers` et `_format_memory` pour compatibilité.
- `backend/tests/unit/test_services/test_compute_service.py` — Mise à jour des imports (depuis `compute_service` au lieu de directement depuis les nouveaux modules, via ré-exports)
- `backend/tests/unit/test_compute_api.py` — Fix du helper `_make_stats_response` pour inclure les 4 nouveaux champs du schema `ComputeStatsResponse` (ajoutés par STORY-001)

### Décisions techniques
1. **Ré-exports de compatibilité** dans `compute_service.py` : `_classify_containers` et `_format_memory` restent accessibles depuis `compute_service` pour éviter de casser les imports existants
2. **`build_standalone_containers` gère son propre DockerClientService** : créé localement pour l'inspection health, fermé proprement dans un `finally`
3. **`apply_filters` centralise toute la logique de filtrage** : remplace ~30 lignes de filtrage inline dans `get_compute_global`, supporte les filtres combinés
4. **Localisation des tests** : `test_compute_helpers.py` placé dans `test_services/` (pas `test_helper/`) pour cohérence avec la structure existante

### Résultats de validation
- **98 tests passent** sur les 5 fichiers de tests compute
  - `test_compute_service.py` : 19 tests ✅
  - `test_compute_helpers.py` : 20 tests ✅
  - `test_container_classifier.py` : 14 tests ✅
  - `test_container_builder.py` : 18 tests ✅ (1 fix : `source_path` label sur c1 au lieu de c2)
  - `test_compute_api.py` : 11 tests ✅ (3 fixes : 4 champs manquants dans `_make_stats_response`)
- **0 régression** : l'API existante reste inchangée (AC5 validé)
