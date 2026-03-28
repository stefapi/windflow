import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mocks stores
const mockFetchStats = vi.fn()
const mockFetchGlobal = vi.fn()
const mockFetchGlobalByTarget = vi.fn()
const mockFetchTargets = vi.fn()

vi.mock('@/stores', () => ({
  useComputeStore: () => ({
    stats: {
      total_containers: 23,
      running_containers: 18,
      stacks_count: 3,
      stacks_services_count: 9,
      discovered_count: 4,
      standalone_count: 10,
      targets_count: 4,
    },
    statsLoading: false,
    globalView: null,
    targetGroups: [],
    loading: false,
    managedStacks: [],
    discoveredItems: [],
    standaloneContainers: [],
    fetchStats: mockFetchStats,
    fetchGlobal: mockFetchGlobal,
    fetchGlobalByTarget: mockFetchGlobalByTarget,
  }),
  useTargetsStore: () => ({
    targets: [
      { id: 'target-1', name: 'localhost' },
      { id: 'target-2', name: 'vps-ovh' },
    ],
    fetchTargets: mockFetchTargets,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ organizationId: 'test-org' }),
}))

vi.mock('@/services/api', () => ({
  containersApi: {
    start: vi.fn(),
    remove: vi.fn(),
  },
}))

// Import après les mocks
import Compute from '@/views/Compute.vue'

const globalConfig = {
  global: {
    stubs: {
      ElButton: {
        template: '<button><slot /></button>',
        props: ['type', 'size', 'disabled'],
      },
      ElRadioGroup: {
        template: '<div><slot /></div>',
        props: ['modelValue'],
      },
      ElRadioButton: {
        template: '<span><slot /></span>',
        props: ['value'],
      },
      ElInput: {
        template: '<input />',
        props: ['modelValue', 'placeholder'],
      },
      ElCard: {
        template: '<div class="el-card"><slot /></div>',
      },
      ElSkeleton: {
        template: '<div class="el-skeleton" />',
      },
      ElCollapse: {
        template: '<div class="el-collapse"><slot /></div>',
      },
      ElCollapseItem: {
        template: '<div class="el-collapse-item"><slot name="title" /><slot /></div>',
        props: ['name'],
      },
      ElTable: {
        template: '<div class="el-table"><slot /></div>',
        props: ['data'],
      },
      ElTableColumn: {
        template: '<div />',
        props: ['prop', 'label'],
      },
      ElTag: {
        template: '<span class="el-tag"><slot /></span>',
        props: ['type', 'size'],
      },
      ElEmpty: {
        template: '<div class="el-empty"><span>{{ description }}</span></div>',
        props: ['description'],
      },
      ElAlert: {
        template: '<div class="el-alert"><slot /></div>',
        props: ['type', 'closable'],
      },
      ElIcon: {
        template: '<i><slot /></i>',
      },
      ComputeStatsBanner: {
        template: '<div class="compute-stats-banner" />',
        props: ['stats', 'loading'],
      },
      ManagedStacksSection: {
        template: '<div class="managed-stubs-section"><slot /></div>',
        props: ['stacks', 'loading'],
      },
      DiscoveredSection: {
        template: '<div class="discovered-stubs-section"><div v-if="items.length === 0" class="el-empty">Aucun objet découvert avec des instances actives</div></div>',
        props: ['items', 'loading'],
      },
      StandaloneSection: {
        template: '<div class="standalone-stubs-section"><slot /></div>',
        props: ['containers', 'loading'],
      },
      TargetGroupView: {
        template: '<div class="target-group-view-stub" />',
        props: ['groups', 'loading'],
      },
      ElCheckbox: {
        template: '<label><input type="checkbox" /><slot /></label>',
        props: ['modelValue'],
      },
      ElDialog: {
        template: '<div class="el-dialog"><slot /><slot name="footer" /></div>',
        props: ['modelValue', 'title', 'width'],
      },
    },
    directives: {
      loading: {},
    },
  },
}

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/compute', component: Compute },
    ],
  })
}

describe('Compute.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('should render the page title "vue globale"', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    expect(wrapper.text()).toContain('vue globale')
  })

  it('should display subtitle with targets_count', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    expect(wrapper.text()).toContain('4 targets')
  })

  it('should call fetchStats and fetchGlobal on mounted', async () => {
    mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    // Attendre le prochain tick
    await new Promise(r => setTimeout(r, 0))

    expect(mockFetchStats).toHaveBeenCalledWith('test-org')
    expect(mockFetchGlobal).toHaveBeenCalled()
    expect(mockFetchTargets).toHaveBeenCalledWith('test-org')
  })

  it('should render ComputeStatsBanner component', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    expect(wrapper.find('.compute-stats-banner').exists()).toBe(true)
  })

  it('should show el-empty in Discovered section when discoveredItems is empty', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    const emptys = wrapper.findAll('.el-empty')
    // Au moins 1 el-empty pour discovered
    expect(emptys.length).toBeGreaterThan(0)
    const texts = emptys.map(e => e.text())
    expect(texts.some(t => t.includes('Aucun objet découvert'))).toBe(true)
  })

  it('should show target pills from targetsStore', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    expect(wrapper.text()).toContain('localhost')
    expect(wrapper.text()).toContain('vps-ovh')
  })

  it('should have toggle buttons "Tout" and "Par machine"', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    expect(wrapper.text()).toContain('Tout')
    expect(wrapper.text()).toContain('Par machine')
  })

  describe('toggle groupByTarget', () => {
    it('should call fetchGlobalByTarget when groupByTarget button is clicked', async () => {
      const wrapper = mount(Compute, {
        ...globalConfig,
        global: {
          ...globalConfig.global,
          plugins: [createTestRouter()],
        },
      })

      // Trouver le bouton "Par machine"
      const buttons = wrapper.findAll('button')
      const parMachineBtn = buttons.find(b => b.text().includes('Par machine'))
      expect(parMachineBtn).toBeDefined()

      await parMachineBtn!.trigger('click')
      await new Promise(r => setTimeout(r, 0))

      expect(mockFetchGlobalByTarget).toHaveBeenCalled()
    })
  })

  it('should render legend at bottom of page', () => {
    const wrapper = mount(Compute, {
      ...globalConfig,
      global: {
        ...globalConfig.global,
        plugins: [createTestRouter()],
      },
    })
    expect(wrapper.text()).toContain('Stack WindFlow')
    expect(wrapper.text()).toContain('Discovered')
    expect(wrapper.text()).toContain('Standalone')
  })
})
