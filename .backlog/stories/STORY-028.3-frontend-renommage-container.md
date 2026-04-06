# STORY-028.3 : Frontend — Renommage du container

**Statut :** DONE
**Story Parente :** STORY-028 — Backend + Frontend — Onglet Config éditable
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
Ajouter la fonctionnalité de renommage d'un container depuis l'UI. Un bouton "Renommer" sera disponible dans le header de la page Container Detail, avec un dialog de confirmation et validation du nouveau nom.

## Critères d'acceptation (AC)
- [x] AC 8 : Un endpoint `POST /api/v1/docker/containers/{id}/rename` accepte `{new_name: str}` (backend déjà implémenté dans STORY-028.1)
- [x] AC 11 : Un bouton "Renommer" avec validation du nouveau nom est disponible

## Contexte technique
- L'endpoint backend `POST /containers/{id}/rename` est implémenté dans STORY-028.1
- Le header du container est dans `frontend/src/views/ContainerDetail.vue` (section `header-identity`)
- Le nom du container est affiché dans un `<h2>` avec la classe `container-name`
- Utilisation d'Element Plus : `ElDialog`, `ElInput`, `ElButton`, `ElMessage`
- Validation du nom : pattern Docker `^[a-zA-Z0-9][a-zA-Z0-9_.-]*$`
- Le store containers (`frontend/src/stores/`) peut être utilisé pour l'action

### Fichiers de référence
- `frontend/src/views/ContainerDetail.vue` — Header avec nom du container
- `frontend/src/services/api.ts` — API service (containersApi)
- `frontend/src/types/api.ts` — Types existants
- `frontend/src/stores/` — Stores Pinia existants

## Dépendances
- STORY-028.1 : Backend API — Update & Rename (endpoint POST rename)

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter le type et la méthode API frontend pour le rename
**Objectif :** Créer le type de requête et la méthode API pour le renommage
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter `ContainerRenameRequest`
- `frontend/src/services/api.ts` — Modifier — Ajouter `containersApi.rename()`
**Dépend de :** Aucune

### Tâche 2 : Ajouter le bouton "Renommer" et le dialog dans ContainerDetail.vue
**Objectif :** Ajouter un bouton edit/renommer à côté du nom du container, avec un dialog ElDialog pour saisir le nouveau nom
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier — Ajouter le bouton, le dialog, la validation, et l'appel API
**Dépend de :** Tâche 1

### Tâche 3 : Tests unitaires frontend
**Objectif :** Tester le dialog de renommage et l'appel API
**Fichiers :**
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Modifier — Ajouter les tests de renommage
**Dépend de :** Tâche 2

## Tests à écrire

### Frontend
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Ajouts
  - Affichage du bouton "Renommer"
  - Ouverture du dialog au clic
  - Validation du nom (caractères invalides rejetés)
  - Appel API correct au clic "Confirmer"
  - Mise à jour du nom affiché après succès
  - Message d'erreur en cas d'échec API
  - Fermeture du dialog sans action au clic "Annuler"

### Commandes de validation
```bash
cd /home/stef/workspace/windflow/frontend && pnpm test:unit -- --run tests/unit/views/ContainerDetail.spec.ts
cd /home/stef/workspace/windflow/frontend && pnpm typecheck
```

## État d'avancement technique
- [x] Tâche 1 : Type et méthode API pour le rename
- [x] Tâche 2 : Bouton "Renommer" + dialog dans ContainerDetail.vue
- [x] Tâche 3 : Tests unitaires frontend

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/types/api.ts` — Ajout `ContainerRenameRequest` + `ContainerRenameResponse`
- `frontend/src/services/api.ts` — Ajout import types + méthode `containersApi.rename()`
- `frontend/src/views/ContainerDetail.vue` — Ajout bouton "Renommer" (icône Edit), dialog ElDialog avec validation pattern Docker, state réactif, fonctions `openRenameDialog()`, `handleRename()`, `onRenameDialogClosed()`
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Ajout mock `containersApi.rename`, stubs `el-dialog`/`el-form`/`el-form-item`, 9 tests de renommage

### Décisions techniques
- Utilisation de `ElDialog` plutôt que `ElMessageBox` pour permettre la validation inline et une meilleure UX
- Validation côté frontend du pattern Docker `^[a-zA-Z0-9][a-zA-Z0-9_.-]*$` avant appel API
- Si le nom est identique, le dialog se ferme sans appel API (optimisation)
- Le dialog se ferme automatiquement après succès et rafraîchit les détails du container

### Tests
- **Exécutés** : `pnpm test:unit` → 453/453 passent (dont 31 dans ContainerDetail.spec.ts, +9 tests rename)
- **Typecheck** : `pnpm type-check` → ✅ sans erreur
