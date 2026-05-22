/**
 * BulkActionBar.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import BulkActionBar from '@/components/compute/BulkActionBar.vue'

// ─── Mount helper ────────────────────────────────────────────────────

function mountComponent(props = {}) {
  return mount(BulkActionBar, {
    props: {
      selectedCount: 0,
      loadingAction: null,
      ...props,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-tag': {
          template: '<span class="el-tag-stub"><slot /></span>',
          props: ['type', 'size', 'effect'],
        },
        'el-button': {
          template: '<button class="el-button-stub" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
          props: ['type', 'size', 'loading'],
          emits: ['click'],
        },
        'el-icon': {
          template: '<i class="el-icon-stub"><slot /></i>',
        },
      },
    },
  })
}

// ─── Tests ───────────────────────────────────────────────────────────

describe('BulkActionBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ─── Rendu ───────────────────────────────────────────────────────

  describe('rendu', () => {
    it('n\'affiche rien quand selectedCount est 0', () => {
      const wrapper = mountComponent({ selectedCount: 0 })
      expect(wrapper.find('.el-tag-stub').exists()).toBe(false)
      expect(wrapper.find('.el-button-stub').exists()).toBe(false)
    })

    it('affiche le compteur de sélection', () => {
      const wrapper = mountComponent({ selectedCount: 3 })
      expect(wrapper.text()).toContain('3 sélectionnés')
    })

    it('affiche les 4 boutons d\'action (start, stop, restart, delete)', () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      const buttons = wrapper.findAll('.el-button-stub')
      const texts = buttons.map((b) => b.text())
      expect(texts).toContain('Démarrer')
      expect(texts).toContain('Arrêter')
      expect(texts).toContain('Redémarrer')
      expect(texts).toContain('Supprimer')
    })

    it('affiche le pluriel quand selectedCount > 1', () => {
      const wrapper = mountComponent({ selectedCount: 2 })
      expect(wrapper.text()).toContain('2 sélectionnés')
    })

    it('affiche le singulier quand selectedCount === 1', () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      expect(wrapper.text()).toContain('1 sélectionné')
    })
  })

  // ─── Interactions ────────────────────────────────────────────────

  describe('interactions', () => {
    it('émet start au clic sur Démarrer', async () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      const buttons = wrapper.findAll('.el-button-stub')
      const startBtn = buttons.find((b) => b.text() === 'Démarrer')
      expect(startBtn).toBeDefined()
      await startBtn!.trigger('click')
      expect(wrapper.emitted('start')).toBeTruthy()
    })

    it('émet stop au clic sur Arrêter', async () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      const buttons = wrapper.findAll('.el-button-stub')
      const stopBtn = buttons.find((b) => b.text() === 'Arrêter')
      expect(stopBtn).toBeDefined()
      await stopBtn!.trigger('click')
      expect(wrapper.emitted('stop')).toBeTruthy()
    })

    it('émet restart au clic sur Redémarrer', async () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      const buttons = wrapper.findAll('.el-button-stub')
      const restartBtn = buttons.find((b) => b.text() === 'Redémarrer')
      expect(restartBtn).toBeDefined()
      await restartBtn!.trigger('click')
      expect(wrapper.emitted('restart')).toBeTruthy()
    })

    it('émet delete au clic sur Supprimer', async () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      const buttons = wrapper.findAll('.el-button-stub')
      const deleteBtn = buttons.find((b) => b.text() === 'Supprimer')
      expect(deleteBtn).toBeDefined()
      await deleteBtn!.trigger('click')
      expect(wrapper.emitted('delete')).toBeTruthy()
    })

    it('émet cancel au clic sur Annuler la sélection', async () => {
      const wrapper = mountComponent({ selectedCount: 1 })
      const buttons = wrapper.findAll('.el-button-stub')
      const cancelBtn = buttons.find((b) => b.text().includes('Annuler'))
      expect(cancelBtn).toBeDefined()
      await cancelBtn!.trigger('click')
      expect(wrapper.emitted('cancel')).toBeTruthy()
    })

    it('affiche l\'état loading sur le bon bouton', () => {
      const wrapper = mountComponent({ selectedCount: 1, loadingAction: 'start' })
      const buttons = wrapper.findAll('.el-button-stub')
      const startBtn = buttons.find((b) => b.text() === 'Démarrer')
      expect(startBtn?.attributes('data-loading')).toBe('true')
    })
  })
})
