/**
 * Plugin Widget Store
 * Manages dynamic dashboard widgets from plugins
 */

import { defineStore } from 'pinia'
import { ref, computed, markRaw } from 'vue'
import type { Component } from 'vue'

/**
 * Represents a widget registered by a plugin
 */
export interface PluginWidget {
  /** Unique identifier for this widget instance */
  id: string
  /** ID of the plugin that registered this widget */
  pluginId: string
  /** Vue component to render */
  component: Component
  /** Props to pass to the component */
  props?: Record<string, unknown>
  /** Order priority (lower = appears first) */
  order?: number
  /** Widget title for header */
  title?: string
}

/**
 * Registration payload for a single widget
 */
export interface PluginWidgetRegistration {
  pluginId: string
  widget: Omit<PluginWidget, 'pluginId'>
}

export const usePluginWidgetStore = defineStore('pluginWidget', () => {
  // State
  const widgets = ref<Map<string, PluginWidget>>(new Map())

  // Getters
  /**
   * Check if any widget is registered
   */
  const hasWidgets = computed(() => widgets.value.size > 0)

  /**
   * Get widget count
   */
  const widgetCount = computed(() => widgets.value.size)

  /**
   * Get all widgets sorted by order
   */
  const sortedWidgets = computed(() => {
    return Array.from(widgets.value.values()).sort((a, b) => {
      const orderA = a.order ?? 100
      const orderB = b.order ?? 100
      return orderA - orderB
    })
  })

  /**
   * Get widget IDs grouped by plugin
   */
  const pluginWidgetIds = computed(() => {
    const grouped = new Map<string, string[]>()
    for (const widget of widgets.value.values()) {
      const existing = grouped.get(widget.pluginId) ?? []
      existing.push(widget.id)
      grouped.set(widget.pluginId, existing)
    }
    return grouped
  })

  // Actions
  /**
   * Register a widget from a plugin
   * @param registration - Widget registration payload
   */
  function registerWidget(registration: PluginWidgetRegistration): void {
    const { pluginId, widget } = registration
    const widgetId = widget.id

    // Check for duplicate
    if (widgets.value.has(widgetId)) {
      console.warn(`Widget ${widgetId} is already registered. Unregister first to update.`)
      return
    }

    // Store the widget (markRaw on component to prevent Vue reactive proxy overhead)
    const fullWidget: PluginWidget = {
      ...widget,
      component: markRaw(widget.component),
      pluginId,
    }

    widgets.value.set(widgetId, fullWidget)
    console.log(`Widget ${widgetId} registered by plugin ${pluginId}`)
  }

  /**
   * Unregister a specific widget
   * @param widgetId - Widget ID to unregister
   */
  function unregisterWidget(widgetId: string): void {
    if (!widgets.value.has(widgetId)) {
      console.warn(`Widget ${widgetId} is not registered`)
      return
    }

    widgets.value.delete(widgetId)
    console.log(`Widget ${widgetId} unregistered`)
  }

  /**
   * Unregister all widgets from a plugin
   * @param pluginId - Plugin ID to unregister all widgets for
   */
  function unregisterPlugin(pluginId: string): void {
    const widgetIds = pluginWidgetIds.value.get(pluginId) ?? []

    if (widgetIds.length === 0) {
      console.warn(`Plugin ${pluginId} has no registered widgets`)
      return
    }

    for (const widgetId of widgetIds) {
      widgets.value.delete(widgetId)
    }

    console.log(`Unregistered ${widgetIds.length} widget(s) from plugin ${pluginId}`)
  }

  /**
   * Update a widget's props
   * @param widgetId - Widget ID to update
   * @param props - New props to merge
   */
  function updateWidgetProps(widgetId: string, props: Record<string, unknown>): void {
    const widget = widgets.value.get(widgetId)
    if (!widget) {
      console.warn(`Widget ${widgetId} is not registered`)
      return
    }

    widget.props = { ...widget.props, ...props }
    console.log(`Widget ${widgetId} props updated`)
  }

  /**
   * Get widgets by plugin ID
   * @param pluginId - Plugin ID to filter by
   */
  function getWidgetsByPlugin(pluginId: string): PluginWidget[] {
    return Array.from(widgets.value.values()).filter(w => w.pluginId === pluginId)
  }

  /**
   * Check if a specific widget is registered
   * @param widgetId - Widget ID to check
   */
  function hasWidget(widgetId: string): boolean {
    return widgets.value.has(widgetId)
  }

  /**
   * Clear all registered widgets
   * Useful for testing or reset
   */
  function clearAll(): void {
    widgets.value.clear()
    console.log('All widgets cleared')
  }

  return {
    // State
    widgets,
    // Getters
    hasWidgets,
    widgetCount,
    sortedWidgets,
    pluginWidgetIds,
    // Actions
    registerWidget,
    unregisterWidget,
    unregisterPlugin,
    updateWidgetProps,
    getWidgetsByPlugin,
    hasWidget,
    clearAll,
  }
})
