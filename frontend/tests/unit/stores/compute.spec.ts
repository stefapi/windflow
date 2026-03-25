import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useComputeStore } from '@/stores/compute'

const mockStats = {
  total_containers: 23,
  running_containers: 18,
  stacks_count: 3,
  stacks_services_count: 9,
  discovered_count: 4,
  standalone_count: 10,
  targets_count: 4,
}

const mockGlobalView = {
  managed_stacks: [
    {
      id: 'stack-1',
      name: 'my-stack',
      technology: 'compose' as const,
      target_id: 'target-1',
      target_name: 'localhost',
      services_total: 3,
      services_running: 3,
      status: 'running' as const,
      services: [],
    },
  ],
  discovered_items: [
    {
      id: 'disc-1',
      name: 'discovered-app',
      type: 'composition' as const,
      technology: 'compose' as const,
      target_id: 'target-1',
      target_name: 'localhost',
      services_total: 2,
      services_running: 1,
      detected_at: '2026-01-01T00:00:00Z',
      adoptable: true,
    },
  ],
  standalone_containers: [
    {
      id: 'container-1',
      name: 'nginx',
      image: 'nginx:latest',
      target_id: 'target-1',
      target_name: 'localhost',
      status: 'running',
      cpu_percent: 0.5,
      memory_usage: '50M',
    },
  ],
}

vi.mock('@/services/api', () => ({
  computeApi: {
    getStats: vi.fn().mockResolvedValue({
      data: {
        total_containers: 23,
        running_containers: 18,
        stacks_count: 3,
        stacks_services_count: 9,
        discovered_count: 4,
        standalone_count: 10,
        targets_count: 4,
      },
    }),
    getGlobal: vi.fn().mockResolvedValue({
      data: {
        managed_stacks: [
          {
            id: 'stack-1',
            name: 'my-stack',
            technology: 'compose',
            target_id: 'target-1',
            target_name: 'localhost',
            services_total: 3,
            services_running: 3,
            status: 'running',
            services: [],
          },
        ],
        discovered_items: [
          {
            id: 'disc-1',
            name: 'discovered-app',
            type: 'composition',
            technology: 'compose',
            target_id: 'target-1',
            target_name: 'localhost',
            services_total: 2,
            services_running: 1,
            detected_at: '2026-01-01T00:00:00Z',
            adoptable: true,
          },
        ],
        standalone_containers: [
          {
            id: 'container-1',
            name: 'nginx',
            image: 'nginx:latest',
            target_id: 'target-1',
            target_name: 'localhost',
            status: 'running',
            cpu_percent: 0.5,
            memory_usage: '50M',
          },
        ],
      },
    }),
    getGlobalByTarget: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

describe('useComputeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('état initial', () => {
    it('should have null stats and globalView initially', () => {
      const store = useComputeStore()
      expect(store.stats).toBeNull()
      expect(store.globalView).toBeNull()
      expect(store.targetGroups).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.statsLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('getters should return [] when globalView is null', () => {
      const store = useComputeStore()
      expect(store.managedStacks).toEqual([])
      expect(store.discoveredItems).toEqual([])
      expect(store.standaloneContainers).toEqual([])
    })
  })

  describe('fetchStats', () => {
    it('should call computeApi.getStats and store result', async () => {
      const { computeApi } = await import('@/services/api')
      const store = useComputeStore()

      await store.fetchStats('org-1')

      expect(computeApi.getStats).toHaveBeenCalledWith('org-1')
      expect(store.stats).toEqual(mockStats)
      expect(store.statsLoading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should set error and reset statsLoading on API failure', async () => {
      const { computeApi } = await import('@/services/api')
      vi.mocked(computeApi.getStats).mockRejectedValueOnce(new Error('Network error'))

      const store = useComputeStore()

      await expect(store.fetchStats()).rejects.toThrow('Network error')
      expect(store.error).toBe('Network error')
      expect(store.statsLoading).toBe(false)
    })
  })

  describe('fetchGlobal', () => {
    it('should call computeApi.getGlobal and store result in globalView', async () => {
      const { computeApi } = await import('@/services/api')
      const store = useComputeStore()

      await store.fetchGlobal({ organization_id: 'org-1' })

      expect(computeApi.getGlobal).toHaveBeenCalledWith({ organization_id: 'org-1' })
      expect(store.globalView).toEqual(mockGlobalView)
      expect(store.targetGroups).toEqual([])
      expect(store.loading).toBe(false)
    })

    it('should reset targetGroups when fetching global', async () => {
      const store = useComputeStore()
      store.targetGroups = [{ target_id: 'x', target_name: 'x', technology: 'docker', stacks: [], discovered: [], standalone: [], metrics: { cpu_total_percent: 0, memory_used: '0', memory_total: '0' } }]

      await store.fetchGlobal()

      expect(store.targetGroups).toEqual([])
    })

    it('should set error and reset loading on API failure', async () => {
      const { computeApi } = await import('@/services/api')
      vi.mocked(computeApi.getGlobal).mockRejectedValueOnce(new Error('Server error'))

      const store = useComputeStore()

      await expect(store.fetchGlobal()).rejects.toThrow('Server error')
      expect(store.error).toBe('Server error')
      expect(store.loading).toBe(false)
    })
  })

  describe('fetchGlobalByTarget', () => {
    it('should call computeApi.getGlobalByTarget and store result in targetGroups', async () => {
      const { computeApi } = await import('@/services/api')
      const mockGroups = [
        {
          target_id: 'target-1',
          target_name: 'localhost',
          technology: 'docker',
          stacks: [],
          discovered: [],
          standalone: [],
          metrics: { cpu_total_percent: 10, memory_used: '500M', memory_total: '8G' },
        },
      ]
      vi.mocked(computeApi.getGlobalByTarget).mockResolvedValueOnce({ data: mockGroups } as never)

      const store = useComputeStore()
      await store.fetchGlobalByTarget({ organization_id: 'org-1' })

      expect(computeApi.getGlobalByTarget).toHaveBeenCalledWith({ organization_id: 'org-1' })
      expect(store.targetGroups).toEqual(mockGroups)
      expect(store.globalView).toBeNull()
      expect(store.loading).toBe(false)
    })
  })

  describe('getters', () => {
    it('managedStacks should return managed_stacks from globalView', async () => {
      const store = useComputeStore()
      await store.fetchGlobal()

      expect(store.managedStacks).toHaveLength(1)
      expect(store.managedStacks[0].name).toBe('my-stack')
    })

    it('discoveredItems should return discovered_items from globalView', async () => {
      const store = useComputeStore()
      await store.fetchGlobal()

      expect(store.discoveredItems).toHaveLength(1)
      expect(store.discoveredItems[0].name).toBe('discovered-app')
    })

    it('standaloneContainers should return standalone_containers from globalView', async () => {
      const store = useComputeStore()
      await store.fetchGlobal()

      expect(store.standaloneContainers).toHaveLength(1)
      expect(store.standaloneContainers[0].name).toBe('nginx')
    })

    it('getters should return [] when globalView is null', () => {
      const store = useComputeStore()
      expect(store.managedStacks).toEqual([])
      expect(store.discoveredItems).toEqual([])
      expect(store.standaloneContainers).toEqual([])
    })
  })

  describe('$reset', () => {
    it('should reset all state to initial values', async () => {
      const store = useComputeStore()
      await store.fetchStats()
      await store.fetchGlobal()

      store.$reset()

      expect(store.stats).toBeNull()
      expect(store.globalView).toBeNull()
      expect(store.targetGroups).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.statsLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })
})
