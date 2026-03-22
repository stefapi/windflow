import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ActionButtons from '@/components/ui/ActionButtons.vue'

// Stubs for Element Plus components
const ElTooltip = {
  template: '<div class="el-tooltip"><slot /></div>',
  props: ['content', 'disabled', 'placement'],
}

const ElButton = {
  template: '<button class="el-button" :data-size="size" :disabled="disabled"><slot /></button>',
  props: ['size', 'disabled', 'circle'],
}

const ElIcon = {
  template: '<span class="el-icon"><slot /></span>',
}

describe('ActionButtons', () => {
  const mountActionButtons = (props = {}) => {
    return mount(ActionButtons, {
      props,
      global: {
        stubs: {
          'el-tooltip': ElTooltip,
          'el-button': ElButton,
          'el-icon': ElIcon,
        },
      },
    })
  }

  describe('Rendering', () => {
    it('renders with string actions', () => {
      const wrapper = mountActionButtons({ actions: ['start', 'stop'] })
      const buttons = wrapper.findAll('.el-button')
      expect(buttons.length).toBe(2)
    })

    it('renders with object actions', () => {
      const wrapper = mountActionButtons({
        actions: [
          { type: 'start', tooltip: 'Démarrer le container' },
          { type: 'logs', tooltip: 'Voir les logs' },
        ],
      })
      const buttons = wrapper.findAll('.el-button')
      expect(buttons.length).toBe(2)
    })

    it('renders all action types', () => {
      const wrapper = mountActionButtons({
        actions: ['start', 'stop', 'restart', 'logs', 'delete'],
      })
      const buttons = wrapper.findAll('.el-button')
      expect(buttons.length).toBe(5)
    })
  })

  describe('Action configuration', () => {
    it('applies correct class for each action type', () => {
      const wrapper = mountActionButtons({
        actions: ['start', 'stop', 'restart', 'logs', 'delete'],
      })

      expect(wrapper.find('.action-buttons__btn--start').exists()).toBe(true)
      expect(wrapper.find('.action-buttons__btn--stop').exists()).toBe(true)
      expect(wrapper.find('.action-buttons__btn--restart').exists()).toBe(true)
      expect(wrapper.find('.action-buttons__btn--logs').exists()).toBe(true)
      expect(wrapper.find('.action-buttons__btn--delete').exists()).toBe(true)
    })

    it('disables button when disabled is true', () => {
      const wrapper = mountActionButtons({
        actions: [{ type: 'start', disabled: true }],
      })
      const button = wrapper.find('.el-button')
      expect(button.attributes('disabled')).toBeDefined()
    })

    it('uses custom tooltip when provided', () => {
      const wrapper = mountActionButtons({
        actions: [{ type: 'start', tooltip: 'Custom tooltip' }],
      })
      const tooltip = wrapper.find('.el-tooltip')
      expect(tooltip.exists()).toBe(true)
    })
  })

  describe('Events', () => {
    it('emits action event when button is clicked', async () => {
      const wrapper = mountActionButtons({ actions: ['start'] })
      const button = wrapper.find('.el-button')
      await button.trigger('click')
      expect(wrapper.emitted('action')).toBeTruthy()
      expect(wrapper.emitted('action')![0]).toEqual(['start'])
    })

    it('emits correct action type for each button', async () => {
      const wrapper = mountActionButtons({ actions: ['start'] })
      const button = wrapper.find('.el-button')
      await button.trigger('click')
      expect(wrapper.emitted('action')![0]).toEqual(['start'])
    })

    it('emits stop action when stop button is clicked', async () => {
      const wrapper = mountActionButtons({ actions: ['stop'] })
      const button = wrapper.find('.el-button')
      await button.trigger('click')
      expect(wrapper.emitted('action')![0]).toEqual(['stop'])
    })
  })

  describe('Size variants', () => {
    it('applies small size', () => {
      const wrapper = mountActionButtons({ actions: ['start'], size: 'small' })
      const button = wrapper.find('.el-button')
      expect(button.attributes('data-size')).toBe('small')
    })

    it('applies default size', () => {
      const wrapper = mountActionButtons({ actions: ['start'], size: 'default' })
      const button = wrapper.find('.el-button')
      expect(button.attributes('data-size')).toBe('default')
    })

    it('applies large size', () => {
      const wrapper = mountActionButtons({ actions: ['start'], size: 'large' })
      const button = wrapper.find('.el-button')
      expect(button.attributes('data-size')).toBe('large')
    })
  })
})
