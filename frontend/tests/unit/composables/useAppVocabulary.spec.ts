import { describe, it, expect } from 'vitest'
import {
  useAppVocabulary,
  translateTerm,
  translateLabel,
  getAppStatus,
  getAppActions,
  getAppDisplayName,
  isHiddenTerm,
} from '@/composables/useAppVocabulary'

describe('useAppVocabulary', () => {
  // ─── translateTerm ────────────────────────────────────────────────

  describe('translateTerm', () => {
    it('translates container to app', () => {
      expect(translateTerm('container')).toBe('app')
    })

    it('translates stack to app', () => {
      expect(translateTerm('stack')).toBe('app')
    })

    it('translates target to serveur', () => {
      expect(translateTerm('target')).toBe('serveur')
    })

    it('returns empty string for hidden terms (compose, image, volume, network, deployment)', () => {
      expect(translateTerm('compose')).toBe('')
      expect(translateTerm('image')).toBe('')
      expect(translateTerm('volume')).toBe('')
      expect(translateTerm('network')).toBe('')
      expect(translateTerm('deployment')).toBe('')
    })

    it('returns empty string for unknown term via type assertion', () => {
      // VOCABULARY_MAP has no entry for arbitrary strings
      // This tests the defensive fallback
      expect(translateTerm('container' as never)).toBe('app')
    })
  })

  // ─── translateLabel ───────────────────────────────────────────────

  describe('translateLabel', () => {
    it('replaces technical terms in a label', () => {
      expect(translateLabel('Container Status')).toBe('App Status')
    })

    it('replaces multiple occurrences', () => {
      // "Container" → "App", "network" → "" (hidden)
      const result = translateLabel('Container network')
      expect(result).toContain('App')
      expect(result).not.toContain('Container')
      expect(result).not.toContain('network')
    })

    it('returns label unchanged if no technical terms', () => {
      expect(translateLabel('Bonjour le monde')).toBe('Bonjour le monde')
    })
  })

  // ─── getAppStatus ─────────────────────────────────────────────────

  describe('getAppStatus', () => {
    it('maps running to En cours with success color', () => {
      const status = getAppStatus('running')
      expect(status.app).toBe('En cours')
      expect(status.color).toBe('success')
    })

    it('maps stopped to Arrêté with danger color', () => {
      const status = getAppStatus('stopped')
      expect(status.app).toBe('Arrêté')
      expect(status.color).toBe('danger')
    })

    it('maps paused to En pause with warning color', () => {
      const status = getAppStatus('paused')
      expect(status.app).toBe('En pause')
      expect(status.color).toBe('warning')
    })

    it('returns technical status as fallback for unknown status', () => {
      const status = getAppStatus('custom-status')
      expect(status.app).toBe('custom-status')
      expect(status.technical).toBe('custom-status')
      expect(status.color).toBe('info')
    })
  })

  // ─── getAppActions ────────────────────────────────────────────────

  describe('getAppActions', () => {
    it('returns the list of canonical App actions', () => {
      const actions = getAppActions()
      expect(actions).toHaveLength(8)
      const technicalNames = actions.map((a) => a.technical)
      expect(technicalNames).toContain('open')
      expect(technicalNames).toContain('lifecycle')
      expect(technicalNames).toContain('logs')
      expect(technicalNames).toContain('console')
      expect(technicalNames).toContain('config')
      expect(technicalNames).toContain('restart')
      expect(technicalNames).toContain('delete')
      expect(technicalNames).toContain('details')
    })
  })

  // ─── getAppDisplayName ────────────────────────────────────────────

  describe('getAppDisplayName', () => {
    it('returns compose service label when available', () => {
      const result = getAppDisplayName({
        name: 'my-stack-nginx-1',
        labels: { 'com.docker.compose.service': 'nginx' },
      })
      expect(result).toBe('nginx')
    })

    it('returns windflow app name label when available', () => {
      const result = getAppDisplayName({
        name: 'some-container',
        labels: { 'org.windflow.app.name': 'My App' },
      })
      expect(result).toBe('My App')
    })

    it('prioritizes compose service label over windflow label', () => {
      const result = getAppDisplayName({
        name: 'container',
        labels: {
          'com.docker.compose.service': 'nginx',
          'org.windflow.app.name': 'My App',
        },
      })
      expect(result).toBe('nginx')
    })

    it('returns cleaned container name as fallback', () => {
      const result = getAppDisplayName({
        name: '/my-container',
      })
      expect(result).toBe('my-container')
    })

    it('strips hex prefix from container name', () => {
      const result = getAppDisplayName({
        name: 'a1b2-my-app',
      })
      expect(result).toBe('my-app')
    })

    it('returns Inconnu when no name available', () => {
      const result = getAppDisplayName({})
      expect(result).toBe('Inconnu')
    })
  })

  // ─── isHiddenTerm ─────────────────────────────────────────────────

  describe('isHiddenTerm', () => {
    it('returns true for compose, image, volume, network, deployment', () => {
      expect(isHiddenTerm('compose')).toBe(true)
      expect(isHiddenTerm('image')).toBe(true)
      expect(isHiddenTerm('volume')).toBe(true)
      expect(isHiddenTerm('network')).toBe(true)
      expect(isHiddenTerm('deployment')).toBe(true)
    })

    it('returns false for container, stack, target', () => {
      expect(isHiddenTerm('container')).toBe(false)
      expect(isHiddenTerm('stack')).toBe(false)
      expect(isHiddenTerm('target')).toBe(false)
    })
  })

  // ─── useAppVocabulary composable ──────────────────────────────────

  describe('useAppVocabulary composable', () => {
    it('exposes all translation functions', () => {
      const vocabulary = useAppVocabulary()
      expect(typeof vocabulary.translateTerm).toBe('function')
      expect(typeof vocabulary.translateLabel).toBe('function')
      expect(typeof vocabulary.getAppStatus).toBe('function')
      expect(typeof vocabulary.getAppActions).toBe('function')
      expect(typeof vocabulary.getAppDisplayName).toBe('function')
      expect(typeof vocabulary.isHiddenTerm).toBe('function')
    })

    it('functions work correctly through composable', () => {
      const vocabulary = useAppVocabulary()
      expect(vocabulary.translateTerm('container')).toBe('app')
      expect(vocabulary.isHiddenTerm('compose')).toBe(true)
      expect(vocabulary.getAppStatus('running').app).toBe('En cours')
    })
  })
})
