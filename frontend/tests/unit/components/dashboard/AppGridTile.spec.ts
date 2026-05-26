import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import AppGridTile from '@/components/dashboard/AppGridTile.vue'
import type { AppCardData } from '@/components/compute/helpers'

// Factory for AppCardData
function createAppCard(overrides: Partial<AppCardData> = {}): AppCardData {
  return {
    id: 'app-1',
    name: 'nginx-web',
    displayName: 'Nginx',
    version: '1.26',
    icon: '🌐',
    domain: 'https://localhost:8080',
    status: 'running',
    statusLabel: 'En cours',
    statusColor: 'success',
    ram: '128 MB',
    cpuPercent: 2.5,
    category: 'managed',
    servicesTotal: 1,
    servicesRunning: 1,
    targetName: 'localhost',
    updateAvailable: false,
    containerId: 'container-abc123',
    labels: {},
    ...overrides,
  }
}

// Router mock
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div />' } },
    { path: '/containers/:id', component: { template: '<div />' } },
  ],
})

function mountTile(app: AppCardData) {
  return mount(AppGridTile, {
    props: { app },
    global: {
      plugins: [router],
      stubs: {},
    },
  })
}

describe('AppGridTile', () => {
  it('affiche l\'icône, le nom et le statut de l\'app', () => {
    const app = createAppCard()
    const wrapper = mountTile(app)

    expect(wrapper.find('[data-testid="app-grid-tile-icon"]').text()).toBe('🌐')
    expect(wrapper.find('[data-testid="app-grid-tile-name"]').text()).toBe('Nginx')
    expect(wrapper.find('[data-testid="app-grid-tile-status"]').text()).toBe('En cours')
  })

  it('affiche le domaine quand disponible', () => {
    const app = createAppCard({ domain: 'https://example.com' })
    const wrapper = mountTile(app)

    expect(wrapper.find('[data-testid="app-grid-tile-domain"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="app-grid-tile-domain"]').text()).toBe('https://example.com')
  })

  it('n\'affiche pas le domaine quand absent', () => {
    const app = createAppCard({ domain: null })
    const wrapper = mountTile(app)

    expect(wrapper.find('[data-testid="app-grid-tile-domain"]').exists()).toBe(false)
  })

  it('applique la classe de couleur verte pour le statut running', () => {
    const app = createAppCard({ statusColor: 'success' })
    const wrapper = mountTile(app)

    const dot = wrapper.find('[data-testid="app-grid-tile-dot"]')
    expect(dot.classes()).toContain('bg-green-500')
  })

  it('applique la classe de couleur rouge pour le statut stopped', () => {
    const app = createAppCard({ statusColor: 'danger' })
    const wrapper = mountTile(app)

    const dot = wrapper.find('[data-testid="app-grid-tile-dot"]')
    expect(dot.classes()).toContain('bg-red-500')
  })

  it('applique la classe de couleur jaune pour le statut paused', () => {
    const app = createAppCard({ statusColor: 'warning' })
    const wrapper = mountTile(app)

    const dot = wrapper.find('[data-testid="app-grid-tile-dot"]')
    expect(dot.classes()).toContain('bg-yellow-500')
  })

  it('applique la classe de couleur bleue par défaut', () => {
    const app = createAppCard({ statusColor: 'info' })
    const wrapper = mountTile(app)

    const dot = wrapper.find('[data-testid="app-grid-tile-dot"]')
    expect(dot.classes()).toContain('bg-blue-400')
  })

  it('navigue vers le détail app au clic', async () => {
    const pushSpy = vi.spyOn(router, 'push')
    const app = createAppCard({ containerId: 'container-xyz' })
    const wrapper = mountTile(app)

    await wrapper.find('[data-testid="app-grid-tile"]').trigger('click')

    expect(pushSpy).toHaveBeenCalledWith('/containers/container-xyz')
  })

  it('affiche le label de statut Mode App', () => {
    const app = createAppCard({ statusLabel: 'Arrêté' })
    const wrapper = mountTile(app)

    expect(wrapper.find('[data-testid="app-grid-tile-status"]').text()).toBe('Arrêté')
  })
})
