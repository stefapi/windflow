<template>
  <div
    class="placeholder-widget"
    data-testid="placeholder-widget"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
    >
      <template #default>
        <div class="placeholder-widget__notice">
          <strong>Demo Widget</strong>
          <span>— This widget appears only in development mode</span>
        </div>
      </template>
    </el-alert>

    <div class="placeholder-widget__content">
      <div class="placeholder-widget__stats">
        <div class="stat-item">
          <el-icon><Connection /></el-icon>
          <span class="stat-value">{{ status }}</span>
          <span class="stat-label">Status</span>
        </div>
        <div class="stat-item">
          <el-icon><Timer /></el-icon>
          <span class="stat-value">{{ uptime }}</span>
          <span class="stat-label">Uptime</span>
        </div>
        <div class="stat-item">
          <el-icon><Cpu /></el-icon>
          <span class="stat-value">{{ cpu }}%</span>
          <span class="stat-label">CPU</span>
        </div>
        <div class="stat-item">
          <el-icon><Coin /></el-icon>
          <span class="stat-value">{{ memory }}MB</span>
          <span class="stat-label">Memory</span>
        </div>
      </div>

      <div class="placeholder-widget__footer">
        <el-tag
          type="warning"
          size="small"
        >
          Plugin: {{ pluginName }}
        </el-tag>
        <el-tag
          type="info"
          size="small"
        >
          v{{ version }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * PlaceholderWidget Component
 *
 * A demo widget to test the plugin widget system.
 * Only displayed in development mode.
 *
 * @example
 * <PlaceholderWidget />
 */

import { ref } from 'vue'
import { Connection, Timer, Cpu, Coin } from '@element-plus/icons-vue'

export interface PlaceholderWidgetProps {
  pluginName?: string
  version?: string
}

withDefaults(defineProps<PlaceholderWidgetProps>(), {
  pluginName: 'demo-plugin',
  version: '1.0.0',
})

// Simulated data
const status = ref('Connected')
const uptime = ref('2h 45m')
const cpu = ref(23)
const memory = ref(128)
</script>

<style scoped>
.placeholder-widget {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.placeholder-widget__notice {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.placeholder-widget__content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.placeholder-widget__stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.75rem;
  background-color: var(--color-bg-secondary);
  border-radius: 0.5rem;
  gap: 0.25rem;
}

.stat-item .el-icon {
  font-size: 1.25rem;
  color: var(--color-accent);
}

.stat-value {
  font-size: var(--text-lg, 1.125rem);
  font-weight: 600;
  color: var(--color-text-primary);
  font-family: var(--font-mono, monospace);
}

.stat-label {
  font-size: var(--text-xs, 0.75rem);
  color: var(--color-text-secondary);
}

.placeholder-widget__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
