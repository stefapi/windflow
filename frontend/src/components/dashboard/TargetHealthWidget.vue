<template>
  <el-card header="Target Health">
    <div class="target-health">
      <div class="health-summary">
        <StatusBadge
          v-for="(count, status) in targetHealth"
          :key="status"
          :status="mapStatus(status)"
          :label="`${status}: ${count}`"
          size="small"
        />
      </div>
      <el-divider />
      <div class="targets-list">
        <div
          v-for="target in targetsDetail"
          :key="target.id"
          class="target-item"
        >
          <StatusBadge
            :status="mapStatus(target.status)"
            size="small"
          />
          <span class="target-name">{{ target.name }}</span>
          <span class="target-host">{{ target.host }}</span>
        </div>
        <el-empty
          v-if="targetsDetail.length === 0"
          description="Aucune target configurée"
          :image-size="60"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { TargetHealthItem } from '@/types/api'
import StatusBadge, { type StatusType } from '@/components/ui/StatusBadge.vue'

interface Props {
  targetHealth: Record<string, number>
  targetsDetail: TargetHealthItem[]
}

defineProps<Props>()

function mapStatus(status: string): StatusType {
  const map: Record<string, StatusType> = {
    online: 'online',
    offline: 'offline',
    error: 'error',
    maintenance: 'maintenance',
  }
  return map[status] ?? 'offline'
}
</script>

<style scoped>
.health-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.health-tag {
  font-size: 14px;
}

.targets-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.target-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.target-item:last-child {
  border-bottom: none;
}

.target-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot-online {
  background-color: var(--el-color-success);
}

.dot-offline,
.dot-error {
  background-color: var(--el-color-danger);
}

.dot-maintenance {
  background-color: var(--el-color-warning);
}

.target-name {
  font-weight: 500;
  flex: 1;
}

.target-host {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
