/**
 * Theme Store
 * STORY-421: Dark Theme Palette
 *
 * Manages application theme (dark/light) with localStorage persistence
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'windflow-theme'

/**
 * Get initial theme from localStorage or system preference
 */
function getInitialTheme(): Theme {
  // Check localStorage first
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') {
    return stored
  }

  // Check system preference
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light'
  }

  // Default to dark
  return 'dark'
}

/**
 * Apply theme to document
 */
function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme)

  // Also set color-scheme for native elements
  document.documentElement.style.colorScheme = theme
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>(getInitialTheme())

  // Apply initial theme
  applyTheme(theme.value)

  // Watch for changes and persist
  watch(theme, (newTheme) => {
    applyTheme(newTheme)
    localStorage.setItem(STORAGE_KEY, newTheme)
  })

  /**
   * Toggle between dark and light theme
   */
  function toggleTheme(): void {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  /**
   * Set specific theme
   */
  function setTheme(newTheme: Theme): void {
    theme.value = newTheme
  }

  /**
   * Check if current theme is dark
   */
  function isDark(): boolean {
    return theme.value === 'dark'
  }

  /**
   * Check if current theme is light
   */
  function isLight(): boolean {
    return theme.value === 'light'
  }

  return {
    theme,
    toggleTheme,
    setTheme,
    isDark,
    isLight
  }
})
