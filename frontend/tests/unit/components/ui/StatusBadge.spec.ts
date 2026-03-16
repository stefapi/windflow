import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '@/components/ui/StatusBadge.vue'

// Stubs for Element Plus components
const ElIcon = {
  template: '<span class="el-icon"><slot /></span>',
}

describe('StatusBadge', () => {
  const mountStatusBadge = (props = {}) => {
    return mount(StatusBadge, {
      props,
      global: {
        stubs: {
          'el-icon': ElIcon,
        },
      },
    })
  }

  describe('Rendering', () => {
    it('renders with default props', () => {
      const wrapper = mountStatusBadge({ status: 'running' })
      expect(wrapper.find('[data-testid="status-badge"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('En cours')
    })

    it('renders with custom label', () => {
      const wrapper = mountStatusBadge({ status: 'running', label: 'Actif' })
      expect(wrapper.text()).toContain('Actif')
    })

    it('renders with icon when showIcon is true', () => {
      const wrapper = mountStatusBadge({ status: 'running', showIcon: true })
      expect(wrapper.find('.el-icon').exists()).toBe(true)
    })

    it('hides icon when showIcon is false', () => {
      const wrapper = mountStatusBadge({ status: 'running', showIcon: false })
      expect(wrapper.find('.el-icon').exists()).toBe(false)
    })
  })

  describe('Status variants', () => {
    it('applies success class for running status', () => {
      const wrapper = mountStatusBadge({ status: 'running' })
      expect(wrapper.find('.status-badge--success').exists()).toBe(true)
      expect(wrapper.text()).toContain('En cours')
    })

    it('applies info class for stopped status', () => {
      const wrapper = mountStatusBadge({ status: 'stopped' })
      expect(wrapper.find('.status-badge--info').exists()).toBe(true)
      expect(wrapper.text()).toContain('Arrêté')
    })

    it('applies error class for error status', () => {
      const wrapper = mountStatusBadge({ status: 'error' })
      expect(wrapper.find('.status-badge--error').exists()).toBe(true)
      expect(wrapper.text()).toContain('Erreur')
    })

    it('applies warning class for deploying status', () => {
      const wrapper = mountStatusBadge({ status: 'deploying' })
      expect(wrapper.find('.status-badge--warning').exists()).toBe(true)
      expect(wrapper.text()).toContain('Déploiement')
    })
  })

  describe('Size variants', () => {
    it('applies small size class', () => {
      const wrapper = mountStatusBadge({ status: 'running', size: 'small' })
      expect(wrapper.find('.status-badge--small').exists()).toBe(true)
    })

    it('applies default size class', () => {
      const wrapper = mountStatusBadge({ status: 'running', size: 'default' })
      expect(wrapper.find('.status-badge--default').exists()).toBe(true)
    })

    it('applies large size class', () => {
      const wrapper = mountStatusBadge({ status: 'running', size: 'large' })
      expect(wrapper.find('.status-badge--large').exists()).toBe(true)
    })
  })
})
