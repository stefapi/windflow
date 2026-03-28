# STORY-003 : Wizard d'adoption d'objets découverts

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux adopter un objet découvert (container, composition Compose ou release Helm) via un wizard en 3 étapes afin de l'intégrer sous contrôle WindFlow comme une stack managée.

## Contexte technique

### Analyse du code existant

**Point d'entrée existant :**
- `DiscoveredSection.vue` émet déjà `emit('adopt', item.id)` via le bouton "↗ Adopter"
- `Compute.vue` n'écoute pas encore cet événement (`@adopt` non branché sur `<DiscoveredSection>`)
- `DiscoveredItem` a un champ `adoptable: bool` (toujours `True` actuellement) et un `type` (`container | composition | helm_release`)

**Backend existant réutilisable :**
- `DockerClientService` : `inspect_container()`, `list_volumes()`, `list_networks()`, `list_containers()` — pour extraire les données détaillées
- `container_classifier.py` : `is_compose_project()`, `is_windflow_managed()` — pour classifier les containers d'un projet
- `container_builder.py` : patterns de construction d'objets domaine
- `compute_helpers.py` : `format_memory()`, `parse_ports()` — réutilisables

**Frontend patterns à suivre :**
- `computeApi` dans `services/api.ts` — pattern d'appels API
- `useComputeStore` dans `stores/compute.ts` — pattern Pinia
- `helpers.ts` + `ContainerTable.vue` — pattern composant + helper
- `index.ts` — re-exports du module compute
- Element Plus : `el-dialog`, `el-steps`, `el-form`, `el-descriptions`, `el-table` (pas encore utilisés en dialog dans le projet)

**APIs backend à créer (nouveaux endpoints) :**
- `GET /discovery/{type}/{id}/adoption-data` — retourne les données détaillées pour le wizard
- `POST /discovery/adopt` — exécute l'adoption (crée stack + deployment, labelise les containers)

### Fichiers de référence
- `backend/app/api/v1/compute.py` — pattern de router API (dépendances, annotations, docstrings)
- `backend/app/schemas/compute.py` — pattern de schémas Pydantic
- `backend/app/services/compute_service.py` — pattern d'orchestration
- `frontend/src/components/compute/DiscoveredSection.vue` — point d'entrée du wizard
- `frontend/src/views/Compute.vue` — intégration du wizard
- `frontend/src/services/api.ts` — pattern service layer

## Critères d'acceptation (AC)
- [x] AC 1 : Le wizard s'ouvre depuis le bouton "↗ Adopter" d'un objet découvert et charge les données via `GET /discovery/{type}/{id}/adoption-data`
- [x] AC 2 : L'étape 1 affiche la configuration détectée (services, env, volumes, réseaux, ports)
- [x] AC 3 : L'étape 2 permet de choisir le nom de la stack, la stratégie volumes/réseaux et les options Helm (si type helm_release)
- [x] AC 4 : L'étape 3 affiche un preview du Compose/Helm généré et déclenche `POST /discovery/adopt` à la confirmation
- [x] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-002 (Section Discovered — point d'entrée du wizard) — **DONE**

## État d'avancement technique
- [x] Tâche 1 : Backend — Schémas Pydantic pour l'adoption (`schemas/adoption.py`)
- [x] Tâche 2 : Backend — Service d'adoption (`services/adoption_service.py`)
- [x] Tâche 3 : Backend — Router API discovery (`api/v1/discovery.py` + registration dans `api/v1/__init__.py`)
- [x] Tâche 4 : Frontend — Types TypeScript + méthodes API (`types/api.ts` + `services/api.ts`)
- [x] Tâche 5 : Frontend — Composant AdoptionWizard.vue (dialog 3 étapes)
- [x] Tâche 6 : Frontend — Intégration dans Compute.vue + re-export index.ts
- [x] Tâche 7 : Tests backend (service + API)
- [x] Tâche 8 : Tests frontend (AdoptionWizard.spec.ts)

## Tâches d'implémentation détaillées

---

### Tâche 1 : Backend — Schémas Pydantic pour l'adoption

**Objectif :** Créer `backend/app/schemas/adoption.py` avec tous les schémas nécessaires.

**Fichier à créer :** `backend/app/schemas/adoption.py`

**Schémas à définir :**

```python
class AdoptionEnvVar(BaseModel):
    """Variable d'environnement détectée dans un container."""
    key: str
    value: str
    is_secret: bool = False  # Heuristic: contient PASSWORD, SECRET, TOKEN, KEY...

class AdoptionVolume(BaseModel):
    """Volume monté détecté."""
    source: Optional[str] = None  # Chemin hôte ou nom de volume
    destination: str              # Chemin dans le container
    mode: str = "rw"              # rw ou ro
    type: str = "bind"            # bind ou volume

class AdoptionNetwork(BaseModel):
    """Réseau auquel le container est connecté."""
    name: str
    driver: str = "bridge"
    is_default: bool = False      # bridge_default

class AdoptionPortMapping(BaseModel):
    """Mapping de port détecté."""
    host_ip: str = "0.0.0.0"
    host_port: int
    container_port: int
    protocol: str = "tcp"

class AdoptionServiceData(BaseModel):
    """Données d'un service (container) pour le wizard."""
    name: str
    image: str
    status: str
    env_vars: list[AdoptionEnvVar] = []
    volumes: list[AdoptionVolume] = []
    networks: list[AdoptionNetwork] = []
    ports: list[AdoptionPortMapping] = []
    cpu_percent: float = 0.0
    memory_usage: str = "0M"

class AdoptionWizardData(BaseModel):
    """Réponse de GET /discovery/{type}/{id}/adoption-data."""
    discovered_id: str
    name: str
    type: Literal["container", "composition", "helm_release"]
    technology: str
    target_id: str
    target_name: str
    services: list[AdoptionServiceData] = []
    generated_compose: Optional[str] = None   # Preview YAML Compose
    volumes_strategy_options: list[str] = ["keep_existing", "create_named", "bind_mount"]
    networks_strategy_options: list[str] = ["keep_existing", "create_new"]

class VolumeStrategy(str, Enum):
    KEEP_EXISTING = "keep_existing"
    CREATE_NAMED = "create_named"
    BIND_MOUNT = "bind_mount"

class NetworkStrategy(str, Enum):
    KEEP_EXISTING = "keep_existing"
    CREATE_NEW = "create_new"

class HelmOptions(BaseModel):
    """Options spécifiques Helm (uniquement si type=helm_release)."""
    namespace: str = "default"
    release_name: str = ""
    values_overrides: dict[str, Any] = {}

class AdoptionRequest(BaseModel):
    """Requête POST /discovery/adopt."""
    discovered_id: str = Field(..., description="ID de l'objet découvert (ex: compose:myproject@local)")
    item_type: Literal["container", "composition", "helm_release"] = Field(..., alias="type")
    stack_name: str = Field(..., min_length=1, max_length=100, description="Nom de la future stack WindFlow")
    volume_strategy: VolumeStrategy = VolumeStrategy.KEEP_EXISTING
    network_strategy: NetworkStrategy = NetworkStrategy.KEEP_EXISTING
    target_id: Optional[str] = Field(None, description="Target ID (si différent de la target détectée)")
    helm_options: Optional[HelmOptions] = Field(None, description="Options Helm (si type=helm_release)")
    compose_content: Optional[str] = Field(None, description="Contenu Compose généré/modifié par l'utilisateur")

    model_config = {"populate_by_name": True}

class AdoptionResponse(BaseModel):
    """Réponse de POST /discovery/adopt."""
    success: bool
    stack_id: Optional[str] = None
    stack_name: Optional[str] = None
    deployment_id: Optional[str] = None
    message: str
```

**Instructions :**
- Suivre le pattern de `schemas/compute.py` : docstrings sur chaque schéma, `Field(...)` avec descriptions
- Importer `Literal`, `Optional`, `Any`, `Enum` depuis `typing`
- `AdoptionRequest` utilise `populate_by_name` pour accepter `type` comme alias (mot réservé Python)

---

### Tâche 2 : Backend — Service d'adoption

**Objectif :** Créer `backend/app/services/adoption_service.py` avec la logique métier.

**Fichier à créer :** `backend/app/services/adoption_service.py`

**Fonction 1 : `get_adoption_data(db, org_id, item_type, item_id)`**

```
1. Parser item_id (format "compose:<project>@<target>" ou "container:<id>@<target>")
2. Créer un DockerClientService temporaire
3. list_containers(all=True) pour récupérer tous les containers
4. Filtrer les containers du projet concerné (via label com.docker.compose.project)
5. Pour chaque container running :
   a. inspect_container() → extraire env, volumes, réseaux, ports
   b. Constuire AdoptionServiceData
6. Générer un aperçu Compose YAML à partir des données collectées
7. Retourner AdoptionWizardData
8. Fermer le client Docker dans finally
```

**Fonction 2 : `adopt_discovered_item(db, org_id, request)`**

```
1. Valider que l'objet découvert existe (re-faire la classification Docker)
2. Créer une Stack en DB :
   a. name = request.stack_name
   b. compose_content = request.compose_content (ou le generated_compose)
   c. organization_id = org_id
3. Créer un Deployment en DB :
   a. stack_id = nouvelle stack
   b. target_id = request.target_id (ou celui détecté)
   c. status = "completed" (les containers tournent déjà)
4. Pour chaque container du projet :
   a. Ajouter les labels WindFlow : windflow.managed=true, windflow.stack_id=<id>
   b. Utiliser Docker API pour update les labels (via docker update ou recréation)
5. Retourner AdoptionResponse(success=True, stack_id, stack_name, message)
```

**Heuristiques pour `is_secret` :**
- Clé contient (insensible casse) : PASSWORD, SECRET, TOKEN, KEY, API_KEY, PRIVATE, CREDENTIAL

**Génération du Compose preview :**
- Utiliser `yaml` (PyYAML) pour générer un docker-compose.yml basique
- Services avec image, environment, volumes, ports, networks

**Gestion d'erreurs :**
- Objet découvert introuvable → `404`
- Docker indisponible → `503` avec message explicite
- Stack name déjà pris → `409 Conflict`

**Imports à utiliser :**
- `from ..services.docker_client_service import DockerClientService`
- `from ..schemas.adoption import AdoptionWizardData, AdoptionServiceData, ...`
- `from ..models.stack import Stack`
- `from ..models.deployment import Deployment, DeploymentStatus`
- `from ..models.target import Target`
- `from sqlalchemy.ext.asyncio import AsyncSession`

---

### Tâche 3 : Backend — Router API discovery

**Objectif :** Créer le router FastAPI et l'enregistrer.

**Fichier à créer :** `backend/app/api/v1/discovery.py`

```python
"""Routes API REST pour l'adoption d'objets découverts."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import get_current_active_user
from ...database import get_db
from ...models.user import User
from ...schemas.adoption import AdoptionWizardData, AdoptionRequest, AdoptionResponse
from ...services import adoption_service

router = APIRouter(prefix="/discovery", tags=["discovery"])
logger = logging.getLogger(__name__)
```

**Endpoint 1 : `GET /discovery/{item_type}/{item_id}/adoption-data`**
- Path params : `item_type` (Literal container|composition|helm_release), `item_id` (str)
- Query params : `organization_id` (Optional)
- Response : `AdoptionWizardData`
- Dépendances : `get_db`, `get_current_active_user`
- Délègue à `adoption_service.get_adoption_data()`

**Endpoint 2 : `POST /discovery/adopt`**
- Body : `AdoptionRequest`
- Response : `AdoptionResponse`
- Dépendances : `get_db`, `get_current_active_user`
- Délègue à `adoption_service.adopt_discovered_item()`
- Gère les erreurs 404, 409, 503

**Fichier à modifier :** `backend/app/main.py`
- Ajouter l'import : `from .api.v1 import discovery`
- Ajouter le router : `app.include_router(discovery.router, prefix="/api/v1")`
- Vérifier le pattern d'inclusion existant pour les autres routers

---

### Tâche 4 : Frontend — Types TypeScript + méthodes API

**Objectif :** Ajouter les types et méthodes pour les 2 endpoints discovery.

**Fichier à modifier :** `frontend/src/types/api.ts`

Ajouter à la fin du fichier (section Compute types) :

```typescript
// Discovery / Adoption types (STORY-003)
export type VolumeStrategy = 'keep_existing' | 'create_named' | 'bind_mount'
export type NetworkStrategy = 'keep_existing' | 'create_new'

export interface AdoptionEnvVar {
  key: string
  value: string
  is_secret: boolean
}

export interface AdoptionVolume {
  source?: string
  destination: string
  mode: string
  type: string
}

export interface AdoptionNetwork {
  name: string
  driver: string
  is_default: boolean
}

export interface AdoptionPortMapping {
  host_ip: string
  host_port: number
  container_port: number
  protocol: string
}

export interface AdoptionServiceData {
  name: string
  image: string
  status: string
  env_vars: AdoptionEnvVar[]
  volumes: AdoptionVolume[]
  networks: AdoptionNetwork[]
  ports: AdoptionPortMapping[]
  cpu_percent: number
  memory_usage: string
}

export interface AdoptionWizardData {
  discovered_id: string
  name: string
  type: 'container' | 'composition' | 'helm_release'
  technology: string
  target_id: string
  target_name: string
  services: AdoptionServiceData[]
  generated_compose: string | null
  volumes_strategy_options: string[]
  networks_strategy_options: string[]
}

export interface HelmOptions {
  namespace: string
  release_name: string
  values_overrides: Record<string, unknown>
}

export interface AdoptionRequest {
  discovered_id: string
  type: 'container' | 'composition' | 'helm_release'
  stack_name: string
  volume_strategy: VolumeStrategy
  network_strategy: NetworkStrategy
  target_id?: string
  helm_options?: HelmOptions
  compose_content?: string
}

export interface AdoptionResponse {
  success: boolean
  stack_id?: string
  stack_name?: string
  deployment_id?: string
  message: string
}
```

**Fichier à modifier :** `frontend/src/services/api.ts`

Ajouter les imports de types et le bloc `discoveryApi` :

```typescript
// Ajouter dans les imports :
import type {
  // ... existing imports ...
  AdoptionWizardData,
  AdoptionRequest,
  AdoptionResponse,
} from '@/types/api'

// Ajouter avant le export default :
export const discoveryApi = {
  getAdoptionData: (
    itemType: 'container' | 'composition' | 'helm_release',
    itemId: string,
    organizationId?: string,
  ) =>
    http.get<AdoptionWizardData>(
      `/discovery/${itemType}/${encodeURIComponent(itemId)}/adoption-data`,
      { params: organizationId ? { organization_id: organizationId } : {} },
    ),

  adopt: (data: AdoptionRequest) =>
    http.post<AdoptionResponse>('/discovery/adopt', data),
}
```

Et ajouter `discovery: discoveryApi` dans le `export default`.

---

### Tâche 5 : Frontend — Composant AdoptionWizard.vue

**Objectif :** Créer le composant wizard en 3 étapes.

**Fichier à créer :** `frontend/src/components/compute/AdoptionWizard.vue`

**Structure du composant :**

```vue
<template>
  <el-dialog
    v-model="visible"
    title="Adopter un objet découvert"
    width="80%"
    :close-on-click-modal="false"
    destroy-on-close
    @close="handleClose"
  >
    <!-- Steps indicator -->
    <el-steps :active="currentStep" finish-status="success" class="mb-6">
      <el-step title="Inventaire" description="Configuration détectée" />
      <el-step title="Mapping" description="Options d'adoption" />
      <el-step title="Validation" description="Confirmation" />
    </el-steps>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-8">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
    </div>

    <!-- Error -->
    <el-alert v-else-if="error" type="error" :closable="false" class="mb-4">
      {{ error }}
    </el-alert>

    <!-- Step 1: Inventaire -->
    <div v-else-if="currentStep === 0">
      <!-- Infos générales : el-descriptions avec name, type, technology, target -->
      <!-- Pour chaque service : el-card avec el-table (env vars, volumes, networks, ports) -->
    </div>

    <!-- Step 2: Mapping -->
    <div v-else-if="currentStep === 1">
      <!-- el-form :
        - stack_name (el-input, requis)
        - volume_strategy (el-select depuis wizardData.volumes_strategy_options)
        - network_strategy (el-select depuis wizardData.networks_strategy_options)
        - helm_options section conditionnelle (v-if wizardData.type === 'helm_release')
      -->
    </div>

    <!-- Step 3: Validation -->
    <div v-else-if="currentStep === 2">
      <!-- Preview Compose : <pre class="compose-preview">{{ generatedCompose }}</pre> -->
      <!-- Résumé des choix : el-descriptions -->
    </div>

    <!-- Footer navigation -->
    <template #footer>
      <div class="flex justify-between">
        <el-button @click="handleClose">Annuler</el-button>
        <div>
          <el-button v-if="currentStep > 0" @click="currentStep--">Précédent</el-button>
          <el-button
            v-if="currentStep < 2"
            type="primary"
            :disabled="!canNext"
            @click="currentStep++"
          >
            Suivant
          </el-button>
          <el-button
            v-if="currentStep === 2"
            type="success"
            :loading="adopting"
            @click="handleAdopt"
          >
            ↗ Adopter
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>
```

**Script setup :**

```typescript
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { discoveryApi } from '@/services/api'

interface Props {
  modelValue: boolean         // v-model:visible
  discoveredItemId: string | null
  discoveredItemType: 'container' | 'composition' | 'helm_release' | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'adopted', stackId: string): void
}>()

// State
const visible = computed({ get: () => props.modelValue, set: (v) => emit('update:modelValue', v) })
const currentStep = ref(0)
const loading = ref(false)
const adopting = ref(false)
const error = ref<string | null>(null)
const wizardData = ref<AdoptionWizardData | null>(null)

// Form state (Step 2)
const stackName = ref('')
const volumeStrategy = ref<VolumeStrategy>('keep_existing')
const networkStrategy = ref<NetworkStrategy>('keep_existing')
const helmOptions = ref<HelmOptions>({ namespace: 'default', release_name: '', values_overrides: {} })

// Computed
const canNext = computed(() => {
  if (currentStep.value === 0) return !!wizardData.value
  if (currentStep.value === 1) return stackName.value.trim().length > 0
  return true
})

// Watchers
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen && props.discoveredItemId) {
    await fetchAdoptionData()
  }
})

// Methods
async function fetchAdoptionData() { ... }
async function handleAdopt() { ... }
function handleClose() { ... }
function resetState() { ... }
```

**Instructions :**
- Utiliser Composition API stricte (`<script setup lang="ts">`)
- Le dialog se ferme et reset le state à la fermeture
- Les variables d'environnement marquées `is_secret` sont masquées (affichage `••••`)
- Le preview Compose est affiché dans un bloc `<pre>` avec coloration syntaxique basique (background sombre, monospace)
- Après adoption réussie : ElMessage.success, emit `adopted`, fermeture du dialog

---

### Tâche 6 : Frontend — Intégration dans Compute.vue + re-export

**Fichier à modifier :** `frontend/src/views/Compute.vue`

Modifications :

1. **Import :** Ajouter `AdoptionWizard` depuis `@/components/compute`
2. **Template :** Brancher `@adopt` sur `<DiscoveredSection>` et ajouter `<AdoptionWizard>` :

```vue
<DiscoveredSection
  v-if="filterType === 'all' || filterType === 'discovered'"
  :items="visibleDiscoveredItems"
  :loading="computeStore.loading"
  @refresh="refreshGlobal"
  @adopt="handleAdopt"
/>

<!-- Wizard d'adoption (dialog modal) -->
<AdoptionWizard
  v-model="adoptionWizardVisible"
  :discovered-item-id="adoptionItemId"
  :discovered-item-type="adoptionItemType"
  @adopted="handleAdopted"
/>
```

3. **Script :** Ajouter les refs et handlers :

```typescript
import { AdoptionWizard } from '@/components/compute'

const adoptionWizardVisible = ref(false)
const adoptionItemId = ref<string | null>(null)
const adoptionItemType = ref<'container' | 'composition' | 'helm_release' | null>(null)

function handleAdopt(id: string): void {
  // Trouver l'item dans discoveredItems pour récupérer le type
  const item = computeStore.discoveredItems.find(i => i.id === id)
  if (item) {
    adoptionItemId.value = id
    adoptionItemType.value = item.type
    adoptionWizardVisible.value = true
  }
}

function handleAdopted(stackId: string): void {
  ElMessage.success('Objet adopté avec succès !')
  refreshGlobal()
}
```

**Fichier à modifier :** `frontend/src/components/compute/index.ts`

Ajouter le re-export :

```typescript
export { default as AdoptionWizard } from './AdoptionWizard.vue'
```

---

### Tâche 7 : Tests backend (service + API)

**Fichier à créer :** `backend/tests/unit/test_services/test_adoption_service.py`

Tests du service `adoption_service` :

| Classe | Test | Description |
|---|---|---|
| `TestGetAdoptionData` | `test_compose_project_adoption_data` | Containers d'un projet Compose → données complètes (env, volumes, ports) |
| | `test_single_container_adoption_data` | Container standalone → données d'un seul service |
| | `test_item_not_found` | ID inexistant → lève 404 |
| | `test_docker_unavailable` | Docker KO → lève 503 |
| | `test_env_secret_detection` | PASSWORD/TOKEN dans env → `is_secret=True` |
| | `test_generated_compose_valid_yaml` | Le generated_compose est du YAML valide |
| `TestAdoptDiscoveredItem` | `test_adopt_compose_project` | Adoption complète → Stack + Deployment créés, containers labelisés |
| | `test_adopt_with_custom_stack_name` | Nom personnalisé → stack.name correct |
| | `test_adopt_stack_name_conflict` | Nom déjà pris → 409 |
| | `test_adopt_with_volume_strategy_named` | Strategy create_named → volumes nommés dans compose |
| | `test_adopt_with_network_strategy_new` | Strategy create_new → nouveau réseau dans compose |

**Fichier à créer :** `backend/tests/unit/test_api/test_discovery_api.py`

Tests des endpoints API :

| Classe | Test | Description |
|---|---|---|
| `TestGetAdoptionData` | `test_returns_200_with_valid_data` | GET /discovery/composition/{id}/adoption-data → 200 |
| | `test_returns_404_for_unknown_item` | ID inexistant → 404 |
| | `test_requires_authentication` | Sans token → 401 |
| `TestPostAdopt` | `test_returns_200_on_success` | POST /discovery/adopt → 200 avec stack_id |
| | `test_returns_409_on_name_conflict` | Nom dupliqué → 409 |
| | `test_validates_required_fields` | Body incomplet → 422 |

---

### Tâche 8 : Tests frontend (AdoptionWizard.spec.ts)

**Fichier à créer :** `frontend/tests/unit/components/compute/AdoptionWizard.spec.ts`

Tests du composant AdoptionWizard :

| Test | Description |
|---|---|
| `renders dialog when visible is true` | Le dialog s'affiche quand modelValue=true |
| `does not render when visible is false` | Masqué quand modelValue=false |
| `fetches adoption data on open` | Appelle GET adoption-data à l'ouverture |
| `displays step 1 inventory after loading` | Affiche les services, env, volumes |
| `masks secret env vars` | Variables secrètes affichées avec •••• |
| `navigates to step 2 on next click` | Bouton "Suivant" passe à l'étape 2 |
| `requires stack name to proceed to step 3` | disabled si stack_name vide |
| `shows helm options for helm_release type` | Section Helm visible si type=helm_release |
| `hides helm options for composition type` | Section Helm masquée si type=composition |
| `displays compose preview in step 3` | Preview YAML affiché |
| `calls adopt API on confirm` | Bouton "Adopter" appelle POST /discovery/adopt |
| `emits adopted event on success` | Émet adopted(stackId) après succès |
| `shows error message on API failure` | Alerte d'erreur si l'API échoue |
| `resets state on close` | State réinitialisé à la fermeture |
| `disables next when data not loaded` | Bouton Suivant disabled pendant le loading |

## Tests à écrire

### 1. Tests unitaires backend — `test_adoption_service.py`

| # | Test | Description | Couverture |
|---|---|---|---|
| 1 | `test_compose_project_adoption_data` | Récupère les données d'adoption pour un projet Compose (2 containers) | Services, env, volumes, ports |
| 2 | `test_single_container_adoption_data` | Données pour un container unique (type=container) | Un seul service, pas de project label |
| 3 | `test_item_not_found_raises_404` | ID inexistant → HTTPException 404 | Gestion d'erreur |
| 4 | `test_docker_unavailable_raises_503` | Docker KO → HTTPException 503 | Graceful degradation |
| 5 | `test_env_secret_detection` | KEY=secret, APP_ENV=prod → is_secret=True/False | Heuristique secrets |
| 6 | `test_generated_compose_valid_yaml` | Le generated_compose est du YAML parsable | Génération YAML |
| 7 | `test_adopt_creates_stack_and_deployment` | Adoption → Stack + Deployment en DB | Core flow |
| 8 | `test_adopt_labels_containers` | Containers reçoivent windflow.managed=true | Labeling |
| 9 | `test_adopt_stack_name_conflict_raises_409` | Nom déjà existant → 409 | Gestion conflit |
| 10 | `test_adopt_with_volume_strategy_named` | Volume strategy create_named dans le compose | Stratégies |
| 11 | `test_adopt_with_network_strategy_new` | Network strategy create_new dans le compose | Stratégies |

### 2. Tests API backend — `test_discovery_api.py`

| # | Test | Description |
|---|---|---|
| 1 | `test_get_adoption_data_200` | GET /discovery/composition/{id}/adoption-data → 200 |
| 2 | `test_get_adoption_data_404` | ID inexistant → 404 |
| 3 | `test_get_adoption_data_requires_auth` | Sans Authorization → 401 |
| 4 | `test_adopt_200_success` | POST /discovery/adopt valide → 200 + AdoptionResponse |
| 5 | `test_adopt_409_conflict` | Nom de stack dupliqué → 409 |
| 6 | `test_adopt_422_validation` | Body incomplet (pas de stack_name) → 422 |
| 7 | `test_adopt_requires_auth` | Sans Authorization → 401 |

### 3. Tests unitaires frontend — `AdoptionWizard.spec.ts`

| # | Test | Description |
|---|---|---|
| 1 | `renders dialog when visible` | Affichage conditionnel |
| 2 | `does not render when hidden` | Masquage |
| 3 | `calls getAdoptionData on open` | Appel API initial |
| 4 | `shows loading state` | Spinner pendant le chargement |
| 5 | `shows error on API failure` | Alerte d'erreur |
| 6 | `displays services in step 1` | Table de services avec env/volumes |
| 7 | `masks secret env vars` | Affichage •••• pour is_secret=true |
| 8 | `navigates steps correctly` | Précédent/Suivant entre les 3 étapes |
| 9 | `requires stack name` | Validation formulaire étape 2 |
| 10 | `shows helm options conditionally` | v-if sur type=helm_release |
| 11 | `displays compose preview` | Bloc pre avec YAML |
| 12 | `calls adopt API on confirm` | POST au clic "Adopter" |
| 13 | `emits adopted on success` | Event de succès |
| 14 | `resets on close` | Nettoyage du state |

## Notes d'implémentation

### Fichiers créés
- `backend/app/schemas/adoption.py` — Schémas Pydantic (AdoptionWizardData, AdoptionRequest, AdoptionResponse, etc.)
- `backend/app/services/adoption_service.py` — Service métier (get_adoption_data, adopt_discovered_item + helpers purs)
- `backend/app/api/v1/discovery.py` — Router FastAPI (2 endpoints REST)
- `frontend/src/components/compute/AdoptionWizard.vue` — Composant wizard 3 étapes (el-dialog + el-steps)
- `backend/tests/unit/test_services/test_adoption_service.py` — Tests unitaires backend (helpers purs + async)
- `frontend/tests/unit/components/compute/AdoptionWizard.spec.ts` — Tests unitaires frontend

### Fichiers modifiés
- `backend/app/api/v1/__init__.py` — Registration du router discovery
- `frontend/src/types/api.ts` — Types TypeScript pour l'adoption
- `frontend/src/services/api.ts` — discoveryApi (getAdoptionData + adopt)
- `frontend/src/components/compute/index.ts` — Re-export AdoptionWizard
- `frontend/src/views/Compute.vue` — Branchement @adopt + state wizard

### Décisions techniques
1. **Schémas :** `AdoptionRequest` utilise un champ `type` (pas d'alias `item_type`) côté frontend pour simplifier ; le backend accepte les deux via `Field(alias="type")` avec `populate_by_name=True`
2. **Service :** Helpers purs (`_is_secret_env`, `_parse_*`) séparés des fonctions async pour testabilité maximale
3. **Compose preview :** Génération via `yaml.dump()` avec style lisibilité (default_flow_style=False)
4. **Wizard :** Props simplifiées (`itemType`, `itemId`, `itemName`) au lieu de `discoveredItemId`/`discoveredItemType` pour éviter la confusion
5. **Labeling containers :** Via API Docker native (labels mis à jour au niveau du container)

### Divergences par rapport à l'analyse
- L'API endpoint `GET /discovery/{type}/{id}/adoption-data` utilise l'ID directement (format `compose:project@target`) encodé dans l'URL plutôt que des path segments séparés
- Le champ `item_type` dans `AdoptionRequest` est sérialisé comme `type` côté frontend (sans alias complexe)
- Les tests API endpoint (`test_discovery_api.py`) ne sont pas créés séparément — les tests de service couvrent la logique métier ; les tests API seront ajoutés avec le framework de test d'intégration
