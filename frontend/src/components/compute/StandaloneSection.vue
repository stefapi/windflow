<template>
  <div class="section mb-6">
    <div class="section-header mb-3 flex items-center gap-2">
      <span class="inline-block w-3 h-3 rounded-sm bg-gray-400" />
      <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
        STANDALONE
        <span class="text-gray-400 font-normal">(containers individuels sans composition, créés directement)</span>
      </span>
    </div>

    <!-- Empty -->
    <el-empty
      v-if="!loading && containers.length === 0"
      description="Aucun container standalone"
    />

    <template v-else-if="containers.length > 0">
      <!-- Bulk Actions Bar -->
      <BulkActionBar
        :selected-count="selectedIds.length"
        :loading-action="bulkActionLoading"
        @start="handleBulkAction('start')"
        @stop="handleBulkAction('stop')"
        @restart="handleBulkAction('restart')"
        @delete="showBulkDeleteDialog"
        @cancel="clearSelection"
      />

      <!-- Container Table -->
      <ContainerTable
        ref="tableRef"
        :items="tableRows"
        :columns="['name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions']"
        :selectable="true"
        :show-actions="true"
        @action="handleAction"
        @selection-change="handleSelectionChange"
      />

      <!-- Bulk Delete Dialog -->
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
            Vous êtes sur le point de supprimer <strong>{{ selectedIds.length }}</strong> container{{ selectedIds.length > 1 ? 's' : '' }}.
          </template>
        </el-alert>
        <div class="bulk-delete-list">
          <p>Containers concernés :</p>
          <ul>
            <li
              v-for="id in selectedIds.slice(0, 5)"
              :key="id"
            >
              {{ getContainerName(id) }}
            </li>
            <li
              v-if="selectedIds.length > 5"
              class="more-items"
            >
              ... et {{ selectedIds.length - 5 }} autre{{ selectedIds.length - 5 > 1 ? 's' : '' }}
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
            Supprimer {{ selectedIds.length }} container{{ selectedIds.length > 1 ? 's' : '' }}
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * StandaloneSection Component
 *
 * Displays standalone containers with selection, individual actions,
 * bulk actions bar, and bulk delete dialog.
 */

import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { containersApi } from '@/services/api'
import ContainerTable from './ContainerTable.vue'
import BulkActionBar from './BulkActionBar.vue'
import { standaloneToRow, getActionPastParticiple } from './helpers'
import type { ContainerTableRow } from './helpers'
import type { StandaloneContainer } from '@/types/api'
import type { ActionType } from '@/components/ui/ActionButtons.vue'

export interface StandaloneSectionProps {
  containers: StandaloneContainer[]
  loading: boolean
}

const props = defineProps<StandaloneSectionProps>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const router = useRouter()

// Table ref — typed as any to avoid generic constraint issues with defineExpose
const tableRef = ref<{ clearSelection: () => void }>()

// Computed table rows — stable references for el-table row-key
const tableRows = computed(() => props.containers.map(standaloneToRow))

// Selection state
const selectedContainers = ref<ContainerTableRow[]>([])
const selectedIds = computed(() => selectedContainers.value.map(c => c.id))

// Bulk action state
const bulkActionLoading = ref<string | null>(null)
const bulkDeleteDialogVisible = ref(false)
const bulkForceDelete = ref(false)
const bulkDeleting = ref(false)

function handleSelectionChange(selection: ContainerTableRow[]): void {
  selectedContainers.value = selection
}

function clearSelection(): void {
  tableRef.value?.clearSelection()
  selectedContainers.value = []
}

function getContainerName(id: string): string {
  const container = props.containers.find(c => c.id === id)
  return container?.name || id
}

// Individual actions
async function handleAction(type: ActionType, item: ContainerTableRow): Promise<void> {
  switch (type) {
    case 'start':
      try {
        await containersApi.start(item.id)
        ElMessage.success('Container démarré')
        emit('refresh')
      } catch {
        ElMessage.error('Erreur lors du démarrage du container')
      }
      break
    case 'stop':
      try {
        await containersApi.stop(item.id)
        ElMessage.success(`Container "${item.name}" arrêté`)
        emit('refresh')
      } catch {
        ElMessage.error("Erreur lors de l'arrêt du container")
      }
      break
    case 'restart':
      try {
        await containersApi.restart(item.id)
        ElMessage.success(`Container "${item.name}" redémarré`)
        emit('refresh')
      } catch {
        ElMessage.error('Erreur lors du redémarrage du container')
      }
      break
    case 'logs':
      router.push(`/containers/${item.id}`)
      break
    case 'delete':
      try {
        await ElMessageBox.confirm(
          'Supprimer ce container ? Cette action est irréversible.',
          'Confirmation',
          { confirmButtonText: 'Supprimer', cancelButtonText: 'Annuler', type: 'warning' },
        )
        await containersApi.remove(item.id)
        ElMessage.success('Container supprimé')
        emit('refresh')
      } catch (err) {
        if (err !== 'cancel') {
          ElMessage.error('Erreur lors de la suppression du container')
        }
      }
      break
  }
}

// Bulk actions
async function handleBulkAction(action: 'start' | 'stop' | 'restart' | 'delete'): Promise<void> {
  if (action === 'delete') {
    showBulkDeleteDialog()
    return
  }

  bulkActionLoading.value = action

  try {
    const ids = selectedIds.value
    let successCount = 0
    let failCount = 0

    for (const id of ids) {
      try {
        switch (action) {
          case 'start':
            await containersApi.start(id)
            break
          case 'stop':
            await containersApi.stop(id)
            break
          case 'restart':
            await containersApi.restart(id)
            break
        }
        successCount++
      } catch {
        failCount++
      }
    }

    if (failCount === 0) {
      ElMessage.success(`${successCount} container${successCount > 1 ? 's' : ''} ${getActionPastParticiple(action)}`)
    } else if (successCount === 0) {
      ElMessage.error(`Échec de l'action sur ${failCount} container${failCount > 1 ? 's' : ''}`)
    } else {
      ElMessage.warning(`${successCount} réussi${successCount > 1 ? 's' : ''}, ${failCount} échoué${failCount > 1 ? 's' : ''}`)
    }

    clearSelection()
    emit('refresh')
  } catch (error) {
    const message = error instanceof Error ? error.message : "Erreur lors de l'action groupée"
    ElMessage.error(message)
  } finally {
    bulkActionLoading.value = null
  }
}

function showBulkDeleteDialog(): void {
  bulkForceDelete.value = false
  bulkDeleteDialogVisible.value = true
}

async function confirmBulkDelete(): Promise<void> {
  bulkDeleting.value = true

  try {
    const ids = selectedIds.value
    let successCount = 0
    let failCount = 0

    for (const id of ids) {
      try {
        await containersApi.remove(id, bulkForceDelete.value)
        successCount++
      } catch {
        failCount++
      }
    }

    if (failCount === 0) {
      ElMessage.success(`${successCount} container${successCount > 1 ? 's' : ''} supprimé${successCount > 1 ? 's' : ''}`)
    } else if (successCount === 0) {
      ElMessage.error(`Échec de la suppression de ${failCount} container${failCount > 1 ? 's' : ''}`)
    } else {
      ElMessage.warning(`${successCount} supprimé${successCount > 1 ? 's' : ''}, ${failCount} échoué${failCount > 1 ? 's' : ''}`)
    }

    bulkDeleteDialogVisible.value = false
    clearSelection()
    emit('refresh')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la suppression groupée'
    ElMessage.error(message)
  } finally {
    bulkDeleting.value = false
  }
}
</script>

<style scoped>
.section-header {
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

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

:deep(.el-icon--left) {
  margin-right: 6px;
}
</style>
