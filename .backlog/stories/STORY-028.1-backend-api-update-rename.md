# STORY-028.1 : Backend API — Update & Rename

**Statut :** DONE
**Story Parente :** STORY-028 — Backend + Frontend — Onglet Config éditable
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
Ajouter les endpoints backend pour la mise à jour de la configuration d'un container : restart policy, resource limits, et renommage. Ces endpoints s'appuient sur l'API Docker Engine (`POST /containers/{id}/update` et `POST /containers/{id}/rename`) et ne nécessitent pas de recréation du container.

## Critères d'acceptation (AC)
- [x] AC 6 : Un endpoint `PATCH /api/v1/docker/containers/{id}/restart-policy` accepte `{name: str, maximum_retry_count: int | None}`
- [x] AC 7 : Un endpoint `PATCH /api/v1/docker/containers/{id}/resources` accepte `{memory_limit: int | None, cpu_shares: int | None, pids_limit: int | None}`
- [x] AC 8 : Un endpoint `POST /api/v1/docker/containers/{id}/rename` accepte `{new_name: str}`
- [x] AC 9 : Les modifications de restart policy et resources utilisent `docker update` (sans recréation) — retourne le résultat immédiatement

## Contexte technique

### API Docker Engine (v1.41+)
- `POST /containers/{id}/update` — Body JSON : `{"RestartPolicy": {"Name": "...", "MaximumRetryCount": N}, "Resources": {"Memory": N, "CpuShares": N, "PidsLimit": N}}`. Retourne `{"Warnings": []}`. Pas de recréation du container.
- `POST /containers/{id}/rename?name=newname` — Query param `name`, pas de body. Retourne `204 No Content`.

### Code existant pertinent
- **Routes existantes** : `backend/app/api/v1/docker.py` — Pattern endpoint action : `pause_container()` (l.495-533) = `get_docker_client()` → appel service → `close()` + gestion `ClientResponseError(404)` / `Exception(500)`
- **Service Docker** : `backend/app/services/docker_client_service.py` — `DockerClientService._request()` (l.391) pour tous les appels HTTP. Pattern : `await self._request("POST", f"/containers/{id}/...")`.
- **Schémas de réponse existants** : `ContainerRestartPolicyInfo` (l.217) et `ContainerResourcesInfo` (l.236) dans `backend/app/schemas/docker.py` — Ce sont des schémas de **lecture** (from_docker_dict). Il faut créer des schémas de **requête** distincts.
- **Pattern validation nom** : `ContainerCreateRequest.name` (l.452) utilise `pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"` — réutiliser pour `ContainerRenameRequest.new_name`
- **Pattern tests** : `test_docker_api_pause.py` — Fixtures `app` (FastAPI + router prefix `/docker`) + `mock_docker_client` (AsyncMock), `patch("app.api.v1.docker.get_docker_client")`, `httpx.AsyncClient` + `ASGITransport`

### Fichiers de référence (patterns à suivre)
- **Endpoint API** → Suivre `pause_container()` / `unpause_container()` dans `docker.py`
- **Méthode service** → Suivre `start_container()` / `stop_container()` dans `docker_client_service.py`
- **Schéma request** → Suivre `ContainerCreateRequest` dans `docker.py`
- **Tests** → Suivre `test_docker_api_pause.py`

## Dépendances
- Aucune sous-story prérequise (première sous-story)
- STORY-024 (schémas structurés) — DONE

## Tâches d'implémentation détaillées

### Tâche 1 : Schémas Pydantic pour les requêtes de mise à jour
**Objectif :** Créer les schémas de validation (request + response) pour les 3 endpoints. Les schémas existants `ContainerRestartPolicyInfo` et `ContainerResourcesInfo` sont des schémas de lecture — il faut des schémas de requête distincts.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Ajouter après la section `# Errors` (avant `# Processes`) les 5 classes suivantes :
  - `ContainerUpdateRestartPolicyRequest(BaseModel)` :
    - `name: str = Field(..., description="Politique de redémarrage", pattern=r"^(no|always|on-failure|unless-stopped)$")`
    - `maximum_retry_count: Optional[int] = Field(None, description="Nombre max de tentatives (pour on-failure)", ge=0)`
  - `ContainerUpdateResourcesRequest(BaseModel)` :
    - `memory_limit: Optional[int] = Field(None, description="Limite mémoire en bytes", ge=0)`
    - `cpu_shares: Optional[int] = Field(None, description="Poids CPU relatif", ge=0)`
    - `pids_limit: Optional[int] = Field(None, description="Limite de PID (-1 = unlimited)", ge=-1)`
  - `ContainerRenameRequest(BaseModel)` :
    - `new_name: str = Field(..., description="Nouveau nom du container", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")`
  - `ContainerUpdateResponse(BaseModel)` :
    - `warnings: list[str] = Field(default_factory=list, description="Avertissements retournés par Docker")`
  - `ContainerRenameResponse(BaseModel)` :
    - `success: bool = Field(..., description="Succès de l'opération")`
    - `message: str = Field(..., description="Message de confirmation")`
**Pattern de référence :** `ContainerCreateRequest` (l.448) pour les validateurs Field + pattern regex
**Dépend de :** Aucune

### Tâche 2 : Méthodes Docker client — update_container() et rename_container()
**Objectif :** Ajouter 2 méthodes async à `DockerClientService` qui appellent l'API Docker Engine. Suivre le pattern des méthodes existantes (`start_container`, `stop_container`).
**Fichiers :**
- `backend/app/services/docker_client_service.py` — Modifier — Ajouter dans la section `# Containers` (après `remove_container`, l.682) :
  - `async def update_container(self, container_id: str, update_config: dict[str, Any]) -> dict[str, Any]` :
    - Appelle `await self._request("POST", f"/containers/{container_id}/update", body=update_config)`
    - Retourne `await response.json()` → `{"Warnings": []}`
    - Docstring : `POST /containers/{id}/update — Met à jour la config d'un container sans recréation`
  - `async def rename_container(self, container_id: str, new_name: str) -> None` :
    - Appelle `await self._request("POST", f"/containers/{container_id}/rename", params={"name": new_name})`
    - Pas de retour (204 No Content)
    - Docstring : `POST /containers/{id}/rename — Renomme un container`
**Pattern de référence :** `start_container()` (l.585) et `stop_container()` (l.596) pour le pattern d'appel `_request`
**Dépend de :** Aucune

### Tâche 3 : Endpoints API PATCH restart-policy, PATCH resources, POST rename
**Objectif :** Exposer les 3 endpoints REST dans le routeur Docker. Suivre le pattern exact de `pause_container()` (l.495-533) : logging avec correlation_id, `get_docker_client()`, appel service, `close()`, gestion `ClientResponseError(404)` / `Exception(500)`.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Ajouter après les imports (l.15-38) les nouveaux schémas : `ContainerUpdateRestartPolicyRequest`, `ContainerUpdateResourcesRequest`, `ContainerRenameRequest`, `ContainerUpdateResponse`, `ContainerRenameResponse`. Puis ajouter 3 endpoints après `remove_container` (l.617) :
  - `PATCH /containers/{container_id}/restart-policy` (status 200, response_model=ContainerUpdateResponse) :
    - Prend `update_data: ContainerUpdateRestartPolicyRequest` en body
    - Construit le dict Docker : `{"RestartPolicy": {"Name": update_data.name, "MaximumRetryCount": update_data.maximum_retry_count}}` (inclure `MaximumRetryCount` seulement si non None)
    - Appelle `client.update_container(container_id, update_config)`
    - Retourne `ContainerUpdateResponse(warnings=result.get("Warnings", []))`
    - Rate limit : 30/60
  - `PATCH /containers/{container_id}/resources` (status 200, response_model=ContainerUpdateResponse) :
    - Prend `update_data: ContainerUpdateResourcesRequest` en body
    - Construit le dict Docker : `{"Resources": {}}` — n'ajouter que les champs non None (`Memory`, `CpuShares`, `PidsLimit`)
    - Appelle `client.update_container(container_id, update_config)`
    - Retourne `ContainerUpdateResponse(warnings=result.get("Warnings", []))`
    - Rate limit : 30/60
  - `POST /containers/{container_id}/rename` (status 200, response_model=ContainerRenameResponse) :
    - Prend `rename_data: ContainerRenameRequest` en body
    - Appelle `client.rename_container(container_id, rename_data.new_name)`
    - Retourne `ContainerRenameResponse(success=True, message=f"Container renommé en {rename_data.new_name}")`
    - Rate limit : 20/60
**Pattern de référence :** `pause_container()` (l.495-533) pour la structure complète (logging, try/except, close)
**Dépend de :** Tâche 1, Tâche 2

### Tâche 4 : Tests unitaires backend
**Objectif :** Tester les 3 endpoints + validation des schémas. Suivre le pattern de `test_docker_api_pause.py` (fixtures, mock, httpx AsyncClient).
**Fichiers :**
- `backend/tests/unit/test_docker/test_docker_config_update.py` — Créer — Tests organisés en 3 classes + 1 classe de validation :
  - Fixture `app` : `FastAPI()` + `include_router(router, prefix="/docker")`
  - Fixture `mock_docker_client` : `DockerClientService()` avec `update_container = AsyncMock(return_value={"Warnings": []})`, `rename_container = AsyncMock()`, `close = AsyncMock()`
  - Helper `_make_client_response_error(status)` (même que test_docker_api_pause.py)
  - `TestUpdateRestartPolicy` :
    - `test_restart_policy_success` — PATCH `/docker/containers/abc123/restart-policy` body `{"name": "always"}` → 200, vérifie appel `update_container`
    - `test_restart_policy_with_retry_count` — body `{"name": "on-failure", "maximum_retry_count": 5}` → 200
    - `test_restart_policy_not_found` — mock lève `ClientResponseError(404)` → 404
    - `test_restart_policy_server_error` — mock lève `Exception` → 500
    - `test_restart_policy_invalid_name` — body `{"name": "invalid"}` → 422 (validation Pydantic)
  - `TestUpdateResources` :
    - `test_resources_success` — PATCH `/docker/containers/abc123/resources` body `{"memory_limit": 536870912}` → 200
    - `test_resources_all_fields` — body avec `memory_limit`, `cpu_shares`, `pids_limit` → 200, vérifie construction du dict Docker
    - `test_resources_not_found` → 404
    - `test_resources_server_error` → 500
    - `test_resources_negative_memory` — body `{"memory_limit": -1}` → 422
  - `TestRenameContainer` :
    - `test_rename_success` — POST `/docker/containers/abc123/rename` body `{"new_name": "my-app"}` → 200 + `{"success": true, "message": "Container renommé en my-app"}`
    - `test_rename_not_found` → 404
    - `test_rename_server_error` → 500
    - `test_rename_invalid_name` — body `{"new_name": "invalid name!"}` → 422
    - `test_rename_empty_name` — body `{"new_name": ""}` → 422
  - `TestSchemaValidation` :
    - `test_restart_policy_request_valid_values` — tester les 4 valeurs valides : "no", "always", "on-failure", "unless-stopped"
    - `test_resources_request_none_values` — tous les champs Optional, body `{}` est valide
    - `test_rename_request_pattern` — noms valides : "my-container", "my_container", "container.v2"
**Pattern de référence :** `test_docker_api_pause.py` pour fixtures, mock, assertions
**Dépend de :** Tâche 3

## Tests à écrire

### Backend
- `backend/tests/unit/test_docker/test_docker_config_update.py` — Tests unitaires (dans le répertoire existant `test_docker/`)
  - **Validation schémas** : RestartPolicyRequest (4 valeurs valides + invalides), ResourcesRequest (None autorisé, négatif refusé), RenameRequest (pattern regex)
  - **PATCH restart-policy** : succès 200 + warnings, 404 container non trouvé, 500 erreur Docker, 422 nom invalide
  - **PATCH resources** : succès 200 + warnings, tous champs optionnels, 404, 500, 422 valeur négative
  - **POST rename** : succès 200 + message, 404, 500, 422 nom invalide/vide
  - **Appels service** : vérifier que `update_container()` et `rename_container()` sont appelés avec les bons arguments

### Commandes de validation
```bash
cd /home/stef/workspace/windflow/backend && poetry run pytest tests/unit/test_docker/test_docker_config_update.py -v
cd /home/stef/workspace/windflow/backend && poetry run mypy app/ --no-error-summary 2>&1 | tail -5
```

## État d'avancement technique
- [x] Tâche 1 : Schémas Pydantic (ContainerUpdateRestartPolicyRequest, ContainerUpdateResourcesRequest, ContainerRenameRequest)
- [x] Tâche 2 : Méthodes Docker client (update_container, rename_container)
- [x] Tâche 3 : Endpoints API (PATCH restart-policy, PATCH resources, POST rename)
- [x] Tâche 4 : Tests unitaires backend

## Notes d'implémentation

### Fichiers modifiés/créés
- **`backend/app/schemas/docker.py`** — Ajout de 5 classes Pydantic : `ContainerUpdateRestartPolicyRequest`, `ContainerUpdateResourcesRequest`, `ContainerRenameRequest`, `ContainerUpdateResponse`, `ContainerRenameResponse`
- **`backend/app/services/docker_client_service.py`** — Ajout de `update_container()` et `rename_container()` après `remove_container()`
- **`backend/app/api/v1/docker.py`** — Ajout imports + 3 endpoints : `PATCH restart-policy`, `PATCH resources`, `POST rename`
- **`backend/tests/unit/test_docker/test_docker_config_update.py`** — Création : 27 tests (4 classes)

### Décisions techniques
- Les schémas de requête sont distincts des schémas de lecture existants (séparation lecture/écriture)
- `maximum_retry_count` est inclus dans le dict Docker uniquement si non-None
- Les champs resources sont inclus dans le dict Docker uniquement si non-None (permet les mises à jour partielles)
- Validation regex réutilisée de `ContainerCreateRequest.name` pour `ContainerRenameRequest.new_name`
- Pattern erreur/gestion identique aux endpoints existants (pause, unpause, etc.)

### Tests
- 27 tests passés (6 restart-policy + 6 resources + 5 rename + 10 schema validation)
- Couverture schema docker.py : 90%
- Aucune divergence par rapport à l'analyse
