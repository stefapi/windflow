/**
 * ImageDetail.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ImageDetail from '@/views/ImageDetail.vue'
import type { ImageDetailResponse } from '@/types/api'

// Mock image detail data
const mockImageDetail: ImageDetailResponse = {
  id: 'sha256:abc123def456789abc123def456789abc123def456789abc123def456789abcd',
  repoTags: ['nginx:latest', 'nginx:1.25'],
  repoDigests: ['nginx@sha256:abc123'],
  created: '2025-01-15T10:30:00Z',
  size: 187600000,
  virtualSize: 187600000,
  labels: { maintainer: 'NGINX Docker Maintainers' },
  architecture: 'amd64',
  os: 'linux',
  author: '',
  cmd: ['nginx', '-g', 'daemon off;'],
  entrypoint: ['/docker-entrypoint.sh'],
  env: ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin', 'NGINX_VERSION=1.25.3'],
  exposedPorts: { '80/tcp': {} },
  dockerVersion: '24.0.7',
  config: null,
}

// Mock imagesApi.get
const mockGet = vi.fn()
vi.mock('@/services/api', () => ({
  imagesApi: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}))

// Mock vue-router
const mockPush = vi.fn()
const mockRouteParams = { id: 'sha256:abc123def456789abc123def456789abc123def456789abc123def456789abcd' }
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: mockRouteParams,
  }),
  useRouter: () => ({
    push: mockPush,
  }),
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
    },
  }
})

// Helper to mount component
function mountComponent() {
  return mount(ImageDetail, {
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('ImageDetail.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockResolvedValue({ data: mockImageDetail })
  })

  it('displays image detail information', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    // Check image ID is displayed
    expect(wrapper.text()).toContain('sha256:abc123def456789abc123def456789abc123def456789abc123def456789abcd')

    // Check tags are displayed
    expect(wrapper.text()).toContain('nginx:latest')
    expect(wrapper.text()).toContain('nginx:1.25')

    // Check formatted size
    expect(wrapper.text()).toContain('178.9 MB')

    // Check architecture and OS
    expect(wrapper.text()).toContain('amd64')
    expect(wrapper.text()).toContain('linux')
  })

  it('displays image configuration details', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    // Check command
    expect(wrapper.text()).toContain('nginx -g daemon off;')

    // Check entrypoint
    expect(wrapper.text()).toContain('/docker-entrypoint.sh')

    // Check docker version
    expect(wrapper.text()).toContain('24.0.7')
  })

  it('displays environment variables', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('PATH')
    expect(wrapper.text()).toContain('/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin')
    expect(wrapper.text()).toContain('NGINX_VERSION')
    expect(wrapper.text()).toContain('1.25.3')
  })

  it('displays exposed ports', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('80/tcp')
  })

  it('displays labels', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('maintainer')
    expect(wrapper.text()).toContain('NGINX Docker Maintainers')
  })

  it('shows error message when image is not found', async () => {
    const { ElMessage } = await import('element-plus')
    mockGet.mockRejectedValue(new Error('Image not found'))

    const wrapper = mountComponent()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
    expect(wrapper.find('.el-empty').exists()).toBe(true)
  })

  it('navigates back to Images when Retour button is clicked', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const backButton = wrapper.findAll('.el-button').find(b => b.text().includes('Retour'))
    expect(backButton).toBeDefined()
    await backButton!.trigger('click')
    await flushPromises()

    expect(mockPush).toHaveBeenCalledWith({ name: 'Images' })
  })

  it('shows loading state while fetching', async () => {
    mockGet.mockReturnValue(new Promise(() => {}))

    const wrapper = mountComponent()

    const vm = wrapper.vm as unknown as { loading: boolean }
    expect(vm.loading).toBe(true)
  })
})
