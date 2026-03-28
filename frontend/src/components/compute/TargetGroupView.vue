<template>
  <div>
    <!-- Loading -->
    <div
      v-if="loading"
      class="flex justify-center py-8"
    >
      <el-icon class="is-loading text-2xl text-blue-500">
        <Loading />
      </el-icon>
    </div>

    <!-- Empty -->
    <el-empty
      v-else-if="groups.length === 0"
      description="Aucun groupe de machines trouvé"
    />

    <!-- Groups collapse -->
    <el-collapse
      v-else
      class="target-groups-collapse"
    >
      <el-collapse-item
        v-for="group in groups"
        :key="group.target_id"
        :name="group.target_id"
      >
        <template #title>
          <div class="flex flex-wrap items-center gap-2 w-full pr-4">
            <span class="font-semibold">{{ group.target_name }}</span>
            <el-tag size="small">
              {{ group.technology }}
            </el-tag>
            <span class="text-xs text-gray-500">
              CPU: {{ group.metrics.cpu_total_percent }}% |
              RAM: {{ group.metrics.memory_used }}/{{ group.metrics.memory_total }}
            </span>
          </div>
        </template>

        <!-- Stacks subsection -->
        <template v-if="group.stacks.length > 0">
          <div class="text-xs font-semibold text-blue-600 mb-2 mt-2">
            Stacks ({{ group.stacks.length }})
          </div>
          <ContainerTable
            :items="group.stacks.flatMap(s => s.services.map(sv => serviceToRow(sv, group.target_name)))"
            :columns="['name', 'status']"
            :show-actions="false"
            size="small"
            class="mb-4"
          />
        </template>

        <!-- Discovered subsection -->
        <template v-if="group.discovered.length > 0">
          <div class="text-xs font-semibold text-orange-500 mb-2">
            Discovered ({{ group.discovered.length }})
          </div>
          <ContainerTable
            :items="group.discovered.flatMap(d => (d.services ?? []).map(sv => serviceToRow(sv, group.target_name)))"
            :columns="['name', 'status']"
            :show-actions="false"
            size="small"
            class="mb-4"
          />
        </template>

        <!-- Standalone subsection -->
        <template v-if="group.standalone.length > 0">
          <div class="text-xs font-semibold text-gray-500 mb-2">
            Standalone ({{ group.standalone.length }})
          </div>
          <ContainerTable
            :items="group.standalone.map(standaloneToRow)"
            :columns="['name', 'image', 'status']"
            :show-actions="false"
            size="small"
          />
        </template>

        <!-- Empty if nothing -->
        <el-empty
          v-if="group.stacks.length === 0 && group.discovered.length === 0 && group.standalone.length === 0"
          description="Aucune ressource sur cette machine"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
/**
 * TargetGroupView Component
 *
 * Displays containers grouped by target machine in a simplified,
 * read-only view. Users switch to normal mode for actions.
 */

import { Loading } from '@element-plus/icons-vue'
import ContainerTable from './ContainerTable.vue'
import { serviceToRow, standaloneToRow } from './helpers'
import type { StackWithServices, DiscoveredItem, StandaloneContainer, TargetMetrics } from '@/types/api'

export interface TargetGroupItem {
  target_id: string
  target_name: string
  technology: string
  stacks: StackWithServices[]
  discovered: DiscoveredItem[]
  standalone: StandaloneContainer[]
  metrics: TargetMetrics
}

export interface TargetGroupViewProps {
  groups: TargetGroupItem[]
  loading: boolean
}

defineProps<TargetGroupViewProps>()
</script>

<style scoped>
.target-groups-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 44px;
  padding: 8px 16px;
}
</style>
