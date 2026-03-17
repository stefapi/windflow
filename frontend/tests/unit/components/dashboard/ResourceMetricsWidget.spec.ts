import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ResourceMetricsWidget from '@/components/dashboard/ResourceMetricsWidget.vue'
import type { ResourceMetrics } from '@/types/api'

// Mock vue-echarts
vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div data-testid="v-chart"></div>',
  },
}))

// Mock echarts/core
vi.mock('echarts/core', () => ({
  use: vi.fn(),
}))

vi.mock('echarts/charts', () => ({
  LineChart: {},
}))

vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  LegendComponent: {},
}))

vi.mock('echarts/renderers', () => ({
  CanvasRenderer: {},
}))

describe('ResourceMetricsWidget', () => {
  const createMetrics = (overrides?: Partial<ResourceMetrics>): ResourceMetrics => ({
    current_cpu: 45.5,
    current_memory: 62.3,
    current_disk: 35.8,
    uptime_seconds: 86400,
    used_memory_mb: 8000,
    total_memory_mb: 16000,
    used_disk_gb: 180,
    total_disk_gb: 500,
    history: [
      { timestamp: '2024-01-01T10:00:00Z', cpu: 40, memory: 60 },
      { timestamp: '2024-01-01T10:01:00Z', cpu: 45, memory: 62 },
      { timestamp: '2024-01-01T10:02:00Z', cpu: 42, memory: 61 },
    ],
    ...overrides,
  })

  describe('rendering', () => {
    it('should render with metrics', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: {
          metrics,
          error: null,
        },
        global: {
          stubs: {
            'el-card': {
              template: '<div class="el-card"><slot name="header" /><slot /></div>',
            },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'el-skeleton': { template: '<div class="el-skeleton" />' },
            'el-alert': { template: '<div class="el-alert" />' },
            'el-empty': { template: '<div class="el-empty" />' },
            ResourceBar: { template: '<div class="resource-bar" />' },
            'router-link': { template: '<a><slot /></a>' },
          },
        },
      })

      expect(wrapper.find('[data-testid="resource-metrics-widget"]').exists()).toBe(true)
    })

    it('should display CPU metric', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('CPU')
      expect(wrapper.text()).toContain('46%') // rounded 45.5
    })

    it('should display RAM metric with MB values', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('RAM')
      expect(wrapper.text()).toContain('8000 / 16000 MB')
    })

    it('should display Disk metric with GB values', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('Disk')
      expect(wrapper.text()).toContain('180.0 / 500.0 GB')
    })

    it('should display uptime in days when > 24h', () => {
      const metrics = createMetrics({ uptime_seconds: 172800 }) // 2 days
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('2d 0h 0m')
    })

    it('should display uptime in hours when < 24h', () => {
      const metrics = createMetrics({ uptime_seconds: 7200 }) // 2 hours
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('2h 0m')
    })

    it('should display uptime in minutes when < 1h', () => {
      const metrics = createMetrics({ uptime_seconds: 1800 }) // 30 minutes
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('30m')
    })
  })

  describe('states', () => {
    it('should show error state when error prop is set', () => {
      const wrapper = mount(ResourceMetricsWidget, {
        props: {
          metrics: null,
          error: 'Connection failed',
        },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'el-alert': { template: '<div class="el-alert"><slot /></div>' },
          },
        },
      })

      expect(wrapper.find('.resource-metrics-widget__error').exists()).toBe(true)
      expect(wrapper.text()).toContain('Unable to retrieve system metrics')
    })

    it('should show no target state when noTarget is true', () => {
      const wrapper = mount(ResourceMetricsWidget, {
        props: {
          metrics: null,
          error: null,
          noTarget: true,
        },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            'router-link': { template: '<a><slot /></a>' },
          },
        },
      })

      expect(wrapper.find('.resource-metrics-widget__no-target').exists()).toBe(true)
      expect(wrapper.text()).toContain('No target selected')
    })

    it('should show loading state when loading is true', () => {
      const wrapper = mount(ResourceMetricsWidget, {
        props: {
          metrics: null,
          error: null,
          loading: true,
        },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-skeleton': { template: '<div class="el-skeleton">Loading...</div>' },
          },
        },
      })

      expect(wrapper.find('.resource-metrics-widget__loading').exists()).toBe(true)
    })

    it('should show empty state when no metrics', () => {
      const wrapper = mount(ResourceMetricsWidget, {
        props: {
          metrics: null,
          error: null,
        },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-empty': { template: '<div class="el-empty">No data</div>' },
          },
        },
      })

      expect(wrapper.find('.el-empty').exists()).toBe(true)
    })

    it('should show "Collecting historical data" when no history', () => {
      const metrics = createMetrics({ history: [] })
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('Collecting historical data')
    })
  })

  describe('target name', () => {
    it('should display target name when provided', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: {
          metrics,
          error: null,
          targetName: 'Server 1',
        },
        global: {
          stubs: {
            'el-card': {
              template: '<div class="el-card"><slot name="header" /><slot /></div>',
            },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('Server 1')
    })

    it('should not display target name when not provided', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': {
              template: '<div class="el-card"><slot name="header" /><slot /></div>',
            },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.find('.target-name').exists()).toBe(false)
    })
  })

  describe('history chart', () => {
    it('should show chart when history is available', () => {
      const metrics = createMetrics()
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
            VChart: { template: '<div data-testid="v-chart"></div>' },
          },
        },
      })

      expect(wrapper.find('.charts-section').exists()).toBe(true)
    })
  })

  describe('formatting fallbacks', () => {
    it('should show percentage for RAM when MB values not available', () => {
      const metrics = createMetrics({
        used_memory_mb: undefined,
        total_memory_mb: undefined,
        current_memory: 75,
      })
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('75%')
    })

    it('should show percentage for Disk when GB values not available', () => {
      const metrics = createMetrics({
        used_disk_gb: undefined,
        total_disk_gb: undefined,
        current_disk: 45,
      })
      const wrapper = mount(ResourceMetricsWidget, {
        props: { metrics, error: null },
        global: {
          stubs: {
            'el-card': { template: '<div class="el-card"><slot /></div>' },
            'el-icon': { template: '<i class="el-icon"><slot /></i>' },
            ResourceBar: { template: '<div class="resource-bar" />' },
          },
        },
      })

      expect(wrapper.text()).toContain('45%')
    })
  })
})
