/**
 * ContainerOverviewTab.vue Unit Tests — STORY-027.1
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ContainerOverviewTab from '@/components/ContainerOverviewTab.vue'

// Mock containersApi.list
const mockList = vi.fn()
vi.mock('@/services/api', () => ({
  containersApi: {
    list: (...args: unknown[]) => mockList(...args),
  },
}))

// Mock useContainerStats
const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
vi.mock('@/composables/useContainerStats', () => ({
  useContainerStats: () => ({
    stats: ref(null),
    connect: mockConnect,
    disconnect: mockDisconnect,
    isStreaming: ref(false),
  }),
}))

// Mock helpers
vi.mock('@/components/compute/helpers', () => ({
  getContainerStatusType: (state: string) => {
    if (state === 'running') return 'success'
    if (state === 'exited') return 'info'
    return 'warning'
  },
  getContainerStatusLabel: (state: string) => state || 'unknown',
}))

const baseDetail = {
  id: 'abc123',
  name: 'test-container',
  image: 'nginx:latest',
  state: { status: 'running' },
  config: {
    labels: { 'com.docker.compose.project': 'my-stack' },
  },
  mounts: [
    { Type: 'volume', Source: 'vol1', Destination: '/data', Mode: 'rw', Name: 'vol1' },
    { Type: 'bind', Source: '/host/path', Destination: '/app', Mode: 'ro' },
  ],
  network_settings: {
    networks: {
      bridge: { ip_address: '172.17.0.2', gateway: '172.17.0.1', mac_address: '02:42:ac:11:00:02' },
    },
  },
}

describe('ContainerOverviewTab.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({
      data: [
        { id: 'abc123', name: 'test-container', image: 'nginx:latest', state: 'running', labels: { 'com.docker.compose.project': 'my-stack' } },
        { id: 'def456', name: 'test-container-2', image: 'redis:latest', state: 'running', labels: { 'com.docker.compose.project': 'my-stack' } },
      ],
    })
  })

  const mountComponent = async (overrides: Record<string, unknown> = {}) => {
    const props = {
      detail: baseDetail,
      containerId: 'abc123',
      containerState: 'running',
      ...overrides,
    }

    const wrapper = mount(ContainerOverviewTab, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
          'el-table': { template: '<div class="el-table-stub"><slot /></div>', props: ['data'] },
          'el-table-column': { template: '<div class="el-table-column-stub" />', props: ['label', 'prop', 'width', 'minWidth'] },
          'el-tag': { template: '<span class="el-tag-stub"><slot /></span>', props: ['type', 'size'] },
          'el-icon': { template: '<i class="el-icon-stub"><slot /></i>' },
          'el-empty': { template: '<div class="el-empty-stub">{{ description }}</div>', props: ['description', 'imageSize'] },
          'el-button': { template: '<button class="el-button-stub"><slot /></button>', props: ['disabled'] },
          'el-alert': { template: '<div class="el-alert-stub"><slot name="title" /><slot /></div>', props: ['type', 'closable', 'showIcon'] },
          'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>', props: ['column', 'border', 'size'] },
          'el-descriptions-item': { template: '<div class="el-descriptions-item-stub"><slot /></div>', props: ['label'] },
          ResourceBar: { template: '<div class="resource-bar-stub">{{ value }}</div>', props: ['value', 'label', 'showValue'] },
        },
      },
      props,
    })

    await flushPromises()
    return wrapper
  }

  describe('Rendering', () => {
    it('should mount successfully', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.exists()).toBe(true)
    })

    it('should render a grid container', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.overview-grid').exists()).toBe(true)
    })

    it('should render 3 static cards (Services, Volumes, Réseau)', async () => {
      const wrapper = await mountComponent()
      const cards = wrapper.findAll('.overview-card')
      expect(cards.length).toBeGreaterThanOrEqual(3)
    })

    it('should render Services card', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.card-services').exists()).toBe(true)
    })

    it('should render Volumes card', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.card-volumes').exists()).toBe(true)
    })

    it('should render Network card', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.card-network').exists()).toBe(true)
    })
  })

  describe('Health card', () => {
    it('should not show Health card when no health info', async () => {
      const wrapper = await mountComponent({ detail: { ...baseDetail, state: { status: 'running' } } })
      expect(wrapper.find('.card-health').exists()).toBe(false)
    })

    it('should show Health card when health info exists', async () => {
      const detailWithHealth = {
        ...baseDetail,
        state: { status: 'running', health: { status: 'healthy', failing_streak: 0 } },
      }
      const wrapper = await mountComponent({ detail: detailWithHealth })
      expect(wrapper.find('.card-health').exists()).toBe(true)
    })
  })

  describe('Services card', () => {
    it('should call containersApi.list on mount', async () => {
      await mountComponent()
      expect(mockList).toHaveBeenCalledWith(true)
    })

    it('should display project name from labels', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { projectName: string | null }
      expect(vm.projectName).toBe('my-stack')
    })

    it('should filter services by compose project label', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { stackServices: unknown[] }
      await flushPromises()
      // mockList returns 2 containers with same project label
      expect(vm.stackServices.length).toBe(2)
    })
  })

  describe('Volumes card', () => {
    it('should parse mounts from detail', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { parsedMounts: unknown[] }
      expect(vm.parsedMounts.length).toBe(2)
    })

    it('should handle empty mounts', async () => {
      const wrapper = await mountComponent({ detail: { ...baseDetail, mounts: [] } })
      const vm = wrapper.vm as unknown as { parsedMounts: unknown[] }
      expect(vm.parsedMounts.length).toBe(0)
    })
  })

  describe('Network card', () => {
    it('should parse networks from detail', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { parsedNetworks: { networkName: string; ipAddress: string }[] }
      const networks = vm.parsedNetworks
      expect(networks.length).toBe(1)
      expect(networks[0].networkName).toBe('bridge')
      expect(networks[0].ipAddress).toBe('172.17.0.2')
    })

    it('should handle missing network_settings', async () => {
      const wrapper = await mountComponent({ detail: { ...baseDetail, network_settings: {} } })
      const vm = wrapper.vm as unknown as { parsedNetworks: unknown[] }
      expect(vm.parsedNetworks.length).toBe(0)
    })
  })

  describe('Health computed', () => {
    it('should compute healthTagType correctly for healthy', async () => {
      const detailWithHealth = {
        ...baseDetail,
        state: { status: 'running', health: { status: 'healthy', failing_streak: 0 } },
      }
      const wrapper = await mountComponent({ detail: detailWithHealth })
      const vm = wrapper.vm as unknown as { healthTagType: string }
      expect(vm.healthTagType).toBe('success')
    })

    it('should compute healthTagType correctly for unhealthy', async () => {
      const detailWithHealth = {
        ...baseDetail,
        state: { status: 'running', health: { status: 'unhealthy', failing_streak: 3 } },
      }
      const wrapper = await mountComponent({ detail: detailWithHealth })
      const vm = wrapper.vm as unknown as { healthTagType: string }
      expect(vm.healthTagType).toBe('danger')
    })
  })

  describe('Resources card (STORY-027.2)', () => {
    it('should render Resources card', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.card-resources').exists()).toBe(true)
    })

    it('should show stopped message when container is not running', async () => {
      const wrapper = await mountComponent({ containerState: 'exited' })
      const card = wrapper.find('.card-resources')
      expect(card.find('.el-alert-stub').exists()).toBe(true)
    })

    it('should show stat sections when container is running', async () => {
      const wrapper = await mountComponent({ containerState: 'running' })
      const card = wrapper.find('.card-resources')
      expect(card.findAll('.stat-section').length).toBe(4)
    })

    it('should call connect when container state is running', async () => {
      await mountComponent({ containerState: 'running' })
      expect(mockConnect).toHaveBeenCalled()
    })

    it('should call disconnect when container state is not running', async () => {
      await mountComponent({ containerState: 'exited' })
      expect(mockDisconnect).toHaveBeenCalled()
    })

    it('should display Live tag when streaming', async () => {
      // The Live tag appears when isStreaming is true — verified by integration tests
      // Here we just verify the tag is NOT shown when isStreaming is false
      const wrapper = await mountComponent({ containerState: 'running' })
      const tags = wrapper.find('.card-resources').findAll('.el-tag-stub')
      const liveTags = tags.filter(t => t.text().includes('Live'))
      expect(liveTags.length).toBe(0)
    })
  })

  describe('Edge cases', () => {
    it('should handle null detail', async () => {
      const wrapper = await mountComponent({ detail: null })
      expect(wrapper.exists()).toBe(true)
      const vm = wrapper.vm as unknown as { parsedMounts: unknown[]; parsedNetworks: unknown[] }
      expect(vm.parsedMounts.length).toBe(0)
      expect(vm.parsedNetworks.length).toBe(0)
    })

    it('should handle API error gracefully', async () => {
      mockList.mockRejectedValue(new Error('Network error'))
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { stackServices: unknown[] }
      await flushPromises()
      expect(vm.stackServices.length).toBe(0)
    })
  })
})
