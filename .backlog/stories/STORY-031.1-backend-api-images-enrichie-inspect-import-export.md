# STORY-031.1 : Backend — API Images enrichie, inspect et import/export

**Statut :** TODO
**Story Parente :** STORY-031 — Images Docker — Sélection, actions en lot, usage et détail
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux que le backend expose toutes les capacités nécessaires pour manipuler les images Docker : enrichir la liste avec un indicateur d'utilisation par containers, inspecter une image individuellement, et importer/exporter des images via des fichiers tar. Cette sous-story fournit la fondation API sur laquelle le frontend s'appuiera.

## Critères d'acceptation (AC)
- [ ] AC 2 : L'import d'image (upload fichier tar via `docker load`) et l'export d'image (download tar via `docker save`, pour les images sélectionnées ou une image individuelle) fonctionnent
- [ ] AC 3 : Chaque image affiche un indicateur d'utilisation (utilisée/non utilisée par des containers) et un filtre permet d'afficher uniquement les images utilisées ou non utilisées (fondation backend)

## Contexte technique

### Fichiers de référence (patterns)
| Couche | Fichier de référence | Pattern à suivre |
|--------|---------------------|------------------|
| Backend schema | `backend/app/schemas/docker.py` — `ImageResponse` | Champs avec `populate_by_name=True`, alias camelCase |
| Backend endpoint | `backend/app/api/v1/docker.py` — `list_images`, `remove_image` | Error handling `aiohttp.ClientResponseError`, `conditional_rate_limiter` |
| Backend service | `backend/app/services/docker_client_service.py` — `inspect_image` | Appel API Docker via `_request`, parsing JSON |

### Exigences sécurité identifiées
- **Auth** : oui — `get_current_user` recommandé sur les endpoints d'import/export (`load`/`save`) car ce sont des actions critiques. Les endpoints de lecture (`list`, `get`) suivent le pattern existant des endpoints Docker (pas de `get_current_user` injecté explicitement, auth gérée au niveau router global).
- **RBAC** : rôles autorisés = viewer, operator, admin (lecture) ; operator, admin (modification) — mais le backend ne vérifie pas les rôles sur les endpoints Docker actuels. Suivre le pattern existant.
- **Validation** : `image_id` dans le path doit être non-vide (`min_length=1`). Le fichier tar uploadé doit être validé (type MIME, taille max).
- **Audit** : suppression en lot et import/export sont des actions critiques → prévoir un log structuré `logger.info("bulk_remove_images", extra={"user_id": ..., "count": ...})`.

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Backend — Enrichir ImageResponse avec `in_use` et `containers_count`
**Objectif :** Permettre au frontend de savoir si une image est utilisée par des containers et combien, en croisant la liste des images avec la liste des containers au niveau de l'endpoint.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Ajouter à `ImageResponse` :
  ```python
  in_use: bool = Field(False, alias="inUse", description="Image utilisée par au moins un container")
  containers_count: int = Field(0, alias="containersCount", description="Nombre de containers utilisant cette image")
  ```
- `backend/app/services/docker_client_service.py` — Modifier — Ajouter à `ImageInfo` dataclass :
  ```python
  in_use: bool = False
  containers_count: int = 0
  ```
- `backend/app/api/v1/docker.py` — Modifier — Dans `list_images`, après avoir récupéré la liste des images, appeler `client.list_containers()` pour obtenir tous les containers, construire un mapping `image_id → count` à partir de `c.image_id` (champ `Image` dans la config du container), puis enrichir chaque `ImageResponse` avec `in_use` et `containers_count` avant de les retourner.
**Exigences sécurité :** Aucune exigence spécifique (endpoint de lecture, pattern existant)
**Dépend de :** Aucune

### Tâche 2 : Backend — Endpoint `GET /docker/images/{id}` (inspect image)
**Objectif :** Exposer l'inspect Docker d'une image via l'API REST pour alimenter la vue de détail.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Créer `ImageDetailResponse` (pattern : `ContainerDetailResponse`) :
  ```python
  class ImageDetailResponse(BaseModel):
      id: str
      repo_tags: list[str] = Field(default_factory=list, alias="repoTags")
      repo_digests: list[str] = Field(default_factory=list, alias="repoDigests")
      created: datetime
      size: int
      virtual_size: int = Field(0, alias="virtualSize")
      labels: dict[str, str] = Field(default_factory=dict)
      architecture: str = Field("", description="Architecture de l'image")
      os: str = Field("", description="OS de l'image")
      cmd: list[str] | None = Field(None, description="Commande par défaut")
      entrypoint: list[str] | None = Field(None, description="Point d'entrée")
      env: list[str] | None = Field(None, description="Variables d'environnement par défaut")
      exposed_ports: dict[str, Any] | None = Field(None, alias="exposedPorts")
      config: dict[str, Any] | None = Field(None, description="Configuration complète de l'image")
      model_config = ConfigDict(populate_by_name=True)
  ```
- `backend/app/api/v1/docker.py` — Modifier — Ajouter endpoint `get_image` :
  - Route `GET /docker/images/{image_id}` avec `response_model=ImageDetailResponse`
  - Appeler `client.inspect_image(image_id)`
  - Parser le dict Docker pour peupler `ImageDetailResponse` (champs PascalCase → snake_case)
  - Gérer `aiohttp.ClientResponseError` 404 → HTTP 404
  - `conditional_rate_limiter(100, 60)`
**Exigences sécurité :** Aucune exigence spécifique (endpoint de lecture)
**Dépend de :** Aucune

### Tâche 3 : Backend — Endpoints import/export d'images (save/load)
**Objectif :** Permettre l'import d'une image via upload de fichier tar (`docker load`) et l'export d'une image en téléchargement de fichier tar (`docker save`).
**Fichiers :**
- `backend/app/services/docker_client_service.py` — Modifier — Ajouter :
  - `save_image(self, image_id: str) → bytes` : appelle `GET /images/{image_id}/get` et retourne le contenu binaire du tar
  - `load_image(self, tar_bytes: bytes) → str` : appelle `POST /images/load` avec le body binaire, retourne le message de statut
- `backend/app/api/v1/docker.py` — Modifier — Ajouter deux endpoints :
  - `POST /docker/images/load` — Accepte `UploadFile`, lit les bytes, appelle `client.load_image()`, retourne `{"success": true, "message": "..."}`
  - `GET /docker/images/{image_id}/save` — Appelle `client.save_image()`, retourne `Response(content=tar_bytes, media_type="application/x-tar", headers={"Content-Disposition": f"attachment; filename={image_id}.tar"})`
  - `conditional_rate_limiter(10, 60)` pour les deux (opérations lourdes)
**Exigences sécurité :** `get_current_user` recommandé sur ces endpoints (actions critiques) — mais suivre le pattern existant des endpoints docker si pas d'injection systématique. Valider le fichier uploadé (taille max ~2Go, type MIME `application/x-tar` ou `application/octet-stream`).
**Dépend de :** Aucune

### Tâche 4 : Tests unitaires backend
**Objectif :** Couvrir les nouveaux endpoints backend avec des tests unitaires.
**Fichiers :**
- `backend/tests/unit/test_docker/test_images_inspect.py` — Créer — Tests de l'endpoint inspect image :
  - `test_get_image_returns_200_and_detail` — cas nominal, retourne `ImageDetailResponse` avec champs attendus
  - `test_get_image_returns_404_when_not_found` — image inexistante
  - `test_get_image_returns_401_without_token` — **sécurité** : accès sans JWT
- `backend/tests/unit/test_docker/test_images_list_in_use.py` — Créer — Tests de la liste enrichie :
  - `test_list_images_marks_in_use_correctly` — image utilisée → `in_use=true`, `containers_count>0`
  - `test_list_images_marks_unused_correctly` — image non utilisée → `in_use=false`, `containers_count=0`
- `backend/tests/unit/test_docker/test_images_import_export.py` — Créer — Tests import/export :
  - `test_load_image_returns_success` — upload tar valide → 200
  - `test_save_image_returns_tar` — download → `Content-Type: application/x-tar`
  - `test_load_image_returns_401_without_token` — **sécurité**
**Exigences sécurité :** Tests 401, 404, route protégée
**Dépend de :** Tâches 1, 2, 3

## Tests à écrire

### Backend
- `backend/tests/unit/test_docker/test_images_inspect.py`
  - `test_get_image_returns_200_and_detail` — cas nominal avec données mockées
  - `test_get_image_returns_404_when_not_found` — image inexistante
  - `test_get_image_returns_401_without_token` — sécurité : pas d'accès sans auth

- `backend/tests/unit/test_docker/test_images_list_in_use.py`
  - `test_list_images_marks_in_use_correctly` — image avec container associé
  - `test_list_images_marks_unused_correctly` — image orpheline

- `backend/tests/unit/test_docker/test_images_import_export.py`
  - `test_load_image_returns_success` — upload tar → succès
  - `test_save_image_returns_tar` — download → blob tar
  - `test_load_image_returns_401_without_token` — sécurité

### Commandes de validation
```bash
# Backend
poetry run pytest backend/tests/unit/test_docker/test_images_inspect.py -v
poetry run pytest backend/tests/unit/test_docker/test_images_list_in_use.py -v
poetry run pytest backend/tests/unit/test_docker/test_images_import_export.py -v
```

## État d'avancement technique
- [ ] Tâche 1 : Backend — Enrichir ImageResponse avec in_use et containers_count
- [ ] Tâche 2 : Backend — Endpoint GET /docker/images/{id} (inspect image)
- [ ] Tâche 3 : Backend — Endpoints import/export d'images (save/load)
- [ ] Tâche 4 : Tests unitaires backend
- [ ] Build & lint OK

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
