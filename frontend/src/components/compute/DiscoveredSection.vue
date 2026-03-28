<template>
  <div class="section mb-6">
    <div class="section-header mb-3 flex items-center gap-2">
      <span class="inline-block w-3 h-3 rounded-sm bg-orange-500" />
      <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
        DISCOVERED — NON MANAGÉS
        <span class="text-gray-400 font-normal">(détectés sur la machine, WindFlow n'en est pas l'auteur)</span>
      </span>
    </div>

    <!-- Empty -->
    <el-empty
      v-if="!loading && items.length === 0"
      description="Aucun objet découvert avec des instances actives"
    />

    <!-- Discovered items collapse -->
    <el-collapse
      v-else-if="items.length > 0"
      class="discovered-collapse"
    >
      <el-collapse-item
        v-for="item in items"
        :key="item.id"
        :name="item.id"
      >
        <template #title>
          <div class="flex flex-wrap items-center gap-2 w-full pr-4">
            <span class="font-semibold text-sm">{{ item.name }}</span>
            <el-tag
              type="warning"
              size="small"
            >
              discovered
            </el-tag>
            <el-tag size="small">
              {{ item.technology }}
            </el-tag>
            <el-tag
              size="small"
              type="info"
            >
              ● {{ item.target_name }}
            </el-tag>
            <span class="text-xs text-gray-500">
              {{ item.services_running }}/{{ item.services_total }} running
            </span>
            <span class="ml-auto flex items-center gap-1">
              👁
              <el-button
                v-if="item.adoptable"
                size="small"
                type="warning"
                @click.stop="emit('adopt', item.id)"
              >
                ↗ Adopter
              </el-button>
            </span>
          </div>
        </template>

        <el-alert
          v-if="item.source_path"
          type="warning"
          :closable="false"
          class="mb-3"
        >
          ⚠ Détecté via {{ item.source_path }} — lecture seule. Adoptez pour gérer depuis WindFlow.
        </el-alert>

        <BulkActionBar
          v-if="item.adoptable"
          :selected-count="getItemSelectedIds(item.id).length"
          :loading-action="bulkActionLoading"
          @start="handleBulkAction('start', item.id)"
          @stop="handleBulkAction('stop', item.id)"
          @restart="handleBulkAction('restart', item.id)"
          @delete="handleBulkAction('delete', item.id)"
          @cancel="clearItemSelection(item.id)"
        />

        <ContainerTable
          :ref="(el: any) => setTableRef(item.id, el)"
          :items="itemRowsMap[item.id] ?? []"
          :columns="['name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions']"
          :selectable="item.adoptable"
          :readonly="!item.adoptable"
          @action="(type, row) => handleServiceAction(type, row, item)"
          @selection-change="(rows: ContainerTableRow[]) => handleItemSelectionChange(item.id, rows)"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
/**
 * DiscoveredSection Component
 *
 * Displays discovered (unmanaged) items in a collapsible list.
 * Each item shows its services in a ContainerTable.
 * Actions are available only if the item is adoptable.
 */

import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { containersApi } from '@/services/api'
import ContainerTable from './ContainerTable.vue'
import BulkActionBar from './BulkActionBar.vue'
import { serviceToRow, getActionPastParticiple } from './helpers'
import type { ContainerTableRow } from './helpers'
import type { DiscoveredItem } from '@/types/api'
import type { ActionType } from '@/components/ui/ActionButtons.vue'

export interface DiscoveredSectionProps {
  items: DiscoveredItem[]
  loading: boolean
}

const props = defineProps<DiscoveredSectionProps>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'adopt', id: string): void
}>()

const router = useRouter()

// ── Computed rows per item (stable references for row-key) ──
const itemRowsMap = computed(() => {
  const map: Record<string, ContainerTableRow[]> = {}
  for (const item of props.items) {
    map[item.id] = (item.services ?? []).map(s => serviceToRow(s, item.target_name))
  }
  return map
})

// ── Per-item selection state ──
const itemSelections = ref<Record<string, ContainerTableRow[]>>({})
const tableRefs = ref<Record<string, { clearSelection: () => void }>>({})
const bulkActionLoading = ref<string | null>(null)

function setTableRef(itemId: string, el: any): void {
  if (el) tableRefs.value[itemId] = el
}

function handleItemSelectionChange(itemId: string, items: ContainerTableRow[]): void {
  itemSelections.value[itemId] = items
}

function getItemSelectedIds(itemId: string): string[] {
  return (itemSelections.value[itemId] ?? []).map(c => c.id)
}

function clearItemSelection(itemId: string): void {
  tableRefs.value[itemId]?.clearSelection()
  itemSelections.value[itemId] = []
}

async function handleBulkAction(action: 'start' | 'stop' | 'restart' | 'delete', itemId: string): Promise<void> {
  const ids = getItemSelectedIds(itemId)
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

  clearItemSelection(itemId)
  bulkActionLoading.value = null
  emit('refresh')
}

async function handleServiceAction(type: ActionType, row: ContainerTableRow, item: DiscoveredItem): Promise<void> {
  // If not adoptable, only allow navigation
  if (!item.adoptable) {
    if (type === 'logs') {
      router.push(`/containers/${row.id}`)
    }
    return
  }

  switch (type) {
    case 'start':
      try {
        await containersApi.start(row.id)
        ElMessage.success('Container démarré')
        emit('refresh')
      } catch {
        ElMessage.error('Erreur lors du démarrage du container')
      }
      break
    case 'stop':
      try {
        await containersApi.stop(row.id)
        ElMessage.success('Container arrêté')
        emit('refresh')
      } catch {
        ElMessage.error("Erreur lors de l'arrêt du container")
      }
      break
    case 'restart':
      try {
        await containersApi.restart(row.id)
        ElMessage.success('Container redémarré')
        emit('refresh')
      } catch {
        ElMessage.error('Erreur lors du redémarrage du container')
      }
      break
    case 'logs':
      router.push(`/containers/${row.id}`)
      break
    case 'delete':
      try {
        await ElMessageBox.confirm(
          'Supprimer ce container ? Cette action est irréversible.',
          'Confirmation',
          { confirmButtonText: 'Supprimer', cancelButtonText: 'Annuler', type: 'warning' },
        )
        await containersApi.remove(row.id)
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
.section-header {
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.discovered-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 44px;
  padding: 8px 16px;
}
</style>
