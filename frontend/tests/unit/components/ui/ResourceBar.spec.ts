import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ResourceBar from '@/components/ui/ResourceBar.vue'

describe('ResourceBar', () => {
  const mountResourceBar = (props = {}) => {
    return mount(ResourceBar, {
      props,
    })
  }

  describe('Rendering', () => {
    it('renders with default props', () => {
      const wrapper = mountResourceBar({ value: 50 })
      expect(wrapper.find('[data-testid="resource-bar"]').exists()).toBe(true)
    })

    it('renders with label', () => {
      const wrapper = mountResourceBar({ value: 50, label: 'CPU' })
      expect(wrapper.find('.resource-bar__label').exists()).toBe(true)
      expect(wrapper.find('.resource-bar__label').text()).toBe('CPU')
    })

    it('renders without label when not provided', () => {
      const wrapper = mountResourceBar({ value: 50 })
      expect(wrapper.find('.resource-bar__label').exists()).toBe(false)
    })

    it('shows value when label is provided and showValue is true', () => {
      const wrapper = mountResourceBar({ value: 75, label: 'CPU', showValue: true })
      expect(wrapper.find('.resource-bar__value').exists()).toBe(true)
      expect(wrapper.find('.resource-bar__value').text()).toBe('75%')
    })

    it('hides value when showValue is false', () => {
      const wrapper = mountResourceBar({ value: 75, label: 'CPU', showValue: false })
      expect(wrapper.find('.resource-bar__value').exists()).toBe(false)
    })

    it('does not show header when no label', () => {
      const wrapper = mountResourceBar({ value: 75, showValue: true })
      expect(wrapper.find('.resource-bar__header').exists()).toBe(false)
    })
  })

  describe('Value clamping', () => {
    it('clamps value to 0 when negative', () => {
      const wrapper = mountResourceBar({ value: -10 })
      const fill = wrapper.find('.resource-bar__fill')
      expect(fill.attributes('style')).toContain('width: 0%')
    })

    it('clamps value to 100 when over 100', () => {
      const wrapper = mountResourceBar({ value: 150 })
      const fill = wrapper.find('.resource-bar__fill')
      expect(fill.attributes('style')).toContain('width: 100%')
    })

    it('displays correct percentage for normal values', () => {
      const wrapper = mountResourceBar({ value: 42 })
      const fill = wrapper.find('.resource-bar__fill')
      expect(fill.attributes('style')).toContain('width: 42%')
    })
  })

  describe('Color thresholds', () => {
    it('applies success class for value < 60%', () => {
      const wrapper = mountResourceBar({ value: 45 })
      expect(wrapper.find('.resource-bar__fill--success').exists()).toBe(true)
    })

    it('applies warning class for value 60% to < 85%', () => {
      const wrapper = mountResourceBar({ value: 70 })
      expect(wrapper.find('.resource-bar__fill--warning').exists()).toBe(true)
    })

    it('applies error class for value >= 85%', () => {
      const wrapper = mountResourceBar({ value: 90 })
      expect(wrapper.find('.resource-bar__fill--error').exists()).toBe(true)
    })

    it('applies success class at boundary 59%', () => {
      const wrapper = mountResourceBar({ value: 59 })
      expect(wrapper.find('.resource-bar__fill--success').exists()).toBe(true)
    })

    it('applies warning class at boundary 60%', () => {
      const wrapper = mountResourceBar({ value: 60 })
      expect(wrapper.find('.resource-bar__fill--warning').exists()).toBe(true)
    })

    it('applies warning class at boundary 84%', () => {
      const wrapper = mountResourceBar({ value: 84 })
      expect(wrapper.find('.resource-bar__fill--warning').exists()).toBe(true)
    })

    it('applies error class at boundary 85%', () => {
      const wrapper = mountResourceBar({ value: 85 })
      expect(wrapper.find('.resource-bar__fill--error').exists()).toBe(true)
    })
  })
})
