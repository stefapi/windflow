import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DockerInfoWidget from '@/components/dashboard/DockerInfoWidget.vue'
import type { SystemInfoResponse } from '@/types/api'

// Mock the API service
const mockInfo = vi.fn()
vi.mock('@/services/api', () => ({
  dockerSystemApi: {
    info: () => mockInfo(),
  },
}))

const createSystemInfo = (overrides?: Partial<SystemInfoResponse>): SystemInfoResponse => ({
  id: 'ABCD1234',
  name: 'docker-desktop',
  server_version: '24.0.7',
  containers: 10,
  containers_running: 5,
  containers_paused: 1,
  containers_stopped: 4,
  images: 25,
  driver: 'overlay2',
  docker_root_dir: '/var/lib/docker',
  kernel_version: '6.1.0-test',
  operating_system: 'Docker Desktop',
  os_type: 'linux',
  architecture: 'x86_64',
  cpus: 8,
  memory: 17179869184, // 16 Go
  ...overrides,
})

const stubs = {
  'el-card': {
    template: '<div class="el-card" data-testid="docker-info-widget"><slot name="header" /><slot /></div>',
  },
  'el-icon': { template: '<i class="el-icon"><slot /></i>' },
  'el-skeleton': { template: '<div class="el-skeleton" />' },
  'el-alert': {
    template: '<div class="el-alert"><slot /></div>',
    props: ['type', 'closable', 'showIcon'],
  },
  'el-empty': {
    template: '<div class="el-empty">{{ description }}</div>',
    props: ['description', 'imageSize'],
  },
  'el-tag': {
    template: '<span class="el-tag" :data-type="type"><slot /></span>',
    props: ['type', 'size'],
  },
}

describe('DockerInfoWidget', () => {
  beforeEach(() => {
    mockInfo.mockReset()
  })

  it('affiche le skeleton pendant le chargement', async () => {
    // Create a promise that won't resolve immediately
    mockInfo.mockReturnValue(new Promise(() => {}))

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    // Wait for onMounted to trigger fetchInfo and set isLoading = true
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-skeleton').exists()).toBe(true)
  })

  it('affiche les informations système quand les données sont chargées', async () => {
    const data = createSystemInfo()
    mockInfo.mockResolvedValue({ data })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    // Wait for the async fetchInfo to complete
    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="docker-info-widget"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Docker System')
  })

  it('affiche la version Docker', async () => {
    const data = createSystemInfo()
    mockInfo.mockResolvedValue({ data })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="docker-version"]').text()).toBe('24.0.7')
  })

  it('affiche les compteurs de containers running/paused/stopped', async () => {
    const data = createSystemInfo()
    mockInfo.mockResolvedValue({ data })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const containersEl = wrapper.find('[data-testid="docker-containers"]')
    expect(containersEl.exists()).toBe(true)
    expect(containersEl.text()).toContain('10')
    expect(containersEl.text()).toContain('5 running')
    expect(containersEl.text()).toContain('1 paused')
    expect(containersEl.text()).toContain('4 stopped')
  })

  it('affiche le nombre d images', async () => {
    const data = createSystemInfo()
    mockInfo.mockResolvedValue({ data })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="docker-images"]').text()).toBe('25')
  })

  it('affiche l OS et l architecture', async () => {
    const data = createSystemInfo()
    mockInfo.mockResolvedValue({ data })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="docker-os"]').text()).toBe('Docker Desktop')
    expect(wrapper.find('[data-testid="docker-architecture"]').text()).toBe('x86_64')
  })

  it('affiche la mémoire formatée correctement', async () => {
    const data = createSystemInfo({ memory: 17179869184 }) // 16 Go
    mockInfo.mockResolvedValue({ data })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const memoryEl = wrapper.find('[data-testid="docker-memory"]')
    expect(memoryEl.exists()).toBe(true)
    expect(memoryEl.text()).toContain('Go')
  })

  it('affiche un message d erreur si l API échoue', async () => {
    mockInfo.mockRejectedValue(new Error('Network error'))

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-alert').exists()).toBe(true)
    expect(wrapper.text()).toContain('Network error')
  })

  it('affiche l état empty si aucune donnée', async () => {
    mockInfo.mockResolvedValue({ data: null })

    const wrapper = mount(DockerInfoWidget, {
      global: { stubs },
    })

    await vi.dynamicImportSettled()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.el-empty').exists()).toBe(true)
  })

  it('appelle fetchInfo au montage du composant', async () => {
    mockInfo.mockResolvedValue({ data: createSystemInfo() })

    mount(DockerInfoWidget, {
      global: { stubs },
    })

    expect(mockInfo).toHaveBeenCalledTimes(1)
  })
})
