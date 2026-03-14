/**
 * Navigation Types
 * Types for sidebar navigation structure
 */

import type { Component } from 'vue'

/**
 * Single navigation item
 */
export interface NavItem {
  /** Icon component from Element Plus */
  icon: Component
  /** Display label */
  label: string
  /** Router path */
  path: string
  /** Optional badge (string or number) */
  badge?: string | number
  /** Whether this item requires advanced mode */
  advancedOnly?: boolean
}

/**
 * Navigation section with optional title
 */
export interface NavSection {
  /** Section title (uppercase, grayed out) - undefined for no title */
  title?: string
  /** Navigation items in this section */
  items: NavItem[]
}

/**
 * Plugin navigation item (extends NavItem with plugin metadata)
 */
export interface PluginNavItem extends NavItem {
  /** ID of the plugin that registered this item */
  pluginId: string
  /** Optional plugin icon URL */
  pluginIcon?: string
}

/**
 * Plugin navigation section
 */
export interface PluginNavSection {
  /** Section title for plugin pages */
  title: string
  /** Plugin ID */
  pluginId: string
  /** Navigation items from this plugin */
  items: PluginNavItem[]
}

/**
 * Plugin registration payload
 */
export interface PluginNavRegistration {
  /** Plugin ID */
  pluginId: string
  /** Plugin display name */
  pluginName: string
  /** Navigation sections to add */
  sections: PluginNavSection[]
}
