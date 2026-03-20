/**
 * Settings.vue Unit Tests
 * Tests for the administration settings page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import Settings from '@/views/Settings.vue'

// Mock auth store
const mockIsSuperuser = vi.fn(() => true)
const mockOrganizationId = vi.fn(() => 'org-123')
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isSuperuser: mockIsSuperuser(),
    organizationId: mockOrganizationId(),
    user: { id: 'user-1', is_superuser: true },
  }),
}))

// Mock composables
const mockFetchOrganizations = vi.fn()
const mockCreateOrganization = vi.fn()
const mockUpdateOrganization = vi.fn()
const mockDeleteOrganization = vi.fn()

const mockFetchEnvironments = vi.fn()
const mockCreateEnvironment = vi.fn()
const mockUpdateEnvironment = vi.fn()
const mockDeleteEnvironment = vi.fn()
const mockScanEnvironment = vi.fn()

const mockFetchUsers = vi.fn()
const mockCreateUser = vi.fn()
const mockUpdateUser = vi.fn()
const mockDeleteUser = vi.fn()

vi.mock('@/composables/useOrganizations', () => ({
  useOrganizations: () => ({
    organizations: { value: [] },
    loading: { value: false },
    error: { value: null },
    total: { value: 0 },
    fetchOrganizations: mockFetchOrganizations,
    createOrganization: mockCreateOrganization,
    updateOrganization: mockUpdateOrganization,
    deleteOrganization: mockDeleteOrganization,
  }),
}))

vi.mock('@/composables/useEnvironments', () => ({
  useEnvironments: () => ({
    environments: { value: [] },
    loading: { value: false },
    error: { value: null },
    total: { value: 0 },
    fetchEnvironments: mockFetchEnvironments,
    createEnvironment: mockCreateEnvironment,
    updateEnvironment: mockUpdateEnvironment,
    deleteEnvironment: mockDeleteEnvironment,
    scanEnvironment: mockScanEnvironment,
  }),
}))

vi.mock('@/composables/useUsers', () => ({
  useUsers: () => ({
    users: { value: [] },
    loading: { value: false },
    error: { value: null },
    total: { value: 0 },
    fetchUsers: mockFetchUsers,
    createUser: mockCreateUser,
    updateUser: mockUpdateUser,
    deleteUser: mockDeleteUser,
  }),
}))

describe('Settings.vue', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(() => {
    vi.clearAllMocks()
    mockIsSuperuser.mockReturnValue(true)

    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', name: 'Home', component: { template: '<div>Home</div>' } },
        { path: '/settings', name: 'Settings', component: Settings },
      ],
    })

    const pinia = createPinia()
    setActivePinia(pinia)
  })

  const mountComponent = async () => {
    await router.push('/settings')
    await router.isReady()

    const wrapper = mount(Settings, {
      global: {
        plugins: [router, ElementPlus, createPinia()],
        stubs: {
          'el-tabs': {
            template: '<div class="el-tabs-stub"><slot /></div>',
            props: ['modelValue'],
          },
          'el-tab-pane': {
            template: '<div class="el-tab-pane-stub" :data-name="name"><slot /></div>',
            props: ['label', 'name'],
          },
          'el-card': {
            template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
          },
          'el-table': {
            template: '<div class="el-table-stub"><slot /></div>',
            props: ['data', 'v-loading'],
          },
          'el-table-column': {
            template: '<div class="el-table-column-stub"><slot :row="mockRow" /></div>',
            props: ['prop', 'label', 'width'],
            data() {
              return { mockRow: {} }
            },
          },
          'el-button': {
            template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'size', 'disabled'],
            emits: ['click'],
          },
          'el-dialog': {
            template: '<div class="el-dialog-stub" v-if="modelValue"><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title', 'width'],
          },
          'el-form': {
            template: '<form class="el-form-stub"><slot /></form>',
            props: ['model', 'label-width'],
          },
          'el-form-item': {
            template: '<div class="el-form-item-stub"><slot /></div>',
            props: ['label', 'required'],
          },
          'el-input': {
            template: '<input class="el-input-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue', 'type', 'rows', 'disabled'],
            emits: ['update:modelValue'],
          },
          'el-input-number': {
            template: '<input type="number" class="el-input-number-stub" :value="modelValue" />',
            props: ['modelValue', 'min', 'max'],
          },
          'el-select': {
            template: '<select class="el-select-stub"><slot /></select>',
            props: ['modelValue'],
          },
          'el-option': {
            template: '<option class="el-option-stub"><slot /></option>',
            props: ['label', 'value'],
          },
          'el-tag': {
            template: '<span class="el-tag-stub"><slot /></span>',
            props: ['type', 'size'],
          },
          'el-switch': {
            template: '<input type="checkbox" class="el-switch-stub" :checked="modelValue" />',
            props: ['modelValue'],
          },
          'el-icon': {
            template: '<i class="el-icon-stub"><slot /></i>',
            props: ['size'],
          },
          'el-empty': {
            template: '<div class="el-empty-stub">{{ description }}<slot /></div>',
            props: ['description'],
          },
          'StatusBadge': {
            template: '<span class="status-badge-stub"><slot /></span>',
            props: ['status'],
          },
          'ActionButtons': {
            template: '<div class="action-buttons-stub"><button v-for="a in actions" :key="a" @click="$emit(\'action\', a)">{{ a }}</button></div>',
            props: ['actions'],
            emits: ['action'],
          },
        },
      },
    })

    await flushPromises()
    return wrapper
  }

  describe('Component mounting', () => {
    it('should mount successfully', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.exists()).toBe(true)
    })

    it('should have default activeTab as organizations', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { activeTab: string }
      expect(vm.activeTab).toBe('organizations')
    })
  })

  describe('Access control', () => {
    it('should show tabs for superuser', async () => {
      mockIsSuperuser.mockReturnValue(true)
      const wrapper = await mountComponent()
      expect(wrapper.find('.el-tabs-stub').exists()).toBe(true)
    })

    it('should show access denied for non-superuser', async () => {
      mockIsSuperuser.mockReturnValue(false)
      const wrapper = await mountComponent()
      expect(wrapper.find('.access-denied').exists()).toBe(true)
      expect(wrapper.html()).toContain('Accès refusé')
    })
  })

  describe('Data fetching on mount', () => {
    it('should fetch all data when superuser', async () => {
      mockIsSuperuser.mockReturnValue(true)
      await mountComponent()
      expect(mockFetchOrganizations).toHaveBeenCalled()
      expect(mockFetchEnvironments).toHaveBeenCalled()
      expect(mockFetchUsers).toHaveBeenCalled()
    })

    it('should not fetch data when not superuser', async () => {
      mockIsSuperuser.mockReturnValue(false)
      await mountComponent()
      expect(mockFetchOrganizations).not.toHaveBeenCalled()
      expect(mockFetchEnvironments).not.toHaveBeenCalled()
      expect(mockFetchUsers).not.toHaveBeenCalled()
    })
  })

  describe('Tab structure', () => {
    it('should have three tabs', async () => {
      const wrapper = await mountComponent()
      const tabs = wrapper.findAll('.el-tab-pane-stub')
      expect(tabs.length).toBe(3)
    })

    it('should have Organizations tab', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Organisations')
    })

    it('should have Environments tab', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Environnements')
    })

    it('should have Users tab', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Utilisateurs')
    })
  })

  describe('Organization CRUD', () => {
    it('should have Add button for organizations', async () => {
      const wrapper = await mountComponent()
      const html = wrapper.html()
      expect(html).toContain('Ajouter')
    })

    it('should open create organization dialog', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; isEdit: boolean }
        openOrgDialog: () => void
      }

      expect(vm.orgDialog.visible).toBe(false)
      vm.openOrgDialog()
      expect(vm.orgDialog.visible).toBe(true)
      expect(vm.orgDialog.isEdit).toBe(false)
    })

    it('should open edit organization dialog with data', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; isEdit: boolean; editId: string | null; form: { name: string } }
        openOrgDialog: (org: { id: string; name: string; description: string | null }) => void
      }

      vm.openOrgDialog({ id: 'org-1', name: 'Test Org', description: 'Test' })
      expect(vm.orgDialog.visible).toBe(true)
      expect(vm.orgDialog.isEdit).toBe(true)
      expect(vm.orgDialog.editId).toBe('org-1')
      expect(vm.orgDialog.form.name).toBe('Test Org')
    })
  })

  describe('Environment CRUD', () => {
    it('should open create environment dialog', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        envDialog: { visible: boolean; isEdit: boolean }
        openEnvDialog: () => void
      }

      expect(vm.envDialog.visible).toBe(false)
      vm.openEnvDialog()
      expect(vm.envDialog.visible).toBe(true)
      expect(vm.envDialog.isEdit).toBe(false)
    })

    it('should open edit environment dialog with data', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        envDialog: { visible: boolean; isEdit: boolean; editId: string | null; form: { name: string; type: string } }
        openEnvDialog: (env: { id: string; name: string; type: string; host: string; port: number; description: string | null }) => void
      }

      vm.openEnvDialog({ id: 'env-1', name: 'Test Env', type: 'docker', host: 'localhost', port: 22, description: null })
      expect(vm.envDialog.visible).toBe(true)
      expect(vm.envDialog.isEdit).toBe(true)
      expect(vm.envDialog.editId).toBe('env-1')
      expect(vm.envDialog.form.name).toBe('Test Env')
      expect(vm.envDialog.form.type).toBe('docker')
    })
  })

  describe('User CRUD', () => {
    it('should open create user dialog', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        userDialog: { visible: boolean; isEdit: boolean }
        openUserDialog: () => void
      }

      expect(vm.userDialog.visible).toBe(false)
      vm.openUserDialog()
      expect(vm.userDialog.visible).toBe(true)
      expect(vm.userDialog.isEdit).toBe(false)
    })

    it('should open edit user dialog with data', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        userDialog: { visible: boolean; isEdit: boolean; editId: string | null; form: { username: string; email: string } }
        openUserDialog: (user: { id: string; username: string; email: string; full_name: string | null; is_active: boolean }) => void
      }

      vm.openUserDialog({ id: 'user-1', username: 'testuser', email: 'test@example.com', full_name: 'Test User', is_active: true })
      expect(vm.userDialog.visible).toBe(true)
      expect(vm.userDialog.isEdit).toBe(true)
      expect(vm.userDialog.editId).toBe('user-1')
      expect(vm.userDialog.form.username).toBe('testuser')
      expect(vm.userDialog.form.email).toBe('test@example.com')
    })
  })

  describe('Action handlers', () => {
    it('should handle organization edit action', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleOrgAction: (action: string, org: { id: string; name: string; description: string | null }) => void
        orgDialog: { visible: boolean; isEdit: boolean }
      }

      vm.handleOrgAction('edit', { id: 'org-1', name: 'Test', description: null })
      expect(vm.orgDialog.visible).toBe(true)
      expect(vm.orgDialog.isEdit).toBe(true)
    })

    it('should handle organization delete action', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleOrgAction: (action: string, org: { id: string }) => void
      }

      vm.handleOrgAction('delete', { id: 'org-1' })
      expect(mockDeleteOrganization).toHaveBeenCalledWith('org-1')
    })

    it('should handle environment scan action', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleEnvAction: (action: string, env: { id: string }) => void
      }

      vm.handleEnvAction('scan', { id: 'env-1' })
      expect(mockScanEnvironment).toHaveBeenCalledWith('env-1')
    })
  })

  describe('Date formatting', () => {
    it('should format date correctly', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { formatDate: (dateStr: string) => string }

      const result = vm.formatDate('2024-01-15T10:30:00Z')
      expect(result).toContain('2024')
    })
  })

  describe('Save operations', () => {
    it('should create organization on save', async () => {
      mockCreateOrganization.mockResolvedValue({ id: 'new-org', name: 'New Org' })
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; isEdit: boolean; form: { name: string; description: string } }
        saveOrg: () => Promise<void>
      }

      vm.orgDialog.form = { name: 'New Org', description: 'Description' }
      vm.orgDialog.isEdit = false
      await vm.saveOrg()

      expect(mockCreateOrganization).toHaveBeenCalled()
      expect(vm.orgDialog.visible).toBe(false)
    })

    it('should update organization on save when editing', async () => {
      mockUpdateOrganization.mockResolvedValue({ id: 'org-1', name: 'Updated' })
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; isEdit: boolean; editId: string | null; form: { name: string; description: string } }
        saveOrg: () => Promise<void>
      }

      vm.orgDialog.form = { name: 'Updated Org', description: 'Updated' }
      vm.orgDialog.isEdit = true
      vm.orgDialog.editId = 'org-1'
      await vm.saveOrg()

      expect(mockUpdateOrganization).toHaveBeenCalledWith('org-1', expect.any(Object))
      expect(vm.orgDialog.visible).toBe(false)
    })
  })
})
