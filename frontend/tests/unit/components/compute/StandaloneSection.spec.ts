/**
 * StandaloneSection.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StandaloneSection from '@/components/compute/StandaloneSection.vue'
import type { StandaloneContainer } from '@/types/api'

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

function createMockContainer(overrides: Partial<StandaloneContainer> = {}): StandaloneContainer {
  return {
    id: 'c-1',
    name: 'traefik',
    image: 'traefik:v2.10',
    target_id: 'target-001',
    target_name: 'Local Docker',
    status: 'running',
    cpu_percent: 2.5,
    memory_usage: '80M',
    uptime: '3 days',
    ports: [],
    health_status: null,
    ...overrides,
  }
}

// ─── Mount helper ────────────────────────────────────────────────────

function mountComponent(props = {}) {
  return mount(StandaloneSection, {
    props: {
      containers: [createMockContainer()],
      loading: false,
      ...props,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-empty': {
          name: 'ElEmpty',
          template: '<div class="el-empty-stub"><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'width'],
          emits: ['update:modelValue'],
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /></div>',
          props: ['type', 'closable', 'show-icon'],
        },
        'el-checkbox': {
          name: 'ElCheckbox',
          template: '<label class="el-checkbox-stub"><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" /></label>',
          props: ['modelValue'],
          emits: ['update:modelValue'],
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub" :disabled="disabled" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
          props: ['type', 'size', 'icon', 'loading', 'disabled'],
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
      },
    },
  })
}

// ─── Tests ───────────────────────────────────────────────────────────

describe('StandaloneSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ─── Rendu ───────────────────────────────────────────────────────

  describe('rendu', () => {
    it('affiche el-empty quand aucun container', () => {
      const wrapper = mountComponent({ containers: [] })
      expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    })

    it('affiche BulkActionBar et ContainerTable quand des containers existent', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.bulk-action-bar-stub').exists()).toBe(true)
      expect(wrapper.find('.container-table-stub').exists()).toBe(true)
    })

    it('affiche les noms et images des containers dans la table', () => {
      const wrapper = mountComponent()
      const table = wrapper.findComponent({ name: 'ContainerTable' })
      expect(table.exists()).toBe(true)
      expect(table.props('items')).toHaveLength(1)
      expect(table.props('columns')).toEqual(['name', 'image', 'status', 'cpu', 'memory', 'uptime', 'ports', 'actions'])
    })
  })

  // ─── Sélection ───────────────────────────────────────────────────

  describe('sélection', () => {
    it('met à jour selectedIds quand la sélection change', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleSelectionChange: (selection: { id: string }[]) => void }
      vm.handleSelectionChange([{ id: 'c-1' }])
      await wrapper.vm.$nextTick()
      const bulkBar = wrapper.findComponent({ name: 'BulkActionBar' })
      expect(bulkBar.props('selectedCount')).toBe(1)
    })

    it('clearSelection réinitialise la sélection', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleSelectionChange: (selection: { id: string }[]) => void
        clearSelection: () => void
      }
      vm.handleSelectionChange([{ id: 'c-1' }])
      await wrapper.vm.$nextTick()

      vm.clearSelection()
      await wrapper.vm.$nextTick()

      const bulkBar = wrapper.findComponent({ name: 'BulkActionBar' })
      expect(bulkBar.props('selectedCount')).toBe(0)
    })
  })

  // ─── Actions individuelles ───────────────────────────────────────

  describe('actions individuelles', () => {
    it('handleAction start appelle containersApi.start et émet refresh', async () => {
      mockStart.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleAction: (type: string, item: { id: string; name: string }) => Promise<void> }
      await vm.handleAction('start', { id: 'c-1', name: 'traefik' })
      await flushPromises()
      expect(mockStart).toHaveBeenCalledWith('c-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('handleAction stop appelle containersApi.stop et émet refresh', async () => {
      mockStop.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleAction: (type: string, item: { id: string; name: string }) => Promise<void> }
      await vm.handleAction('stop', { id: 'c-1', name: 'traefik' })
      await flushPromises()
      expect(mockStop).toHaveBeenCalledWith('c-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('handleAction restart appelle containersApi.restart et émet refresh', async () => {
      mockRestart.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleAction: (type: string, item: { id: string; name: string }) => Promise<void> }
      await vm.handleAction('restart', { id: 'c-1', name: 'traefik' })
      await flushPromises()
      expect(mockRestart).toHaveBeenCalledWith('c-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('handleAction logs navigue vers /containers/:id', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleAction: (type: string, item: { id: string; name: string }) => Promise<void> }
      await vm.handleAction('logs', { id: 'c-1', name: 'traefik' })
      await flushPromises()
      expect(mockRouterPush).toHaveBeenCalledWith('/containers/c-1')
    })

    it('handleAction delete demande confirmation puis supprime', async () => {
      mockConfirm.mockResolvedValue('confirm')
      mockRemove.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleAction: (type: string, item: { id: string; name: string }) => Promise<void> }
      await vm.handleAction('delete', { id: 'c-1', name: 'traefik' })
      await flushPromises()
      expect(mockConfirm).toHaveBeenCalled()
      expect(mockRemove).toHaveBeenCalledWith('c-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })
  })

  // ─── Bulk actions ────────────────────────────────────────────────

  describe('bulk actions', () => {
    it('handleBulkAction start démarre les containers sélectionnés', async () => {
      mockStart.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleSelectionChange: (selection: { id: string }[]) => void
        handleBulkAction: (action: string) => Promise<void>
      }
      vm.handleSelectionChange([{ id: 'c-1' }])
      await vm.handleBulkAction('start')
      await flushPromises()
      expect(mockStart).toHaveBeenCalledWith('c-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('handleBulkAction stop arrête les containers sélectionnés', async () => {
      mockStop.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleSelectionChange: (selection: { id: string }[]) => void
        handleBulkAction: (action: string) => Promise<void>
      }
      vm.handleSelectionChange([{ id: 'c-1' }])
      await vm.handleBulkAction('stop')
      await flushPromises()
      expect(mockStop).toHaveBeenCalledWith('c-1')
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })

    it('showBulkDeleteDialog ouvre le dialog avec la liste des containers', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        handleSelectionChange: (selection: { id: string }[]) => void
        showBulkDeleteDialog: () => void
        bulkDeleteDialogVisible: boolean
      }
      vm.handleSelectionChange([{ id: 'c-1' }])
      vm.showBulkDeleteDialog()
      await wrapper.vm.$nextTick()
      expect(vm.bulkDeleteDialogVisible).toBe(true)
    })

    it('confirmBulkDelete supprime avec force si checkbox cochée', async () => {
      mockRemove.mockResolvedValue({})
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        selectedContainers: { id: string; name: string }[]
        bulkDeleteDialogVisible: boolean
        bulkForceDelete: boolean
        confirmBulkDelete: () => Promise<void>
      }
      vm.selectedContainers = [{ id: 'c-1', name: 'traefik' }]
      vm.bulkDeleteDialogVisible = true
      vm.bulkForceDelete = true
      await wrapper.vm.$nextTick()

      await vm.confirmBulkDelete()
      await flushPromises()

      expect(mockRemove).toHaveBeenCalledWith('c-1', true)
      expect(vm.bulkDeleteDialogVisible).toBe(false)
      expect(wrapper.emitted('refresh')).toBeTruthy()
    })
  })
})
