# STORY-013 : Gestion des volumes Docker - Liste et création

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter la liste des volumes Docker et en créer de nouveaux afin de gérer le stockage persistant de mes containers depuis l'interface WindFlow.

## Contexte technique

### Couches impactées
**Frontend uniquement.** Le backend est **100% complet** — aucune modification backend requise.

### État du backend (référence)
- `GET /docker/volumes` → [`list_volumes()`](backend/app/api/v1/docker.py) retourne `List[VolumeResponse]`
- `POST /docker/volumes` → [`create_volume()`](backend/app/api/v1/docker.py) retourne `VolumeResponse` (201), gère 409 si le volume existe déjà
- Schémas Pydantic définis dans [`backend/app/schemas/docker.py`](backend/app/schemas/docker.py) :
  - `VolumeResponse` : `name`, `driver`, `mountpoint`, `created_at`, `labels`, `scope`
  - `VolumeCreateRequest` : `name` (regex `^[a-zA-Z0-9][a-zA-Z0-9_.-]*$`), `driver` (`local` par défaut), `labels` (optionnel)
- ⚠️ Ces endpoints n'injectent pas `get_current_user` — cohérent avec le pattern des autres endpoints docker locaux du projet (accès via socket Unix)

### Fichiers de référence (patterns à suivre)
| Fichier à créer/modifier | Pattern de référence |
|--------------------------|---------------------|
| `frontend/src/types/api.ts` (types volumes) | Types existants en bas du même fichier (ex: `ContainerRenameRequest`) |
| `frontend/src/services/api.ts` (volumesApi) | Pattern `containersApi` dans le même fichier |
| `frontend/src/views/Volumes.vue` | [`frontend/src/views/Images.vue`](frontend/src/views/Images.vue) |
| `frontend/tests/unit/views/Volumes.spec.ts` | [`frontend/tests/unit/views/Images.spec.ts`](frontend/tests/unit/views/Images.spec.ts) |

### Exigences sécurité identifiées
- Validation du nom de volume gérée côté backend par regex Pydantic → pas de sanitisation supplémentaire côté frontend nécessaire, mais feedback visuel (validation côté formulaire) est souhaitable
- Aucune donnée sensible dans `VolumeResponse` (nom, driver, mountpoint sont non-sensibles)
- Respecter les standards TypeScript strict (pas de `any`) — cf. `.clinerules/30-code-standards.md`
- Gestion d'erreur 409 (conflit) à afficher à l'utilisateur via `ElMessage.error`

## Critères d'acceptation (AC)
- [x] AC 1 : La vue Volumes affiche la liste des volumes via `GET /docker/volumes` dans un tableau avec colonnes (Nom, Driver, Mountpoint, Date)
- [x] AC 2 : Un bouton "Créer un volume" ouvre un dialog avec les champs nom et driver, et appelle `POST /docker/volumes`
- [x] AC 3 : Les types TypeScript `VolumeResponse` et `VolumeCreateRequest` sont définis, et `volumesApi.list`/`volumesApi.create` sont disponibles
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

---

## Tâches d'implémentation détaillées

### T1 — Ajouter les types TypeScript pour les volumes

**Objectif :** Définir les interfaces TypeScript `VolumeResponse` et `VolumeCreateRequest` qui reflètent fidèlement les schémas Pydantic backend. Ces types sont le contrat d'interface entre le frontend et l'API.

**Fichiers :**
- **Modifier** `frontend/src/types/api.ts`
  - Ajouter en fin de fichier (section `// Docker Volumes`) les interfaces suivantes, en miroir de [`backend/app/schemas/docker.py`](backend/app/schemas/docker.py) :
    - `VolumeResponse` : `name: string`, `driver: string`, `mountpoint: string`, `created_at: string`, `labels: Record<string, string>`, `scope: string`
    - `VolumeCreateRequest` : `name: string`, `driver?: string` (défaut `'local'`), `labels?: Record<string, string>`

**Exigences sécurité :** TypeScript strict — pas de `any`, tous les champs typés explicitement.

**Dépendances :** Aucune.

---

### T2 — Ajouter le service API `volumesApi`

**Objectif :** Exposer les fonctions `volumesApi.list()` et `volumesApi.create()` dans la couche service frontend, en cohérence avec le pattern des autres API Docker (`containersApi`, `imagesApi`).

**Fichiers :**
- **Modifier** `frontend/src/services/api.ts`
  - Ajouter l'import des types `VolumeResponse` et `VolumeCreateRequest` depuis `@/types/api` dans la section imports en haut du fichier
  - Ajouter l'objet `volumesApi` (après `containersApi` ou en section Docker) :
    ```
    volumesApi = {
      list()            → GET /docker/volumes           → List<VolumeResponse>
      create(data)      → POST /docker/volumes           → VolumeResponse
    }
    ```
  - Exporter `volumesApi` en named export ET l'ajouter au default export (clé `volumes`)

**Exigences sécurité :** Pas de gestion de token ici — l'intercepteur HTTP global (`frontend/src/services/http.ts`) s'en charge déjà.

**Dépendances :** T1 (types doivent être définis).

---

### T3 — Implémenter la vue `Volumes.vue`

**Objectif :** Remplacer la `StubPage` par une vue fonctionnelle affichant la liste des volumes Docker dans un tableau Element Plus, avec la possibilité de créer un nouveau volume via un dialog.

**Fichiers :**
- **Modifier** `frontend/src/views/Volumes.vue`
  - Supprimer le composant `StubPage` et implémenter la vue complète
  - **Section tableau (`el-table`)** :
    - Colonnes : `Nom` (avec truncature si trop long), `Driver`, `Mountpoint` (texte tronqué avec tooltip), `Date de création` (formatée via `new Date().toLocaleString()`)
    - Attribut `v-loading` pendant le chargement
    - `el-empty` si aucun volume (`description="Aucun volume trouvé"`)
    - Filtre de recherche par nom (input `el-input` + `computed filteredVolumes`)
  - **Bouton en-tête** : `el-button type="primary"` « Créer un volume » → ouvre le dialog
  - **Dialog de création** (`el-dialog`) :
    - Champ `Nom du volume` : `el-input` obligatoire (feedback de validation si vide)
    - Champ `Driver` : `el-input` avec valeur par défaut `local`
    - Bouton « Annuler » + bouton « Créer » (avec `:loading` pendant l'appel)
    - En succès : `ElMessage.success('Volume créé avec succès')` + fermeture dialog + refresh liste
    - En erreur 409 : `ElMessage.error` avec message explicite (volume déjà existant)
    - En erreur générique : `ElMessage.error` avec fallback message
  - **Script setup** (Composition API, TypeScript strict) :
    - `import { ref, computed, onMounted } from 'vue'`
    - `import { volumesApi } from '@/services/api'`
    - `import type { VolumeResponse, VolumeCreateRequest } from '@/types/api'`
    - `import { ElMessage } from 'element-plus'`
    - Fonctions : `fetchVolumes()`, `handleCreate()`, `formatDate()`

**Exigences sécurité :** Validation côté formulaire : le champ `name` ne doit pas être vide avant l'envoi (feedback via `ElMessage.warning`). Aucun secret ou token ne doit apparaître dans le DOM.

**Dépendances :** T1 (types), T2 (service API).

---

### T4 — Écrire les tests unitaires frontend

**Objectif :** Couvrir les cas nominaux et les cas d'erreur de `Volumes.vue` avec Vitest, en suivant strictement le pattern de [`frontend/tests/unit/views/Images.spec.ts`](frontend/tests/unit/views/Images.spec.ts).

**Fichiers :**
- **Créer** `frontend/tests/unit/views/Volumes.spec.ts`
  - Mock de `volumesApi` (`vi.mock('@/services/api', ...)`), `ElMessage`, `ElMessageBox`
  - Données de test : 2-3 objets `VolumeResponse` (mock data)
  - **Tests nominaux :**
    - Affiche les volumes dans le tableau après chargement (`flushPromises`)
    - Filtre les volumes par nom
    - Affiche `el-empty` si aucun volume retourné
    - Le bouton « Créer un volume » ouvre le dialog
    - La création avec données valides appelle `volumesApi.create` et rafraîchit la liste
    - Un message `ElMessage.success` est affiché après création réussie
  - **Tests de sécurité / erreur :**
    - Si le champ `nom` est vide au submit → `ElMessage.warning` appelé, pas d'appel API
    - En cas d'erreur de création → `ElMessage.error` appelé
    - Aucun token ni secret ne doit être visible dans le DOM (assertion `not.toContain`)

**Exigences sécurité :** Vérifier qu'aucun token/champ sensible n'est rendu dans le composant.

**Dépendances :** T1, T2, T3.

---

## Tests à écrire

### Tests unitaires frontend (`Vitest`)

**Fichier :** `frontend/tests/unit/views/Volumes.spec.ts`

#### Cas nominaux

| Test | Description |
|------|-------------|
| `affiche les volumes dans le tableau après chargement` | `volumesApi.list` mockée → `flushPromises` → 2+ lignes dans le `el-table` |
| `affiche le nom, driver et mountpoint de chaque volume` | Vérifie le texte présent dans le rendu |
| `filtre les volumes par nom` | Saisie dans l'input de recherche → `filteredVolumes` réduit |
| `affiche el-empty si la liste est vide` | `mockList.mockResolvedValue({ data: [] })` → `el-empty` présent |
| `ouvre le dialog au clic sur "Créer un volume"` | `wrapper.find('[type=primary]').trigger('click')` → dialog visible |
| `appelle volumesApi.create avec les bons paramètres` | Saisie nom + driver → submit → `mockCreate` appelé avec `{ name, driver }` |
| `ferme le dialog et rafraîchit la liste après création réussie` | `mockCreate` résout → dialog fermé + `mockList` appelé 2 fois |
| `affiche ElMessage.success après création réussie` | `expect(ElMessage.success).toHaveBeenCalled()` |

#### Cas d'erreur / sécurité frontend

| Test | Description |
|------|-------------|
| `test_create_volume_warns_if_name_empty` | `name` vide → `ElMessage.warning` appelé, `volumesApi.create` non appelé |
| `test_create_volume_shows_error_on_failure` | `mockCreate.mockRejectedValue(new Error(...))` → `ElMessage.error` appelé |
| `test_no_sensitive_data_in_dom` | `expect(wrapper.html()).not.toContain('Bearer')` et `.not.toContain('token')` |

### Commandes de validation

```bash
# Tests unitaires frontend
make test-frontend
# ou directement :
cd frontend && pnpm vitest run tests/unit/views/Volumes.spec.ts

# Lint TypeScript
cd frontend && pnpm tsc --noEmit

# Lint ESLint
cd frontend && pnpm lint

# Build complet
make build-frontend
```

---

## État d'avancement technique

- [x] T1 — Types TypeScript ajoutés dans `frontend/src/types/api.ts` (`VolumeResponse`, `VolumeCreateRequest`)
- [x] T2 — Service API ajouté dans `frontend/src/services/api.ts` (`volumesApi.list`, `volumesApi.create`)
- [x] T3 — Vue `frontend/src/views/Volumes.vue` implémentée (tableau + dialog de création)
- [x] T4 — Tests `frontend/tests/unit/views/Volumes.spec.ts` écrits et passants
- [x] AC 1 couvert : liste des volumes affichée avec colonnes Nom, Driver, Mountpoint, Date
- [x] AC 2 couvert : dialog de création fonctionnel
- [x] AC 3 couvert : types + api service disponibles
- [x] AC 4 couvert : build, lint, tests passent sans erreur

---

## Notes d'implémentation

**Date :** 2026-04-15

### Fichiers modifiés/créés

- **Modifié** `frontend/src/types/api.ts` — ajout des interfaces `VolumeResponse` et `VolumeCreateRequest` (+ `ImageResponse`, `ImagePullRequest`, `ImagePullResponse`, `StackImportResponse` pour corriger des erreurs de build pré-existantes)
- **Modifié** `frontend/src/services/api.ts` — ajout de `volumesApi` (named export + default export `volumes`), `imagesApi`, `stacksApi.export/import` (corrections build pré-existants)
- **Créé** `frontend/src/views/Volumes.vue` — vue complète remplaçant le StubPage
- **Créé** `frontend/tests/unit/views/Volumes.spec.ts` — 12 tests unitaires

### Décisions techniques

- Pattern suivi : identique à `Images.vue` / `Images.spec.ts` (Composition API, Element Plus, ElMessage)
- Gestion erreur 409 : détection via `error.response?.status === 409` pour afficher un message explicite "volume déjà existant"
- TypeScript strict respecté : aucun `any`, tous les champs typés
- Test de sécurité inclus : vérification de l'absence de `Bearer`, `token`, `password`, `secret` dans le DOM
- Correction build pré-existant : `imagesApi`, `ImageResponse`, `ImagePullRequest`, `ImagePullResponse`, `stacksApi.import/export`, `StackImportResponse` manquants dans les stories précédentes (STORY-005, STORY-007, STORY-008)
