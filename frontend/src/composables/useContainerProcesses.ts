/**
 * useContainerProcesses Composable
 * Handles fetching container processes via REST API with optional auto-refresh
 */

import { ref, onUnmounted, type Ref } from 'vue'
import http from '@/services/http'
import type { ContainerProcessListResponse, ContainerProcess } from '@/types/api'

export interface UseContainerProcessesOptions {
  containerId: string
  autoRefresh?: boolean
  refreshInterval?: number
}

export interface UseContainerProcessesReturn {
  processes: Ref<ContainerProcess[]>
  titles: Ref<string[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  timestamp: Ref<string | null>
  autoRefresh: Ref<boolean>
  fetchProcesses: () => Promise<void>
  startAutoRefresh: () => void
  stopAutoRefresh: () => void
  toggleAutoRefresh: () => void
}

const DEFAULT_REFRESH_INTERVAL = 3000 // 3 seconds

/**
 * Composable for fetching container processes
 *
 * @param options - Configuration options
 * @returns Process data and control methods
 */
export function useContainerProcesses(options: UseContainerProcessesOptions): UseContainerProcessesReturn {
  const { containerId, autoRefresh: initialAutoRefresh = false, refreshInterval = DEFAULT_REFRESH_INTERVAL } = options

  // State
  const processes = ref<ContainerProcess[]>([])
  const titles = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const timestamp = ref<string | null>(null)
  const autoRefresh = ref(initialAutoRefresh)

  let refreshTimer: ReturnType<typeof setInterval> | null = null

  /**
   * Fetch processes from API
   */
  async function fetchProcesses(): Promise<void> {
    if (loading.value) return

    loading.value = true
    error.value = null

    try {
      const response = await http.get<ContainerProcessListResponse>(
        `/docker/containers/${containerId}/top`
      )

      processes.value = response.data.processes
      titles.value = response.data.titles
      timestamp.value = response.data.timestamp
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la récupération des processus'
      error.value = errorMessage
      console.error('[ContainerProcesses] Error fetching processes:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Start auto-refresh timer
   */
  function startAutoRefresh(): void {
    if (refreshTimer) return

    autoRefresh.value = true
    refreshTimer = setInterval(() => {
      fetchProcesses()
    }, refreshInterval)
  }

  /**
   * Stop auto-refresh timer
   */
  function stopAutoRefresh(): void {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
    autoRefresh.value = false
  }

  /**
   * Toggle auto-refresh
   */
  function toggleAutoRefresh(): void {
    if (autoRefresh.value) {
      stopAutoRefresh()
    } else {
      startAutoRefresh()
    }
  }

  // Initial fetch
  fetchProcesses()

  // Start auto-refresh if enabled
  if (initialAutoRefresh) {
    startAutoRefresh()
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    processes,
    titles,
    loading,
    error,
    timestamp,
    autoRefresh,
    fetchProcesses,
    startAutoRefresh,
    stopAutoRefresh,
    toggleAutoRefresh,
  }
}
