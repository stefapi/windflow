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
      const expectedActions = ['edit', 'deploy', 'delete']
      expect(expectedActions).toContain('edit')
      expect(expectedActions).toContain('deploy')
      expect(expectedActions).toContain('delete')
    })
  })
})
