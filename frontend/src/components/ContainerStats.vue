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
          @click="handleRefresh"
        >
          <el-icon><RefreshRight /></el-icon>
          {{ autoRefresh ? 'Reconnect' : 'Refresh' }}
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

    <!-- Not running state (no stats available) -->
    <div
      v-else-if="!isStreaming && !stats"
      class="stats-not-running"
    >
      <el-empty description="Les statistiques ne sont disponibles que lorsque le container est en cours d'exécution" />
    </div>

    <!-- Stats content (streaming or manual mode with cached stats) -->
    <div
      v-else
      class="stats-content"
    >
      <!-- Manual mode indicator -->
      <el-alert
        v-if="!autoRefresh && !isStreaming"
        type="info"
        :closable="false"
        show-icon
      >
        <template #title>
          Mode manuel - Cliquez sur "Refresh" pour mettre à jour les statistiques
        </template>
      </el-alert>

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
          <div class="history-chart">
            <div class="chart-title">Réseau</div>
            <v-chart
              :option="networkChartOptions"
              class="chart"
              autoresize
            />
          </div>
          <div class="history-chart">
            <div class="chart-title">I/O Disque</div>
            <v-chart
              :option="ioChartOptions"
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
import { ref, computed, watch } from 'vue'
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
  connect,
  disconnect,
  reconnect,
  fetchOnce,
} = useContainerStats({
  containerId: props.containerId,
  autoConnect: true,
})

// Auto-refresh state
const autoRefresh = ref(true)

// Watch autoRefresh to control WebSocket connection
watch(autoRefresh, (newValue) => {
  if (newValue) {
    // Auto mode: continuous streaming
    connect()
  } else {
    // Manual mode: disconnect and keep last stats displayed
    disconnect()
  }
})

// Helper to get optimal CPU scale (autoscale with padding)
function getCpuScale(maxPercent: number): { niceMax: number } {
  // Minimum 1% to avoid flat chart, 15% padding
  const paddedMax = Math.max(maxPercent * 1.15, 1)
  // Round up to nearest nice value
  const niceValues = [1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 80, 100]
  const niceMax = niceValues.find(v => v >= paddedMax) ?? Math.ceil(paddedMax / 10) * 10
  return { niceMax }
}

// ECharts options for CPU chart with autoscale
const cpuChartOptions = computed(() => {
  const data = history.value.slice(-60).map((entry) => entry.cpu_percent)

  // Calculate dynamic max with padding
  const maxValue = data.length > 0 ? Math.max(...data) : 0
  const scale = getCpuScale(maxValue)

  return {
    grid: {
      left: 40,
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
        formatter: (value: number) => `${value}%`,
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
        data: data,
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
  }
})

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

// ECharts options for Network chart with autoscale (RX + TX on same chart)
const networkChartOptions = computed(() => {
  const historySlice = history.value.slice(-60)
  const rxData = historySlice.map((entry) => entry.network_rx_bytes)
  const txData = historySlice.map((entry) => entry.network_tx_bytes)

  // Calculate dynamic max with padding (max of both RX and TX)
  const maxRx = rxData.length > 0 ? Math.max(...rxData) : 0
  const maxTx = txData.length > 0 ? Math.max(...txData) : 0
  const maxValue = Math.max(maxRx, maxTx)
  const paddedMax = Math.max(maxValue * 1.15, 1024) // 15% padding, minimum 1KB

  // Get optimal scale
  const scale = getOptimalScale(paddedMax)
  const scaledRxData = rxData.map(v => v / scale.divisor)
  const scaledTxData = txData.map(v => v / scale.divisor)

  return {
    grid: {
      left: 50,
      right: 10,
      top: 30,
      bottom: 20,
    },
    legend: {
      data: ['RX', 'TX'],
      top: 0,
      right: 0,
      textStyle: {
        color: 'var(--el-text-color-secondary)',
        fontSize: 10,
      },
    },
    xAxis: {
      type: 'category',
      show: false,
      data: rxData.map((_, i) => i),
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
      formatter: (params: Array<{ seriesName: string; value: number }>) => {
        const parts = params.map((p) => {
          const bytes = p.value * scale.divisor
          return `${p.seriesName}: ${formatBytesAxis(bytes)}`
        })
        return parts.join('<br/>')
      },
    },
    series: [
      {
        name: 'RX',
        type: 'line',
        data: scaledRxData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: 'var(--el-color-info)',
          width: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(144, 147, 153, 0.3)' },
              { offset: 1, color: 'rgba(144, 147, 153, 0.05)' },
            ],
          },
        },
      },
      {
        name: 'TX',
        type: 'line',
        data: scaledTxData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: 'var(--el-color-warning)',
          width: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(230, 162, 60, 0.3)' },
              { offset: 1, color: 'rgba(230, 162, 60, 0.05)' },
            ],
          },
        },
      },
    ],
  }
})

// ECharts options for Block I/O chart with autoscale (Read + Write on same chart)
const ioChartOptions = computed(() => {
  const historySlice = history.value.slice(-60)
  const readData = historySlice.map((entry) => entry.block_read_bytes)
  const writeData = historySlice.map((entry) => entry.block_write_bytes)
  // Calculate dynamic max with padding (max of both Read and Write)
  const maxRead = readData.length > 0 ? Math.max(...readData) : 0
  const maxWrite = writeData.length > 0 ? Math.max(...writeData) : 0
  const maxValue = Math.max(maxRead, maxWrite)
  const paddedMax = Math.max(maxValue * 1.15, 1024) // 15% padding, minimum 1KB

  // Get optimal scale
  const scale = getOptimalScale(paddedMax)
  const scaledReadData = readData.map(v => v / scale.divisor)
  const scaledWriteData = writeData.map(v => v / scale.divisor)

  return {
    grid: {
      left: 50,
      right: 10,
      top: 30,
      bottom: 20,
    },
    legend: {
      data: ['Lecture', 'Écriture'],
      top: 0,
      right: 0,
      textStyle: {
        color: 'var(--el-text-color-secondary)',
        fontSize: 10,
      },
    },
    xAxis: {
      type: 'category',
      show: false,
      data: readData.map((_, i) => i),
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
      formatter: (params: Array<{ seriesName: string; value: number }>) => {
        const parts = params.map((p) => {
          const bytes = p.value * scale.divisor
          return `${p.seriesName}: ${formatBytesAxis(bytes)}`
        })
        return parts.join('<br/>')
      },
    },
    series: [
      {
        name: 'Lecture',
        type: 'line',
        data: scaledReadData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: 'var(--el-color-primary)',
          width: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
            ],
          },
        },
      },
      {
        name: 'Écriture',
        type: 'line',
        data: scaledWriteData,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: 'var(--el-color-danger)',
          width: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(245, 108, 108, 0.3)' },
              { offset: 1, color: 'rgba(245, 108, 108, 0.05)' },
            ],
          },
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

function handleRefresh(): void {
  if (autoRefresh.value) {
    // Auto mode: reconnect
    reconnect()
  } else {
    // Manual mode: fetch stats once
    fetchOnce()
  }
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
