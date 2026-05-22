/**
 * ManagedStacksSection.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ManagedStacksSection from '@/components/compute/ManagedStacksSection.vue'
import type { StackWithServices, ServiceWithMetrics } from '@/types/api'

// ─── Mocks ──────────────────────────────────────────────────────────

const mockStart = vi.fn()
const mockStop = vi.fn()
const mockRestart = vi.fn()
const mockRemove = vi.fn()

vi.mock('@/services/api', () => ({
  containersApi: {
    start: (...args: unknown[]) => mockStart(...args),
    stop: (...args: unknown[]) => mockStop(...args),
    restart: (...args: unknown[]) => mockRestart(...args),
    remove: (...args: unknown[]) => mockRemove(...args),
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

function createMockStack(overrides: Partial<StackWithServices> = {}): StackWithServices {
  return {
    id: 'stack-001',
    name: 'Test Stack',
    technology: 'docker',
    target_id: 'target-001',
    target_name: 'Local Docker',
    services_total: 3,
    services_running: 2,
    status: 'partial',
    services: [
      createMockService(),
      createMockService({ id: 'svc-2', name: 'db', image: 'postgres:15', status: 'exited', cpu_percent: 0, memory_usage: '0M' }),
    ],
    ...overrides,
  }
}

// ─── Mount helper ────────────────────────────────────────────────────

function mountComponent(props = {}) {
  return mount(ManagedStacksSection, {
    props: {
      stacks: [createMockStack()],
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
        'el-icon': {
          name: 'ElIcon',
          template: '<i class="el-icon-stub"><slot /></i>',
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
          props: ['items', 'columns', 'selectable', 'showActions'],
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
        'StackActionsBar': {
          name: 'StackActionsBar',
          template: '<div class="stack-actions-bar-stub"><slot /></div>',
          props: ['stack'],
          emits: ['action-completed'],
        },
      },
    },
  })
}

// ─── Tests ───────────────────────────────────────────────────────────

describe('ManagedStacksSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ─── Rendu ───────────────────────────────────────────────────────

  describe('rendu', () => {
    it('affiche le spinner pendant le chargement', () => {
      const wrapper = mountComponent({ loading: true, stacks: [] })
      expect(wrapper.find('.el-icon-stub').exists()).toBe(true)
    })

    it('affiche el-empty quand aucune stack', () => {
      const wrapper = mountComponent({ stacks: [] })
      expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    })

    it('affiche les stacks avec leurs tags', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Test Stack')
      expect(wrapper.text()).toContain('stack WindFlow')
      expect(wrapper.text()).toContain('docker')
      expect(wrapper.text()).toContain('Local Docker')
      expect(wrapper.text()).toContain('2/3 running')
    })

    it('affiche StackActionsBar et BulkActionBar pour chaque stack', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.stack-actions-bar-stub').exists()).toBe(true)
      expect(wrapper.find('.bulk-action-bar-stub').exists()).toBe(true)
    })

    it('affiche ContainerTable avec les bonnes colonnes', () => {
      const wrapper = mountComponent()
      const table = wrapper.findComponent({ name: 'ContainerTable' })
      expect(table.exists()).toBe(true)
      expect(table.props('columns')).toEqual(['name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions'])
      expect(table.props('selectable')).toBe(true)
      expect(table.props('showActions')).toBe(true)
    })
  })

  // ─── Interactions ────────────────────────────────────────────────

  describe('interactions', () => {
    it('émet copy-id au clic sur le bouton copie', async () => {
      const wrapper = mountComponent()
      wrapper.vm.$emit('copy-id', 'stack-001')
      await flushPromises()
      expect(wrapper.emitted('copy-id')).toBeTruthy()
      expect(wrapper.emitted('copy-id')![0]).toEqual(['stack-001'])
    })

    it('émet refresh au clic sur le bouton rafraîchir', async () => {
      const wrapper = mountComponent()
      wrapper.vm.$emit('refresh')
      await flushPromises()
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('émet refresh après une action de service (start)', async () => {
      mockStart.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleServiceAction: (type: string, item: { id: string }) => Promise<void> }
      await vm.handleServiceAction('start', { id: 'svc-1', name: 'web' })
      await flushPromises()
      expect(mockStart).toHaveBeenCalledWith('svc-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('émet refresh après une action de service (stop)', async () => {
      mockStop.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleServiceAction: (type: string, item: { id: string }) => Promise<void> }
      await vm.handleServiceAction('stop', { id: 'svc-1', name: 'web' })
      await flushPromises()
      expect(mockStop).toHaveBeenCalledWith('svc-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('navigue vers les logs au clic sur logs', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleServiceAction: (type: string, item: { id: string }) => Promise<void> }
      await vm.handleServiceAction('logs', { id: 'svc-1', name: 'web' })
      await flushPromises()
      expect(mockRouterPush).toHaveBeenCalledWith('/containers/svc-1')
    })

    it('gère la sélection et le bulk action start', async () => {
      mockStart.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleStackSelectionChange: (stackId: string, items: { id: string }[]) => void
        handleBulkAction: (action: string, stackId: string) => Promise<void>
      }
      vm.handleStackSelectionChange('stack-001', [{ id: 'svc-1' }, { id: 'svc-2' }])
      await vm.handleBulkAction('start', 'stack-001')
      await flushPromises()
      expect(mockStart).toHaveBeenCalledWith('svc-1')
      expect(mockStart).toHaveBeenCalledWith('svc-2')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('affiche la confirmation avant suppression bulk', async () => {
      mockConfirm.mockResolvedValue('confirm')
      mockRemove.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleStackSelectionChange: (stackId: string, items: { id: string }[]) => void
        handleBulkAction: (action: string, stackId: string) => Promise<void>
      }
      vm.handleStackSelectionChange('stack-001', [{ id: 'svc-1' }])
      await vm.handleBulkAction('delete', 'stack-001')
      await flushPromises()
      expect(mockConfirm).toHaveBeenCalled()
      expect(mockRemove).toHaveBeenCalledWith('svc-1')
    })

    it('annule la suppression bulk si l\'utilisateur refuse', async () => {
      mockConfirm.mockRejectedValue('cancel')
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleStackSelectionChange: (stackId: string, items: { id: string }[]) => void
        handleBulkAction: (action: string, stackId: string) => Promise<void>
      }
      vm.handleStackSelectionChange('stack-001', [{ id: 'svc-1' }])
      await vm.handleBulkAction('delete', 'stack-001')
      await flushPromises()
      expect(mockConfirm).toHaveBeenCalled()
      expect(mockRemove).not.toHaveBeenCalled()
    })

    it('gère les erreurs lors du bulk action start', async () => {
      mockStart.mockRejectedValue(new Error('fail'))
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleStackSelectionChange: (stackId: string, items: { id: string }[]) => void
        handleBulkAction: (action: string, stackId: string) => Promise<void>
      }
      vm.handleStackSelectionChange('stack-001', [{ id: 'svc-1' }])
      await vm.handleBulkAction('start', 'stack-001')
      await flushPromises()
      expect(mockError).toHaveBeenCalled()
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })
  })
})
