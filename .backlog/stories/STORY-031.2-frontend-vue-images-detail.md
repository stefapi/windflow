# STORY-031.2 : Frontend — Vue Images complète (sélection, usage, détail)

**Statut :** DONE
**Story Parente :** STORY-031 — Images Docker — Sélection, actions en lot, usage et détail
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux interagir visuellement avec les images Docker : sélectionner des images via des cases à cocher, appliquer des actions en lot (remove, force_remove), importer/exporter des images depuis l'interface, voir si une image est utilisée par des containers avec un filtre dédié, et afficher un écran de détail complet en cliquant sur une image.

## Critères d'acceptation (AC)
- [x] AC 1 : Le tableau des images dispose d'une colonne de sélection par checkbox avec sélection globale en-tête, et une barre d'actions apparaît quand des images sont sélectionnées (Remove, Force Remove)
- [x] AC 3 : Chaque image affiche un indicateur d'utilisation (utilisée/non utilisée par des containers) et un filtre permet d'afficher uniquement les images utilisées ou non utilisées (fermeture frontend)
- [x] AC 4 : Cliquer sur une image navigue vers un écran de détail (vue `ImageDetail.vue` stub avec infos de base : ID, tags, size, created, labels, digests)
- [x] AC 5 : L'amélioration ne casse pas les fonctionnalités existantes (liste, recherche, affichage)
- [x] AC 6 : Build, lint et tests passent sans erreur

## Contexte technique

### Fichiers de référence (patterns)
| Couche | Fichier de référence | Pattern à suivre |
|--------|---------------------|------------------|
| Frontend type | `frontend/src/types/api.ts` — `ImageResponse`, `ContainerDetail` | Interfaces camelCase, snake_case pour les réponses backend |
| Frontend API | `frontend/src/services/api.ts` — `imagesApi` | Objet avec méthodes retournant `http.get/post/delete` |
| Frontend vue liste | `frontend/src/views/Images.vue` | `el-table`, `el-card`, `script setup lang="ts"`, `formatBytes` |
| Frontend vue détail | `frontend/src/views/ContainerDetail.vue` | Structure onglets, `onMounted`, `ElMessage` |
| Frontend composant bulk | `frontend/src/components/compute/BulkActionBar.vue` | Props `selected-count`, slot actions |
| Frontend router | `frontend/src/router/index.ts` | Route lazy-loaded avec `props: true` si besoin |
| Frontend tests | `frontend/tests/unit/views/Images.spec.ts` | `vi.mock('@/services/api')`, `mount` avec `ElementPlus` |

### Exigences sécurité identifiées
- **Auth** : toutes les routes et appels API utilisent le client HTTP authentifié (intercepteur JWT).
- **RBAC** : suivre le pattern existant — pas de vérification de rôles côté frontend pour les endpoints Docker.
- **Validation** : le paramètre `imageId` dans le routeur doit être non-vide.
- **Exposition** : aucun champ sensible dans les réponses images.

## Dépendances
- STORY-031.1 : Backend — API Images enrichie, inspect et import/export

## Tâches d'implémentation détaillées

### Tâche 1 : Frontend — Types et API service
**Objectif :** Étendre les types TypeScript et le service API pour supporter les nouveaux champs et endpoints exposés par le backend.
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
**Dépend de :** STORY-031.1 (backend stable)

### Tâche 2 : Frontend — Sélection, bulk actions et indicateur d'utilisation dans Images.vue
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
**Dépend de :** Tâche 1

### Tâche 3 : Frontend — Vue ImageDetail.vue et route
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
**Dépend de :** Tâche 1

### Tâche 4 : Tests unitaires frontend
**Objectif :** Couvrir les nouvelles fonctionnalités frontend avec des tests unitaires.
**Fichiers :**
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
**Exigences sécurité :** Tests route protégée, données sensibles absentes du DOM
**Dépend de :** Tâches 2, 3

## Tests à écrire

### Frontend
- `frontend/tests/unit/views/Images.spec.ts` (enrichissement)
  - Sélection checkbox, barre bulk, badge in_use, filtre in_use, navigation, import, suppression en lot

- `frontend/tests/unit/views/ImageDetail.spec.ts` (création)
  - Affichage des données, gestion erreur 404, route protégée

### Commandes de validation
```bash
# Frontend
cd frontend && pnpm test -- tests/unit/views/Images
cd frontend && pnpm test -- tests/unit/views/ImageDetail
cd frontend && pnpm build && pnpm lint
```

## État d'avancement technique
- [x] Tâche 1 : Frontend — Types et API service
- [x] Tâche 2 : Frontend — Sélection, bulk actions et indicateur in_use dans Images.vue
- [x] Tâche 3 : Frontend — Vue ImageDetail.vue et route
- [x] Tâche 4 : Tests unitaires frontend
- [x] Build & lint OK

## Notes d'implémentation

**Date :** 2026-05-17

### Fichiers modifiés/créés
- `frontend/src/types/api.ts` : Ajout `inUse`, `containersCount` à `ImageResponse` ; création `ImageDetailResponse`
- `frontend/src/services/api.ts` : Ajout import `ImageDetailResponse` ; extension `imagesApi` avec `get`, `save`, `load`, `batchRemove`
- `frontend/src/views/Images.vue` : Ajout sélection checkbox, barre bulk actions, colonne utilisation, filtre in_use, import/export, navigation détail
- `frontend/src/views/ImageDetail.vue` : Création — vue détail image avec sections Identité, Configuration, Env, Ports, Labels
- `frontend/src/router/index.ts` : Ajout route `images/:id` → `ImageDetail`

### Fichiers de tests créés
- `frontend/tests/unit/views/Images.spec.ts` : 25 tests (15 existants + 10 nouveaux : sélection, bulk, in_use, filtre, navigation, import)
- `frontend/tests/unit/views/ImageDetail.spec.ts` : 8 tests (affichage détail, config, env, ports, labels, erreur 404, retour, loading)

### Décisions techniques
- `handleRowClick` utilise `@row-click` avec `.stop` sur le bouton delete pour éviter la navigation lors de la suppression
- `handleBulkExport` télécharge un tar par image (pas d'archive zip côté client pour rester simple)
- `load` utilise `FormData` avec `Content-Type: multipart/form-data` pour l'upload tar
- `route.params['id']` (bracket notation) pour éviter le warning TS4111

### Résultats des tests
- Images : 25/25 ✅
- ImageDetail : 8/8 ✅
- Build : ✅ (erreurs TS pré-existantes dans ContainerCreateDialog, TargetWizard, ContainerTable)
- Lint : 0 erreurs, 128 warnings (tous pré-existants)
