import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { markRaw, h } from 'vue'
import CounterCard from '@/components/ui/CounterCard.vue'

// Mock icon component using markRaw to avoid reactive warning
const MockIcon = markRaw({
  name: 'MockIcon',
  render: () => h('svg', { 'data-testid': 'mock-icon' }),
})

// Stubs for Element Plus components
const ElIcon = {
  template: '<span class="el-icon" :data-size="size"><slot /></span>',
  props: ['size'],
}

// Stub for RouterLink
const RouterLinkStub = {
  name: 'RouterLink',
  template: '<a class="router-link" :data-to="JSON.stringify(to)"><slot /></a>',
  props: ['to'],
}

describe('CounterCard', () => {
  const mountCounterCard = (props = {}) => {
    return mount(CounterCard, {
      props,
      global: {
        stubs: {
          'el-icon': ElIcon,
          'RouterLink': RouterLinkStub,
        },
      },
    })
  }

  describe('Rendering', () => {
    it('renders with default props', () => {
      const wrapper = mountCounterCard({
        count: 42,
        label: 'Containers',
        icon: MockIcon,
      })
      expect(wrapper.find('[data-testid="counter-card"]').exists()).toBe(true)
      expect(wrapper.find('.counter-card__count').text()).toBe('42')
      expect(wrapper.find('.counter-card__label').text()).toBe('Containers')
    })

    it('renders as div when to is not provided', () => {
      const wrapper = mountCounterCard({
        count: 7,
        label: 'VMs',
        icon: MockIcon,
      })
      expect(wrapper.find('.router-link').exists()).toBe(false)
      expect(wrapper.find('.counter-card').exists()).toBe(true)
    })

    it('renders as RouterLink when to is provided', () => {
      const wrapper = mountCounterCard({
        count: 7,
        label: 'VMs',
        icon: MockIcon,
        to: '/vms',
      })
      expect(wrapper.find('.router-link').exists()).toBe(true)
    })
  })

  describe('Count formatting', () => {
    it('displays small numbers as-is', () => {
      const wrapper = mountCounterCard({
        count: 42,
        label: 'Test',
        icon: MockIcon,
      })
      expect(wrapper.find('.counter-card__count').text()).toBe('42')
    })

    it('formats thousands with K suffix', () => {
      const wrapper = mountCounterCard({
        count: 1500,
        label: 'Test',
        icon: MockIcon,
      })
      expect(wrapper.find('.counter-card__count').text()).toBe('1.5K')
    })

    it('formats millions with M suffix', () => {
      const wrapper = mountCounterCard({
        count: 2500000,
        label: 'Test',
        icon: MockIcon,
      })
      expect(wrapper.find('.counter-card__count').text()).toBe('2.5M')
    })
  })

  describe('Size variants', () => {
    it('applies small size class', () => {
      const wrapper = mountCounterCard({
        count: 5,
        label: 'Test',
        icon: MockIcon,
        size: 'small',
      })
      expect(wrapper.find('.counter-card--small').exists()).toBe(true)
    })

    it('applies default size class', () => {
      const wrapper = mountCounterCard({
        count: 5,
        label: 'Test',
        icon: MockIcon,
        size: 'default',
      })
      expect(wrapper.find('.counter-card--default').exists()).toBe(true)
    })

    it('applies large size class', () => {
      const wrapper = mountCounterCard({
        count: 5,
        label: 'Test',
        icon: MockIcon,
        size: 'large',
      })
      expect(wrapper.find('.counter-card--large').exists()).toBe(true)
    })
  })

  describe('Clickable behavior', () => {
    it('has clickable class when to is provided', () => {
      const wrapper = mountCounterCard({
        count: 5,
        label: 'Test',
        icon: MockIcon,
        to: '/test',
      })
      expect(wrapper.find('.counter-card--clickable').exists()).toBe(true)
    })

    it('does not have clickable class when to is not provided', () => {
      const wrapper = mountCounterCard({
        count: 5,
        label: 'Test',
        icon: MockIcon,
      })
      expect(wrapper.find('.counter-card--clickable').exists()).toBe(false)
    })
  })

  // STORY-432: Running/Stopped indicators
  describe('Running/Stopped indicators (STORY-432)', () => {
    it('does not display status indicators when runningCount and stoppedCount are undefined', () => {
      const wrapper = mountCounterCard({
        count: 10,
        label: 'Test',
        icon: MockIcon,
      })
      expect(wrapper.find('.counter-card__status').exists()).toBe(false)
    })

    it('displays status indicators when runningCount is provided', () => {
      const wrapper = mountCounterCard({
        count: 10,
        label: 'Containers',
        icon: MockIcon,
        runningCount: 7,
      })
      expect(wrapper.find('.counter-card__status').exists()).toBe(true)
      expect(wrapper.find('.counter-card__status-item--running').exists()).toBe(true)
      expect(wrapper.find('.counter-card__status-item--running .counter-card__status-count').text()).toBe('7')
    })

    it('displays status indicators when stoppedCount is provided', () => {
      const wrapper = mountCounterCard({
        count: 10,
        label: 'Containers',
        icon: MockIcon,
        stoppedCount: 3,
      })
      expect(wrapper.find('.counter-card__status').exists()).toBe(true)
      expect(wrapper.find('.counter-card__status-item--stopped').exists()).toBe(true)
      expect(wrapper.find('.counter-card__status-item--stopped .counter-card__status-count').text()).toBe('3')
    })

    it('displays both running and stopped counts when both are provided', () => {
      const wrapper = mountCounterCard({
        count: 10,
        label: 'Containers',
        icon: MockIcon,
        runningCount: 7,
        stoppedCount: 3,
      })
      expect(wrapper.find('.counter-card__status').exists()).toBe(true)
      expect(wrapper.find('.counter-card__status-item--running .counter-card__status-count').text()).toBe('7')
      expect(wrapper.find('.counter-card__status-item--stopped .counter-card__status-count').text()).toBe('3')
    })
  })
})
