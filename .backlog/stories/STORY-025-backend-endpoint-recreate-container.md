# STORY-025 : Backend — Endpoint de recréation de container

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir modifier des paramètres structurels d'un container (image, ports, volumes, variables d'environnement, labels, mode privilégié, capabilities) via une API backend qui gère automatiquement l'arrêt, la suppression et la recréation du container afin de ne pas avoir à le faire manuellement.

## Contexte technique

Docker ne supporte pas la modification à chaud de la plupart des paramètres de configuration d'un container (image, ports, volumes, env vars, labels, privileged, capabilities). La seule solution est de recréer le container avec la nouvelle configuration.

### Architecture — Abstraction pour multi-backend

L'API doit être abstraite pour supporter à terme plusieurs backends (Docker, Kubernetes, etc.). Le principe :
- **Schémas Pydantic** : agnostiques du runtime (format abstrait)
- **Service client** : chaque backend implémente `recreate_container()` avec sa propre logique
- **Route handler** : fin, ne fait que déléguer au service

### Réutilisation de code existant

- ✅ `pull_image()` déjà présent dans `DockerClientService` (ligne 938)
- ✅ `get_container()`, `stop_container()`, `remove_container()`, `start_container()` déjà existants
- ✅ `create_container()` existe mais doit être **étendu** avec des params additionnels (mounts, cap_add, cap_drop, readonly_rootfs, port_bindings)
- ✅ Pattern de test établi dans `test_docker_config_update.py` (FastAPI + httpx AsyncClient + mock `get_docker_client`)

### Méthode `recreate_container()` au niveau service

Ajoutée dans `DockerClientService`, cette méthode orchestre le cycle complet :

1. `get_container()` → inspect courant → 404 si absent
2. Merge chaque champ : si `None` dans la requête → garder la valeur existante (depuis le detail inspecté)
3. Optionnel `pull_image()`
4. `stop_container(timeout=stop_timeout)`
5. `remove_container(force=True, remove_volumes=False)` — **volumes préservés !**
6. `create_container(name=..., image=..., mounts=..., cap_add=..., ...)` — avec les params étendus
7. `start_container(new_id)`
8. Retourne `(new_id, ContainerDetail)`

**Chemin critique** : si étape 5 réussit mais 6 ou 7 échouent → logger en CRITICAL avec `old_container_id`, retourner HTTP 500 avec détail.

### Extension de `create_container()`

La méthode actuelle (ligne 516 de `docker_client_service.py`) accepte : `name, image, command, env, ports, volumes, labels, restart_policy, network_mode, privileged`.

Paramètres à ajouter :
- `mounts: Optional[list[dict[str, Any]]]` — liste de mounts au format abstrait (`{"source": "...", "destination": "...", "mode": "rw", "type": "bind|volume|tmpfs"}`)
- `cap_add: Optional[list[str]]`
- `cap_drop: Optional[list[str]]`
- `readonly_rootfs: Optional[bool]`
- `port_bindings: Optional[dict[str, Any]]` — format `{"80/tcp": [{"HostPort": "8080"}]}`

Conversion mounts dans `create_container()` (côté Docker) :
```python
if mounts:
    binds = []
    for m in mounts:
        if m["type"] == "bind":
            binds.append(f"{m['source']}:{m['destination']}:{m.get('mode', 'rw')}")
    if binds:
        config["HostConfig"]["Binds"] = binds
    config["HostConfig"]["Mounts"] = mounts  # format natif Docker
```

Pour K8s (futur), les mounts abstraits seraient traduits en `volumeMounts` + `volumes` dans le spec du Pod.

### Fichiers backend à modifier

- `backend/app/schemas/docker.py` — ajouter `ContainerRecreateRequest` et `ContainerRecreateResponse`
- `backend/app/services/docker_client_service.py` — étendre `create_container()` + ajouter `recreate_container()`
- `backend/app/api/v1/docker.py` — ajouter le route handler `POST /containers/{id}/recreate`

### Schéma de requête

```python
class ContainerRecreateRequest(BaseModel):
    image: Optional[str] = None          # si None, conserve l'image actuelle
    pull_image: bool = False             # pull avant de recréer (si image fournie ou actuelle)
    env: Optional[list[str]] = None      # format ["KEY=VALUE", ...]
    labels: Optional[dict[str, str]] = None
    port_bindings: Optional[dict[str, Any]] = None
    mounts: Optional[list[dict[str, Any]]] = None
    privileged: Optional[bool] = None
    readonly_rootfs: Optional[bool] = None
    cap_add: Optional[list[str]] = None
    cap_drop: Optional[list[str]] = None
    stop_timeout: int = Field(10, ge=0, le=300)
```

### Schéma de réponse

```python
class ContainerRecreateResponse(BaseModel):
    success: bool
    message: str
    old_container_id: str
    new_container_id: str
    container: ContainerDetailResponse
    warnings: list[str] = []
```

### Contrainte critique

Si la suppression réussit mais la création échoue, logger l'incident (le container original est perdu — erreur non rattrapable) et retourner HTTP 500 avec `old_container_id` dans le message d'erreur.

### Rate limit

10 requêtes/min (opération coûteuse).

## Critères d'acceptation (AC)

- [x] AC 1 : `POST /docker/containers/{container_id}/recreate` est disponible et documenté dans OpenAPI
- [x] AC 2 : Les champs `None` dans la requête conservent la valeur actuelle du container (merge, pas remplacement total)
- [x] AC 3 : Si `pull_image=True`, l'image est pullée avant la recréation
- [x] AC 4 : L'image du container peut être modifiée (ex: `nginx:latest` → `nginx:1.26`)
- [x] AC 5 : Le nouveau container est démarré automatiquement après recréation
- [x] AC 6 : La réponse contient `old_container_id` et `new_container_id`
- [x] AC 7 : Si le container source n'existe pas → HTTP 404
- [x] AC 8 : Si la suppression réussit mais la création échoue → HTTP 500 avec détail explicite incluant `old_container_id`
- [x] AC 9 : Les named volumes et bind mounts du container original sont préservés (recréés avec la même config)
- [x] AC 10 : Tests unitaires couvrant les cas nominaux et d'erreur (≥ 80%)

## Dépendances

- Aucune dépendance sur d'autres stories de cette epic

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter `ContainerRecreateRequest` et `ContainerRecreateResponse` dans `schemas/docker.py`

**Fichier** : `backend/app/schemas/docker.py`
**Emplacement** : Après `ContainerCreateRequest` (~ligne 465)

Ajouter les deux classes Pydantic :
- `ContainerRecreateRequest` : tous les champs optionnels (`None` = conserver la valeur actuelle), `stop_timeout` avec validation (0-300s, défaut 10)
- `ContainerRecreateResponse` : `success`, `message`, `old_container_id`, `new_container_id`, `container` (ContainerDetailResponse), `warnings`

### Tâche 2 : Étendre `create_container()` + ajouter `recreate_container()` dans `docker_client_service.py`

**Fichier** : `backend/app/services/docker_client_service.py`

#### 2a. Étendre `create_container()`

Ajouter les paramètres optionnels suivants à la signature existante :
- `mounts: Optional[list[dict[str, Any]]] = None`
- `cap_add: Optional[list[str]] = None`
- `cap_drop: Optional[list[str]] = None`
- `readonly_rootfs: Optional[bool] = None`
- `port_bindings: Optional[dict[str, Any]] = None`

Dans le body de la méthode, ajouter la conversion de ces params en Docker API format :
- `mounts` → `HostConfig.Mounts` + `HostConfig.Binds` (conversion bind mounts)
- `cap_add` → `HostConfig.CapAdd`
- `cap_drop` → `HostConfig.CapDrop`
- `readonly_rootfs` → `HostConfig.ReadonlyRootfs`
- `port_bindings` → `HostConfig.PortBindings` + `ExposedPorts`

#### 2b. Ajouter `recreate_container()`

Nouvelle méthode avec la signature :
```python
async def recreate_container(
    self,
    container_id: str,
    image: Optional[str] = None,
    pull_image: bool = False,
    env: Optional[list[str]] = None,
    labels: Optional[dict[str, str]] = None,
    port_bindings: Optional[dict[str, Any]] = None,
    mounts: Optional[list[dict[str, Any]]] = None,
    privileged: Optional[bool] = None,
    readonly_rootfs: Optional[bool] = None,
    cap_add: Optional[list[str]] = None,
    cap_drop: Optional[list[str]] = None,
    stop_timeout: int = 10,
) -> tuple[str, ContainerDetail]:
```

Logique :
1. Inspect via `get_container(container_id)` → remonte 404 si non trouvé
2. Merge config : chaque champ `None` dans la requête prend la valeur de l'inspect existant
   - Image : `image or detail.config.get("Image")`
   - Env : `env or detail.config.get("Env")`
   - Labels : `labels or detail.config.get("Labels")`
   - PortBindings : `port_bindings or detail.host_config.get("PortBindings")`
   - Mounts : `mounts or detail.mounts`
   - Privileged : `privileged or detail.host_config.get("Privileged")`
   - CapAdd/CapDrop : depuis `detail.host_config`
   - ReadonlyRootfs : depuis `detail.host_config`
   - NetworkMode : conservé depuis `detail.host_config.get("NetworkMode")`
   - RestartPolicy : conservé depuis `detail.host_config.get("RestartPolicy")`
   - Cmd/Entrypoint : conservés depuis `detail.config`
3. Si `pull_image=True` : appeler `pull_image()` avec l'image merged
4. `stop_container(container_id, timeout=stop_timeout)`
5. `remove_container(container_id, force=True, remove_volumes=False)` — **volumes préservés !**
6. **Chemin critique** : si étape 6 ou 7 échoue après étape 5, logger en CRITICAL et lever exception avec `old_container_id`
7. `create_container(name=..., image=merged_image, mounts=merged_mounts, cap_add=..., ...)` avec params étendus
8. `start_container(new_id)`
9. `get_container(new_id)` pour récupérer le détail complet
10. Retourner `(new_id, new_detail)`

### Tâche 3 : Implémenter le handler `recreate_container()` dans `docker.py` (routes)

**Fichier** : `backend/app/api/v1/docker.py`
**Emplacement** : Après `remove_container()`, avant `update_restart_policy()`

Route handler fin :
- `POST /containers/{container_id}/recreate`
- `response_model=ContainerRecreateResponse`
- Rate limit : `conditional_rate_limiter(10, 60)`
- Import `ContainerRecreateRequest`, `ContainerRecreateResponse`
- Appelle `client.recreate_container(container_id, ...)` avec les params de la requête
- Construit et retourne `ContainerRecreateResponse`
- Gestion 404 (container non trouvé), 500 (erreur chemin critique), erreurs générales

### Tâche 4 : Écrire les tests unitaires dans `test_container_recreate.py`

**Fichier** : `backend/tests/unit/test_docker/test_container_recreate.py` (nouveau)

Pattern de test : même approche que `test_docker_config_update.py` (FastAPI app + httpx AsyncClient + mock `get_docker_client`).

Tests à écrire :

1. `test_recreate_success_no_overrides` — Tous champs None → merge complet depuis l'inspect, recréation OK
2. `test_recreate_with_image_override` — Changement d'image (`nginx:latest` → `nginx:1.26`), vérifie que `create_container` est appelé avec la nouvelle image
3. `test_recreate_with_env_override` — Override des variables d'environnement
4. `test_recreate_with_labels_override` — Override des labels
5. `test_recreate_with_port_bindings_override` — Override des port bindings
6. `test_recreate_mounts_preserved` — Les volumes/bind mounts du container original sont préservés (AC 9)
7. `test_recreate_privileged_and_caps` — Override privileged, cap_add, cap_drop
8. `test_recreate_readonly_rootfs` — Override readonly_rootfs
9. `test_recreate_with_pull_image` — `pull_image=True` déclenche un appel à `pull_image()` (AC 3)
10. `test_recreate_container_not_found` — Container inexistant → 404 (AC 7)
11. `test_recreate_stop_fails` — Erreur au stop → erreur 500 remontée
12. `test_recreate_remove_succeeds_create_fails` — Chemin critique : remove OK mais create échoue → 500 avec `old_container_id` dans le détail (AC 8)
13. `test_recreate_remove_succeeds_start_fails` — Chemin critique : remove + create OK mais start échoue → 500 avec `old_container_id`
14. `test_recreate_auto_start` — Vérifie que `start_container` est appelé après création (AC 5)
15. `test_recreate_response_contains_ids` — Vérifie `old_container_id` et `new_container_id` dans la réponse (AC 6)
16. `test_recreate_schema_validation` — Validation Pydantic : `stop_timeout` hors bornes, types invalides

## Tests à écrire

Voir Tâche 4 ci-dessus — 16 tests unitaires couvrant :
- **Cas nominaux** : recréation sans overrides, avec overrides partiels, avec pull, préservation mounts
- **Cas d'erreur** : container non trouvé (404), échec stop, chemin critique remove→create fail (500), chemin critique remove→start fail (500)
- **Validation** : schémas Pydantic, types, bornes stop_timeout

## État d'avancement technique

- [x] Tâche 1 : Ajouter `ContainerRecreateRequest` et `ContainerRecreateResponse` dans `schemas/docker.py`
- [x] Tâche 2a : Étendre `create_container()` dans `docker_client_service.py`
- [x] Tâche 2b : Ajouter `recreate_container()` dans `docker_client_service.py`
- [x] Tâche 3 : Implémenter le handler `recreate_container()` dans `docker.py` (routes)
- [x] Tâche 4 : Écrire les tests unitaires dans `test_container_recreate.py`

## Notes d'implémentation

### Fichiers modifiés/créés

- **`backend/app/schemas/docker.py`** — Ajout de `ContainerRecreateRequest` (10 champs optionnels + stop_timeout) et `ContainerRecreateResponse` (success, message, old/new IDs, container detail, warnings)
- **`backend/app/services/docker_client_service.py`** — Extension de `create_container()` avec 5 nouveaux params (mounts, cap_add, cap_drop, readonly_rootfs, port_bindings) + nouvelle méthode `recreate_container()` (~110 lignes) avec merge config, stop→remove→create→start flow, gestion chemin critique
- **`backend/app/api/v1/docker.py`** — Nouveau handler `POST /containers/{container_id}/recreate` (~85 lignes) avec rate limit 10/min, gestion 404/500/critical path
- **`backend/tests/unit/test_docker/test_container_recreate.py`** — 18 tests unitaires (11 nominaux, 4 erreurs, 3 validation)

### Décisions techniques

- **Merge None = conserver** : chaque champ optionnel à `None` prend la valeur de l'inspect existant du container
- **Mounts en format natif Docker** : Les mounts sont passés tels quels à `HostConfig.Mounts`, avec extraction des binds pour `HostConfig.Binds`
- **PortBindings + ExposedPorts** : Si port_bindings fourni, les ports sont aussi ajoutés à `ExposedPorts` du container config
- **Chemin critique** : `RuntimeError` levée avec `old_container_id` dans le message si remove réussit mais create/start échoue. Le handler route attrape cette erreur et la loggue en CRITICAL
- **stop_container tolérant** : Les erreurs de stop sont ignorées (le container peut déjà être arrêté)

### Tests — Résultats

```
18 passed in 1.82s
```

Couverture : 11 tests nominaux (AC 1-6, 9), 4 tests d'erreur (AC 7-8), 3 tests validation schéma (AC 10)
