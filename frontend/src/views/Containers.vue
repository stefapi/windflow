<template>
  <div class="p-0">
    <!-- Header -->
    <el-card class="mb-5">
      <template #header>
        <div class="flex justify-between items-center">
          <div class="flex flex-col gap-1">
            <span class="text-xl font-semibold text-[var(--color-text-primary)]">Containers</span>
            <span class="text-sm text-[var(--color-text-secondary)]">Gestion des containers Docker</span>
          </div>
          <div class="flex items-center gap-3">
            <el-badge
              :value="containersStore.runningContainers.length"
              type="success"
            >
              <el-tag type="success">
                Running
              </el-tag>
            </el-badge>
            <el-badge
              :value="containersStore.stoppedContainers.length"
              type="info"
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
        class="mb-4"
        @close="containersStore.error = null"
      />

      <!-- Filters Bar -->
      <div class="flex justify-between items-center mb-4 px-4 py-3 bg-[var(--color-bg-secondary)] rounded-lg">
        <div class="flex items-center gap-3">
          <el-select
            v-model="filters.status.value"
            placeholder="Statut"
            clearable
            class="w-35"
            @change="onFilterChange"
          >
            <el-option
              label="Tous"
              value="all"
            />
            <el-option
              label="Running"
              value="running"
            />
            <el-option
              label="Stopped"
              value="stopped"
            />
            <el-option
              label="Error"
              value="error"
            />
          </el-select>

          <el-input
            v-model="filters.search.value"
            placeholder="Rechercher par nom..."
            clearable
            class="w-62"
            @input="onSearchInput"
          >
            <template #prefix>
              <el-icon>
                <Search />
              </el-icon>
            </template>
          </el-input>

          <el-button
            v-if="filters.hasActiveFilters.value"
            text
            @click="clearFilters"
          >
            Effacer les filtres
          </el-button>
        </div>

        <div class="flex items-center gap-3">
          <span class="text-sm text-[var(--color-text-secondary)]">
            {{ resultsCountText }}
          </span>
        </div>
      </div>

      <!-- Bulk Actions Bar -->
      <transition name="slide-down">
        <div
          v-if="selectedContainerIds.length > 0"
          class="flex justify-between items-center px-4 py-3 mb-4 bg-[var(--color-accent-light)] border border-[var(--color-accent)] rounded-lg"
        >
          <div class="flex items-center gap-3">
            <el-tag
              type="primary"
              effect="dark"
            >
              {{ selectedContainerIds.length }} sélectionné{{ selectedContainerIds.length > 1 ? 's' : '' }}
            </el-tag>
            <el-button
              text
              size="small"
              @click="clearSelection"
            >
              Annuler la sélection
            </el-button>
          </div>
          <div class="flex items-center gap-2">
            <el-button
              size="small"
              :loading="bulkActionLoading === 'start'"
              @click="handleBulkAction('start')"
            >
              <el-icon class="el-icon--left">
                <VideoPlay />
              </el-icon>
              Démarrer
            </el-button>
            <el-button
              size="small"
              :loading="bulkActionLoading === 'stop'"
              @click="handleBulkAction('stop')"
            >
              <el-icon class="el-icon--left">
                <VideoPause />
              </el-icon>
              Arrêter
            </el-button>
            <el-button
              size="small"
              :loading="bulkActionLoading === 'restart'"
              @click="handleBulkAction('restart')"
            >
              <el-icon class="el-icon--left">
                <RefreshRight />
              </el-icon>
              Redémarrer
            </el-button>
            <el-button
              type="danger"
              size="small"
              :loading="bulkActionLoading === 'delete'"
              @click="showBulkDeleteDialog"
            >
              <el-icon class="el-icon--left">
                <Delete />
              </el-icon>
              Supprimer
            </el-button>
          </div>
        </div>
      </transition>

      <!-- Containers Table -->
      <el-table
        ref="tableRef"
        v-loading="containersStore.loading"
        :data="filteredContainers"
        :empty-text="emptyText"
        stripe
        class="w-full"
        @selection-change="handleSelectionChange"
      >
        <el-table-column
          type="selection"
          width="55"
        />

        <el-table-column
          prop="name"
          label="Nom"
          min-width="180"
        >
          <template #default="{ row }">
            <router-link
              :to="`/containers/${row.id}`"
              class="text-[var(--color-accent)] no-underline font-medium hover:underline"
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
              <span class="font-mono text-xs">{{ row.image }}</span>
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
            <span class="text-xs text-[var(--color-text-secondary)]">{{ row.status }}</span>
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
              class="flex flex-wrap gap-1"
            >
              <el-tag
                v-for="(port, index) in row.ports.slice(0, 3)"
                :key="index"
                size="small"
                class="font-mono text-[11px]"
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
              class="text-[var(--color-text-muted)]"
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
      class="logs-drawer"
    >
      <ContainerLogs
        v-if="logsDrawerVisible && selectedContainer"
        :key="selectedContainer.id"
        :container-id="selectedContainer.id"
        :container-name="selectedContainer.name"
      />
    </el-drawer>

    <!-- Delete Confirmation Dialog (single) -->
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

    <!-- Bulk Delete Confirmation Dialog -->
    <el-dialog
      v-model="bulkDeleteDialogVisible"
      title="Confirmer la suppression groupée"
      width="500px"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="bulk-delete-alert"
      >
        <template #title>
          Vous êtes sur le point de supprimer <strong>{{ selectedContainerIds.length }}</strong> container{{ selectedContainerIds.length > 1 ? 's' : '' }}.
        </template>
      </el-alert>
      <div class="bulk-delete-list">
        <p>Containers concernés :</p>
        <ul>
          <li
            v-for="id in selectedContainerIds.slice(0, 5)"
            :key="id"
          >
            {{ getContainerName(id) }}
          </li>
          <li
            v-if="selectedContainerIds.length > 5"
            class="more-items"
          >
            ... et {{ selectedContainerIds.length - 5 }} autre{{ selectedContainerIds.length - 5 > 1 ? 's' : '' }}
          </li>
        </ul>
      </div>
      <el-checkbox v-model="bulkForceDelete">
        Forcer la suppression
      </el-checkbox>
      <template #footer>
        <el-button @click="bulkDeleteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="danger"
          :loading="bulkDeleting"
          @click="confirmBulkDelete"
        >
          Supprimer {{ selectedContainerIds.length }} container{{ selectedContainerIds.length > 1 ? 's' : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh,
  Search,
  VideoPlay,
  VideoPause,
  RefreshRight,
  Delete,
} from '@element-plus/icons-vue'
import { useContainersStore } from '@/stores'
import { useUrlFilters } from '@/composables/useUrlFilters'
import StatusBadge, { type StatusType } from '@/components/ui/StatusBadge.vue'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import ContainerLogs from '@/components/ContainerLogs.vue'
import type { Container, ContainerPort } from '@/types/api'
const containersStore = useContainersStore()

// URL Filters
const filters = useUrlFilters(300)

// Table ref for selection
const tableRef = ref()

// Selection state
const selectedContainers = ref<Container[]>([])
const selectedContainerIds = computed(() => selectedContainers.value.map(c => c.id))

// Bulk action state
const bulkActionLoading = ref<string | null>(null)
const bulkDeleteDialogVisible = ref(false)
const bulkForceDelete = ref(false)
const bulkDeleting = ref(false)

// Logs drawer state
const logsDrawerVisible = ref(false)
const selectedContainer = ref<Container | null>(null)

// Delete dialog state (single)
const deleteDialogVisible = ref(false)
const containerToDelete = ref<Container | null>(null)
const forceDelete = ref(false)
const deleting = ref(false)

// Filtered containers
const filteredContainers = computed(() => {
  let result = containersStore.containers

  // Filter by status
  const statusFilter = filters.status.value
  if (statusFilter !== 'all') {
    result = result.filter(container => {
      if (statusFilter === 'running') {
        return container.state === 'running'
      }
      if (statusFilter === 'stopped') {
        return ['exited', 'created', 'dead'].includes(container.state)
      }
      if (statusFilter === 'error') {
        return container.state === 'dead'
      }
      return true
    })
  }

  // Filter by search
  const searchTerm = filters.debouncedSearch.value.toLowerCase().trim()
  if (searchTerm) {
    result = result.filter(container =>
      container.name.toLowerCase().includes(searchTerm) ||
      container.image.toLowerCase().includes(searchTerm)
    )
  }

  return result
})

// Results count text
const resultsCountText = computed(() => {
  const total = containersStore.containers.length
  const filtered = filteredContainers.value.length

  if (filters.hasActiveFilters.value && filtered !== total) {
    return `${filtered} containers (sur ${total})`
  }
  return `${total} containers`
})

// Computed
const emptyText = computed(() => {
  if (containersStore.loading) return 'Chargement...'
  if (containersStore.error) return 'Erreur lors du chargement'
  if (filters.hasActiveFilters.value) return 'Aucun container ne correspond aux filtres'
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

function getContainerName(id: string): string {
  const container = containersStore.containers.find(c => c.id === id)
  return container?.name || id
}

// Filter handlers
function onFilterChange(): void {
  // Filters are automatically synced via useUrlFilters
}

function onSearchInput(): void {
  // Search is debounced via useUrlFilters
}

function clearFilters(): void {
  filters.resetFilters()
}

// Selection handlers
function handleSelectionChange(selection: Container[]): void {
  selectedContainers.value = selection
}

function clearSelection(): void {
  tableRef.value?.clearSelection()
  selectedContainers.value = []
}

// Single container actions
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
      showLogs(container)
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

function showLogs(container: Container) {
  selectedContainer.value = container
  logsDrawerVisible.value = true
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

// Bulk actions
async function handleBulkAction(action: 'start' | 'stop' | 'restart' | 'delete') {
  if (action === 'delete') {
    showBulkDeleteDialog()
    return
  }

  bulkActionLoading.value = action

  try {
    const ids = selectedContainerIds.value
    let result: { success: string[]; failed: string[] }

    switch (action) {
      case 'start':
        result = await containersStore.startContainers(ids)
        break
      case 'stop':
        result = await containersStore.stopContainers(ids)
        break
      case 'restart':
        result = await containersStore.restartContainers(ids)
        break
      default:
        return
    }

    // Show result message
    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} container${result.success.length > 1 ? 's' : ''} ${getActionPastParticiple(action)}`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de l'action sur ${result.failed.length} container${result.failed.length > 1 ? 's' : ''}`)
    } else {
      ElMessage.warning(`${result.success.length} réussi${result.success.length > 1 ? 's' : ''}, ${result.failed.length} échoué${result.failed.length > 1 ? 's' : ''}`)
    }

    clearSelection()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de l\'action groupée'
    ElMessage.error(message)
  } finally {
    bulkActionLoading.value = null
  }
}

function getActionPastParticiple(action: 'start' | 'stop' | 'restart'): string {
  const map: Record<string, string> = {
    start: 'démarré(s)',
    stop: 'arrêté(s)',
    restart: 'redémarré(s)',
  }
  return map[action] || action
}

function showBulkDeleteDialog(): void {
  bulkForceDelete.value = false
  bulkDeleteDialogVisible.value = true
}

async function confirmBulkDelete(): Promise<void> {
  bulkDeleting.value = true

  try {
    const result = await containersStore.removeContainers(selectedContainerIds.value, bulkForceDelete.value)

    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} container${result.success.length > 1 ? 's' : ''} supprimé${result.success.length > 1 ? 's' : ''}`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de la suppression de ${result.failed.length} container${result.failed.length > 1 ? 's' : ''}`)
    } else {
      ElMessage.warning(`${result.success.length} supprimé${result.success.length > 1 ? 's' : ''}, ${result.failed.length} échoué${result.failed.length > 1 ? 's' : ''}`)
    }

    bulkDeleteDialogVisible.value = false
    clearSelection()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la suppression groupée'
    ElMessage.error(message)
  } finally {
    bulkDeleting.value = false
  }
}

async function refreshContainers() {
  try {
    await containersStore.fetchContainers()
  } catch {
    // Error is already handled in the store
  }
}

// Lifecycle
onMounted(() => {
  refreshContainers()
})
</script>

<style scoped>
/* Slide down transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Logs Drawer */
.logs-drawer :deep(.el-drawer__body) {
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Bulk Delete Dialog */
.bulk-delete-alert {
  margin-bottom: 16px;
}

.bulk-delete-list {
  margin-bottom: 16px;
}

.bulk-delete-list p {
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--color-text-primary);
}

.bulk-delete-list ul {
  margin: 0;
  padding-left: 20px;
  max-height: 150px;
  overflow-y: auto;
}

.bulk-delete-list li {
  margin-bottom: 4px;
  color: var(--color-text-primary);
}

.bulk-delete-list .more-items {
  font-style: italic;
  color: var(--color-text-secondary);
}
</style>
