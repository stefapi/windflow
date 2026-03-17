<template>
  <div class="containers-page">
    <!-- Header -->
    <el-card class="page-header">
      <template #header>
        <div class="header-content">
          <div class="header-title">
            <span class="title">Containers</span>
            <span class="subtitle">Gestion des containers Docker</span>
          </div>
          <div class="header-actions">
            <el-badge
              :value="containersStore.runningContainers.length"
              type="success"
              class="counter-badge"
            >
              <el-tag type="success">
                Running
              </el-tag>
            </el-badge>
            <el-badge
              :value="containersStore.stoppedContainers.length"
              type="info"
              class="counter-badge"
            >
              <el-tag type="info">
                Stopped
              </el-tag>
            </el-badge>
            <el-button
              :loading="containersStore.loading"
              @click="refreshContainers"
            >
              <el-icon class="el-icon--left">
                <Refresh />
              </el-icon>
              Rafraîchir
            </el-button>
          </div>
        </div>
      </template>

      <!-- Error Alert -->
      <el-alert
        v-if="containersStore.error"
        :title="containersStore.error"
        type="error"
        show-icon
        closable
        class="error-alert"
        @close="containersStore.error = null"
      />

      <!-- Containers Table -->
      <el-table
        v-loading="containersStore.loading"
        :data="containersStore.containers"
        :empty-text="emptyText"
        stripe
        class="containers-table"
      >
        <el-table-column
          prop="name"
          label="Nom"
          min-width="180"
        >
          <template #default="{ row }">
            <router-link
              :to="`/containers/${row.id}`"
              class="container-name-link"
            >
              {{ row.name }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column
          prop="image"
          label="Image"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tooltip
              :content="row.imageId"
              placement="top"
            >
              <span class="image-name">{{ row.image }}</span>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column
          prop="state"
          label="Statut"
          width="140"
        >
          <template #default="{ row }">
            <StatusBadge :status="mapContainerState(row.state)" />
          </template>
        </el-table-column>

        <el-table-column
          prop="status"
          label="État"
          min-width="140"
        >
          <template #default="{ row }">
            <span class="status-text">{{ row.status }}</span>
          </template>
        </el-table-column>

        <el-table-column
          prop="ports"
          label="Ports"
          min-width="180"
        >
          <template #default="{ row }">
            <div
              v-if="row.ports && row.ports.length > 0"
              class="ports-list"
            >
              <el-tag
                v-for="(port, index) in row.ports.slice(0, 3)"
                :key="index"
                size="small"
                class="port-tag"
              >
                {{ formatPort(port) }}
              </el-tag>
              <el-tag
                v-if="row.ports.length > 3"
                size="small"
                type="info"
              >
                +{{ row.ports.length - 3 }}
              </el-tag>
            </div>
            <span
              v-else
              class="no-ports"
            >-</span>
          </template>
        </el-table-column>

        <el-table-column
          label="Actions"
          width="200"
          fixed="right"
        >
          <template #default="{ row }">
            <ActionButtons
              :actions="getContainerActions(row)"
              @action="handleAction($event, row)"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Logs Drawer -->
    <el-drawer
      v-model="logsDrawerVisible"
      :title="`Logs - ${selectedContainer?.name || ''}`"
      direction="rtl"
      size="50%"
    >
      <div class="logs-container">
        <div class="logs-actions">
          <el-button
            size="small"
            @click="refreshLogs"
          >
            <el-icon class="el-icon--left">
              <Refresh />
            </el-icon>
            Rafraîchir
          </el-button>
          <el-input-number
            v-model="logsTail"
            :min="10"
            :max="10000"
            size="small"
            class="logs-tail-input"
          />
          <span class="logs-tail-label">lignes</span>
        </div>
        <el-input
          v-model="logsContent"
          type="textarea"
          :rows="25"
          readonly
          class="logs-textarea"
        />
      </div>
    </el-drawer>

    <!-- Delete Confirmation Dialog -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="Confirmer la suppression"
      width="400px"
    >
      <p>Voulez-vous vraiment supprimer le container <strong>{{ containerToDelete?.name }}</strong> ?</p>
      <el-checkbox v-model="forceDelete">
        Forcer la suppression
      </el-checkbox>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="danger"
          :loading="deleting"
          @click="confirmDelete"
        >
          Supprimer
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useContainersStore } from '@/stores'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import type { Container, ContainerPort, StatusType } from '@/types/api'

const router = useRouter()
const containersStore = useContainersStore()

// Logs drawer state
const logsDrawerVisible = ref(false)
const selectedContainer = ref<Container | null>(null)
const logsContent = ref('')
const logsTail = ref(100)

// Delete dialog state
const deleteDialogVisible = ref(false)
const containerToDelete = ref<Container | null>(null)
const forceDelete = ref(false)
const deleting = ref(false)

// Computed
const emptyText = computed(() => {
  if (containersStore.loading) return 'Chargement...'
  if (containersStore.error) return 'Erreur lors du chargement'
  return 'Aucun container trouvé'
})

// Methods
function mapContainerState(state: string): StatusType {
  const stateMap: Record<string, StatusType> = {
    running: 'running',
    exited: 'stopped',
    paused: 'pending',
    restarting: 'deploying',
    created: 'draft',
    dead: 'error',
  }
  return stateMap[state] || 'offline'
}

function formatPort(port: ContainerPort): string {
  if (port.PublicPort && port.PrivatePort) {
    return `${port.IP || '0.0.0.0'}:${port.PublicPort}->${port.PrivatePort}/${port.Type || 'tcp'}`
  }
  if (port.PrivatePort) {
    return `${port.PrivatePort}/${port.Type || 'tcp'}`
  }
  return ''
}

function getContainerActions(container: Container) {
  const isRunning = container.state === 'running'
  const isStopped = container.state === 'exited' || container.state === 'created'

  return [
    { type: 'start' as ActionType, disabled: !isStopped },
    { type: 'stop' as ActionType, disabled: !isRunning },
    { type: 'restart' as ActionType, disabled: !isRunning },
    { type: 'logs' as ActionType },
    { type: 'delete' as ActionType },
  ]
}

async function handleAction(action: ActionType, container: Container) {
  switch (action) {
    case 'start':
      await startContainer(container)
      break
    case 'stop':
      await stopContainer(container)
      break
    case 'restart':
      await restartContainer(container)
      break
    case 'logs':
      await showLogs(container)
      break
    case 'delete':
      showDeleteDialog(container)
      break
  }
}

async function startContainer(container: Container) {
  try {
    await containersStore.startContainer(container.id)
    ElMessage.success(`Container "${container.name}" démarré`)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors du démarrage'
    ElMessage.error(message)
  }
}

async function stopContainer(container: Container) {
  try {
    await containersStore.stopContainer(container.id)
    ElMessage.success(`Container "${container.name}" arrêté`)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de l\'arrêt'
    ElMessage.error(message)
  }
}

async function restartContainer(container: Container) {
  try {
    await containersStore.restartContainer(container.id)
    ElMessage.success(`Container "${container.name}" redémarré`)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors du redémarrage'
    ElMessage.error(message)
  }
}

async function showLogs(container: Container) {
  selectedContainer.value = container
  logsDrawerVisible.value = true
  await refreshLogs()
}

async function refreshLogs() {
  if (!selectedContainer.value) return

  try {
    logsContent.value = await containersStore.getContainerLogs(selectedContainer.value.id, logsTail.value)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors du chargement des logs'
    ElMessage.error(message)
    logsContent.value = ''
  }
}

function showDeleteDialog(container: Container) {
  containerToDelete.value = container
  forceDelete.value = false
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  if (!containerToDelete.value) return

  deleting.value = true
  try {
    await containersStore.removeContainer(containerToDelete.value.id, forceDelete.value)
    ElMessage.success(`Container "${containerToDelete.value.name}" supprimé`)
    deleteDialogVisible.value = false
    containerToDelete.value = null
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la suppression'
    ElMessage.error(message)
  } finally {
    deleting.value = false
  }
}

async function refreshContainers() {
  try {
    await containersStore.fetchContainers()
  } catch {
    // Error is already handled in the store
  }
}

// Navigate to container detail (handled by router-link in template)

// Lifecycle
onMounted(() => {
  refreshContainers()
})
</script>

<style scoped>
.containers-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.subtitle {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.counter-badge {
  margin-right: 8px;
}

.error-alert {
  margin-bottom: 16px;
}

.containers-table {
  width: 100%;
}

.container-name-link {
  color: var(--el-color-primary);
  text-decoration: none;
  font-weight: 500;
}

.container-name-link:hover {
  text-decoration: underline;
}

.image-name {
  font-family: monospace;
  font-size: 13px;
}

.status-text {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.ports-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.port-tag {
  font-family: monospace;
  font-size: 11px;
}

.no-ports {
  color: var(--el-text-color-placeholder);
}

/* Logs Drawer */
.logs-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.logs-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.logs-tail-input {
  width: 100px;
}

.logs-tail-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.logs-textarea :deep(textarea) {
  font-family: monospace;
  font-size: 12px;
  line-height: 1.5;
  background-color: #1e1e1e;
  color: #d4d4d4;
}
</style>
