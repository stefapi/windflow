<template>
  <el-card
    class="recent-deployments-widget"
    data-testid="recent-deployments-widget"
  >
    <template #header>
      <div class="widget-header">
        <span class="widget-title">
          <el-icon><Clock /></el-icon>
          Derniers Déploiements
        </span>
        <router-link
          to="/deployments"
          class="view-all-link"
        >
          Voir tout
        </router-link>
      </div>
    </template>

    <!-- Loading state -->
    <div
      v-if="loading"
      class="recent-deployments-widget__loading"
    >
      <el-skeleton
        :rows="3"
        animated
      />
    </div>

    <!-- Error state -->
    <el-alert
      v-else-if="error"
      type="error"
      :title="error"
      show-icon
      :closable="false"
      data-testid="deployments-error"
    />

    <!-- Empty state -->
    <el-empty
      v-else-if="deployments.length === 0"
      description="Aucun déploiement récent"
      :image-size="60"
      data-testid="deployments-empty"
    />

    <!-- Deployments list -->
    <div
      v-else
      class="deployments-list"
    >
      <div
        v-for="deployment in deployments"
        :key="deployment.id"
        class="deployment-row"
        :class="{ 'deployment-row--clickable': true }"
        @click="navigateToDeployment(deployment)"
      >
        <div class="deployment-row__main">
          <div class="deployment-row__info">
            <span class="deployment-name">{{ deployment.name || deployment.id.slice(0, 8) }}</span>
            <StatusBadge
              :status="mapDeploymentStatus(deployment.status)"
              size="small"
            />
          </div>
          <div class="deployment-row__meta">
            <span class="deployment-time">{{ formatRelativeTime(deployment.created_at) }}</span>
            <span
              v-if="deployment.target?.name"
              class="deployment-target"
            >
              <el-icon><Monitor /></el-icon>
              {{ deployment.target.name }}
            </span>
          </div>
        </div>
        <div class="deployment-row__actions">
          <el-button
            v-if="deployment.status === 'failed'"
            type="warning"
            size="small"
            :loading="retryingId === deployment.id"
            @click.stop="handleRetry(deployment)"
          >
            <el-icon><RefreshRight /></el-icon>
            Redéployer
          </el-button>
          <el-icon class="deployment-row__arrow">
            <ArrowRight />
          </el-icon>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
/**
 * RecentDeploymentsWidget Component
 *
 * Displays the last 10 deployments with status, relative time, and quick actions.
 * Part of STORY-433: Dashboard recent deployments list.
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Clock, RefreshRight, ArrowRight, Monitor } from '@element-plus/icons-vue'
import { deploymentsApi } from '@/services/api'
import { formatRelativeTime } from '@/composables/useRelativeTime'
import StatusBadge, { type StatusType } from '@/components/ui/StatusBadge.vue'
import type { Deployment, DeploymentStatus } from '@/types/api'

interface Props {
  /** Maximum number of deployments to display */
  limit?: number
  /** Refresh interval in milliseconds */
  refreshInterval?: number
}

const props = withDefaults(defineProps<Props>(), {
  limit: 10,
  refreshInterval: 30000, // 30 seconds, consistent with dashboard tiles
})

const router = useRouter()

// State
const deployments = ref<Deployment[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const retryingId = ref<string | null>(null)
let refreshTimer: number | null = null

// Map deployment status to StatusBadge status
function mapDeploymentStatus(status: DeploymentStatus): StatusType {
  const statusMap: Record<DeploymentStatus, StatusType> = {
    pending: 'pending',
    running: 'deploying',
    completed: 'deployed',
    failed: 'failed',
    cancelled: 'stopped',
  }
  return statusMap[status] ?? 'pending'
}

// Fetch recent deployments
async function fetchDeployments(): Promise<void> {
  try {
    error.value = null
    const response = await deploymentsApi.list({
      limit: props.limit,
      skip: 0,
    })
    deployments.value = response.data.items ?? []
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Erreur lors du chargement des déploiements'
    console.error('Failed to fetch deployments:', err)
  } finally {
    loading.value = false
  }
}

// Navigate to deployment detail
function navigateToDeployment(deployment: Deployment): void {
  router.push(`/deployments/${deployment.id}`)
}

// Handle retry action
async function handleRetry(deployment: Deployment): Promise<void> {
  retryingId.value = deployment.id
  try {
    await deploymentsApi.retry(deployment.id)
    // Refresh the list after successful retry
    await fetchDeployments()
  } catch (err) {
    console.error('Failed to retry deployment:', err)
    error.value = err instanceof Error ? err.message : 'Erreur lors du redéploiement'
  } finally {
    retryingId.value = null
  }
}

// Lifecycle
onMounted(() => {
  fetchDeployments()
  // Set up polling
  refreshTimer = window.setInterval(fetchDeployments, props.refreshInterval)
})

onUnmounted(() => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
  }
})

// Expose for testing
defineExpose({
  fetchDeployments,
  deployments,
  loading,
  error,
})
</script>

<style scoped>
.recent-deployments-widget {
  height: 100%;
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.widget-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
}

.view-all-link {
  font-size: 0.875rem;
  text-decoration: none;
  color: var(--el-color-primary);
}

.view-all-link:hover {
  text-decoration: underline;
}

.recent-deployments-widget__loading {
  padding: 1rem;
}

.deployments-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.deployment-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background-color: var(--el-fill-color-light);
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.deployment-row--clickable {
  cursor: pointer;
}

.deployment-row--clickable:hover {
  background-color: var(--el-fill-color);
  transform: translateX(4px);
}

.deployment-row__main {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.deployment-row__info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.deployment-name {
  overflow: hidden;
  max-width: 200px;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.deployment-row__meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

.deployment-time {
  white-space: nowrap;
}

.deployment-target {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deployment-row__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.deployment-row__arrow {
  color: var(--el-text-color-secondary);
  transition: transform 0.2s ease;
}

.deployment-row--clickable:hover .deployment-row__arrow {
  transform: translateX(4px);
  color: var(--el-color-primary);
}
</style>
