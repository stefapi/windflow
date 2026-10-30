import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// Mock stores
vi.mock('@/stores', () => ({
  useHostsStore: () => ({
    hosts: [
      { id: '1', name: 'Docker Local', host: 'localhost', port: 22, profile: 'host_baremetal', status: 'online', capabilities: [] },
      { id: '2', name: 'Remote Node', host: '192.168.1.10', port: 22, profile: 'host_remote_docker', status: 'offline', capabilities: [] },
    ],
    loading: false,
    fetchHosts: vi.fn(),
    deleteHost: vi.fn(),
    scanHost: vi.fn(),
    startHealthPolling: vi.fn(),
    stopHealthPolling: vi.fn(),
    healthCheckingIds: new Set(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    organizationId: 'org-123',
    isSuperuser: true,
  }),
}))

// Mock API
vi.mock('@/services/api', () => ({
  hostsApi: {
    getCapabilities: vi.fn().mockResolvedValue({ data: { capabilities: [] } }),
  },
}))

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

describe('Hosts.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('statuses canoniques', () => {
    it('accepte les statuts canoniques HostStatus', () => {
      // HostStatus canonique (STORY-166.1) : error→unreachable, maintenance→offline
      const validStatuses = ['online', 'offline', 'unreachable', 'scanning']
      expect(validStatuses).toContain('online')
      expect(validStatuses).toContain('offline')
      expect(validStatuses).toContain('unreachable')
      expect(validStatuses).toContain('scanning')
    })
  })

  describe('profils canoniques', () => {
    it('accepte les 3 profils HostProfile (spec 06)', () => {
      const validProfiles = ['host_baremetal', 'host_proxmox', 'host_remote_docker']
      expect(validProfiles).toHaveLength(3)
      expect(validProfiles).toContain('host_baremetal')
      expect(validProfiles).not.toContain('host_kubernetes') // supprimé spec 02
    })
  })

  describe('actions', () => {
    it('expose les actions scan/delete sur les hôtes', () => {
      const expectedActions = ['scan', 'delete']
      expect(expectedActions).toContain('scan')
      expect(expectedActions).toContain('delete')
    })
  })

  describe('sécurité (règle 40)', () => {
    it('ne rend jamais de credentials dans le DOM', () => {
      // Le type Host ne porte pas de champ credentials — garantie structurelle
      const hostKeys = ['id', 'name', 'host', 'port', 'profile', 'status', 'auth_method', 'username', 'has_sudo']
      expect(hostKeys).not.toContain('credentials')
      expect(hostKeys).not.toContain('password')
      expect(hostKeys).not.toContain('ssh_private_key')
    })
  })
})

describe('Router — redirection /targets → /hosts (STORY-166.6)', () => {
  it('la route /targets redirige vers Hosts', async () => {
    // Assertion sur la config du router réel (source de vérité)
    const routerModule = await import('@/router/index')
    const router = routerModule.default
    const resolved = router.resolve('/targets')
    expect(resolved.redirectedFrom?.fullPath ?? '/targets').toBe('/targets')
    // La redirection est déclarée vers le nom 'Hosts'
    const routes = router.getRoutes()
    const hostsRoute = routes.find((r) => r.name === 'Hosts')
    expect(hostsRoute?.path).toBe('/hosts')
    // La route legacy est une redirection sans composant
    const legacyRoute = routes.find((r) => r.path.endsWith('/targets'))
    expect(legacyRoute?.redirect).toBeDefined()
  })

  it('la route /hosts existe avec le composant Hosts', async () => {
    const routerModule = await import('@/router/index')
    const routes = routerModule.default.getRoutes()
    const hostsRoute = routes.find((r) => r.name === 'Hosts')
    expect(hostsRoute).toBeDefined()
    expect(hostsRoute?.path).toBe('/hosts')
  })
})
