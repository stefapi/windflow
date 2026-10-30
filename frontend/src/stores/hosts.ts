import { defineStore } from 'pinia'
import { ref } from 'vue'
import { hostsApi } from '@/services/api'
import type { ConnectionTestRequest, ConnectionTestResponse, HealthCheckResponse, Host, HostCreate, HostReachabilityRequest, HostReachabilityResponse, HostUpdate, LegacyListBody, PaginationMeta } from '@/types/api'

/** Interval between automatic health checks (ms). */
const HEALTH_POLL_INTERVAL = 60_000 // 1 minute

export const useHostsStore = defineStore('hosts', () => {
  const hosts = ref<Host[]>([])
  const currentHost = ref<Host | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const healthCheckingIds = ref<Set<string>>(new Set())
  // STORY-128 : métadonnées de pagination exposées pour l'UI (total/pages).
  const pagination = ref<PaginationMeta | null>(null)
  let _pollTimer: ReturnType<typeof setInterval> | null = null

  async function fetchHosts(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await hostsApi.list({ organization_id: organizationId })
      // STORY-128 : post-unwrap, response.data est la liste (nouveau format
      // paginé) ; fallback transition {items} legacy et liste nue tolérés.
      const body: unknown = response.data
      hosts.value = Array.isArray(body) ? body : ((body as LegacyListBody<Host>)?.items ?? [])
      pagination.value = response.pagination ?? null
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch hosts'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchHost(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await hostsApi.get(id)
      currentHost.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch host'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createHost(data: HostCreate): Promise<Host> {
    loading.value = true
    error.value = null
    try {
      const response = await hostsApi.create(data)
      hosts.value.unshift(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to create host'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateHost(id: string, data: HostUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await hostsApi.update(id, data)
      const index = hosts.value.findIndex((h) => h.id === id)
      if (index !== -1) hosts.value[index] = response.data
      if (currentHost.value?.id === id) currentHost.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to update host'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteHost(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await hostsApi.delete(id)
      hosts.value = hosts.value.filter((h) => h.id !== id)
      if (currentHost.value?.id === id) currentHost.value = null
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to delete host'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function testReachability(data: HostReachabilityRequest): Promise<HostReachabilityResponse> {
    try {
      const response = await hostsApi.testReachability(data)
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
      const response = await hostsApi.testConnection(data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to test connection'
      throw err
    } finally {
      loading.value = false
    }
  }

  // ── Health check ──────────────────────────────────────────────

  /** Update a single host in the local list with health data */
  function _applyHealthResult(result: HealthCheckResponse): void {
    // STORY-166.6 : `host_id` est le champ canonique de
    // HostHealthCheckResponse (l'alias `target_id` n'est plus consommé).
    const idx = hosts.value.findIndex((h) => h.id === result.host_id)
    if (idx !== -1) {
      const existing = hosts.value[idx]!
      hosts.value[idx] = {
        ...existing,
        status: result.status as Host['status'],
        updated_at: result.last_check,
      }
    }
    if (currentHost.value?.id === result.host_id) {
      currentHost.value = {
        ...currentHost.value,
        status: result.status as Host['status'],
        updated_at: result.last_check,
      }
    }
  }

  /** Trigger a health check for a single host */
  async function healthCheckHost(id: string): Promise<HealthCheckResponse> {
    healthCheckingIds.value.add(id)
    try {
      const response = await hostsApi.healthCheck(id)
      _applyHealthResult(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Health check failed'
      throw err
    } finally {
      healthCheckingIds.value.delete(id)
    }
  }

  /** Run health checks for all known hosts (used by polling) */
  async function healthCheckAll(): Promise<void> {
    const ids = hosts.value.map((h) => h.id)
    for (const id of ids) {
      try {
        const response = await hostsApi.healthCheck(id)
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

  async function scanHost(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await hostsApi.scan(id)

      // Update host in the list
      const index = hosts.value.findIndex((h) => h.id === id)
      if (index !== -1) {
        hosts.value[index] = response.data
      }

      // Update currentHost if it's the same host
      if (currentHost.value?.id === id) {
        currentHost.value = response.data
      }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to scan host'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    hosts,
    currentHost,
    loading,
    error,
    pagination,
    fetchHosts,
    fetchHost,
    createHost,
    updateHost,
    deleteHost,
    scanHost,
    testReachability,
    testConnection,
    healthCheckingIds,
    healthCheckHost,
    healthCheckAll,
    startHealthPolling,
    stopHealthPolling,
  }
})
