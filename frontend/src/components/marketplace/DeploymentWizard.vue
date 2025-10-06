<template>
  <el-dialog
    v-model="visible"
    :title="`Déployer ${stack.name}`"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- Steps -->
    <el-steps :active="currentStep" finish-status="success" align-center class="mb-8">
      <el-step title="Cible" />
      <el-step title="Configuration" />
      <el-step title="Révision" />
      <el-step title="Déploiement" />
    </el-steps>

    <!-- Contenu des étapes -->
    <div class="wizard-content min-h-96">
      <!-- Étape 1: Sélection de la cible -->
      <div v-if="currentStep === 0" class="step-content">
        <h3 class="text-lg font-semibold mb-4">
          Choisir la cible de déploiement
        </h3>
        <TargetSelector v-model="selectedTargetId" />
      </div>

      <!-- Étape 2: Configuration avec JSONForms -->
      <div v-if="currentStep === 1" class="step-content">
        <h3 class="text-lg font-semibold mb-4">
          Configuration du déploiement
        </h3>

        <!-- JSONForms renderer -->
        <div class="jsonforms-container p-4 border border-gray-200 rounded-lg bg-gray-50">
          <json-forms
            :data="formData"
            :schema="convertedSchema.schema"
            :uischema="convertedSchema.uischema"
            :renderers="renderers"
            @change="onFormChange"
          />
        </div>

        <!-- Bouton génération automatique -->
        <div
          v-if="convertedSchema.metadata.generateableFields.length > 0"
          class="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <h4 class="font-medium text-blue-900 mb-1">
                Génération automatique
              </h4>
              <p class="text-sm text-blue-700">
                Générez automatiquement des valeurs sécurisées pour :
                <span class="font-mono">
                  {{ convertedSchema.metadata.generateableFields.join(', ') }}
                </span>
              </p>
            </div>
            <el-button
              type="primary"
              size="small"
              :icon="Refresh"
              @click="generateFields"
            >
              Générer
            </el-button>
          </div>
        </div>

        <!-- Nom du déploiement -->
        <div class="mt-4">
          <el-input
            v-model="deploymentName"
            placeholder="Nom du déploiement (optionnel)"
          >
            <template #prepend>Nom</template>
          </el-input>
          <p class="text-xs text-gray-500 mt-1">
            Par défaut: {{ stack.name }}-{{ stack.version }}
          </p>
        </div>
      </div>

      <!-- Étape 3: Révision -->
      <div v-if="currentStep === 2" class="step-content">
        <h3 class="text-lg font-semibold mb-4">
          Révision de la configuration
        </h3>

        <el-alert
          type="warning"
          :closable="false"
          class="mb-4"
        >
          <p class="text-sm">
            ⚠️ Vérifiez attentivement votre configuration avant de déployer.
          </p>
        </el-alert>

        <el-descriptions :column="1" border class="mb-4">
          <el-descriptions-item label="Stack">
            <div class="flex items-center gap-2">
              <strong>{{ stack.name }}</strong>
              <el-tag size="small">v{{ stack.version }}</el-tag>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="Cible">
            <strong>{{ selectedTarget?.name || 'Non sélectionnée' }}</strong>
            <span v-if="selectedTarget" class="text-gray-500 ml-2">
              ({{ selectedTarget.type }})
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="Nom du déploiement">
            {{ deploymentName || `${stack.name}-${stack.version}` }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="mt-4">
          <h4 class="font-medium mb-2">Configuration :</h4>
          <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 max-h-96 overflow-auto">
            <table class="w-full text-sm">
              <thead class="border-b">
                <tr>
                  <th class="text-left py-2 px-3 text-gray-700">Paramètre</th>
                  <th class="text-left py-2 px-3 text-gray-700">Valeur</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="([key, value], index) in Object.entries(formData)"
                  :key="key"
                  :class="{ 'border-t': index > 0 }"
                >
                  <td class="py-2 px-3 font-mono text-xs text-gray-600">
                    {{ key }}
                  </td>
                  <td class="py-2 px-3">
                    <span v-if="isPasswordField(key)" class="text-gray-400">
                      ••••••••••••
                    </span>
                    <span v-else class="font-mono text-xs">
                      {{ formatValue(value) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <el-alert
          v-if="hasPasswordFields"
          type="info"
          :closable="false"
          class="mt-4"
        >
          <p class="text-sm">
            💡 Les mots de passe seront stockés de manière sécurisée.
            Notez-les si vous en avez besoin pour un accès ultérieur.
          </p>
        </el-alert>
      </div>

      <!-- Étape 4: Déploiement en cours -->
      <div v-if="currentStep === 3" class="step-content">
        <DeploymentProgress
          v-if="deploymentId"
          :deployment-id="deploymentId"
          @complete="onDeploymentComplete"
          @error="onDeploymentError"
        />
      </div>
    </div>

    <!-- Footer avec navigation -->
    <template #footer>
      <div class="flex justify-between">
        <el-button
          v-if="currentStep > 0 && currentStep < 3"
          @click="previousStep"
          :disabled="deploying"
        >
          Précédent
        </el-button>
        <div class="flex-1" />
        <el-button
          v-if="currentStep < 2"
          type="primary"
          @click="nextStep"
          :disabled="!canProceed"
        >
          Suivant
        </el-button>
        <el-button
          v-if="currentStep === 2"
          type="primary"
          :icon="Promotion"
          @click="startDeployment"
          :loading="deploying"
        >
          Déployer
        </el-button>
        <el-button
          v-if="currentStep === 3"
          @click="handleClose"
        >
          Fermer
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { JsonForms } from '@jsonforms/vue'
import { elementPlusRenderers } from '@/components/marketplace/renderers'
import { convertToJsonSchema, extractDefaults } from '@/utils/schemaConverter'
import { generatePasswordForField } from '@/utils/passwordGenerator'
import { useMarketplaceStore } from '@/stores/marketplace'
import TargetSelector from '@/components/marketplace/TargetSelector.vue'
import DeploymentProgress from '@/components/marketplace/DeploymentProgress.vue'
import type { StackDetails, Target } from '@/types/marketplace'
import { Refresh, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Props {
  stack: StackDetails
  visible: boolean
}

interface Emits {
  'update:visible': [value: boolean]
  deployed: [deploymentId: string]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const store = useMarketplaceStore()

// État du wizard
const currentStep = ref(0)
const selectedTargetId = ref('')
const formData = ref<Record<string, any>>({})
const deploymentName = ref('')
const deploying = ref(false)
const deploymentId = ref('')

// Mock pour selectedTarget (à implémenter avec vrai service)
const selectedTarget = ref<Target | null>(null)

// JSONForms renderers Element Plus
const renderers = Object.freeze(elementPlusRenderers)

// Conversion du schema
const convertedSchema = computed(() => {
  return convertToJsonSchema(props.stack.variables)
})

const hasPasswordFields = computed(() => {
  return convertedSchema.value.metadata.generateableFields.length > 0
})

const canProceed = computed(() => {
  if (currentStep.value === 0) return !!selectedTargetId.value
  if (currentStep.value === 1) return validateForm()
  return true
})

// Initialiser les valeurs par défaut
watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    currentStep.value = 0
    formData.value = extractDefaults(convertedSchema.value.schema)
    deploymentName.value = ''
    deploymentId.value = ''
    selectedTargetId.value = ''
  }
})

function onFormChange(event: any) {
  formData.value = event.data
}

function validateForm(): boolean {
  // JSONForms gère la validation automatique via le schema
  // Vérifier les champs requis
  const required = convertedSchema.value.schema.required || []
  return required.every(field => {
    const value = formData.value[field]
    return value !== undefined && value !== null && value !== ''
  })
}

function generateFields() {
  const fields = convertedSchema.value.metadata.generateableFields

  fields.forEach(field => {
    const variable = props.stack.variables[field]

    if (variable.type === 'password') {
      const minLength = variable.min_length || 16
      formData.value[field] = generatePasswordForField(minLength, variable.max_length)
    }
  })

  ElMessage.success('Mots de passe générés automatiquement')
}

function isPasswordField(key: string): boolean {
  return props.stack.variables[key]?.type === 'password'
}

function formatValue(value: any): string {
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function nextStep() {
  if (canProceed.value && currentStep.value < 3) {
    currentStep.value++
  }
}

function previousStep() {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

async function startDeployment() {
  if (!selectedTargetId.value) {
    ElMessage.error('Veuillez sélectionner une cible de déploiement')
    return
  }

  deploying.value = true

  try {
    const response = await store.deployStack(
      props.stack.id,
      selectedTargetId.value,
      formData.value,
      deploymentName.value || undefined
    )

    deploymentId.value = response.deployment_id
    currentStep.value = 3
  } catch (err) {
    ElMessage.error('Erreur lors du lancement du déploiement')
    console.error(err)
  } finally {
    deploying.value = false
  }
}

function onDeploymentComplete() {
  emit('deployed', deploymentId.value)
  handleClose()
}

function onDeploymentError(error: any) {
  ElMessage.error(`Déploiement échoué: ${error.message || error}`)
  currentStep.value = 2  // Retour à la révision
}

function handleClose() {
  emit('update:visible', false)

  // Reset après un court délai pour éviter les glitches visuels
  setTimeout(() => {
    currentStep.value = 0
    formData.value = {}
    deploymentName.value = ''
    deploymentId.value = ''
    selectedTargetId.value = ''
  }, 300)
}
</script>

<style scoped>
.wizard-content {
  min-height: 400px;
}

.step-content {
  padding: 20px;
}

.jsonforms-container {
  max-height: 500px;
  overflow-y: auto;
}

/* Styles pour JSONForms avec Element Plus */
:deep(.vertical-layout) {
  display: flex;
  flex-direction: column;
  gap: 0;
}

:deep(.jsonforms-control) {
  margin-bottom: 0;
}
</style>
