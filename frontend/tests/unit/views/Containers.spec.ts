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
    },
  }
})

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRouter: () => ({
      push: mockPush,
    }),
    useRoute: () => ({
      params: {},
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
          },
          'el-table-column': {
            template: '<td><slot :row="{}" /></td>',
            props: ['prop', 'label'],
          },
          'el-button': {
            template: '<button><slot /></button>',
            props: ['loading', 'type'],
          },
          'el-badge': {
            template: '<div class="el-badge"><slot /></div>',
            props: ['value', 'type'],
          },
          'el-tag': {
            template: '<span class="el-tag"><slot /></span>',
            props: ['type', 'size'],
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
            template: '<input type="text" />',
            props: ['modelValue', 'type', 'rows', 'readonly'],
          },
          'el-input-number': {
            template: '<input type="number" />',
            props: ['modelValue', 'min', 'max', 'size'],
          },
          'el-checkbox': {
            template: '<input type="checkbox" />',
            props: ['modelValue'],
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
      expect(wrapper.find('.title').text()).toBe('Containers')
    })

    it('should display subtitle', () => {
      const wrapper = mountContainers()
      expect(wrapper.find('.subtitle').text()).toBe('Gestion des containers Docker')
    })
  })

  describe('Store Integration', () => {
    it('should call fetchContainers on mount', async () => {
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

      expect(store.containers).toHaveLength(2)
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

  describe('Logs Drawer', () => {
    it('should open logs drawer when logs action is triggered', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'getContainerLogs').mockResolvedValue('log content')

      const wrapper = mountContainers()
      await wrapper.vm.showLogs(mockContainers[0])

      expect(wrapper.vm.logsDrawerVisible).toBe(true)
      expect(wrapper.vm.selectedContainer).toEqual(mockContainers[0])
    })

    it('should fetch logs when showing logs drawer', async () => {
      const store = useContainersStore()
      vi.spyOn(store, 'fetchContainers').mockResolvedValue()
      vi.spyOn(store, 'getContainerLogs').mockResolvedValue('log line 1\nlog line 2')

      const wrapper = mountContainers()
      await wrapper.vm.showLogs(mockContainers[0])

      expect(store.getContainerLogs).toHaveBeenCalledWith('abc123', 100)
      expect(wrapper.vm.logsContent).toBe('log line 1\nlog line 2')
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
  })
})
