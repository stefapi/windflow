import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { listMock, healthCheckMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  healthCheckMock: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  hostsApi: {
    list: listMock,
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    scan: vi.fn(),
    getCapabilities: vi.fn(),
    testReachability: vi.fn(),
    testConnection: vi.fn(),
    healthCheck: healthCheckMock,
  },
}))

import { useHostsStore } from '@/stores/hosts'
import type { Host } from '@/types/api'

function makeHost(overrides: Partial<Host> = {}): Host {
  return {
    id: 'host-1',
    name: 'Test Host',
    host: '127.0.0.1',
    port: 22,
    profile: 'host_baremetal',
    type: 'physical',
    description: null,
    status: 'online',
    auth_method: 'local',
    username: null,
    has_sudo: false,
    scan_date: null,
    scan_success: null,
    platform_info: null,
    hardware_info: null,
    installed_engines: [],
    last_scan_at: null,
    origin: 'managed',
    environment_id: null,
    os_info: null,
    access_profile: null,
    extra_metadata: {},
    organization_id: 'org-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('useHostsStore (STORY-166.6)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('fetchHosts — enveloppe STORY-128', () => {
    it('liste vide → hosts = []', async () => {
      listMock.mockResolvedValue({ data: [], pagination: { page: 1, per_page: 20, total: 0, total_pages: 0 } })
      const store = useHostsStore()
      await store.fetchHosts()
      expect(store.hosts).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('dépacke response.data (enveloppe paginée) et propage la meta pagination', async () => {
      const hosts = [makeHost(), makeHost({ id: 'host-2', name: 'Second' })]
      listMock.mockResolvedValue({
        data: hosts,
        pagination: { page: 1, per_page: 20, total: 2, total_pages: 1 },
      })
      const store = useHostsStore()
      await store.fetchHosts('org-42')
      expect(listMock).toHaveBeenCalledWith({ organization_id: 'org-42' })
      expect(store.hosts).toHaveLength(2)
      expect(store.pagination?.total).toBe(2)
    })

    it('tolère le fallback legacy {items} et la liste nue', async () => {
      listMock.mockResolvedValueOnce({ data: { items: [makeHost()] }, pagination: null })
      const store = useHostsStore()
      await store.fetchHosts()
      expect(store.hosts).toHaveLength(1)
    })

    it('erreur API → error setté, pas de crash', async () => {
      listMock.mockRejectedValue(new Error('Network Error'))
      const store = useHostsStore()
      await expect(store.fetchHosts()).rejects.toThrow('Network Error')
      expect(store.error).toBe('Network Error')
      expect(store.loading).toBe(false)
    })

    it('401 → aucune donnée stockée en clair (sécurité)', async () => {
      listMock.mockRejectedValue(new Error('Request failed with status code 401'))
      const store = useHostsStore()
      await expect(store.fetchHosts()).rejects.toThrow()
      expect(store.hosts).toEqual([])
      expect(store.error).not.toMatch(/password|token|secret/i)
    })
  })

  describe('health polling (non-régression)', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('_applyHealthResult met à jour le statut du host via host_id canonique', async () => {
      listMock.mockResolvedValue({ data: [makeHost({ status: 'online' })], pagination: null })
      const store = useHostsStore()
      await store.fetchHosts()

      healthCheckMock.mockResolvedValue({
        data: { host_id: 'host-1', status: 'unreachable', last_check: '2026-01-02T00:00:00Z', message: 'down' },
      })
      await store.healthCheckHost('host-1')

      expect(store.hosts[0]!.status).toBe('unreachable')
    })

    it('healthCheckHost consomme host_id canonique (plus target_id)', async () => {
      listMock.mockResolvedValue({ data: [makeHost()], pagination: null })
      const store = useHostsStore()
      await store.fetchHosts()

      healthCheckMock.mockResolvedValue({
        data: { host_id: 'host-1', status: 'online', last_check: '2026-01-02T00:00:00Z', message: 'up' },
      })
      const result = await store.healthCheckHost('host-1')
      expect(result.host_id).toBe('host-1')
      expect(store.hosts[0]!.status).toBe('online')
    })

    it('startHealthPolling déclenche un check immédiat puis à intervalle — stop purge', async () => {
      listMock.mockResolvedValue({ data: [makeHost()], pagination: null })
      const store = useHostsStore()
      await store.fetchHosts()

      healthCheckMock.mockResolvedValue({
        data: { host_id: 'host-1', status: 'online', last_check: '2026-01-02T00:00:00Z', message: 'up' },
      })

      store.startHealthPolling(1000)
      // Check initial immédiat
      await vi.advanceTimersByTimeAsync(0)
      expect(healthCheckMock).toHaveBeenCalledTimes(1)

      // Interval suivant
      await vi.advanceTimersByTimeAsync(1000)
      expect(healthCheckMock).toHaveBeenCalledTimes(2)

      // Stop → plus aucun appel
      store.stopHealthPolling()
      await vi.advanceTimersByTimeAsync(5000)
      expect(healthCheckMock).toHaveBeenCalledTimes(2)
    })

    it('échec health-check silencieux dans le polling (retry au prochain cycle)', async () => {
      listMock.mockResolvedValue({ data: [makeHost()], pagination: null })
      const store = useHostsStore()
      await store.fetchHosts()

      healthCheckMock.mockRejectedValue(new Error('unreachable network'))
      store.startHealthPolling(1000)
      await vi.advanceTimersByTimeAsync(0)
      expect(store.error).toBeNull() // échec silencieux
      store.stopHealthPolling()
    })
  })

  describe('scanHost', () => {
    it('met à jour le host dans la liste après scan', async () => {
      const scanned = makeHost({ status: 'scanning', installed_engines: [{ capability_type: 'docker', version: '27.0', is_available: true }] })
      listMock.mockResolvedValue({ data: [makeHost()], pagination: null })
      const { hostsApi } = await import('@/services/api')
      ;(hostsApi.scan as ReturnType<typeof vi.fn>).mockResolvedValue({ data: scanned })

      const store = useHostsStore()
      await store.fetchHosts()
      await store.scanHost('host-1')
      expect(store.hosts[0]!.installed_engines).toHaveLength(1)
    })
  })
})
