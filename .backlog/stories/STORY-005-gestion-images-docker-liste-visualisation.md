# STORY-005 : Gestion des images Docker - Liste et visualisation

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter la liste des images Docker disponibles sur mes targets afin de visualiser les images présentes, leur taille et leurs tags.

## Contexte technique
- Vue existante `views/Images.vue` (actuellement StubPage — à implémenter)
- API : `GET /docker/images`
- Type TypeScript à ajouter : `ImageResponse` dans `types/api.ts`
- Table avec colonnes : ID, Repo Tags, Size, Created, Actions
- Pagination pour les listes longues

## Critères d'acceptation (AC)
- [x] AC 1 : La vue Images affiche la liste des images via `GET /docker/images` dans un tableau avec colonnes (ID, Tags, Taille, Date de création)
- [x] AC 2 : La taille des images est affichée dans un format lisible (MB/GB)
- [x] AC 3 : Un champ de recherche permet de filtrer les images par tag ou ID
- [x] AC 4 : Le type TypeScript `ImageResponse` est défini dans `types/api.ts` et l'API `imagesApi.list` est disponible dans `services/api.ts`
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
- [x] Tâche 1 : Ajouter le type ImageResponse dans types/api.ts
- [x] Tâche 2 : Ajouter imagesApi dans services/api.ts
- [x] Tâche 3 : Réécrire Images.vue avec tableau et recherche
- [x] Tests frontend
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter le type ImageResponse dans types/api.ts
**Objectif :** Définir l'interface TypeScript `ImageResponse` qui reflète le schéma backend `ImageResponse` de `backend/app/schemas/docker.py`
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter l'interface `ImageResponse` dans la section Docker (après les types existants). Signature :
  ```typescript
  export interface ImageResponse {
    id: string
    repo_tags: string[]
    repo_digests: string[]
    created: string
    size: number
    virtual_size: number
    labels: Record<string, string>
  }
  ```
  Suivre le pattern des interfaces existantes dans le fichier (ex: `Container`, `ContainerDetail`). Les noms de propriétés sont en snake_case car le backend utilise `populate_by_name=True` et le frontend communique en JSON snake_case.
**Dépend de :** Aucune

### Tâche 2 : Ajouter imagesApi dans services/api.ts
**Objectif :** Créer l'objet API `imagesApi` avec la méthode `list()` qui appelle `GET /docker/images`, et l'ajouter à l'export default
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier —
  1. Ajouter `ImageResponse` aux imports depuis `@/types/api` (ligne ~7-50)
  2. Ajouter le bloc `imagesApi` après `containersApi` (après ligne ~327), suivant le pattern de `containersApi` :
     ```typescript
     // Docker Images API
     export const imagesApi = {
       list: (all: boolean = false) =>
         http.get<ImageResponse[]>('/docker/images', { params: { all } }),
     }
     ```
  3. Ajouter `images: imagesApi,` dans l'export default (après `containers: containersApi,` vers la ligne 387)
**Dépend de :** Tâche 1

### Tâche 3 : Réécrire Images.vue avec tableau et recherche
**Objectif :** Remplacer le contenu StubPage de `Images.vue` par une vue fonctionnelle avec un tableau el-table affichant les images Docker, un champ de recherche, et le formatage des tailles
**Fichiers :**
- `frontend/src/views/Images.vue` — Réécrire entièrement — Remplacer le contenu StubPage par une vue complète (pattern: `Deployments.vue`). Structure :
  - **Template :**
    - `el-card` avec header contenant titre "Images" et champ `el-input` de recherche (placeholder "Rechercher par tag ou ID...")
    - `el-table` avec `v-loading="loading"` et `:data="filteredImages"` et `stripe`
    - Colonnes :
      - `ID` : `prop="id"`, affichage tronqué du SHA256 (les 12 premiers chars avec `...`)
      - `Tags` : template custom itérant sur `repo_tags` avec `el-tag` pour chaque tag, ou `<none>` en gris si tableau vide
      - `Taille` : template custom utilisant `formatBytes(row.size)` depuis `@/utils/format`
      - `Date de création` : template custom formatant `row.created` en date locale
    - `el-empty` si pas d'images et pas de loading
  - **Script setup :**
    - Imports : `ref, computed, onMounted` depuis `vue`, `imagesApi` depuis `@/services/api`, `ImageResponse` depuis `@/types/api`, `formatBytes` depuis `@/utils/format`, `ElMessage` depuis `element-plus`
    - `images: Ref<ImageResponse[]>` — données des images
    - `loading: Ref<boolean>` — état de chargement
    - `searchQuery: Ref<string>` — texte de recherche
    - `filteredImages: ComputedRef<ImageResponse[]>` — filtre par tag ou ID (insensible à la casse)
    - `fetchImages()` — appelle `imagesApi.list()`, gère erreur avec `ElMessage.error`
    - `onMounted` → `fetchImages()`
  - **Styles :** Scoped minimal, cohérent avec les autres vues
**Dépend de :** Tâche 2

## Tests à écrire

### Frontend
- `frontend/tests/unit/views/Images.spec.ts` — Tests de la vue Images :
  - Test que le tableau affiche les images mockées (ID, Tags, Taille, Date)
  - Test que `formatBytes` est utilisé pour afficher la taille en format lisible
  - Test que le champ de recherche filtre les images par tag
  - Test que le champ de recherche filtre les images par ID
  - Test l'état loading (spinner affiché)
  - Test l'état vide (el-empty affiché quand aucune image)
  - Test la gestion d'erreur API (ElMessage.error appelé)
  - Pattern de test : `ContainerDetail.spec.ts` — utiliser `vi.mock` pour mocker `@/services/api`, monter avec `createPinia()`, `ElementPlus`, et router mocké

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
- `frontend/src/types/api.ts` : Ajout de l'interface `ImageResponse` (7 propriétés, snake_case)
- `frontend/src/services/api.ts` : Ajout import `ImageResponse`, bloc `imagesApi` avec méthode `list()`, ajout dans export default
- `frontend/src/views/Images.vue` : Réécriture complète — remplacement du stub par une vue fonctionnelle avec el-table, recherche, formatBytes
- `frontend/tests/unit/views/Images.spec.ts` : Création — 7 tests unitaires couvrant affichage, formatage, filtrage, loading, état vide et erreur API

### Décisions techniques
- Utilisation d'une variable `noneLabel` dans le script pour afficher `<none>` dans le template, car le parser Vue interprète `<none>` comme un élément HTML
- Utilisation de `formatDate()` locale au composant plutôt qu'un utilitaire externe pour le formatage des dates
- Le test de loading vérifie l'état interne `vm.loading` plutôt que le DOM (v-loading ne rend pas le masque dans JSDOM)

### Divergences par rapport à l'analyse
- Aucune divergence significative

### Tests ajoutés
- `frontend/tests/unit/views/Images.spec.ts` : 7 tests passants (affichage images, formatBytes, filtrage par tag, filtrage par ID, état loading, état vide, gestion erreur)
