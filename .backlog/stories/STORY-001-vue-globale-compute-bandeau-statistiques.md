# STORY-001 : Backend — Endpoints Compute Stats et Global

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant que développeur, je veux disposer de deux endpoints REST (`GET /compute/stats` et `GET /compute/global`) afin de fournir au frontend les données d'agrégation nécessaires à la vue globale Compute (métriques synthétiques, stacks managées, objets découverts, containers standalone).

## Contexte technique
- Couche **backend uniquement** (API-first). La partie frontend est couverte par STORY-021.
- Endpoints à créer : `GET /compute/stats` et `GET /compute/global`
- Schemas Pydantic à créer dans `backend/app/schemas/compute.py`
- Service d'agrégation à créer dans `backend/app/services/compute_service.py`
- Router à créer dans `backend/app/api/v1/compute.py`
- Enregistrement dans `backend/app/api/v1/__init__.py`
- Données sources :
  - Stacks "managées" : table `stacks` (SQLAlchemy, relationnelles)
  - Containers Docker : client Docker local via le service existant (même approche que `backend/app/api/v1/docker.py`)
  - Targets : table `targets`
- **Graceful degradation** : si Docker n'est pas disponible, retourner des listes vides (pas d'erreur 500)
- Filtres sur `/compute/global` : `type`, `technology`, `target_id`, `status`, `search`, `group_by` (stack | target)

## Critères d'acceptation (AC)
- [x] AC 1 : `GET /compute/stats` retourne un objet `ComputeStatsResponse` avec les 7 champs (total_containers, running_containers, stacks_count, stacks_services_count, discovered_count, standalone_count, targets_count)
- [x] AC 2 : `GET /compute/global` sans paramètre retourne un `ComputeGlobalView` avec les 3 sections (managed_stacks, discovered_items, standalone_containers)
- [x] AC 3 : `GET /compute/global?group_by=target` retourne une liste de `TargetGroup[]`
- [x] AC 4 : Les filtres `type`, `technology`, `target_id`, `status`, `search` fonctionnent sur `/compute/global`
- [x] AC 5 : Les endpoints sont protégés par authentification JWT (`get_current_active_user`)
- [x] AC 6 : La documentation OpenAPI est correcte (schemas visibles dans `/docs`)
- [x] AC 7 : Tests unitaires passants pour le service et les endpoints

## Dépendances
- Aucune story pré-requise

## Tâches d'implémentation détaillées

### Tâche 1 : Schemas Pydantic pour le module Compute
**Objectif :** Définir tous les types de données échangés par les endpoints compute, en suivant les conventions Pydantic v2 du projet.
**Fichiers :**
- `backend/app/schemas/compute.py` — Créer — Nouveau fichier de schemas (pattern : `backend/app/schemas/docker.py`). Définir les classes suivantes :
  - `ServiceWithMetrics(BaseModel)` : `id: str`, `name: str`, `image: str`, `status: str`, `cpu_percent: float = 0.0`, `memory_usage: str = "0M"`, `memory_limit: Optional[str] = None`
  - `StackWithServices(BaseModel)` : `id: str`, `name: str`, `technology: str = "compose"`, `target_id: str`, `target_name: str`, `services_total: int`, `services_running: int`, `status: Literal["running", "partial", "stopped", "archived"]`, `services: list[ServiceWithMetrics] = []`
  - `StandaloneContainer(BaseModel)` : `id: str`, `name: str`, `image: str`, `target_id: str`, `target_name: str`, `status: str`, `cpu_percent: float = 0.0`, `memory_usage: str = "0M"`
  - `DiscoveredItem(BaseModel)` : `id: str`, `name: str`, `type: Literal["container", "composition", "helm_release"]`, `technology: str`, `source_path: Optional[str]`, `target_id: str`, `target_name: str`, `services_total: int = 0`, `services_running: int = 0`, `detected_at: str`, `adoptable: bool = True`
  - `ComputeGlobalView(BaseModel)` : `managed_stacks: list[StackWithServices] = []`, `discovered_items: list[DiscoveredItem] = []`, `standalone_containers: list[StandaloneContainer] = []`
  - `TargetMetrics(BaseModel)` : `cpu_total_percent: float = 0.0`, `memory_used: str = "0M"`, `memory_total: str = "0M"`
  - `TargetGroup(BaseModel)` : `target_id: str`, `target_name: str`, `technology: str = "docker"`, `stacks: list[StackWithServices] = []`, `discovered: list[DiscoveredItem] = []`, `standalone: list[StandaloneContainer] = []`, `metrics: TargetMetrics`
  - `ComputeStatsResponse(BaseModel)` : `total_containers: int`, `running_containers: int`, `stacks_count: int`, `stacks_services_count: int`, `discovered_count: int`, `standalone_count: int`, `targets_count: int`
- `backend/app/schemas/__init__.py` — Modifier — Ajouter les imports depuis `compute` si le fichier utilise un pattern d'exports centralisés (vérifier d'abord si nécessaire)
**Dépend de :** Aucune

### Tâche 2 : Service d'agrégation compute
**Objectif :** Implémenter la logique métier qui agrège les données DB (stacks, targets) et Docker (containers) pour répondre aux deux endpoints.
**Fichiers :**
- `backend/app/services/compute_service.py` — Créer — Nouveau service async (pattern : `backend/app/services/` existants). Définir les fonctions suivantes :
  - `async def get_compute_stats(db: AsyncSession, org_id: Optional[str]) -> ComputeStatsResponse` :
    - Compte les stacks depuis la DB (`select(func.count(Stack.id))` filtré par org)
    - Compte les targets depuis la DB
    - Interroge Docker pour les containers (via `docker.from_env()` ou équivalent utilisé dans `docker.py`) — retourne 0 si Docker non disponible (try/except)
    - Construit et retourne `ComputeStatsResponse`
  - `async def get_compute_global(db: AsyncSession, org_id: Optional[str], type_filter: Optional[str], technology: Optional[str], target_id: Optional[str], status: Optional[str], search: Optional[str], group_by: str = "stack") -> ComputeGlobalView | list[TargetGroup]` :
    - Récupère les stacks DB → construit `StackWithServices[]` (services_total/running = 0 si Docker non dispo)
    - Appelle Docker pour lister containers → sépare discovered (orphelins) et standalone (individuels)
    - Applique les filtres (search sur `name`, `status` filter, etc.)
    - Si `group_by == "target"` : regroupe par target_id et retourne `list[TargetGroup]`
    - Sinon retourne `ComputeGlobalView`
  - Fonction helper privée `_format_memory(bytes_val: int) -> str` : formate en Ko/Mo/Go (ex: "540M")
**Dépend de :** Tâche 1

### Tâche 3 : Router FastAPI compute + enregistrement
**Objectif :** Exposer les 2 endpoints REST au format OpenAPI, avec authentification, documentation et query params.
**Fichiers :**
- `backend/app/api/v1/compute.py` — Créer — Nouveau router (pattern : `backend/app/api/v1/stats.py`). Définir :
  - `router = APIRouter()`
  - `@router.get("/stats", response_model=ComputeStatsResponse, tags=["compute"])` → `async def get_compute_stats(organization_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user))` → appelle `compute_service.get_compute_stats(db, org_id)`
  - `@router.get("/global", tags=["compute"])` → `async def get_compute_global(type: Optional[str] = Query(None, description="Filter par type: managed|discovered|standalone"), technology: Optional[str] = Query(None), target_id: Optional[str] = Query(None), status: Optional[str] = Query(None), search: Optional[str] = Query(None), group_by: str = Query("stack", regex="^(stack|target)$"), organization_id: Optional[str] = Query(None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user))` → appelle `compute_service.get_compute_global(...)`
  - Docstrings explicatives sur chaque endpoint
- `backend/app/api/v1/__init__.py` — Modifier — Ajouter `from .compute import router as compute_router` dans les imports et `api_router.include_router(compute_router, prefix="/compute", tags=["compute"])` dans les include_router
**Dépend de :** Tâche 1, Tâche 2

## Tests à écrire

### Backend
- `backend/tests/unit/test_services/test_compute_service.py` — Créer — Tester :
  - `get_compute_stats()` avec DB mockée (stacks et targets présents) + Docker indisponible → retourne stats correctes avec compteurs Docker à 0
  - `get_compute_stats()` avec Docker disponible (mock client Docker) → retourne total_containers et running_containers corrects
  - `get_compute_global()` sans filtres → retourne `ComputeGlobalView` avec managed_stacks alimentées depuis DB
  - `get_compute_global(group_by="target")` → retourne une liste de `TargetGroup` groupés par target_id
  - `get_compute_global(search="nginx")` → filtre correctement sur le nom
- `backend/tests/unit/test_compute_api.py` — Créer — Tester :
  - `GET /api/v1/compute/stats` sans auth → 401
  - `GET /api/v1/compute/stats` avec auth → 200 + body `ComputeStatsResponse` valide
  - `GET /api/v1/compute/global` avec auth → 200 + body `ComputeGlobalView` valide
  - `GET /api/v1/compute/global?group_by=target` → 200 + liste `TargetGroup`
  - `GET /api/v1/compute/global?group_by=invalid` → 422 Unprocessable Entity

### Commandes de validation
```bash
# Tests unitaires ciblés
pytest backend/tests/unit/test_services/test_compute_service.py -v
pytest backend/tests/unit/test_compute_api.py -v
# Lancer tous les tests unitaires
pytest backend/tests/unit/ -v
# Vérifier que les endpoints apparaissent dans l'OpenAPI
curl http://localhost:8000/openapi.json | python -m json.tool | grep -A5 'compute'
```

## État d'avancement technique
- [x] Tâche 1 : Schemas Pydantic compute (compute.py)
- [x] Tâche 2 : Service d'agrégation compute (compute_service.py)
- [x] Tâche 3 : Router FastAPI + enregistrement (__init__.py)
- [x] Tests backend (test_compute_service.py + test_compute_api.py)
- [x] Validation tests pytest OK — 30/30 (19 service + 11 API)

## Notes d'implémentation

### Fichiers créés
- `backend/app/schemas/compute.py` — 8 classes Pydantic v2 : `ServiceWithMetrics`, `StandaloneContainer`, `DiscoveredItem`, `StackWithServices`, `ComputeGlobalView`, `TargetMetrics`, `TargetGroup`, `ComputeStatsResponse`. Couverture 100%.
- `backend/app/services/compute_service.py` — Service d'agrégation avec classification des containers Docker en 3 catégories (managed, discovered, standalone) via labels. Graceful degradation si Docker indisponible.
- `backend/app/api/v1/compute.py` — 2 endpoints REST (`/stats`, `/global`) avec validation par regex Pattern (`^(managed|discovered|standalone)$`, `^(stack|target)$`). Couverture 100%.
- `backend/tests/unit/test_services/test_compute_service.py` — 19 tests passants (couverture service 85%).
- `backend/tests/unit/test_compute_api.py` — 11 tests passants (couverture API 100%).

### Fichiers modifiés
- `backend/app/api/v1/__init__.py` — Ajout du router compute avec prefix `/compute`.
- `backend/app/schemas/__init__.py` — Ajout exports des 8 classes compute.

### Décisions techniques
1. **Classification containers** : 3 catégories via labels Docker :
   - `windflow.managed=true` + `windflow.stack_id=<id>` → managé WindFlow
   - `com.docker.compose.project` (sans label WindFlow) → découvert (Docker Compose externe)
   - Aucun label compose/WindFlow → standalone
2. **Graceful degradation** : `try/except Exception` autour de tous les appels Docker. Retour 0/listes vides si Docker indisponible.
3. **Tests API et disable_auth** : ajout d'un fixture `autouse` `force_real_auth` dans `test_compute_api.py` qui force `settings.disable_auth=False` via `monkeypatch`. Cela résout le 500 causé par le mode dev cherchant un superadmin inexistant en base de test.
4. **Réponse polymorphique** `/compute/global` : retourne `ComputeGlobalView` (dict) si `group_by=stack` (défaut) ou `list[TargetGroup]` si `group_by=target`. FastAPI sérialise via `response_model_by_alias=True` et `Union` implicite.

### Difficultés rencontrées
- Les tests API échouaient avec HTTP 500 au lieu de 401/200 : causé par `settings.disable_auth=True` en env de test, qui fait que `get_current_user` cherche un superadmin absent. Résolu par le fixture `force_real_auth`.
