/**
 * Tests unitaires pour Login.vue
 * STORY-471 : Refonte Page Login avec Design Unifié et Nouveau Logo
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'

// Mock router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
    { path: '/login', name: 'Login', component: { template: '<div>Login</div>' } },
  ],
})

// Mock auth store
const mockLogin = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    loading: false,
    login: mockLogin,
  })),
}))

describe('Login.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockLogin.mockReset()
  })

  const mountComponent = async () => {
    const wrapper = mount(Login, {
      global: {
        plugins: [router],
        stubs: {
          WindFlowLogo: {
            template: '<div class="windflow-logo-stub" data-testid="windflow-logo"></div>',
          },
          'el-form': {
            template: '<form @submit.prevent="$emit(\'submit\')"><slot /></form>',
          },
          'el-form-item': {
            template: '<div class="el-form-item"><slot /></div>',
          },
          'el-input': {
            template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" :placeholder="placeholder" :type="type" :disabled="disabled" />',
            props: ['modelValue', 'placeholder', 'type', 'disabled', 'prefixIcon', 'size', 'showPassword'],
          },
        },
      },
    })
    await router.isReady()
    return wrapper
  }

  describe('AC-1: Thème sombre unifié', () => {
    it('rend la page avec la classe login-page (fond sombre)', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.login-page').exists()).toBe(true)
    })

    it('contient la carte de login avec fond semi-transparent', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.login-card').exists()).toBe(true)
    })

    it('affiche les particules de fond', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.findAll('.login-particle').length).toBe(3)
    })
  })

  describe('AC-2: Logo WindFlow', () => {
    it('affiche le composant WindFlowLogo', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('[data-testid="windflow-logo"]').exists()).toBe(true)
    })

    it('affiche le titre "WindFlow"', async () => {
      const wrapper = await mountComponent()
      const title = wrapper.find('.login-card-title')
      expect(title.exists()).toBe(true)
      expect(title.text()).toBe('WindFlow')
    })

    it('affiche le sous-titre', async () => {
      const wrapper = await mountComponent()
      const subtitle = wrapper.find('.login-card-subtitle')
      expect(subtitle.exists()).toBe(true)
      expect(subtitle.text()).toBe('Container Deployment Platform')
    })
  })

  describe('AC-3: Formulaire de login', () => {
    it('rend le formulaire de login', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.login-card-form').exists()).toBe(true)
    })

    it('contient un champ username', async () => {
      const wrapper = await mountComponent()
      const inputs = wrapper.findAll('input')
      const usernameInput = inputs.find(i => i.attributes('placeholder') === 'Username')
      expect(usernameInput).toBeTruthy()
    })

    it('contient un champ password', async () => {
      const wrapper = await mountComponent()
      const inputs = wrapper.findAll('input')
      const passwordInput = inputs.find(i => i.attributes('placeholder') === 'Password')
      expect(passwordInput).toBeTruthy()
    })

    it('contient un bouton de soumission', async () => {
      const wrapper = await mountComponent()
      const btn = wrapper.find('.login-btn')
      expect(btn.exists()).toBe(true)
      expect(btn.text()).toContain('Sign In')
    })
  })

  describe('AC-5: Structure de la page', () => {
    it('contient le header avec logo', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.login-card-header').exists()).toBe(true)
    })

    it('contient le footer avec version', async () => {
      const wrapper = await mountComponent()
      const footer = wrapper.find('.login-card-footer')
      expect(footer.exists()).toBe(true)
      expect(footer.text()).toContain('v1.0')
    })
  })

  describe('Fonctionnement du formulaire', () => {
    it('le bouton submit a le type "submit"', async () => {
      const wrapper = await mountComponent()
      const btn = wrapper.find('.login-btn')
      expect(btn.attributes('type')).toBe('submit')
    })

    it('les champs sont liés au modèle réactif', async () => {
      const wrapper = await mountComponent()

      const inputs = wrapper.findAll('input')
      await inputs[0].setValue('admin')
      await inputs[1].setValue('password123')

      // Vérifie que les valeurs sont capturées dans le formulaire
      expect(inputs[0].element.value).toBe('admin')
      expect(inputs[1].element.value).toBe('password123')
    })

    it('le bouton est désactivé pendant le chargement', async () => {
      // Re-mock avec loading=true
      const { useAuthStore } = await import('@/stores/auth')
      vi.mocked(useAuthStore).mockReturnValue({
        loading: true,
        login: mockLogin,
      } as ReturnType<typeof useAuthStore>)

      const wrapper = await mountComponent()
      const btn = wrapper.find('.login-btn')
      expect(btn.attributes('disabled')).toBeDefined()
      expect(btn.classes()).toContain('login-btn-loading')
    })
  })
})
