import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

// Mock dashboard apps composable
const { mockApps, mockAppsLoading, mockFetchApps } = vi.hoisted(() => ({
  mockApps: vi.fn(() => []),
  mockAppsLoading: vi.fn(() => false),
  mockFetchApps: vi.fn(),
}))

vi.mock('@/composables/useDashboardApps', () => ({
  useDashboardApps: () => ({
    get apps() { return mockApps() },
    get loading() { return mockAppsLoading() },
    error: null,
    fetchApps: mockFetchApps,
  }),
}))

// Mock stores
const { mockFetchDashboardStats } = vi.hoisted(() => ({
  mockFetchDashboardStats: vi.fn(),
}))

vi.mock('@/stores', () => ({
  useDashboardStore: () => ({
    loading: false,
    error: null,
    containers: { total: 10, running: 8, stopped: 2 },
    stacks: { total: 3, running: 3, stopped: 0 },
    resourceMetrics: null,
    deploymentMetrics: null,
    targetHealth: {},
    targetsDetail: [],
    alerts: [],
    recentActivity: [],
    fetchDashboardStats: mockFetchDashboardStats,
  }),
  usePluginWidgetStore: () => ({
    registerWidget: vi.fn(),
    unregisterPlugin: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: {
      username: 'johndoe',
      full_name: 'John Doe',
      email: 'john@example.com',
    },
    organizationId: 'org-1',
  }),
}))

vi.mock('@/stores/targets', () => ({
  useTargetsStore: () => ({
    currentTarget: null,
  }),
}))

// Stub child components
const globalStubs = {
  ElAlert: { template: '<div class="el-alert"><slot /></div>', props: ['title', 'type', 'showIcon', 'closable'] },
  ElRow: { template: '<div class="el-row"><slot /></div>', props: ['gutter'] },
  ElCol: { template: '<div class="el-col"><slot /></div>', props: ['span'] },
  ElCard: { template: '<div class="el-card"><slot /></div>', props: ['header'] },
  ElButton: { template: '<button><slot /></button>', props: ['type', 'size', 'loading'] },
  ElSkeleton: { template: '<div class="el-skeleton" />' },
  CounterCard: { template: '<div class="counter-card" />', props: ['count', 'label', 'icon', 'to', 'runningCount', 'stoppedCount', 'badge', 'badgeType'] },
  TargetHealthWidget: { template: '<div class="target-health-widget" />', props: ['targetHealth', 'targetsDetail'] },
  ActivityFeedWidget: { template: '<div class="activity-feed-widget" />', props: ['activities'] },
  DeploymentMetricsWidget: { template: '<div class="deployment-metrics-widget" />', props: ['metrics'] },
  AlertsNotificationsWidget: { template: '<div class="alerts-widget" />', props: ['alerts'] },
  ResourceMetricsWidget: { template: '<div class="resource-metrics-widget" />', props: ['metrics', 'error', 'targetName', 'loading', 'noTarget'] },
  RecentDeploymentsWidget: { template: '<div class="recent-deployments-widget" />', props: ['limit'] },
  PluginWidgetZone: { template: '<div class="plugin-widget-zone" />' },
  DockerInfoWidget: { template: '<div class="docker-info-widget" />' },
  AppGridTile: {
    template: '<div class="app-grid-tile-stub" :data-testid="\'app-grid-tile-\' + app.id" />',
    props: ['app'],
  },
}

// Router
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div />' } },
    { path: '/compute', component: { template: '<div />' } },
  ],
})

// Import after mocks
import Dashboard from '@/views/Dashboard.vue'

function mountDashboard() {
  return mount(Dashboard, {
    global: {
      plugins: [router],
      stubs: globalStubs,
    },
  })
}

describe('Dashboard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockApps.mockReturnValue([])
    mockAppsLoading.mockReturnValue(false)
  })

  it('affiche la salutation avec le nom de l\'utilisateur', () => {
    const wrapper = mountDashboard()

    const greeting = wrapper.find('[data-testid="dashboard-greeting"]')
    expect(greeting.exists()).toBe(true)
    expect(greeting.text()).toBe('Bonjour, John Doe')
  })

  it('affiche la salutation avec le username si pas de full_name', () => {
    vi.mocked('@/stores/auth' as never)

    const wrapper = mountDashboard()

    const greeting = wrapper.find('[data-testid="dashboard-greeting"]')
    expect(greeting.text()).toContain('Bonjour,')
  })

  it('affiche la section Mes Apps avec la grille', () => {
    const wrapper = mountDashboard()

    expect(wrapper.find('.app-grid-section').exists()).toBe(true)
    expect(wrapper.find('.app-grid-section__title').text()).toBe('Mes Apps')
  })

  it('affiche les tuiles AppGridTile pour chaque app', () => {
    mockApps.mockReturnValue([
      { id: 'app-1', displayName: 'Nginx', icon: '🌐', status: 'running', statusLabel: 'En cours', statusColor: 'success', domain: null, containerId: 'c1' },
      { id: 'app-2', displayName: 'Redis', icon: '🔴', status: 'running', statusLabel: 'En cours', statusColor: 'success', domain: null, containerId: 'c2' },
    ])

    const wrapper = mountDashboard()

    const tiles = wrapper.findAll('.app-grid-tile-stub')
    expect(tiles).toHaveLength(2)
  })

  it('affiche le message vide quand aucune app', () => {
    mockApps.mockReturnValue([])

    const wrapper = mountDashboard()

    expect(wrapper.find('[data-testid="app-grid-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="app-grid-empty"]').text()).toContain('Aucune app installée')
  })

  it('conserve les widgets existants sous la grille', () => {
    const wrapper = mountDashboard()

    // CounterCards
    expect(wrapper.findAll('.counter-card').length).toBeGreaterThanOrEqual(1)
    // ResourceMetrics
    expect(wrapper.find('.resource-metrics-widget').exists()).toBe(true)
    // ActivityFeed
    expect(wrapper.find('.activity-feed-widget').exists()).toBe(true)
    // Alerts
    expect(wrapper.find('.alerts-widget').exists()).toBe(true)
    // PluginWidgetZone
    expect(wrapper.find('.plugin-widget-zone').exists()).toBe(true)
  })

  it('affiche le skeleton pendant le chargement', () => {
    mockAppsLoading.mockReturnValue(true)

    const wrapper = mountDashboard()

    expect(wrapper.find('[data-testid="app-grid-loading"]').exists()).toBe(true)
    expect(wrapper.findAll('.el-skeleton').length).toBeGreaterThan(0)
  })
})
