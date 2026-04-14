# STORY-006 : Gestion des images Docker - Pull et suppression

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux pouvoir télécharger (pull) de nouvelles images Docker et supprimer des images existantes depuis l'interface afin de gérer le registre local d'images sur mes targets.

## Contexte technique
- Vue existante `views/Images.vue`
- APIs : `POST /docker/images/pull`, `DELETE /docker/images/{id}`
- Types TypeScript : `ImagePullRequest`, `ImagePullResponse`
- Dialog pull avec champ de saisie `nom:tag`
- Dialogue de confirmation avant suppression

## Critères d'acceptation (AC)
- [x] AC 1 : Un bouton "Pull image" ouvre un dialog avec un champ de saisie pour le nom de l'image (format `nom:tag`) et déclenche `POST /docker/images/pull`
- [x] AC 2 : La progression du pull est indiquée (loading state) et la liste se rafraîchit après succès
- [x] AC 3 : Chaque ligne de la table dispose d'une action "Supprimer" qui demande confirmation avant d'appeler `DELETE /docker/images/{id}`
- [x] AC 4 : Les erreurs (image introuvable, image en cours d'utilisation) sont affichées via une notification toast
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-005 (Liste des images — même vue, mêmes APIs)

## État d'avancement technique
- [x] Tâche 1 : Ajouter types ImagePullRequest et ImagePullResponse dans types/api.ts
- [x] Tâche 2 : Ajouter méthodes pull() et remove() à imagesApi dans services/api.ts
- [x] Tâche 3 : Ajouter bouton Pull + dialog + colonne Actions avec suppression dans Images.vue
- [x] Tests frontend
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter types ImagePullRequest et ImagePullResponse dans types/api.ts
**Objectif :** Définir les interfaces TypeScript `ImagePullRequest` et `ImagePullResponse` qui reflètent les schémas backend `ImagePullRequest` et `ImagePullResponse` de `backend/app/schemas/docker.py`
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter les interfaces après `ImageResponse` (après ligne 966). Signatures :
  ```typescript
  export interface ImagePullRequest {
    name: string
    tag?: string
  }

  export interface ImagePullResponse {
    status: string
    progress?: string
    id?: string
  }
  ```
  Suivre le pattern des interfaces existantes dans le fichier (camelCase pour les propriétés). Le backend utilise `populate_by_name=True` donc le JSON peut être en camelCase ou snake_case. Le tag est optionnel côté backend avec valeur par défaut `"latest"`.
**Dépend de :** Aucune

### Tâche 2 : Ajouter méthodes pull() et remove() à imagesApi dans services/api.ts
**Objectif :** Compléter l'objet `imagesApi` avec les méthodes `pull()` et `remove()` qui appellent les endpoints backend existants
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier —
  1. Ajouter `ImagePullRequest, ImagePullResponse` aux imports depuis `@/types/api` (ligne ~7-50)
  2. Compléter le bloc `imagesApi` (ligne 331-333) en ajoutant les méthodes après `list` :
     ```typescript
     export const imagesApi = {
       list: (all: boolean = false) =>
         http.get<ImageResponse[]>('/docker/images', { params: { all } }),

       pull: (data: ImagePullRequest) =>
         http.post<ImagePullResponse>('/docker/images/pull', data),

       remove: (imageId: string, force: boolean = false) =>
         http.delete<void>(`/docker/images/${imageId}`, { params: { force } }),
     }
     ```
  Suivre le pattern de `containersApi.remove()` (ligne 308) pour le delete avec params. Le endpoint backend `DELETE /docker/images/{image_id}` accepte un paramètre query `force` (défaut `false`).
**Dépend de :** Tâche 1

### Tâche 3 : Ajouter bouton Pull + dialog + colonne Actions avec suppression dans Images.vue
**Objectif :** Enrichir la vue Images.vue avec les fonctionnalités de pull et suppression d'images. Ajouter un bouton "Pull image" dans le header qui ouvre un dialog, et une colonne Actions avec bouton supprimer par ligne.
**Fichiers :**
- `frontend/src/views/Images.vue` — Modifier — Ajouter les fonctionnalités suivantes au composant existant (pattern: `ContainerDetail.vue` pour confirmation, `Stacks.vue` pour dialog). Modifications :
  1. **Imports à ajouter :** `ElMessageBox` depuis `element-plus`, `Download, Delete` depuis `@element-plus/icons-vue`, `ImagePullRequest` depuis `@/types/api`
  2. **Template — Header :** Ajouter un `el-button` "Pull image" avec icône `Download` dans le `card-header` (à côté du champ de recherche), de type `primary`
  3. **Template — Colonne Actions :** Ajouter un `el-table-column` label="Actions" width="120" avec un `el-button` icône `Delete` de type `danger` par ligne, qui appelle `handleDelete(row)`
  4. **Template — Dialog Pull :** Ajouter un `el-dialog` "Pull une image" avec `v-model="pullDialogVisible"`, contenant un `el-form` :
     - Champ `el-input` "Nom de l'image" avec placeholder "ex: nginx" (requis)
     - Champ `el-input` "Tag" avec placeholder "latest" (optionnel, défaut latest)
     - Bouton "Pull" avec `:loading="pulling"` et `@click="handlePull"`
  5. **Script — Nouvelles refs :**
     - `pullDialogVisible: Ref<boolean>` — visibilité du dialog
     - `pullForm: Ref<{ name: string; tag: string }>` — formulaire pull (initialisé avec `{ name: '', tag: 'latest' }`)
     - `pulling: Ref<boolean>` — état loading du pull
  6. **Script — Nouvelle fonction `handlePull()` :**
     - Valider que `pullForm.value.name` n'est pas vide (si vide, `ElMessage.warning`)
     - Set `pulling.value = true`
     - Appeler `imagesApi.pull({ name: pullForm.value.name, tag: pullForm.value.tag || 'latest' })`
     - En cas de succès : `ElMessage.success` avec le status, fermer le dialog, appeler `fetchImages()` pour rafraîchir la liste
     - En cas d'erreur : `ElMessage.error` avec le message d'erreur
     - Finally : `pulling.value = false`
  7. **Script — Nouvelle fonction `handleDelete(image: ImageResponse)` :**
     - `ElMessageBox.confirm()` avec message "Supprimer l'image `[premier tag ou ID tronqué]` ? Cette action est irréversible." et type `warning`
     - Si confirmé : appeler `imagesApi.remove(image.id)`
     - En cas de succès : `ElMessage.success`, appeler `fetchImages()` pour rafraîchir
     - En cas d'erreur : `ElMessage.error` avec le message (ex: "image en cours d'utilisation")
     - Catch `cancel` pour ignorer (l'utilisateur a annulé)
**Dépend de :** Tâche 2

## Tests à écrire

### Frontend
- `frontend/tests/unit/views/Images.spec.ts` — Modifier les tests existants pour couvrir les nouvelles fonctionnalités :
  - Test que le bouton "Pull image" est présent dans le header
  - Test que le dialog de pull s'ouvre au clic sur le bouton
  - Test que le pull appelle `imagesApi.pull()` avec les bons paramètres et rafraîchit la liste
  - Test que le pull affiche une erreur si le nom est vide
  - Test que le pull affiche une erreur si l'API échoue
  - Test que chaque ligne a un bouton de suppression
  - Test que la suppression demande confirmation via `ElMessageBox.confirm`
  - Test que la suppression appelle `imagesApi.remove()` après confirmation et rafraîchit la liste
  - Test que la suppression affiche une erreur si l'API échoue (ex: image utilisée)
  - Test que l'annulation de la confirmation ne supprime pas l'image
  - **Pattern de test :** Étendre le mock existant `imagesApi` pour inclure `pull` et `remove`, mocker `ElMessageBox.confirm` avec `vi.mock('element-plus')`

### Commandes de validation
```bash
# Frontend tests
cd frontend && pnpm test -- tests/unit/views/Images
# Build & lint
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-04-13

### Fichiers modifiés/créés
- `frontend/src/types/api.ts` : Ajout des interfaces ImagePullRequest et ImagePullResponse
- `frontend/src/services/api.ts` : Ajout des méthodes pull() et remove() à imagesApi + imports
- `frontend/src/views/Images.vue` : Ajout bouton Pull image, dialog de pull, colonne Actions avec suppression
- `frontend/tests/unit/views/Images.spec.ts` : Ajout de 9 tests couvrant pull et suppression

### Décisions techniques
- Utilisation de ElMessageBox.confirm pour la confirmation de suppression (pattern existant dans le projet)
- Le formulaire de pull utilise deux champs séparés (nom + tag) plutôt qu'un seul champ "nom:tag" pour une meilleure UX
- Le tag par défaut "latest" est géré côté frontend ET backend (double sécurité)

### Tests ajoutés
- `frontend/tests/unit/views/Images.spec.ts` : 9 nouveaux tests (pull dialog, pull API, pull erreur, suppression confirmation, suppression erreur, annulation)
