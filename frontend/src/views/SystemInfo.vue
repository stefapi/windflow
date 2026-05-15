<template>
  <div
    class="system-info-page"
    data-testid="system-info-page"
  >
    <div class="page-header">
      <h1 class="page-title">
        <el-icon><Platform /></el-icon>
        Docker System Information
      </h1>
    </div>

    <el-alert
      v-if="error"
      type="error"
      :closable="false"
      data-testid="error-alert"
    >
      {{ error }}
    </el-alert>

    <el-skeleton
      v-if="loading"
      :rows="5"
      animated
      data-testid="loading-skeleton"
    />

    <template v-else-if="versionInfo">
      <el-row :gutter="20">
        <el-col :span="16">
          <el-card data-testid="version-card">
            <template #header>
              <div class="card-header">
                <span>Version</span>
              </div>
            </template>
            <el-descriptions
              :column="2"
              border
            >
              <el-descriptions-item label="Version Docker">
                <span data-testid="version-value">{{ versionInfo.version }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="API Version">
                <span data-testid="api-version-value">{{ versionInfo.api_version }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Min API Version">
                {{ versionInfo.min_api_version }}
              </el-descriptions-item>
              <el-descriptions-item label="Go Version">
                <span data-testid="go-version-value">{{ versionInfo.go_version }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="OS">
                <span data-testid="os-value">{{ versionInfo.os }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Architecture">
                <span data-testid="arch-value">{{ versionInfo.arch }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Kernel">
                <span data-testid="kernel-value">{{ versionInfo.kernel_version }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Build Time">
                <span data-testid="build-time-value">{{ versionInfo.build_time }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Git Commit">
                {{ versionInfo.git_commit }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card data-testid="connectivity-card">
            <template #header>
              <div class="card-header">
                <span>Connectivity</span>
              </div>
            </template>
            <div
              v-if="pingResult"
              class="connectivity-content"
            >
              <el-tag
                v-if="pingResult.available"
                type="success"
                size="large"
                data-testid="ping-available"
              >
                Docker is available
              </el-tag>
              <el-tag
                v-else
                type="danger"
                size="large"
                data-testid="ping-unavailable"
              >
                Docker is not available
              </el-tag>
              <p
                v-if="pingResult.message"
                class="ping-message"
              >
                {{ pingResult.message }}
              </p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-empty
      v-else-if="!error"
      description="No system information available"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * SystemInfo Page
 * Docker system information page showing version details and connectivity status
 */

import { ref, onMounted } from 'vue'
import { Platform } from '@element-plus/icons-vue'
import { dockerSystemApi } from '@/services/api'
import type { SystemVersionResponse, PingResponse } from '@/types/api'

const versionInfo = ref<SystemVersionResponse | null>(null)
const pingResult = ref<PingResponse | null>(null)
const error = ref<string | null>(null)
const loading = ref(false)

async function fetchData(): Promise<void> {
  loading.value = true
  error.value = null

  try {
    const [versionResult, pingResponse] = await Promise.allSettled([
      dockerSystemApi.version(),
      dockerSystemApi.ping(),
    ])

    if (versionResult.status === 'fulfilled') {
      versionInfo.value = versionResult.value.data
    } else {
      error.value = 'Failed to load Docker version information'
    }

    if (pingResponse.status === 'fulfilled') {
      pingResult.value = pingResponse.value.data
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'An unexpected error occurred'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.system-info-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.connectivity-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 0;
}

.ping-message {
  margin-top: 8px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
</style>
