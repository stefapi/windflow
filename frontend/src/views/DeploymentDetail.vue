<template>
  <div class="deployment-detail">
    <el-page-header @back="$router.push('/deployments')" style="margin-bottom: 20px">
      <template #content>
        <span>Deployment Details</span>
      </template>
    </el-page-header>

    <div v-if="deploymentsStore.loading && !deployment" v-loading="true" style="min-height: 200px" />

    <template v-if="deployment">
      <!-- En-tête avec statut et actions -->
      <el-card>
        <template #header>
          <div class="card-header">
            <div class="header-left">
              <span class="deployment-title">{{ deployment.name || deployment.id.slice(0, 12) }}</span>
              <el-tag :type="getStatusType(deployment.status)" size="large">
                {{ deployment.status }}
              </el-tag>
            </div>
            <div class="header-actions">
              <el-button
                v-if="deployment.status === 'running'"
                type="danger"
                @click="handleCancel"
                :loading="actionLoading"
              >
                Stop
              </el-button>
              <el-button
                v-if="deployment.status === 'failed' || deployment.status === 'cancelled'"
                type="warning"
                @click="handleRetry"
                :loading="actionLoading"
              >
                Retry
              </el-button>
              <el-button
                v-if="deployment.status === 'completed' || deployment.status === 'running'"
                type="primary"
                @click="handleRedeploy"
                :loading="actionLoading"
              >
                Redeploy
              </el-button>
            </div>
          </div>
        </template>

        <!-- Timeline de progression -->
        <div class="deployment-timeline">
          <el-steps :active="currentStepIndex" finish-status="success" :process-status="processStatus" align-center>
            <el-step title="Pending" description="Waiting to start" />
            <el-step title="Building" description="Preparing stack" />
            <el-step title="Deploying" description="Deploying to target" />
            <el-step title="Running" description="Active and healthy" />
          </el-steps>
        </div>
      </el-card>

      <!-- Informations détaillées -->
      <el-card style="margin-top: 20px">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">
            <code>{{ deployment.id }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="Status">
            <el-tag :type="getStatusType(deployment.status)" size="small">
              {{ deployment.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Stack">
            <router-link v-if="deployment.stack" to="/stacks" class="link">
              {{ deployment.stack.name }}
            </router-link>
            <code v-else>{{ deployment.stack_id.slice(0, 12) }}...</code>
          </el-descriptions-item>
          <el-descriptions-item label="Target">
            <router-link v-if="deployment.target" to="/targets" class="link">
              {{ deployment.target.name }} ({{ deployment.target.host }})
            </router-link>
            <code v-else>{{ deployment.target_id.slice(0, 12) }}...</code>
          </el-descriptions-item>
          <el-descriptions-item label="Created">
            {{ formatDate(deployment.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="Updated">
            {{ formatDate(deployment.updated_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- Onglets: Logs, Variables d'environnement -->
      <el-card style="margin-top: 20px">
        <el-tabs v-model="activeTab">
          <!-- Logs en temps réel -->
          <el-tab-pane label="Logs" name="logs">
            <div class="logs-container">
              <DeploymentLogs
                :deployment-id="deploymentId"
                :auto-connect="true"
              />
            </div>
          </el-tab-pane>

          <!-- Variables d'environnement -->
          <el-tab-pane label="Environment" name="env">
            <div v-if="envVars.length > 0">
              <el-table :data="envVars" size="small">
                <el-table-column prop="key" label="Variable" min-width="200" />
                <el-table-column label="Value" min-width="300">
                  <template #default="{ row }">
                    <div class="env-value-cell">
                      <span v-if="row.hidden && !row.revealed">••••••••</span>
                      <code v-else>{{ row.value }}</code>
                      <el-button
                        v-if="row.hidden"
                        size="small"
                        link
                        @click="row.revealed = !row.revealed"
                      >
                        {{ row.revealed ? 'Hide' : 'Show' }}
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-empty v-else description="No environment variables available" :image-size="60" />
          </el-tab-pane>

          <!-- Métriques -->
          <el-tab-pane label="Metrics" name="metrics">
            <el-descriptions :column="2" border v-if="deployment.metadata">
              <el-descriptions-item label="Uptime">
                {{ deployment.metadata['uptime'] || 'N/A' }}
              </el-descriptions-item>
              <el-descriptions-item label="CPU Usage">
                {{ deployment.metadata['cpu_usage'] || 'N/A' }}
              </el-descriptions-item>
              <el-descriptions-item label="Memory Usage">
                {{ deployment.metadata['memory_usage'] || 'N/A' }}
              </el-descriptions-item>
              <el-descriptions-item label="Restart Count">
                {{ deployment.metadata['restart_count'] ?? 'N/A' }}
              </el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="No metrics available yet" :image-size="60" />
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </template>

    <el-empty v-if="!deploymentsStore.loading && !deployment" description="Deployment not found" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeploymentsStore } from '@/stores'
import { ElMessage } from 'element-plus'
import DeploymentLogs from '@/components/DeploymentLogs.vue'
import type { Deployment } from '@/types/api'

const route = useRoute()
const router = useRouter()
const deploymentsStore = useDeploymentsStore()

const deploymentId = route.params['id'] as string
const activeTab = ref('logs')
const actionLoading = ref(false)

const deployment = computed<Deployment | null>(() => deploymentsStore.currentDeployment)

// Status type mapping
type TagType = 'success' | 'primary' | 'info' | 'danger' | 'warning'

function getStatusType(status: string): TagType {
  const map: Record<string, TagType> = {
    completed: 'success',
    running: 'primary',
    pending: 'info',
    deploying: 'warning',
    building: 'warning',
    failed: 'danger',
    cancelled: 'warning',
  }
  return map[status] || 'info'
}

// Timeline step index
const stepOrder = ['pending', 'building', 'deploying', 'running']

const currentStepIndex = computed(() => {
  if (!deployment.value) return 0
  const status = deployment.value.status
  if (status === 'completed') return 4
  if (status === 'failed' || status === 'cancelled') {
    const idx = stepOrder.indexOf(status)
    return idx >= 0 ? idx : 1
  }
  const idx = stepOrder.indexOf(status)
  return idx >= 0 ? idx : 0
})

const processStatus = computed(() => {
  if (!deployment.value) return 'process'
  if (deployment.value.status === 'failed') return 'error'
  if (deployment.value.status === 'completed') return 'success'
  return 'process'
})

// Parse env vars from stack compose content
const envVars = computed(() => {
  const content = deployment.value?.stack?.compose_content
  if (!content) return []

  const vars: { key: string; value: string; hidden: boolean; revealed: boolean }[] = []
  const lines = content.split('\n')

  for (const line of lines) {
    const envMatch = line.match(/^\s+-\s*(\w+)=(.*)$/)
    if (envMatch?.[1] && envMatch[2] !== undefined) {
      const key = envMatch[1]
      const value = envMatch[2]
      const isSecret = /password|secret|key|token/i.test(key)
      vars.push({ key, value, hidden: isSecret, revealed: false })
    }
    const envMapMatch = line.match(/^\s{6}(\w+):\s*(.+)$/)
    if (envMapMatch?.[1] && envMapMatch[2]) {
      const key = envMapMatch[1]
      const value = envMapMatch[2]
      const isSecret = /password|secret|key|token/i.test(key)
      vars.push({ key, value, hidden: isSecret, revealed: false })
    }
  }
  return vars
})

// Actions
async function handleCancel(): Promise<void> {
  actionLoading.value = true
  try {
    await deploymentsStore.cancelDeployment(deploymentId)
    ElMessage.success('Deployment stopped')
  } catch {
    ElMessage.error('Failed to stop deployment')
  } finally {
    actionLoading.value = false
  }
}

async function handleRetry(): Promise<void> {
  actionLoading.value = true
  try {
    await deploymentsStore.retryDeployment(deploymentId)
    ElMessage.success('Deployment retried')
  } catch {
    ElMessage.error('Failed to retry deployment')
  } finally {
    actionLoading.value = false
  }
}

async function handleRedeploy(): Promise<void> {
  if (!deployment.value) return
  actionLoading.value = true
  try {
    const newDeployment = await deploymentsStore.createDeployment({
      stack_id: deployment.value.stack_id,
      target_id: deployment.value.target_id,
    })
    ElMessage.success('Redeployment started')
    router.push(`/deployments/${newDeployment.id}`)
  } catch {
    ElMessage.error('Failed to redeploy')
  } finally {
    actionLoading.value = false
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return 'N/A'
  return new Date(dateStr).toLocaleString()
}

// Status polling
let statusInterval: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await deploymentsStore.fetchDeployment(deploymentId)

  // Poll status for active deployments
  statusInterval = setInterval(async () => {
    if (deployment.value && ['pending', 'building', 'deploying', 'running'].includes(deployment.value.status)) {
      await deploymentsStore.fetchDeployment(deploymentId)
    }
  }, 5000)
})

onUnmounted(() => {
  if (statusInterval) {
    clearInterval(statusInterval)
  }
})
</script>

<style scoped>
.deployment-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.deployment-title {
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.deployment-timeline {
  padding: 20px 0;
}

.logs-container {
  height: 500px;
}

.link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.env-value-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
