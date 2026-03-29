<template>
  <el-dialog
    v-model="visible"
    :title="wizardTitle"
    width="900px"
    :close-on-click-modal="false"
    :close-on-press-escape="!loading"
    @close="handleClose"
  >
    <!-- Steps indicator -->
    <el-steps
      :active="currentStep"
      finish-status="success"
      align-center
      class="wizard-steps"
    >
      <el-step
        title="Services détectés"
        description="Inventaire"
      />
      <el-step
        title="Options d'adoption"
        description="Configuration"
      />
      <el-step
        title="Confirmation"
        description="Valider"
      />
    </el-steps>

    <div
      v-loading="loading"
      class="wizard-content"
    >
      <!-- Erreur -->
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        closable
        class="wizard-error"
        @close="error = ''"
      />

      <!-- Étape 1 : Inventaire des services -->
      <div
        v-if="currentStep === 0"
        class="step-content"
      >
        <h3>Services détectés ({{ services.length }})</h3>
        <el-table
          :data="services"
          border
          stripe
          max-height="400"
        >
          <el-table-column
            prop="name"
            label="Service"
            min-width="120"
          />
          <el-table-column
            prop="image"
            label="Image"
            min-width="150"
          />
          <el-table-column
            prop="status"
            label="État"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'running' ? 'success' : 'info'"
                size="small"
              >
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Env"
            width="80"
            align="center"
          >
            <template #default="{ row }">
              {{ row.env_vars.length }}
            </template>
          </el-table-column>
          <el-table-column
            label="Volumes"
            width="80"
            align="center"
          >
            <template #default="{ row }">
              {{ row.volumes.length }}
            </template>
          </el-table-column>
          <el-table-column
            label="Ports"
            width="80"
            align="center"
          >
            <template #default="{ row }">
              {{ row.ports.length }}
            </template>
          </el-table-column>
        </el-table>

        <!-- Aperçu Compose -->
        <div
          v-if="wizardData?.generated_compose"
          class="compose-preview"
        >
          <el-collapse>
            <el-collapse-item
              title="Aperçu docker-compose.yml"
              name="compose"
            >
              <pre class="compose-code">{{ wizardData.generated_compose }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- Étape 2 : Options d'adoption -->
      <div
        v-if="currentStep === 1"
        class="step-content"
      >
        <h3>Configuration de l'adoption</h3>

        <el-form
          :model="form"
          label-width="180px"
          label-position="top"
        >
          <!-- Nom de la stack -->
          <el-form-item
            label="Nom de la future stack"
            required
          >
            <el-input
              v-model="form.stack_name"
              placeholder="my-adopted-stack"
              :maxlength="100"
              show-word-limit
            />
          </el-form-item>

          <!-- Cible -->
          <el-form-item label="Target">
            <el-input
              :model-value="wizardData?.target_name ?? ''"
              disabled
            />
          </el-form-item>

          <!-- Stratégie volumes -->
          <el-form-item label="Stratégie pour les volumes">
            <el-select
              v-model="form.volume_strategy"
              style="width: 100%"
            >
              <el-option
                v-for="opt in volumeStrategyOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>

          <!-- Stratégie réseaux -->
          <el-form-item label="Stratégie pour les réseaux">
            <el-select
              v-model="form.network_strategy"
              style="width: 100%"
            >
              <el-option
                v-for="opt in networkStrategyOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <!-- Étape 3 : Confirmation -->
      <div
        v-if="currentStep === 2"
        class="step-content"
      >
        <h3>Récapitulatif</h3>

        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="Type">
            <el-tag size="small">
              {{ wizardData?.type }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Technologie">
            {{ wizardData?.technology }}
          </el-descriptions-item>
          <el-descriptions-item label="Nom stack">
            <strong>{{ form.stack_name }}</strong>
          </el-descriptions-item>
          <el-descriptions-item label="Target">
            {{ wizardData?.target_name }}
          </el-descriptions-item>
          <el-descriptions-item label="Services">
            {{ services.length }}
          </el-descriptions-item>
          <el-descriptions-item label="Volumes">
            {{ totalVolumes }} — stratégie : {{ volumeStrategyLabel }}
          </el-descriptions-item>
          <el-descriptions-item label="Réseaux">
            {{ totalNetworks }} — stratégie : {{ networkStrategyLabel }}
          </el-descriptions-item>
          <el-descriptions-item label="Ports">
            {{ totalPorts }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- Succès -->
        <el-result
          v-if="adoptionResult?.success"
          icon="success"
          title="Adoption réussie !"
          :sub-title="adoptionResult.message"
        />
      </div>
    </div>

    <!-- Footer -->
    <template #footer>
      <div class="wizard-footer">
        <el-button
          v-if="currentStep > 0 && !adoptionResult?.success"
          @click="prevStep"
        >
          Précédent
        </el-button>
        <el-button @click="handleClose">
          {{ adoptionResult?.success ? 'Fermer' : 'Annuler' }}
        </el-button>
        <el-button
          v-if="currentStep === 0"
          type="primary"
          :disabled="services.length === 0"
          @click="nextStep"
        >
          Suivant
        </el-button>
        <el-button
          v-if="currentStep === 1"
          type="primary"
          :disabled="!form.stack_name"
          @click="nextStep"
        >
          Suivant
        </el-button>
        <el-button
          v-if="currentStep === 2 && !adoptionResult?.success"
          type="success"
          :loading="adopting"
          @click="handleAdopt"
        >
          Confirmer l'adoption
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { discoveryApi } from '@/services/api'
import type {
  AdoptionWizardData,
  AdoptionServiceData,
  AdoptionRequest,
  AdoptionResponse,
  VolumeStrategy,
  NetworkStrategy,
} from '@/types/api'

// ---------------------------------------------------------------------------
// Props & Emits
// ---------------------------------------------------------------------------

const props = defineProps<{
  /** v-model pour la visibilité du dialog */
  modelValue: boolean
  /** Type d'objet (container, composition, helm_release) */
  itemType: 'container' | 'composition' | 'helm_release'
  /** ID de l'objet découvert (ex: compose:myproject@local) */
  itemId: string
  /** Nom affiché de l'objet */
  itemName: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'adopted', response: AdoptionResponse): void
}>()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const currentStep = ref(0)
const loading = ref(false)
const adopting = ref(false)
const error = ref('')
const wizardData = ref<AdoptionWizardData | null>(null)
const adoptionResult = ref<AdoptionResponse | null>(null)

const form = ref({
  stack_name: '',
  volume_strategy: 'keep_existing' as VolumeStrategy,
  network_strategy: 'keep_existing' as NetworkStrategy,
})

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const services = computed<AdoptionServiceData[]>(() => wizardData.value?.services ?? [])

const wizardTitle = computed(() => {
  const stepLabels = ['Inventaire des services', 'Options d\'adoption', 'Confirmation']
  return `Adopter : ${props.itemName} — ${stepLabels[currentStep.value]}`
})

const volumeStrategyOptions = [
  { value: 'keep_existing', label: 'Conserver les volumes existants' },
  { value: 'create_named', label: 'Créer des volumes nommés' },
  { value: 'bind_mount', label: 'Utiliser des bind mounts' },
]

const networkStrategyOptions = [
  { value: 'keep_existing', label: 'Conserver les réseaux existants' },
  { value: 'create_new', label: 'Créer de nouveaux réseaux' },
]

const totalVolumes = computed(() =>
  services.value.reduce((sum, s) => sum + s.volumes.length, 0),
)
const totalNetworks = computed(() =>
  services.value.reduce((sum, s) => sum + s.networks.length, 0),
)
const totalPorts = computed(() =>
  services.value.reduce((sum, s) => sum + s.ports.length, 0),
)

const volumeStrategyLabel = computed(
  () => volumeStrategyOptions.find(o => o.value === form.value.volume_strategy)?.label ?? form.value.volume_strategy,
)
const networkStrategyLabel = computed(
  () => networkStrategyOptions.find(o => o.value === form.value.network_strategy)?.label ?? form.value.network_strategy,
)

// ---------------------------------------------------------------------------
// Watchers
// ---------------------------------------------------------------------------

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      await loadAdoptionData()
    }
  },
  { immediate: true },
)

// ---------------------------------------------------------------------------
// Methods
// ---------------------------------------------------------------------------

async function loadAdoptionData() {
  loading.value = true
  error.value = ''
  currentStep.value = 0
  wizardData.value = null
  adoptionResult.value = null

  try {
    const { data } = await discoveryApi.getAdoptionData(props.itemType, props.itemId)
    wizardData.value = data
    // Pré-remplir le nom de stack avec le nom du projet
    form.value.stack_name = data.name.replace(/[^a-zA-Z0-9_-]/g, '-')
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Erreur lors du chargement des données d\'adoption'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function nextStep() {
  if (currentStep.value < 2) {
    currentStep.value++
  }
}

function prevStep() {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

async function handleAdopt() {
  if (!wizardData.value) return

  adopting.value = true
  error.value = ''

  try {
    const request: AdoptionRequest = {
      discovered_id: wizardData.value.discovered_id,
      type: props.itemType,
      stack_name: form.value.stack_name,
      volume_strategy: form.value.volume_strategy,
      network_strategy: form.value.network_strategy,
      compose_content: wizardData.value.generated_compose ?? undefined,
    }

    const { data } = await discoveryApi.adopt(request)
    adoptionResult.value = data
    emit('adopted', data)
    ElMessage.success(data.message)
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Erreur lors de l\'adoption'
    error.value = msg
    ElMessage.error(msg)
  } finally {
    adopting.value = false
  }
}

function handleClose() {
  visible.value = false
  currentStep.value = 0
  wizardData.value = null
  adoptionResult.value = null
  error.value = ''
}
</script>

<style scoped>
.wizard-steps {
  margin-bottom: 24px;
}

.wizard-content {
  min-height: 200px;
}

.wizard-error {
  margin-bottom: 16px;
}

.step-content {
  padding: 0 8px;
}

.step-content h3 {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.compose-preview {
  margin-top: 16px;
}

.compose-code {
  overflow-x: auto;
  max-height: 300px;
  padding: 12px;
  font-size: 13px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  line-height: 1.5;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
