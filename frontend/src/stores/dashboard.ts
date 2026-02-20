/**
 * Dashboard Store
 * Gestion centralisée des statistiques du dashboard.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { dashboardApi } from '@/services/api'
import type { DashboardStats } from '@/types/api'

export const useDashboardStore = defineStore('dashboard', () => {
  // State
  const stats = ref<DashboardStats | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const targetHealth = computed(() => stats.value?.target_health ?? {})
  const targetsDetail = computed(() => stats.value?.targets_detail ?? [])
  const deploymentMetrics = computed(() => stats.value?.deployment_metrics ?? null)
  const recentActivity = computed(() => stats.value?.recent_activity ?? [])
  const totalTargets = computed(() => stats.value?.total_targets ?? 0)
  const onlineTargets = computed(() => stats.value?.online_targets ?? 0)
  const totalStacks = computed(() => stats.value?.total_stacks ?? 0)
  const activeDeployments = computed(() => stats.value?.active_deployments ?? 0)
  const totalWorkflows = computed(() => stats.value?.total_workflows ?? 0)

  // Actions
  async function fetchDashboardStats(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await dashboardApi.getStats(organizationId)
      stats.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Erreur lors du chargement des statistiques'
      console.error('Dashboard stats fetch error:', err)
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    loading,
    error,
    targetHealth,
    targetsDetail,
    deploymentMetrics,
    recentActivity,
    totalTargets,
    onlineTargets,
    totalStacks,
    activeDeployments,
    totalWorkflows,
    fetchDashboardStats,
  }
})
