/**
 * ContainerLogs.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import ContainerLogs from '@/components/ContainerLogs.vue'

// Mock the composable
const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockClearLogs = vi.fn()
const mockDownloadLogs = vi.fn()

vi.mock('@/composables/useContainerLogs', () => ({
  useContainerLogs: () => ({
    logs: { value: '' },
    status: { value: 'disconnected' },
    error: { value: null },
    isStreaming: { value: false },
    connect: mockConnect,
    disconnect: mockDisconnect,
    clearLogs: mockClearLogs,
    downloadLogs: mockDownloadLogs,
  }),
}))

// Mock auth store
vi.mock('@/stores', () => ({
  useAuthStore: () => ({
    token: 'mock-jwt-token',
  }),
}))

describe('ContainerLogs.vue', () => {
  let router: ReturnType<typeof createRouter>

  const mockContainerId = 'test-container-123'

  beforeEach(() => {
    vi.clearAllMocks()

    // Create router
    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'Home', component: { template: '<div>Home</div>' } },
        { path: '/containers/:id', name: 'ContainerDetail', component: { template: '<div>ContainerDetail</div>' } },
      ],
    })

    // Create pinia
    const pinia = createPinia()
    setActivePinia(pinia)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountComponent = async (containerId = mockContainerId, props = {}) => {
    await router.push(`/containers/${containerId}`)
    await router.isReady()

    const wrapper = mount(ContainerLogs, {
      props: {
        containerId,
        containerName: 'test-container',
        ...props,
      },
      global: {
        plugins: [router, ElementPlus, createPinia()],
        stubs: {
          'el-tag': {
            template: '<span class="el-tag-stub"><slot /></span>',
            props: ['type', 'size'],
          },
          'el-select': {
            template: '<select class="el-select-stub"><slot /></select>',
            props: ['modelValue', 'size', 'placeholder', 'clearable'],
          },
          'el-option': {
            template: '<option class="el-option-stub"><slot /></option>',
            props: ['label', 'value'],
          },
          'el-input-number': {
            template: '<input type="number" class="el-input-number-stub" />',
            props: ['modelValue', 'min', 'max', 'size'],
          },
          'el-button': {
            template: '<button class="el-button-stub"><slot /></button>',
            props: ['size', 'type', 'circle'],
          },
          'el-button-group': {
            template: '<div class="el-button-group-stub"><slot /></div>',
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
        },
      },
    })

    await flushPromises()
    return wrapper
  }

  describe('Component mounting', () => {
    it('should mount successfully', async () => {
      const wrapper = await mountComponent()

      expect(wrapper.exists()).toBe(true)
    })

    it('should render logs container', async () => {
      const wrapper = await mountComponent()

      // Component should render with logs container class
      expect(wrapper.find('.container-logs').exists()).toBe(true)
      expect(wrapper.find('.logs-container').exists()).toBe(true)
    })

    it('should display connection status', async () => {
      const wrapper = await mountComponent()

      // Component should show status tag
      expect(wrapper.find('.el-tag-stub').exists()).toBe(true)
    })
  })

  describe('Actions', () => {
    it('should call downloadLogs when handleDownload is called', async () => {
      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        handleDownload: () => void
      }

      vm.handleDownload()

      expect(mockDownloadLogs).toHaveBeenCalled()
    })

    it('should call clearLogs when handleClear is called', async () => {
      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        handleClear: () => void
      }

      vm.handleClear()

      expect(mockClearLogs).toHaveBeenCalled()
    })

    it('should toggle auto-scroll', async () => {
      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        autoScroll: boolean
        toggleAutoScroll: () => void
      }

      const initialValue = vm.autoScroll
      vm.toggleAutoScroll()

      expect(vm.autoScroll).toBe(!initialValue)
    })
  })

  describe('Auto-scroll functionality', () => {
    it('should have auto-scroll enabled by default', async () => {
      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as { autoScroll: boolean }
      expect(vm.autoScroll).toBe(true)
    })
  })

  describe('Cleanup', () => {
    it('should disconnect on unmount', async () => {
      const wrapper = await mountComponent()

      wrapper.unmount()

      expect(mockDisconnect).toHaveBeenCalled()
    })
  })
})
