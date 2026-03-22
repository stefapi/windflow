import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import PluginWidgetZone from '@/components/dashboard/PluginWidgetZone.vue'
import { usePluginWidgetStore } from '@/stores/pluginWidget'
import { defineComponent } from 'vue'

// Create a dummy widget component for testing
const DummyWidget = defineComponent({
  name: 'DummyWidget',
  props: {
    message: {
      type: String,
      default: '',
    },
  },
  template: '<div class="dummy-widget">Dummy Widget Content</div>',
})

describe('PluginWidgetZone', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('rendering', () => {
    it('should not render when no widgets are registered', () => {
      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot name="header" /><slot /></div>' },
          },
        },
      })

      expect(wrapper.find('[data-testid="plugin-widget-zone"]').exists()).toBe(false)
    })

    it('should render when widgets are registered', () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot name="header" /><slot /></div>' },
          },
        },
      })

      expect(wrapper.find('[data-testid="plugin-widget-zone"]').exists()).toBe(true)
    })

    it('should display section title', () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot /></div>' },
          },
        },
      })

      expect(wrapper.text()).toContain('Plugin Widgets')
    })

    it('should render widget with title in card header', () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
          title: 'My Custom Widget',
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': {
              template: `
                <div class="el-card">
                  <div v-if="$slots.header" class="el-card__header"><slot name="header" /></div>
                  <slot />
                </div>
              `,
            },
          },
        },
      })

      expect(wrapper.text()).toContain('My Custom Widget')
    })

    it('should render multiple widgets', () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-2',
          component: DummyWidget,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot /></div>' },
          },
        },
      })

      const cards = wrapper.findAll('.el-card')
      expect(cards.length).toBe(2)
    })

    it('should render widgets in order', () => {
      const WidgetA = defineComponent({
        name: 'WidgetA',
        template: '<div class="widget-a">Widget A</div>',
      })
      const WidgetB = defineComponent({
        name: 'WidgetB',
        template: '<div class="widget-b">Widget B</div>',
      })

      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-b',
          component: WidgetB,
          order: 100,
        },
      })
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-a',
          component: WidgetA,
          order: 10,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot /></div>' },
          },
        },
      })

      const cards = wrapper.findAll('.el-card')
      expect(cards[0].text()).toContain('Widget A')
      expect(cards[1].text()).toContain('Widget B')
    })
  })

  describe('data-testid', () => {
    it('should have data-testid for each widget', () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'my-widget',
          component: DummyWidget,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': {
              template: '<div :data-testid="dataTestid" class="el-card"><slot /></div>',
              props: ['dataTestid'],
            },
          },
        },
      })

      expect(wrapper.find('[data-testid="plugin-widget-my-widget"]').exists()).toBe(true)
    })
  })

  describe('grid layout', () => {
    it('should have grid class', () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot /></div>' },
          },
        },
      })

      expect(wrapper.find('.plugin-widget-zone__grid').exists()).toBe(true)
    })
  })

  describe('reactivity', () => {
    it('should update when widget is registered after mount', async () => {
      const store = usePluginWidgetStore()

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot /></div>' },
          },
        },
      })

      expect(wrapper.find('[data-testid="plugin-widget-zone"]').exists()).toBe(false)

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.find('[data-testid="plugin-widget-zone"]').exists()).toBe(true)
    })

    it('should update when widget is unregistered after mount', async () => {
      const store = usePluginWidgetStore()
      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      const wrapper = mount(PluginWidgetZone, {
        global: {
          stubs: {
            'el-icon': { template: '<i><slot /></i>' },
            'el-card': { template: '<div class="el-card"><slot /></div>' },
          },
        },
      })

      expect(wrapper.find('[data-testid="plugin-widget-zone"]').exists()).toBe(true)

      store.unregisterWidget('widget-1')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('[data-testid="plugin-widget-zone"]').exists()).toBe(false)
    })
  })
})
