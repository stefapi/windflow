/**
 * Plugin Navigation Store
 * Manages dynamic navigation entries from plugins
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { PluginNavSection, PluginNavItem, PluginNavRegistration } from '@/types/navigation'

export const usePluginNavStore = defineStore('pluginNav', () => {
  // State
  const pluginSections = ref<PluginNavSection[]>([])
  const registeredPlugins = ref<Map<string, PluginNavRegistration>>(new Map())

  // Getters
  /**
   * Check if any plugin has registered UI pages
   */
  const hasPluginPages = computed(() => pluginSections.value.length > 0)

  /**
   * Get all plugin navigation sections
   */
  const sections = computed(() => pluginSections.value)

  /**
   * Get plugin IDs that have registered pages
   */
  const activePluginIds = computed(() =>
    Array.from(registeredPlugins.value.keys())
  )

  // Actions
  /**
   * Register plugin navigation pages
   * Called by plugins when they want to add pages to the sidebar
   */
  function registerPlugin(registration: PluginNavRegistration): void {
    // Check if plugin is already registered
    if (registeredPlugins.value.has(registration.pluginId)) {
      console.warn(`Plugin ${registration.pluginId} is already registered. Unregister first to update.`)
      return
    }

    // Store the registration
    registeredPlugins.value.set(registration.pluginId, registration)

    // Add sections to the sidebar
    for (const section of registration.sections) {
      pluginSections.value.push(section)
    }

    console.log(`Plugin ${registration.pluginId} registered ${registration.sections.length} navigation section(s)`)
  }

  /**
   * Unregister plugin navigation pages
   * Called when a plugin is disabled/uninstalled
   */
  function unregisterPlugin(pluginId: string): void {
    const registration = registeredPlugins.value.get(pluginId)
    if (!registration) {
      console.warn(`Plugin ${pluginId} is not registered`)
      return
    }

    // Remove sections from this plugin
    pluginSections.value = pluginSections.value.filter(
      section => section.pluginId !== pluginId
    )

    // Remove registration
    registeredPlugins.value.delete(pluginId)

    console.log(`Plugin ${pluginId} unregistered from navigation`)
  }

  /**
   * Update a plugin's navigation sections
   * Replaces existing sections with new ones
   */
  function updatePlugin(registration: PluginNavRegistration): void {
    // Remove existing registration
    unregisterPlugin(registration.pluginId)
    // Register new one
    registerPlugin(registration)
  }

  /**
   * Get all navigation items from a specific plugin
   */
  function getPluginItems(pluginId: string): PluginNavItem[] {
    const items: PluginNavItem[] = []
    for (const section of pluginSections.value) {
      if (section.pluginId === pluginId) {
        items.push(...section.items)
      }
    }
    return items
  }

  /**
   * Check if a specific plugin has registered pages
   */
  function hasPlugin(pluginId: string): boolean {
    return registeredPlugins.value.has(pluginId)
  }

  /**
   * Clear all plugin registrations
   * Useful for testing or reset
   */
  function clearAll(): void {
    pluginSections.value = []
    registeredPlugins.value.clear()
  }

  return {
    // State
    pluginSections,
    registeredPlugins,
    // Getters
    hasPluginPages,
    sections,
    activePluginIds,
    // Actions
    registerPlugin,
    unregisterPlugin,
    updatePlugin,
    getPluginItems,
    hasPlugin,
    clearAll,
  }
})
