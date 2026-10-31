/**
 * DynamicFormField.vue Unit Tests — STORY-171 (AC 3 : binds canoniques minimum/maximum).
 *
 * Le composant consomme le contrat `GET /stacks/{id}` : les bornes arrivent en
 * `minimum`/`maximum` et doivent alimenter les attributs `min`/`max` de
 * `el-input-number` (contrôle bloquant Element Plus).
 */
import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import DynamicFormField from '@/components/DynamicFormField.vue'
import type { FormField } from '@/composables/useDynamicForm'

function makeIntegerField(overrides: Partial<FormField> = {}): FormField {
  return {
    key: 'host_port',
    type: 'integer',
    label: 'Port hôte',
    required: true,
    visible: true,
    minimum: 1,
    maximum: 65535,
    default: 5432,
    validationRules: [],
    ...overrides,
  }
}

function mountField(field: FormField, modelValue: unknown = null) {
  return mount(DynamicFormField, {
    props: { field, modelValue },
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('DynamicFormField — STORY-171 binds canoniques minimum/maximum', () => {
  describe('champ integer borné', () => {
    it('rend un el-input-number avec min/max alimentés depuis minimum/maximum', async () => {
      const wrapper = mountField(makeIntegerField(), 5432)

      const inputNumber = wrapper.findComponent({ name: 'ElInputNumber' })
      expect(inputNumber.exists()).toBe(true)

      // Les props Element Plus sont alimentées depuis les bornes canoniques
      expect(inputNumber.props('min')).toBe(1)
      expect(inputNumber.props('max')).toBe(65535)
    })

    it('precision vaut 0 pour un champ integer', async () => {
      const wrapper = mountField(makeIntegerField(), 5432)
      const inputNumber = wrapper.findComponent({ name: 'ElInputNumber' })

      expect(inputNumber.exists()).toBe(true)
      expect(inputNumber.props('precision')).toBe(0)
    })

    it('rend un champ natif de type number', async () => {
      const wrapper = mountField(makeIntegerField(), 5432)
      await Promise.resolve()

      // el-input-number rend un <input type="number"> natif
      const input = wrapper.find('input')
      expect(input.exists()).toBe(true)
    })
  })

  describe('champ number décimal', () => {
    it('garde precision 2 quand le type est number non entier', () => {
      const wrapper = mountField(
        makeIntegerField({
          key: 'cpu_limit',
          type: 'number',
          default: 0.5,
          minimum: 0,
          maximum: 4,
        }),
        0.5
      )

      const inputNumber = wrapper.findComponent({ name: 'ElInputNumber' })
      expect(inputNumber.exists()).toBe(true)
      expect(inputNumber.props('min')).toBe(0)
      expect(inputNumber.props('max')).toBe(4)
      expect(inputNumber.props('precision')).toBe(2)
    })
  })

  describe('bornes absentes', () => {
    it("rend el-input-number avec les bornes par défaut d'Element Plus (±Infinity)", () => {
      const wrapper = mountField(
        makeIntegerField({
          key: 'workers',
          minimum: undefined,
          maximum: undefined,
          default: 4,
        }),
        4
      )

      const inputNumber = wrapper.findComponent({ name: 'ElInputNumber' })
      expect(inputNumber.exists()).toBe(true)
      // `:min="undefined"` → défaut de prop Element Plus = ±MAX_SAFE_INTEGER
      expect(inputNumber.props('min')).toBe(Number.MIN_SAFE_INTEGER)
      expect(inputNumber.props('max')).toBe(Number.MAX_SAFE_INTEGER)
    })
  })

  describe('header de groupe', () => {
    it('rend un header de groupe sans champ de saisie', () => {
      const wrapper = mountField(
        makeIntegerField({
          key: '__group_performance',
          type: 'group',
          label: 'Performance',
          required: false,
          isGroupHeader: true,
        })
      )

      expect(wrapper.find('.group-header').exists()).toBe(true)
      expect(wrapper.findComponent({ name: 'ElInputNumber' }).exists()).toBe(false)
    })
  })

  describe('enum_labels', () => {
    afterEach(() => {
      // Le dropdown el-select est téléporté vers document.body — nettoyage
      document.body.innerHTML = ''
    })

    it("utilise les libellés localisés pour les options d'enum", async () => {
      const wrapper = mount(DynamicFormField, {
        props: {
          field: makeIntegerField({
            key: 'mode',
            type: 'string',
            default: 'balanced',
            minimum: undefined,
            maximum: undefined,
            enum: ['light', 'balanced', 'aggressive'],
            enum_labels: { light: 'Léger', balanced: 'Équilibré', aggressive: 'Agressif' },
          }),
          modelValue: 'balanced',
        },
        global: { plugins: [ElementPlus] },
        attachTo: document.body,
      })

      const select = wrapper.findComponent({ name: 'ElSelect' })
      expect(select.exists()).toBe(true)

      // Les options sont téléportées dans body (el-select teleported par défaut)
      await Promise.resolve()
      const renderedLabels = Array.from(document.body.querySelectorAll('.el-select-dropdown__item')).map((item) => item.textContent?.trim())
      expect(renderedLabels).toEqual(['Léger', 'Équilibré', 'Agressif'])

      wrapper.unmount()
    })
  })
})
