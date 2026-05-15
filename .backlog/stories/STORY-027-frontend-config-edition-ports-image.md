# STORY-027 : Frontend Config — Édition des ports et mise à jour de l'image

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir modifier l'image et les ports exposés d'un container directement depuis l'onglet Config de la page ContainerDetail afin de mettre à jour ces paramètres sans intervention manuelle sur le daemon Docker.

## Contexte technique

**Dépendance** : STORY-025 (endpoint `/recreate`) doit être implémentée côté backend avant cette story.

**Composant principal** : `frontend/src/components/ContainerConfigTab.vue`

**Nouvelle section Image** — interface :
- Input text pré-rempli avec l'image actuelle (ex: `ghcr.io/open-webui/open-webui:latest`)
- Checkbox "Puller la nouvelle image avant recréation" (`pull_image`)
- Bouton "Mettre à jour l'image" → confirmation → appel `POST /docker/containers/{id}/recreate` avec `{ image: newImage, pull_image: true/false }`
- Après succès : redirect vers la nouvelle URL `/containers/<new_id>` (l'ID change après recréation)

**Nouvelle section Ports** — interface :
```
┌──────────┬──────────┬──────────────┬──────────┬────────┐
│ Host IP  │ Host Port│ Container Port│ Protocole│ Action │
├──────────┼──────────┼──────────────┼──────────┼────────┤
│ 0.0.0.0  │ 8080     │ 80           │ TCP      │ [🗑️]   │
└──────────┴──────────┴──────────────┴──────────┴────────┘
[+ Ajouter un port]                              [Appliquer]
```

Validation des ports :
- Host port : entier 1–65535
- Container port : entier 1–65535
- Protocole : `tcp` ou `udp`
- Pas de doublon sur le couple `hostIp:hostPort`

Format de la requête vers `/recreate` :
```typescript
port_bindings: {
  "80/tcp": [{ HostIp: "0.0.0.0", HostPort: "8080" }]
}
```

**Nouveaux types TypeScript** à ajouter dans `frontend/src/types/api.ts` :
```typescript
interface ContainerRecreateRequest {
  image?: string
  pull_image?: boolean
  env?: string[]
  labels?: Record<string, string>
  port_bindings?: Record<string, Array<{ HostIp: string; HostPort: string }>>
  mounts?: Array<Record<string, unknown>>
  privileged?: boolean
  readonly_rootfs?: boolean
  cap_add?: string[]
  cap_drop?: string[]
  stop_timeout?: number
}

interface ContainerRecreateResponse {
  success: boolean
  message: string
  old_container_id: string
  new_container_id: string
  container: ContainerDetail
  warnings: string[]
}
```

**Nouveau service API** dans `frontend/src/services/api.ts` :
```typescript
recreate: (id: string, data: ContainerRecreateRequest) =>
  http.post<ContainerRecreateResponse>(`/docker/containers/${id}/recreate`, data)
```

**Gestion post-recréation** : après succès, rediriger vers `/containers/<new_container_id>` car l'ID du container change.

## Critères d'acceptation (AC)

- [x] AC 1 : Une section "Image" est présente dans l'onglet Config avec l'image actuelle pré-remplie
- [x] AC 2 : L'opérateur peut modifier l'image et déclencher la recréation avec confirmation
- [x] AC 3 : L'option "Puller la nouvelle image" est disponible (checkbox)
- [x] AC 4 : La section "Ports" affiche les ports actuels dans un tableau éditable
- [x] AC 5 : L'opérateur peut ajouter/supprimer des mappings de ports avec validation
- [x] AC 6 : Cliquer "Appliquer" sur les ports déclenche la recréation après confirmation
- [x] AC 7 : Après une recréation réussie, l'utilisateur est redirigé vers la nouvelle URL du container (`/containers/<new_id>`)
- [x] AC 8 : Un `el-alert type="warning"` indique explicitement que ces actions nécessitent la recréation du container
- [x] AC 9 : Les types TypeScript `ContainerRecreateRequest` et `ContainerRecreateResponse` sont ajoutés dans `api.ts`
- [x] AC 10 : Le service `containersApi.recreate()` est ajouté dans `services/api.ts`
- [x] AC 11 : Tests unitaires du composant (≥ 80%)

## Dépendances

- **STORY-025** : Backend endpoint `/recreate` (requis avant implémentation)

## État d'avancement technique

- [x] Analyse du codebase et identification des fichiers impactés
- [x] Ajouter les types TypeScript dans `frontend/src/types/api.ts`
- [x] Ajouter `containersApi.recreate()` dans `frontend/src/services/api.ts`
- [x] Ajouter la section Image dans `ContainerConfigTab.vue`
- [x] Ajouter la section Ports dans `ContainerConfigTab.vue`
- [x] Implémenter la logique de redirect après recréation
- [x] Écrire les tests unitaires

## Tâches d'implémentation détaillées

### Tâche 1 — Types TypeScript `ContainerRecreateRequest` / `ContainerRecreateResponse`

**Objectif** : Ajouter les types miroirs des schémas Pydantic backend dans le fichier types centralisé.

**Fichier** : [`frontend/src/types/api.ts`](frontend/src/types/api.ts)

**Actions** :
1. Ajouter l'interface `ContainerRecreateRequest` avec les champs :
   - `image?: string`
   - `pull_image?: boolean`
   - `env?: string[]`
   - `labels?: Record<string, string>`
   - `port_bindings?: Record<string, Array<{ HostIp: string; HostPort: string }>>`
   - `mounts?: Array<Record<string, unknown>>`
   - `privileged?: boolean`
   - `readonly_rootfs?: boolean`
   - `cap_add?: string[]`
   - `cap_drop?: string[]`
   - `stop_timeout?: number`
2. Ajouter l'interface `ContainerRecreateResponse` avec les champs :
   - `success: boolean`
   - `message: string`
   - `old_container_id: string`
   - `new_container_id: string`
   - `container: ContainerDetail`
   - `warnings: string[]`
3. Exporter les deux interfaces (ajouter `export` devant chaque).

**Référence pattern** : Les types `ContainerUpdateRestartPolicyRequest` et `ContainerUpdateResourcesRequest` existent déjà dans le même fichier (lignes 948+).

**Vérification post-implémentation** : `cd frontend && pnpm typecheck` doit passer sans erreur.

---

### Tâche 2 — Service API `containersApi.recreate()`

**Objectif** : Ajouter la méthode `recreate` dans le service containers API.

**Fichier** : [`frontend/src/services/api.ts`](frontend/src/services/api.ts)

**Actions** :
1. Importer `ContainerRecreateRequest` et `ContainerRecreateResponse` dans le bloc d'imports type (ligne 7-74).
2. Ajouter dans l'objet `containersApi` (après `create`, avant la fin) :
   ```typescript
   recreate: (id: string, data: ContainerRecreateRequest) =>
     http.post<ContainerRecreateResponse>(`/docker/containers/${id}/recreate`, data)
   ```
3. S'assurer que le typage est strict (pas de `any` implicite).

**Référence pattern** : `containersApi.create` et `containersApi.rename` dans le même fichier (lignes 364-375).

---

### Tâche 3 — Section Image dans `ContainerConfigTab.vue`

**Objectif** : Ajouter une card éditable pour modifier l'image Docker avec recréation.

**Fichier** : [`frontend/src/components/ContainerConfigTab.vue`](frontend/src/components/ContainerConfigTab.vue)

**Actions** :
1. **Template** : Ajouter une nouvelle `<el-card>` après la section Resources (ou avant, selon l'ordre logique) avec :
   - `#header` avec icône + titre "Image" + classe CSS `header-purple`
   - `el-alert type="warning"` : "⚠️ Modifier l'image nécessite de recréer le container. Le layer writable sera perdu."
   - `el-form` avec :
     - `el-input` pré-rempli avec `detail.image` (bindé sur `newImage` ref)
     - `el-checkbox` "Puller la nouvelle image avant recréation" bindé sur `pullImage` ref
     - Hint text sous l'input : "Image actuelle : {detail.image}"
   - Bouton "Mettre à jour l'image" `type="primary"` avec `:loading="loadingRecreate"`
2. **Script** :
   - Ajouter les refs : `newImage = ref('')`, `pullImage = ref(false)`, `loadingRecreate = ref(false)`
   - Dans le `watch` sur `detail`, initialiser `newImage.value = detail.image ?? ''`
   - Créer `async function updateImage()` :
     - Vérifier `props.detail?.id` existe
     - Vérifier que `newImage.value` est non vide et différent de l'image actuelle (optionnel)
     - `ElMessageBox.confirm()` avec message explicitant la recréation et la perte du layer writable
     - Appeler `containersApi.recreate(props.detail.id, { image: newImage.value, pull_image: pullImage.value })`
     - En cas de succès : émettre un event `recreate-success` avec `new_container_id` pour que le parent fasse le redirect
     - `ElMessage.success('Container recréé avec succès')`
     - En cas d'erreur : `ElMessage.error(message)`
     - Gérer `loadingRecreate` dans un `finally`
3. **Style** :
   - Ajouter `.card-config-image :deep(.el-card__header) { border-bottom: 3px solid #9b59b6; }`
   - Ajouter `.header-purple { color: #9b59b6; }`

**Référence pattern** :
- Card + alert warning : `ContainerConfigTab.vue` section env vars (lignes 4-86)
- Appel API + loading + ElMessage : `ContainerConfigTab.vue` `applyRestartPolicy` (lignes 482-501)
- ElMessageBox.confirm : `ContainerConfigTab.vue` `applyEnvVars` (lignes 438-453)

**Sécurité** :
- Validation frontend : l'input image doit être non vide (trim > 0)
- Le endpoint backend valide déjà via Pydantic
- Confirmation utilisateur obligatoire avant toute recréation

---

### Tâche 4 — Section Ports dans `ContainerConfigTab.vue`

**Objectif** : Ajouter une card éditable pour modifier les port bindings avec validation et recréation.

**Fichier** : [`frontend/src/components/ContainerConfigTab.vue`](frontend/src/components/ContainerConfigTab.vue)

**Actions** :
1. **Interface locale** : Ajouter `interface PortBindingRow { hostIp: string; hostPort: string; containerPort: string; protocol: 'tcp' | 'udp' }`
2. **Template** : Ajouter une `<el-card>` avec :
   - `#header` avec icône + titre "Ports" + classe CSS `header-purple`
   - `el-alert type="warning"` : "⚠️ Modifier les ports nécessite de recréer le container."
   - `el-table :data="portBindings"` avec colonnes :
     - Host IP : `el-input` (placeholder "0.0.0.0")
     - Host Port : `el-input-number` `:min="1" :max="65535"`
     - Container Port : `el-input-number` `:min="1" :max="65535"`
     - Protocol : `el-select` avec options `tcp` / `udp`
     - Action : `el-button` 🗑️ pour supprimer la ligne
   - Boutons sous le tableau :
     - "+ Ajouter un port" pour ajouter une ligne vide
     - "Appliquer" `type="primary"` avec `:loading="loadingRecreate"`
3. **Script** :
   - Ajouter `portBindings = ref<PortBindingRow[]>([])`
   - Dans le `watch` sur `detail`, parser `detail.host_config?.port_bindings` (format Docker `{"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}`) vers le tableau de rows
   - Fonction `addPortBinding()` : push une row vide `{ hostIp: '0.0.0.0', hostPort: '', containerPort: '', protocol: 'tcp' }`
   - Fonction `removePortBinding(index: number)`
   - Fonction `validatePortBindings(): string | null` :
     - Vérifier que chaque hostPort et containerPort sont des entiers 1-65535
     - Vérifier qu'il n'y a pas de doublon sur le couple `hostIp:hostPort`
     - Retourner un message d'erreur ou `null` si valide
   - Fonction `buildPortBindingsPayload(): Record<string, Array<{HostIp: string; HostPort: string}>>` :
     - Transformer le tableau de rows vers le format Docker attendu par l'API
     - Ex: `{"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}`
   - `async function applyPortBindings()` :
     - Vérifier `props.detail?.id`
     - Appeler `validatePortBindings()` → si erreur, `ElMessage.error(error)` et return
     - `ElMessageBox.confirm()`
     - Construire le payload avec `buildPortBindingsPayload()`
     - Appeler `containersApi.recreate(props.detail.id, { port_bindings: payload })`
     - Émettre `recreate-success` avec `new_container_id`
     - Messages success/error + loading state
4. **Style** :
   - Ajouter `.card-config-ports :deep(.el-card__header) { border-bottom: 3px solid #9b59b6; }`

**Référence pattern** :
- Table éditable + add/remove : `ContainerConfigTab.vue` env vars (lignes 24-85)
- Validation + formatage payload : adapter selon le format Docker

**Sécurité** :
- Validation frontend stricte des ports (1-65535, entiers)
- Vérification des doublons hostIp:hostPort
- Pas de sanitisation d'IP nécessaire (l'API Docker la gère)
- Confirmation utilisateur obligatoire

---

### Tâche 5 — Émission d'event `recreate-success` et redirect

**Objectif** : Permettre à `ContainerConfigTab` de notifier `ContainerDetail` du changement d'ID après recréation.

**Fichiers** :
- [`frontend/src/components/ContainerConfigTab.vue`](frontend/src/components/ContainerConfigTab.vue)
- [`frontend/src/views/ContainerDetail.vue`](frontend/src/views/ContainerDetail.vue)

**Actions** :
1. Dans `ContainerConfigTab.vue` :
   - Ajouter `const emit = defineEmits<{ (e: 'recreate-success', newId: string): void }>()`
   - Dans `updateImage()` et `applyPortBindings()`, après succès de l'API :
     ```typescript
     emit('recreate-success', response.data.new_container_id)
     ```
2. Dans `ContainerDetail.vue` :
   - Sur `<ContainerConfigTab>`, ajouter `@recreate-success="handleRecreateSuccess"`
   - Ajouter la méthode `handleRecreateSuccess(newId: string)` :
     ```typescript
     function handleRecreateSuccess(newId: string): void {
       router.push(`/containers/${newId}`)
       // Recharger les détails du nouveau container
       loadContainerDetail()
     }
     ```
   - Note : `loadContainerDetail()` utilise `containerId` qui est un computed sur `route.params.id`. Après le `router.push`, il faut potentiellement attendre le changement de route avant d'appeler `loadContainerDetail()`. Utiliser `nextTick()` ou appeler directement après le push si le router est synchrone.

**Référence pattern** :
- Redirect après suppression : `ContainerDetail.vue` `handleDelete` (ligne 859)
- Emission d'events : pattern Vue 3 standard avec `defineEmits`

---

### Tâche 6 — Tests unitaires `ContainerConfigTab.spec.ts`

**Objectif** : Couvrir les nouvelles fonctionnalités Image et Ports avec ≥ 80% de couverture.

**Fichier** : [`frontend/tests/unit/components/ContainerConfigTab.spec.ts`](frontend/tests/unit/components/ContainerConfigTab.spec.ts)

**Actions** :
1. **Mock API** : Ajouter `mockRecreate` dans le mock de `@/services/api`
2. **Tests de rendu** :
   - `should render 6 config cards` (au lieu de 4 actuellement)
   - `should render Image card with correct header`
   - `should render Ports card with correct header`
   - `should render warning alerts for image and ports sections`
3. **Tests pré-remplissage** :
   - `should pre-fill image input from detail.image`
   - `should pre-fill port bindings from detail.host_config.port_bindings`
   - `should handle empty port_bindings`
4. **Tests validation ports** :
   - `should reject host port below 1`
   - `should reject host port above 65535`
   - `should reject container port below 1`
   - `should reject container port above 65535`
   - `should reject duplicate hostIp:hostPort combinations`
5. **Tests interactions Image** :
   - `should call recreate API when updating image`
   - `should include pull_image in recreate payload when checkbox is checked`
   - `should emit recreate-success event with new container id`
   - `should show error message on API failure`
6. **Tests interactions Ports** :
   - `should add a new port binding row`
   - `should remove a port binding row`
   - `should call recreate API with correct port_bindings payload`
   - `should emit recreate-success event after applying ports`
   - `should show validation error for invalid port`
7. **Tests loading state** :
   - `should set loadingRecreate to true during image update`
   - `should set loadingRecreate to true during ports apply`
8. **Tests edge cases** :
   - `should handle null detail gracefully`
   - `should handle detail with no host_config`
   - `should not call API when detail is null`

**Référence pattern** : Le fichier de test existant (lignes 1-454) utilise des stubs ElementPlus et des mocks d'API. Étendre le même pattern.

**Commandes de validation** :
```bash
cd frontend && pnpm test -- tests/unit/components/ContainerConfigTab
```

---

## Tests à écrire

### Frontend — Tests unitaires (`ContainerConfigTab.spec.ts`)

| Cas | Description |
|-----|-------------|
| Rendu initial | 6 cards affichées (env, labels, restart, resources, image, ports) |
| Pré-remplissage image | Input image = `detail.image` au montage |
| Pré-remplissage ports | Tableau ports parsé depuis `host_config.port_bindings` |
| Validation port host | Refusé si < 1 ou > 65535 |
| Validation port container | Refusé si < 1 ou > 65535 |
| Validation doublon | Refusé si couple `hostIp:hostPort` dupliqué |
| Ajout port | Clic "+ Ajouter" → nouvelle ligne vide |
| Suppression port | Clic 🗑️ → ligne supprimée |
| Update image | `ElMessageBox.confirm` → `containersApi.recreate` appelé avec `{ image, pull_image }` |
| Update ports | `ElMessageBox.confirm` → `containersApi.recreate` appelé avec `{ port_bindings }` au format Docker |
| Émission event | `recreate-success` émis avec `new_container_id` après succès |
| Erreur API | `ElMessage.error` affiché si l'API échoue |
| Loading state | Bouton en état `loading` pendant l'appel API |
| Edge case null | Composant ne plante pas si `detail` est null |

### Backend — Tests de sécurité (à vérifier / compléter si besoin)

> Le endpoint `/recreate` existe déjà (STORY-025). Les tests de sécurité suivants doivent être présents ou vérifiés :

| Cas | Test attendu | Statut |
|-----|-------------|--------|
| Accès sans token | `test_recreate_returns_401_without_token` | À vérifier dans `test_docker.py` |
| Body invalide | `test_recreate_returns_422_on_invalid_body` | À vérifier |
| Container inexistant | `test_recreate_returns_404_when_not_found` | À vérifier |
| Rate limiting | `test_recreate_rate_limited` | À vérifier (10/min) |

**Note** : Le endpoint `/recreate` n'injecte pas `get_current_active_user` (contrairement à `/promote`). Si le middleware d'authentification global ne couvre pas cette route, un test `401_without_token` échouera. **Action de vérification** : confirmer que le routeur Docker est monté avec `dependencies=[Depends(get_current_active_user)]` dans `main.py`.

---

## Notes d'implémentation

### Format de parsing des port bindings

Le `host_config.port_bindings` reçu du backend est au format Docker :
```json
{
  "80/tcp": [{ "HostIp": "0.0.0.0", "HostPort": "8080" }],
  "443/tcp": [{ "HostIp": "", "HostPort": "8443" }]
}
```

**Parsing vers rows UI** :
- Clé `"80/tcp"` → `containerPort = "80"`, `protocol = "tcp"`
- `HostIp` peut être `""` → afficher `"0.0.0.0"` par défaut ou laisser vide
- `HostPort` est une string

**Reconstruction vers payload API** :
- Row `{ hostIp: "0.0.0.0", hostPort: "8080", containerPort: "80", protocol: "tcp" }`
- → `"80/tcp": [{ "HostIp": "0.0.0.0", "HostPort": "8080" }]`

### Gestion du redirect

Après recréation, l'ID du container change. Le redirect doit être fait au niveau de la vue parente (`ContainerDetail.vue`) car c'est elle qui possède le `router` et la logique de chargement. Le composant `ContainerConfigTab` émet un event `recreate-success` avec le `new_container_id`.

### Ordre des sections dans l'onglet Config

Proposition d'ordre (cohérent avec l'epic) :
1. Variables d'environnement (gris)
2. Labels (gris)
3. Image (violet)
4. Ports (violet)
5. Restart Policy (orange)
6. Resource Limits (rouge)

### Couleurs thématiques

| Section | Couleur | Classe CSS |
|---------|---------|------------|
| Image | Violet `#9b59b6` | `.header-purple` |
| Ports | Violet `#9b59b6` | `.header-purple` |

Les sections Volumes, Réseaux et Sécurité seront ajoutées par STORY-028, STORY-029 et suivantes.

## Notes d'implémentation

### Changements réalisés

- **Types** : `ContainerRecreateRequest` et `ContainerRecreateResponse` ajoutés dans [`frontend/src/types/api.ts`](frontend/src/types/api.ts) après les types existants.
- **Service API** : Méthode `containersApi.recreate(id, data)` ajoutée dans [`frontend/src/services/api.ts`](frontend/src/services/api.ts), importée et exportée correctement.
- **ContainerConfigTab.vue** :
  - Ajout des sections **Image** et **Ports** (cards violettes avec `.header-purple` et bordure `#9b59b6`).
  - Section Image : input pré-rempli, checkbox `pull_image`, confirmation modale, appel `recreate` avec `{ image, pull_image }`.
  - Section Ports : tableau éditable avec colonnes Host IP / Host Port / Container Port / Protocol / Action, validation 1–65535, anti-doublon `hostIp:hostPort`, conversion vers/from format Docker `{"80/tcp": [{"HostIp": "...", "HostPort": "..."}]}`.
  - Émission de l'event `recreate-success` avec `new_container_id` après succès des deux sections.
  - `loadingRecreate` géré dans un `finally` pour les deux opérations.
- **ContainerDetail.vue** :
  - Écoute de `@recreate-success` sur `<ContainerConfigTab>`.
  - `handleRecreateSuccess(newId)` redirige vers `/containers/${newId}` puis recharge les détails.

### Défis techniques

- **Typage TypeScript** : le champ `containerPort` dans `PortBindingRow` a dû rester en `string` (et non `number | ''`) car il provient du split de la clé Docker `"80/tcp"`. Le `hostPort` reste `number | ''` pour fonctionner avec `<el-input-number>`.
- **Mock ElMessageBox** dans les tests : les tests appelant `updateImage()` ou `applyPortBindings()` bloquaient sur la confirmation modale. Résolu en mockant `ElMessageBox.confirm` via `vi.spyOn` avant l'import du composant.

### Validation

- `pnpm build` : ✅ (vue-tsc + vite build passent, 0 erreurs liées à nos changements)
- `pnpm lint` : ✅ (0 nouvelles erreurs, 0 nouveaux warnings)
- `pnpm test -- tests/unit/components/ContainerConfigTab` : ✅ 55 tests passent
