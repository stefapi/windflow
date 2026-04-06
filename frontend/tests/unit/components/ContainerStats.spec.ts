/**
 * ContainerStats.vue Unit Tests — STORY-029.2
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import { ref, type Ref } from 'vue'
import ContainerStats from '@/components/ContainerStats.vue'
import type { ContainerStats as ContainerStatsType, StatsStreamStatus } from '@/composables/useContainerStats'

// Mutable mock state
let mockStats: Ref<ContainerStatsType | null> = ref(null)
let mockStatus: Ref<StatsStreamStatus> = ref('disconnected')
let mockError: Ref<string | null> = ref(null)
let mockIsStreaming = ref(false)
let mockHistory: Ref<ContainerStatsType[]> = ref([])

const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockReconnect = vi.fn()
const mockFetchOnce = vi.fn()

vi.mock('@/composables/useContainerLogs', () => ({}))

vi.mock('@/composables/useContainerStats', () => ({
  useContainerStats: () => ({
    stats: mockStats,
    status: mockStatus,
    error: mockError,
    isStreaming: mockIsStreaming,
    history: mockHistory,
    connect: mockConnect,
    disconnect: mockDisconnect,
    reconnect: mockReconnect,
    fetchOnce: mockFetchOnce,
  }),
}))

vi.mock('@/stores', () => ({
  useAuthStore: () => ({
    token: 'mock-jwt-token',
  }),
}))

// Mock vue-echarts
vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div class="v-chart-stub"></div>',
    props: ['option', 'autoresize'],
  },
}))

function createSampleStats(overrides: Partial<ContainerStatsType> = {}): ContainerStatsType {
  return {
    cpu_percent: 25.5,
    memory_percent: 45.2,
    memory_used: 512 * 1024 * 1024,
    memory_limit: 1024 * 1024 * 1024,
    network_rx_bytes: 1024 * 1024 * 10,
    network_tx_bytes: 1024 * 1024 * 5,
    block_read_bytes: 2048 * 1024,
    block_write_bytes: 1024 * 512,
    timestamp: new Date().toISOString(),
    network_interfaces: [
      {
        name: 'eth0',
        rx_bytes: 1024 * 1024 * 10,
        tx_bytes: 1024 * 1024 * 5,
        rx_packets: 10000,
        tx_packets: 5000,
        rx_errors: 0,
        tx_errors: 0,
        rx_dropped: 0,
        tx_dropped: 0,
      },
    ],
    total_rx_errors: 0,
    total_tx_errors: 0,
    total_rx_dropped: 0,
    total_tx_dropped: 0,
    blkio_devices: [
      {
        major: 8,
        minor: 0,
        read_bytes: 2048 * 1024,
        write_bytes: 1024 * 512,
        read_ops: 150,
        write_ops: 75,
      },
    ],
    network_rx_rate: 1024 * 100, // 100 KB/s
    network_tx_rate: 1024 * 50, // 50 KB/s
    block_read_rate: 1024 * 200, // 200 KB/s
    block_write_rate: 1024 * 80, // 80 KB/s
    ...overrides,
  }
}

describe('ContainerStats.vue', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(() => {
    vi.clearAllMocks()
    mockStats.value = null
    mockStatus.value = 'disconnected'
    mockError.value = null
    mockIsStreaming.value = false
    mockHistory.value = []

    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'Home', component: { template: '<div>Home</div>' } },
        { path: '/containers/:id', name: 'ContainerDetail', component: { template: '<div>ContainerDetail</div>' } },
      ],
    })

    const pinia = createPinia()
    setActivePinia(pinia)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountComponent = async (containerId = 'test-container-123', props = {}) => {
    await router.push(`/containers/${containerId}`)
    await router.isReady()

    const wrapper = mount(ContainerStats, {
      props: {
        containerId,
        containerName: 'test-container',
        ...props,
      },
      global: {
        plugins: [router, ElementPlus, createPinia()],
        stubs: {
          'el-tag': {
            template: '<span class="el-tag-stub" :data-type="type"><slot /></span>',
            props: ['type', 'size'],
          },
          'el-switch': {
            template: '<div class="el-switch-stub"></div>',
            props: ['modelValue', 'size', 'activeText', 'inactiveText'],
          },
          'el-button': {
            template: '<button class="el-button-stub"><slot /></button>',
            props: ['size', 'type'],
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
          'v-chart': {
            template: '<div class="v-chart-stub"></div>',
            props: ['option', 'autoresize'],
          },
          'resource-bar': {
            template: '<div class="resource-bar-stub"></div>',
            props: ['value', 'label', 'showValue'],
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

    it('should display stats-not-running when disconnected with no stats (AC7)', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.stats-not-running').exists()).toBe(true)
      expect(wrapper.find('.el-empty-stub').text()).toContain('Les statistiques ne sont disponibles')
    })
  })

  describe('Network I/O section (STORY-029.2)', () => {
    it('should display network rates when stats are available', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const networkSection = wrapper.findAll('.stat-section')[2] // 3rd section = Network
      expect(networkSection.exists()).toBe(true)

      const rateValues = networkSection.findAll('.io-rate')
      expect(rateValues.length).toBe(2)
      expect(rateValues[0].text()).toContain('/s') // RX rate
      expect(rateValues[1].text()).toContain('/s') // TX rate
    })

    it('should display cumulative totals', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const networkSection = wrapper.findAll('.stat-section')[2]
      const totals = networkSection.find('.io-totals')
      expect(totals.exists()).toBe(true)
      expect(totals.text()).toContain('Total')
    })

    it('should display warning badge when network has errors', async () => {
      mockStats.value = createSampleStats({
        total_rx_errors: 5,
        total_tx_errors: 2,
        total_rx_dropped: 1,
        total_tx_dropped: 0,
      })
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const networkSection = wrapper.findAll('.stat-section')[2]
      const badge = networkSection.find('.io-badge-warning')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toContain('8') // 5+2+1+0
    })

    it('should not display warning badge when no network errors', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const networkSection = wrapper.findAll('.stat-section')[2]
      const badge = networkSection.find('.io-badge-warning')
      expect(badge.exists()).toBe(false)
    })
  })

  describe('Disk I/O section (STORY-029.2)', () => {
    it('should display disk rates when stats are available', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const diskSection = wrapper.findAll('.stat-section')[3] // 4th section = Disk
      expect(diskSection.exists()).toBe(true)

      const rateValues = diskSection.findAll('.io-rate')
      expect(rateValues.length).toBe(2)
      expect(rateValues[0].text()).toContain('/s') // Read rate
      expect(rateValues[1].text()).toContain('/s') // Write rate
    })

    it('should display cumulative disk totals', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const diskSection = wrapper.findAll('.stat-section')[3]
      const totals = diskSection.find('.io-totals')
      expect(totals.exists()).toBe(true)
      expect(totals.text()).toContain('Total')
    })

    it('should display IOPS per device when available', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const diskSection = wrapper.findAll('.stat-section')[3]
      const iopsSection = diskSection.find('.io-iops')
      expect(iopsSection.exists()).toBe(true)
      expect(iopsSection.find('.iops-device').exists()).toBe(true)
    })

    it('should not display IOPS section when no devices have ops', async () => {
      mockStats.value = createSampleStats({
        blkio_devices: [
          { major: 8, minor: 0, read_bytes: 0, write_bytes: 0, read_ops: 0, write_ops: 0 },
        ],
      })
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      const diskSection = wrapper.findAll('.stat-section')[3]
      const iopsSection = diskSection.find('.io-iops')
      expect(iopsSection.exists()).toBe(false)
    })
  })

  describe('Charts section', () => {
    it('should show history section with charts when history is available', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true
      mockHistory.value = [
        {
          cpu_percent: 10,
          memory_percent: 30,
          memory_used: 512 * 1024 * 1024,
          network_rx_bytes: 1024,
          network_tx_bytes: 512,
          block_read_bytes: 2048,
          block_write_bytes: 1024,
          network_rx_rate: 100,
          network_tx_rate: 50,
          block_read_rate: 200,
          block_write_rate: 80,
          timestamp: Date.now(),
        },
      ] as any

      const wrapper = await mountComponent()

      const historySection = wrapper.find('.history-section')
      expect(historySection.exists()).toBe(true)
      expect(wrapper.findAll('.v-chart-stub').length).toBe(4)
    })

    it('should show loading message when no history', async () => {
      mockStats.value = createSampleStats()
      mockStatus.value = 'connected'
      mockIsStreaming.value = true

      const wrapper = await mountComponent()

      expect(wrapper.find('.no-history').exists()).toBe(true)
      expect(wrapper.find('.no-history').text()).toContain('Collecte')
    })
  })

  describe('Connection controls', () => {
    it('should call reconnect when auto-refresh and refresh clicked', async () => {
      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        autoRefresh: boolean
        handleRefresh: () => void
      }

      vm.autoRefresh = true
      vm.handleRefresh()

      expect(mockReconnect).toHaveBeenCalled()
    })

    it('should call fetchOnce when manual mode and refresh clicked', async () => {
      const wrapper = await mountComponent()

      const vm = wrapper.vm as unknown as {
        autoRefresh: boolean
        handleRefresh: () => void
      }

      vm.autoRefresh = false
      vm.handleRefresh()

      expect(mockFetchOnce).toHaveBeenCalled()
    })

    it('should unmount without errors', async () => {
      const wrapper = await mountComponent()
      expect(() => wrapper.unmount()).not.toThrow()
    })
  })
})
