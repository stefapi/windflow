/**
 * Tests unitaires pour useAppContextMenu composable
 * STORY-003 : Menu Contextuel `[⋯ Plus]` Canonique
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppContextMenu, getContextMenuActions, isDangerousAction } from '@/composables/useAppContextMenu'
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

/**
 * Helper to create default props for the composable.
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

describe('useAppContextMenu', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockModeStore.mode = 'app'
    mockModeStore.isAppMode = true
    mockModeStore.isInfraMode = false
  })

  describe('structure canonique', () => {
    it('retourne 3 sections (primary, tools, advanced)', () => {
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      expect(sections.value).toHaveLength(3)
      expect(sections.value[0]!.key).toBe('primary')
      expect(sections.value[1]!.key).toBe('tools')
      expect(sections.value[2]!.key).toBe('advanced')
    })

    it('chaque section a un label', () => {
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      for (const section of sections.value) {
        expect(section.label).toBeTruthy()
      }
    })
  })

  describe('section primary', () => {
    it('contient Ouvrir quand domain est fourni', () => {
      const props = createProps({ domain: 'https://test.example.com' })
      const { sections } = useAppContextMenu(props)

      const primary = sections.value.find((s) => s.key === 'primary')!
      const openItem = primary.items.find((i) => i.action === 'open')
      expect(openItem).toBeDefined()
      expect(openItem!.label).toBe('Ouvrir')
    })

    it('ne contient pas Ouvrir sans domain', () => {
      const props = createProps({ domain: undefined })
      const { sections } = useAppContextMenu(props)

      const primary = sections.value.find((s) => s.key === 'primary')!
      const openItem = primary.items.find((i) => i.action === 'open')
      expect(openItem).toBeUndefined()
    })

    it('contient Stop quand status est running', () => {
      const props = createProps({ containerStatus: 'running' })
      const { sections } = useAppContextMenu(props)

      const primary = sections.value.find((s) => s.key === 'primary')!
      const stopItem = primary.items.find((i) => i.action === 'stop')
      expect(stopItem).toBeDefined()
      expect(stopItem!.label).toBe('Arrêter')
    })

    it('contient Start quand status est stopped', () => {
      const props = createProps({ containerStatus: 'stopped' })
      const { sections } = useAppContextMenu(props)

      const primary = sections.value.find((s) => s.key === 'primary')!
      const startItem = primary.items.find((i) => i.action === 'start')
      expect(startItem).toBeDefined()
      expect(startItem!.label).toBe('Démarrer')
    })

    it('contient Restart quand status est running', () => {
      const props = createProps({ containerStatus: 'running' })
      const { sections } = useAppContextMenu(props)

      const primary = sections.value.find((s) => s.key === 'primary')!
      const restartItem = primary.items.find((i) => i.action === 'restart')
      expect(restartItem).toBeDefined()
      expect(restartItem!.label).toBe('Redémarrer')
    })

    it('ne contient pas Restart quand status est stopped', () => {
      const props = createProps({ containerStatus: 'stopped' })
      const { sections } = useAppContextMenu(props)

      const primary = sections.value.find((s) => s.key === 'primary')!
      const restartItem = primary.items.find((i) => i.action === 'restart')
      expect(restartItem).toBeUndefined()
    })
  })

  describe('section tools', () => {
    it('contient Logs, Console, Config', () => {
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      const tools = sections.value.find((s) => s.key === 'tools')!
      const actions = tools.items.map((i) => i.action)
      expect(actions).toContain('logs')
      expect(actions).toContain('console')
      expect(actions).toContain('config')
    })
  })

  describe('section advanced', () => {
    it('contient Détails techniques et Supprimer', () => {
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      const advanced = sections.value.find((s) => s.key === 'advanced')!
      const actions = advanced.items.map((i) => i.action)
      expect(actions).toContain('details')
      expect(actions).toContain('delete')
    })

    it('Supprimer est marqué danger=true', () => {
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      const advanced = sections.value.find((s) => s.key === 'advanced')!
      const deleteItem = advanced.items.find((i) => i.action === 'delete')!
      expect(deleteItem.danger).toBe(true)
    })
  })

  describe('Mode App vs Mode Infra', () => {
    it('en Mode App, les labels utilisent le vocabulaire non-technique', () => {
      mockModeStore.isAppMode = true
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      const advanced = sections.value.find((s) => s.key === 'advanced')!
      const detailsItem = advanced.items.find((i) => i.action === 'details')!
      expect(detailsItem.label).toBe('Détails techniques')
    })

    it('en Mode App, la section Avancé utilise le vocabulaire technique', () => {
      mockModeStore.isAppMode = true
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      const advanced = sections.value.find((s) => s.key === 'advanced')!
      // In Mode App, "details" label is "Détails techniques" (controlled leak)
      const detailsItem = advanced.items.find((i) => i.action === 'details')!
      expect(detailsItem.label).toContain('techniques')
    })

    it('en Mode Infra, les labels utilisent le vocabulaire technique', () => {
      mockModeStore.isAppMode = false
      const props = createProps()
      const { sections } = useAppContextMenu(props)

      const advanced = sections.value.find((s) => s.key === 'advanced')!
      const detailsItem = advanced.items.find((i) => i.action === 'details')!
      expect(detailsItem.label).toBe('Inspecter le container')
    })
  })

  describe('isMenuVisible', () => {
    it('retourne true quand des actions sont disponibles', () => {
      const props = createProps()
      const { isMenuVisible } = useAppContextMenu(props)
      expect(isMenuVisible.value).toBe(true)
    })
  })

  describe('getActionHandler', () => {
    it('retourne une fonction pour chaque action', () => {
      const props = createProps()
      const { getActionHandler } = useAppContextMenu(props)

      const handler = getActionHandler('start')
      expect(typeof handler).toBe('function')
    })
  })
})

describe('getContextMenuActions', () => {
  it('retourne toutes les actions possibles', () => {
    const actions = getContextMenuActions()
    expect(actions).toContain('open')
    expect(actions).toContain('start')
    expect(actions).toContain('stop')
    expect(actions).toContain('restart')
    expect(actions).toContain('logs')
    expect(actions).toContain('console')
    expect(actions).toContain('config')
    expect(actions).toContain('details')
    expect(actions).toContain('delete')
  })
})

describe('isDangerousAction', () => {
  it('retourne true pour delete', () => {
    expect(isDangerousAction('delete')).toBe(true)
  })

  it('retourne false pour les autres actions', () => {
    expect(isDangerousAction('start')).toBe(false)
    expect(isDangerousAction('restart')).toBe(false)
    expect(isDangerousAction('logs')).toBe(false)
  })
})
