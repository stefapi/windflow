/**
 * DiscoveredSection.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import DiscoveredSection from '@/components/compute/DiscoveredSection.vue'
import type { DiscoveredItem, ServiceWithMetrics } from '@/types/api'

// ─── Mocks ──────────────────────────────────────────────────────────

const mockStart = vi.fn()
const mockStop = vi.fn()
const mockRestart = vi.fn()
const mockRemove = vi.fn()
const mockBatchStart = vi.fn()
const mockBatchStop = vi.fn()

vi.mock('@/services/api', () => ({
  containersApi: {
    start: (...args: unknown[]) => mockStart(...args),
    stop: (...args: unknown[]) => mockStop(...args),
    restart: (...args: unknown[]) => mockRestart(...args),
    remove: (...args: unknown[]) => mockRemove(...args),
    batchStart: (...args: unknown[]) => mockBatchStart(...args),
    batchStop: (...args: unknown[]) => mockBatchStop(...args),
  },
}))

const mockConfirm = vi.fn()
const mockSuccess = vi.fn()
const mockWarning = vi.fn()
const mockError = vi.fn()

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessageBox: {
      confirm: (...args: unknown[]) => mockConfirm(...args),
    },
    ElMessage: {
      success: (...args: unknown[]) => mockSuccess(...args),
      warning: (...args: unknown[]) => mockWarning(...args),
      error: (...args: unknown[]) => mockError(...args),
    },
  }
})

const mockRouterPush = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockRouterPush,
  }),
}))

// ─── Test Data ───────────────────────────────────────────────────────

function createMockService(overrides: Partial<ServiceWithMetrics> = {}): ServiceWithMetrics {
  return {
    id: 'svc-1',
    name: 'web',
    image: 'nginx:latest',
    status: 'running',
    cpu_percent: 1.5,
    memory_usage: '50M',
    ...overrides,
  }
}

function createMockItem(overrides: Partial<DiscoveredItem> = {}): DiscoveredItem {
  return {
    id: 'disc-001',
    name: 'monitoring',
    type: 'composition',
    technology: 'compose',
    source_path: '/home/user/monitoring/docker-compose.yml',
    target_id: 'target-001',
    target_name: 'vps-ovh',
    services_total: 2,
    services_running: 2,
    detected_at: '2024-01-01T00:00:00Z',
    adoptable: true,
    services: [
      createMockService(),
      createMockService({ id: 'svc-2', name: 'db', image: 'postgres:15' }),
    ],
    ...overrides,
  }
}

// ─── Mount helper ────────────────────────────────────────────────────

function mountComponent(props = {}) {
  return mount(DiscoveredSection, {
    props: {
      items: [createMockItem()],
      loading: false,
      ...props,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-collapse': {
          name: 'ElCollapse',
          template: '<div class="el-collapse-stub"><slot /></div>',
        },
        'el-collapse-item': {
          name: 'ElCollapseItem',
          template: '<div class="el-collapse-item-stub" :name="name"><slot /><slot name="title" /></div>',
          props: ['name'],
        },
        'el-empty': {
          name: 'ElEmpty',
          template: '<div class="el-empty-stub"><slot /></div>',
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub" :data-type="type"><slot /></div>',
          props: ['type', 'closable'],
        },
        'el-tag': {
          name: 'ElTag',
          template: '<span class="el-tag-stub" :data-type="type"><slot /></span>',
          props: ['type', 'size', 'effect'],
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub" :disabled="disabled" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
          props: ['type', 'size', 'icon', 'loading', 'disabled', 'text'],
          emits: ['click'],
        },
        'ContainerTable': {
          name: 'ContainerTable',
          template: '<div class="container-table-stub"><slot /></div>',
          props: ['items', 'columns', 'selectable', 'showActions', 'readonly'],
          emits: ['action', 'selection-change'],
          methods: {
            clearSelection() {},
          },
        },
        'BulkActionBar': {
          name: 'BulkActionBar',
          template: '<div class="bulk-action-bar-stub"><slot /></div>',
          props: ['selectedCount', 'loadingAction'],
          emits: ['start', 'stop', 'restart', 'delete', 'cancel'],
        },
      },
    },
  })
}

// ─── Tests ───────────────────────────────────────────────────────────

describe('DiscoveredSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ─── Rendu ───────────────────────────────────────────────────────

  describe('rendu', () => {
    it('affiche el-empty quand aucun item découvert', () => {
      const wrapper = mountComponent({ items: [] })
      expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    })

    it('affiche les items avec badge discovered et technologie', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('monitoring')
      expect(wrapper.text()).toContain('discovered')
      expect(wrapper.text()).toContain('compose')
      expect(wrapper.text()).toContain('vps-ovh')
      expect(wrapper.text()).toContain('2/2 running')
    })

    it('affiche le bouton Adopter si adoptable', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Adopter')
    })

    it('masque les actions si non adoptable', () => {
      const wrapper = mountComponent({
        items: [createMockItem({ adoptable: false })],
      })
      expect(wrapper.text()).not.toContain('Adopter')
      const table = wrapper.findComponent({ name: 'ContainerTable' })
      expect(table.props('readonly')).toBe(true)
      expect(table.props('selectable')).toBe(false)
    })

    it('affiche l\'alerte source_path si présent', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.el-alert-stub').exists()).toBe(true)
      expect(wrapper.text()).toContain('/home/user/monitoring/docker-compose.yml')
    })

    it('n\'affiche pas l\'alerte si source_path absent', () => {
      const wrapper = mountComponent({
        items: [createMockItem({ source_path: undefined })],
      })
      expect(wrapper.find('.el-alert-stub').exists()).toBe(false)
    })
  })

  // ─── Interactions ────────────────────────────────────────────────

  describe('interactions', () => {
    it('émet adopt au clic sur Adopter', async () => {
      const wrapper = mountComponent()
      wrapper.vm.$emit('adopt', 'disc-001')
      await flushPromises()
      expect(wrapper.emitted('adopt')).toBeTruthy()
      expect(wrapper.emitted('adopt')![0]).toEqual(['disc-001'])
    })

    it('handleItemStart appelle containersApi.batchStart avec les bons IDs', async () => {
      mockBatchStart.mockResolvedValue({ data: { success: true, message: 'Démarré' } })
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleItemStart: (item: DiscoveredItem) => Promise<void> }
      await vm.handleItemStart(createMockItem({ services: [
        createMockService({ id: 'svc-1', status: 'exited' }),
        createMockService({ id: 'svc-2', status: 'running' }),
      ]}))
      await flushPromises()
      expect(mockBatchStart).toHaveBeenCalledWith(['svc-1'])
      expect(mockSuccess).toHaveBeenCalledWith('Démarré')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('handleItemStop appelle containersApi.batchStop avec les bons IDs', async () => {
      mockBatchStop.mockResolvedValue({ data: { success: true, message: 'Arrêté' } })
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleItemStop: (item: DiscoveredItem) => Promise<void> }
      await vm.handleItemStop(createMockItem({ services: [
        createMockService({ id: 'svc-1', status: 'exited' }),
        createMockService({ id: 'svc-2', status: 'running' }),
      ]}))
      await flushPromises()
      expect(mockBatchStop).toHaveBeenCalledWith(['svc-2'])
      expect(mockSuccess).toHaveBeenCalledWith('Arrêté')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('gère les bulk actions sur les containers d\'un item', async () => {
      mockStart.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        setTableRef: (itemId: string, el: { clearSelection: () => void }) => void
        handleItemSelectionChange: (itemId: string, items: { id: string }[]) => void
        handleBulkAction: (action: string, itemId: string) => Promise<void>
      }
      vm.setTableRef('disc-001', { clearSelection: vi.fn() })
      vm.handleItemSelectionChange('disc-001', [{ id: 'svc-1' }])
      await vm.handleBulkAction('start', 'disc-001')
      await flushPromises()
      expect(mockStart).toHaveBeenCalledWith('svc-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('navigue vers les logs au clic sur logs', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleServiceAction: (type: string, row: { id: string }, item: DiscoveredItem) => Promise<void> }
      await vm.handleServiceAction('logs', { id: 'svc-1', name: 'web' }, createMockItem())
      await flushPromises()
      expect(mockRouterPush).toHaveBeenCalledWith('/containers/svc-1')
    })

    it('ne permet pas les actions individuelles si non adoptable', async () => {
      const wrapper = mountComponent({
        items: [createMockItem({ adoptable: false })],
      })
      const vm = wrapper.vm as unknown as { handleServiceAction: (type: string, row: { id: string }, item: DiscoveredItem) => Promise<void> }
      await vm.handleServiceAction('start', { id: 'svc-1', name: 'web' }, createMockItem({ adoptable: false }))
      await flushPromises()
      expect(mockStart).not.toHaveBeenCalled()
    })
  })
})
