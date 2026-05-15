/**
 * SystemInfo.vue Unit Tests
 * STORY-020: Page d'informations système Docker
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SystemInfo from '@/views/SystemInfo.vue'

// Mock data
const mockVersionData = {
  version: '24.0.7',
  api_version: '1.43',
  min_api_version: '1.12',
  git_commit: 'afdd53b',
  go_version: 'go1.20.10',
  os: 'linux',
  arch: 'amd64',
  kernel_version: '6.1.0-test',
  build_time: '2023-10-26T14:00:00.000000000+00:00',
}

const mockPingAvailable = {
  available: true,
  message: 'Docker is available',
}

const mockPingUnavailable = {
  available: false,
  message: 'Docker is not available',
}

// Mock API
const mockVersion = vi.fn()
const mockPing = vi.fn()

vi.mock('@/services/api', () => ({
  dockerSystemApi: {
    version: (...args: unknown[]) => mockVersion(...args),
    ping: (...args: unknown[]) => mockPing(...args),
  },
}))

// Helper to mount component
function mountComponent() {
  return mount(SystemInfo, {
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('SystemInfo.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockVersion.mockResolvedValue({ data: mockVersionData })
    mockPing.mockResolvedValue({ data: mockPingAvailable })
  })

  it('affiche le skeleton pendant le chargement', async () => {
    // Make API calls hang so loading stays true
    mockVersion.mockReturnValue(new Promise(() => {}))
    mockPing.mockReturnValue(new Promise(() => {}))

    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="loading-skeleton"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="system-info-page"]').exists()).toBe(true)
  })

  it('affiche les informations de version quand les données sont chargées', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="version-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="connectivity-card"]').exists()).toBe(true)
  })

  it('affiche la version Docker', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="version-value"]').text()).toBe('24.0.7')
  })

  it('affiche l API version', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="api-version-value"]').text()).toBe('1.43')
  })

  it('affiche la version Go', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="go-version-value"]').text()).toBe('go1.20.10')
  })

  it('affiche l OS et l architecture', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="os-value"]').text()).toBe('linux')
    expect(wrapper.find('[data-testid="arch-value"]').text()).toBe('amd64')
  })

  it('affiche le kernel et le build time', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="kernel-value"]').text()).toBe('6.1.0-test')
    expect(wrapper.find('[data-testid="build-time-value"]').text()).toBe(
      '2023-10-26T14:00:00.000000000+00:00',
    )
  })

  it('affiche l indicateur de connectivite disponible', async () => {
    mockPing.mockResolvedValue({ data: mockPingAvailable })

    const wrapper = mountComponent()
    await flushPromises()

    const tag = wrapper.find('[data-testid="ping-available"]')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toContain('Docker is available')
  })

  it('affiche l indicateur de connectivite indisponible', async () => {
    mockPing.mockResolvedValue({ data: mockPingUnavailable })

    const wrapper = mountComponent()
    await flushPromises()

    const tag = wrapper.find('[data-testid="ping-unavailable"]')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toContain('Docker is not available')
  })

  it('affiche un message d erreur si l API echoue', async () => {
    mockVersion.mockRejectedValue(new Error('Network error'))
    mockPing.mockRejectedValue(new Error('Network error'))

    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('[data-testid="error-alert"]').exists()).toBe(true)
  })

  it('appelle fetchData au montage du composant', async () => {
    mountComponent()
    await flushPromises()

    expect(mockVersion).toHaveBeenCalledTimes(1)
    expect(mockPing).toHaveBeenCalledTimes(1)
  })
})
