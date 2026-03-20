<template>
  <div class="container-processes">
    <!-- Header with controls -->
    <div class="processes-header">
      <div class="processes-count">
        <el-tag
          v-if="processes.length > 0"
          type="info"
          size="small"
        >
          {{ processes.length }} processus{{ processes.length > 1 ? 's' : '' }}
        </el-tag>
      </div>

      <div class="processes-controls">
        <el-switch
          v-model="localAutoRefresh"
          size="small"
          active-text="Auto"
          inactive-text="Manual"
        />
        <el-button
          size="small"
          :loading="loading"
          @click="handleRefresh"
        >
          <el-icon><RefreshRight /></el-icon>
          Rafraîchir
        </el-button>
      </div>
    </div>

    <!-- Error alert -->
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      @close="clearError"
    />

    <!-- Loading state -->
    <div
      v-if="loading && processes.length === 0"
      class="processes-loading"
    >
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>Chargement des processus...</span>
    </div>

    <!-- Empty state -->
    <el-empty
      v-else-if="!loading && processes.length === 0"
      description="Aucun processus en cours d'exécution"
    />

    <!-- Processes table -->
    <el-table
      v-else
      :data="processes"
      stripe
      size="small"
      :max-height="500"
    >
      <el-table-column
        prop="pid"
        label="PID"
        width="100"
        fixed
      >
        <template #default="{ row }">
          <code>{{ row.pid }}</code>
        </template>
      </el-table-column>
      <el-table-column
        prop="user"
        label="USER"
        width="120"
      >
        <template #default="{ row }">
          <span>{{ row.user || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="cpu"
        label="%CPU"
        width="100"
        align="right"
      >
        <template #default="{ row }">
          <el-tag
            :type="getCpuTagType(row.cpu)"
            size="small"
          >
            {{ row.cpu.toFixed(1) }}%
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="mem"
        label="%MEM"
        width="100"
        align="right"
      >
        <template #default="{ row }">
          <el-tag
            :type="getMemTagType(row.mem)"
            size="small"
          >
            {{ row.mem.toFixed(1) }}%
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="time"
        label="TIME"
        width="120"
      >
        <template #default="{ row }">
          <span class="mono">{{ row.time || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="command"
        label="COMMAND"
        min-width="200"
      >
        <template #default="{ row }">
          <el-tooltip
            :content="row.command"
            placement="top"
            :show-after="500"
          >
            <code class="command-cell">{{ truncateCommand(row.command) }}</code>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <!-- Timestamp -->
    <div
      v-if="timestamp"
      class="processes-timestamp"
    >
      <el-icon><Clock /></el-icon>
      <span>Dernière mise à jour : {{ formatTimestamp(timestamp) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { RefreshRight, Loading, Clock } from '@element-plus/icons-vue'
import { useContainerProcesses } from '@/composables/useContainerProcesses'
import type { ContainerProcess } from '@/types/api'

// Props
const props = defineProps<{
  containerId: string
  containerName?: string
}>()

// Local auto-refresh state (synced with composable)
const localAutoRefresh = ref(false)

// Use the composable
const {
  processes,
  loading,
  error,
  timestamp,
  autoRefresh,
  fetchProcesses,
  startAutoRefresh,
  stopAutoRefresh,
} = useContainerProcesses({
  containerId: props.containerId,
  autoRefresh: false,
})

// Sync local switch with composable
watch(localAutoRefresh, (newValue) => {
  if (newValue) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

watch(autoRefresh, (newValue) => {
  localAutoRefresh.value = newValue
})

// Initial fetch
onMounted(() => {
  fetchProcesses()
})

// Cleanup on unmount
onUnmounted(() => {
  stopAutoRefresh()
})

// Methods
function getCpuTagType(cpu: number): 'success' | 'warning' | 'danger' | 'info' {
  if (cpu >= 80) return 'danger'
  if (cpu >= 50) return 'warning'
  if (cpu >= 20) return 'success'
  return 'info'
}

function getMemTagType(mem: number): 'success' | 'warning' | 'danger' | 'info' {
  if (mem >= 80) return 'danger'
  if (mem >= 50) return 'warning'
  if (mem >= 20) return 'success'
  return 'info'
}

function truncateCommand(command: string): string {
  if (!command) return '-'
  if (command.length <= 60) return command
  return command.substring(0, 57) + '...'
}

function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return timestamp
  }
}

async function handleRefresh(): Promise<void> {
  await fetchProcesses()
}

function clearError(): void {
  error.value = null
}
</script>

<style scoped>
.container-processes {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 300px;
}

.processes-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.processes-count {
  display: flex;
  align-items: center;
  gap: 8px;
}

.processes-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.processes-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 200px;
  color: var(--el-text-color-secondary);
}

.processes-timestamp {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  border-top: 1px solid var(--el-border-color-lighter);
}

.command-cell {
  font-family: monospace;
  font-size: 12px;
  color: var(--el-text-color-primary);
  word-break: break-all;
}

.mono {
  font-family: monospace;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .processes-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .processes-controls {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
