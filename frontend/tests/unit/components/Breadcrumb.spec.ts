import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import Breadcrumb from '@/components/Breadcrumb.vue'

// Routes de test
const routes = [
  { path: '/', name: 'Dashboard' },
  { path: '/compute', name: 'Compute' },
  { path: '/deployments', name: 'Deployments' },
  { path: '/deployments/:id', name: 'DeploymentDetail' },
  { path: '/workflows', name: 'Workflows' },
  { path: '/workflows/:id/edit', name: 'WorkflowEditor' },
  { path: '/settings', name: 'Settings' },
]

const createTestRouter = async (initialPath = '/') => {
  const router = createRouter({
    history: createWebHistory(),
    routes,
  })
  await router.push(initialPath)
  await router.isReady()
  return router
}

// Stubs pour les composants Element Plus
const ElBreadcrumb = {
  template: '<div class="el-breadcrumb"><slot /></div>',
}

const ElBreadcrumbItem = {
  template: '<span class="el-breadcrumb-item"><slot /></span>',
}

describe('Breadcrumb', () => {
  it('affiche Dashboard sur la page d\'accueil', async () => {
    const router = await createTestRouter('/')
    const wrapper = mount(Breadcrumb, {
      global: {
        plugins: [router],
        stubs: {
          'el-breadcrumb': ElBreadcrumb,
          'el-breadcrumb-item': ElBreadcrumbItem,
        },
      },
    })

    const items = wrapper.findAll('.el-breadcrumb-item')
    expect(items.length).toBe(1)
    expect(items[0].text()).toContain('Dashboard')
  })

  it('affiche le bon chemin pour Compute', async () => {
    const router = await createTestRouter('/compute')
    const wrapper = mount(Breadcrumb, {
      global: {
        plugins: [router],
        stubs: {
          'el-breadcrumb': ElBreadcrumb,
          'el-breadcrumb-item': ElBreadcrumbItem,
        },
      },
    })

    const items = wrapper.findAll('.el-breadcrumb-item')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('Dashboard')
    expect(items[1].text()).toContain('Compute')
  })

  it('affiche le bon chemin pour Deployments', async () => {
    const router = await createTestRouter('/deployments')
    const wrapper = mount(Breadcrumb, {
      global: {
        plugins: [router],
        stubs: {
          'el-breadcrumb': ElBreadcrumb,
          'el-breadcrumb-item': ElBreadcrumbItem,
        },
      },
    })

    const items = wrapper.findAll('.el-breadcrumb-item')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('Dashboard')
    expect(items[1].text()).toContain('Déploiements')
  })

  it('affiche le bon chemin pour une page de détail', async () => {
    const router = await createTestRouter('/deployments/123')
    const wrapper = mount(Breadcrumb, {
      global: {
        plugins: [router],
        stubs: {
          'el-breadcrumb': ElBreadcrumb,
          'el-breadcrumb-item': ElBreadcrumbItem,
        },
      },
    })

    const items = wrapper.findAll('.el-breadcrumb-item')
    expect(items.length).toBe(3)
    expect(items[0].text()).toContain('Dashboard')
    expect(items[1].text()).toContain('Déploiements')
    expect(items[2].text()).toContain('Détail Déploiement')
  })

  it('affiche le bon chemin pour Settings', async () => {
    const router = await createTestRouter('/settings')
    const wrapper = mount(Breadcrumb, {
      global: {
        plugins: [router],
        stubs: {
          'el-breadcrumb': ElBreadcrumb,
          'el-breadcrumb-item': ElBreadcrumbItem,
        },
      },
    })

    const items = wrapper.findAll('.el-breadcrumb-item')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('Dashboard')
    expect(items[1].text()).toContain('Paramètres')
  })
})
