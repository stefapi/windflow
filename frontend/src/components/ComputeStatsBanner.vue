<template>
  <div
    v-loading="loading"
    class="grid grid-cols-2 md:grid-cols-5 gap-4"
  >
    <!-- CONTAINERS TOTAL -->
    <el-card shadow="never">
      <template v-if="stats === null && !loading">
        <el-skeleton
          :rows="2"
          animated
        />
      </template>
      <template v-else>
        <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Containers Total
        </div>
        <div class="text-3xl font-bold mt-1 text-gray-800 dark:text-gray-100">
          {{ stats?.total_containers ?? '—' }}
        </div>
        <div class="text-sm text-gray-400 mt-1">
          sur {{ stats?.targets_count ?? 0 }} machines
        </div>
      </template>
    </el-card>

    <!-- RUNNING -->
    <el-card shadow="never">
      <template v-if="stats === null && !loading">
        <el-skeleton
          :rows="2"
          animated
        />
      </template>
      <template v-else>
        <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Running
        </div>
        <div
          class="text-3xl font-bold mt-1"
          :class="runningColorClass"
        >
          {{ stats?.running_containers ?? '—' }}
        </div>
        <div class="text-sm text-gray-400 mt-1">
          healthy
        </div>
      </template>
    </el-card>

    <!-- STACKS WINDFLOW -->
    <el-card shadow="never">
      <template v-if="stats === null && !loading">
        <el-skeleton
          :rows="2"
          animated
        />
      </template>
      <template v-else>
        <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Stacks WindFlow
        </div>
        <div class="text-3xl font-bold mt-1 text-blue-600">
          {{ stats?.stacks_running_count ?? '—' }}
        </div>
        <div class="text-sm text-gray-400 mt-1">
          sur {{ stats?.stacks_targets_count ?? 0 }} machines
        </div>
      </template>
    </el-card>

    <!-- DISCOVERED -->
    <el-card shadow="never">
      <template v-if="stats === null && !loading">
        <el-skeleton
          :rows="2"
          animated
        />
      </template>
      <template v-else>
        <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Discovered
        </div>
        <div
          class="text-3xl font-bold mt-1"
          :class="discoveredColorClass"
        >
          {{ stats?.discovered_count ?? '—' }}
        </div>
        <div class="text-sm text-gray-400 mt-1">
          sur {{ stats?.discovered_targets_count ?? 0 }} machines
        </div>
      </template>
    </el-card>

    <!-- STANDALONE -->
    <el-card shadow="never">
      <template v-if="stats === null && !loading">
        <el-skeleton
          :rows="2"
          animated
        />
      </template>
      <template v-else>
        <div class="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Standalone
        </div>
        <div class="text-3xl font-bold mt-1 text-gray-800 dark:text-gray-100">
          {{ stats?.standalone_count ?? '—' }}
        </div>
        <div class="text-sm text-gray-400 mt-1">
          sur {{ stats?.standalone_targets_count ?? 0 }} machines
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ComputeStatsResponse } from '@/types/api'

interface Props {
  stats: ComputeStatsResponse | null
  loading: boolean
}

const props = defineProps<Props>()

const runningColorClass = computed(() => {
  if (props.stats === null) return 'text-gray-800 dark:text-gray-100'
  return props.stats.running_containers > 0 ? 'text-green-600' : 'text-red-500'
})

const discoveredColorClass = computed(() => {
  if (props.stats === null) return 'text-gray-400'
  return props.stats.discovered_count > 0 ? 'text-orange-500' : 'text-gray-400'
})
</script>
