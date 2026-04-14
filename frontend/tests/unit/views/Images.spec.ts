/**
 * Images.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import Images from '@/views/Images.vue'
import type { ImageResponse } from '@/types/api'

// Mock data
const mockImages: ImageResponse[] = [
  {
    id: 'sha256:abc123def456789abc123def456789abc123def456789abc123def456789abcd',
    repoTags: ['nginx:latest', 'nginx:1.25'],
    repoDigests: ['nginx@sha256:abc123'],
    created: '2025-01-15T10:30:00Z',
    size: 187600000,
    virtualSize: 187600000,
    labels: {},
  },
  {
    id: 'sha256:fed456cba789abc123def456789abc123def456789abc123def456789abcdef',
    repoTags: ['postgres:16'],
    repoDigests: ['postgres@sha256:fed456'],
    created: '2025-01-14T08:00:00Z',
    size: 432100000,
    virtualSize: 432100000,
    labels: { maintainer: 'PG Docker' },
  },
  {
    id: 'sha256:111222333444555666777888999000aaabbbcccdddeeefff000111222333444',
    repoTags: [],
    repoDigests: [],
    created: '2025-01-13T12:00:00Z',
    size: 50000000,
    virtualSize: 50000000,
    labels: {},
  },
]

// Mock imagesApi.list, pull, remove
const mockList = vi.fn()
const mockPull = vi.fn()
const mockRemove = vi.fn()
vi.mock('@/services/api', () => ({
  imagesApi: {
    list: (...args: unknown[]) => mockList(...args),
    pull: (...args: unknown[]) => mockPull(...args),
    remove: (...args: unknown[]) => mockRemove(...args),
  },
}))

// Mock ElMessage.error, ElMessage.success, ElMessage.warning + ElMessageBox.confirm
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
    ElMessageBox: {
      confirm: vi.fn(),
    },
  }
})

// Helper to mount component
function mountComponent() {
  return mount(Images, {
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('Images.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: mockImages })
  })

  it('displays images in the table after loading', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    // Check table rows (one per image)
    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(3)

    // Check first image ID is truncated
    expect(wrapper.text()).toContain('sha256:abc12...')

    // Check tags are displayed
    expect(wrapper.text()).toContain('nginx:latest')
    expect(wrapper.text()).toContain('nginx:1.25')
    expect(wrapper.text()).toContain('postgres:16')
  })

  it('formats image sizes using formatBytes', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    // nginx image: 187600000 bytes → 178.9 MB
    expect(wrapper.text()).toContain('178.9 MB')

    // postgres image: 432100000 bytes → 412.1 MB
    expect(wrapper.text()).toContain('412.1 MB')
  })

  it('filters images by tag', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('nginx')
    await flushPromises()

    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('nginx:latest')
    expect(wrapper.text()).not.toContain('postgres:16')
  })

  it('filters images by ID', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('fed456')
    await flushPromises()

    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('postgres:16')
  })

  it('shows loading state while fetching', async () => {
    // Make the API call hang so loading stays true
    mockList.mockReturnValue(new Promise(() => {}))

    const wrapper = mountComponent()

    // The table should exist (rendered even during loading)
    const table = wrapper.find('.el-table')
    expect(table.exists()).toBe(true)

    // Verify the loading ref is true (v-loading is bound to it)
    // Access the component's internal state via vm
    const vm = wrapper.vm as unknown as { loading: boolean }
    expect(vm.loading).toBe(true)
  })

  it('shows el-empty when no images are returned', async () => {
    mockList.mockResolvedValue({ data: [] })

    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('.el-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('Aucune image trouvée')
  })

  it('shows ElMessage.error when API call fails', async () => {
    const { ElMessage } = await import('element-plus')
    mockList.mockRejectedValue(new Error('Network error'))

    mountComponent()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('shows Pull image button in header', async () => {
    const wrapper = mountComponent()
    await flushPromises()
    const buttons = wrapper.findAll('.card-header .el-button')
    expect(buttons.length).toBeGreaterThanOrEqual(1)
    expect(buttons.some(b => b.text().includes('Pull image'))).toBe(true)
  })

  it('opens pull dialog when Pull image button is clicked', async () => {
    const wrapper = mountComponent()
    await flushPromises()
    const pullButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Pull image'))
    expect(pullButton).toBeDefined()
    await pullButton!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.el-dialog').exists()).toBe(true)
    expect(wrapper.text()).toContain('Pull une image')
  })

  it('calls imagesApi.pull with correct params and refreshes list', async () => {
    mockPull.mockResolvedValue({ data: { status: 'Downloaded newer image' } })
    const wrapper = mountComponent()
    await flushPromises()

    // Open dialog
    const pullButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Pull image'))
    await pullButton!.trigger('click')
    await flushPromises()

    // Fill form
    const inputs = wrapper.findAll('.el-dialog input')
    await inputs[0].setValue('nginx')
    await inputs[1].setValue('alpine')
    await flushPromises()

    // Click Pull button in dialog
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Pull'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockPull).toHaveBeenCalledWith({ name: 'nginx', tag: 'alpine' })
    expect(mockList).toHaveBeenCalledTimes(2) // initial + refresh after pull
  })

  it('shows warning when pull is called with empty name', async () => {
    const { ElMessage } = await import('element-plus')
    const wrapper = mountComponent()
    await flushPromises()

    const pullButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Pull image'))
    await pullButton!.trigger('click')
    await flushPromises()

    // Name is empty by default, click Pull
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Pull'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.warning).toHaveBeenCalled()
    expect(mockPull).not.toHaveBeenCalled()
  })

  it('shows error when pull API fails', async () => {
    const { ElMessage } = await import('element-plus')
    mockPull.mockRejectedValue(new Error('Image not found'))
    const wrapper = mountComponent()
    await flushPromises()

    const pullButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Pull image'))
    await pullButton!.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('.el-dialog input')
    await inputs[0].setValue('nonexistent')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Pull'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('shows delete button for each image row', async () => {
    const wrapper = mountComponent()
    await flushPromises()
    const deleteButtons = wrapper.findAll('.el-button--danger')
    expect(deleteButtons.length).toBe(3) // one per image
  })

  it('calls imagesApi.remove after confirmation and refreshes list', async () => {
    const { ElMessageBox } = await import('element-plus')
    const { ElMessage } = await import('element-plus')
    ;(ElMessageBox.confirm as ReturnType<typeof vi.fn>).mockResolvedValue('confirm')
    mockRemove.mockResolvedValue({})

    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mockRemove).toHaveBeenCalledWith(mockImages[0].id)
    expect(ElMessage.success).toHaveBeenCalled()
    expect(mockList).toHaveBeenCalledTimes(2) // initial + refresh
  })

  it('shows error when remove API fails', async () => {
    const { ElMessageBox } = await import('element-plus')
    const { ElMessage } = await import('element-plus')
    ;(ElMessageBox.confirm as ReturnType<typeof vi.fn>).mockResolvedValue('confirm')
    mockRemove.mockRejectedValue(new Error('Image is in use'))

    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('does not remove image when confirmation is cancelled', async () => {
    const { ElMessageBox } = await import('element-plus')
    ;(ElMessageBox.confirm as ReturnType<typeof vi.fn>).mockRejectedValue('cancel')

    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(mockRemove).not.toHaveBeenCalled()
  })
})
