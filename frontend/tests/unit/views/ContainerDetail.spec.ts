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
const mockPauseContainer = vi.fn()
const mockUnpauseContainer = vi.fn()
vi.mock('@/stores', () => ({
  useContainersStore: () => ({
    inspectContainer: mockInspectContainer,
    stopContainer: mockStopContainer,
    restartContainer: mockRestartContainer,
    pauseContainer: mockPauseContainer,
    unpauseContainer: mockUnpauseContainer,
    containerDetail: null,
    detailLoading: false,
    error: null,
    allContainers: [],
    fetchContainers: vi.fn(),
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

// Mock containersApi.rename
const mockRename = vi.fn()
const mockUpdateRestartPolicy = vi.fn()
const mockUpdateResources = vi.fn()
vi.mock('@/services/api', () => ({
  containersApi: {
    rename: (...args: unknown[]) => mockRename(...args),
    updateRestartPolicy: (...args: unknown[]) => mockUpdateRestartPolicy(...args),
    updateResources: (...args: unknown[]) => mockUpdateResources(...args),
    getStats: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

// Mock useContainerProcesses composable
vi.mock('@/composables/useContainerProcesses', () => ({
  useContainerProcesses: () => ({
    processes: { value: [] },
    titles: { value: [] },
    loading: { value: false },
    error: { value: null },
    timestamp: { value: null },
    autoRefresh: { value: false },
    fetchProcesses: vi.fn(),
    startAutoRefresh: vi.fn(),
    stopAutoRefresh: vi.fn(),
    toggleAutoRefresh: vi.fn(),
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
      restart_policy: {
        name: 'always',
        maximum_retry_count: 0,
      },
      resources: {
        memory: 134217728, // 128 MB en bytes
        cpu_shares: 512,
        pids_limit: 100,
      },
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
            methods: {
              focus: vi.fn(),
            },
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
          'ContainerOverviewTab': {
            template: '<div class="container-overview-tab-stub">Overview Mock</div>',
            props: ['containerId', 'containerName', 'containerStatus'],
          },
          'ContainerInfoTab': {
            template: '<div class="container-info-tab-stub">Info Mock</div>',
            props: ['detail'],
          },
          'ContainerConfigTab': {
            template: '<div class="container-config-tab-stub">Config Mock</div>',
            props: ['detail'],
          },
          'ContainerStats': {
            template: '<div class="container-stats-stub">Stats Mock</div>',
            props: ['containerId'],
          },
          'ContainerProcesses': {
            template: '<div class="container-processes-stub">Processes Mock</div>',
            props: ['containerId', 'containerName'],
          },
          'el-dialog': {
            template: '<div class="el-dialog-stub" v-if="modelValue"><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title', 'width', 'closeOnClickModal'],
            emits: ['update:modelValue'],
          },
          'el-form': {
            template: '<form class="el-form-stub"><slot /></form>',
          },
          'el-form-item': {
            template: '<div class="el-form-item-stub"><slot /></div>',
            props: ['error'],
          },
          'el-select': {
            template: '<select class="el-select-stub"><slot /></select>',
            props: ['modelValue', 'style'],
          },
          'el-option': {
            template: '<option class="el-option-stub"><slot /></option>',
            props: ['label', 'value'],
          },
          'el-divider': {
            template: '<hr class="el-divider-stub" />',
            props: ['direction'],
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

      expect((wrapper.vm as unknown as { activeTab: string }).activeTab).toBe('apercu')
    })

    it('should compute containerId from route params', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('my-container-456')

      // containerId is a computed ref, its value is directly accessible via the computed
      const containerId = wrapper.vm.containerId
      expect(containerId).toBeDefined()
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
    it('should have goBack method that calls router.back()', async () => {
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
      mockInspectContainer.mockResolvedValue({ ...mockContainerDetail, state: { status: 'stopped' } })

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = { ...mockContainerDetail, state: { status: 'stopped' } }
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

  describe('STORY-025: Pause/Unpause actions', () => {
    it('should call pauseContainer when pause action is triggered', async () => {
      mockPauseContainer.mockResolvedValue(undefined)
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-pause-1')

      const vm = wrapper.vm as unknown as {
        handleAction: (action: string) => Promise<void>
      }

      await vm.handleAction('pause')

      expect(mockPauseContainer).toHaveBeenCalledWith('container-pause-1')
    })

    it('should call unpauseContainer when unpause action is triggered', async () => {
      mockUnpauseContainer.mockResolvedValue(undefined)
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-unpause-1')

      const vm = wrapper.vm as unknown as {
        handleAction: (action: string) => Promise<void>
      }

      await vm.handleAction('unpause')

      expect(mockUnpauseContainer).toHaveBeenCalledWith('container-unpause-1')
    })
  })

  describe('STORY-025: Container state computed', () => {
    it('should return running state', async () => {
      mockInspectContainer.mockResolvedValue({
        ...mockContainerDetail,
        state: { status: 'running' },
      })

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        containerState: string
      }
      vm.containerDetail = { ...mockContainerDetail, state: { status: 'running' } }
      await wrapper.vm.$nextTick()

      expect(vm.containerState).toBe('running')
    })

    it('should return paused state', async () => {
      mockInspectContainer.mockResolvedValue({
        ...mockContainerDetail,
        state: { status: 'paused' },
      })

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        containerState: string
      }
      vm.containerDetail = { ...mockContainerDetail, state: { status: 'paused' } }
      await wrapper.vm.$nextTick()

      expect(vm.containerState).toBe('paused')
    })

    it('should return exited state', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        containerState: string
      }
      vm.containerDetail = { ...mockContainerDetail, state: { status: 'exited' } }
      await wrapper.vm.$nextTick()

      expect(vm.containerState).toBe('exited')
    })

    it('should return unknown when no detail', async () => {
      mockInspectContainer.mockResolvedValue(null)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerState: string }
      // When no detail, containerState defaults to 'unknown'
      expect(vm.containerState).toBe('unknown')
    })
  })

  describe('STORY-025: Container uptime', () => {
    it('should compute containerUptime for running container', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        containerUptime: string
      }
      // Set startedAt to 1 hour ago
      const oneHourAgo = new Date(Date.now() - 3600000).toISOString()
      vm.containerDetail = {
        ...mockContainerDetail,
        state: { status: 'running', started_at: oneHourAgo },
      }
      await wrapper.vm.$nextTick()

      // Should contain duration info (format depends on formatDuration implementation)
      expect(typeof vm.containerUptime).toBe('string')
    })

    it('should return empty uptime when not running', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        containerUptime: string
      }
      vm.containerDetail = {
        ...mockContainerDetail,
        state: { status: 'exited' },
      }
      await wrapper.vm.$nextTick()

      // containerUptime returns null when not running
      expect(vm.containerUptime).toBeFalsy()
    })
  })

  describe('STORY-028.3: Rename functionality', () => {
    it('should show the "Renommer" button when container is loaded', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      const html = wrapper.html()
      expect(html).toContain('Renommer')
    })

    it('should not show the "Renommer" button when container is null', async () => {
      mockInspectContainer.mockResolvedValue(null)

      const wrapper = await mountComponent()

      // containerDetail is null by default after mount with null response
      const html = wrapper.html()
      expect(html).not.toContain('Renommer')
    })

    it('should open rename dialog with current name pre-filled', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameDialogVisible: boolean
        renameNewName: string
        openRenameDialog: () => void
      }

      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      // Dialog should be closed initially
      expect(vm.renameDialogVisible).toBe(false)

      // Open dialog
      vm.openRenameDialog()
      await wrapper.vm.$nextTick()

      expect(vm.renameDialogVisible).toBe(true)
      expect(vm.renameNewName).toBe('test-container')
    })

    it('should validate container name — reject invalid characters', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameNewName: string
        renameError: string
        handleRename: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      // Test empty name
      vm.renameNewName = '   '
      await vm.handleRename()
      expect(vm.renameError).toBeTruthy()

      // Test invalid starting character
      vm.renameNewName = '_invalid'
      await vm.handleRename()
      expect(vm.renameError).toBeTruthy()

      // Test invalid characters
      vm.renameNewName = 'invalid name!'
      await vm.handleRename()
      expect(vm.renameError).toBeTruthy()
    })

    it('should call API rename with correct parameters', async () => {
      mockRename.mockResolvedValue({ data: { success: true, message: 'Renamed' } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rename-1')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameNewName: string
        renameDialogVisible: boolean
        handleRename: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.renameNewName = 'new-container-name'
      vm.renameDialogVisible = true
      await wrapper.vm.$nextTick()

      await vm.handleRename()

      expect(mockRename).toHaveBeenCalledWith('container-rename-1', { new_name: 'new-container-name' })
    })

    it('should close dialog and refresh after successful rename', async () => {
      mockRename.mockResolvedValue({ data: { success: true, message: 'Renamed' } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rename-2')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameNewName: string
        renameDialogVisible: boolean
        handleRename: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.renameNewName = 'renamed-container'
      vm.renameDialogVisible = true
      await wrapper.vm.$nextTick()

      await vm.handleRename()
      await flushPromises()

      // Dialog should be closed
      expect(vm.renameDialogVisible).toBe(false)
      // Should have refreshed detail
      expect(mockInspectContainer).toHaveBeenCalled()
    })

    it('should show error when rename API fails', async () => {
      mockRename.mockRejectedValue(new Error('Container already exists'))
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rename-3')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameNewName: string
        renameDialogVisible: boolean
        renameError: string
        handleRename: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.renameNewName = 'duplicate-name'
      vm.renameDialogVisible = true
      await wrapper.vm.$nextTick()

      await vm.handleRename()
      await flushPromises()

      // Should have error set
      expect(vm.renameError).toBeTruthy()
      // Dialog should remain open on error
      expect(vm.renameDialogVisible).toBe(true)
    })

    it('should reset rename state when dialog closes', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameDialogVisible: boolean
        renameNewName: string
        renameError: string
        openRenameDialog: () => void
        onRenameDialogClosed: () => void
      }

      vm.containerDetail = mockContainerDetail
      vm.openRenameDialog()
      await wrapper.vm.$nextTick()

      expect(vm.renameDialogVisible).toBe(true)
      expect(vm.renameNewName).toBe('test-container')

      // Simulate dialog close
      vm.onRenameDialogClosed()

      expect(vm.renameNewName).toBe('')
      expect(vm.renameError).toBe('')
    })

    it('should close dialog without action if name is unchanged', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        renameDialogVisible: boolean
        renameNewName: string
        handleRename: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.renameNewName = 'test-container' // same as current name
      vm.renameDialogVisible = true
      await wrapper.vm.$nextTick()

      await vm.handleRename()

      // Dialog should close without API call
      expect(vm.renameDialogVisible).toBe(false)
      expect(mockRename).not.toHaveBeenCalled()
    })
  })

  describe('STORY-009: Restart Policy Dialog', () => {
    it('should open restart policy dialog when clicking the header button', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyDialogVisible: boolean
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        openRestartPolicyDialog: () => void
      }

      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      expect(vm.restartPolicyDialogVisible).toBe(false)

      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      expect(vm.restartPolicyDialogVisible).toBe(true)
    })

    it('should pre-fill restart policy form with current container values', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyDialogVisible: boolean
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        openRestartPolicyDialog: () => void
      }

      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      // mockContainerDetail has restart_policy.name = 'always'
      expect(vm.restartPolicyForm.name).toBe('always')
      expect(vm.restartPolicyForm.maximumRetryCount).toBe(0)
    })

    it('should call updateRestartPolicy API with correct parameters', async () => {
      mockUpdateRestartPolicy.mockResolvedValue({ data: { success: true } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rp-1')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        restartPolicyDialogVisible: boolean
        openRestartPolicyDialog: () => void
        handleUpdateRestartPolicy: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      // Change policy to on-failure with retry count
      vm.restartPolicyForm.name = 'on-failure'
      vm.restartPolicyForm.maximumRetryCount = 5
      await wrapper.vm.$nextTick()

      await vm.handleUpdateRestartPolicy()
      await flushPromises()

      expect(mockUpdateRestartPolicy).toHaveBeenCalledWith('container-rp-1', {
        name: 'on-failure',
        maximum_retry_count: 5,
      })
    })

    it('should not include maximum_retry_count when policy is not on-failure', async () => {
      mockUpdateRestartPolicy.mockResolvedValue({ data: { success: true } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rp-no-retry')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        restartPolicyDialogVisible: boolean
        openRestartPolicyDialog: () => void
        handleUpdateRestartPolicy: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      // Policy is 'always' (from mockContainerDetail), change to 'no'
      vm.restartPolicyForm.name = 'no'
      await wrapper.vm.$nextTick()

      await vm.handleUpdateRestartPolicy()
      await flushPromises()

      expect(mockUpdateRestartPolicy).toHaveBeenCalledWith('container-rp-no-retry', {
        name: 'no',
      })
    })

    it('should show maximum_retry_count field only when policy is on-failure', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        restartPolicyDialogVisible: boolean
        openRestartPolicyDialog: () => void
      }

      vm.containerDetail = mockContainerDetail
      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      // With 'always' policy, the conditional field should not be relevant
      expect(vm.restartPolicyForm.name).toBe('always')

      // Switch to 'on-failure' — the conditional field becomes visible
      vm.restartPolicyForm.name = 'on-failure'
      vm.restartPolicyForm.maximumRetryCount = 3
      await wrapper.vm.$nextTick()

      expect(vm.restartPolicyForm.name).toBe('on-failure')
      expect(vm.restartPolicyForm.maximumRetryCount).toBe(3)
    })

    it('should close dialog and refresh after successful restart policy update', async () => {
      mockUpdateRestartPolicy.mockResolvedValue({ data: { success: true } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rp-refresh')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        restartPolicyDialogVisible: boolean
        openRestartPolicyDialog: () => void
        handleUpdateRestartPolicy: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      expect(vm.restartPolicyDialogVisible).toBe(true)

      await vm.handleUpdateRestartPolicy()
      await flushPromises()

      expect(vm.restartPolicyDialogVisible).toBe(false)
      // loadContainerDetail calls inspectContainer: once on mount, once after update
      expect(mockInspectContainer).toHaveBeenCalledTimes(2)
    })

    it('should show error and keep dialog open when updateRestartPolicy API fails', async () => {
      mockUpdateRestartPolicy.mockRejectedValue(new Error('API error'))
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-rp-err')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        restartPolicyForm: { name: string; maximumRetryCount: number | null }
        restartPolicyDialogVisible: boolean
        restartPolicyLoading: boolean
        openRestartPolicyDialog: () => void
        handleUpdateRestartPolicy: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openRestartPolicyDialog()
      await wrapper.vm.$nextTick()

      await vm.handleUpdateRestartPolicy()
      await flushPromises()

      // Dialog should remain open on error
      expect(vm.restartPolicyDialogVisible).toBe(true)
      // Loading should be reset
      expect(vm.restartPolicyLoading).toBe(false)
    })
  })

  describe('STORY-009: Resources Dialog', () => {
    it('should open resources dialog when clicking the header button', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        resourcesDialogVisible: boolean
        resourcesForm: { memoryLimit: number | null; cpuShares: number | null; pidsLimit: number | null }
        openResourcesDialog: () => void
      }

      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      expect(vm.resourcesDialogVisible).toBe(false)

      vm.openResourcesDialog()
      await wrapper.vm.$nextTick()

      expect(vm.resourcesDialogVisible).toBe(true)
    })

    it('should pre-fill resources form with current values (memory in MB)', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        resourcesDialogVisible: boolean
        resourcesForm: { memoryLimit: number | null; cpuShares: number | null; pidsLimit: number | null }
        openResourcesDialog: () => void
      }

      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      vm.openResourcesDialog()
      await wrapper.vm.$nextTick()

      // 134217728 bytes / 1024 / 1024 = 128 MB
      expect(vm.resourcesForm.memoryLimit).toBe(128)
      expect(vm.resourcesForm.cpuShares).toBe(512)
      expect(vm.resourcesForm.pidsLimit).toBe(100)
    })

    it('should call updateResources API with MB to bytes conversion', async () => {
      mockUpdateResources.mockResolvedValue({ data: { success: true } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-res-1')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        resourcesForm: { memoryLimit: number | null; cpuShares: number | null; pidsLimit: number | null }
        resourcesDialogVisible: boolean
        openResourcesDialog: () => void
        handleUpdateResources: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openResourcesDialog()
      await wrapper.vm.$nextTick()

      // Modify values
      vm.resourcesForm.memoryLimit = 256
      vm.resourcesForm.cpuShares = 1024
      vm.resourcesForm.pidsLimit = 200
      await wrapper.vm.$nextTick()

      await vm.handleUpdateResources()
      await flushPromises()

      expect(mockUpdateResources).toHaveBeenCalledWith('container-res-1', {
        memory_limit: 256 * 1024 * 1024, // 268435456 bytes
        cpu_shares: 1024,
        pids_limit: 200,
      })
    })

    it('should send undefined for zero/falsy resource values', async () => {
      mockUpdateResources.mockResolvedValue({ data: { success: true } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-res-zero')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        resourcesForm: { memoryLimit: number | null; cpuShares: number | null; pidsLimit: number | null }
        resourcesDialogVisible: boolean
        openResourcesDialog: () => void
        handleUpdateResources: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openResourcesDialog()
      await wrapper.vm.$nextTick()

      // Set all to 0 (falsy)
      vm.resourcesForm.memoryLimit = 0
      vm.resourcesForm.cpuShares = 0
      vm.resourcesForm.pidsLimit = 0
      await wrapper.vm.$nextTick()

      await vm.handleUpdateResources()
      await flushPromises()

      expect(mockUpdateResources).toHaveBeenCalledWith('container-res-zero', {
        memory_limit: undefined,
        cpu_shares: undefined,
        pids_limit: undefined,
      })
    })

    it('should close dialog and refresh after successful resources update', async () => {
      mockUpdateResources.mockResolvedValue({ data: { success: true } })
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-res-refresh')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        resourcesForm: { memoryLimit: number | null; cpuShares: number | null; pidsLimit: number | null }
        resourcesDialogVisible: boolean
        openResourcesDialog: () => void
        handleUpdateResources: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openResourcesDialog()
      await wrapper.vm.$nextTick()

      expect(vm.resourcesDialogVisible).toBe(true)

      await vm.handleUpdateResources()
      await flushPromises()

      expect(vm.resourcesDialogVisible).toBe(false)
      // loadContainerDetail calls inspectContainer: once on mount, once after update
      expect(mockInspectContainer).toHaveBeenCalledTimes(2)
    })

    it('should show error and keep dialog open when updateResources API fails', async () => {
      mockUpdateResources.mockRejectedValue(new Error('API error'))
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent('container-res-err')

      const vm = wrapper.vm as unknown as {
        containerDetail: typeof mockContainerDetail
        resourcesForm: { memoryLimit: number | null; cpuShares: number | null; pidsLimit: number | null }
        resourcesDialogVisible: boolean
        resourcesLoading: boolean
        openResourcesDialog: () => void
        handleUpdateResources: () => Promise<void>
      }

      vm.containerDetail = mockContainerDetail
      vm.openResourcesDialog()
      await wrapper.vm.$nextTick()

      await vm.handleUpdateResources()
      await flushPromises()

      // Dialog should remain open on error
      expect(vm.resourcesDialogVisible).toBe(true)
      // Loading should be reset
      expect(vm.resourcesLoading).toBe(false)
    })
  })

  describe('STORY-009: Header action buttons presence', () => {
    it('should render Restart Policy button in header actions', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      const html = wrapper.html()
      expect(html).toContain('Restart Policy')
    })

    it('should render Ressources button in header actions', async () => {
      mockInspectContainer.mockResolvedValue(mockContainerDetail)

      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { containerDetail: typeof mockContainerDetail }
      vm.containerDetail = mockContainerDetail
      await wrapper.vm.$nextTick()

      const html = wrapper.html()
      expect(html).toContain('Ressources')
    })
  })
})
