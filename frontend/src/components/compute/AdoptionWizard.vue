<template>
  <BaseWizard
    ref="wizardRef"
    v-model="visible"
    v-model:error="error"
    :title="wizardTitle"
    :steps="wizardSteps"
    :loading="loading"
    confirm-label="Confirmer l'adoption"
    :confirm-loading="adopting"
    :confirm-disabled="!form.stack_name"
    :completed="!!adoptionResult?.success"
    :next-disabled="currentStepInternal === 0 && services.length === 0"
    @confirm="handleAdopt"
    @close="handleClose"
  >
    <!-- STEP 0: Inventaire des services -->
    <template #step-0>
      <h3 class="mb-4 text-heading">
        Services détectés ({{ services.length }})
      </h3>
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
        class="mt-4"
      >
        <el-collapse>
          <el-collapse-item
            title="Aperçu docker-compose.yml"
            name="compose"
          >
            <pre class="code-block overflow-x-auto max-h-300px text-13px leading-relaxed">{{ wizardData.generated_compose }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>

    <!-- STEP 1: Options d'adoption -->
    <template #step-1>
      <h3 class="mb-4 text-heading">
        Configuration de l'adoption
      </h3>

      <el-form
        :model="form"
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
    </template>

    <!-- STEP 2: Confirmation -->
    <template #step-2>
      <h3 class="mb-4 text-heading">
        Récapitulatif
      </h3>

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
    </template>
  </BaseWizard>
</template>

<script setup lang="ts">
/**
 * AdoptionWizard — Adopt a discovered composition/container
 *
 * Uses BaseWizard for the step engine. Three steps:
 *   0: Service inventory
 *   1: Adoption options
 *   2: Confirmation / Result
 */
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import BaseWizard from '@/components/BaseWizard.vue'
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

const wizardRef = ref<InstanceType<typeof BaseWizard>>()

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const loading = ref(false)
const adopting = ref(false)
const error = ref('')
const wizardData = ref<AdoptionWizardData | null>(null)
const adoptionResult = ref<AdoptionResponse | null>(null)

// Track current step for next-disabled logic
const currentStepInternal = computed(() => wizardRef.value?.currentStep ?? 0)

const form = ref({
  stack_name: '',
  volume_strategy: 'keep_existing' as VolumeStrategy,
  network_strategy: 'keep_existing' as NetworkStrategy,
})

const wizardSteps = [
  { title: 'Services détectés', description: 'Inventaire' },
  { title: "Options d'adoption", description: 'Configuration' },
  { title: 'Confirmation', description: 'Valider' },
]

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const services = computed<AdoptionServiceData[]>(() => wizardData.value?.services ?? [])

const wizardTitle = computed(() => {
  const stepLabels = ['Inventaire des services', "Options d'adoption", 'Confirmation']
  return `Adopter : ${props.itemName} — ${stepLabels[currentStepInternal.value]}`
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
  wizardData.value = null
  adoptionResult.value = null

  try {
    const { data } = await discoveryApi.getAdoptionData(props.itemType, props.itemId)
    wizardData.value = data
    // Pré-remplir le nom de stack avec le nom du projet
    form.value.stack_name = data.name.replace(/[^a-zA-Z0-9_-]/g, '-')
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Erreur lors du chargement des données d'adoption"
    error.value = msg
    ElMessage.error(msg)
  } finally {
    loading.value = false
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
    const msg = err instanceof Error ? err.message : "Erreur lors de l'adoption"
    error.value = msg
    ElMessage.error(msg)
  } finally {
    adopting.value = false
  }
}

function handleClose() {
  visible.value = false
  wizardData.value = null
  adoptionResult.value = null
  error.value = ''
}
</script>
