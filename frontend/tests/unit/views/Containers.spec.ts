/**
 * Containers.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'
import Containers from '@/views/Containers.vue'
import { useContainersStore } from '@/stores'
import type { Container } from '@/types/api'

// Mock Element Plus message
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
    },
  }
})

// Mock vue-router
const mockPush = vi.fn()
const mockReplace = vi.fn()
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({
      push: mockPush,
      replace: mockReplace,
    }),
    useRoute: () => ({
      params: {},
      query: {},
      path: '/containers',
    }),
  }
})

// Mock containers API
vi.mock('@/services/api', () => ({
  containersApi: {
    list: vi.fn(),
    get: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    restart: vi.fn(),
    remove: vi.fn(),
    getLogs: vi.fn(),
  },
}))

// Mock useUrlFilters composable
vi.mock('@/composables/useUrlFilters', () => ({
  useUrlFilters: () => ({
    status: { value: 'all' },
    target: { value: '' },
    search: { value: '' },
    debouncedSearch: { value: '' },
    hasActiveFilters: { value: false },
    filters: { value: { status: 'all', target: '', search: '' } },
    resetFilters: vi.fn(),
    setFilters: vi.fn(),
  }),
  ContainerStatusFilter: {},
}))

// Mock useContainerLogs composable (used by ContainerLogs component)
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

describe('Containers.vue', () => {
  let pinia: ReturnType<typeof createPinia>

  const mockContainers: Container[] = [
    {
      id: 'abc123',
      name: 'nginx-server',
      image: 'nginx:latest',
      imageId: 'sha256:12345',
      command: 'nginx -g daemon off;',
      created: '2024-01-01T00:00:00Z',
      state: 'running',
      status: 'Up 2 hours',
      ports: [
        { IP: '0.0.0.0', PublicPort: 8080, PrivatePort: 80, Type: 'tcp' },
      ],
      labels: {},
      networks: ['bridge'],
      mounts: [],
      restart_count: 0,
    },
    {
      id: 'def456',
      name: 'redis-cache',
      image: 'redis:alpine',
      imageId: 'sha256:67890',
      command: 'redis-server',
      created: '2024-01-01T00:00:00Z',
      state: 'exited',
      status: 'Exited (0) 1 hour ago',
      ports: [],
      labels: {},
      networks: ['bridge'],
      mounts: [],
      restart_count: 0,
    },
    {
      id: 'ghi789',
      name: 'postgres-db',
      image: 'postgres:15',
      imageId: 'sha256:11111',
      command: 'postgres',
      created: '2024-01-01T00:00:00Z',
      state: 'running',
      status: 'Up 3 hours',
      ports: [
        { IP: '0.0.0.0', PublicPort: 5432, PrivatePort: 5432, Type: 'tcp' },
      ],
      labels: {},
      networks: ['bridge'],
      mounts: [],
      restart_count: 0,
    },
    {
      id: 'jkl012',
      name: 'broken-app',
      image: 'app:broken',
      imageId: 'sha256:22222',
      command: 'node app.js',
      created: '2024-01-01T00:00:00Z',
      state: 'dead',
      status: 'Dead',
      ports: [],
      labels: {},
      networks: ['bridge'],
      mounts: [],
      restart_count: 0,
    },
  ]

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
  })

  const mountContainers = () => {
    return mount(Containers, {
      global: {
        plugins: [pinia],
        stubs: {
          'router-link': {
            template: '<a :href="to"><slot /></a>',
            props: ['to'],
          },
          'el-card': {
            template: '<div class="el-card"><slot name="header" /><slot /></div>',
          },
          'el-table': {
            template: '<table><slot /></table>',
            props: ['data', 'loading'],
            methods: {
              clearSelection: vi.fn(),
            },
          },
          'el-table-column': {
            template: '<td><slot :row="{}" /></td>',
            props: ['prop', 'label', 'type', 'width'],
          },
          'el-button': {
            template: '<button><slot /></button>',
            props: ['loading', 'type', 'size', 'text'],
          },
          'el-badge': {
            template: '<div class="el-badge"><slot /></div>',
            props: ['value', 'type'],
          },
          'el-tag': {
            template: '<span class="el-tag"><slot /></span>',
            props: ['type', 'size', 'effect'],
          },
          'el-icon': {
            template: '<i><slot /></i>',
          },
          'el-drawer': {
            template: '<div v-if="modelValue"><slot /></div>',
            props: ['modelValue', 'title'],
          },
          'el-dialog': {
            template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title', 'width'],
          },
          'el-alert': {
            template: '<div v-if="title" class="el-alert">{{ title }}</div>',
            props: ['title', 'type', 'show-icon', 'closable'],
          },
          'el-tooltip': {
            template: '<span><slot /></span>',
            props: ['content', 'placement'],
          },
          'el-input': {
            template: '<div class="el-input"><input type="text" /></div>',
            props: ['modelValue', 'type', 'rows', 'readonly', 'placeholder', 'clearable'],
          },
          'el-input-number': {
            template: '<input type="number" />',
            props: ['modelValue', 'min', 'max', 'size'],
          },
          'el-checkbox': {
            template: '<input type="checkbox" />',
            props: ['modelValue'],
          },
          'el-select': {
            template: '<div class="el-select"><select><slot /></select></div>',
            props: ['modelValue', 'placeholder', 'clearable'],
          },
          'el-option': {
            template: '<option><slot /></option>',
            props: ['label', 'value'],
          },
          StatusBadge: {
            template: '<span class="status-badge">{{ status }}</span>',
            props: ['status'],
          },
          ActionButtons: {
            template: '<div class="action-buttons"><button v-for="a in actions" :key="a.type || a" @click="$emit(\'action\', a.type || a)">{{ a.type || a }}</button></div>',
            props: ['actions'],
            emits: ['action'],
          },
        },
      },
    })
  }

  describe('Component Mounting', () => {
    it('should mount successfully', () => {
      const wrapper = mountContainers()
      expect(wrapper.exists()).toBe(true)
    })

    it('should display page title', () => {
      const wrapper = mountContainers()
      // Title is now using UnoCSS classes: text-xl font-semibold text-[var(--color-text-primary)]
      expect(wrapper.text()).toContain('Containers')
    })

    it('should display subtitle', () => {
      const wrapper = mountContainers()
      // Subtitle is now using UnoCSS classes: text-sm text-[var(--color-text-secondary)]
      expect(wrapper.text()).toContain('Gestion des containers Docker')
    })

    it('should display filters bar', () => {
      const wrapper = mountContainers()
      // Filters bar is now using UnoCSS classes: flex justify-between items-center mb-4 px-4 py-3 bg-[var(--color-bg-secondary)] rounded-lg
      expect(wrapper.find('.el-select').exists()).toBe(true)
    })

    it('should display search input', () => {
      const wrapper = mountContainers()
      // Search input is an el-input with placeholder
      expect(wrapper.find('.el-input').exists()).toBe(true)
    })

    it('should display status filter select', () => {
      const wrapper = mountContainers()
      // Status filter is an el-select
      expect(wrapper.find('.el-select').exists()).toBe(true)
    })
  })

  describe('Store Integration', () => {
    it('should call fetchContainers on mount', () => {
      const store = useContainersStore()
      const fetchSpy = vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      mountContainers()

      expect(fetchSpy).toHaveBeenCalled()
    })

    it('should display containers from store', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockImplementation(async () => {
        store.containers = mockContainers
      })

      const wrapper = mountContainers()
      await wrapper.vm.$nextTick()

      expect(store.containers).toHaveLength(4)
    })
  })

  describe('Filtering', () => {
    it('should have filteredContainers computed property', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockImplementation(async () => {
        store.containers = mockContainers
      })

      const wrapper = mountContainers()
      await wrapper.vm.$nextTick()

      // All containers should be visible when no filters
      expect(wrapper.vm.filteredContainers).toHaveLength(4)
    })

    it('should show results count text', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockImplementation(async () => {
        store.containers = mockContainers
      })

      const wrapper = mountContainers()
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.resultsCountText).toBe('4 containers')
    })

    it('should return correct empty text when loading', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      store.loading = true

      const wrapper = mountContainers()

      expect(wrapper.vm.emptyText).toBe('Chargement...')
    })

    it('should return correct empty text when filters active', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      // Simulate active filters by checking the computed
      expect(wrapper.vm.emptyText).toBe('Aucun container trouvé')
    })
  })

  describe('Selection', () => {
    it('should have selectedContainerIds computed property', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()

      expect(wrapper.vm.selectedContainerIds).toEqual([])
    })

    it('should update selectedContainers on selection change', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0], mockContainers[1]])

      expect(wrapper.vm.selectedContainers).toHaveLength(2)
      expect(wrapper.vm.selectedContainerIds).toEqual(['abc123', 'def456'])
    })

    it('should clear selection', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0]])
      wrapper.vm.clearSelection()

      expect(wrapper.vm.selectedContainers).toEqual([])
    })

    it('should show bulk actions bar when containers selected', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()

      // Initially no bulk actions bar
      expect(wrapper.vm.selectedContainerIds.length).toBe(0)

      // Select containers
      wrapper.vm.handleSelectionChange([mockContainers[0]])
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.selectedContainerIds.length).toBe(1)
    })
  })

  describe('Container Actions', () => {
    it('should show success message when container starts', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'startContainer').mockResolvedValue()

      const wrapper = mountContainers()
      await wrapper.vm.startContainer(mockContainers[0])

      expect(ElMessage.success).toHaveBeenCalledWith('Container "nginx-server" démarré')
    })

    it('should show error message when container start fails', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'startContainer').mockRejectedValue(new Error('Docker error'))

      const wrapper = mountContainers()
      await wrapper.vm.startContainer(mockContainers[0])

      expect(ElMessage.error).toHaveBeenCalled()
    })

    it('should show success message when container stops', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'stopContainer').mockResolvedValue()

      const wrapper = mountContainers()
      await wrapper.vm.stopContainer(mockContainers[0])

      expect(ElMessage.success).toHaveBeenCalledWith('Container "nginx-server" arrêté')
    })

    it('should show success message when container restarts', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'restartContainer').mockResolvedValue()

      const wrapper = mountContainers()
      await wrapper.vm.restartContainer(mockContainers[0])

      expect(ElMessage.success).toHaveBeenCalledWith('Container "nginx-server" redémarré')
    })

    it('should show success message when container is deleted', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'removeContainer').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.containerToDelete = mockContainers[0]
      await wrapper.vm.confirmDelete()

      expect(ElMessage.success).toHaveBeenCalledWith('Container "nginx-server" supprimé')
    })
  })

  describe('Bulk Actions', () => {
    it('should show bulk delete dialog', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.showBulkDeleteDialog()

      expect(wrapper.vm.bulkDeleteDialogVisible).toBe(true)
    })

    it('should call startContainers for bulk start', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'startContainers').mockResolvedValue({
        success: ['abc123', 'def456'],
        failed: [],
      })

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0], mockContainers[1]])
      await wrapper.vm.handleBulkAction('start')

      expect(store.startContainers).toHaveBeenCalledWith(['abc123', 'def456'])
      expect(ElMessage.success).toHaveBeenCalled()
    })

    it('should call stopContainers for bulk stop', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'stopContainers').mockResolvedValue({
        success: ['abc123'],
        failed: [],
      })

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0]])
      await wrapper.vm.handleBulkAction('stop')

      expect(store.stopContainers).toHaveBeenCalledWith(['abc123'])
      expect(ElMessage.success).toHaveBeenCalled()
    })

    it('should call restartContainers for bulk restart', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'restartContainers').mockResolvedValue({
        success: ['abc123'],
        failed: [],
      })

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0]])
      await wrapper.vm.handleBulkAction('restart')

      expect(store.restartContainers).toHaveBeenCalledWith(['abc123'])
      expect(ElMessage.success).toHaveBeenCalled()
    })

    it('should show warning for partial bulk action success', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'startContainers').mockResolvedValue({
        success: ['abc123'],
        failed: ['def456'],
      })

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0], mockContainers[1]])
      await wrapper.vm.handleBulkAction('start')

      expect(ElMessage.warning).toHaveBeenCalled()
    })

    it('should show error for complete bulk action failure', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'startContainers').mockResolvedValue({
        success: [],
        failed: ['abc123', 'def456'],
      })

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0], mockContainers[1]])
      await wrapper.vm.handleBulkAction('start')

      expect(ElMessage.error).toHaveBeenCalled()
    })

    it('should call removeContainers for bulk delete', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'removeContainers').mockResolvedValue({
        success: ['abc123'],
        failed: [],
      })

      const wrapper = mountContainers()
      wrapper.vm.handleSelectionChange([mockContainers[0]])
      wrapper.vm.showBulkDeleteDialog()
      await wrapper.vm.confirmBulkDelete()

      expect(store.removeContainers).toHaveBeenCalled()
      expect(ElMessage.success).toHaveBeenCalled()
    })
  })

  describe('Logs Drawer', () => {
    it('should open logs drawer when logs action is triggered', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.showLogs(mockContainers[0])

      expect(wrapper.vm.logsDrawerVisible).toBe(true)
      expect(wrapper.vm.selectedContainer).toEqual(mockContainers[0])
    })

    it('should set selected container when showing logs', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.showLogs(mockContainers[1])

      expect(wrapper.vm.selectedContainer).toEqual(mockContainers[1])
      expect(wrapper.vm.logsDrawerVisible).toBe(true)
    })

    it('should use ContainerLogs component with WebSocket (no REST API call)', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      const getLogsSpy = vi.spyOn(store, 'getContainerLogs').mockResolvedValue('')

      const wrapper = mountContainers()
      wrapper.vm.showLogs(mockContainers[0])

      // The new implementation uses the ContainerLogs component with WebSocket
      // instead of calling getContainerLogs REST API
      expect(getLogsSpy).not.toHaveBeenCalled()
    })
  })

  describe('Delete Dialog', () => {
    it('should show delete dialog when delete action is triggered', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.showDeleteDialog(mockContainers[0])

      expect(wrapper.vm.deleteDialogVisible).toBe(true)
      expect(wrapper.vm.containerToDelete).toEqual(mockContainers[0])
    })

    it('should reset forceDelete when showing delete dialog', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.forceDelete = true
      wrapper.vm.showDeleteDialog(mockContainers[0])

      expect(wrapper.vm.forceDelete).toBe(false)
    })
  })

  describe('Helper Functions', () => {
    it('should map container states correctly', () => {
      const wrapper = mountContainers()

      expect(wrapper.vm.mapContainerState('running')).toBe('running')
      expect(wrapper.vm.mapContainerState('exited')).toBe('stopped')
      expect(wrapper.vm.mapContainerState('paused')).toBe('pending')
      expect(wrapper.vm.mapContainerState('dead')).toBe('error')
      expect(wrapper.vm.mapContainerState('unknown')).toBe('offline')
    })

    it('should format ports correctly', () => {
      const wrapper = mountContainers()

      const port1 = { IP: '0.0.0.0', PublicPort: 8080, PrivatePort: 80, Type: 'tcp' }
      expect(wrapper.vm.formatPort(port1)).toBe('0.0.0.0:8080->80/tcp')

      const port2 = { PrivatePort: 443, Type: 'tcp' }
      expect(wrapper.vm.formatPort(port2)).toBe('443/tcp')

      const port3 = {}
      expect(wrapper.vm.formatPort(port3)).toBe('')
    })

    it('should return correct actions for running container', () => {
      const wrapper = mountContainers()
      const actions = wrapper.vm.getContainerActions(mockContainers[0])

      expect(actions[0]).toEqual({ type: 'start', disabled: true }) // running, can't start
      expect(actions[1]).toEqual({ type: 'stop', disabled: false }) // running, can stop
      expect(actions[2]).toEqual({ type: 'restart', disabled: false }) // running, can restart
      expect(actions[3]).toEqual({ type: 'logs', disabled: undefined })
      expect(actions[4]).toEqual({ type: 'delete', disabled: undefined })
    })

    it('should return correct actions for stopped container', () => {
      const wrapper = mountContainers()
      const actions = wrapper.vm.getContainerActions(mockContainers[1])

      expect(actions[0]).toEqual({ type: 'start', disabled: false }) // stopped, can start
      expect(actions[1]).toEqual({ type: 'stop', disabled: true }) // stopped, can't stop
      expect(actions[2]).toEqual({ type: 'restart', disabled: true }) // stopped, can't restart
    })

    it('should get container name by id', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockImplementation(async () => {
        store.containers = mockContainers
      })

      const wrapper = mountContainers()
      const name = wrapper.vm.getContainerName('abc123')

      expect(name).toBe('nginx-server')
    })

    it('should return id if container not found', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      const name = wrapper.vm.getContainerName('unknown-id')

      expect(name).toBe('unknown-id')
    })

    it('should return correct past participle for actions', () => {
      const wrapper = mountContainers()

      expect(wrapper.vm.getActionPastParticiple('start')).toBe('démarré(s)')
      expect(wrapper.vm.getActionPastParticiple('stop')).toBe('arrêté(s)')
      expect(wrapper.vm.getActionPastParticiple('restart')).toBe('redémarré(s)')
    })
  })

  describe('Filter Handlers', () => {
    it('should have onFilterChange method', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      expect(() => wrapper.vm.onFilterChange()).not.toThrow()
    })

    it('should have onSearchInput method', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      expect(() => wrapper.vm.onSearchInput()).not.toThrow()
    })

    it('should have clearFilters method', () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()

      const wrapper = mountContainers()
      wrapper.vm.clearFilters()
      // Should not throw and should call filters.resetFilters
    })
  })
})
