<template>
  <el-card header="Target Health">
    <div class="target-health">
      <div class="health-summary">
        <el-tag v-for="(count, status) in targetHealth" :key="status" :type="statusTagType(status)" effect="dark" class="health-tag">
          {{ status }}: {{ count }}
        </el-tag>
      </div>
      <el-divider />
      <div class="targets-list">
        <div v-for="target in targetsDetail" :key="target.id" class="target-item">
          <span class="target-dot" :class="`dot-${target.status}`" />
          <span class="target-name">{{ target.name }}</span>
          <span class="target-host">{{ target.host }}</span>
          <el-tag :type="statusTagType(target.status)" size="small">{{ target.status }}</el-tag>
        </div>
        <el-empty v-if="targetsDetail.length === 0" description="Aucune target configurée" :image-size="60" />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { TargetHealthItem } from '@/types/api'

interface Props {
  targetHealth: Record<string, number>
  targetsDetail: TargetHealthItem[]
}

defineProps<Props>()

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    online: 'success',
    offline: 'danger',
    error: 'danger',
    maintenance: 'warning',
  }
  return map[status] ?? 'info'
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
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
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
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
