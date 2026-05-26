import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mutable mode state — tests can change this before mounting
const { modeState } = vi.hoisted(() => ({
  modeState: { mode: 'app' as 'app' | 'infra' },
}))

// Mock container detail data
const mockContainerDetail = {
  id: 'container-123',
  name: 'my-app-container',
  image: 'nginx:latest',
  state: { status: 'running', running: true, started_at: new Date().toISOString() },
  config: {
    labels: {
      'com.docker.compose.service': 'my-app',
      'com.docker.compose.project': 'myproject',
    },
  },
  host_config: {
    restart_policy: { name: 'always' },
    resources: { memory: 268435456, cpu_shares: 512 },
  },
}

const { mockInspectContainer, mockStartContainer, mockStopContainer, mockRestartContainer, mockRemoveContainer } = vi.hoisted(() => ({
  mockInspectContainer: vi.fn(),
  mockStartContainer: vi.fn(),
  mockStopContainer: vi.fn(),
  mockRestartContainer: vi.fn(),
  mockRemoveContainer: vi.fn(),
}))

vi.mock('@/stores', () => ({
  useContainersStore: () => ({
    containerDetail: mockContainerDetail,
    detailLoading: false,
    error: null,
    inspectContainer: mockInspectContainer.mockResolvedValue(undefined),
    startContainer: mockStartContainer.mockResolvedValue(undefined),
    stopContainer: mockStopContainer.mockResolvedValue(undefined),
    restartContainer: mockRestartContainer.mockResolvedValue(undefined),
    removeContainer: mockRemoveContainer.mockResolvedValue(undefined),
  }),
}))

vi.mock('@/stores/mode', () => ({
  useModeStore: () => ({
    get mode() { return modeState.mode },
    get isAppMode() { return modeState.mode === 'app' },
    get isInfraMode() { return modeState.mode === 'infra' },
  }),
}))

vi.mock('@/services/api', () => ({
  containersApi: {
    getStats: vi.fn().mockResolvedValue({ data: {} }),
    rename: vi.fn(),
    updateRestartPolicy: vi.fn(),
    updateResources: vi.fn(),
    promote: vi.fn(),
  },
}))

vi.mock('@/composables/useAppVocabulary', () => ({
  useAppVocabulary: () => ({
    getAppStatus: (status: string) => {
      const map: Record<string, { app: string; color: string }> = {
        running: { app: 'En cours', color: 'success' },
        stopped: { app: 'Arrêté', color: 'danger' },
        exited: { app: 'Terminé', color: 'info' },
      }
      return map[status] ?? { app: status, color: 'info' }
    },
    getAppDisplayName: (container: { name?: string; labels?: Record<string, string> }) => {
      if (container.labels?.['com.docker.compose.service']) {
        return container.labels['com.docker.compose.service']
      }
      return container.name ?? 'Inconnu'
    },
  }),
  getAppDisplayName: (container: { name?: string; labels?: Record<string, string> }) => {
    if (container.labels?.['com.docker.compose.service']) {
      return container.labels['com.docker.compose.service']
    }
    return container.name ?? 'Inconnu'
  },
}))

// Stub child components — ElTabPane renders its label as a data attribute for testing
const childStubs = {
  ContainerOverviewTab: { template: '<div data-testid="overview-tab">Overview</div>', props: ['detail', 'containerId', 'containerState'] },
  ContainerInfoTab: { template: '<div data-testid="info-tab">Info</div>', props: ['detail'] },
  ContainerLogs: { template: '<div data-testid="logs-tab">Logs</div>', props: ['containerId', 'containerName'] },
  ContainerTerminal: { template: '<div data-testid="terminal-tab">Terminal</div>', props: ['containerId', 'containerName'] },
  ContainerStats: { template: '<div data-testid="stats-tab">Stats</div>', props: ['containerId', 'containerName'] },
  ContainerConfigTab: { template: '<div data-testid="config-tab">Config</div>', props: ['detail'] },
  ContainerProcesses: { template: '<div data-testid="processes-tab">Processes</div>', props: ['containerId', 'containerName'] },
  AppContextMenu: { template: '<div data-testid="app-context-menu">Menu</div>', props: ['containerId', 'containerName', 'containerStatus', 'domain'] },
  ElCard: { template: '<div class="el-card"><slot /><slot name="header" /></div>' },
  ElTabs: {
    template: '<div class="el-tabs" data-testid="el-tabs"><slot /></div>',
    props: ['modelValue'],
  },
  ElTabPane: {
    template: '<div class="el-tab-pane" :data-label="label" :data-name="name"><slot /></div>',
    props: ['label', 'name', 'disabled'],
  },
  ElButton: {
    template: '<button :data-type="type" :class="{ \'is-link\': link }"><slot /></button>',
    props: ['type', 'size', 'disabled', 'icon', 'plain', 'link'],
  },
  ElTag: { template: '<span class="el-tag"><slot /></span>', props: ['type', 'size', 'effect'] },
  ElIcon: { template: '<span class="el-icon"><slot /></span>' },
  ElTooltip: {
    template: '<span class="el-tooltip"><slot /></span>',
    props: ['content', 'placement'],
  },
  ElDivider: { template: '<hr />', props: ['direction'] },
  ElAlert: { template: '<div class="el-alert"><slot /></div>', props: ['title', 'type', 'showIcon', 'closable'] },
  ElDialog: { template: '<div class="el-dialog"><slot /></div>', props: ['modelValue', 'title', 'width'] },
  ElDrawer: { template: '<div class="el-drawer"><slot /></div>', props: ['modelValue', 'title', 'direction', 'size'] },
  ElInput: { template: '<input />', props: ['modelValue', 'placeholder', 'clearable', 'disabled', 'type', 'rows', 'readonly'] },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<div><slot /></div>', props: ['label', 'error'] },
  ElSelect: { template: '<select><slot /></select>', props: ['modelValue'] },
  ElOption: { template: '<option><slot /></option>', props: ['label', 'value'] },
  ElInputNumber: { template: '<input type="number" />', props: ['modelValue', 'min', 'max', 'step'] },
  ElEmpty: { template: '<div class="el-empty"><slot /></div>', props: ['description', 'imageSize'] },
}

import ContainerDetail from '@/views/ContainerDetail.vue'

async function createWrapper(initialMode: 'app' | 'infra' = 'app') {
  modeState.mode = initialMode

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/compute', component: { template: '<div />' } },
      { path: '/containers/:id', component: { template: '<div />' } },
    ],
  })

  await router.push('/containers/container-123')
  await router.isReady()

  const wrapper = mount(ContainerDetail, {
    global: {
      plugins: [router],
      stubs: childStubs,
    },
  })

  // Wait for onMounted async operations (loadContainerDetail, fetchHeaderStats)
  await flushPromises()

  return wrapper
}

describe('ContainerDetail.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Mode App — Header', () => {
    it('affiche le nom de l\'app via getAppDisplayName en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const headerText = wrapper.text()
      // getAppDisplayName returns 'my-app' from com.docker.compose.service label
      expect(headerText).toContain('my-app')
    })

    it('affiche le statut traduit en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const tags = wrapper.findAll('.el-tag')
      const statusTags = tags.filter(t => t.text().includes('En cours'))
      expect(statusTags.length).toBeGreaterThan(0)
    })

    it('masque le bouton Renommer en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const text = wrapper.text()
      expect(text).not.toContain('Renommer')
    })

    it('masque l\'image du container en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const text = wrapper.text()
      expect(text).not.toContain('nginx:latest')
    })

    it('masque les métadonnées techniques (Target, Restart, Ressources) en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const text = wrapper.text()
      expect(text).not.toContain('Target :')
      expect(text).not.toContain('Restart :')
      expect(text).not.toContain('Ressources :')
    })
  })

  describe('Mode App — Onglets', () => {
    it('affiche les onglets Mode App (Aperçu, Logs, Console, Métriques, Config)', async () => {
      const wrapper = await createWrapper('app')
      const panes = wrapper.findAll('.el-tab-pane')
      const labels = panes.map(p => p.attributes('data-label'))

      expect(labels).toContain('Aperçu')
      expect(labels).toContain('Logs')
      expect(labels).toContain('Console')
      expect(labels).toContain('Métriques')
      expect(labels).toContain('Config')
    })

    it('masque les onglets techniques (Infos, Processus) en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const panes = wrapper.findAll('.el-tab-pane')
      const labels = panes.map(p => p.attributes('data-label'))

      expect(labels).not.toContain('Infos')
      expect(labels).not.toContain('Processus')
    })
  })

  describe('Mode App — Action bar', () => {
    it('affiche l\'action bar simplifiée en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const text = wrapper.text()
      expect(text).toContain('Arrêter')
      expect(text).toContain('Redémarrer')
      expect(text).toContain('Logs')
      expect(text).toContain('Console')
      expect(text).toContain('Config')
    })

    it('affiche le menu contextuel [⋯ Plus] en Mode App', async () => {
      const wrapper = await createWrapper('app')
      expect(wrapper.find('[data-testid="app-context-menu"]').exists()).toBe(true)
    })

    it('n\'affiche pas les actions techniques (Pause, Inspect, Promouvoir) en Mode App', async () => {
      const wrapper = await createWrapper('app')
      const text = wrapper.text()
      expect(text).not.toContain('Pause')
      expect(text).not.toContain('Inspect')
      expect(text).not.toContain('Promouvoir')
    })
  })

  describe('Mode Infra — Comportement classique', () => {
    it('affiche les actions techniques en Mode Infra', async () => {
      const wrapper = await createWrapper('infra')
      const text = wrapper.text()
      expect(text).toContain('Démarrer')
      expect(text).toContain('Pause')
      expect(text).toContain('Arrêter')
      expect(text).toContain('Redémarrer')
      expect(text).toContain('Supprimer')
      expect(text).toContain('Inspect')
    })

    it('affiche les onglets techniques en Mode Infra', async () => {
      const wrapper = await createWrapper('infra')
      const panes = wrapper.findAll('.el-tab-pane')
      const labels = panes.map(p => p.attributes('data-label'))

      expect(labels).toContain('Infos')
      expect(labels).toContain('Terminal')
      expect(labels).toContain('Stats')
      expect(labels).toContain('Processus')
    })

    it('affiche le bouton Renommer en Mode Infra', async () => {
      const wrapper = await createWrapper('infra')
      const text = wrapper.text()
      expect(text).toContain('Renommer')
    })

    it('affiche l\'image du container en Mode Infra', async () => {
      const wrapper = await createWrapper('infra')
      const text = wrapper.text()
      expect(text).toContain('nginx:latest')
    })

    it('masque le menu contextuel [⋯ Plus] en Mode Infra', async () => {
      const wrapper = await createWrapper('infra')
      expect(wrapper.find('[data-testid="app-context-menu"]').exists()).toBe(false)
    })
  })
})
