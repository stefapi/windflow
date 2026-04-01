<template>
  <div class="section mb-6">
    <div class="section-header border-b border-border py-2 mb-3 flex items-center gap-2">
      <span class="inline-block w-3 h-3 rounded-sm bg-blue-600" />
      <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
        STACKS WINDFLOW
        <span class="text-gray-400 font-normal">(managées, source of truth dans WindFlow)</span>
      </span>
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="flex justify-center py-8"
    >
      <el-icon class="is-loading text-2xl text-blue-500">
        <Loading />
      </el-icon>
    </div>

    <!-- Empty -->
    <el-empty
      v-else-if="stacks.length === 0"
      description="Aucune stack WindFlow avec des instances actives"
    />

    <!-- Stacks collapse -->
    <el-collapse
      v-else
      class="stacks-collapse"
    >
      <el-collapse-item
        v-for="stack in stacks"
        :key="stack.id"
        :name="stack.id"
      >
        <template #title>
          <div class="flex flex-wrap items-center gap-2 w-full pr-4">
            <span class="font-semibold text-sm">{{ stack.name }}</span>
            <el-tag
              type="primary"
              size="small"
            >
              stack WindFlow
            </el-tag>
            <el-tag size="small">
              {{ stack.technology }}
            </el-tag>
            <el-tag
              size="small"
              type="info"
            >
              ● {{ stack.target_name }}
            </el-tag>
            <span
              class="text-xs font-semibold"
              :class="servicesRunningClass(stack.services_running, stack.services_total)"
            >
              {{ stack.services_running }}/{{ stack.services_total }} running
            </span>
            <div class="ml-auto flex items-center gap-1">
              <el-button
                size="small"
                text
                title="Copier ID"
                @click.stop="emit('copy-id', stack.id)"
              >
                📄
              </el-button>
              <el-button
                size="small"
                text
                title="Rafraîchir"
                @click.stop="emit('refresh')"
              >
                🔄
              </el-button>
              <el-button
                size="small"
                type="primary"
                @click.stop
              >
                Éditer stack
              </el-button>
            </div>
          </div>
        </template>

        <!-- Stack global actions (STORY-004) -->
        <StackActionsBar
          :stack="stack"
          @action-completed="handleStackActionCompleted"
        />

        <BulkActionBar
          :selected-count="getStackSelectedIds(stack.id).length"
          :loading-action="bulkActionLoading"
          @start="handleBulkAction('start', stack.id)"
          @stop="handleBulkAction('stop', stack.id)"
          @restart="handleBulkAction('restart', stack.id)"
          @delete="handleBulkAction('delete', stack.id)"
          @cancel="clearStackSelection(stack.id)"
        />

        <ContainerTable
          :ref="(el: any) => setTableRef(stack.id, el)"
          :items="stackRowsMap[stack.id] ?? []"
          :columns="['name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions']"
          :selectable="true"
          :show-actions="true"
          @action="(type, item) => handleServiceAction(type, item)"
          @selection-change="(items: ContainerTableRow[]) => handleStackSelectionChange(stack.id, items)"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
/**
 * ManagedStacksSection Component
 *
 * Displays managed WindFlow stacks in a collapsible list.
 * Each stack shows its services in a ContainerTable with individual actions.
 */

import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { containersApi } from '@/services/api'
import ContainerTable from './ContainerTable.vue'
import BulkActionBar from './BulkActionBar.vue'
import StackActionsBar from './StackActionsBar.vue'
import { serviceToRow, servicesRunningClass, getActionPastParticiple } from './helpers'
import type { ContainerTableRow } from './helpers'
import type { StackWithServices } from '@/types/api'
import type { ActionType } from '@/components/ui/ActionButtons.vue'

export interface ManagedStacksSectionProps {
  stacks: StackWithServices[]
  loading: boolean
}

const props = defineProps<ManagedStacksSectionProps>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'copy-id', id: string): void
}>()

const router = useRouter()

// ── Computed rows per stack (stable references for row-key) ──
const stackRowsMap = computed(() => {
  const map: Record<string, ContainerTableRow[]> = {}
  for (const stack of props.stacks) {
    map[stack.id] = stack.services.map(s => serviceToRow(s, stack.target_name))
  }
  return map
})

// ── Per-stack selection state ──
const stackSelections = ref<Record<string, ContainerTableRow[]>>({})
const tableRefs = ref<Record<string, { clearSelection: () => void }>>({})
const bulkActionLoading = ref<string | null>(null)

function setTableRef(stackId: string, el: any): void {
  if (el) tableRefs.value[stackId] = el
}

function handleStackSelectionChange(stackId: string, items: ContainerTableRow[]): void {
  stackSelections.value[stackId] = items
}

function getStackSelectedIds(stackId: string): string[] {
  return (stackSelections.value[stackId] ?? []).map(c => c.id)
}

function clearStackSelection(stackId: string): void {
  tableRefs.value[stackId]?.clearSelection()
  stackSelections.value[stackId] = []
}

async function handleBulkAction(action: 'start' | 'stop' | 'restart' | 'delete', stackId: string): Promise<void> {
  const ids = getStackSelectedIds(stackId)
  if (ids.length === 0) return

  if (action === 'delete') {
    try {
      await ElMessageBox.confirm(
        `Supprimer ${ids.length} container${ids.length > 1 ? 's' : ''} ? Cette action est irréversible.`,
        'Confirmation',
        { confirmButtonText: 'Supprimer', cancelButtonText: 'Annuler', type: 'warning' },
      )
    } catch { return }
  }

  bulkActionLoading.value = action
  let successCount = 0
  let failCount = 0

  for (const id of ids) {
    try {
      switch (action) {
        case 'start': await containersApi.start(id); break
        case 'stop': await containersApi.stop(id); break
        case 'restart': await containersApi.restart(id); break
        case 'delete': await containersApi.remove(id); break
      }
      successCount++
    } catch { failCount++ }
  }

  if (failCount === 0) {
    ElMessage.success(`${successCount} container${successCount > 1 ? 's' : ''} ${getActionPastParticiple(action as 'start' | 'stop' | 'restart')}`)
  } else if (successCount === 0) {
    ElMessage.error(`Échec de l'action sur ${failCount} container${failCount > 1 ? 's' : ''}`)
  } else {
    ElMessage.warning(`${successCount} réussi${successCount > 1 ? 's' : ''}, ${failCount} échoué${failCount > 1 ? 's' : ''}`)
  }

  clearStackSelection(stackId)
  bulkActionLoading.value = null
  emit('refresh')
}

/** Callback après une action globale de stack (start/stop/redeploy) */
function handleStackActionCompleted(_stackId: string): void {
  emit('refresh')
}

async function handleServiceAction(type: ActionType, item: ContainerTableRow): Promise<void> {
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
        ElMessage.success('Container arrêté')
        emit('refresh')
      } catch {
        ElMessage.error("Erreur lors de l'arrêt du container")
      }
      break
    case 'restart':
      try {
        await containersApi.restart(item.id)
        ElMessage.success('Container redémarré')
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
</script>

<style scoped>
.stacks-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 44px;
  padding: 8px 16px;
}
</style>
