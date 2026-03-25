/**
 * Compute Store
 * Pinia store for Compute global view management (STORY-021)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { computeApi } from '@/services/api'
import type {
  ComputeStatsResponse,
  ComputeGlobalView,
  TargetGroup,
  ControlLevel,
  StackWithServices,
  DiscoveredItem,
  StandaloneContainer,
} from '@/types/api'

type ComputeGlobalParams = {
  type?: ControlLevel
  technology?: string
  target_id?: string
  status?: string
  search?: string
  organization_id?: string
}

export const useComputeStore = defineStore('compute', () => {
  // State
  const stats = ref<ComputeStatsResponse | null>(null)
  const globalView = ref<ComputeGlobalView | null>(null)
  const targetGroups = ref<TargetGroup[]>([])
  const loading = ref(false)
  const statsLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const managedStacks = computed<StackWithServices[]>(() =>
    globalView.value?.managed_stacks ?? []
  )

  const discoveredItems = computed<DiscoveredItem[]>(() =>
    globalView.value?.discovered_items ?? []
  )

  const standaloneContainers = computed<StandaloneContainer[]>(() =>
    globalView.value?.standalone_containers ?? []
  )

  // Actions
  async function fetchStats(organizationId?: string): Promise<void> {
    statsLoading.value = true
    error.value = null

    try {
      const response = await computeApi.getStats(organizationId)
      stats.value = response.data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement des statistiques compute'
      error.value = errorMessage
      throw err
    } finally {
      statsLoading.value = false
    }
  }

  async function fetchGlobal(params?: ComputeGlobalParams): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await computeApi.getGlobal(params)
      globalView.value = response.data
      targetGroups.value = []
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement de la vue globale compute'
      error.value = errorMessage
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchGlobalByTarget(params?: ComputeGlobalParams): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await computeApi.getGlobalByTarget(params)
      targetGroups.value = response.data
      globalView.value = null
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement de la vue par target compute'
      error.value = errorMessage
      throw err
    } finally {
      loading.value = false
    }
  }

  function $reset(): void {
    stats.value = null
    globalView.value = null
    targetGroups.value = []
    loading.value = false
    statsLoading.value = false
    error.value = null
  }

  return {
    // State
    stats,
    globalView,
    targetGroups,
    loading,
    statsLoading,
    error,
    // Getters
    managedStacks,
    discoveredItems,
    standaloneContainers,
    // Actions
    fetchStats,
    fetchGlobal,
    fetchGlobalByTarget,
    $reset,
  }
})
