# STORY-007 : Export de stacks au format JSON

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux exporter une stack au format JSON depuis l'interface afin de sauvegarder ou partager la configuration d'une stack avec d'autres utilisateurs.

## Contexte technique
- Vue existante `views/Stacks.vue`
- API : `GET /stacks/{id}/export`
- Type TypeScript à ajouter : `StackExportData`
- Bouton "Exporter" sur chaque stack → déclenche téléchargement du fichier JSON
- Extension de `stacksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [x] AC 1 : Chaque stack dispose d'un bouton/action "Exporter" qui appelle `GET /stacks/{id}/export`
- [x] AC 2 : L'export déclenche automatiquement le téléchargement d'un fichier `{nom-stack}.json` dans le navigateur
- [x] AC 3 : Le type TypeScript `StackExportData` est défini et `stacksApi.export` est disponible
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
- [x] T1 : Type `StackExportData` ajouté dans `frontend/src/types/api.ts`
- [x] T2 : Méthode `stacksApi.export()` ajoutée dans `frontend/src/services/api.ts`
- [x] T3 : Action `'export'` ajoutée au composant `ActionButtons.vue`
- [x] T4 : Bouton Export + logique de téléchargement dans `Stacks.vue`
- [x] T5 : Tests unitaires de l'export dans `Stacks.spec.ts`

## Tâches d'implémentation détaillées

### T1 — Ajouter le type TypeScript `StackExportData`
**Objectif :** Définir le type TypeScript correspondant à la réponse JSON du backend pour l'export de stack.

- **Modifier** `frontend/src/types/api.ts` — Ajouter après les types Stack existants (vers ligne 261) :
  ```typescript
  // Stack export types (mirrors backend import_export.py response)
  export interface StackExportData {
    version: string
    stack: {
      name: string
      description: string | null
      version: string
      category: string | null
      tags: string[]
      template: string
      variables: Record<string, unknown>
      icon_url: string | null
      screenshots: string[]
      documentation_url: string | null
      author: string | null
      license: string | null
    }
  }
  ```
- **Dépendance :** Aucune
- **Fichier de référence :** Types `Stack` / `StackCreate` existants dans le même fichier + format de réponse backend dans `backend/app/api/v1/import_export.py` lignes 47-63

---

### T2 — Ajouter la méthode `stacksApi.export()`
**Objectif :** Exposer l'appel API `GET /stacks/{id}/export` côté frontend via le service layer.

- **Modifier** `frontend/src/services/api.ts` — Ajouter dans l'objet `stacksApi` (après `redeploy`, vers ligne 213) :
  ```typescript
  export: (id: string) =>
    http.get<StackExportData>(`/stacks/${id}/export`),
  ```
- **Modifier** `frontend/src/services/api.ts` — Ajouter `StackExportData` dans les imports depuis `@/types/api` (ligne 27)
- **Dépendance :** T1
- **Fichier de référence :** Méthodes existantes `stacksApi.get()`, `stacksApi.validate()` dans le même objet

---

### T3 — Ajouter l'action `'export'` au composant `ActionButtons`
**Objectif :** Permettre l'affichage d'un bouton Export dans les barres d'actions génériques.

- **Modifier** `frontend/src/components/ui/ActionButtons.vue` :
  1. Ajouter `Download` dans les imports depuis `@element-plus/icons-vue` (ligne 42)
  2. Ajouter `'export'` au type `ActionType` (ligne 50) :
     ```typescript
     export type ActionType = 'start' | 'stop' | 'restart' | 'logs' | 'delete' | 'edit' | 'deploy' | 'scan' | 'select' | 'password' | 'export'
     ```
  3. Ajouter l'entrée dans `defaultActionConfig` (vers ligne 120) :
     ```typescript
     export: {
       icon: Download,
       tooltip: 'Exporter',
     },
     ```
  4. Ajouter le style hover pour le bouton export (section CSS, vers ligne 200) :
     ```css
     .action-buttons__btn--export:hover:not(:disabled) {
       color: var(--color-info);
       border-color: var(--color-info);
     }
     ```
- **Dépendance :** Aucune
- **Fichier de référence :** Entrées existantes dans `defaultActionConfig` (ex: `deploy`, `edit`)

---

### T4 — Ajouter le bouton Export et la logique de téléchargement dans `Stacks.vue`
**Objectif :** Permettre à l'utilisateur d'exporter une stack en cliquant sur le bouton Export, ce qui déclenche le téléchargement d'un fichier `{nom-stack}.json`.

- **Modifier** `frontend/src/views/Stacks.vue` :
  1. **Template** — Modifier les actions de la table (ligne 60) pour inclure `'export'` :
     ```html
     <ActionButtons
       :actions="['edit', 'deploy', 'export', 'delete']"
       @action="(type) => handleStackAction(type, row)"
     />
     ```
  2. **Script** — Ajouter la fonction `exportStack` (après `confirmDelete`, vers ligne 745) :
     ```typescript
     async function exportStack(stack: Stack): Promise<void> {
       try {
         const response = await stacksApi.export(stack.id)
         const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
         const url = URL.createObjectURL(blob)
         const link = document.createElement('a')
         link.href = url
         link.download = `${stack.name}.json`
         document.body.appendChild(link)
         link.click()
         document.body.removeChild(link)
         URL.revokeObjectURL(url)
         ElMessage.success(`Stack "${stack.name}" exported successfully`)
       } catch {
         ElMessage.error('Failed to export stack')
       }
     }
     ```
  3. **Script** — Ajouter le case `'export'` dans `handleStackAction` (ligne 750) :
     ```typescript
     case 'export':
       exportStack(stack)
       break
     ```
- **Dépendance :** T2 + T3
- **Fichier de référence :** Fonction `confirmDelete` existante dans le même fichier pour le pattern try/catch + ElMessage

---

### T5 — Tests unitaires pour l'export
**Objectif :** Vérifier que la fonctionnalité d'export fonctionne correctement (appel API, téléchargement, gestion d'erreur).

- **Modifier** `frontend/tests/unit/views/Stacks.spec.ts` :
  1. Ajouter `export: vi.fn().mockResolvedValue({ data: { version: '1.0', stack: { name: 'Test Stack', ... } } })` dans le mock de `stacksApi` (ligne 16)
  2. Ajouter un test dans le describe `ActionButtons integration` :
     - Vérifier que les actions attendues incluent `'export'`
  3. Ajouter un nouveau `describe('exportStack')` :
     - Test : appelle `stacksApi.export` avec le bon ID
     - Test : affiche un message de succès après export
     - Test : affiche un message d'erreur si l'API échoue
- **Dépendance :** T4
- **Fichier de référence :** Tests existants dans le même fichier (pattern de mock, stubs Element Plus)

---

## Tests à écrire

### Tests frontend

**Fichier :** `frontend/tests/unit/views/Stacks.spec.ts`

| Cas de test | Description |
|-------------|-------------|
| ActionButtons inclut export | Vérifier que les actions de la table contiennent `'export'` |
| exportStack appelle l'API | `stacksApi.export` est appelé avec le bon `stack.id` |
| exportStack succès | Message `ElMessage.success` affiché après export réussi |
| exportStack erreur | Message `ElMessage.error` affiché si l'API rejette |

**Fichier :** `frontend/tests/unit/components/ActionButtons.spec.ts` (si existant)

| Cas de test | Description |
|-------------|-------------|
| Action export affichée | Le bouton export est rendu avec l'icône Download |
| Action export cliquable | Un clic émet l'événement `'action'` avec type `'export'` |

### Commandes de validation

```bash
# Lint frontend
cd frontend && npx eslint src/views/Stacks.vue src/services/api.ts src/types/api.ts src/components/ui/ActionButtons.vue

# Tests unitaires
cd frontend && npx vitest run tests/unit/views/Stacks.spec.ts

# Build frontend (vérifie que tout compile)
cd frontend && npx vue-tsc --noEmit && npm run build
```

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/types/api.ts` — Ajout du type `StackExportData` (interface avec `version` et `stack` imbriqué)
- `frontend/src/services/api.ts` — Ajout de l'import `StackExportData` et de la méthode `stacksApi.export(id)` appelant `GET /stacks/{id}/export`
- `frontend/src/components/ui/ActionButtons.vue` — Ajout de l'action `'export'` : icône `Download`, type étendu, config par défaut, style hover `--color-info`
- `frontend/src/views/Stacks.vue` — Ajout de `'export'` dans les actions de la table, fonction `exportStack()` avec téléchargement JSON via Blob/URL.createObjectURL, case `'export'` dans `handleStackAction`
- `frontend/tests/unit/views/Stacks.spec.ts` — Ajout du mock `stacksApi.export`, test d'intégration ActionButtons avec `'export'`, 3 tests unitaires exportStack (appel API, succès, erreur), mock `URL.createObjectURL` pour jsdom
- `frontend/tests/unit/components/ui/ActionButtons.spec.ts` — Ajout de 2 tests pour l'action export (rendu et événement)

### Divergences
- Aucune divergence par rapport aux tâches pré-analysées. L'implémentation suit exactement les spécifications de la story.

### Résultats de validation
- **Tests unitaires** : 22/22 passés (8 Stacks + 14 ActionButtons)
- **Lint ESLint** : 0 erreurs sur les 4 fichiers modifiés
- **Build frontend** : Succès (exit code 0). Les warnings TypeScript pré-existants dans `TargetWizard.vue` et `ContainerTable.vue` ne sont pas liés à cette story.
