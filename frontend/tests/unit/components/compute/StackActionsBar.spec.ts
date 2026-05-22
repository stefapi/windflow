/**
 * StackActionsBar.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import StackActionsBar from '@/components/compute/StackActionsBar.vue'
import type { StackWithServices } from '@/types/api'

// ─── Mocks ──────────────────────────────────────────────────────────

const mockStart = vi.fn()
const mockStop = vi.fn()
const mockRedeploy = vi.fn()

vi.mock('@/services/api', () => ({
  stacksApi: {
    start: (...args: unknown[]) => mockStart(...args),
    stop: (...args: unknown[]) => mockStop(...args),
    redeploy: (...args: unknown[]) => mockRedeploy(...args),
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

// ─── Test Data ───────────────────────────────────────────────────────

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
    services: [],
    ...overrides,
  }
}

// ─── Mount helper ────────────────────────────────────────────────────

function mountComponent(stack: StackWithServices = createMockStack()) {
  return mount(StackActionsBar, {
    props: { stack },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-button': {
          template: '<button class="el-button-stub" :disabled="disabled" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
          props: ['type', 'size', 'icon', 'loading', 'disabled'],
          emits: ['click'],
        },
        'el-tag': {
          template: '<span class="el-tag-stub" :data-type="type"><slot /></span>',
          props: ['type', 'size', 'effect'],
        },
        'el-dialog': {
          template: '<div class="el-dialog-stub" v-if="modelValue"><slot /><slot name="footer" /></div>',
          props: ['modelValue', 'title', 'width', 'closeOnClickModal'],
          emits: ['update:modelValue'],
        },
        'el-radio-group': {
          template: '<div class="el-radio-group-stub"><slot /></div>',
          props: ['modelValue'],
          emits: ['update:modelValue'],
        },
        'el-radio': {
          template: '<label class="el-radio-stub"><slot /></label>',
          props: ['value', 'size'],
        },
      },
    },
  })
}

// ─── Tests ───────────────────────────────────────────────────────────

describe('StackActionsBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ─── Rendu ───────────────────────────────────────────────────────

  describe('rendu', () => {
    it('affiche le nom de la stack', () => {
      const wrapper = mountComponent(createMockStack({ name: 'My Stack' }))
      expect(wrapper.text()).toContain('My Stack')
    })

    it('affiche le tag de status avec la bonne couleur', () => {
      const wrapper = mountComponent(createMockStack({ status: 'running' }))
      const tag = wrapper.find('.el-tag-stub')
      expect(tag.exists()).toBe(true)
      expect(tag.attributes('data-type')).toBe('success')
    })

    it('affiche le tag warning pour status partial', () => {
      const wrapper = mountComponent(createMockStack({ status: 'partial' }))
      const tag = wrapper.find('.el-tag-stub')
      expect(tag.attributes('data-type')).toBe('warning')
    })

    it('affiche le tag danger pour status stopped', () => {
      const wrapper = mountComponent(createMockStack({ status: 'stopped' }))
      const tag = wrapper.find('.el-tag-stub')
      expect(tag.attributes('data-type')).toBe('danger')
    })

    it('affiche le compteur de services', () => {
      const wrapper = mountComponent(createMockStack({
        services_running: 2,
        services_total: 3,
      }))
      expect(wrapper.text()).toContain('2/3 services')
    })

    it('affiche les 3 boutons d\'action', () => {
      const wrapper = mountComponent()
      const buttons = wrapper.findAll('.el-button-stub')
      const texts = buttons.map((b) => b.text())
      expect(texts).toContain('Démarrer')
      expect(texts).toContain('Arrêter')
      expect(texts).toContain('Redéployer')
    })
  })

  // ─── États des boutons ───────────────────────────────────────────

  describe('états des boutons', () => {
    it('désactive le bouton Démarrer si tous les services sont running', () => {
      const wrapper = mountComponent(createMockStack({
        services_running: 3,
        services_total: 3,
        status: 'running',
      }))
      const buttons = wrapper.findAll('.el-button-stub')
      const startBtn = buttons.find((b) => b.text() === 'Démarrer')
      expect(startBtn?.attributes('disabled')).toBeDefined()
    })

    it('désactive le bouton Arrêter si tous les services sont stopped', () => {
      const wrapper = mountComponent(createMockStack({
        services_running: 0,
        services_total: 3,
        status: 'stopped',
      }))
      const buttons = wrapper.findAll('.el-button-stub')
      const stopBtn = buttons.find((b) => b.text() === 'Arrêter')
      expect(stopBtn?.attributes('disabled')).toBeDefined()
    })

    it('désactive tous les boutons pendant le loading', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { loading: boolean }
      vm.loading = true
      await wrapper.vm.$nextTick()

      const buttons = wrapper.findAll('.el-button-stub')
      for (const btn of buttons) {
        expect(btn.attributes('data-loading')).toBe('true')
      }
    })
  })

  // ─── Interactions ────────────────────────────────────────────────

  describe('interactions', () => {
    it('handleStart appelle stacksApi.start et émet action-completed', async () => {
      mockConfirm.mockResolvedValue('confirm')
      mockStart.mockResolvedValue({
        data: { success: true, message: 'Stack démarrée' },
      })

      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleStart: () => Promise<void> }

      await vm.handleStart()
      await flushPromises()

      expect(mockConfirm).toHaveBeenCalled()
      expect(mockStart).toHaveBeenCalledWith('stack-001')
      expect(mockSuccess).toHaveBeenCalledWith('Stack démarrée')
      expect(wrapper.emitted('action-completed')).toBeTruthy()
      expect(wrapper.emitted('action-completed')![0]).toEqual(['stack-001'])
    })

    it('handleStart annule si l\'utilisateur refuse la confirmation', async () => {
      mockConfirm.mockRejectedValue('cancel')

      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleStart: () => Promise<void> }

      await vm.handleStart()
      await flushPromises()

      expect(mockConfirm).toHaveBeenCalled()
      expect(mockStart).not.toHaveBeenCalled()
      expect(wrapper.emitted('action-completed')).toBeFalsy()
    })

    it('handleStop appelle stacksApi.stop et émet action-completed', async () => {
      mockConfirm.mockResolvedValue('confirm')
      mockStop.mockResolvedValue({
        data: { success: true, message: 'Stack arrêtée' },
      })

      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as { handleStop: () => Promise<void> }

      await vm.handleStop()
      await flushPromises()

      expect(mockConfirm).toHaveBeenCalled()
      expect(mockStop).toHaveBeenCalledWith('stack-001')
      expect(mockSuccess).toHaveBeenCalledWith('Stack arrêtée')
      expect(wrapper.emitted('action-completed')).toBeTruthy()
    })

    it('handleRedeploy ouvre le dialog puis appelle stacksApi.redeploy', async () => {
      mockRedeploy.mockResolvedValue({
        data: { success: true, message: 'Stack redéployée', strategy: 'stop_start' },
      })

      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        openRedeployDialog: () => void
        handleRedeploy: () => Promise<void>
        redeployDialogVisible: boolean
        selectedStrategy: string
      }

      // Ouvrir le dialog
      vm.openRedeployDialog()
      await wrapper.vm.$nextTick()
      expect(vm.redeployDialogVisible).toBe(true)

      // Exécuter le redéploiement
      await vm.handleRedeploy()
      await flushPromises()

      expect(mockRedeploy).toHaveBeenCalledWith('stack-001', { strategy: 'stop_start' })
      expect(wrapper.emitted('action-completed')).toBeTruthy()
    })
  })

  // ─── Dialog de redéploiement ─────────────────────────────────────

  describe('dialog de redéploiement', () => {
    it('affiche les 2 options de stratégie (stop_start et rolling)', async () => {
      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        openRedeployDialog: () => void
        redeployDialogVisible: boolean
      }

      vm.openRedeployDialog()
      await wrapper.vm.$nextTick()

      const dialog = wrapper.find('.el-dialog-stub')
      expect(dialog.exists()).toBe(true)
      expect(dialog.text()).toContain('Arrêt puis démarrage')
      expect(dialog.text()).toContain('Rolling')
    })

    it('appelle stacksApi.redeploy avec la stratégie sélectionnée', async () => {
      mockRedeploy.mockResolvedValue({
        data: { success: true, message: 'Stack redéployée', strategy: 'rolling' },
      })

      const wrapper = mountComponent()
      const vm = wrapper.vm as unknown as {
        openRedeployDialog: () => void
        handleRedeploy: () => Promise<void>
        selectedStrategy: string
      }

      vm.openRedeployDialog()
      await wrapper.vm.$nextTick()

      // Sélectionner la stratégie rolling
      vm.selectedStrategy = 'rolling'
      await wrapper.vm.$nextTick()

      await vm.handleRedeploy()
      await flushPromises()

      expect(mockRedeploy).toHaveBeenCalledWith('stack-001', { strategy: 'rolling' })
    })
  })
})
