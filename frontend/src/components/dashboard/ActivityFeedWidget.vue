<template>
  <el-card header="Recent Activity">
    <el-timeline v-if="activities.length > 0">
      <el-timeline-item
        v-for="item in activities"
        :key="item.id"
        :timestamp="formatDate(item.timestamp)"
        :type="activityType(item.status)"
        placement="top"
      >
        <div class="activity-item">
          <el-tag :type="activityType(item.status)" size="small" class="activity-type-tag">
            {{ item.type }}
          </el-tag>
          <span class="activity-title">{{ item.title }}</span>
        </div>
        <p v-if="item.details" class="activity-details">{{ item.details }}</p>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-else description="Aucune activité récente" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import type { ActivityFeedItem } from '@/types/api'

interface Props {
  activities: ActivityFeedItem[]
}

defineProps<Props>()

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function activityType(status: string): TagType {
  const map: Record<string, TagType> = {
    running: 'success',
    pending: 'warning',
    deploying: 'warning',
    failed: 'danger',
    stopped: 'info',
  }
  return map[status] ?? 'info'
}

function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleString()
}
</script>

<style scoped>
.activity-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.activity-type-tag {
  text-transform: capitalize;
}

.activity-title {
  font-weight: 500;
}

.activity-details {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 4px;
}
</style>
