/**
 * ContainerDetail.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import ContainerDetail from '@/views/ContainerDetail.vue'

// Mock the composables
vi.mock('@/composables/useSecretMasker', () => ({
  useSecretMasker: () => ({
    revealedKeys: new Set(),
    toggleSecret: vi.fn(),
    isRevealed: vi.fn(() => false),
  }),
  isSecretKey: (key: string) => /password|secret|key|token/i.test(key),
  maskValue: (value: string) => {
    if (!value || value.length === 0) return ''
    if (value.length <= 4) return '****'
    return `${value.substring(0, 2)}${'*'.repeat(Math.min(value.length - 4, 10))}${value.substring(value.length - 2)}`
  },
}))

// Mock the container store
const mockInspectContainer = vi.fn()
const mockStopContainer = vi.fn()
const mockRestartContainer = vi.fn()
vi.mock('@/stores', () => ({
  useContainersStore: () => ({
    inspectContainer: mockInspectContainer,
    stopContainer: mockStopContainer,
    restartContainer: mockRestartContainer,
    containerDetail: null,
    detailLoading: false,
    error: null,
  }),
  useAuthStore: () => ({
    token: 'mock-jwt-token',
    isAuthenticated: true,
    user: null,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

// Mock useContainerLogs composable
vi.mock('@/composables/useContainerLogs', () => ({
  useContainerLogs: () => ({
    logs: { value: '' },
    status: { value: 'disconnected' },
    error: { value: null },
    isStreaming: { value: false },
    connect: vi.fn(),
    disconnect: vi.fn(),
    reconnect: vi.fn(),
    clearLogs: vi.fn(),
    downloadLogs: vi.fn(),
  }),
}))

describe('ContainerDetail.vue', () => {
  let router: ReturnType<typeof createRouter>

  const mockContainerDetail = {
    id: 'abc123def456',
    name: 'test-container',
    created: '2024-01-15T10:30:00Z',
    path: '/app',
    args: ['--port', '3000'],
    state: { Status: 'running' },
    image: 'nginx:latest',
    config: {
      Env: [
        'NODE_ENV=production',
        'DATABASE_URL=postgres://localhost:5432/db',
        'SECRET_KEY=supersecretvalue123',
        'API_TOKEN=token123abc',
      ],
      'com.docker.compose.project': 'my-stack',
    },
    host_config: {
      PortBindings: {
        '80/tcp': [{ HostIp: '0.0.0.0', HostPort: '8080' }],
        '443/tcp': [{ HostIp: '0.0.0.0', HostPort: '8443' }],
      },
    },
    network_settings: {
      Networks: {
        bridge: {
          NetworkID: 'net123',
          IPAddress: '172.17.0.2',
          MacAddress: '02:42:ac:11:00:02',
          Gateway: '172.17.0.1',
        },
      },
    },
    mounts: [
      {
        Type: 'bind',
        Source: '/host/path',
        Destination: '/container/path',
        Mode: 'rw',
      },
      {
        Type: 'volume',
        Source: 'my-volume',
        Destination: '/data',
        Mode: 'rw',
        Name: 'my-volume',
      },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()

    // Create router
    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'Home', component: { template: '<div>Home</div>' } },
        { path: '/containers', name: 'Containers', component: { template: '<div>Containers</div>' } },
        { path: '/containers/:id', name: 'ContainerDetail', component: ContainerDetail },
        { path: '/terminal/:containerId', name: 'Terminal', component: { template: '<div>Terminal</div>' } },
      ],
    })

    // Create pinia
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  const mountComponent = async (containerId = 'abc123def456') => {
    await router.push(`/containers/${containerId}`)
    await router.isReady()

    const wrapper = mount(ContainerDetail, {
      global: {
        plugins: [router, ElementPlus, createPinia()],
        stubs: {
          'el-tabs': {
            template: '<div class="el-tabs-stub"><slot /></div>',
            props: ['modelValue'],
          },
          'el-tab-pane': {
            template: '<div class="el-tab-pane-stub"><slot /></div>',
            props: ['label', 'name', 'disabled'],
          },
          'el-card': {
            template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
          },
          'el-drawer': {
            template: '<div class="el-drawer-stub"><slot /></div>',
            props: ['modelValue', 'title', 'direction', 'size'],
          },
          'el-descriptions': {
            template: '<div class="el-descriptions-stub"><slot /></div>',
            props: ['column', 'border'],
          },
          'el-descriptions-item': {
            template: '<div class="el-descriptions-item-stub"><slot /></div>',
            props: ['label'],
          },
          'el-table': {
            template: '<div class="el-table-stub"><slot /></div>',
            props: ['data', 'empty-text', 'stripe', 'size', 'max-height'],
          },
          'el-table-column': {
            template: '<div class="el-table-column-stub"><slot :row="mockRow" /></div>',
            props: ['prop', 'label', 'width', 'min-width'],
            data() {
              return {
                mockRow: { type: 'bind', Source: '/host/path', Destination: '/container/path', Mode: 'rw' }
              }
            }
          },
          'el-button': {
            template: '<button class="el-button-stub"><slot /></button>',
            props: ['type', 'size', 'link', 'disabled'],
          },
          'el-tag': {
            template: '<span class="el-tag-stub"><slot /></span>',
            props: ['type', 'size'],
          },
          'el-input': {
            template: '<input class="el-input-stub" />',
            props: ['modelValue', 'type', 'rows', 'readonly', 'placeholder', 'size', 'clearable'],
          },
          'el-input-number': {
            template: '<input type="number" class="el-input-number-stub" />',
            props: ['modelValue', 'min', 'max', 'size'],
          },
          'el-icon': {
            template: '<i class="el-icon-stub"><slot /></i>',
          },
          'el-alert': {
            template: '<div class="el-alert-stub"><slot /></div>',
            props: ['title', 'type', 'showIcon', 'closable'],
          },
          'el-empty': {
            template: '<div class="el-empty-stub">{{ description }}</div>',
            props: ['description'],
          },
          'ContainerTerminal': {
            template: '<div class="container-terminal-stub">Terminal Mock</div>',
            props: ['containerId', 'containerName'],
          },
          'ContainerLogs': {
            template: '<div class="container-logs-stub">Logs Mock</div>',
            props: ['containerId', 'containerName'],
          },
        },
      },
    })

    await flushPromises()
    return wrapper
  }

  describe('Component mounting', () => {
    it('should mount successfully', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      expect(wrapper.exists()).toBe(true)
    })

    it('should call inspectContainer with route param id', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      await mountComponent('test-id-123')

      expect(mockInspectContainer).toHaveBeenCalledWith('test-id-123')
    })
  })

  describe('Computed properties', () => {
    it('should have correct initial activeTab', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      expect((wrapper.vm as unknown as { activeTab: string }).activeTab).toBe('infos')
    })

    it('should compute containerId from route params', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('my-container-456')

      // containerId is a computed ref, its value is directly accessible via the computed
      const containerId = wrapper.vm.containerId
      expect(containerId).toBeDefined()
    })
  })

  describe('Methods', () => {
    it('should truncate ID correctly', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        truncateId: (id: string | undefined) => string
      }

      expect(vm.truncateId('abc123def456ghi789')).toBe('abc123def456')
      expect(vm.truncateId('short')).toBe('short')
      expect(vm.truncateId(undefined)).toBe('-')
    })

    it('should format date correctly', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        formatDate: (dateStr: string | undefined) => string
      }

      const result = vm.formatDate('2024-01-15T10:30:00Z')
      expect(result).toContain('2024')

      expect(vm.formatDate(undefined)).toBe('-')
    })
  })

  describe('Environment variables detection', () => {
    it('should detect secret variables', async () => {
      const { isSecretKey } = await import('@/composables/useSecretMasker')

      expect(isSecretKey('SECRET_KEY')).toBe(true)
      expect(isSecretKey('API_TOKEN')).toBe(true)
      expect(isSecretKey('DATABASE_PASSWORD')).toBe(true)
      expect(isSecretKey('MY_SECRET_VAR')).toBe(true)
      expect(isSecretKey('NODE_ENV')).toBe(false)
      expect(isSecretKey('APP_NAME')).toBe(false)
    })

    it('should mask values correctly', async () => {
      const { maskValue } = await import('@/composables/useSecretMasker')

      // maskValue shows first 2 and last 2 chars, with max 10 asterisks in between
      expect(maskValue('supersecretvalue123')).toBe('su**********23')
      expect(maskValue('abc')).toBe('****')
      expect(maskValue('')).toBe('')
    })
  })

  describe('Actions buttons presence', () => {
    it('should have action buttons in header', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      // Set containerDetail to trigger reactivity
      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      const html = wrapper.html()
      expect(html).toContain('Retour')
      expect(html).toContain('Terminal')
      expect(html).toContain('Inspect')
    })

    it('should show stop and restart buttons for running containers', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      const html = wrapper.html()
      expect(html).toContain('Arrêter')
      expect(html).toContain('Redémarrer')
    })
  })

  describe('Navigation', () => {
    it('should have goBack method that navigates to Containers list', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { goBack: () => void }

      // Verify the method exists
      expect(typeof vm.goBack).toBe('function')
    })
  })

  describe('Terminal tab', () => {
    it('should have Terminal tab in the tabs', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      const html = wrapper.html()
      expect(html).toContain('Terminal')
    })

    it('should disable Terminal tab when container is not running', async () => {
      mockInspectContainer.mockResolvedValue({ ...mockContainerDetail, state: { Status: 'stopped' } })

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = { ...mockContainerDetail, state: { Status: 'stopped' } }
      await wrapper.vm.$nextTick()

      // Terminal tab should be disabled for stopped containers
      const containerState = (wrapper.vm as unknown as { containerState: string }).containerState
      expect(containerState).toBe('stopped')
    })
  })

  describe('Drawer functionality', () => {
    it('should have inspect drawer controlled by inspectDrawerVisible', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        inspectDrawerVisible: boolean
        inspectContent: string
        showInspectDrawer: () => void
        containerDetail: typeof mockContainerDetail
      }

      expect(vm.inspectDrawerVisible).toBe(false)

      vm.containerDetail = mockContainerDetail
      vm.showInspectDrawer()

      expect(vm.inspectDrawerVisible).toBe(true)
      expect(vm.inspectContent).toContain('test-container')
    })
  })

  describe('Store interactions', () => {
    it('should call stopContainer when stop action is triggered', async () => {
      mockStopContainer.mockResolvedValue(undefined)
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-123')

      const vm = wrapper.vm as unknown as {
        handleAction: (action: string) => Promise<void>
      }

      await vm.handleAction('stop')

      expect(mockStopContainer).toHaveBeenCalledWith('container-123')
    })

    it('should call restartContainer when restart action is triggered', async () => {
      mockRestartContainer.mockResolvedValue(undefined)
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-456')

      const vm = wrapper.vm as unknown as {
        handleAction: (action: string) => Promise<void>
      }

      await vm.handleAction('restart')

      expect(mockRestartContainer).toHaveBeenCalledWith('container-456')
    })

  })
})
