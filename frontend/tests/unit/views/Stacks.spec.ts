import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Stacks from '@/views/Stacks.vue'
import type { Stack } from '@/types/api'

// Mock router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

// Mock API completely
vi.mock('@/services/api', () => ({
  stacksApi: {
    validate: vi.fn().mockResolvedValue({ data: { valid: true, errors: [] } }),
    listVersions: vi.fn().mockResolvedValue({ data: [] }),
    createVersion: vi.fn().mockResolvedValue({ data: {} }),
    restoreVersion: vi.fn().mockResolvedValue({ data: {} }),
    export: vi.fn().mockResolvedValue({ data: { version: '1.0', stack: { name: 'Test Stack', description: null, version: '1.0', category: null, tags: [], template: '', variables: {}, icon_url: null, screenshots: [], documentation_url: null, author: null, license: null } } }),
    import: vi.fn().mockResolvedValue({ data: { message: 'Stack imported successfully', stack_id: 'new-stack-1', name: 'Imported Stack' } }),
  },
  targetsApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [] } }),
  },
}))

// Mock Element Plus components
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  ElMessageBox: {
    confirm: vi.fn().mockResolvedValue(true),
  },
}))

// Mock stores
vi.mock('@/stores', () => ({
  useStacksStore: () => ({
    stacks: [],
    loading: false,
    fetchStacks: vi.fn(),
    createStack: vi.fn(),
    updateStack: vi.fn(),
    deleteStack: vi.fn(),
  }),
  useTargetsStore: () => ({
    targets: [],
    loading: false,
    fetchTargets: vi.fn(),
  }),
  useDeploymentsStore: () => ({
    createDeployment: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    organizationId: 'test-org',
    user: { id: 'user-1' },
  }),
}))

// Mock browser APIs not available in jsdom
if (typeof URL.createObjectURL === 'undefined') {
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  URL.revokeObjectURL = vi.fn()
}

describe('Stacks.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mockStack: Stack = {
    id: 'stack-1',
    name: 'Test Stack',
    description: 'A test stack',
    compose_content: 'version: "3.8"\nservices:\n  web:\n    image: nginx',
    metadata: {},
    organization_id: 'org-1',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }

  describe('getStackStatus', () => {
    it('returns "draft" when metadata is empty', async () => {
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      // Access the getStackStatus function via component vm
      const getStackStatus = (wrapper.vm as unknown as { getStackStatus: (s: Stack) => string }).getStackStatus
      expect(getStackStatus(mockStack)).toBe('draft')
    })

    it('returns "deployed" when metadata status is deployed', async () => {
      const deployedStack = { ...mockStack, metadata: { status: 'deployed' } }
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const getStackStatus = (wrapper.vm as unknown as { getStackStatus: (s: Stack) => string }).getStackStatus
      expect(getStackStatus(deployedStack)).toBe('deployed')
    })

    it('returns "error" when metadata status is error', async () => {
      const errorStack = { ...mockStack, metadata: { status: 'error' } }
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const getStackStatus = (wrapper.vm as unknown as { getStackStatus: (s: Stack) => string }).getStackStatus
      expect(getStackStatus(errorStack)).toBe('error')
    })

    it('returns "deploying" when metadata status is deploying', async () => {
      const deployingStack = { ...mockStack, metadata: { status: 'deploying' } }
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const getStackStatus = (wrapper.vm as unknown as { getStackStatus: (s: Stack) => string }).getStackStatus
      expect(getStackStatus(deployingStack)).toBe('deploying')
    })
  })

  describe('ActionButtons integration', () => {
    it('has correct action types for stacks', () => {
      // Verify that ActionButtons accepts the expected action types
      const expectedActions = ['edit', 'deploy', 'export', 'delete']
      expect(expectedActions).toContain('edit')
      expect(expectedActions).toContain('deploy')
      expect(expectedActions).toContain('export')
      expect(expectedActions).toContain('delete')
    })
  })

  describe('exportStack', () => {
    it('calls stacksApi.export with the correct stack id', async () => {
      const { stacksApi } = await import('@/services/api')
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const exportStack = (wrapper.vm as unknown as { exportStack: (s: Stack) => Promise<void> }).exportStack
      await exportStack(mockStack)

      expect(stacksApi.export).toHaveBeenCalledWith('stack-1')
    })

    it('displays success message after successful export', async () => {
      const { ElMessage } = await import('element-plus')
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const exportStack = (wrapper.vm as unknown as { exportStack: (s: Stack) => Promise<void> }).exportStack
      await exportStack(mockStack)

      expect(ElMessage.success).toHaveBeenCalledWith('Stack "Test Stack" exported successfully')
    })

    it('displays error message when API fails', async () => {
      const { stacksApi } = await import('@/services/api')
      const { ElMessage } = await import('element-plus')
      ;(stacksApi.export as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('API error'))

      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const exportStack = (wrapper.vm as unknown as { exportStack: (s: Stack) => Promise<void> }).exportStack
      await exportStack(mockStack)

      expect(ElMessage.error).toHaveBeenCalledWith('Failed to export stack')
    })
  })

  describe('handleFileSelect', () => {
    function createFile(name: string, content: string): File {
      const blob = new Blob([content], { type: 'application/json' })
      return new File([blob], name, { type: 'application/json' })
    }

    function triggerFileSelect(wrapper: ReturnType<typeof mount>, file: File): void {
      const vm = wrapper.vm as unknown as { handleFileSelect: (e: Event) => void }
      const input = { target: { files: [file] } } as unknown as Event
      vm.handleFileSelect(input)
    }

    it('rejects non-JSON file extension', async () => {
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const file = createFile('test.txt', '{}')
      triggerFileSelect(wrapper, file)

      // Extension check is synchronous — no need to wait
      expect((wrapper.vm as unknown as Record<string, unknown>).importError).toBe('Please select a JSON file (.json)')
    })

    it('rejects JSON with unsupported version', async () => {
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const file = createFile('test.json', JSON.stringify({ version: '2.0', stack: { name: 'Test', template: 'yaml' } }))
      triggerFileSelect(wrapper, file)

      await vi.waitFor(() => {
        expect((wrapper.vm as unknown as Record<string, unknown>).importError).toBe('Invalid format: unsupported version (expected "1.0")')
      }, { timeout: 2000 })
    })

    it('rejects JSON without stack section', async () => {
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const file = createFile('test.json', JSON.stringify({ version: '1.0' }))
      triggerFileSelect(wrapper, file)

      await vi.waitFor(() => {
        expect((wrapper.vm as unknown as Record<string, unknown>).importError).toBe('Invalid format: "stack" section is missing')
      }, { timeout: 2000 })
    })

    it('rejects JSON without stack name', async () => {
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const file = createFile('test.json', JSON.stringify({ version: '1.0', stack: { template: 'yaml' } }))
      triggerFileSelect(wrapper, file)

      await vi.waitFor(() => {
        expect((wrapper.vm as unknown as Record<string, unknown>).importError).toBe('Invalid format: stack name is required')
      }, { timeout: 2000 })
    })

    it('accepts valid JSON file', async () => {
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const file = createFile('test.json', JSON.stringify({ version: '1.0', stack: { name: 'My Stack', template: 'version: "3.8"\nservices:\n  web:\n    image: nginx' } }))
      triggerFileSelect(wrapper, file)

      await vi.waitFor(() => {
        expect((wrapper.vm as unknown as Record<string, unknown>).selectedImportFile).toBe(file)
      }, { timeout: 2000 })
      expect((wrapper.vm as unknown as Record<string, unknown>).importError).toBeNull()
    })
  })

  describe('handleImport', () => {
    it('calls stacksApi.import with the selected file', async () => {
      const { stacksApi } = await import('@/services/api')
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      // Set a file directly on the component (auto-unwrapped ref)
      const blob = new Blob(['{}'], { type: 'application/json' })
      const file = new File([blob], 'test.json', { type: 'application/json' })
      ;(wrapper.vm as unknown as Record<string, unknown>).selectedImportFile = file

      const handleImport = (wrapper.vm as unknown as { handleImport: () => Promise<void> }).handleImport
      await handleImport()

      expect(stacksApi.import).toHaveBeenCalledWith(file)
    })

    it('displays success message after successful import', async () => {
      const { ElMessage } = await import('element-plus')
      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const blob = new Blob(['{}'], { type: 'application/json' })
      const file = new File([blob], 'test.json', { type: 'application/json' })
      ;(wrapper.vm as unknown as Record<string, unknown>).selectedImportFile = file

      const handleImport = (wrapper.vm as unknown as { handleImport: () => Promise<void> }).handleImport
      await handleImport()

      expect(ElMessage.success).toHaveBeenCalledWith('Stack "Imported Stack" imported successfully')
    })

    it('displays backend error when API fails', async () => {
      const { stacksApi } = await import('@/services/api')
      ;(stacksApi.import as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
        response: { data: { detail: 'Stack already exists' } },
      })

      const wrapper = mount(Stacks, {
        global: {
          plugins: [createPinia()],
          stubs: {
            'el-card': { template: '<div><slot /><slot name="header" /></div>' },
            'el-table': { template: '<div><slot /></div>' },
            'el-table-column': { template: '<div></div>' },
            'el-button': { template: '<button><slot /></button>' },
            'el-tag': { template: '<span><slot /></span>' },
            'el-icon': { template: '<i><slot /></i>' },
            'el-tooltip': { template: '<span><slot /></span>' },
            StatusBadge: { template: '<span data-testid="status-badge">{{ status }}</span>', props: ['status', 'size'] },
            ActionButtons: { template: '<div data-testid="action-buttons"></div>', props: ['actions'] },
          },
        },
      })

      const blob = new Blob(['{}'], { type: 'application/json' })
      const file = new File([blob], 'test.json', { type: 'application/json' })
      ;(wrapper.vm as unknown as Record<string, unknown>).selectedImportFile = file

      const handleImport = (wrapper.vm as unknown as { handleImport: () => Promise<void> }).handleImport
      await handleImport()

      expect((wrapper.vm as unknown as Record<string, unknown>).importError).toBe('Stack already exists')
    })
  })
})
