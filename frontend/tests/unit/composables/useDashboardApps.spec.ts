import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock compute store data
const mockFetchGlobal = vi.fn()

const { mockManagedStacks, mockDiscoveredItems, mockStandaloneContainers, mockLoading, mockError } =
  vi.hoisted(() => ({
    mockManagedStacks: vi.fn(() => []),
    mockDiscoveredItems: vi.fn(() => []),
    mockStandaloneContainers: vi.fn(() => []),
    mockLoading: vi.fn(() => false),
    mockError: vi.fn(() => null),
  }))

vi.mock('@/stores', () => ({
  useComputeStore: () => ({
    get managedStacks() { return mockManagedStacks() },
    get discoveredItems() { return mockDiscoveredItems() },
    get standaloneContainers() { return mockStandaloneContainers() },
    get loading() { return mockLoading() },
    get error() { return mockError() },
    fetchGlobal: mockFetchGlobal,
  }),
}))

// Import after mocks
import { useDashboardApps } from '@/composables/useDashboardApps'

describe('useDashboardApps', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('retourne une liste vide quand le store est vide', () => {
    mockManagedStacks.mockReturnValue([])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([])

    const { apps } = useDashboardApps()
    expect(apps.value).toEqual([])
  })

  it('agrège les managed stacks en AppCardData', () => {
    mockManagedStacks.mockReturnValue([
      {
        services: [
          {
            id: 'svc-1',
            name: 'nginx',
            image: 'nginx:1.26',
            status: 'running',
            cpu_percent: 2.5,
            memory_usage: '128 MB',
            ports: [],
          },
        ],
        target_name: 'localhost',
        services_total: 1,
        services_running: 1,
      },
    ])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([])

    const { apps } = useDashboardApps()
    expect(apps.value).toHaveLength(1)
    expect(apps.value[0].name).toBe('nginx')
    expect(apps.value[0].category).toBe('managed')
  })

  it('agrège les standalone containers en AppCardData', () => {
    mockManagedStacks.mockReturnValue([])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([
      {
        id: 'container-1',
        name: 'my-app',
        image: 'myapp:latest',
        status: 'running',
        cpu_percent: 5.0,
        memory_usage: '256 MB',
        target_name: 'localhost',
        ports: [],
      },
    ])

    const { apps } = useDashboardApps()
    expect(apps.value).toHaveLength(1)
    expect(apps.value[0].name).toBe('my-app')
    expect(apps.value[0].category).toBe('standalone')
  })

  it('agrège les discovered items en AppCardData', () => {
    mockManagedStacks.mockReturnValue([])
    mockDiscoveredItems.mockReturnValue([
      {
        services: [
          {
            id: 'disc-svc-1',
            name: 'redis',
            image: 'redis:7',
            status: 'running',
            cpu_percent: 1.0,
            memory_usage: '64 MB',
            ports: [],
          },
        ],
        target_name: 'vps-ovh',
        services_total: 1,
        services_running: 1,
      },
    ])
    mockStandaloneContainers.mockReturnValue([])

    const { apps } = useDashboardApps()
    expect(apps.value).toHaveLength(1)
    expect(apps.value[0].name).toBe('redis')
    expect(apps.value[0].category).toBe('discovered')
  })

  it('trie les apps par displayName', () => {
    mockManagedStacks.mockReturnValue([
      {
        services: [
          { id: 'svc-2', name: 'zzz-app', image: 'zzz:1', status: 'running', cpu_percent: 0, memory_usage: '0', ports: [] },
          { id: 'svc-1', name: 'aaa-app', image: 'aaa:1', status: 'running', cpu_percent: 0, memory_usage: '0', ports: [] },
        ],
        target_name: 'localhost',
        services_total: 2,
        services_running: 2,
      },
    ])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([])

    const { apps } = useDashboardApps()
    expect(apps.value).toHaveLength(2)
    expect(apps.value[0].name).toBe('aaa-app')
    expect(apps.value[1].name).toBe('zzz-app')
  })

  it('expose le loading du computeStore', () => {
    mockLoading.mockReturnValue(true)
    mockManagedStacks.mockReturnValue([])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([])

    const { loading } = useDashboardApps()
    expect(loading.value).toBe(true)
  })

  it('expose l\'erreur du computeStore', () => {
    mockError.mockReturnValue('Network error')
    mockManagedStacks.mockReturnValue([])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([])

    const { error } = useDashboardApps()
    expect(error.value).toBe('Network error')
  })

  it('fetchApps appelle computeStore.fetchGlobal', async () => {
    mockFetchGlobal.mockResolvedValue(undefined)
    mockManagedStacks.mockReturnValue([])
    mockDiscoveredItems.mockReturnValue([])
    mockStandaloneContainers.mockReturnValue([])

    const { fetchApps } = useDashboardApps()
    await fetchApps('org-123')

    expect(mockFetchGlobal).toHaveBeenCalledWith({ organization_id: 'org-123' })
  })
})
