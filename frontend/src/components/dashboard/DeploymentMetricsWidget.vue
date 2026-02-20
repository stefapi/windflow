<template>
  <el-card header="Deployment Metrics">
    <div v-if="metrics" class="metrics-grid">
      <div class="metric-item">
        <el-statistic title="Total" :value="metrics.total" />
      </div>
      <div class="metric-item">
        <el-statistic title="Running" :value="metrics.running">
          <template #suffix>
            <el-icon color="var(--el-color-success)"><CircleCheckFilled /></el-icon>
          </template>
        </el-statistic>
      </div>
      <div class="metric-item">
        <el-statistic title="Failed" :value="metrics.failed">
          <template #suffix>
            <el-icon color="var(--el-color-danger)"><CircleCloseFilled /></el-icon>
          </template>
        </el-statistic>
      </div>
      <div class="metric-item">
        <el-statistic title="Success Rate" :value="metrics.success_rate" suffix="%" />
      </div>
      <div class="progress-section">
        <span class="progress-label">Success Rate</span>
        <el-progress
          :percentage="metrics.success_rate"
          :color="progressColor"
          :stroke-width="18"
          striped
          striped-flow
        />
      </div>
    </div>
    <el-empty v-else description="Aucune donnée de déploiement" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import type { DeploymentMetrics } from '@/types/api'

interface Props {
  metrics: DeploymentMetrics | null
}

const props = defineProps<Props>()

const progressColor = computed(() => {
  if (!props.metrics) return ''
  const rate = props.metrics.success_rate
  if (rate >= 80) return 'var(--el-color-success)'
  if (rate >= 50) return 'var(--el-color-warning)'
  return 'var(--el-color-danger)'
})
</script>

<style scoped>
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.metric-item {
  text-align: center;
}

.progress-section {
  grid-column: 1 / -1;
  margin-top: 12px;
}

.progress-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  display: block;
}
</style>
