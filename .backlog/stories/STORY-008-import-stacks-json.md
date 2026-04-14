# STORY-008 : Import de stacks depuis fichier JSON

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux importer une stack depuis un fichier JSON afin de restaurer une configuration sauvegardée ou déployer une stack partagée par un collègue.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `POST /stacks/import` (multipart/form-data)
- Upload fichier + validation format avant envoi
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [x] AC 1 : Un bouton "Importer" ouvre un dialog permettant de sélectionner un fichier JSON
- [x] AC 2 : Le fichier est validé côté client (format JSON valide, structure attendue) avant envoi
- [x] AC 3 : L'import appelle `POST /stacks/import` et redirige vers la stack créée en cas de succès
- [x] AC 4 : Les erreurs de validation (format invalide, stack existante) sont affichées clairement
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-007 (Export — format JSON de référence)

## État d'avancement technique
- [x] Tâche 1 : Type `StackImportResponse` dans `types/api.ts`
- [x] Tâche 2 : Méthode `stacksApi.import()` dans `services/api.ts`
- [x] Tâche 3 : Bouton Import + dialog + validation client + logique dans `Stacks.vue`
- [x] Tâche 4 : Tests unitaires de l'import dans `Stacks.spec.ts`
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter le type TypeScript `StackImportResponse`
**Objectif :** Définir le type TypeScript correspondant à la réponse JSON du backend pour l'import de stack.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter après `StackExportData` (après ligne 280) :
  ```typescript
  // Stack import response (mirrors backend import_export.py POST /stacks/import response)
  export interface StackImportResponse {
    message: string
    stack_id: string
    name: string
  }
  ```
**Dépend de :** Aucune
**Fichier de référence :** Type [`StackExportData`](frontend/src/types/api.ts:264) dans le même fichier + format de réponse backend dans [`import_export.py`](backend/app/api/v1/import_export.py:114) lignes 114-118

---

### Tâche 2 : Ajouter la méthode `stacksApi.import()`
**Objectif :** Exposer l'appel API `POST /stacks/import` côté frontend via le service layer. L'endpoint backend attend du `multipart/form-data` avec un champ `file`.
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier — Ajouter dans l'objet `stacksApi` (après `export`, vers ligne 217) :
  ```typescript
  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.post<StackImportResponse>('/stacks/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  ```
- `frontend/src/services/api.ts` — Modifier — Ajouter `StackImportResponse` dans les imports depuis `@/types/api` (ligne 61, après `StackExportData`)
**Dépend de :** Tâche 1
**Fichier de référence :** Méthode [`stacksApi.export()`](frontend/src/services/api.ts:216) dans le même objet. Noter que contrairement à `export` qui fait un GET simple, `import` doit construire un `FormData` et forcer le `Content-Type: multipart/form-data` pour correspondre au backend [`UploadFile = File(...)`](backend/app/api/v1/import_export.py:73).

---

### Tâche 3 : Bouton Import + dialog avec validation client + logique complète dans `Stacks.vue`
**Objectif :** Ajouter un bouton "Import" dans le header de la carte Stacks, un dialog de sélection de fichier avec validation côté client avant envoi, et la logique d'appel API avec gestion des erreurs.
**Fichiers :**
- `frontend/src/views/Stacks.vue` — Modifier — Modifications détaillées :

  1. **Template — Bouton Import dans le card header** (ligne 8-13) — Ajouter un bouton "Import" à côté de "Create Stack" :
     ```html
     <el-button
       type="primary"
       @click="openCreateDialog"
     >
       Create Stack
     </el-button>
     <el-button
       @click="showImportDialog = true"
     >
       Import
     </el-button>
     ```

  2. **Template — Dialog d'import** (après le dialog de déploiement, vers ligne 469) — Ajouter un nouveau `el-dialog` :
     ```html
     <!-- Dialog d'import -->
     <el-dialog
       v-model="showImportDialog"
       title="Import Stack"
       width="500px"
       destroy-on-close
     >
       <el-form label-width="120px">
         <el-form-item label="JSON File">
           <input
             ref="fileInputRef"
             type="file"
             accept=".json"
             class="import-file-input"
             @change="handleFileSelect"
           />
         </el-form-item>
         <el-alert
           v-if="importError"
           :title="importError"
           type="error"
           show-icon
           closable
           style="margin-top: 12px"
         />
       </el-form>
       <template #footer>
         <el-button @click="showImportDialog = false">
           Cancel
         </el-button>
         <el-button
           type="primary"
           :disabled="!selectedImportFile"
           :loading="importing"
           @click="handleImport"
         >
           Import
         </el-button>
       </template>
     </el-dialog>
     ```

  3. **Script — Nouveaux états réactifs** (après `creatingVersion`, vers ligne 504) :
     ```typescript
     const showImportDialog = ref(false)
     const selectedImportFile = ref<File | null>(null)
     const importing = ref(false)
     const importError = ref<string | null>(null)
     const fileInputRef = ref<HTMLInputElement | null>(null)
     ```

  4. **Script — Fonction `handleFileSelect`** — Validation côté client du fichier sélectionné :
     ```typescript
     function handleFileSelect(event: Event): void {
       const input = event.target as HTMLInputElement
       const file = input.files?.[0]
       importError.value = null
       selectedImportFile.value = null

       if (!file) return

       // Vérifier l'extension
       if (!file.name.endsWith('.json')) {
         importError.value = 'Please select a JSON file (.json)'
         return
       }

       // Lire et valider le contenu JSON
       const reader = new FileReader()
       reader.onload = (e): void => {
         try {
           const content = JSON.parse(e.target?.result as string)

           // Validation de la structure (AC 2)
           if (content.version !== '1.0') {
             importError.value = 'Invalid format: unsupported version (expected "1.0")'
             return
           }
           if (!content.stack || typeof content.stack !== 'object') {
             importError.value = 'Invalid format: "stack" section is missing'
             return
           }
           if (!content.stack.name) {
             importError.value = 'Invalid format: stack name is required'
             return
           }
           if (!content.stack.template) {
             importError.value = 'Invalid format: stack template is required'
             return
           }

           selectedImportFile.value = file
         } catch {
           importError.value = 'Invalid JSON file: unable to parse content'
         }
       }
       reader.readAsText(file)
     }
     ```

  5. **Script — Fonction `handleImport`** — Appel API + rafraîchissement + sélection :
     ```typescript
     async function handleImport(): Promise<void> {
       if (!selectedImportFile.value) return
       importing.value = true
       importError.value = null
       try {
         const response = await stacksApi.import(selectedImportFile.value)
         ElMessage.success(`Stack "${response.data.name}" imported successfully`)
         showImportDialog.value = false
         selectedImportFile.value = null
         // Rafraîchir la liste et sélectionner la nouvelle stack
         await stacksStore.fetchStacks(authStore.organizationId || undefined)
         const newStack = stacksStore.stacks.find(s => s.id === response.data.stack_id)
         if (newStack) {
           selectStack(newStack)
         }
       } catch (err: unknown) {
         // Afficher l'erreur du backend si disponible (AC 4)
         const axiosErr = err as { response?: { data?: { detail?: string } } }
         importError.value = axiosErr.response?.data?.detail || 'Failed to import stack'
       } finally {
         importing.value = false
       }
     }
     ```

  6. **Style — Input file styling** (dans la section `<style scoped>`, vers ligne 908) :
     ```css
     .import-file-input {
       width: 100%;
     }
     ```

**Dépend de :** Tâche 2
**Fichier de référence :** Dialog de création existant dans [`Stacks.vue`](frontend/src/views/Stacks.vue:366) pour la structure `el-dialog`. Fonction [`exportStack()`](frontend/src/views/Stacks.vue:748) pour le pattern try/catch + ElMessage. Format d'export [`StackExportData`](frontend/src/types/api.ts:264) pour les clés de validation côté client.

---

### Tâche 4 : Tests unitaires pour l'import
**Objectif :** Vérifier que la fonctionnalité d'import fonctionne correctement (validation client, appel API, gestion d'erreur, rafraîchissement de la liste).
**Fichiers :**
- `frontend/tests/unit/views/Stacks.spec.ts` — Modifier — Ajouts :
  1. Ajouter `import: vi.fn().mockResolvedValue({ data: { message: 'Stack imported successfully', stack_id: 'new-stack-1', name: 'Imported Stack' } })` dans le mock de `stacksApi` (ligne 16, après `export`)
  2. Ajouter un nouveau `describe('importStack')` :
     - Test : `handleFileSelect` rejette un fichier non-JSON → `importError` est renseigné
     - Test : `handleFileSelect` rejette un JSON sans `version: "1.0"` → `importError` est renseigné
     - Test : `handleFileSelect` rejette un JSON sans section `stack` → `importError` est renseigné
     - Test : `handleFileSelect` accepte un fichier JSON valide → `selectedImportFile` est renseigné
     - Test : `handleImport` appelle `stacksApi.import` avec le bon fichier
     - Test : `handleImport` affiche un message de succès après import
     - Test : `handleImport` affiche l'erreur backend si l'API échoue
**Dépend de :** Tâche 3
**Fichier de référence :** [`describe('exportStack')`](frontend/tests/unit/views/Stacks.spec.ts:195) dans le même fichier pour le pattern de mock et de test

## Tests à écrire

### Tests frontend

**Fichier :** `frontend/tests/unit/views/Stacks.spec.ts`

| Cas de test | Description |
|-------------|-------------|
| handleFileSelect rejette fichier non-JSON | `importError` contient un message d'erreur sur l'extension |
| handleFileSelect rejette JSON version invalide | `importError` indique version non supportée |
| handleFileSelect rejette JSON sans section stack | `importError` indique section stack manquante |
| handleFileSelect rejette JSON sans stack.name | `importError` indique nom requis |
| handleFileSelect accepte fichier JSON valide | `selectedImportFile` est renseigné, `importError` est null |
| handleImport appelle stacksApi.import | `stacksApi.import` est appelé avec le fichier sélectionné |
| handleImport succès | `ElMessage.success` affiché + liste rafraîchie |
| handleImport erreur API | `importError` affiche le détail de l'erreur backend |

### Commandes de validation

```bash
# Lint frontend
cd frontend && npx eslint src/views/Stacks.vue src/services/api.ts src/types/api.ts

# Tests unitaires
cd frontend && npx vitest run tests/unit/views/Stacks.spec.ts

# Build frontend (vérifie que tout compile)
cd frontend && npx vue-tsc --noEmit && npm run build
```

## Notes d'implémentation

**Date :** 2026-04-14

### Fichiers modifiés/créés
- `frontend/src/types/api.ts` — Ajout de l'interface `StackImportResponse` (message, stack_id, name)
- `frontend/src/services/api.ts` — Ajout de l'import `StackImportResponse` et de la méthode `stacksApi.import(file)` utilisant `FormData` avec `Content-Type: multipart/form-data`
- `frontend/src/views/Stacks.vue` — Ajout du bouton "Import" dans le header, dialog d'import avec input file, validation client (extension .json, version "1.0", présence stack.name et stack.template), logique d'appel API avec gestion d'erreur inline, rafraîchissement de la liste et sélection de la nouvelle stack après succès
- `frontend/tests/unit/views/Stacks.spec.ts` — Ajout du mock `stacksApi.import`, 8 nouveaux tests (5 handleFileSelect + 3 handleImport)

### Décisions techniques
- Validation client via `FileReader` + `JSON.parse` avant envoi : vérifie extension, version, présence de stack/name/template
- Erreur d'import affichée inline dans le dialog (`el-alert`) plutôt que via `ElMessage.error` — meilleur UX car l'utilisateur reste dans le contexte du dialog
- Utilisation d'un `<input type="file">` natif plutôt que `el-upload` pour garder le contrôle total sur la validation

### Divergences par rapport à l'analyse
- Aucune divergence significative

### Tests ajoutés
- `frontend/tests/unit/views/Stacks.spec.ts` — 8 nouveaux tests (16 total, tous passants)
  - handleFileSelect : rejet extension non-JSON, version invalide, stack manquant, name manquant, fichier valide
  - handleImport : appel API avec bon fichier, message de succès, erreur backend affichée
