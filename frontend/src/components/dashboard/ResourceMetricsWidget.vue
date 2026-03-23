<template>
  <el-card
    class="resource-metrics-widget"
    data-testid="resource-metrics-widget"
  >
    <!-- Header with target name -->
    <template #header>
      <div class="resource-metrics-widget__header">
        <div class="header-left">
          <el-icon><Monitor /></el-icon>
          <span class="header-title">System Resources</span>
          <span
            v-if="targetName"
            class="target-name"
          >{{ targetName }}</span>
        </div>
        <div
          v-if="lastUpdate"
          class="last-update"
        >
          <el-icon><Clock /></el-icon>
          <span>{{ lastUpdate }}</span>
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div
      v-if="error"
      class="resource-metrics-widget__error"
    >
      <el-alert
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <div class="error-content">
            <el-icon><Warning /></el-icon>
            <span>Unable to retrieve system metrics</span>
          </div>
        </template>
      </el-alert>
    </div>

    <!-- No target state -->
    <div
      v-else-if="noTarget"
      class="resource-metrics-widget__no-target"
    >
      <el-icon><InfoFilled /></el-icon>
      <span>No target selected. <router-link to="/targets">Select a target</router-link> to view its metrics.</span>
    </div>

    <!-- Loading state -->
    <div
      v-else-if="loading"
      class="resource-metrics-widget__loading"
    >
      <el-skeleton
        :rows="4"
        animated
      />
    </div>

    <!-- Content -->
    <div
      v-else-if="metrics"
      class="resource-metrics-widget__content"
    >
      <!-- Current metrics with ResourceBars -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-label">CPU</span>
            <span class="metric-value">{{ formatPercent(metrics.current_cpu) }}</span>
          </div>
          <ResourceBar
            :value="metrics.current_cpu"
            label=""
            :show-value="false"
          />
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-label">RAM</span>
            <span class="metric-value">{{ formatMemory(metrics) }}</span>
          </div>
          <ResourceBar
            :value="metrics.current_memory"
            label=""
            :show-value="false"
          />
        </div>

        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-label">Disk</span>
            <span class="metric-value">{{ formatDisk(metrics) }}</span>
          </div>
          <ResourceBar
            :value="metrics.current_disk"
            label=""
            :show-value="false"
          />
        </div>

        <div class="metric-card metric-card--uptime">
          <div class="metric-header">
            <span class="metric-label">Uptime</span>
          </div>
          <div class="uptime-value">
            <el-icon><Timer /></el-icon>
            <span>{{ formatUptime(metrics.uptime_seconds) }}</span>
          </div>
        </div>
      </div>

      <!-- Historical charts -->
      <div
        v-if="hasHistory"
        class="charts-section"
      >
        <v-chart
          :option="chartOption"
          autoresize
          class="history-chart"
        />
      </div>
      <div
        v-else
        class="no-history"
      >
        <el-icon><TrendCharts /></el-icon>
        <span>Collecting historical data...</span>
      </div>
    </div>

    <!-- Empty state -->
    <el-empty
      v-else
      description="No resource metrics available"
      :image-size="60"
    />
  </el-card>
</template>

<script setup lang="ts">
/**
 * ResourceMetricsWidget Component
 *
 * Unified component displaying system metrics with:
 * - Current values using ResourceBar components
 * - Historical charts using ECharts
 * - Error, loading, and no-target states
 *
 * @example
 * <ResourceMetricsWidget
 *   :metrics="resourceMetrics"
 *   :error="null"
 *   target-name="Server 1"
 *   :loading="false"
 *   :no-target="false"
 * />
 */

import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Monitor, Warning, InfoFilled, Clock, Timer, TrendCharts } from '@element-plus/icons-vue'
import ResourceBar from '@/components/ui/ResourceBar.vue'
import { getCssVar } from '@/utils/css'
import type { ResourceMetrics } from '@/types/api'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

export interface ResourceMetricsWidgetProps {
  metrics: ResourceMetrics | null
  error: string | null
  targetName?: string
  loading?: boolean
  noTarget?: boolean
}

const props = withDefaults(defineProps<ResourceMetricsWidgetProps>(), {
  targetName: '',
  loading: false,
  noTarget: false,
})

// Check if history data is available
const hasHistory = computed(() => {
  return props.metrics?.history && props.metrics.history.length > 0
})

// Format last update time
const lastUpdate = computed(() => {
  if (!props.metrics?.history?.length) return null
  const now = new Date()
  return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
})

// Chart configuration
const chartOption = computed(() => {
  if (!hasHistory.value) return {}

  const timestamps = props.metrics!.history!.map((p) => {
    const d = new Date(p.timestamp)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  })

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: getCssVar('--color-bg-elevated'),
      borderColor: getCssVar('--color-border'),
      textStyle: { color: getCssVar('--color-text-primary') },
    },
    legend: {
      data: ['CPU %', 'Memory %', 'Disk %'],
      bottom: 0,
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '5%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timestamps,
      axisLine: { lineStyle: { color: 'var(--color-border)' } },
      axisLabel: { color: 'var(--color-text-secondary)' },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%', color: 'var(--color-text-secondary)' },
      splitLine: { lineStyle: { color: 'var(--color-border-light)' } },
    },
    series: [
      {
        name: 'CPU %',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
        itemStyle: { color: getCssVar('--color-accent') },
        data: props.metrics!.history!.map((p) => p.cpu),
      },
      {
        name: 'Memory %',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
        itemStyle: { color: getCssVar('--color-warning') },
        data: props.metrics!.history!.map((p) => p.memory),
      },
    ],
  }
})

// Format percentage
const formatPercent = (value: number): string => {
  return `${Math.round(value)}%`
}

// Format memory usage
const formatMemory = (metrics: ResourceMetrics): string => {
  if (metrics.used_memory_mb && metrics.total_memory_mb) {
    return `${Math.round(metrics.used_memory_mb)} / ${Math.round(metrics.total_memory_mb)} MB`
  }
  return `${Math.round(metrics.current_memory)}%`
}

// Format disk usage
const formatDisk = (metrics: ResourceMetrics): string => {
  if (metrics.used_disk_gb && metrics.total_disk_gb) {
    return `${metrics.used_disk_gb.toFixed(1)} / ${metrics.total_disk_gb.toFixed(1)} GB`
  }
  return `${Math.round(metrics.current_disk)}%`
}

// Format uptime
const formatUptime = (seconds: number): string => {
  if (!seconds) return '0m'

  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}
</script>

<style scoped>
.resource-metrics-widget {
  width: 100%;
}

.resource-metrics-widget__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-title {
  font-weight: 600;
  color: var(--color-text-primary);
}

.target-name {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text-secondary);
  background-color: var(--color-bg-secondary);
  padding: 0.125rem 0.5rem;
  border-radius: 0.25rem;
}

.last-update {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: var(--text-xs, 0.75rem);
  color: var(--color-text-secondary);
}

.resource-metrics-widget__error {
  width: 100%;
}

.error-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.resource-metrics-widget__no-target {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background-color: var(--color-bg-secondary);
  border-radius: 0.375rem;
  color: var(--color-text-secondary);
}

.resource-metrics-widget__no-target a {
  color: var(--color-accent);
}

.resource-metrics-widget__loading {
  padding: 1rem;
}

.resource-metrics-widget__content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}

@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background-color: var(--color-bg-secondary);
  border-radius: 0.5rem;
}

.metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-label {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text-secondary);
  font-weight: 500;
}

.metric-value {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text-primary);
  font-weight: 600;
  font-family: var(--font-mono, monospace);
}

.metric-card--uptime .uptime-value {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-lg, 1.125rem);
  color: var(--color-text-primary);
  font-weight: 600;
  font-family: var(--font-mono, monospace);
  padding: 0.25rem 0;
}

.charts-section {
  margin-top: 0.5rem;
}

.history-chart {
  height: 250px;
  width: 100%;
}

.no-history {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2rem;
  background-color: var(--color-bg-secondary);
  border-radius: 0.5rem;
  color: var(--color-text-secondary);
  font-size: var(--text-sm, 0.875rem);
}
</style>
