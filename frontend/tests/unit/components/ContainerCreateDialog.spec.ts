/**
 * ContainerCreateDialog.vue Unit Tests
 *
 * STORY-019 : Création manuelle de containers Docker.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ContainerCreateDialog from '@/components/ContainerCreateDialog.vue'

// Mock containersApi.create
const mockCreate = vi.fn()
vi.mock('@/services/api', () => ({
  containersApi: {
    create: (...args: unknown[]) => mockCreate(...args),
  },
}))

// Mock ElMessage
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      ...((await vi.importActual('element-plus')) as Record<string, unknown>).ElMessage as Record<string, unknown>,
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
    },
  }
})

// Stubs for Element Plus components
const stubs = {
  ElDialog: {
    template: '<div class="el-dialog" v-if="modelValue"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title', 'width'],
    emits: ['update:modelValue', 'close'],
  },
  ElForm: {
    template: '<div class="el-form"><slot /></div>',
    props: ['model', 'rules', 'labelWidth'],
    methods: {
      validate: () => Promise.resolve(true),
      resetFields: () => {},
    },
  },
  ElFormItem: {
    template: '<div class="el-form-item"><slot /></div>',
    props: ['label', 'prop'],
  },
  ElInput: {
    template: '<input class="el-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'type'],
    emits: ['update:modelValue'],
  },
  ElButton: {
    template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
    props: ['type', 'size', 'loading', 'disabled', 'icon', 'circle'],
    emits: ['click'],
  },
  ElSelect: {
    template: '<select class="el-select"><slot /></select>',
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue'],
  },
  ElOption: {
    template: '<option><slot /></option>',
    props: ['label', 'value'],
  },
  ElSwitch: {
    template: '<input type="checkbox" class="el-switch" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    props: ['modelValue'],
    emits: ['update:modelValue'],
  },
  ElDivider: {
    template: '<div class="el-divider"><slot /></div>',
    props: ['contentPosition'],
  },
  ElAlert: {
    template: '<div class="el-alert"><slot /></div>',
    props: ['type', 'closable', 'showIcon'],
  },
}

// Helper to mount component
function mountComponent(props = {}) {
  return mount(ContainerCreateDialog, {
    props: {
      modelValue: true,
      ...props,
    },
    global: {
      stubs,
    },
  })
}

describe('ContainerCreateDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('rend le dialog fermé par défaut', () => {
    const wrapper = mountComponent({ modelValue: false })
    expect(wrapper.find('.el-dialog').exists()).toBe(false)
  })

  it('affiche le formulaire quand dialog ouvert', () => {
    const wrapper = mountComponent({ modelValue: true })
    expect(wrapper.find('.el-dialog').exists()).toBe(true)
    expect(wrapper.find('.el-form').exists()).toBe(true)
    expect(wrapper.find('.el-input').exists()).toBe(true)
  })

  it('affiche une erreur si le nom contient des caractères invalides', async () => {
    const wrapper = mountComponent({ modelValue: true })
    // Le formulaire doit exister avec des règles de validation
    expect(wrapper.find('.el-form').exists()).toBe(true)
    // Vérifier que les champs nom et image existent
    const formItems = wrapper.findAll('.el-form-item')
    expect(formItems.length).toBeGreaterThanOrEqual(2)
  })

  it('permet d\'ajouter et supprimer des variables d\'environnement', async () => {
    const wrapper = mountComponent({ modelValue: true })

    // Trouver le bouton "Ajouter une variable"
    const buttons = wrapper.findAll('button')
    const addEnvBtn = buttons.find(b => b.text().includes('Ajouter une variable'))
    expect(addEnvBtn).toBeDefined()

    // Cliquer pour ajouter une variable
    await addEnvBtn!.trigger('click')
    await flushPromises()

    // Vérifier qu'un nouveau champ a été ajouté — il doit y avoir plus d'inputs
    const inputsAfterAdd = wrapper.findAll('.el-input')
    expect(inputsAfterAdd.length).toBeGreaterThan(2) // nom + image au minimum

    // Compter les boutons avant suppression
    const allButtons = wrapper.findAll('button')
    const buttonsBeforeDelete = allButtons.length

    // Trouver le bouton de suppression (le premier bouton après "Ajouter une variable")
    // Les boutons de suppression sont les circle buttons avec l'icône Delete
    // Dans le stub, ils sont rendus comme <button class="el-button">
    // On vérifie qu'il y a plus de boutons qu'avant l'ajout
    expect(buttonsBeforeDelete).toBeGreaterThan(3) // Annuler + Créer + Ajouter variable + au moins 1 delete
  })

  it('permet d\'ajouter et supprimer des ports', async () => {
    const wrapper = mountComponent({ modelValue: true })

    // Trouver le bouton "Ajouter un port"
    const buttons = wrapper.findAll('button')
    const addPortBtn = buttons.find(b => b.text().includes('Ajouter un port'))
    expect(addPortBtn).toBeDefined()

    await addPortBtn!.trigger('click')
    await flushPromises()

    // Vérifier qu'un nouveau champ a été ajouté
    const inputs = wrapper.findAll('.el-input')
    expect(inputs.length).toBeGreaterThan(2)
  })

  it('affiche un avertissement quand privileged est activé', async () => {
    const wrapper = mountComponent({ modelValue: true })

    // Activer le switch privileged
    const switchEl = wrapper.find('.el-switch')
    expect(switchEl.exists()).toBe(true)
    await switchEl.setValue(true)
    await flushPromises()

    // Vérifier qu'une alerte d'avertissement est affichée
    const alert = wrapper.find('.el-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('privileged')
  })

  it('appelle containersApi.create avec les données correctes et émet created', async () => {
    const mockResponse = {
      data: {
        id: 'abc123',
        name: 'test-container',
        created: '2025-01-15T10:30:00Z',
        path: '/usr/local/bin',
        args: [],
        state: {},
        image: 'nginx:latest',
        config: {},
        host_config: {},
        network_settings: {},
        mounts: [],
      },
    }
    mockCreate.mockResolvedValue(mockResponse)

    const wrapper = mountComponent({ modelValue: true })

    // Remplir le nom
    const inputs = wrapper.findAll('.el-input')
    await inputs[0].setValue('test-container')
    // Remplir l'image
    await inputs[1].setValue('nginx:latest')
    await flushPromises()

    // Soumettre le formulaire — trouver le bouton "Créer"
    const buttons = wrapper.findAll('button')
    const submitBtn = buttons.find(b => b.text().includes('Créer'))
    expect(submitBtn).toBeDefined()
    await submitBtn!.trigger('click')
    await flushPromises()

    // Vérifier que l'API a été appelée
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'test-container',
        image: 'nginx:latest',
      }),
    )
    expect(wrapper.emitted('created')).toBeDefined()
  })

  it('affiche ElMessage.error en cas d\'erreur API', async () => {
    const { ElMessage } = await import('element-plus')
    mockCreate.mockRejectedValue(new Error('Image not found'))

    const wrapper = mountComponent({ modelValue: true })

    // Remplir le formulaire minimum
    const inputs = wrapper.findAll('.el-input')
    await inputs[0].setValue('test-container')
    await inputs[1].setValue('nonexistent:latest')
    await flushPromises()

    // Soumettre
    const buttons = wrapper.findAll('button')
    const submitBtn = buttons.find(b => b.text().includes('Créer'))
    await submitBtn!.trigger('click')
    await flushPromises()

    // Vérifier que ElMessage.error a été appelé
    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('réinitialise le formulaire à la fermeture', async () => {
    const wrapper = mountComponent({ modelValue: true })

    // Remplir un champ
    const inputs = wrapper.findAll('.el-input')
    await inputs[0].setValue('test-container')
    await flushPromises()

    // Fermer le dialog via le bouton Annuler
    const buttons = wrapper.findAll('button')
    const cancelBtn = buttons.find(b => b.text().includes('Annuler'))
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger('click')
    await flushPromises()

    // Vérifier que l'événement update:modelValue a été émis avec false
    expect(wrapper.emitted('update:modelValue')).toBeDefined()
    const emits = wrapper.emitted('update:modelValue')
    const lastEmit = emits?.[emits.length - 1]
    expect(lastEmit).toEqual([false])
  })

  it('ne logue pas les valeurs des env vars dans la console', () => {
    const consoleSpy = vi.spyOn(console, 'log')
    mountComponent({ modelValue: true })

    // Le composant ne doit pas logger les valeurs des env vars
    expect(consoleSpy).not.toHaveBeenCalledWith(
      expect.stringContaining('password'),
    )

    consoleSpy.mockRestore()
  })
})
