<template>
  <div class="deployment-progress">
    <!-- État du déploiement -->
    <div class="text-center mb-8">
      <el-icon
        v-if="status === 'success'"
        class="text-8xl text-green-500 mb-4"
      >
        <CircleCheck />
      </el-icon>
      <el-icon
        v-else-if="status === 'failed'"
        class="text-8xl text-red-500 mb-4"
      >
        <CircleClose />
      </el-icon>
      <div
        v-else
        class="mb-4"
      >
        <el-icon class="text-8xl text-primary animate-spin">
          <Loading />
        </el-icon>
      </div>

      <h3 class="text-2xl font-bold mb-2" :class="getStatusColor(status)">
        {{ getStatusMessage(status) }}
      </h3>
      <p class="text-gray-600">
        {{ deploymentInfo?.name || deploymentId }}
      </p>
    </div>

    <!-- Barre de progression -->
    <el-progress
      v-if="status === 'pending' || status === 'running'"
      :percentage="progress"
      :status="status === 'running' ? 'success' : undefined"
      :indeterminate="status === 'pending'"
      :duration="3"
    />

    <!-- Étapes du déploiement -->
    <div class="mt-6">
      <el-timeline>
        <el-timeline-item
          v-for="step in deploymentSteps"
          :key="step.id"
          :timestamp="step.timestamp"
          :type="getStepType(step.status)"
          :icon="getStepIcon(step.status)"
        >
          <div class="flex items-start justify-between">
            <div>
              <p class="font-medium">{{ step.title }}</p>
              <p v-if="step.description" class="text-sm text-gray-600">
                {{ step.description }}
              </p>
            </div>
            <el-tag :type="getStepTagType(step.status)" size="small">
              {{ step.status }}
            </el-tag>
          </div>
        </el-timeline-item>
      </el-timeline>
    </div>

    <!-- Logs en temps réel -->
    <el-collapse v-if="logs.length > 0" v-model="activeCollapse" class="mt-6">
      <el-collapse-item title="Logs de déploiement" name="logs">
        <div class="logs-container bg-gray-900 text-gray-100 p-4 rounded font-mono text-xs max-h-64 overflow-auto">
          <div v-for="(log, index) in logs" :key="index" class="log-line">
            {{ log }}
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- Erreur détaillée -->
    <el-alert
      v-if="status === 'failed' && error"
      type="error"
      :title="error"
      :closable="false"
      show-icon
      class="mt-6"
    >
      <p class="text-sm">
        Le déploiement a échoué. Consultez les logs ci-dessus pour plus de détails.
      </p>
    </el-alert>

    <!-- Actions de succès -->
    <div v-if="status === 'success'" class="mt-6 text-center">
      <el-alert
        type="success"
        :closable="false"
        class="mb-4"
      >
        <p class="text-sm">
          🎉 Votre stack a été déployé avec succès !
        </p>
      </el-alert>

      <div class="flex justify-center gap-3">
        <el-button type="primary" @click="viewDeployment">
          Voir le déploiement
        </el-button>
        <el-button @click="$emit('complete')">
          Fermer
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDeploymentLogs } from '@/composables/useDeploymentLogs'
import {
  CircleCheck,
  CircleClose,
  Loading,
  Check,
  Close,
  Clock
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Props {
  deploymentId: string
}

interface Emits {
  complete: []
  error: [error: any]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const router = useRouter()

// Utilisation du composable WebSocket avec authentification
const {
  logs: wsLogs,
  connected,
  connecting,
  currentStatus,
  error: wsError,
  isComplete,
  isSuccess
} = useDeploymentLogs(computed(() => props.deploymentId), {
  onConnect: () => {
    console.log('✅ WebSocket connected for deployment logs')
    ElMessage.success('Connexion WebSocket établie')
  },
  onDisconnect: () => {
    console.log('WebSocket déconnecté')
  },
  onError: (err) => {
    console.error('Erreur WebSocket:', err)
    ElMessage.error('Erreur de connexion aux logs')
  }
})

// Connexion WebSocket avec authentification automatique
onMounted(() => {
  console.log('🔌 Initializing WebSocket connection for deployment:', props.deploymentId)
  // Le composable useDeploymentLogs va automatiquement utiliser connectWithAuth()
})

// État local
const activeCollapse = ref<string[]>([])
const deploymentInfo = ref<any>(null)

// Computed depuis le WebSocket
const status = computed<'pending' | 'running' | 'success' | 'failed'>(() => {
  if (isComplete.value) {
    return isSuccess.value ? 'success' : 'failed'
  }
  if (currentStatus.value === 'running') {
    return 'running'
  }
  return 'pending'
})

const error = computed(() => wsError.value)

const logs = computed(() => {
  return wsLogs.value
    .filter(log => log.type === 'log')
    .map(log => {
      const timestamp = new Date(log.timestamp).toLocaleTimeString('fr-FR')
      const level = log.level?.toUpperCase() || 'INFO'
      return `[${timestamp}] [${level}] ${log.message || ''}`
    })
})

const progress = computed(() => {
  const total = deploymentSteps.value.length
  const completed = deploymentSteps.value.filter(s => s.status === 'completed').length
  return Math.round((completed / total) * 100)
})

interface DeploymentStep {
  id: string
  title: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  timestamp?: string
}

const deploymentSteps = ref<DeploymentStep[]>([
  {
    id: '1',
    title: 'Préparation du déploiement',
    description: 'Validation de la configuration et génération du compose',
    status: 'pending'
  },
  {
    id: '2',
    title: 'Téléchargement des images Docker',
    description: 'Pull des images depuis le registry',
    status: 'pending'
  },
  {
    id: '3',
    title: 'Création des volumes et réseaux',
    description: 'Configuration de l\'infrastructure',
    status: 'pending'
  },
  {
    id: '4',
    title: 'Démarrage des services',
    description: 'Lancement des containers Docker',
    status: 'pending'
  },
  {
    id: '5',
    title: 'Health checks',
    description: 'Vérification de l\'état des services',
    status: 'pending'
  }
])


function getStatusMessage(st: string): string {
  const messages: Record<string, string> = {
    'pending': 'Déploiement en attente...',
    'running': 'Déploiement en cours...',
    'success': 'Déploiement réussi !',
    'failed': 'Déploiement échoué'
  }
  return messages[st] || 'Statut inconnu'
}

function getStatusColor(st: string): string {
  const colors: Record<string, string> = {
    'pending': 'text-gray-600',
    'running': 'text-blue-600',
    'success': 'text-green-600',
    'failed': 'text-red-600'
  }
  return colors[st] || 'text-gray-600'
}

function getStepType(st: string): string {
  const types: Record<string, string> = {
    'completed': 'success',
    'running': 'primary',
    'failed': 'danger',
    'pending': 'info'
  }
  return types[st] || 'info'
}

function getStepIcon(st: string) {
  const icons: Record<string, any> = {
    'completed': Check,
    'running': Loading,
    'failed': Close,
    'pending': Clock
  }
  return icons[st] || Clock
}

function getStepTagType(st: string): string {
  const types: Record<string, string> = {
    'completed': 'success',
    'running': 'primary',
    'failed': 'danger',
    'pending': 'info'
  }
  return types[st] || 'info'
}


function updateStep(index: number, newStatus: DeploymentStep['status'], description?: string) {
  if (deploymentSteps.value[index]) {
    deploymentSteps.value[index].status = newStatus
    deploymentSteps.value[index].timestamp = new Date().toLocaleTimeString('fr-FR')
    if (description) {
      deploymentSteps.value[index].description = description
    }
  }
}


function viewDeployment() {
  router.push(`/deployments/${props.deploymentId}`)
}

// Watcher sur les logs pour auto-scroll
watch(() => logs.value.length, () => {
  setTimeout(() => {
    const logsContainer = document.querySelector('.logs-container')
    if (logsContainer) {
      logsContainer.scrollTop = logsContainer.scrollHeight
    }
  }, 100)
})

// Watcher sur le statut pour mettre à jour les steps et émettre les événements
watch(currentStatus, (newStatus) => {
  // Mettre à jour les steps selon le statut
  switch (newStatus) {
    case 'running':
      updateStep(0, 'completed')
      updateStep(1, 'running')
      break
  }
})

watch(isComplete, (complete) => {
  if (complete) {
    // Marquer toutes les steps comme terminées
    deploymentSteps.value.forEach((_, index) => {
      updateStep(index, 'completed')
    })

    if (isSuccess.value) {
      emit('complete')
    } else {
      emit('error', { message: error.value || 'Déploiement échoué' })
    }
  }
})
</script>

<style scoped>
.deployment-progress {
  padding: 20px;
}

.animate-spin {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.log-line {
  padding: 2px 0;
  font-family: 'Courier New', monospace;
}

.log-line:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.logs-container {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.3) transparent;
}

.logs-container::-webkit-scrollbar {
  width: 8px;
}

.logs-container::-webkit-scrollbar-track {
  background: transparent;
}

.logs-container::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.3);
  border-radius: 4px;
}
</style>
