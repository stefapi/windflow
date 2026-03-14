/**
 * Tests unitaires pour SidebarNav.vue
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import SidebarNav from '@/components/SidebarNav.vue'
import { usePluginNavStore } from '@/stores/pluginNav'

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

describe('SidebarNav', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mountComponent = async () => {
    const wrapper = mount(SidebarNav, {
      global: {
        plugins: [router],
        stubs: {
          'el-menu': {
            template: '<div class="el-menu"><slot /></div>',
          },
          'el-sub-menu': {
            template: '<div class="el-sub-menu"><slot /></div>',
            props: ['index'],
          },
          'el-menu-item': {
            template: '<div class="el-menu-item"><slot /></div>',
            props: ['index', 'route'],
          },
          'el-menu-item-group': {
            template: '<div class="el-menu-item-group"><slot /></div>',
            props: ['title'],
          },
          'el-dropdown': {
            template: '<div class="el-dropdown"><slot /></div>',
          },
          'el-dropdown-menu': {
            template: '<div class="el-dropdown-menu"><slot /></div>',
          },
          'el-dropdown-item': {
            template: '<div class="el-dropdown-item"><slot /></div>',
          },
          'el-avatar': {
            template: '<div class="el-avatar"><slot /></div>',
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

    it('affiche la section Plugins quand des plugins sont enregistrés', async () => {
      const pluginNavStore = usePluginNavStore()
      pluginNavStore.registerPluginPages({
        id: 'test-plugin',
        name: 'Test Plugin',
        pages: [
          { id: 'page1', label: 'Page 1', route: '/plugins/test/page1', icon: 'Document' },
        ],
      })

      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('PLUGINS')
    })
  })

  describe('AC4: Store usePluginNavStore', () => {
    it('utilise le store pour injecter les pages de plugin', async () => {
      const pluginNavStore = usePluginNavStore()

      pluginNavStore.registerPluginPages({
        id: 'plugin-1',
        name: 'Plugin 1',
        pages: [
          { id: 'p1', label: 'Page 1', route: '/p1', icon: 'Document' },
        ],
      })

      expect(pluginNavStore.hasPluginPages).toBe(true)
      expect(pluginNavStore.pluginNavigationItems).toHaveLength(1)
    })

    it('permet de désenregistrer les pages de plugin', async () => {
      const pluginNavStore = usePluginNavStore()

      pluginNavStore.registerPluginPages({
        id: 'plugin-2',
        name: 'Plugin 2',
        pages: [{ id: 'p2', label: 'Page 2', route: '/p2', icon: 'Document' }],
      })

      expect(pluginNavStore.hasPluginPages).toBe(true)

      pluginNavStore.unregisterPluginPages('plugin-2')
      expect(pluginNavStore.hasPluginPages).toBe(false)
    })
  })

  describe('AC5: Sélecteur de target actif', () => {
    it('affiche le sélecteur de target', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('🎯')
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
      expect(html).toContain('Deployments')
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
