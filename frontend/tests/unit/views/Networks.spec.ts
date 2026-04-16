/**
 * Networks.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import Networks from '@/views/Networks.vue'
import type { NetworkResponse } from '@/types/api'

// Mock data
const mockNetworks: NetworkResponse[] = [
  {
    id: 'abc123def456789',
    name: 'bridge',
    driver: 'bridge',
    scope: 'local',
    internal: false,
    attachable: false,
    ingress: false,
    created: '2025-01-15T10:30:00Z',
    subnet: '172.17.0.0/16',
    gateway: '172.17.0.1',
  },
  {
    id: 'def456abc789012',
    name: 'my-internal-net',
    driver: 'bridge',
    scope: 'local',
    internal: true,
    attachable: true,
    ingress: false,
    created: '2025-01-14T08:00:00Z',
    subnet: '172.18.0.0/16',
    gateway: '172.18.0.1',
  },
  {
    id: 'ghi789jkl012345',
    name: 'host',
    driver: 'host',
    scope: 'local',
    internal: false,
    attachable: false,
    ingress: false,
    created: '2025-01-13T12:00:00Z',
    subnet: '',
    gateway: '',
  },
]

// Mock networksApi.list
const mockList = vi.fn()
vi.mock('@/services/api', () => ({
  networksApi: {
    list: (...args: unknown[]) => mockList(...args),
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

// Helper to mount component
function mountComponent() {
  return mount(Networks, {
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('Networks.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: mockNetworks })
  })

  it('affiche les réseaux dans le tableau après chargement', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(3)
  })

  it('affiche le nom, driver et scope de chaque réseau', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('bridge')
    expect(wrapper.text()).toContain('my-internal-net')
    expect(wrapper.text()).toContain('host')
    expect(wrapper.text()).toContain('local')
  })

  it("affiche l'ID tronqué avec 12 caractères", async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('abc123def456')
    expect(wrapper.text()).not.toContain('abc123def456789')
  })

  it('affiche le subnet et la gateway quand présents', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('172.17.0.0/16')
    expect(wrapper.text()).toContain('172.17.0.1')
    expect(wrapper.text()).toContain('172.18.0.0/16')
    expect(wrapper.text()).toContain('172.18.0.1')
  })

  it("n'affiche pas subnet/gateway quand vides", async () => {
    const wrapper = mountComponent()
    await flushPromises()

    // Le réseau host n'a pas de subnet/gateway — on vérifie le tiret
    const cells = wrapper.findAll('td')
    const hostRowCells = cells.filter((c) => c.text() === '—')
    expect(hostRowCells.length).toBeGreaterThanOrEqual(2)
  })

  it('affiche un badge Interne pour les réseaux internes', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const tags = wrapper.findAll('.el-tag')
    const internalTags = tags.filter((t) => t.text() === 'Interne')
    expect(internalTags.length).toBe(1)
  })

  it('affiche un badge Externe pour les réseaux externes', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const tags = wrapper.findAll('.el-tag')
    const externalTags = tags.filter((t) => t.text() === 'Externe')
    expect(externalTags.length).toBe(2)
  })

  it('filtre les réseaux par nom', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const input = wrapper.find('input')
    // Filtre sur "host" — seul le réseau "host" (driver: "host") matche
    await input.setValue('host')
    await flushPromises()

    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('host')
    expect(wrapper.text()).not.toContain('my-internal-net')
    expect(wrapper.text()).not.toContain('bridge')
  })

  it('affiche el-empty si la liste est vide', async () => {
    mockList.mockResolvedValue({ data: [] })

    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('.el-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('Aucun réseau trouvé')
  })

  it('affiche ElMessage.error quand le chargement échoue', async () => {
    const { ElMessage } = await import('element-plus')
    mockList.mockRejectedValue(new Error('Network error'))

    mountComponent()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('test_no_sensitive_data_in_dom', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.html()).not.toContain('Bearer')
    expect(wrapper.html()).not.toContain('token')
    expect(wrapper.html()).not.toContain('password')
    expect(wrapper.html()).not.toContain('secret')
  })
})
