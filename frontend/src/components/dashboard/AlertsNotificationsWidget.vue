<template>
  <el-card>
    <template #header>
      <div class="alerts-header">
        <span>Alertes & Notifications</span>
        <el-badge
          v-if="criticalCount > 0"
          :value="criticalCount"
          type="danger"
          class="ml-2"
        />
      </div>
    </template>

    <div
      v-if="alerts.length > 0"
      class="alerts-list"
    >
      <div
        v-for="alert in alerts"
        :key="alert.id"
        class="alert-item"
        :class="`alert-${alert.severity}`"
      >
        <div class="alert-icon">
          <el-icon :size="18">
            <WarningFilled v-if="alert.severity === 'critical'" />
            <Warning v-else-if="alert.severity === 'warning'" />
            <InfoFilled v-else />
          </el-icon>
        </div>
        <div class="alert-content">
          <div class="alert-title">
            {{ alert.title }}
          </div>
          <div class="alert-message">
            {{ alert.message }}
          </div>
          <div class="alert-meta">
            <el-tag
              :type="severityTagType(alert.severity)"
              size="small"
            >
              {{ alert.source }}
            </el-tag>
            <span class="alert-time">{{ formatDate(alert.timestamp) }}</span>
          </div>
        </div>
      </div>
    </div>
    <el-empty
      v-else
      description="Aucune alerte active"
      :image-size="60"
    />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { WarningFilled, Warning, InfoFilled } from '@element-plus/icons-vue'
import type { AlertItem, AlertSeverity } from '@/types/api'

interface Props {
  alerts: AlertItem[]
}

const props = defineProps<Props>()

const criticalCount = computed(() =>
  props.alerts.filter(a => a.severity === 'critical').length
)

type TagType = 'danger' | 'warning' | 'info'

function severityTagType(severity: AlertSeverity): TagType {
  const map: Record<AlertSeverity, TagType> = {
    critical: 'danger',
    warning: 'warning',
    info: 'info',
  }
  return map[severity]
}

function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleString()
}
</script>

<style scoped>
.alerts-header {
  display: flex;
  align-items: center;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.alert-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  border-left: 4px solid;
}

.alert-critical {
  background-color: var(--el-color-danger-light-9);
  border-left-color: var(--el-color-danger);
}

.alert-warning {
  background-color: var(--el-color-warning-light-9);
  border-left-color: var(--el-color-warning);
}

.alert-info {
  background-color: var(--el-color-info-light-9);
  border-left-color: var(--el-color-info);
}

.alert-icon {
  flex-shrink: 0;
  padding-top: 2px;
}

.alert-critical .alert-icon {
  color: var(--el-color-danger);
}

.alert-warning .alert-icon {
  color: var(--el-color-warning);
}

.alert-info .alert-icon {
  color: var(--el-color-info);
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}

.alert-message {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-bottom: 8px;
}

.alert-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.alert-time {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
</style>
