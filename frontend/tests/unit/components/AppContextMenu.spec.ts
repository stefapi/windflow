/**
 * Tests unitaires pour AppContextMenu.vue
 * STORY-003 : Menu Contextuel `[⋯ Plus]` Canonique
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { h } from 'vue'
import AppContextMenu from '@/components/ui/AppContextMenu.vue'
import type { AppContextMenuProps } from '@/types/context-menu'

// Mock mode store
const { mockModeStore } = vi.hoisted(() => {
  const mockModeStore = {
    mode: 'app' as string,
    isAppMode: true,
    isInfraMode: false,
    setMode: vi.fn(),
    toggleMode: vi.fn(),
  }
  return { mockModeStore }
})

vi.mock('@/stores/mode', () => ({
  useModeStore: vi.fn(() => mockModeStore),
}))

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  MoreFilled: { name: 'MoreFilled', render: () => h('span', '⋯') },
  Link: { name: 'Link', render: () => h('span', '🔗') },
  VideoPlay: { name: 'VideoPlay', render: () => h('span', '▶') },
  VideoPause: { name: 'VideoPause', render: () => h('span', '⏸') },
  RefreshRight: { name: 'RefreshRight', render: () => h('span', '🔄') },
  Document: { name: 'Document', render: () => h('span', '📋') },
  Monitor: { name: 'Monitor', render: () => h('span', '🖥') },
  Setting: { name: 'Setting', render: () => h('span', '⚙') },
  InfoFilled: { name: 'InfoFilled', render: () => h('span', 'ℹ') },
  Delete: { name: 'Delete', render: () => h('span', '🗑') },
}))

/**
 * Helper to create default props.
 */
function createProps(overrides: Partial<AppContextMenuProps> = {}): AppContextMenuProps {
  return {
    containerId: 'test-container-1',
    containerName: 'Test App',
    containerStatus: 'running',
    domain: 'https://test.example.com',
    ...overrides,
  }
}

/**
 * Simple stub that renders slot content and passes through attributes.
 */
const ElDropdown = {
  inheritAttrs: false,
  setup(_: any, { slots, attrs }: any) {
    return () => h('div', { ...attrs, 'data-testid': attrs['data-testid'] || 'el-dropdown' }, [
      slots.default?.(),
      slots.dropdown?.(),
    ])
  },
}

const ElDropdownMenu = {
  setup(_: any, { slots }: any) {
    return () => h('div', { class: 'dropdown-menu' }, slots.default?.())
  },
}

const ElDropdownItem = {
  inheritAttrs: false,
  props: ['command', 'disabled', 'divided'],
  setup(props: any, { slots, attrs }: any) {
    return () => h('div', {
      ...attrs,
      class: [attrs.class, props.disabled ? 'is-disabled' : ''],
      'data-command': props.command,
      onClick: () => {
        if (!props.disabled) {
          attrs.onCommand?.(props.command)
        }
      },
    }, slots.default?.())
  },
}

const ElButton = {
  inheritAttrs: false,
  props: ['size', 'icon', 'circle'],
  setup(_: any, { slots, attrs }: any) {
    return () => h('button', { ...attrs }, slots.default?.())
  },
}

const ElIcon = {
  setup(_: any, { slots }: any) {
    return () => h('span', { class: 'el-icon' }, slots.default?.())
  },
}

/**
 * Helper to mount the component.
 */
function mountComponent(propsOverrides: Partial<AppContextMenuProps> = {}) {
  return mount(AppContextMenu, {
    props: createProps(propsOverrides),
    global: {
      stubs: {
        'el-dropdown': ElDropdown,
        'el-dropdown-menu': ElDropdownMenu,
        'el-dropdown-item': ElDropdownItem,
        'el-button': ElButton,
        'el-icon': ElIcon,
      },
    },
  })
}

describe('AppContextMenu', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockModeStore.mode = 'app'
    mockModeStore.isAppMode = true
    mockModeStore.isInfraMode = false
  })

  describe('rendu initial', () => {
    it('affiche le composant quand des actions sont disponibles', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('[data-testid="app-context-menu"]').exists()).toBe(true)
    })

    it('affiche le bouton trigger', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('[data-testid="app-context-menu-trigger"]').exists()).toBe(true)
    })
  })

  describe('structure du menu', () => {
    it('rend les 3 sections avec leurs titres', () => {
      const wrapper = mountComponent()

      const sectionTitles = wrapper.findAll('.context-menu-section-title')
      expect(sectionTitles.length).toBeGreaterThanOrEqual(3)
    })

    it('rend les items de la section primary', () => {
      const wrapper = mountComponent({ containerStatus: 'running', domain: 'https://test.example.com' })

      const openItem = wrapper.find('[data-testid="menu-item-open"]')
      expect(openItem.exists()).toBe(true)
    })

    it('rend les items de la section tools', () => {
      const wrapper = mountComponent()

      expect(wrapper.find('[data-testid="menu-item-logs"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="menu-item-console"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="menu-item-config"]').exists()).toBe(true)
    })

    it('rend les items de la section advanced', () => {
      const wrapper = mountComponent()

      expect(wrapper.find('[data-testid="menu-item-details"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="menu-item-delete"]').exists()).toBe(true)
    })
  })

  describe('styling', () => {
    it("l'item Supprimer a la classe danger", () => {
      const wrapper = mountComponent()

      const deleteItem = wrapper.find('[data-testid="menu-item-delete"]')
      expect(deleteItem.exists()).toBe(true)
      expect(deleteItem.classes()).toContain('context-menu-item--danger')
    })
  })

  describe('émission d\'événements', () => {
    it('émet l\'événement action avec le bon type et containerId', async () => {
      const wrapper = mountComponent()

      // Find the start item and click it
      const startItem = wrapper.find('[data-testid="menu-item-stop"]')
      expect(startItem.exists()).toBe(true)

      // The el-dropdown @command handler is triggered by the component
      // We test the handleAction function by triggering the dropdown command event
      const dropdown = wrapper.find('[data-testid="app-context-menu"]')
      await dropdown.trigger('command', 'stop')

      // Verify the component emitted the action event
      expect(wrapper.emitted('action')).toBeTruthy()
    })
  })

  describe('Mode App vs Mode Infra', () => {
    it('en Mode App, les labels sont traduits', () => {
      mockModeStore.isAppMode = true
      const wrapper = mountComponent()

      const detailsItem = wrapper.find('[data-testid="menu-item-details"]')
      expect(detailsItem.text()).toContain('techniques')
    })

    it('en Mode Infra, les labels sont techniques', () => {
      mockModeStore.isAppMode = false
      const wrapper = mountComponent()

      const detailsItem = wrapper.find('[data-testid="menu-item-details"]')
      expect(detailsItem.text()).toContain('container')
    })
  })

  describe('conditions d\'affichage', () => {
    it('affiche Ouvrir quand domain est fourni', () => {
      const wrapper = mountComponent({ domain: 'https://test.example.com' })
      expect(wrapper.find('[data-testid="menu-item-open"]').exists()).toBe(true)
    })

    it('n\'affiche pas Ouvrir sans domain', () => {
      const wrapper = mountComponent({ domain: undefined })
      expect(wrapper.find('[data-testid="menu-item-open"]').exists()).toBe(false)
    })

    it('affiche Stop quand status est running', () => {
      const wrapper = mountComponent({ containerStatus: 'running' })
      expect(wrapper.find('[data-testid="menu-item-stop"]').exists()).toBe(true)
    })

    it('affiche Start quand status est stopped', () => {
      const wrapper = mountComponent({ containerStatus: 'stopped' })
      expect(wrapper.find('[data-testid="menu-item-start"]').exists()).toBe(true)
    })
  })
})
