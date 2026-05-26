/**
 * Tests unitaires pour le store modeStore
 * STORY-002 : Refonte Sidebar — Navigation Mode App
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useModeStore } from '@/stores/mode'

describe('modeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('initialisation', () => {
    it('initialise en mode App par défaut', () => {
      const store = useModeStore()
      expect(store.mode).toBe('app')
      expect(store.isAppMode).toBe(true)
      expect(store.isInfraMode).toBe(false)
    })

    it('restaure le mode depuis localStorage', () => {
      localStorage.setItem('windflow-ui-mode', 'infra')
      // Re-create pinia to trigger getInitialMode
      setActivePinia(createPinia())
      const store = useModeStore()
      expect(store.mode).toBe('infra')
      expect(store.isInfraMode).toBe(true)
      expect(store.isAppMode).toBe(false)
    })

    it('ignore les valeurs invalides dans localStorage et utilise app', () => {
      localStorage.setItem('windflow-ui-mode', 'invalid')
      setActivePinia(createPinia())
      const store = useModeStore()
      expect(store.mode).toBe('app')
    })
  })

  describe('persistance', () => {
    it('persiste le mode dans localStorage au changement', () => {
      const store = useModeStore()
      store.setMode('infra')
      expect(localStorage.getItem('windflow-ui-mode')).toBe('infra')
    })

    it('persiste le mode app dans localStorage', () => {
      const store = useModeStore()
      store.setMode('infra')
      store.setMode('app')
      expect(localStorage.getItem('windflow-ui-mode')).toBe('app')
    })
  })

  describe('setMode', () => {
    it('change le mode de app à infra', () => {
      const store = useModeStore()
      store.setMode('infra')
      expect(store.mode).toBe('infra')
    })

    it('ne fait rien si mode identique', () => {
      const store = useModeStore()
      const initialMode = store.mode
      store.setMode('app') // déjà 'app'
      expect(store.mode).toBe(initialMode)
    })
  })

  describe('toggleMode', () => {
    it('bascule de app à infra', () => {
      const store = useModeStore()
      expect(store.mode).toBe('app')
      store.toggleMode()
      expect(store.mode).toBe('infra')
    })

    it('bascule de infra à app', () => {
      const store = useModeStore()
      store.setMode('infra')
      store.toggleMode()
      expect(store.mode).toBe('app')
    })
  })

  describe('computed', () => {
    it('isAppMode retourne true en mode app', () => {
      const store = useModeStore()
      expect(store.isAppMode).toBe(true)
    })

    it('isAppMode retourne false en mode infra', () => {
      const store = useModeStore()
      store.setMode('infra')
      expect(store.isAppMode).toBe(false)
    })

    it('isInfraMode retourne true en mode infra', () => {
      const store = useModeStore()
      store.setMode('infra')
      expect(store.isInfraMode).toBe(true)
    })

    it('isInfraMode retourne false en mode app', () => {
      const store = useModeStore()
      expect(store.isInfraMode).toBe(false)
    })
  })
})
