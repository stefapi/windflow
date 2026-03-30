import { defineStore } from 'pinia'
import { ref } from 'vue'
import { targetsApi } from '@/services/api'
import type { ConnectionTestRequest, ConnectionTestResponse, HealthCheckResponse, HostReachabilityRequest, HostReachabilityResponse, Target, TargetCreate, TargetUpdate } from '@/types/api'

/** Interval between automatic health checks (ms). */
const HEALTH_POLL_INTERVAL = 60_000 // 1 minute

export const useTargetsStore = defineStore('targets', () => {
  const targets = ref<Target[]>([])
  const currentTarget = ref<Target | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const healthCheckingIds = ref<Set<string>>(new Set())
  let _pollTimer: ReturnType<typeof setInterval> | null = null

  async function fetchTargets(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.list({ organization_id: organizationId })
      // Backend returns List[TargetResponse] directly, not wrapped in {items:[]}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      targets.value = (response.data as any).items || response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch targets'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchTarget(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.get(id)
      currentTarget.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createTarget(data: TargetCreate): Promise<Target> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.create(data)
      targets.value.unshift(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to create target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateTarget(id: string, data: TargetUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.update(id, data)
      const index = targets.value.findIndex(t => t.id === id)
      if (index !== -1) targets.value[index] = response.data
      if (currentTarget.value?.id === id) currentTarget.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to update target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteTarget(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await targetsApi.delete(id)
      targets.value = targets.value.filter(t => t.id !== id)
      if (currentTarget.value?.id === id) currentTarget.value = null
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to delete target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function testReachability(data: HostReachabilityRequest): Promise<HostReachabilityResponse> {
    try {
      const response = await targetsApi.testReachability(data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to test reachability'
      throw err
    }
  }

  async function testConnection(data: ConnectionTestRequest): Promise<ConnectionTestResponse> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.testConnection(data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to test connection'
      throw err
    } finally {
      loading.value = false
    }
  }

  // ── Health check ──────────────────────────────────────────────

  /** Update a single target in the local list with health data */
  function _applyHealthResult(result: HealthCheckResponse): void {
    const idx = targets.value.findIndex(t => t.id === result.target_id)
    if (idx !== -1) {
      targets.value[idx] = {
        ...targets.value[idx],
        status: result.status as Target['status'],
        updated_at: result.last_check,
      }
    }
    if (currentTarget.value?.id === result.target_id) {
      currentTarget.value = {
        ...currentTarget.value,
        status: result.status as Target['status'],
        updated_at: result.last_check,
      }
    }
  }

  /** Trigger a health check for a single target */
  async function healthCheckTarget(id: string): Promise<HealthCheckResponse> {
    healthCheckingIds.value.add(id)
    try {
      const response = await targetsApi.healthCheck(id)
      _applyHealthResult(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Health check failed'
      throw err
    } finally {
      healthCheckingIds.value.delete(id)
    }
  }

  /** Run health checks for all known targets (used by polling) */
  async function healthCheckAll(): Promise<void> {
    const ids = targets.value.map(t => t.id)
    for (const id of ids) {
      try {
        const response = await targetsApi.healthCheck(id)
        _applyHealthResult(response.data)
      } catch {
        // Silently skip — next poll will retry
      }
    }
  }

  /** Start periodic health polling (idempotent) */
  function startHealthPolling(intervalMs: number = HEALTH_POLL_INTERVAL): void {
    if (_pollTimer) return
    // Initial immediate check
    healthCheckAll()
    _pollTimer = setInterval(() => healthCheckAll(), intervalMs)
  }

  /** Stop periodic health polling */
  function stopHealthPolling(): void {
    if (_pollTimer) {
      clearInterval(_pollTimer)
      _pollTimer = null
    }
  }

  async function scanTarget(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.scan(id)

      // Update target in the list
      const index = targets.value.findIndex(t => t.id === id)
      if (index !== -1) {
        targets.value[index] = response.data
      }

      // Update currentTarget if it's the same target
      if (currentTarget.value?.id === id) {
        currentTarget.value = response.data
      }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to scan target'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    targets,
    currentTarget,
    loading,
    error,
    fetchTargets,
    fetchTarget,
    createTarget,
    updateTarget,
    deleteTarget,
    scanTarget,
    testReachability,
    testConnection,
    healthCheckingIds,
    healthCheckTarget,
    healthCheckAll,
    startHealthPolling,
    stopHealthPolling,
  }
})
