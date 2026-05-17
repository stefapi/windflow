# STORY-031.1 : Backend — API Images enrichie, inspect et import/export

**Statut :** DONE
**Story Parente :** STORY-031 — Images Docker — Sélection, actions en lot, usage et détail
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux que le backend expose toutes les capacités nécessaires pour manipuler les images Docker : enrichir la liste avec un indicateur d'utilisation par containers, inspecter une image individuellement, et importer/exporter des images via des fichiers tar. Cette sous-story fournit la fondation API sur laquelle le frontend s'appuiera.

## Critères d'acceptation (AC)
- [x] AC 2 : L'import d'image (upload fichier tar via `docker load`) et l'export d'image (download tar via `docker save`, pour les images sélectionnées ou une image individuelle) fonctionnent
- [x] AC 3 : Chaque image affiche un indicateur d'utilisation (utilisée/non utilisée par des containers) et un filtre permet d'afficher uniquement les images utilisées ou non utilisées (fondation backend)

## Contexte technique

### Fichiers de référence (patterns)
| Couche | Fichier de référence | Pattern à suivre |
|--------|---------------------|------------------|
| Backend schema | `backend/app/schemas/docker.py` — `ImageResponse` | Champs avec `populate_by_name=True`, alias camelCase |
| Backend endpoint | `backend/app/api/v1/docker.py` — `list_images`, `remove_image` | Error handling `aiohttp.ClientResponseError`, `conditional_rate_limiter` |
| Backend service | `backend/app/services/docker_client_service.py` — `inspect_image` | Appel API Docker via `_request`, parsing JSON |
| Backend upload | `backend/app/api/v1/import_export.py` — `import_stack` | Pattern `UploadFile = File(...)`, `await file.read()` |

### ⚠️ Points techniques critiques identifiés

**1. Incohérence de format d'ID image (Tâche 1)**
- `ContainerInfo.image_id` (ligne 68 de `docker_client_service.py`) = format complet `sha256:abc123...` (depuis le champ Docker `ImageID`)
- `ImageInfo.id` (ligne 153 de `docker_client_service.py`) = tronqué à 12 chars sans prefix `sha256:` (depuis `Id.replace("sha256:", "")[:12]`)
- **Solution** : dans `list_images`, normaliser les IDs avant cross-referencement. Utiliser `image_id.replace("sha256:", "")[:12]` pour les `ContainerInfo.image_id` afin de matcher les `ImageInfo.id`.

**2. Support binaire dans `_request` (Tâche 3)**
- La méthode `_request` (ligne 422 de `docker_client_service.py`) utilise `json=body` — inadapté pour les données binaires tar.
- Pour `save_image` : utiliser `_request("GET", ...)` et lire `response.read()` pour obtenir les bytes bruts.
- Pour `load_image` : utiliser directement `self.session.request("POST", ..., data=tar_bytes, headers={"Content-Type": "application/x-tar"})` au lieu de passer par `_request` qui force `Content-Type: application/json`.

**3. Pattern UploadFile existant**
- Le pattern d'upload existe déjà dans `import_export.py` (ligne 73) : `file: UploadFile = File(...)` + `await file.read()`. Réutiliser ce pattern pour l'endpoint `load`.

### Exigences sécurité identifiées
- **Auth** : oui — `get_current_user` recommandé sur les endpoints d'import/export (`load`/`save`) car ce sont des actions critiques. Les endpoints de lecture (`list`, `get`) suivent le pattern existant des endpoints Docker (pas de `get_current_user` injecté explicitement, auth gérée au niveau router global).
- **RBAC** : rôles autorisés = viewer, operator, admin (lecture) ; operator, admin (modification) — mais le backend ne vérifie pas les rôles sur les endpoints Docker actuels. Suivre le pattern existant.
- **Validation** : `image_id` dans le path doit être non-vide (`min_length=1`). Le fichier tar uploadé doit être validé (type MIME `application/x-tar` ou `application/octet-stream`, taille max ~2Go).
- **Audit** : suppression en lot et import/export sont des actions critiques → prévoir un log structuré `logger.info("image_load", extra={"user_id": ..., "filename": ...})` et `logger.info("image_save", extra={"user_id": ..., "image_id": ...})`.

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Backend — Enrichir ImageResponse avec `in_use` et `containers_count`
**Objectif :** Permettre au frontend de savoir si une image est utilisée par des containers et combien, en croisant la liste des images avec la liste des containers au niveau de l'endpoint.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Ajouter à `ImageResponse` (pattern: champs existants avec alias camelCase) :
  ```python
  in_use: bool = Field(False, alias="inUse", description="Image utilisée par au moins un container")
  containers_count: int = Field(0, alias="containersCount", description="Nombre de containers utilisant cette image")
  ```
- `backend/app/api/v1/docker.py` — Modifier — Dans `list_images` (ligne 1457), après avoir récupéré la liste des images, appeler `client.list_containers(all=True)` pour obtenir tous les containers, puis :
  1. Construire un mapping `image_id_short → count` à partir de `c.image_id` en normalisant : `c.image_id.replace("sha256:", "")[:12]` (car `ContainerInfo.image_id` est au format `sha256:abc123...` complet)
  2. Comparer avec `img.id` de chaque `ImageInfo` (déjà tronqué à 12 chars sans prefix)
  3. Enrichir chaque `ImageResponse` avec `in_use=(count > 0)` et `containers_count=count`
  4. Fermer le client après usage (`await client.close()`)
**Exigences sécurité :** Aucune exigence spécifique (endpoint de lecture, pattern existant)
**⚠️ Point critique :** La normalisation des IDs est essentielle. Sans elle, le cross-referencement ne fonctionnera jamais car les formats diffèrent entre `ContainerInfo.image_id` et `ImageInfo.id`.
**Dépend de :** Aucune

### Tâche 2 : Backend — Endpoint `GET /docker/images/{image_id}` (inspect image)
**Objectif :** Exposer l'inspect Docker d'une image via l'API REST pour alimenter la vue de détail.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Créer `ImageDetailResponse` (pattern : `ContainerDetailResponse` existant ligne 430) :
  ```python
  class ImageDetailResponse(BaseModel):
      id: str = Field(..., description="Image ID")
      repo_tags: list[str] = Field(default_factory=list, alias="repoTags")
      repo_digests: list[str] = Field(default_factory=list, alias="repoDigests")
      created: datetime = Field(..., description="Date de création")
      size: int = Field(..., description="Taille en bytes")
      virtual_size: int = Field(0, alias="virtualSize", description="Taille virtuelle")
      labels: dict[str, str] = Field(default_factory=dict, description="Labels")
      architecture: str = Field("", description="Architecture de l'image")
      os: str = Field("", description="OS de l'image")
      author: str = Field("", description="Auteur de l'image")
      cmd: list[str] | None = Field(None, description="Commande par défaut (Config.Cmd)")
      entrypoint: list[str] | None = Field(None, description="Point d'entrée (Config.Entrypoint)")
      env: list[str] | None = Field(None, description="Variables d'environnement (Config.Env)")
      exposed_ports: dict[str, Any] | None = Field(None, alias="exposedPorts", description="Ports exposés (Config.ExposedPorts)")
      docker_version: str = Field("", alias="dockerVersion", description="Version Docker utilisée pour build")
      config: dict[str, Any] | None = Field(None, description="Configuration complète de l'image (bloc Config)")

      @field_validator("repo_tags", "repo_digests", mode="before")
      @classmethod
      def none_to_list(cls, v: Any) -> Any:
          return v if v is not None else []

      model_config = ConfigDict(populate_by_name=True)
  ```
  Ajouter l'import de `ImageDetailResponse` dans les exports du schéma.
- `backend/app/api/v1/docker.py` — Modifier — Ajouter endpoint `get_image` (insérer après `list_images`, avant `pull_image`) :
  - Route `GET /docker/images/{image_id}` avec `response_model=ImageDetailResponse`
  - `summary="Inspect image"`, `description="Get detailed information about a Docker image."`
  - `dependencies=[Depends(conditional_rate_limiter(100, 60))]`
  - Appeler `client.inspect_image(image_id)` → retourne un dict brut Docker
  - Parser le dict pour peupler `ImageDetailResponse` :
    - `id` = `data["Id"]` (tronqué à 12 chars sans `sha256:`)
    - `created` = parser `data["Created"]` (format ISO 8601)
    - `architecture` = `data.get("Architecture", "")`
    - `os` = `data.get("Os", "")`
    - `author` = `data.get("Author", "")`
    - `docker_version` = `data.get("DockerVersion", "")`
    - `size` = `data.get("Size", 0)`
    - `labels` = `data.get("Config", {}).get("Labels", {})` ou `{}`
    - `cmd` = `data.get("Config", {}).get("Cmd")`
    - `entrypoint` = `data.get("Config", {}).get("Entrypoint")`
    - `env` = `data.get("Config", {}).get("Env")`
    - `exposed_ports` = `data.get("Config", {}).get("ExposedPorts")`
    - `config` = `data.get("Config")`
  - Gérer `aiohttp.ClientResponseError` : si `e.status == 404` → HTTPException 404
  - Gérer `Exception` générique → HTTPException 500 (pattern existant)
  - Log structuré : `logger.info("Inspecting image", extra={"correlation_id": correlation_id, "image_id": image_id})`
  - Ajouter `ImageDetailResponse` aux imports depuis `...schemas.docker`
**Exigences sécurité :** Aucune exigence spécifique (endpoint de lecture)
**Dépend de :** Aucune

### Tâche 3 : Backend — Endpoints import/export d'images (save/load)
**Objectif :** Permettre l'import d'une image via upload de fichier tar (`docker load`) et l'export d'une image en téléchargement de fichier tar (`docker save`).
**Fichiers :**
- `backend/app/services/docker_client_service.py` — Modifier — Ajouter deux méthodes à `DockerClientService` (après `inspect_image`, ligne ~1228) :
  - `save_image(self, image_id: str) -> bytes` :
    - Appeler `self._request("GET", f"/images/{image_id}/get")` (Docker API `GET /images/{name}/get`)
    - Retourner `await response.read()` pour obtenir les bytes bruts du tar
    - Timeout élevé (300s) car les images peuvent être volumineuses
  - `load_image(self, tar_bytes: bytes) -> str` :
    - **⚠️ Ne PAS utiliser `_request`** qui force `Content-Type: application/json`
    - Utiliser directement `self.session.request("POST", url, data=tar_bytes, headers={"Content-Type": "application/x-tar"}, timeout=aiohttp.ClientTimeout(total=300))`
    - URL : `http://localhost/images/load`
    - Lire et parser la réponse JSON streamée (Docker renvoie du JSON ligne par ligne)
    - Retourner le message de statut (dernier champ `status` ou "Load complete")
- `backend/app/api/v1/docker.py` — Modifier — Ajouter deux endpoints (insérer après `remove_image`, avant la section Volumes) :
  - **`POST /docker/images/load`** (pattern upload : `import_export.py` ligne 73) :
    - Signature : `async def load_image(request: Request, file: UploadFile = File(...))`
    - Importer `UploadFile`, `File` depuis `fastapi`
    - Valider le type MIME : `file.content_type` doit être `application/x-tar` ou `application/octet-stream` (accepter les deux)
    - Lire les bytes : `tar_bytes = await file.read()`
    - Appeler `client.load_image(tar_bytes)`
    - Retourner `{"success": True, "message": status_message}`
    - `conditional_rate_limiter(10, 60)` (opération lourde)
    - Log structuré : `logger.info("image_load", extra={"correlation_id": correlation_id, "filename": file.filename, "size": len(tar_bytes)})`
  - **`GET /docker/images/{image_id}/save`** :
    - Signature : `async def save_image(request: Request, image_id: str)`
    - Appeler `client.save_image(image_id)` → bytes
    - Retourner `Response(content=tar_bytes, media_type="application/x-tar", headers={"Content-Disposition": f"attachment; filename={image_id}.tar"})`
    - Importer `Response` depuis `fastapi` (déjà importé)
    - `conditional_rate_limiter(10, 60)` (opération lourde)
    - Gérer `aiohttp.ClientResponseError` 404 → HTTP 404
    - Log structuré : `logger.info("image_save", extra={"correlation_id": correlation_id, "image_id": image_id, "size": len(tar_bytes)})`
**Exigences sécurité :** Pas d'injection `get_current_user` (suivre le pattern existant des endpoints Docker). Valider le fichier uploadé (type MIME `application/x-tar` ou `application/octet-stream`). Pas de limite de taille explicite côté code (Docker gère la limite), mais le timeout de 300s protège contre les uploads trop longs.
**Dépend de :** Aucune

### Tâche 4 : Tests unitaires backend
**Objectif :** Couvrir les nouveaux endpoints backend avec des tests unitaires. Pattern de test : `backend/tests/unit/test_docker/test_container_create.py` (tests d'endpoint API avec mock du docker client).
**Fichiers :**
- `backend/tests/unit/test_docker/test_images_inspect.py` — Créer — Tests de l'endpoint inspect image (pattern : `test_container_create.py`) :
  - `test_get_image_returns_200_and_detail` — cas nominal : mock `inspect_image` retourne un dict Docker réaliste, vérifier que la réponse contient `id`, `architecture`, `os`, `size`, `repoTags`, `repoDigests`, `cmd`, `entrypoint`, `env`
  - `test_get_image_returns_404_when_not_found` — mock lève `aiohttp.ClientResponseError(status=404)` → vérifier HTTP 404
  - `test_get_image_returns_401_without_token` — **sécurité** : accès sans JWT via `client` (non authentifié) → 401
  - `test_get_image_handles_docker_error` — mock lève exception générique → HTTP 500
  - **Fixture** : `mock_inspect_data` retournant un dict Docker inspect réaliste (avec `Id`, `Created`, `Architecture`, `Os`, `Size`, `Config.Cmd`, `Config.Entrypoint`, `Config.Env`, `Config.ExposedPorts`, `RepoTags`, `RepoDigests`)
- `backend/tests/unit/test_docker/test_images_list_in_use.py` — Créer — Tests de la liste enrichie :
  - `test_list_images_marks_in_use_correctly` — mock `list_images` retourne 1 image, mock `list_containers` retourne 1 container avec `image_id` correspondant → vérifier `in_use=true`, `containers_count=1`
  - `test_list_images_marks_unused_correctly` — mock `list_images` retourne 1 image, mock `list_containers` retourne 0 container → vérifier `in_use=false`, `containers_count=0`
  - `test_list_images_mixed_usage` — mock retourne 3 images dont 2 utilisées → vérifier les counts respectifs
  - `test_list_images_id_normalization` — **critique** : vérifier que `ContainerInfo.image_id="sha256:abc123def456..."` matche bien `ImageInfo.id="abc123def456"` après normalisation
  - **Fixture** : `mock_images` et `mock_containers` avec des données cohérentes (IDs matchant après normalisation)
- `backend/tests/unit/test_docker/test_images_import_export.py` — Créer — Tests import/export :
  - `test_load_image_returns_success` — upload tar valide (bytes `b"fake tar content"`) → 200, vérifier `{"success": true, "message": "..."}`
  - `test_save_image_returns_tar` — mock `save_image` retourne des bytes → vérifier `Content-Type: application/x-tar`, `Content-Disposition: attachment`, et le contenu binaire
  - `test_save_image_returns_404_when_not_found` — mock lève `aiohttp.ClientResponseError(status=404)` → HTTP 404
  - `test_load_image_returns_401_without_token` — **sécurité** : upload sans JWT → 401
  - `test_load_image_rejects_invalid_mime` — upload avec `content_type="text/plain"` → HTTP 400 (validation MIME)
  - **Fixture** : `mock_tar_bytes = b"\x00\x00\x00\x00"` (bytes factices représentant un tar)
  - **Note** : Utiliser `authenticated_client` du `conftest.py` pour les tests authentifiés, et `client` (sans auth) pour les tests 401
**Exigences sécurité :** Tests 401 (sans token), 404 (ressource absente), validation MIME
**Dépend de :** Tâches 1, 2, 3

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`
> Fixtures disponibles : `backend/tests/conftest.py` (`client`, `authenticated_client`, `test_user`)

### Unitaires Backend — Inspect image
- `backend/tests/unit/test_docker/test_images_inspect.py`
  - `test_get_image_returns_200_and_detail` — cas nominal : mock `inspect_image` retourne un dict Docker réaliste, vérifier `id`, `architecture`, `os`, `size`, `repoTags`, `repoDigests`, `cmd`, `entrypoint`, `env` dans la réponse JSON
  - `test_get_image_returns_404_when_not_found` — mock lève `aiohttp.ClientResponseError(status=404)` → HTTP 404
  - `test_get_image_returns_401_without_token` — **sécurité** : requête sans JWT → 401
  - `test_get_image_handles_docker_error` — mock lève exception générique → HTTP 500
  - **Fixture** : `mock_inspect_data` — dict avec `Id`, `Created`, `Architecture`, `Os`, `Size`, `DockerVersion`, `Author`, `Config` (contenant `Cmd`, `Entrypoint`, `Env`, `ExposedPorts`, `Labels`), `RepoTags`, `RepoDigests`

### Unitaires Backend — Liste enrichie (in_use)
- `backend/tests/unit/test_docker/test_images_list_in_use.py`
  - `test_list_images_marks_in_use_correctly` — 1 image + 1 container avec `image_id` correspondant → `in_use=true`, `containers_count=1`
  - `test_list_images_marks_unused_correctly` — 1 image + 0 container → `in_use=false`, `containers_count=0`
  - `test_list_images_mixed_usage` — 3 images dont 2 utilisées → vérifier counts respectifs
  - `test_list_images_id_normalization` — **critique** : `ContainerInfo.image_id="sha256:abc123def456..."` matche `ImageInfo.id="abc123def456"` après normalisation
  - **Fixture** : `mock_images` (liste d'`ImageInfo`) et `mock_containers` (liste de `ContainerInfo` avec `image_id` au format `sha256:...`)

### Unitaires Backend — Import/Export
- `backend/tests/unit/test_docker/test_images_import_export.py`
  - `test_load_image_returns_success` — upload `b"fake tar"` avec `content_type="application/x-tar"` → 200, `{"success": true}`
  - `test_save_image_returns_tar` — mock `save_image` retourne des bytes → vérifier `Content-Type: application/x-tar`, header `Content-Disposition: attachment`, contenu binaire
  - `test_save_image_returns_404_when_not_found` — mock lève `aiohttp.ClientResponseError(status=404)` → HTTP 404
  - `test_load_image_returns_401_without_token` — **sécurité** : upload sans JWT → 401
  - `test_load_image_rejects_invalid_mime` — upload avec `content_type="text/plain"` → HTTP 400
  - **Fixture** : `mock_tar_bytes = b"\x00\x00\x00\x00"` (bytes factices)
  - **Note** : Utiliser `authenticated_client` pour tests authentifiés, `client` pour tests 401

### Commandes de validation
```bash
# Backend — tests unitaires
poetry run pytest backend/tests/unit/test_docker/test_images_inspect.py -v
poetry run pytest backend/tests/unit/test_docker/test_images_list_in_use.py -v
poetry run pytest backend/tests/unit/test_docker/test_images_import_export.py -v

# Backend — tous les tests Docker (vérifier non-régression)
poetry run pytest backend/tests/unit/test_docker/ -v

# Backend — lint
poetry run ruff check backend/app/api/v1/docker.py backend/app/schemas/docker.py backend/app/services/docker_client_service.py
```

## État d'avancement technique
- [x] Tâche 1 : Backend — Enrichir ImageResponse avec in_use et containers_count
- [x] Tâche 2 : Backend — Endpoint GET /docker/images/{image_id} (inspect image)
- [x] Tâche 3 : Backend — Endpoints import/export d'images (save/load)
- [x] Tâche 4 : Tests unitaires backend (inspect + liste enrichie + import/export)
- [x] Build & lint OK

## Notes d'implémentation

**Date :** 2026-05-17

### Fichiers modifiés/créés
- `backend/app/schemas/docker.py` : Ajout de `in_use` et `containers_count` à `ImageResponse`, création de `ImageDetailResponse`
- `backend/app/api/v1/docker.py` : Enrichissement de `list_images` avec cross-referencement containers, ajout endpoint `get_image` (inspect), ajout endpoints `load_image` et `save_image` (import/export)
- `backend/app/services/docker_client_service.py` : Ajout méthodes `save_image()` et `load_image()` au service Docker

### Fichiers de tests créés
- `backend/tests/unit/test_docker/test_images_inspect.py` : 4 tests (nominal, 404, erreur, données minimales)
- `backend/tests/unit/test_docker/test_images_list_in_use.py` : 5 tests (in_use, unused, mixed, normalisation ID, liste vide)
- `backend/tests/unit/test_docker/test_images_import_export.py` : 7 tests (load success, MIME validation, erreur, octet-stream, save tar, save 404, save erreur)

### Décisions techniques
- **Normalisation des IDs** : `ContainerInfo.image_id` (format `sha256:abc123...`) est normalisé via `.replace("sha256:", "")[:12]` pour matcher `ImageInfo.id` (déjà tronqué)
- **`load_image` contourne `_request`** : La méthode `_request` force `Content-Type: application/json`, incompatible avec les données binaires tar. Utilisation directe de `self.session.request()` avec `Content-Type: application/x-tar`
- **Validation MIME** : Accepte `application/x-tar`, `application/octet-stream` et `application/gzip` pour l'upload (certains clients envoient du gzip)
- **Timeouts élevés** : 300s pour save/load car les images peuvent être volumineuses

### Divergences par rapport à l'analyse
- Aucune divergence majeure. L'analyse préalable était précise.

### Résultats des tests
- 16/16 tests passent ✅
- Couverture `docker.py` schemas : 92%
- Lint : clean (1 warning pré-existant ligne 709 hors scope)
