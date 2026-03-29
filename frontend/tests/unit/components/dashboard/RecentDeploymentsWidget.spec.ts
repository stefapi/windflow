import { describe, it, expect, vi, beforeEach, beforeAll, afterAll } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import RecentDeploymentsWidget from '@/components/dashboard/RecentDeploymentsWidget.vue'
import type { Deployment } from '@/types/api'

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

// Mock deployments API
const mockDeploymentsResponse = {
  data: {
    items: [] as Deployment[],
    total: 0,
    page: 1,
    size: 10,
    pages: 1,
  },
}

vi.mock('@/services/api', () => ({
  deploymentsApi: {
    list: vi.fn(() => Promise.resolve(mockDeploymentsResponse)),
    retry: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

// Mock formatRelativeTime
vi.mock('@/composables/useRelativeTime', () => ({
  formatRelativeTime: (date: string) => {
    if (!date) return ''
    return 'il y a 2h'
  },
}))

// Mock window timers - must be set before component import
const mockSetInterval = vi.fn(() => 1)
const mockClearInterval = vi.fn()

// Store original timers
const originalSetInterval = window.setInterval
const originalClearInterval = window.clearInterval

// Set up mocks before tests
beforeAll(() => {
  window.setInterval = mockSetInterval
  window.clearInterval = mockClearInterval
})

afterAll(() => {
  window.setInterval = originalSetInterval
  window.clearInterval = originalClearInterval
})

const createDeployment = (overrides?: Partial<Deployment>): Deployment => ({
  id: 'test-deployment-id',
  name: 'test-deployment',
  stack_id: 'stack-1',
  target_id: 'target-1',
  status: 'completed',
  config: {},
  container_id: null,
  variables: {},
  logs: null,
  error_message: null,
  metadata: {},
  organization_id: 'org-1',
  deployed_at: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
})

describe('RecentDeploymentsWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDeploymentsResponse.data.items = []
  })

  describe('rendering', () => {
    it('should render with data-testid', async () => {
      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot name="header" /><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-empty': { template: '<div class="el-empty" />' },
            'el-alert': { template: '<div class="el-alert" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      // Wait for loading to complete
      await nextTick()

      expect(wrapper.find('[data-testid="recent-deployments-widget"]').exists()).toBe(true)
    })

    it('should show loading state initially', () => {
      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton">Loading...</div>' },
          },
        },
      })

      expect(wrapper.find('.recent-deployments-widget__loading').exists()).toBe(true)
    })

    it('should show empty state when no deployments', async () => {
      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-empty': { template: '<div class="el-empty" data-testid="deployments-empty">No deployments</div>' },
          },
        },
      })

      // Trigger fetch and wait
      await nextTick()
      await nextTick()

      expect(wrapper.find('[data-testid="deployments-empty"]').exists()).toBe(true)
    })

    it('should display deployment list when deployments exist', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({ id: 'dep-1', name: 'Deployment 1', status: 'completed' }),
        createDeployment({ id: 'dep-2', name: 'Deployment 2', status: 'failed' }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-empty': { template: '<div class="el-empty" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.find('.deployments-list').exists()).toBe(true)
      expect(wrapper.findAll('.deployment-row')).toHaveLength(2)
    })

    it('should display deployment name', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({ id: 'dep-1', name: 'My App Deployment' }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.text()).toContain('My App Deployment')
    })

    it('should display truncated ID when name is null', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({ id: '12345678-1234-1234-1234-123456789abc', name: null }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.text()).toContain('12345678')
    })

    it('should display relative time', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({ created_at: new Date(Date.now() - 7200000).toISOString() }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.text()).toContain('il y a 2h')
    })

    it('should display target name when available', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({
          target: {
            id: 'target-1',
            name: 'Production Server',
            type: 'docker',
            host: 'localhost',
            port: 2375,
            status: 'online',
            metadata: {},
            organization_id: 'org-1',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.text()).toContain('Production Server')
    })
  })

  describe('retry button', () => {
    it('should show retry button for failed deployments', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({ id: 'dep-1', status: 'failed' }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button class="retry-btn"><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.text()).toContain('Redéployer')
    })

    it('should NOT show retry button for successful deployments', async () => {
      mockDeploymentsResponse.data.items = [
        createDeployment({ id: 'dep-1', status: 'completed' }),
      ]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.text()).not.toContain('Redéployer')
    })
  })

  describe('navigation', () => {
    it('should navigate to deployment detail on row click', async () => {
      const deployment = createDeployment({ id: 'dep-123' })
      mockDeploymentsResponse.data.items = [deployment]

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-button': { template: '<button><slot /></button>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
            StatusBadge: { template: '<span class="status-badge" />' },
          },
        },
      })

      await nextTick()
      await nextTick()

      const row = wrapper.find('.deployment-row')
      await row.trigger('click')

      expect(mockPush).toHaveBeenCalledWith('/deployments/dep-123')
    })
  })

  describe('error handling', () => {
    it('should show error state when API fails', async () => {
      const { deploymentsApi } = await import('@/services/api')
      vi.mocked(deploymentsApi.list).mockRejectedValueOnce(new Error('Network error'))

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-alert': { template: '<div class="el-alert" data-testid="deployments-error"><slot /></div>' },
          },
        },
      })

      await nextTick()
      await nextTick()

      expect(wrapper.find('[data-testid="deployments-error"]').exists()).toBe(true)
    })
  })

  describe('polling', () => {
    it('should set up polling on mount', async () => {
      mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
          },
        },
      })

      expect(mockSetInterval).toHaveBeenCalled()
    })

    it('should clear polling on unmount', async () => {
      // Clear previous calls
      mockClearInterval.mockClear()

      const wrapper = mount(RecentDeploymentsWidget, {
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
          },
        },
      })

      wrapper.unmount()
      expect(mockClearInterval).toHaveBeenCalled()
    })
  })
})
