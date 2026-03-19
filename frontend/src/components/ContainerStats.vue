<template>
  <div class="container-stats">
    <!-- Header with connection status and controls -->
    <div class="stats-header">
      <div class="stats-status">
        <el-tag
          :type="connectionTagType"
          size="small"
        >
          {{ connectionStatusText }}
        </el-tag>
      </div>

      <div class="stats-controls">
        <el-switch
          v-model="autoRefresh"
          size="small"
          active-text="Auto-refresh"
          inactive-text="Manual"
        />
        <el-button
          size="small"
          @click="handleReconnect"
        >
          <el-icon><RefreshRight /></el-icon>
          Reconnect
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
      v-if="status === 'connecting'"
      class="stats-loading"
    >
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>Connexion en cours...</span>
    </div>

    <!-- Not running state -->
    <div
      v-else-if="!isStreaming"
      class="stats-not-running"
    >
      <el-empty description="Les statistiques ne sont disponibles que lorsque le container est en cours d'exécution" />
    </div>

    <!-- Stats content -->
    <div
      v-else
      class="stats-content"
    >
      <!-- CPU Section -->
      <div class="stat-section">
        <div class="stat-header">
          <el-icon><Cpu /></el-icon>
          <span>CPU</span>
        </div>
        <div class="stat-value">
          <ResourceBar
            :value="stats?.cpu_percent ?? 0"
            label="Utilisation"
            :show-value="true"
          />
        </div>
      </div>

      <!-- Memory Section -->
      <div class="stat-section">
        <div class="stat-header">
          <el-icon><Odometer /></el-icon>
          <span>Mémoire</span>
        </div>
        <div class="stat-value">
          <ResourceBar
            :value="stats?.memory_percent ?? 0"
            label="Utilisation"
            :show-value="true"
          />
          <div class="memory-details">
            {{ formatBytes(stats?.memory_used ?? 0) }} / {{ formatBytes(stats?.memory_limit ?? 1) }}
          </div>
        </div>
      </div>

      <!-- Network I/O Section -->
      <div class="stat-section">
        <div class="stat-header">
          <el-icon><Connection /></el-icon>
          <span>Réseau</span>
        </div>
        <div class="io-grid">
          <div class="io-item">
            <span class="io-label">↓ Reçu</span>
            <span class="io-value">{{ formatBytes(stats?.network_rx_bytes ?? 0) }}</span>
          </div>
          <div class="io-item">
            <span class="io-label">↑ Envoyé</span>
            <span class="io-value">{{ formatBytes(stats?.network_tx_bytes ?? 0) }}</span>
          </div>
        </div>
      </div>

      <!-- Block I/O Section -->
      <div class="stat-section">
        <div class="stat-header">
          <el-icon><Coin /></el-icon>
          <span>Disque</span>
        </div>
        <div class="io-grid">
          <div class="io-item">
            <span class="io-label">Lecture</span>
            <span class="io-value">{{ formatBytes(stats?.block_read_bytes ?? 0) }}</span>
          </div>
          <div class="io-item">
            <span class="io-label">Écriture</span>
            <span class="io-value">{{ formatBytes(stats?.block_write_bytes ?? 0) }}</span>
          </div>
        </div>
      </div>

      <!-- History Charts Section -->
      <div class="history-section">
        <h4>Historique (5 dernières minutes)</h4>
        <div
          v-if="history.length > 0"
          class="history-charts"
        >
          <div class="history-chart">
            <div class="chart-title">CPU %</div>
            <v-chart
              :option="cpuChartOptions"
              class="chart"
              autoresize
            />
          </div>
          <div class="history-chart">
            <div class="chart-title">RAM</div>
            <v-chart
              :option="memoryChartOptions"
              class="chart"
              autoresize
            />
          </div>
        </div>
        <div
          v-else
          class="no-history"
        >
          Collecte de données en cours...
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Loading,
  RefreshRight,
  Cpu,
  Odometer,
  Connection,
  Coin,
} from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { ResourceBar } from '@/components/ui'
import { useContainerStats } from '@/composables/useContainerStats'

// Register ECharts components
use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

// Props
interface Props {
  containerId: string
  containerName?: string
}

const props = defineProps<Props>()

// Use the composable for WebSocket connection
const {
  stats,
  status,
  error,
  isStreaming,
  history,
  reconnect,
} = useContainerStats({
  containerId: props.containerId,
  autoConnect: true,
})

// Auto-refresh state (for manual reconnect)
const autoRefresh = ref(true)

// ECharts options for CPU chart
const cpuChartOptions = computed(() => ({
  grid: {
    left: 40,
    right: 10,
    top: 10,
    bottom: 20,
  },
  xAxis: {
    type: 'category',
    show: false,
    data: history.value.slice(-60).map((_, i) => i),
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 100,
    splitLine: {
      lineStyle: {
        color: 'var(--el-border-color-lighter)',
      },
    },
    axisLabel: {
      color: 'var(--el-text-color-secondary)',
      fontSize: 10,
    },
  },
  tooltip: {
    trigger: 'axis',
    formatter: (params: Array<{ value: number }>) => {
      const value = params[0]?.value ?? 0
      return `CPU: ${value.toFixed(1)}%`
    },
  },
  series: [
    {
      type: 'line',
      data: history.value.slice(-60).map((entry) => entry.cpu_percent),
      smooth: true,
      symbol: 'none',
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64, 158, 255, 0.4)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
          ],
        },
      },
      lineStyle: {
        color: 'var(--el-color-primary)',
        width: 2,
      },
    },
  ],
}))

// Helper to format bytes for chart axis
function formatBytesAxis(value: number): string {
  if (value === 0) return '0'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const base = 1024
  const unitIndex = Math.floor(Math.log(value) / Math.log(base))
  const safeIndex = Math.min(unitIndex, units.length - 1)
  const scaledValue = value / Math.pow(base, safeIndex)
  return `${scaledValue.toFixed(safeIndex > 0 ? 1 : 0)} ${units[safeIndex]}`
}

// Helper to find optimal unit and scale for given max value
function getOptimalScale(maxBytes: number): { divisor: number; unit: string; niceMax: number } {
  if (maxBytes < 1024) return { divisor: 1, unit: 'B', niceMax: Math.ceil(maxBytes) }
  if (maxBytes < 1024 * 1024) return { divisor: 1024, unit: 'KB', niceMax: Math.ceil(maxBytes / 1024) }
  if (maxBytes < 1024 * 1024 * 1024) return { divisor: 1024 * 1024, unit: 'MB', niceMax: Math.ceil(maxBytes / (1024 * 1024)) }
  if (maxBytes < 1024 * 1024 * 1024 * 1024) return { divisor: 1024 * 1024 * 1024, unit: 'GB', niceMax: Math.ceil(maxBytes / (1024 * 1024 * 1024)) }
  return { divisor: 1024 * 1024 * 1024 * 1024, unit: 'TB', niceMax: Math.ceil(maxBytes / (1024 * 1024 * 1024 * 1024)) }
}

// ECharts options for Memory chart with autoscale in bytes (KB/MB/GB)
const memoryChartOptions = computed(() => {
  const data = history.value.slice(-60).map((entry) => entry.memory_used)

  // Calculate dynamic max with padding
  const maxValue = data.length > 0 ? Math.max(...data) : 0
  const paddedMax = Math.max(maxValue * 1.15, 1024 * 1024) // 15% padding, minimum 1MB

  // Get optimal scale
  const scale = getOptimalScale(paddedMax)
  const scaledData = data.map(v => v / scale.divisor)

  return {
    grid: {
      left: 50,
      right: 10,
      top: 10,
      bottom: 20,
    },
    xAxis: {
      type: 'category',
      show: false,
      data: data.map((_, i) => i),
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: scale.niceMax,
      splitLine: {
        lineStyle: {
          color: 'var(--el-border-color-lighter)',
        },
      },
      axisLabel: {
        color: 'var(--el-text-color-secondary)',
        fontSize: 10,
        formatter: (value: number) => `${value} ${scale.unit}`,
      },
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ value: number }>) => {
        const rawValue = params[0]?.value ?? 0
        const bytes = rawValue * scale.divisor
        return `RAM: ${formatBytesAxis(bytes)}`
      },
    },
    series: [
      {
        type: 'line',
        data: scaledData,
        smooth: true,
        symbol: 'none',
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103, 194, 58, 0.4)' },
              { offset: 1, color: 'rgba(103, 194, 58, 0.05)' },
            ],
          },
        },
        lineStyle: {
          color: 'var(--el-color-success)',
          width: 2,
        },
      },
    ],
  }
})

// Computed
const connectionTagType = computed(() => {
  switch (status.value) {
    case 'connected':
      return 'success'
    case 'connecting':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
})

const connectionStatusText = computed(() => {
  switch (status.value) {
    case 'connected':
      return 'Connecté'
    case 'connecting':
      return 'Connexion...'
    case 'error':
      return 'Erreur'
    default:
      return 'Déconnecté'
  }
})

// Methods
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes < 1024 * 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  return `${(bytes / (1024 * 1024 * 1024 * 1024)).toFixed(2)} TB`
}

function handleReconnect(): void {
  reconnect()
}

function clearError(): void {
  error.value = null
}
</script>

<style scoped>
.container-stats {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 350px);
  min-height: 400px;
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.stats-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stats-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stats-loading,
.stats-not-running {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--el-text-color-secondary);
}

.stats-loading {
  flex-direction: row;
  gap: 8px;
}

.stats-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stat-section {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.stat-value {
  margin-top: 8px;
}

.memory-details {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.io-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 8px;
}

.io-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
}

.io-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.io-value {
  font-family: monospace;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.history-section {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
}

.history-section h4 {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.history-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.history-chart {
  background-color: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 12px;
}

.chart-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
}

.chart {
  height: 120px;
  width: 100%;
}

.no-history {
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  padding: 20px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .stats-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .stats-controls {
    flex-wrap: wrap;
  }

  .history-charts {
    grid-template-columns: 1fr;
  }
}
</style>
