# STORY-031 : Images Docker — Sélection, actions en lot, usage et détail

**Statut :** IN_PROGRESS
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration

## Description
En tant qu'utilisateur DevOps, je veux pouvoir sélectionner des images Docker via des cases à cocher (individuelle ou sélection globale), appliquer des actions en lot (remove, force_remove), importer/exporter des images, voir si une image est utilisée par des containers, filtrer sur ce critère, et cliquer sur une image pour afficher son détail.

## Contexte technique

### Comportement actuel
- La vue `views/Images.vue` affiche un tableau basique avec colonnes ID, Tags, Taille, Date de création et un champ de recherche
- `imagesApi` dans `services/api.ts` ne dispose que de `list()`
- Backend : `GET /docker/images`, `POST /docker/images/pull`, `DELETE /docker/images/{id}?force=false`
- Le service backend `docker_client_service.py` a une méthode `inspect_image()` mais aucun endpoint API ne l'expose
- Aucune indication d'utilisation (image utilisée par des containers ou non)
- Aucune route pour l'import/export d'images Docker (save/load)
- Pas de vue détail image

### Comportement attendu
- **Sélection** : colonne de checkboxes dans le tableau avec case globale dans le header (pattern `el-table` avec `@selection-change`)
- **Actions en lot** : barre d'actions contextuelle (pattern `BulkActionBar.vue` de STORY-023) avec boutons Remove et Force Remove, visibles uniquement quand des images sont sélectionnées
- **Import/Export** : boutons dans le header pour importer (upload tar) et exporter (download tar) des images
- **Utilisation** : colonne indiquant si l'image est utilisée par des containers (badge vert/rouge), avec filtre dédié
- **Détail** : clic sur une ligne → navigation vers `ImageDetail.vue` (écran vide/stub pour le moment, avec juste les infos de base de l'image)
- **Backend** : enrichir `ImageResponse` avec un champ `in_use` (booléen) et le nombre de containers; ajouter endpoint `GET /docker/images/{id}` pour l'inspect; ajouter endpoints save/load pour import/export

### Fichiers de référence (patterns)
| Couche | Fichier de référence | Pattern à suivre |
|--------|---------------------|------------------|
| Backend schema | `backend/app/schemas/docker.py` — `ImageResponse` | Champs avec `populate_by_name=True`, alias camelCase |
| Backend endpoint | `backend/app/api/v1/docker.py` — `list_images`, `remove_image` | Error handling `aiohttp.ClientResponseError`, `conditional_rate_limiter` |
| Backend service | `backend/app/services/docker_client_service.py` — `inspect_image` | Appel API Docker via `_request`, parsing JSON |
| Frontend type | `frontend/src/types/api.ts` — `ImageResponse`, `ContainerDetail` | Interfaces camelCase, snake_case pour les réponses backend |
| Frontend API | `frontend/src/services/api.ts` — `imagesApi` | Objet avec méthodes retournant `http.get/post/delete` |
| Frontend vue liste | `frontend/src/views/Images.vue` | `el-table`, `el-card`, `script setup lang="ts"`, `formatBytes` |
| Frontend vue détail | `frontend/src/views/ContainerDetail.vue` | Structure onglets, `onMounted`, `ElMessage` |
| Frontend composant bulk | `frontend/src/components/compute/BulkActionBar.vue` | Props `selected-count`, slot actions |
| Frontend router | `frontend/src/router/index.ts` | Route lazy-loaded avec `props: true` si besoin |
| Frontend tests | `frontend/tests/unit/views/Images.spec.ts` | `vi.mock('@/services/api')`, `mount` avec `ElementPlus` |

### Exigences sécurité identifiées
- **Auth** : oui — `get_current_user` recommandé sur les endpoints d'import/export (`load`/`save`) car ce sont des actions critiques. Les endpoints de lecture (`list`, `get`) suivent le pattern existant des endpoints Docker (pas de `get_current_user` injecté explicitement, auth gérée au niveau router global).
- **RBAC** : rôles autorisés = viewer, operator, admin (lecture) ; operator, admin (modification) — mais le backend ne vérifie pas les rôles sur les endpoints Docker actuels. Suivre le pattern existant.
- **Validation** : `image_id` dans le path doit être non-vide (`min_length=1`). Le fichier tar uploadé doit être validé (type MIME, taille max).
- **Exposition** : aucun champ sensible dans les réponses images.
- **Audit** : suppression en lot et import/export sont des actions critiques → prévoir un log structuré `logger.info("bulk_remove_images", extra={"user_id": ..., "count": ...})`.

> ⚠️ **Complexité élevée détectée** : cette story dépasse les seuils (>5 tâches, >6 fichiers, backend+frontend). Une découpe en sous-stories est recommandée via `split-story` avant implémentation.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le tableau des images dispose d'une colonne de sélection par checkbox avec sélection globale en-tête, et une barre d'actions apparaît quand des images sont sélectionnées (Remove, Force Remove)
- [ ] AC 2 : L'import d'image (upload fichier tar via `docker load`) et l'export d'image (download tar via `docker save`, pour les images sélectionnées ou une image individuelle) fonctionnent
- [ ] AC 3 : Chaque image affiche un indicateur d'utilisation (utilisée/non utilisée par des containers) et un filtre permet d'afficher uniquement les images utilisées ou non utilisées
- [ ] AC 4 : Cliquer sur une image navigue vers un écran de détail (vue `ImageDetail.vue` stub avec infos de base : ID, tags, size, created, labels, digests)
- [ ] AC 5 : L'amélioration ne casse pas les fonctionnalités existantes (liste, recherche, affichage)
- [ ] AC 6 : Build, lint et tests passent sans erreur

## Sous-stories
- [ ] STORY-031.1 : Backend — API Images enrichie, inspect et import/export — Couvre AC 2, AC 3
- [ ] STORY-031.2 : Frontend — Vue Images complète (sélection, usage, détail) — Couvre AC 1, AC 3, AC 4, AC 5, AC 6

## Dépendances
- STORY-005 (Gestion des images Docker - Liste et visualisation — REVIEW)
- STORY-006 (Gestion des images Docker - Pull et suppression — TODO, partiellement couvert par cette story pour la suppression en lot)

## État d'avancement technique

> ⚠️ L'avancement technique est désormais suivi dans les sous-stories individuelles.

**Progression :** 0/2 sous-stories terminées
- [ ] STORY-031.1 : Backend — API Images enrichie, inspect et import/export
- [ ] STORY-031.2 : Frontend — Vue Images complète (sélection, usage, détail)

## Tâches d'implémentation détaillées

> ⚠️ Cette story a été découpée en sous-stories avant implémentation (complexité détectée par analyse-story).
> Toutes les tâches ont été redistribuées dans les sous-stories listées ci-dessus.
> Consulter chaque sous-story pour les tâches détaillées.

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

### Tâche 4 : Frontend — Types et API service
**Objectif :** Étendre les types TypeScript et le service API pour supporter les nouveaux champs et endpoints.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier —
  1. Ajouter à `ImageResponse` : `inUse: boolean` et `containersCount: number`
  2. Créer `ImageDetailResponse` avec les mêmes champs que le schéma Pydantic backend (camelCase)
- `frontend/src/services/api.ts` — Modifier — Étendre `imagesApi` :
  ```typescript
  export const imagesApi = {
    list: (all: boolean = false) => http.get<ImageResponse[]>('/docker/images', { params: { all } }),
    pull: (data: ImagePullRequest) => http.post<ImagePullResponse>('/docker/images/pull', data),
    remove: (imageId: string, force: boolean = false) => http.delete<void>(`/docker/images/${imageId}`, { params: { force } }),
    get: (imageId: string) => http.get<ImageDetailResponse>(`/docker/images/${imageId}`),
    save: (imageId: string) => http.get<Blob>(`/docker/images/${imageId}/save`, { responseType: 'blob' }),
    load: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return http.post<{ success: boolean; message: string }>('/docker/images/load', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    batchRemove: (imageIds: string[], force: boolean = false) =>
      Promise.all(imageIds.map((id) => http.delete<void>(`/docker/images/${id}`, { params: { force } }))),
  }
  ```
  Ajouter `ImageDetailResponse` aux imports depuis `@/types/api`.
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâches 1, 2, 3

### Tâche 5 : Frontend — Sélection, bulk actions et indicateur d'utilisation dans Images.vue
**Objectif :** Enrichir la vue Images.vue avec la sélection par checkbox, la barre d'actions en lot, l'indicateur d'utilisation, le filtre in_use, les boutons import/export, et la navigation au clic sur une ligne.
**Fichiers :**
- `frontend/src/views/Images.vue` — Modifier —
  1. **Sélection** : Ajouter `<el-table-column type="selection" width="55" />` en première colonne. Ajouter `@selection-change="handleSelectionChange"` sur `el-table`. Créer `selectedImages: Ref<ImageResponse[]>` et `handleSelectionChange(val: ImageResponse[])`.
  2. **Barre d'actions contextuelle** : Insérer un bloc `div.bulk-actions-bar` (pattern `BulkActionBar.vue`) entre le header et le tableau, visible quand `selectedImages.length > 0`. Contient :
     - `el-tag` affichant `"N sélectionnée(s)"`
     - Bouton `Remove` (type danger, icon Delete) appelant `handleBulkRemove(false)`
     - Bouton `Force Remove` (type danger, icon DeleteFilled) appelant `handleBulkRemove(true)`
     - Bouton `Export` (type primary, icon Download) appelant `handleBulkExport()` (télécharge un tar par image sélectionnée, ou utilise une archive zip côté client)
  3. **Indicateur in_use** : Ajouter colonne "Utilisation" avec template affichant :
     - `el-tag type="success"` + icône + "Utilisée (N)" si `row.inUse`
     - `el-tag type="info"` + "Non utilisée" sinon
  4. **Filtre in_use** : Ajouter `el-select` dans le header avec options `[{label: 'Toutes', value: ''}, {label: 'Utilisées', value: 'used'}, {label: 'Non utilisées', value: 'unused'}]`. Filtrer `filteredImages` en combinant recherche textuelle + filtre in_use.
  5. **Import** : Ajouter bouton "Importer" (icon Upload) ouvrant un `el-upload` acceptant `.tar`. Au changement de fichier, appeler `imagesApi.load(file.raw)` puis `fetchImages()`.
  6. **Navigation détail** : Ajouter `@row-click="handleRowClick"` sur `el-table`. `handleRowClick(row)` fait `router.push({ name: 'ImageDetail', params: { id: row.id } })`.
  7. **Suppression en lot** : `handleBulkRemove(force)` itère sur `selectedImages`, appelle `imagesApi.batchRemove`, affiche `ElMessage.success` ou `ElMessage.error`, puis rafraîchit.
**Exigences sécurité :** Aucune exigence spécifique (lecture seule, pas de données sensibles affichées)
**Dépend de :** Tâche 4

### Tâche 6 : Frontend — Vue ImageDetail.vue et route
**Objectif :** Créer une vue de détail d'image affichant les informations de base et permettant de revenir à la liste.
**Fichiers :**
- `frontend/src/views/ImageDetail.vue` — Créer — Nouvelle vue (pattern : `ContainerDetail.vue` sans onglets). Structure :
  - **Template** : `el-card` avec header "Détail de l'image" + bouton retour. Contenu :
    - Section "Identité" : ID (code), Tags (`el-tag` pour chaque), Digests (liste), Date de création, Taille (`formatBytes`)
    - Section "Configuration" : Architecture, OS, Commande (`cmd`), Entrypoint, Variables d'environnement (table ou liste), Ports exposés (liste)
    - Section "Labels" : `el-descriptions` ou tableau key-value des labels
    - `el-empty` si image non trouvée + message d'erreur
  - **Script** : `ref`, `onMounted`, `useRoute`, `useRouter` depuis `vue`. `image: Ref<ImageDetailResponse | null>`, `loading`, `error`. `fetchImage()` appelle `imagesApi.get(route.params.id as string)`.
- `frontend/src/router/index.ts` — Modifier — Ajouter dans `children` du layout principal :
  ```typescript
  {
    path: 'images/:id',
    name: 'ImageDetail',
    component: () => import('@/views/ImageDetail.vue'),
  }
  ```
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 4

### Tâche 7 : Tests unitaires backend et frontend
**Objectif :** Couvrir les nouveaux endpoints backend et les nouvelles fonctionnalités frontend avec des tests unitaires.
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
- `frontend/tests/unit/views/Images.spec.ts` — Modifier — Ajouter tests :
  - `affiche les checkboxes de sélection` — `el-table-column type="selection"` présente
  - `affiche la barre bulk quand une image est sélectionnée` — sélectionner une ligne → barre visible
  - `appelle batchRemove au clic sur Remove bulk` — bulk remove + refresh
  - `affiche le badge vert pour image utilisée` — `inUse=true` → tag success
  - `filtre les images par utilisation` — filtre "Utilisées" → seules images inUse affichées
  - `navigue vers ImageDetail au clic sur une ligne` — `router.push` appelé
  - `affiche le bouton Importer` — bouton upload présent
- `frontend/tests/unit/views/ImageDetail.spec.ts` — Créer — Tests de la vue détail :
  - `affiche les informations de l'image` — ID, tags, taille formatée
  - `affiche un message d'erreur si l'image n'existe pas` — API 404 → message d'erreur
  - `redirige vers /login si non authentifié` — **sécurité** : route protégée
**Exigences sécurité :** Tests 401, 404, route protégée, données sensibles absentes du DOM
**Dépend de :** Tâches 5, 6

## Tests à écrire

> ⚠️ Les tests sont désormais définis dans les sous-stories individuelles.
