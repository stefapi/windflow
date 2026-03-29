j'ai<template>
  <el-table
    ref="tableRef"
    :data="items"
    :size="size"
    row-key="id"
    stripe
    class="container-table w-full"
    @selection-change="handleSelectionChange"
  >
    <!-- Selection column -->
    <el-table-column
      v-if="selectable"
      type="selection"
      width="55"
      reserve-selection
    />

    <!-- Name column (always shown) -->
    <el-table-column
      label="Nom"
      min-width="160"
    >
      <template #default="{ row }">
        <router-link
          v-if="row.link"
          :to="row.link"
          class="text-[var(--color-accent)] no-underline font-medium hover:underline"
        >
          <span
            class="mr-1"
            :class="getContainerStatusColor(row.status, row.healthStatus)"
          >●</span>
          {{ row.name }}
        </router-link>
        <span v-else>
          <span
            class="mr-1"
            :class="getContainerStatusColor(row.status, row.healthStatus)"
          >●</span>
          {{ row.name }}
        </span>
      </template>
    </el-table-column>

    <!-- Image column -->
    <el-table-column
      v-if="isVisible('image')"
      prop="image"
      label="Image"
      min-width="180"
    />

    <!-- Target column -->
    <el-table-column
      v-if="isVisible('target')"
      label="Target"
      width="100"
    >
      <template #default="{ row }">
        <el-tag
          v-if="row.targetName"
          size="small"
        >
          {{ row.targetName }}
        </el-tag>
      </template>
    </el-table-column>

    <!-- Status column -->
    <el-table-column
      v-if="isVisible('status')"
      label="Statut"
      width="110"
    >
      <template #default="{ row }">
        <el-tag
          :type="getContainerStatusType(row.status, row.healthStatus)"
          size="small"
        >
          {{ getContainerStatusLabel(row.status, row.healthStatus) }}
        </el-tag>
      </template>
    </el-table-column>

    <!-- CPU column (bar + percentage) -->
    <el-table-column
      v-if="isVisible('cpu')"
      label="CPU"
      width="120"
    >
      <template #default="{ row }">
        <div class="flex items-center gap-1">
          <div class="flex-1 bg-gray-200 rounded h-2">
            <div
              class="h-2 rounded bg-blue-500"
              :style="{ width: Math.min(row.cpuPercent, 100) + '%' }"
            />
          </div>
          <span class="text-xs text-gray-500">{{ row.cpuPercent.toFixed(1) }}%</span>
        </div>
      </template>
    </el-table-column>

    <!-- Memory column -->
    <el-table-column
      v-if="isVisible('memory')"
      label="Mémoire"
      width="80"
    >
      <template #default="{ row }">
        {{ row.memoryUsage }}
      </template>
    </el-table-column>

    <!-- Uptime column -->
    <el-table-column
      v-if="isVisible('uptime')"
      label="Uptime"
      width="120"
      class-name="col-uptime"
    >
      <template #default="{ row }">
        <span
          v-if="row.uptime"
          class="text-xs text-gray-600"
        >
          {{ row.uptime }}
        </span>
        <span
          v-else
          class="text-xs text-gray-400"
        >-</span>
      </template>
    </el-table-column>

    <!-- Ports column -->
    <el-table-column
      v-if="isVisible('ports')"
      label="Ports"
      min-width="140"
      class-name="col-ports"
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
          class="text-xs text-gray-400"
        >-</span>
      </template>
    </el-table-column>

    <!-- Actions column -->
    <el-table-column
      v-if="showActions"
      label="Actions"
      width="140"
      fixed="right"
    >
      <template #default="{ row }">
        <ActionButtons
          :actions="getRowActions(row)"
          @action="(type: ActionType) => emit('action', type, row)"
        />
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
/**
 * ContainerTable Component
 *
 * A unified, reusable table for displaying container data with
 * configurable columns, optional selection, and individual actions.
 */

import { ref, computed } from 'vue'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import {
  getContainerStatusColor,
  getContainerStatusType,
  getContainerStatusLabel,
  formatPort,
} from './helpers'
import type { ContainerTableRow, ColumnKey } from './helpers'

/** Props for ContainerTable */
export interface ContainerTableProps {
  /** Normalized row data */
  items: ContainerTableRow[]
  /** Visible columns (defaults to name, image, status, cpu, memory, actions) */
  columns?: ColumnKey[]
  /** Enable selection mode with checkboxes */
  selectable?: boolean
  /** Show action buttons column */
  showActions?: boolean
  /** Disable all actions (read-only mode) */
  readonly?: boolean
  /** Loading state */
  loading?: boolean
  /** Table size */
  size?: 'small' | 'default'
}

const props = withDefaults(defineProps<ContainerTableProps>(), {
  columns: undefined,
  selectable: false,
  showActions: true,
  readonly: false,
  loading: false,
  size: 'small',
})

const emit = defineEmits<{
  (e: 'action', type: ActionType, item: ContainerTableRow): void
  (e: 'selection-change', items: ContainerTableRow[]): void
}>()

// Table ref — exposed for parent to call clearSelection()
const tableRef = ref<InstanceType<typeof import('element-plus')['ElTable']>>()

/** Resolved columns: use provided or default */
const resolvedColumns = computed<ColumnKey[]>(() =>
  props.columns ?? ['name', 'image', 'status', 'cpu', 'memory', 'actions'],
)

/** Check if a column is visible */
function isVisible(key: ColumnKey): boolean {
  return resolvedColumns.value.includes(key)
}

/** Build action list for a row */
function getRowActions(row: ContainerTableRow): { type: ActionType; disabled?: boolean }[] {
  if (props.readonly) {
    return [{ type: 'logs' as ActionType, disabled: true }]
  }

  const isRunning = row.status === 'running'
  const isStopped = row.status === 'exited' || row.status === 'created'

  return [
    { type: 'start' as ActionType, disabled: !isStopped },
    { type: 'stop' as ActionType, disabled: !isRunning },
    { type: 'restart' as ActionType, disabled: !isRunning },
    { type: 'logs' as ActionType },
    { type: 'delete' as ActionType },
  ]
}

/** Forward selection-change from el-table */
function handleSelectionChange(selection: ContainerTableRow[]): void {
  emit('selection-change', selection)
}

/** Clear table selection — can be called by parent via ref */
function clearSelection(): void {
  tableRef.value?.clearSelection()
}

defineExpose({ clearSelection, tableRef })
</script>

<style scoped>
@media (width <= 768px) {
  .container-table :deep(.col-ports),
  .container-table :deep(.col-uptime) {
    display: none;
  }
}
</style>
