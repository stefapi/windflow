<template>
  <el-card header="System Resources">
    <div v-if="metrics" class="resource-charts">
      <el-row :gutter="20" style="margin-bottom: 16px">
        <el-col :span="6">
          <el-statistic title="CPU Usage" :value="metrics.current_cpu" suffix="%" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Memory Usage" :value="metrics.current_memory" suffix="%" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Used Memory" :value="Math.round(metrics.used_memory_mb)" suffix="MB" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="Total Memory" :value="Math.round(metrics.total_memory_mb)" suffix="MB" />
        </el-col>
      </el-row>
      <v-chart :option="chartOption" autoresize style="height: 300px; width: 100%" />
    </div>
    <el-empty v-else description="No resource metrics available" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ResourceMetrics } from '@/types/api'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface Props {
  metrics: ResourceMetrics | null
}

const props = defineProps<Props>()

const chartOption = computed(() => {
  if (!props.metrics?.history?.length) return {}

  const timestamps = props.metrics.history.map((p) => {
    const d = new Date(p.timestamp)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  })

  return {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: ['CPU %', 'Memory %'],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: timestamps,
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%' },
    },
    series: [
      {
        name: 'CPU %',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
        itemStyle: { color: '#409EFF' },
        data: props.metrics.history.map((p) => p.cpu),
      },
      {
        name: 'Memory %',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
        itemStyle: { color: '#E6A23C' },
        data: props.metrics.history.map((p) => p.memory),
      },
    ],
  }
})
</script>

<style scoped>
.resource-charts {
  min-height: 100px;
}
</style>
