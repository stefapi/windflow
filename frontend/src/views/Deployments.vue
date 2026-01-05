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
            <el-tag :type="getStatusType(getRealtimeStatus(row.id, row.status))">
              {{ getRealtimeStatus(row.id, row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created At" />
        <el-table-column label="Actions" width="420">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetails(row.id)">Details</el-button>
            <el-button
              size="small"
              type="success"
              @click="viewLogs(row.id, row.stack?.name || 'Deployment')"
            >
              <span class="i-carbon-document-blank mr-1" />
              Logs
            </el-button>
            <el-button size="small" type="warning" @click="cancelDeployment(row.id)" v-if="row.status === 'pending' || row.status === 'installing'">Cancel</el-button>
            <el-button size="small" type="info" @click="retryDeployment(row.id)" v-if="row.status === 'failed'">Retry</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id, row.name)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Drawer pour les logs en temps réel -->
    <el-drawer
      v-model="showLogsDrawer"
      :title="`Logs - ${currentDeploymentName}`"
      direction="rtl"
      size="70%"
      :close-on-click-modal="false"
    >
      <DeploymentLogs
        v-if="currentDeploymentId"
        :deployment-id="currentDeploymentId"
        :deployment-name="currentDeploymentName"
        :debug="false"
      />
    </el-drawer>

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

        <!-- Nom du déploiement -->
        <el-form-item
          label="Nom"
          :rules="[{ required: true, message: 'Nom', trigger: 'blur' }]"
          prop="name"
        >
          <el-input
            v-model="form.name"
            placeholder="Nom du déploiement"
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
            v-model="form[field.key]"
            @regenerate="handleRegenerateVariable(field.key)"
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
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import type { DeploymentCreate } from '@/types/api'
import DynamicFormField from '@/components/DynamicFormField.vue'
import DeploymentLogs from '@/components/DeploymentLogs.vue'
import { useDynamicForm } from '@/composables/useDynamicForm'
import { useDeploymentStatusMonitor } from '@/composables/useDeploymentWebSocket'
import { stacksApi } from '@/services/api'

const router = useRouter()
const deploymentsStore = useDeploymentsStore()
const stacksStore = useStacksStore()
const targetsStore = useTargetsStore()
const authStore = useAuthStore()

// Surveillance des statuts en temps réel via WebSocket
const { getStatus } = useDeploymentStatusMonitor()

// État du dialog
const showDialog = ref(false)
const deploying = ref(false)
const formRef = ref<FormInstance>()

// État du drawer des logs
const showLogsDrawer = ref(false)
const currentDeploymentId = ref<string | null>(null)
const currentDeploymentName = ref<string>('Deployment')

// Formulaire de base + champs dynamiques fusionnés
const form = reactive<DeploymentCreate & { name?: string; [key: string]: any }>({
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
const dynamicFormInstance = ref<ReturnType<typeof useDynamicForm> | null>(null)

const dynamicFields = computed(() => {
  return dynamicFormInstance.value?.fields || []
})

/**
 * Gestion du changement de stack.
 * Réinitialise le formulaire dynamique avec les variables du nouveau stack.
 */
const onStackChange = async () => {
  // Nettoyer les anciens champs dynamiques du formulaire
  const staticKeys = ['stack_id', 'target_id', 'name']
  Object.keys(form).forEach(key => {
    if (!staticKeys.includes(key)) {
      delete form[key]
    }
  })

  // Réinitialiser le formulaire dynamique avant chargement
  dynamicFormInstance.value = null

  try {
    if (!form.stack_id) return

    // Récupère les détails du stack (inclut les variables)
    const { data } = await stacksApi.get(form.stack_id)

    // Pré-remplir le nom avec le default_name généré par le backend
    if (data && (data as any).default_name) {
      form.name = (data as any).default_name
    }

    if (data && (data as any).variables && Object.keys((data as any).variables).length > 0) {
      // Créer l'instance du formulaire dynamique
      dynamicFormInstance.value = useDynamicForm((data as any).variables)

      // Fusionner les valeurs par défaut dans le formulaire principal
      Object.entries(dynamicFormInstance.value.formData).forEach(([key, value]) => {
        form[key] = value
      })
    } else {
      // Aucun champ de configuration requis
      dynamicFormInstance.value = null
    }
  } catch (err: any) {
    console.error('Erreur lors du chargement des détails du stack:', err)
    ElMessage.error(err?.message || 'Impossible de charger la configuration du stack')
  }
}

/**
 * Régénère la valeur d'une variable contenant une macro.
 */
const handleRegenerateVariable = async (variableName: string) => {
  if (!form.stack_id) {
    ElMessage.warning('Aucun stack sélectionné')
    return
  }

  try {
    // Appeler l'API pour régénérer la variable
    const { data } = await stacksApi.regenerateVariable(form.stack_id, variableName)

    // Mettre à jour la valeur dans le formulaire
    form[variableName] = data.new_value

    // Afficher un message de succès
    ElMessage.success(`Nouvelle valeur générée pour ${variableName}`)
  } catch (err: any) {
    console.error('Erreur lors de la régénération de la variable:', err)
    ElMessage.error(err?.message || 'Impossible de régénérer la variable')
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
  dynamicFormInstance.value = null
}

/**
 * Fermeture du dialog.
 */
const closeDialog = () => {
  showDialog.value = false

  // Nettoyer tous les champs du formulaire
  const staticKeys = ['stack_id', 'target_id', 'name']
  Object.keys(form).forEach(key => {
    if (staticKeys.includes(key)) {
      form[key] = ''
    } else {
      delete form[key]
    }
  })

  dynamicFormInstance.value = null

  // Reset la validation du formulaire
  formRef.value?.resetFields()
}

/**
 * Gestion de la création du déploiement.
 */
const handleCreate = async () => {
  // Validation complète du formulaire (champs de base + dynamiques)
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch (validationError) {
    console.error('Validation échouée:', validationError)
    ElMessage.warning('Veuillez corriger les erreurs de validation')
    return
  }

  deploying.value = true

  try {
    // Extraire les champs statiques
    const staticKeys = ['stack_id', 'target_id', 'name']

    // Construire la payload
    const payload: any = {
      stack_id: form.stack_id,
      target_id: form.target_id
    }

    // Ajouter le nom si fourni
    if (form.name && form.name.trim()) {
      payload.name = form.name.trim()
    }

    // Extraire les champs dynamiques pour les variables
    const dynamicVariables: Record<string, any> = {}
    Object.entries(form).forEach(([key, value]) => {
      if (!staticKeys.includes(key)) {
        dynamicVariables[key] = value
      }
    })

    // Ajouter les variables si présentes
    if (Object.keys(dynamicVariables).length > 0) {
      payload.variables = dynamicVariables
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
 * Obtenir le statut en temps réel d'un déploiement
 * Si un statut WebSocket est disponible, l'utiliser, sinon utiliser le statut du store
 */
const getRealtimeStatus = (deploymentId: string, fallbackStatus: string): string => {
  const realtimeStatus = getStatus(deploymentId)
  return realtimeStatus || fallbackStatus
}

/**
 * Ouvrir le drawer des logs
 */
const viewLogs = (deploymentId: string, deploymentName: string) => {
  currentDeploymentId.value = deploymentId
  currentDeploymentName.value = deploymentName
  showLogsDrawer.value = true
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
 * Suppression d'un déploiement avec confirmation.
 */
const handleDelete = async (id: string, name: string) => {
  try {
    await ElMessageBox.confirm(
      `Êtes-vous sûr de vouloir supprimer le déploiement "${name}" ? Cette action arrêtera le déploiement et supprimera toutes les ressources associées (conteneurs, volumes, etc.). Cette action est irréversible.`,
      'Confirmation de suppression',
      {
        confirmButtonText: 'Supprimer',
        cancelButtonText: 'Annuler',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )

    // Si l'utilisateur confirme, procéder à la suppression
    await deploymentsStore.deleteDeployment(id)
    ElMessage.success('Déploiement supprimé avec succès')
  } catch (error) {
    // Si l'utilisateur annule, error sera 'cancel'
    if (error !== 'cancel') {
      ElMessage.error('Échec de la suppression du déploiement')
    }
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
