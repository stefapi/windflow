import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import type { AppCardData } from '@/components/compute/helpers'

// Use vi.hoisted to define mocks that are used inside vi.mock factories
const { mockStart, mockStop, mockRestart } = vi.hoisted(() => ({
  mockStart: vi.fn(),
  mockStop: vi.fn(),
  mockRestart: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  containersApi: {
    start: mockStart,
    stop: mockStop,
    restart: mockRestart,
  },
}))

// Mock ElMessage
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
    },
  }
})

// Mock useAppContextMenu (used by AppContextMenu)
vi.mock('@/stores/mode', () => ({
  useModeStore: () => ({
    mode: 'app',
    isAppMode: true,
    isInfraMode: false,
  }),
}))

// Import after mocks
import AppCard from '@/components/compute/AppCard.vue'

// ─── Factory ────────────────────────────────────────────────────────────────

function createAppCardData(overrides: Partial<AppCardData> = {}): AppCardData {
  return {
    id: 'app-1',
    name: 'nginx',
    displayName: 'nginx',
    version: '1.26',
    icon: '🌐',
    domain: 'http://localhost:8080',
    status: 'running',
    statusLabel: 'En cours',
    statusColor: 'success',
    ram: '50 MiB',
    cpuPercent: 2.5,
    category: 'managed',
    servicesTotal: 3,
    servicesRunning: 2,
    targetName: 'localhost',
    updateAvailable: false,
    containerId: 'ctr-1',
    labels: {},
    ...overrides,
  }
}

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/containers/:id', component: { template: '<div />' } }],
})

const globalConfig = {
  global: {
    plugins: [router],
    stubs: {
      ElCard: {
        template: '<div class="el-card" data-testid="app-card"><slot /></div>',
        props: ['shadow'],
      },
      ElButton: {
        template: '<button @click="$emit(\'click\')"><slot /></button>',
        props: ['size', 'type'],
        emits: ['click'],
      },
      ElTag: {
        template: '<span class="el-tag"><slot /></span>',
        props: ['size', 'type'],
      },
      AppContextMenu: {
        template: '<div data-testid="app-context-menu" />',
        props: ['containerId', 'containerName', 'containerStatus', 'domain', 'labels', 'size'],
        emits: ['action'],
      },
    },
  },
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe('AppCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('affiche le nom affiché, la version et le statut de l\'app', () => {
    const data = createAppCardData()
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    expect(wrapper.text()).toContain('nginx')
    expect(wrapper.text()).toContain('1.26')
    expect(wrapper.text()).toContain('En cours')
  })

  it('affiche le domaine comme lien cliquable quand présent', () => {
    const data = createAppCardData({ domain: 'http://localhost:8080' })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const link = wrapper.find('[data-testid="domain-link"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('http://localhost:8080')
  })

  it('n\'affiche pas le lien domaine quand absent', () => {
    const data = createAppCardData({ domain: null })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const link = wrapper.find('[data-testid="domain-link"]')
    expect(link.exists()).toBe(false)
  })

  it('affiche le badge de mise à jour quand updateAvailable est true', () => {
    const data = createAppCardData({ updateAvailable: true })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const badge = wrapper.find('[data-testid="update-badge"]')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('⬆')
  })

  it('masque le badge de mise à jour quand updateAvailable est false', () => {
    const data = createAppCardData({ updateAvailable: false })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const badge = wrapper.find('[data-testid="update-badge"]')
    expect(badge.exists()).toBe(false)
  })

  it('affiche les actions inline pour une app running', () => {
    const data = createAppCardData({ status: 'running', domain: 'http://localhost' })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const text = wrapper.text()
    expect(text).toContain('Ouvrir')
    expect(text).toContain('Logs')
    expect(text).toContain('Terminal')
    expect(text).toContain('Stop')
  })

  it('affiche l\'action Start pour une app arrêtée', () => {
    const data = createAppCardData({ status: 'exited', domain: null })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const text = wrapper.text()
    expect(text).toContain('Start')
    expect(text).not.toContain('Stop')
  })

  it('déclenche l\'action stop au clic sur le bouton Stop', async () => {
    const data = createAppCardData({ status: 'running' })
    mockStop.mockResolvedValue({})
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const buttons = wrapper.findAll('button')
    const stopBtn = buttons.find(b => b.text().includes('Stop'))
    expect(stopBtn).toBeTruthy()
    await stopBtn!.trigger('click')
    expect(mockStop).toHaveBeenCalledWith('ctr-1')
  })

  it('émet l\'événement refresh après une action lifecycle', async () => {
    const data = createAppCardData({ status: 'running' })
    mockStop.mockResolvedValue({})
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const buttons = wrapper.findAll('button')
    const stopBtn = buttons.find(b => b.text().includes('Stop'))
    await stopBtn!.trigger('click')
    await nextTick()
    expect(wrapper.emitted('refresh')).toBeTruthy()
  })

  it('rend le menu contextuel AppContextMenu', () => {
    const data = createAppCardData()
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const menu = wrapper.find('[data-testid="app-context-menu"]')
    expect(menu.exists()).toBe(true)
  })

  it('affiche la RAM et les informations de services', () => {
    const data = createAppCardData({ ram: '342 MiB', servicesTotal: 3, servicesRunning: 2 })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    const text = wrapper.text()
    expect(text).toContain('342 MiB')
    expect(text).toContain('2/3 services')
  })

  it('n\'affiche pas le compteur de services pour une app mono-service', () => {
    const data = createAppCardData({ servicesTotal: 1, servicesRunning: 1 })
    const wrapper = mount(AppCard, {
      props: { app: data },
      ...globalConfig,
    })

    expect(wrapper.text()).not.toContain('services')
  })
})
