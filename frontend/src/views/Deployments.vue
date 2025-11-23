<template>
  <div class="deployments">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Deployments</span>
          <el-button type="primary" @click="openDialog">New Deployment</el-button>
        </div>
      </template>
      <el-table :data="deploymentsStore.deployments" v-loading="deploymentsStore.loading">
        <el-table-column prop="id" label="ID" width="100" />
        <el-table-column prop="status" label="Status">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created At" />
        <el-table-column label="Actions" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetails(row.id)">Details</el-button>
            <el-button size="small" type="warning" @click="cancelDeployment(row.id)" v-if="row.status === 'running'">Cancel</el-button>
            <el-button size="small" type="info" @click="retryDeployment(row.id)" v-if="row.status === 'failed'">Retry</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="showDialog"
      title="Create Deployment"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        label-width="140px"
        label-position="left"
      >
        <!-- Sélection du Stack -->
        <el-form-item
          label="Stack"
          :rules="[{ required: true, message: 'Stack requis', trigger: 'change' }]"
          prop="stack_id"
        >
          <el-select
            v-model="form.stack_id"
            placeholder="Sélectionner un stack"
            style="width: 100%"
            @change="onStackChange"
            clearable
          >
            <el-option
              v-for="stack in stacksStore.stacks"
              :key="stack.id"
              :label="stack.name"
              :value="stack.id"
            />
          </el-select>
        </el-form-item>

        <!-- Sélection de la Target -->
        <el-form-item
          label="Target"
          :rules="[{ required: true, message: 'Target requise', trigger: 'change' }]"
          prop="target_id"
        >
          <el-select
            v-model="form.target_id"
            placeholder="Sélectionner une cible"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="target in targetsStore.targets"
              :key="target.id"
              :label="target.name"
              :value="target.id"
            />
          </el-select>
        </el-form-item>

        <!-- Nom du déploiement (optionnel) -->
        <el-form-item label="Nom (optionnel)">
          <el-input
            v-model="form.name"
            placeholder="Auto-généré si vide"
            clearable
          />
        </el-form-item>

        <!-- Divider avant les variables -->
        <el-divider v-if="selectedStack && dynamicFields.length > 0">
          Configuration des variables
        </el-divider>

        <!-- Formulaire dynamique des variables -->
        <template v-if="selectedStack && dynamicFields.length > 0">
          <DynamicFormField
            v-for="field in dynamicFields"
            :key="field.key"
            :field="field"
            v-model="dynamicFormData[field.key]"
          />
        </template>

        <!-- Message si aucune variable -->
        <el-alert
          v-else-if="selectedStack && dynamicFields.length === 0"
          title="Aucune configuration requise"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form>

      <template #footer>
        <el-button @click="closeDialog">Annuler</el-button>
        <el-button
          type="primary"
          @click="handleCreate"
          :loading="deploying"
          :disabled="!form.stack_id || !form.target_id"
        >
          Déployer
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDeploymentsStore, useStacksStore, useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, type FormInstance } from 'element-plus'
import type { DeploymentCreate } from '@/types/api'
import DynamicFormField from '@/components/DynamicFormField.vue'
import { useDynamicForm } from '@/composables/useDynamicForm'

const router = useRouter()
const deploymentsStore = useDeploymentsStore()
const stacksStore = useStacksStore()
const targetsStore = useTargetsStore()
const authStore = useAuthStore()

// État du dialog
const showDialog = ref(false)
const deploying = ref(false)
const formRef = ref<FormInstance>()

// Formulaire de base
const form = reactive<DeploymentCreate & { name?: string }>({
  stack_id: '',
  target_id: '',
  name: ''
})

// Stack sélectionné
const selectedStack = computed(() => {
  if (!form.stack_id) return null
  return stacksStore.stacks.find(s => s.id === form.stack_id)
})

// Initialisation du formulaire dynamique
let dynamicFormInstance: ReturnType<typeof useDynamicForm> | null = null

const dynamicFormData = computed(() => {
  return dynamicFormInstance?.formData || {}
})

const dynamicFields = computed(() => {
  return dynamicFormInstance?.fields || []
})

/**
 * Gestion du changement de stack.
 * Réinitialise le formulaire dynamique avec les variables du nouveau stack.
 */
const onStackChange = () => {
  if (selectedStack.value && selectedStack.value.variables) {
    // Créer une nouvelle instance du formulaire dynamique
    dynamicFormInstance = useDynamicForm(selectedStack.value.variables)
  } else {
    dynamicFormInstance = null
  }
}

/**
 * Ouverture du dialog.
 */
const openDialog = () => {
  showDialog.value = true
  // Réinitialiser le formulaire
  form.stack_id = ''
  form.target_id = ''
  form.name = ''
  dynamicFormInstance = null
}

/**
 * Fermeture du dialog.
 */
const closeDialog = () => {
  showDialog.value = false
  form.stack_id = ''
  form.target_id = ''
  form.name = ''
  dynamicFormInstance = null
}

/**
 * Gestion de la création du déploiement.
 */
const handleCreate = async () => {
  // Validation du formulaire de base
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    ElMessage.warning('Veuillez remplir tous les champs requis')
    return
  }

  // Validation du formulaire dynamique si présent
  if (dynamicFormInstance) {
    const validation = dynamicFormInstance.validateRequired()
    if (!validation.valid) {
      ElMessage.warning(validation.errors.join(', '))
      return
    }
  }

  deploying.value = true

  try {
    // Construire la payload
    const payload: any = {
      stack_id: form.stack_id,
      target_id: form.target_id
    }

    // Ajouter le nom si fourni
    if (form.name && form.name.trim()) {
      payload.name = form.name.trim()
    }

    // Ajouter les variables si présentes
    if (dynamicFormInstance) {
      payload.variables = dynamicFormInstance.getAllValues()
    }

    // Créer le déploiement
    await deploymentsStore.createDeployment(payload)

    ElMessage.success('Déploiement lancé avec succès')
    closeDialog()

    // Rafraîchir la liste
    const orgId = authStore.organizationId || undefined
    await deploymentsStore.fetchDeployments(orgId)
  } catch (err: any) {
    console.error('Erreur lors de la création du déploiement:', err)
    ElMessage.error(err?.message || 'Échec de la création du déploiement')
  } finally {
    deploying.value = false
  }
}

/**
 * Mapping des statuts vers les types Element Plus.
 */
const getStatusType = (status: string) => {
  const map: Record<string, any> = {
    completed: 'success',
    running: 'primary',
    pending: 'info',
    failed: 'danger',
    cancelled: 'warning'
  }
  return map[status] || 'info'
}

/**
 * Navigation vers les détails d'un déploiement.
 */
const viewDetails = (id: string) => {
  router.push(`/deployments/${id}`)
}

/**
 * Annulation d'un déploiement.
 */
const cancelDeployment = async (id: string) => {
  try {
    await deploymentsStore.cancelDeployment(id)
    ElMessage.success('Déploiement annulé')
  } catch {
    ElMessage.error('Échec de l\'annulation du déploiement')
  }
}

/**
 * Réessai d'un déploiement échoué.
 */
const retryDeployment = async (id: string) => {
  try {
    await deploymentsStore.retryDeployment(id)
    ElMessage.success('Déploiement relancé')
  } catch {
    ElMessage.error('Échec du relancement du déploiement')
  }
}

/**
 * Chargement initial des données.
 */
onMounted(async () => {
  const orgId = authStore.organizationId || undefined
  await Promise.all([
    deploymentsStore.fetchDeployments(orgId),
    stacksStore.fetchStacks(orgId),
    targetsStore.fetchTargets(orgId)
  ])
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
