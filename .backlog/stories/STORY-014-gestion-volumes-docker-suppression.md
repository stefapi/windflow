# STORY-014 : Gestion des volumes Docker - Suppression

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux supprimer des volumes Docker inutilisés depuis l'interface afin de libérer de l'espace disque sur mes machines cibles.

## Contexte technique

### Couches impactées
**Frontend uniquement.** Le backend est **100% complet** — aucune modification backend requise.

### État du backend (référence)
- `DELETE /docker/volumes/{volume_name}` → [`remove_volume()`](backend/app/api/v1/docker.py:1576) retourne 204 No Content
  - Paramètre query `force` (booléen, défaut `false`) : force la suppression même si le volume est en cours d'utilisation
  - Erreur 404 : volume introuvable
  - Erreur 500 : erreur Docker (volume en cours d'utilisation sans `force`)
  - Rate limiting : 30 req/60s
- ⚠️ Cet endpoint n'injecte pas `get_current_user` — cohérent avec le pattern des autres endpoints docker locaux du projet (accès via socket Unix)

### Fichiers de référence (patterns à suivre)
| Fichier à modifier | Pattern de référence |
|---------------------|---------------------|
| `frontend/src/services/api.ts` (ajout `volumesApi.remove`) | Pattern `imagesApi.remove` dans le même fichier |
| `frontend/src/views/Volumes.vue` (colonne Actions + dialog suppression) | [`frontend/src/views/Images.vue`](frontend/src/views/Images.vue) — colonne Actions + `handleDelete` |
| `frontend/tests/unit/views/Volumes.spec.ts` (tests suppression) | [`frontend/tests/unit/views/Images.spec.ts`](frontend/tests/unit/views/Images.spec.ts) |

### Exigences sécurité identifiées
- **Authentification** : Pas nécessaire pour les endpoints Docker locaux (cohérent avec le pattern existant — accès socket Unix)
- **Confirmation avant suppression** : Dialog de confirmation obligatoire avant tout appel DELETE (AC 1) — un volume peut contenir des données critiques
- **Flag force** : Checkbox dans le dialog de confirmation permettant de forcer la suppression d'un volume en cours d'utilisation — à utiliser avec précaution
- **Validation des inputs** : `volume_name` est un path param string validé côté backend, `force` est un booléen — pas de sanitisation frontend supplémentaire nécessaire
- **Données sensibles** : Aucune donnée sensible dans les volumes (nom, driver, mountpoint sont non-sensibles)
- **Gestion d'erreur** : Erreur volume en cours d'utilisation → `ElMessage.error` avec message explicite (AC 3)
- **TypeScript strict** : Pas de `any` — cf. `.clinerules/30-code-standards.md`

## Critères d'acceptation (AC)
- [x] AC 1 : Chaque volume dans la liste dispose d'une action "Supprimer" qui demande confirmation
- [x] AC 2 : La suppression appelle `DELETE /docker/volumes/{name}` et la liste se rafraîchit
- [x] AC 3 : Si le volume est en cours d'utilisation, l'erreur retournée par l'API est affichée via notification toast
- [x] AC 4 : `volumesApi.remove` est disponible dans `services/api.ts`
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-013 (Liste volumes — même vue)

---

## Tâches d'implémentation détaillées

### T1 — Ajouter `volumesApi.remove` dans le service API

**Objectif :** Exposer la fonction `volumesApi.remove(name, force?)` dans la couche service frontend, en cohérence avec le pattern `imagesApi.remove`.

**Fichiers :**
- **Modifier** `frontend/src/services/api.ts`
  - Ajouter la méthode `remove` dans l'objet `volumesApi` existant (ligne 374) :
    ```
    remove: (name: string, force?: boolean) =>
      http.delete<void>(`/docker/volumes/${name}`, { params: { force } }),
    ```

**Exigences sécurité :** Pas de gestion de token ici — l'intercepteur HTTP global (`frontend/src/services/http.ts`) s'en charge déjà. Le paramètre `force` est optionnel et transmis tel quel au backend.

**Dépendances :** Aucune (les types `VolumeResponse` existent déjà depuis STORY-013).

---

### T2 — Ajouter le bouton Supprimer, le dialog de confirmation avec flag force et `handleDelete` dans Volumes.vue

**Objectif :** Ajouter une colonne "Actions" dans le tableau des volumes avec un bouton Supprimer. Au clic, ouvrir un dialog de confirmation personnalisé incluant une checkbox "Forcer la suppression" pour les volumes en cours d'utilisation.

**Fichiers :**
- **Modifier** `frontend/src/views/Volumes.vue`
  - **Template — Colonne Actions** : Ajouter après la colonne "Date de création" :
    ```html
    <el-table-column label="Actions" width="120">
      <template #default="{ row }">
        <el-button type="danger" :icon="Delete" size="small" @click="openDeleteConfirm(row)" />
      </template>
    </el-table-column>
    ```
  - **Template — Dialog de confirmation** : Ajouter un `el-dialog` dédié (après le dialog de création) :
    - Titre : "Supprimer le volume"
    - Message : "Voulez-vous vraiment supprimer le volume {nom} ? Cette action est irréversible."
    - Checkbox `el-checkbox` : "Forcer la suppression (le volume peut être en cours d'utilisation)" → lie `forceDelete`
    - Bouton "Annuler" + bouton "Supprimer" (`type="danger"`, `:loading="deleting"`)
  - **Script setup** :
    - Ajouter l'import : `import { Delete } from '@element-plus/icons-vue'`
    - Ajouter l'import : `import { ElMessageBox } from 'element-plus'` (si utilisé pour le pattern confirm/cancel)
    - Ajouter les refs : `deleteDialogVisible`, `volumeToDelete` (ref `VolumeResponse | null`), `forceDelete` (ref `boolean`), `deleting` (ref `boolean`)
    - Ajouter la fonction `openDeleteConfirm(volume: VolumeResponse)` : stocke le volume, reset `forceDelete` à `false`, ouvre le dialog
    - Ajouter la fonction `handleDelete()` :
      - Appelle `volumesApi.remove(volumeToDelete.value!.name, forceDelete.value)`
      - En succès : `ElMessage.success('Volume supprimé avec succès')`, fermeture dialog, refresh liste via `fetchVolumes()`
      - En erreur : distinguer l'erreur volume en cours d'utilisation (message Docker spécifique) → `ElMessage.error` avec message explicite
      - En erreur générique : `ElMessage.error` avec fallback message
    - Ajouter l'import de `ElMessageBox` si utilisé pour le pattern confirm simple (alternative au dialog custom)

**Exigences sécurité :** La confirmation est obligatoire avant tout appel DELETE. Le flag `force` est désactivé par défaut — l'utilisateur doit cocher explicitement. Aucun secret ou token ne doit apparaître dans le DOM.

**Dépendances :** T1 (`volumesApi.remove` doit être disponible).

---

### T3 — Écrire les tests unitaires frontend pour la suppression

**Objectif :** Couvrir les cas nominaux et les cas d'erreur de la suppression de volumes dans `Volumes.vue`, en suivant le pattern de [`frontend/tests/unit/views/Images.spec.ts`](frontend/tests/unit/views/Images.spec.ts).

**Fichiers :**
- **Modifier** `frontend/tests/unit/views/Volumes.spec.ts`
  - Ajouter le mock `mockRemove` dans le mock de `volumesApi` :
    ```ts
    const mockRemove = vi.fn()
    // Dans vi.mock('@/services/api', ...) :
    volumesApi: {
      list: (...args: unknown[]) => mockList(...args),
      create: (...args: unknown[]) => mockCreate(...args),
      remove: (...args: unknown[]) => mockRemove(...args),
    }
    ```
  - **Tests nominaux :**
    - `affiche un bouton Supprimer pour chaque volume` : colonne Actions présente avec un bouton `type="danger"` par ligne
    - `ouvre le dialog de confirmation au clic sur Supprimer` : clic sur bouton delete → dialog visible avec le nom du volume
    - `appelle volumesApi.remove après confirmation` : clic Supprimer → confirmation → `mockRemove` appelé avec le nom du volume
    - `transmet le flag force quand la checkbox est cochée` : coche force → confirmation → `mockRemove` appelé avec `(name, true)`
    - `affiche ElMessage.success après suppression réussie` : `expect(ElMessage.success).toHaveBeenCalled()`
    - `rafraîchit la liste après suppression réussie` : `mockList` appelé 2 fois (initial + refresh)
  - **Tests d'erreur / sécurité :**
    - `n appelle pas volumesApi.remove si confirmation annulée` : clic Annuler → `mockRemove` non appelé
    - `affiche ElMessage.error si la suppression échoue` : `mockRemove.mockRejectedValue(...)` → `ElMessage.error` appelé
    - `test_no_sensitive_data_in_dom` : `expect(wrapper.html()).not.toContain('Bearer')` et `.not.toContain('token')`

**Exigences sécurité :** Vérifier qu'aucun token/champ sensible n'est rendu dans le composant. Vérifier que la suppression ne peut pas être déclenchée sans confirmation.

**Dépendances :** T1, T2.

---

## Tests à écrire

### Tests unitaires frontend (`Vitest`)

**Fichier :** `frontend/tests/unit/views/Volumes.spec.ts` (enrichissement du fichier existant)

#### Cas nominaux — Suppression

| Test | Description |
|------|-------------|
| `affiche un bouton Supprimer pour chaque volume` | Colonne Actions présente, chaque ligne a un bouton danger |
| `ouvre le dialog de confirmation au clic sur Supprimer` | Clic bouton delete → dialog visible avec nom du volume |
| `appelle volumesApi.remove après confirmation` | Confirmation → `mockRemove` appelé avec le nom du volume |
| `transmet le flag force quand la checkbox est cochée` | Checkbox force cochée → `mockRemove` appelé avec `(name, true)` |
| `affiche ElMessage.success après suppression réussie` | `expect(ElMessage.success).toHaveBeenCalled()` |
| `rafraîchit la liste après suppression réussie` | `mockList` appelé 2 fois (initial + refresh) |

#### Cas d'erreur / sécurité — Suppression

| Test | Description |
|------|-------------|
| `n appelle pas volumesApi.remove si confirmation annulée` | Clic Annuler → `mockRemove` non appelé |
| `affiche ElMessage.error si la suppression échoue` | `mockRemove.mockRejectedValue(new Error('volume in use'))` → `ElMessage.error` appelé |
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

- [x] T1 — Méthode `volumesApi.remove` ajoutée dans `frontend/src/services/api.ts`
- [x] T2 — Colonne Actions + dialog confirmation avec flag force + `handleDelete` implémentés dans `frontend/src/views/Volumes.vue`
- [x] T3 — Tests de suppression ajoutés dans `frontend/tests/unit/views/Volumes.spec.ts`
- [x] AC 1 couvert : bouton Supprimer avec confirmation pour chaque volume
- [x] AC 2 couvert : appel DELETE + refresh liste
- [x] AC 3 couvert : gestion erreur volume en cours d'utilisation via toast
- [x] AC 4 couvert : `volumesApi.remove` disponible
- [x] AC 5 couvert : build, lint, tests passent

---

## Notes d'implémentation

**Date :** 2026-04-15

**Fichiers modifiés :**
- `frontend/src/services/api.ts` — Ajout de `volumesApi.remove(name, force?)` suivant le pattern `imagesApi.remove`
- `frontend/src/views/Volumes.vue` — Ajout colonne Actions (bouton danger + icône Delete), dialog de confirmation personnalisé avec checkbox `forceDelete`, fonctions `openDeleteConfirm` et `handleDelete`
- `frontend/tests/unit/views/Volumes.spec.ts` — Ajout de `mockRemove` dans le mock + 8 nouveaux tests couvrant les cas nominaux et les cas d'erreur de suppression

**Décisions techniques :**
- **Dialog custom** (non `ElMessageBox.confirm`) retenu car la story exige une checkbox "force" dans le dialog de confirmation — impossible avec `ElMessageBox.confirm` standard
- **Pattern suivi :** `imagesApi.remove` pour la couche API, `Images.vue` pour la structure dialog+bouton dans la vue
- Pas de `any` TypeScript — typage strict avec `VolumeResponse | null` pour `volumeToDelete`
- Le `test_no_sensitive_data_in_dom` pré-existant dans la spec couvre déjà cet AC — non dupliqué (8 nouveaux tests ajoutés au lieu de 9)

**Résultats validation :**
- Tests : 20/20 ✅
- Build : exit code 0 ✅
- Lint : 0 erreur, 127 warnings tous pré-existants (aucun dans les fichiers modifiés) ✅
