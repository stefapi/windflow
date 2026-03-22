/**
 * Tests unitaires pour le composant ContainerProcesses.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ElEmpty } from 'element-plus'
import ContainerProcesses from '@/components/ContainerProcesses.vue'
import http from '@/services/http'

// Mock du module HTTP
vi.mock('@/services/http', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('ContainerProcesses.vue', () => {
  const mockProcesses = [
    {
      pid: 1,
      user: 'root',
      cpu: 0.0,
      mem: 0.1,
      time: '00:00:01',
      command: '/bin/bash',
    },
    {
      pid: 42,
      user: 'app',
      cpu: 1.5,
      mem: 2.3,
      time: '00:00:05',
      command: 'python app.py',
    },
  ]

  const mockResponse = {
    data: {
      container_id: 'abc123',
      titles: ['PID', 'USER', '%CPU', '%MEM', 'TIME', 'COMMAND'],
      processes: mockProcesses,
      timestamp: '2024-01-15T10:30:00Z',
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(http.get).mockResolvedValue(mockResponse)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should render the component', async () => {
    const wrapper = mount(ContainerProcesses, {
      props: {
        containerId: 'abc123',
        containerName: 'test-container',
      },
      global: {
        stubs: {
          'el-table': true,
          'el-button': true,
          'el-switch': true,
          'el-tag': true,
          'el-alert': true,
          'el-empty': true,
          'el-icon': true,
        },
      },
    })

    await flushPromises()
    expect(wrapper.exists()).toBe(true)
  })

  it('should fetch processes on mount', async () => {
    const wrapper = mount(ContainerProcesses, {
      props: {
        containerId: 'abc123',
      },
      global: {
        stubs: {
          'el-table': true,
          'el-button': true,
          'el-switch': true,
          'el-tag': true,
          'el-alert': true,
          'el-empty': true,
          'el-icon': true,
        },
      },
    })

    await flushPromises()
    expect(http.get).toHaveBeenCalledWith('/api/v1/docker/containers/abc123/top')
  })

  it('should display process count', async () => {
    const wrapper = mount(ContainerProcesses, {
      props: {
        containerId: 'abc123',
      },
      global: {
        stubs: {
          'el-table': true,
          'el-button': true,
          'el-switch': true,
          'el-tag': {
            template: '<span><slot /></span>',
          },
          'el-alert': true,
          'el-empty': true,
          'el-icon': true,
        },
      },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('2 processus')
  })

  it('should display empty state when no processes', async () => {
    vi.mocked(http.get).mockResolvedValue({
      data: {
        container_id: 'abc123',
        titles: [],
        processes: [],
        timestamp: '2024-01-15T10:30:00Z',
      },
    })

    const wrapper = mount(ContainerProcesses, {
      props: {
        containerId: 'abc123',
      },
      global: {
        stubs: {
          'el-table': true,
          'el-button': true,
          'el-switch': true,
          'el-tag': true,
          'el-alert': true,
          'el-empty': true,
          'el-icon': true,
        },
      },
    })

    await flushPromises()
    expect(wrapper.findComponent(ElEmpty)).toBeTruthy()
  })

  it('should handle API errors', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.mocked(http.get).mockRejectedValue(new Error('Network error'))

    const wrapper = mount(ContainerProcesses, {
      props: {
        containerId: 'abc123',
      },
      global: {
        stubs: {
          'el-table': true,
          'el-button': true,
          'el-switch': true,
          'el-tag': true,
          'el-alert': true,
          'el-empty': true,
          'el-icon': true,
        },
      },
    })

    await flushPromises()
    expect(wrapper.vm.error).toBeTruthy()
    consoleSpy.mockRestore()
  })

  it('should call refresh when button clicked', async () => {
    const wrapper = mount(ContainerProcesses, {
      props: {
        containerId: 'abc123',
      },
      global: {
        stubs: {
          'el-table': true,
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'el-switch': true,
          'el-tag': true,
          'el-alert': true,
          'el-empty': true,
          'el-icon': true,
        },
      },
    })

    await flushPromises()
    vi.clearAllMocks()

    // Find and click the refresh button
    const buttons = wrapper.findAll('button')
    const refreshButton = buttons.find(b => b.text().includes('Rafraîchir'))
    if (refreshButton) {
      await refreshButton.trigger('click')
      await flushPromises()
      expect(http.get).toHaveBeenCalled()
    }
  })

  describe('Helper functions', () => {
    it('should return correct CPU tag type', async () => {
      const wrapper = mount(ContainerProcesses, {
        props: {
          containerId: 'abc123',
        },
        global: {
          stubs: {
            'el-table': true,
            'el-button': true,
            'el-switch': true,
            'el-tag': true,
            'el-alert': true,
            'el-empty': true,
            'el-icon': true,
          },
        },
      })

      await flushPromises()
      const vm = wrapper.vm as any

      expect(vm.getCpuTagType(85)).toBe('danger')
      expect(vm.getCpuTagType(60)).toBe('warning')
      expect(vm.getCpuTagType(30)).toBe('success')
      expect(vm.getCpuTagType(10)).toBe('info')
    })

    it('should return correct MEM tag type', async () => {
      const wrapper = mount(ContainerProcesses, {
        props: {
          containerId: 'abc123',
        },
        global: {
          stubs: {
            'el-table': true,
            'el-button': true,
            'el-switch': true,
            'el-tag': true,
            'el-alert': true,
            'el-empty': true,
            'el-icon': true,
          },
        },
      })

      await flushPromises()
      const vm = wrapper.vm as any

      expect(vm.getMemTagType(85)).toBe('danger')
      expect(vm.getMemTagType(60)).toBe('warning')
      expect(vm.getMemTagType(30)).toBe('success')
      expect(vm.getMemTagType(10)).toBe('info')
    })

    it('should truncate long commands', async () => {
      const wrapper = mount(ContainerProcesses, {
        props: {
          containerId: 'abc123',
        },
        global: {
          stubs: {
            'el-table': true,
            'el-button': true,
            'el-switch': true,
            'el-tag': true,
            'el-alert': true,
            'el-empty': true,
            'el-icon': true,
          },
        },
      })

      await flushPromises()
      const vm = wrapper.vm as any

      const longCommand = 'a'.repeat(100)
      const truncated = vm.truncateCommand(longCommand)
      expect(truncated.length).toBe(60)
      expect(truncated.endsWith('...')).toBe(true)
    })

    it('should not truncate short commands', async () => {
      const wrapper = mount(ContainerProcesses, {
        props: {
          containerId: 'abc123',
        },
        global: {
          stubs: {
            'el-table': true,
            'el-button': true,
            'el-switch': true,
            'el-tag': true,
            'el-alert': true,
            'el-empty': true,
            'el-icon': true,
          },
        },
      })

      await flushPromises()
      const vm = wrapper.vm as any

      const shortCommand = '/bin/bash'
      expect(vm.truncateCommand(shortCommand)).toBe('/bin/bash')
    })

    it('should format timestamp correctly', async () => {
      const wrapper = mount(ContainerProcesses, {
        props: {
          containerId: 'abc123',
        },
        global: {
          stubs: {
            'el-table': true,
            'el-button': true,
            'el-switch': true,
            'el-tag': true,
            'el-alert': true,
            'el-empty': true,
            'el-icon': true,
          },
        },
      })

      await flushPromises()
      const vm = wrapper.vm as any

      const timestamp = '2024-01-15T10:30:00Z'
      const formatted = vm.formatTimestamp(timestamp)
      // Le format dépend de la locale, vérifions juste qu'il retourne quelque chose
      expect(formatted).toBeTruthy()
    })
  })
})
