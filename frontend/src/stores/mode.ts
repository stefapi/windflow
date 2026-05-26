/**
 * Mode Store
 * EPIC-010: Mode App — Navigation & UX Simplifiée
 *
 * Manages the UI mode (App/Infra) with localStorage persistence.
 * Default mode is 'app' (simplified, non-technical vocabulary).
 */

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

export type UIMode = 'app' | 'infra'

const STORAGE_KEY = 'windflow-ui-mode'

/**
 * Get initial mode from localStorage, defaulting to 'app'.
 */
function getInitialMode(): UIMode {
  if (typeof localStorage === 'undefined') return 'app'
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'app' || stored === 'infra') {
    return stored
  }
  return 'app'
}

export const useModeStore = defineStore('mode', () => {
  const mode = ref<UIMode>(getInitialMode())

  // Watch for changes and persist to localStorage (sync flush for immediate persistence)
  watch(mode, (newMode) => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newMode)
    }
  }, { flush: 'sync' })

  /**
   * Whether the current mode is App (simplified UI)
   */
  const isAppMode = computed(() => mode.value === 'app')

  /**
   * Whether the current mode is Infra (technical UI)
   */
  const isInfraMode = computed(() => mode.value === 'infra')

  /**
   * Set the UI mode explicitly.
   * No-op if the mode is already the same.
   */
  function setMode(newMode: UIMode): void {
    if (mode.value === newMode) return
    mode.value = newMode
  }

  /**
   * Toggle between App and Infra modes.
   */
  function toggleMode(): void {
    mode.value = mode.value === 'app' ? 'infra' : 'app'
  }

  return {
    mode,
    isAppMode,
    isInfraMode,
    setMode,
    toggleMode,
  }
})
