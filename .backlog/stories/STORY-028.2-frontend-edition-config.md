# STORY-028.2 : Frontend — Onglet Config éditable

**Statut :** DONE
**Story Parente :** STORY-028 — Backend + Frontend — Onglet Config éditable
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
Créer l'onglet **Config** dans la vue Container Detail avec les sections éditables : variables d'environnement, labels, restart policy et resource limits. Les modifications de restart policy et resources utilisent les endpoints de la STORY-028.1 (docker update, sans recréation). Les modifications d'env vars et labels affichent un avertissement de recréation avec confirmation.

## Critères d'acceptation (AC)
- [x] AC 1 : Un nouvel onglet **Config** est ajouté après l'onglet Stats
- [x] AC 2 : La section **Env Vars** affiche les variables dans un tableau éditable (clé/valeur) avec possibilité d'ajouter/supprimer des lignes
- [x] AC 3 : La section **Labels** affiche les labels dans un tableau éditable (clé/valeur) avec possibilité d'ajouter/supprimer
- [x] AC 4 : La section **Restart Policy** permet de changer la politique via un sélecteur (no, always, on-failure, unless-stopped) avec un bouton "Appliquer"
- [x] AC 5 : La section **Resource Limits** permet de modifier Memory limit, CPU shares, PidsLimit via des inputs numériques avec un bouton "Appliquer"
- [x] AC 9 : Les modifications de restart policy et resources utilisent `docker update` (sans recréation) — retourne le résultat immédiatement
- [x] AC 10 : Les modifications d'env vars / labels affichent un avertissement : "⚠️ Modifier les variables d'environnement nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir." avec confirmation obligatoire
- [x] AC 12 : Les inputs sont pré-remplis avec les valeurs actuelles du container

## Contexte technique
- L'onglet est ajouté dans `ContainerDetail.vue` au même niveau que "Stats"
- Un nouveau composant `ContainerConfigTab.vue` sera créé
- Les types frontend existent dans `frontend/src/types/api.ts` — `ContainerConfigInfo`, `ContainerHostConfigInfo`, `ContainerRestartPolicyInfo`, `ContainerResourcesInfo`
- L'API service est dans `frontend/src/services/api.ts` — `containersApi`
- Utilisation d'Element Plus pour les composants UI (ElTable, ElSelect, ElInputNumber, ElButton, ElMessageBox)
- Pattern de référence : `ContainerInfoTab.vue` pour l'affichage des données structurées
- Les données du container sont déjà disponibles via `containerDetail` dans `ContainerDetail.vue`

### Fichiers de référence
- `frontend/src/components/ContainerInfoTab.vue` — Pattern d'affichage existant
- `frontend/src/views/ContainerDetail.vue` — Intégration des onglets
- `frontend/src/types/api.ts` — Types existants
- `frontend/src/services/api.ts` — API service

## Dépendances
- STORY-028.1 : Backend API — Update & Rename (endpoints PATCH restart-policy, PATCH resources)

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter les types et méthodes API frontend
**Objectif :** Créer les types de requête/réponse et les méthodes API pour les endpoints PATCH de la STORY-028.1
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier
- `frontend/src/services/api.ts` — Modifier
**Dépend de :** Aucune

**Détails :**

1. Dans `frontend/src/types/api.ts`, ajouter après les types existants du container :

```typescript
/** Requête PATCH restart policy — correspond à ContainerUpdateRestartPolicyRequest backend */
export interface ContainerUpdateRestartPolicyRequest {
  name: string // 'no' | 'always' | 'on-failure' | 'unless-stopped'
  maximum_retry_count?: number
}

/** Requête PATCH resources — correspond à ContainerUpdateResourcesRequest backend */
export interface ContainerUpdateResourcesRequest {
  memory_limit?: number  // bytes
  cpu_shares?: number
  pids_limit?: number    // -1 = unlimited
}

/** Réponse PATCH restart policy / resources — correspond à ContainerUpdateResponse backend */
export interface ContainerUpdateResponse {
  warnings: string[]
}
```

2. Dans `frontend/src/services/api.ts` :
   - Ajouter les 3 nouveaux types dans l'import depuis `@/types/api`
   - Ajouter dans `containersApi` (après `batchStop`) :

```typescript
updateRestartPolicy: (id: string, data: ContainerUpdateRestartPolicyRequest) =>
  http.patch<ContainerUpdateResponse>(`/docker/containers/${id}/restart-policy`, data),

updateResources: (id: string, data: ContainerUpdateResourcesRequest) =>
  http.patch<ContainerUpdateResponse>(`/docker/containers/${id}/resources`, data),
```

### Tâche 2 : Créer le composant ContainerConfigTab.vue
**Objectif :** Créer le composant avec les 4 sections éditables (Env Vars, Labels, Restart Policy, Resource Limits)
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Créer
**Dépend de :** Tâche 1

**Props :** `detail: ContainerDetail | null`

**Structure du composant (4 sections dans des `div class="bg-[var(--color-bg-secondary)] rounded-lg p-4"`) :**

#### Section 1 — Variables d'environnement (éditable)
- Transformer `detail.config.env` (string[] type `"KEY=VALUE"`) en tableau réactif `envVars: Ref<{key: string, value: string}[]>`
- `el-table` avec colonnes : Variable (`el-input`), Valeur (`el-input`), Actions (bouton supprimer `el-icon Delete`)
- Bouton "Ajouter une variable" (`el-button + CirclePlus`)
- ⚠️ Alert de warning : `el-alert type="warning" :closable="false"` avec texte "⚠️ Modifier les variables d'environnement nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir."
- Bouton "Appliquer" → `ElMessageBox.confirm` avec message de confirmation → si confirmé, afficher `ElMessage.info("Fonctionnalité de recréation à venir")` (placeholder backend non disponible)
- Détecter les secrets avec `isSecretKey` de `@/composables/useSecretMasker` et masquer par défaut

#### Section 2 — Labels (éditable)
- Transformer `detail.config.labels` (dict) en tableau réactif `labels: Ref<{key: string, value: string}[]>`
- Même pattern que env vars : `el-table` éditable + bouton ajouter/supprimer
- ⚠️ Même alert de warning que pour les env vars
- Bouton "Appliquer" → même comportement placeholder que env vars

#### Section 3 — Restart Policy (éditable, docker update)
- `el-descriptions` avec un champ éditable :
  - Politique : `el-select` avec options `no`, `always`, `on-failure`, `unless-stopped`
  - Max retry count : `el-input-number` (visible uniquement si `on-failure` sélectionné)
- Bouton "Appliquer" → appelle `containersApi.updateRestartPolicy(containerId, data)`
- State réactif : `loadingRestart`, pré-rempli depuis `detail.host_config.restart_policy`
- Toast de succès/erreur via `ElMessage`

#### Section 4 — Resource Limits (éditable, docker update)
- `el-descriptions` avec champs éditables :
  - Memory limit : `el-input-number` + sélecteur d'unité (MB/GB) → converti en bytes. Utiliser `formatBytes` pour l'affichage initial.
  - CPU shares : `el-input-number` (min 0)
  - PIDs limit : `el-input-number` (min -1, -1 = illimité)
- Bouton "Appliquer" → appelle `containersApi.updateResources(containerId, data)`
- State réactif : `loadingResources`, pré-rempli depuis `detail.host_config.resources`
- Toast de succès/erreur via `ElMessage`

**Imports requis :**
```typescript
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CirclePlus, Delete } from '@element-plus/icons-vue'
import { containersApi } from '@/services/api'
import { formatBytes } from '@/utils/format'
import { isSecretKey, useSecretMasker } from '@/composables/useSecretMasker'
import type { ContainerDetail, ContainerUpdateRestartPolicyRequest, ContainerUpdateResourcesRequest } from '@/types/api'
```

### Tâche 3 : Intégrer l'onglet Config dans ContainerDetail.vue
**Objectif :** Ajouter le tab-pane "Config" et importer le composant
**Fichiers :**
- `frontend/src/views/ContainerDetail.vue` — Modifier
**Dépend de :** Tâche 2

**Détails :**

1. Ajouter l'import du composant :
```typescript
import ContainerConfigTab from '@/components/ContainerConfigTab.vue'
```

2. Ajouter un `<el-tab-pane>` après le tab-pane "Stats" :
```html
<el-tab-pane label="Config" name="config">
  <ContainerConfigTab :detail="containerDetail" />
</el-tab-pane>
```

3. Vérifier que `containerDetail` est bien disponible dans le scope (il l'est déjà, passé aux autres tab-panes)

### Tâche 4 : Tests unitaires frontend
**Objectif :** Tester le composant ContainerConfigTab (rendu, interactions, appels API)
**Fichiers :**
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — Créer
**Dépend de :** Tâche 3

**Pattern de test :** Suivre le pattern de `ContainerOverviewTab.spec.ts` (mock Element Plus, mock API, mount avec stubs)

**Tests à implémenter :**

1. **Rendu — 4 sections présentes** : Le composant monte sans erreur et contient les 4 sections (Env Vars, Labels, Restart Policy, Resource Limits)
2. **Restart Policy — modification** : Changer la valeur du select → cliquer Appliquer → vérifier appel `containersApi.updateRestartPolicy` avec les bons params
3. **Resources — modification** : Changer les valeurs numériques → cliquer Appliquer → vérifier appel `containersApi.updateResources` avec les bons params
4. **Env Vars — ajout/suppression** : Cliquer "Ajouter" → une ligne vide apparaît → cliquer supprimer → la ligne disparaît
5. **Labels — ajout/suppression** : Même pattern que env vars
6. **Warning recréation** : Les sections Env Vars et Labels contiennent un `el-alert` de type "warning"
7. **Loading state** : Le bouton "Appliquer" est désactivé pendant le loading (vérifier attribut `disabled`)
8. **Pré-remplissage** : Les champs sont pré-remplis avec les valeurs de `detail`

**Mock data de base :**
```typescript
const baseDetail = {
  id: 'abc123',
  name: 'test-container',
  config: {
    env: ['PATH=/usr/bin', 'NODE_ENV=production'],
    labels: { 'com.docker.compose.project': 'my-stack', 'version': '1.0' },
  },
  host_config: {
    restart_policy: { name: 'always', maximum_retry_count: null },
    resources: { memory: 536870912, cpu_shares: 1024, pids_limit: 100 },
  },
}
```

**Mocks API :**
```typescript
const mockUpdateRestartPolicy = vi.fn()
const mockUpdateResources = vi.fn()
vi.mock('@/services/api', () => ({
  containersApi: {
    updateRestartPolicy: (...args: unknown[]) => mockUpdateRestartPolicy(...args),
    updateResources: (...args: unknown[]) => mockUpdateResources(...args),
  },
}))
```

## Tests à écrire

### Frontend
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts`
  - Rendu des 4 sections avec données pré-remplies
  - Modification de restart policy → appel API correct
  - Modification de resources → appel API correct
  - Ajout/suppression d'env var → mise à jour du tableau
  - Ajout/suppression de label → mise à jour du tableau
  - Affichage de l'avertissement de recréation pour env vars/labels
  - Bouton "Appliquer" désactivé pendant le loading

### Commandes de validation
```bash
cd /home/stef/workspace/windflow/frontend && pnpm test:unit -- --run tests/unit/components/ContainerConfigTab.spec.ts
cd /home/stef/workspace/windflow/frontend && pnpm typecheck
cd /home/stef/workspace/windflow/frontend && pnpm build
```

## État d'avancement technique
- [x] Tâche 1 : Types et méthodes API frontend
- [x] Tâche 2 : Composant ContainerConfigTab.vue
- [x] Tâche 3 : Intégration dans ContainerDetail.vue
- [x] Tâche 4 : Tests unitaires frontend
- [x] Build & lint OK (tests 29/29 passent, type-check OK sur fichiers modifiés)

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/types/api.ts` — Ajout de `ContainerUpdateRestartPolicyRequest`, `ContainerUpdateResourcesRequest`, `ContainerUpdateResponse`
- `frontend/src/services/api.ts` — Ajout de `updateRestartPolicy()` et `updateResources()` dans `containersApi`
- `frontend/src/components/ContainerConfigTab.vue` — Nouveau composant (4 sections éditables)
- `frontend/src/views/ContainerDetail.vue` — Import du composant + ajout tab-pane "Config"
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — 29 tests unitaires

### Décisions techniques
- Les sections Env Vars et Labels affichent un warning de recréation et un bouton "Appliquer" avec confirmation via `ElMessageBox` — le backend de recréation n'est pas encore disponible, donc un placeholder `ElMessage.info('Fonctionnalité de recréation à venir')` est utilisé
- Les secrets (password, token, key, secret) sont détectés via `isSecretKey` et masqués par défaut dans les inputs (type password)
- La conversion memory utilise MB par défaut et GB si la valeur est un multiple exact de 1024 MB
- `formatBytes` importé depuis `@/utils/format` pour l'affichage de la valeur actuelle en hint

### Validation
- `pnpm test:unit` : 29/29 tests passent sur ContainerConfigTab.spec.ts
- `pnpm type-check` : Erreur préexistante dans `targets.ts` (non liée à cette story)
- Pas de régression introduite
