<template>
  <el-card
    class="docker-info-widget"
    data-testid="docker-info-widget"
  >
    <!-- Header -->
    <template #header>
      <div class="docker-info-widget__header">
        <div class="header-left">
          <el-icon><Platform /></el-icon>
          <span class="header-title">Docker System</span>
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div
      v-if="error"
      class="docker-info-widget__error"
    >
      <el-alert
        type="error"
        :closable="false"
        show-icon
      >
        <template #default>
          <div class="error-content">
            <span>{{ error }}</span>
          </div>
        </template>
      </el-alert>
    </div>

    <!-- Loading state -->
    <div
      v-else-if="isLoading"
      class="docker-info-widget__loading"
    >
      <el-skeleton
        :rows="3"
        animated
      />
    </div>

    <!-- Content -->
    <div
      v-else-if="info"
      class="docker-info-widget__content"
    >
      <div class="info-grid">
        <!-- Version Docker -->
        <div class="info-item">
          <span class="info-label">Version</span>
          <span
            class="info-value"
            data-testid="docker-version"
          >{{ info.server_version }}</span>
        </div>

        <!-- Containers -->
        <div class="info-item">
          <span class="info-label">Containers</span>
          <div
            class="info-value info-value--badges"
            data-testid="docker-containers"
          >
            <span class="badge-total">{{ info.containers }}</span>
            <el-tag
              type="success"
              size="small"
            >
              {{ info.containers_running }} running
            </el-tag>
            <el-tag
              type="warning"
              size="small"
            >
              {{ info.containers_paused }} paused
            </el-tag>
            <el-tag
              type="danger"
              size="small"
            >
              {{ info.containers_stopped }} stopped
            </el-tag>
          </div>
        </div>

        <!-- Images -->
        <div class="info-item">
          <span class="info-label">Images</span>
          <span
            class="info-value"
            data-testid="docker-images"
          >{{ info.images }}</span>
        </div>

        <!-- OS -->
        <div class="info-item">
          <span class="info-label">OS</span>
          <span
            class="info-value"
            data-testid="docker-os"
          >{{ info.operating_system }}</span>
        </div>

        <!-- Architecture -->
        <div class="info-item">
          <span class="info-label">Architecture</span>
          <span
            class="info-value"
            data-testid="docker-architecture"
          >{{ info.architecture }}</span>
        </div>

        <!-- CPUs -->
        <div class="info-item">
          <span class="info-label">CPUs</span>
          <span
            class="info-value"
            data-testid="docker-cpus"
          >{{ info.cpus }}</span>
        </div>

        <!-- Memory -->
        <div class="info-item">
          <span class="info-label">Memory</span>
          <span
            class="info-value"
            data-testid="docker-memory"
          >{{ formatMemory(info.memory) }}</span>
        </div>

        <!-- Kernel -->
        <div class="info-item">
          <span class="info-label">Kernel</span>
          <span
            class="info-value"
            data-testid="docker-kernel"
          >{{ info.kernel_version }}</span>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <el-empty
      v-else
      description="No Docker system information available"
      :image-size="60"
    />
  </el-card>
</template>

<script setup lang="ts">
/**
 * DockerInfoWidget Component
 *
 * Dashboard widget displaying Docker system information:
 * - Version, containers, images, OS, architecture, CPUs, memory, kernel
 * - Error, loading, and empty states
 *
 * @example
 * <DockerInfoWidget />
 */

import { onMounted, ref } from 'vue'
import { Platform } from '@element-plus/icons-vue'
import { dockerSystemApi } from '@/services/api'
import type { SystemInfoResponse } from '@/types/api'

export interface DockerInfoWidgetProps {
  loading?: boolean
}

withDefaults(defineProps<DockerInfoWidgetProps>(), {
  loading: false,
})

const info = ref<SystemInfoResponse | null>(null)
const error = ref<string | null>(null)
const isLoading = ref(false)

async function fetchInfo(): Promise<void> {
  isLoading.value = true
  error.value = null
  try {
    const response = await dockerSystemApi.info()
    info.value = response.data
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Unable to retrieve Docker system information'
  } finally {
    isLoading.value = false
  }
}

function formatMemory(bytes: number): string {
  if (bytes === 0) return '0 o'
  const units = ['o', 'Ko', 'Mo', 'Go', 'To']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const value = bytes / Math.pow(k, i)
  return `${Math.round(value)} ${units[i]}`
}

onMounted(() => {
  fetchInfo()
})
</script>

<style scoped>
.docker-info-widget__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-title {
  font-weight: 600;
  font-size: 16px;
}

.docker-info-widget__error {
  padding: 8px 0;
}

.error-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.docker-info-widget__loading {
  padding: 8px 0;
}

.docker-info-widget__content {
  padding: 4px 0;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.info-value--badges {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.badge-total {
  font-weight: 700;
  font-size: 18px;
  margin-right: 4px;
}
</style>
