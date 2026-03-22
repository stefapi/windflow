/**
 * Tests unitaires pour StubPage.vue
 * Liés à STORY-461 (Vues stubs Volumes, Networks, Images)
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import StubPage from '@/components/ui/StubPage.vue'
import { FolderOpened, Link, PictureFilled, Monitor, ShoppingCart, Grid, DocumentChecked } from '@element-plus/icons-vue'

import { ElCard, ElTag, ElButton, ElIcon } from 'element-plus'

// Mock router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } },
    { path: '/volumes', name: 'Volumes', component: { template: '<div>Volumes</div>' } },
    { path: '/networks', name: 'Networks', component: { template: '<div>Networks</div>' } },
    { path: '/images', name: 'Images', component: { template: '<div>Images</div>' } },
    { path: '/vms', name: 'VMs', component: { template: '<div>VMs</div>' } },
    { path: '/marketplace', name: 'Marketplace', component: { template: '<div>Marketplace</div>' } },
    { path: '/plugins', name: 'Plugins', component: { template: '<div>Plugins</div>' } },
    { path: '/audit', name: 'Audit', component: { template: '<div>Audit</div>' } },
  ],
})

describe('StubPage.vue', () => {
  const mountComponent = async (props: Record<string, unknown> = {}) => {
    const wrapper = mount(StubPage, {
      props: {
        title: 'Test Title',
        description: 'Test description',
        icon: FolderOpened,
        ...props,
      },
      global: {
        plugins: [router],
        components: {
          ElCard,
          ElTag,
          ElButton,
          ElIcon,
        },
      },
    })
    await router.isReady()
    return wrapper
  }

  describe('Rendu de base', () => {
    it('affiche le titre', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.text()).toContain('Test Title')
    })

    it('affiche la description', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.text()).toContain('Test description')
    })

    it('affiche le tag de version par défaut', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.text()).toContain('Prévu pour v1.1 — Phase 2')
    })

    it('affiche un tag de version personnalisé', async () => {
      const wrapper = await mountComponent({ version: 'v2.0' })
      expect(wrapper.text()).toContain('Prévu pour v2.0')
    })

    it('affiche le bouton de retour au Dashboard', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.text()).toContain('Retour au Dashboard')
    })
  })

  describe('Props', () => {
    it('accepte l\'icône FolderOpened', async () => {
      const wrapper = await mountComponent({ icon: FolderOpened })
      expect(wrapper.findComponent(FolderOpened)).toBeTruthy()
    })

    it('accepte l\'icône Link', async () => {
      const wrapper = await mountComponent({ icon: Link })
      expect(wrapper.findComponent(Link)).toBeTruthy()
    })

    it('accepte l\'icône PictureFilled', async () => {
      const wrapper = await mountComponent({ icon: PictureFilled })
      expect(wrapper.findComponent(PictureFilled)).toBeTruthy()
    })

    it('accepte l\'icône Monitor', async () => {
      const wrapper = await mountComponent({ icon: Monitor })
      expect(wrapper.findComponent(Monitor)).toBeTruthy()
    })

    it('accepte l\'icône ShoppingCart', async () => {
      const wrapper = await mountComponent({ icon: ShoppingCart })
      expect(wrapper.findComponent(ShoppingCart)).toBeTruthy()
    })

    it('accepte l\'icône Grid', async () => {
      const wrapper = await mountComponent({ icon: Grid })
      expect(wrapper.findComponent(Grid)).toBeTruthy()
    })

    it('accepte l\'icône DocumentChecked', async () => {
      const wrapper = await mountComponent({ icon: DocumentChecked })
      expect(wrapper.findComponent(DocumentChecked)).toBeTruthy()
    })
  })

  describe('Structure CSS', () => {
    it('a les classes CSS appropriées', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.stub-page').exists()).toBe(true)
      expect(wrapper.find('.stub-card').exists()).toBe(true)
      expect(wrapper.find('.stub-content').exists()).toBe(true)
      expect(wrapper.find('.stub-icon').exists()).toBe(true)
      expect(wrapper.find('.stub-title').exists()).toBe(true)
      expect(wrapper.find('.stub-description').exists()).toBe(true)
      expect(wrapper.find('.stub-badge').exists()).toBe(true)
    })
  })
})
