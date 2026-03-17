import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePluginWidgetStore } from '@/stores/pluginWidget'
import { defineComponent } from 'vue'

// Create a dummy component for testing
const DummyWidget = defineComponent({
  template: '<div>Dummy Widget</div>',
})

describe('pluginWidgetStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('initial state', () => {
    it('should start with no widgets', () => {
      const store = usePluginWidgetStore()

      expect(store.hasWidgets).toBe(false)
      expect(store.widgetCount).toBe(0)
      expect(store.sortedWidgets).toEqual([])
    })
  })

  describe('registerWidget', () => {
    it('should register a widget', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      expect(store.hasWidgets).toBe(true)
      expect(store.widgetCount).toBe(1)
      expect(store.hasWidget('widget-1')).toBe(true)
    })

    it('should register widget with props and title', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
          title: 'My Widget',
          props: { foo: 'bar' },
        },
      })

      const widget = store.sortedWidgets[0]
      expect(widget.title).toBe('My Widget')
      expect(widget.props).toEqual({ foo: 'bar' })
    })

    it('should not register duplicate widget', () => {
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
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      expect(store.widgetCount).toBe(1)
    })

    it('should warn when registering duplicate widget', () => {
      const store = usePluginWidgetStore()
      const warnSpy = vi.spyOn(console, 'warn')

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
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      expect(warnSpy).toHaveBeenCalledWith(
        'Widget widget-1 is already registered. Unregister first to update.'
      )
    })
  })

  describe('unregisterWidget', () => {
    it('should unregister a widget', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      store.unregisterWidget('widget-1')

      expect(store.hasWidgets).toBe(false)
      expect(store.hasWidget('widget-1')).toBe(false)
    })

    it('should warn when unregistering non-existent widget', () => {
      const store = usePluginWidgetStore()
      const warnSpy = vi.spyOn(console, 'warn')

      store.unregisterWidget('non-existent')

      expect(warnSpy).toHaveBeenCalledWith('Widget non-existent is not registered')
    })
  })

  describe('unregisterPlugin', () => {
    it('should unregister all widgets from a plugin', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'plugin-a',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      store.registerWidget({
        pluginId: 'plugin-a',
        widget: {
          id: 'widget-2',
          component: DummyWidget,
        },
      })

      store.registerWidget({
        pluginId: 'plugin-b',
        widget: {
          id: 'widget-3',
          component: DummyWidget,
        },
      })

      store.unregisterPlugin('plugin-a')

      expect(store.widgetCount).toBe(1)
      expect(store.hasWidget('widget-1')).toBe(false)
      expect(store.hasWidget('widget-2')).toBe(false)
      expect(store.hasWidget('widget-3')).toBe(true)
    })

    it('should warn when plugin has no widgets', () => {
      const store = usePluginWidgetStore()
      const warnSpy = vi.spyOn(console, 'warn')

      store.unregisterPlugin('non-existent-plugin')

      expect(warnSpy).toHaveBeenCalledWith('Plugin non-existent-plugin has no registered widgets')
    })
  })

  describe('sortedWidgets', () => {
    it('should sort widgets by order', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
          order: 100,
        },
      })

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-2',
          component: DummyWidget,
          order: 10,
        },
      })

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-3',
          component: DummyWidget,
          order: 50,
        },
      })

      const sorted = store.sortedWidgets
      expect(sorted[0].id).toBe('widget-2') // order: 10
      expect(sorted[1].id).toBe('widget-3') // order: 50
      expect(sorted[2].id).toBe('widget-1') // order: 100
    })

    it('should use default order of 100 when not specified', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
          order: 50,
        },
      })

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-2',
          component: DummyWidget,
          // no order specified
        },
      })

      const sorted = store.sortedWidgets
      expect(sorted[0].id).toBe('widget-1') // order: 50
      expect(sorted[1].id).toBe('widget-2') // order: 100 (default)
    })
  })

  describe('updateWidgetProps', () => {
    it('should update widget props', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'test-plugin',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
          props: { foo: 'bar' },
        },
      })

      store.updateWidgetProps('widget-1', { baz: 'qux' })

      const widget = store.sortedWidgets[0]
      expect(widget.props).toEqual({ foo: 'bar', baz: 'qux' })
    })

    it('should warn when updating non-existent widget', () => {
      const store = usePluginWidgetStore()
      const warnSpy = vi.spyOn(console, 'warn')

      store.updateWidgetProps('non-existent', { foo: 'bar' })

      expect(warnSpy).toHaveBeenCalledWith('Widget non-existent is not registered')
    })
  })

  describe('getWidgetsByPlugin', () => {
    it('should return widgets for a specific plugin', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'plugin-a',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      store.registerWidget({
        pluginId: 'plugin-b',
        widget: {
          id: 'widget-2',
          component: DummyWidget,
        },
      })

      store.registerWidget({
        pluginId: 'plugin-a',
        widget: {
          id: 'widget-3',
          component: DummyWidget,
        },
      })

      const pluginAWidgets = store.getWidgetsByPlugin('plugin-a')
      expect(pluginAWidgets.length).toBe(2)
      expect(pluginAWidgets.map((w) => w.id)).toContain('widget-1')
      expect(pluginAWidgets.map((w) => w.id)).toContain('widget-3')
    })

    it('should return empty array for non-existent plugin', () => {
      const store = usePluginWidgetStore()

      const widgets = store.getWidgetsByPlugin('non-existent')
      expect(widgets).toEqual([])
    })
  })

  describe('clearAll', () => {
    it('should clear all widgets', () => {
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

      store.clearAll()

      expect(store.hasWidgets).toBe(false)
      expect(store.widgetCount).toBe(0)
    })
  })

  describe('pluginWidgetIds', () => {
    it('should group widget IDs by plugin', () => {
      const store = usePluginWidgetStore()

      store.registerWidget({
        pluginId: 'plugin-a',
        widget: {
          id: 'widget-1',
          component: DummyWidget,
        },
      })

      store.registerWidget({
        pluginId: 'plugin-a',
        widget: {
          id: 'widget-2',
          component: DummyWidget,
        },
      })

      store.registerWidget({
        pluginId: 'plugin-b',
        widget: {
          id: 'widget-3',
          component: DummyWidget,
        },
      })

      const grouped = store.pluginWidgetIds
      expect(grouped.get('plugin-a')).toEqual(['widget-1', 'widget-2'])
      expect(grouped.get('plugin-b')).toEqual(['widget-3'])
    })
  })
})
