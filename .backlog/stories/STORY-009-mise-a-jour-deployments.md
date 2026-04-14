# STORY-009 : Édition à chaud des containers depuis la vue Compute

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux modifier la restart policy et les limites de ressources d'un container depuis la vue Compute afin d'ajuster son comportement à chaud, sans recréation.

Cette story couvre les **modifications à chaud** (sans recréation du container) :
- **Restart policy** : politique de redémarrage (`no`, `always`, `on-failure`, `unless-stopped`)
- **Ressources** : limites mémoire, CPU shares, PIDs limit

Les modifications nécessitant une recréation (env vars, labels, image, ports, volumes, sécurité) sont couvertes par les stories de l'EPIC-009 :
- STORY-027 : Édition des ports et image
- STORY-028 : Gestion des réseaux à chaud
- STORY-029 : Édition volumes et sécurité
- STORY-030 : Implémentation env vars et labels

## Contexte technique
- Vue existante `views/ContainerDetail.vue` (accessible depuis la vue Compute via `ContainerTable`)
- Endpoints backend déjà implémentés :
  - `PATCH /docker/containers/{id}/restart-policy` — mise à jour de la politique de redémarrage
  - `PATCH /docker/containers/{id}/resources` — mise à jour des limites mémoire, CPU, PIDs
- Types TypeScript déjà définis dans `types/api.ts` :
  - `ContainerUpdateRestartPolicyRequest` (ligne 929)
  - `ContainerUpdateResourcesRequest` (ligne 935)
  - `ContainerUpdateResponse` (ligne 942)
- Méthodes API déjà disponibles dans `services/api.ts` :
  - `containersApi.updateRestartPolicy(id, data)` (ligne 319)
  - `containersApi.updateResources(id, data)` (ligne 322)
- Le renommage est déjà fonctionnel dans `ContainerDetail.vue` (dialog + logique, ligne 336-696)

## Critères d'acceptation (AC)
- [x] AC 1 : La page de détail d'un container affiche la restart policy actuelle avec un bouton pour la modifier
- [x] AC 2 : Un dialog permet de changer la restart policy (no, always, on-failure, unless-stopped) et le maximum_retry_count pour on-failure
- [x] AC 3 : La page de détail affiche les limites de ressources actuelles (mémoire, CPU shares, PIDs limit) avec un bouton pour les modifier
- [x] AC 4 : Un dialog permet de modifier les limites mémoire (en MB), CPU shares et PIDs limit
- [x] AC 5 : Après chaque mise à jour, un toast de confirmation s'affiche et les données du container se rafraîchissent
- [x] AC 6 : Les erreurs sont gérées avec toast d'erreur et message descriptif
- [x] AC 7 : Des boutons d'accès rapide aux dialogs restart policy et ressources sont disponibles dans la barre d'actions du header
- [ ] AC 8 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune (les endpoints backend, types et méthodes API sont déjà en place)

## État d'avancement technique
- [x] Tâche 1 : Affichage et édition de la restart policy dans ContainerDetail.vue
- [x] Tâche 2 : Affichage et édition des ressources dans ContainerDetail.vue
- [x] Tâche 3 : Intégration des actions dans le header de ContainerDetail.vue

## Notes d'implémentation

**Date :** 2026-04-14

### Fichiers modifiés/créés
- `frontend/src/views/ContainerDetail.vue` : Ajout des dialogs restart policy et ressources, boutons d'action header, computed properties, fonctions de gestion
- `frontend/tests/unit/views/ContainerDetail.spec.ts` : Ajout de 16 tests unitaires couvrant les nouvelles fonctionnalités

### Décisions techniques
- Utilisation de `el-dialog` + `el-form` pour les dialogs, cohérent avec le dialog de rename existant
- Conversion bytes ↔ MB pour la mémoire (API utilise bytes, UI affiche MB)
- Champ `maximum_retry_count` conditionnellement visible uniquement pour la policy `on-failure`
- Valeurs à 0 dans le formulaire ressources envoyées comme `undefined` (null) à l'API pour signifier "illimité"
- Computed properties `restartPolicyLabel` et `resourcesSummary` pour l'affichage dans le header

### Divergences par rapport à l'analyse
- Aucune divergence : l'implémentation suit exactement les tâches pré-analysées

### Difficultés rencontrées
- Aucune difficulté majeure

### Tests ajoutés
- `frontend/tests/unit/views/ContainerDetail.spec.ts` : 16 nouveaux tests (3 describe blocks)
  - Restart Policy Dialog : 7 tests (ouverture, pré-remplissage, appel API, champ conditionnel, fermeture, gestion erreur)
  - Resources Dialog : 7 tests (ouverture, pré-remplissage, conversion MB→bytes, valeurs undefined, fermeture, gestion erreur)
  - Header action buttons : 2 tests (présence des boutons)
- Total : 46 tests passent (30 existants + 16 nouveaux)

### Validation
- Lint : ✅ 0 erreur
- Tests : ✅ 514 tests passent (0 échec)
- Type check : ✅ Aucune erreur dans les fichiers de la story (7 erreurs pré-existantes dans Images.vue et Stacks.vue)

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter l'affichage et l'édition de la restart policy dans ContainerDetail.vue
**Objectif :** Afficher la restart policy actuelle du container dans la section infos et ajouter un dialog pour la modifier via `containersApi.updateRestartPolicy()`
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  1. Dans la section d'informations du container (onglet Infos ou section header-meta), ajouter l'affichage de la restart policy actuelle :
     - Récupérer depuis `containerDetail.value?.host_config?.restart_policy?.name`
     - Afficher avec un `el-tag` et un bouton "Modifier" à côté
  2. Ajouter un state pour le dialog restart policy :
     ```typescript
     const restartPolicyDialogVisible = ref(false)
     const restartPolicyLoading = ref(false)
     const restartPolicyForm = reactive({
       name: 'no' as string,
       maximum_retry_count: 0 as number | null,
     })
     ```
  3. Ajouter le dialog `el-dialog` avec :
     - `el-select` pour la policy : options `no`, `always`, `on-failure`, `unless-stopped`
     - `el-input-number` pour `maximum_retry_count`, visible uniquement si `name === 'on-failure'`
  4. Implémenter `openRestartPolicyDialog()` : pré-remplir avec les valeurs actuelles
  5. Implémenter `handleUpdateRestartPolicy()` : appeler `containersApi.updateRestartPolicy()`, toast succès/erreur, rafraîchir les données via `loadContainerDetail()`
  6. Ajouter le template du dialog dans la section dialogs (après le dialog de rename existant)
**Dépend de :** Aucune

### Tâche 2 : Ajouter l'affichage et l'édition des ressources dans ContainerDetail.vue
**Objectif :** Afficher les limites de ressources actuelles (mémoire, CPU shares, PIDs) et ajouter un dialog pour les modifier via `containersApi.updateResources()`
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  1. Dans la section d'informations du container, ajouter l'affichage des ressources actuelles :
     - Mémoire : depuis `containerDetail.value?.host_config?.resources?.memory` (convertir bytes → MB)
     - CPU shares : depuis `containerDetail.value?.host_config?.resources?.cpu_shares`
     - PIDs limit : depuis `containerDetail.value?.host_config?.resources?.pids_limit`
     - Afficher dans un bloc avec un bouton "Modifier"
  2. Ajouter un state pour le dialog ressources :
     ```typescript
     const resourcesDialogVisible = ref(false)
     const resourcesLoading = ref(false)
     const resourcesForm = reactive({
       memory_limit: 0 as number | null,  // en MB dans le form, converti en bytes pour l'API
       cpu_shares: 0 as number | null,
       pids_limit: 0 as number | null,
     })
     ```
  3. Ajouter le dialog `el-dialog` avec :
     - `el-input-number` pour la mémoire (en MB, avec step=64, min=0) — label "Limite mémoire (MB)"
     - `el-input-number` pour CPU shares (min=0, max=1024) — label "CPU shares"
     - `el-input-number` pour PIDs limit (min=0) — label "Limite PIDs"
     - Indication : laisser à 0 ou vide pour "illimité" (envoyer `null` à l'API)
  4. Implémenter `openResourcesDialog()` : pré-remplir avec les valeurs actuelles (convertir bytes → MB pour mémoire)
  5. Implémenter `handleUpdateResources()` : appeler `containersApi.updateResources()` en convertissant MB → bytes (`memory_limit * 1024 * 1024`), toast succès/erreur, rafraîchir via `loadContainerDetail()`
  6. Ajouter le template du dialog dans la section dialogs
**Dépend de :** Aucune

### Tâche 3 : Intégrer les nouvelles actions dans le header de ContainerDetail.vue
**Objectif :** Ajouter des boutons d'accès rapide aux dialogs restart policy et ressources dans la barre d'actions du header
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier —
  1. Dans la section `header-actions` (ligne ~76), ajouter après les boutons existants :
     - Bouton "Restart Policy" avec icône `RefreshRight`, ouvre `restartPolicyDialogVisible = true`
     - Bouton "Ressources" avec icône `Cpu`, ouvre `resourcesDialogVisible = true`
  2. Grouper ces boutons dans un `el-button-group` ou les séparer visuellement avec un divider
**Dépend de :** Tâche 1, Tâche 2

## Tests à écrire

### Frontend
- `frontend/tests/unit/views/ContainerDetail.spec.ts` — Tests des nouvelles fonctionnalités :
  - Test que le bouton "Restart Policy" ouvre le dialog
  - Test que le dialog restart policy affiche les valeurs actuelles du container
  - Test que la soumission du formulaire restart policy appelle `containersApi.updateRestartPolicy()` avec les bons paramètres
  - Test que le bouton "Ressources" ouvre le dialog
  - Test que le dialog ressources affiche les valeurs actuelles (mémoire en MB, CPU shares, PIDs)
  - Test que la soumission du formulaire ressources appelle `containersApi.updateResources()` avec la conversion MB → bytes
  - Test que les erreurs API sont gérées avec toast d'erreur
  - Test que `loadContainerDetail()` est appelé après chaque mise à jour réussie
