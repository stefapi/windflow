/**
 * Tests unitaires pour SidebarNav.vue
 * Liés à STORY-411 (Sidebar restructuration) et STORY-412 (Navigation 2 clics)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import SidebarNav from '@/components/SidebarNav.vue'

// Mock router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
    { path: '/containers', name: 'Containers', component: { template: '<div>Containers</div>' } },
    { path: '/volumes', name: 'Volumes', component: { template: '<div>Volumes</div>' } },
    { path: '/marketplace', name: 'Marketplace', component: { template: '<div>Marketplace</div>' } },
    { path: '/settings', name: 'Settings', component: { template: '<div>Settings</div>' } },
  ],
})

// Mock auth store
vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { username: 'testuser', email: 'test@example.com' },
    isAuthenticated: true,
    logout: vi.fn(),
  })),
}))

// Mock targets store
vi.mock('@/stores/targets', () => ({
  useTargetsStore: vi.fn(() => ({
    targets: [
      { id: '1', name: 'Target 1', type: 'docker' },
      { id: '2', name: 'Target 2', type: 'ssh' },
    ],
    activeTargetId: '1',
    setActiveTarget: vi.fn(),
  })),
}))

// Mock pluginNav store
vi.mock('@/stores/pluginNav', () => ({
  usePluginNavStore: vi.fn(() => ({
    hasPluginPages: false,
    pluginNavigationItems: [],
  })),
}))

describe('SidebarNav', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mountComponent = async () => {
    const wrapper = mount(SidebarNav, {
      global: {
        plugins: [router],
        stubs: {
          'el-dropdown': {
            template: '<div class="el-dropdown"><slot /></div>',
          },
          'el-icon': {
            template: '<span class="el-icon"><slot /></span>',
          },
        },
      },
    })
    await router.isReady()
    return wrapper
  }

  describe('AC1: Structure des sections', () => {
    it('affiche la section Dashboard', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Dashboard')
    })

    it('affiche la section INFRASTRUCTURE', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('INFRASTRUCTURE')
    })

    it('affiche la section STOCKAGE & RÉSEAU', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('STOCKAGE')
    })

    it('affiche la section MARKETPLACE', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('MARKETPLACE')
    })

    it('affiche la section ADMINISTRATION', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('ADMINISTRATION')
    })
  })

  describe('AC2: Labels de catégorie visibles', () => {
    it('affiche les labels en uppercase', async () => {
      const wrapper = await mountComponent()
      const categories = wrapper.findAll('.nav-category')

      categories.forEach(category => {
        const text = category.text()
        if (text) {
          expect(text).toBe(text.toUpperCase())
        }
      })
    })
  })

  describe('AC3: Section Plugins dynamique', () => {
    it('ne affiche pas la section Plugins par défaut', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      // Plugins section should not be visible when no plugins registered
      expect(html).not.toContain('PLUGINS')
    })
  })

  describe('AC5: Sélecteur de target actif', () => {
    it('affiche le sélecteur de target', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      // Le sélecteur de target est présent (indicateur ⚪ pour "Aucun target")
      expect(html).toContain('Aucun target')
    })
  })

  describe('AC6: Utilisateur connecté affiché', () => {
    it('affiche le nom d\'utilisateur', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('testuser')
    })
  })

  describe('Navigation', () => {
    it('rend les éléments de navigation infrastructure', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Containers')
      expect(html).toContain('Targets')
      expect(html).toContain('Stacks')
      // Note: Deployments n'est plus dans la sidebar (STORY-411)
    })

    it('rend les éléments de navigation stockage', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Volumes')
      expect(html).toContain('Networks')
      expect(html).toContain('Images')
    })

    it('rend les éléments de navigation marketplace', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Marketplace')
    })

    it('rend les éléments de navigation administration', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Settings')
      expect(html).toContain('Audit')
    })
  })
})
