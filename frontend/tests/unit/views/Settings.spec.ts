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
const mockDeleteOrganizations = vi.fn()

const mockFetchUsers = vi.fn()
const mockCreateUser = vi.fn()
const mockUpdateUser = vi.fn()
const mockDeleteUser = vi.fn()
const mockDeleteUsers = vi.fn()
const mockAssignOrganization = vi.fn()
const mockUpdatePassword = vi.fn()

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
    deleteOrganizations: mockDeleteOrganizations,
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
    deleteUsers: mockDeleteUsers,
    assignOrganization: mockAssignOrganization,
    updatePassword: mockUpdatePassword,
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
          'el-drawer': {
            template: '<div class="el-drawer-stub" v-if="modelValue"><slot /><slot name="footer" /></div>',
            props: ['modelValue', 'title', 'direction', 'size'],
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
            props: ['modelValue', 'type', 'rows', 'disabled', 'placeholder'],
            emits: ['update:modelValue'],
          },
          'el-select': {
            template: '<select class="el-select-stub"><slot /></select>',
            props: ['modelValue', 'placeholder', 'clearable'],
          },
          'el-option': {
            template: '<option class="el-option-stub"><slot /></option>',
            props: ['label', 'value'],
          },
          'el-tag': {
            template: '<span class="el-tag-stub"><slot /></span>',
            props: ['type', 'size', 'effect'],
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
          'el-badge': {
            template: '<div class="el-badge-stub"><slot /></div>',
            props: ['value', 'type'],
          },
          'el-alert': {
            template: '<div class="el-alert-stub"><slot name="title" /></div>',
            props: ['type', 'closable', 'show-icon'],
          },
          'el-descriptions': {
            template: '<div class="el-descriptions-stub"><slot /></div>',
            props: ['column', 'border'],
          },
          'el-descriptions-item': {
            template: '<div class="el-descriptions-item-stub"><slot /></div>',
            props: ['label'],
          },
          // Stub settings components
          'OrganizationsTab': {
            template: '<div class="organizations-tab-stub"><slot /></div>',
            props: ['organizations', 'total', 'loading', 'bulkDeleting'],
            emits: ['add', 'edit', 'delete', 'bulk-delete'],
          },
          'UsersTab': {
            template: '<div class="users-tab-stub"><slot /></div>',
            props: ['users', 'total', 'loading', 'bulkDeleting'],
            emits: ['add', 'edit', 'password', 'delete', 'bulk-delete', 'bulk-assign', 'show-details'],
          },
          'OrganizationDialog': {
            template: '<div class="organization-dialog-stub" v-if="visible"><slot /></div>',
            props: ['visible', 'organization'],
            emits: ['update:visible', 'save'],
          },
          'UserDialog': {
            template: '<div class="user-dialog-stub" v-if="visible"><slot /></div>',
            props: ['visible', 'user', 'organizations'],
            emits: ['update:visible', 'save'],
          },
          'PasswordDialog': {
            template: '<div class="password-dialog-stub" v-if="visible"><slot /></div>',
            props: ['visible', 'user', 'loading'],
            emits: ['update:visible', 'save'],
          },
          'UserDetailsDrawer': {
            template: '<div class="user-details-drawer-stub" v-if="visible"><slot /></div>',
            props: ['visible', 'user', 'organizations'],
            emits: ['update:visible', 'edit'],
          },
          'BulkDeleteDialog': {
            template: '<div class="bulk-delete-dialog-stub" v-if="visible"><slot /></div>',
            props: ['visible', 'items', 'itemLabel', 'listLabel', 'loading', 'getItemLabel', 'getItemKey'],
            emits: ['update:visible', 'confirm'],
          },
          'BulkAssignDialog': {
            template: '<div class="bulk-assign-dialog-stub" v-if="visible"><slot /></div>',
            props: ['visible', 'userIds', 'userLabels', 'organizations', 'loading'],
            emits: ['update:visible', 'confirm'],
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
      expect(mockFetchUsers).toHaveBeenCalled()
    })

    it('should not fetch data when not superuser', async () => {
      mockIsSuperuser.mockReturnValue(false)
      await mountComponent()
      expect(mockFetchOrganizations).not.toHaveBeenCalled()
      expect(mockFetchUsers).not.toHaveBeenCalled()
    })
  })

  describe('Tab structure', () => {
    it('should have two tabs', async () => {
      const wrapper = await mountComponent()
      const tabs = wrapper.findAll('.el-tab-pane-stub')
      expect(tabs.length).toBe(2)
    })

    it('should render OrganizationsTab component', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.organizations-tab-stub').exists()).toBe(true)
    })

    it('should render UsersTab component', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.users-tab-stub').exists()).toBe(true)
    })
  })

  describe('Organization Dialog', () => {
    it('should have organization dialog state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; organization: null }
      }

      expect(vm.orgDialog.visible).toBe(false)
      expect(vm.orgDialog.organization).toBe(null)
    })

    it('should open organization dialog', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; organization: null }
        openOrgDialog: () => void
      }

      vm.openOrgDialog()
      expect(vm.orgDialog.visible).toBe(true)
    })

    it('should open edit organization dialog with data', async () => {
      const wrapper = await mountComponent()
      const mockOrg = { id: 'org-1', name: 'Test Org', slug: 'test-org', description: 'Test' }
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean; organization: typeof mockOrg | null }
        openOrgDialog: (org: typeof mockOrg) => void
      }

      vm.openOrgDialog(mockOrg)
      expect(vm.orgDialog.visible).toBe(true)
      expect(vm.orgDialog.organization).toEqual(mockOrg)
    })
  })

  describe('User Dialog', () => {
    it('should have user dialog state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        userDialog: { visible: boolean; user: null }
      }

      expect(vm.userDialog.visible).toBe(false)
      expect(vm.userDialog.user).toBe(null)
    })

    it('should open user dialog', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        userDialog: { visible: boolean; user: null }
        openUserDialog: () => void
      }

      vm.openUserDialog()
      expect(vm.userDialog.visible).toBe(true)
    })

    it('should open edit user dialog with data', async () => {
      const wrapper = await mountComponent()
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
        is_active: true,
        is_superuser: false,
        organization_id: null,
      }
      const vm = wrapper.vm as unknown as {
        userDialog: { visible: boolean; user: typeof mockUser | null }
        openUserDialog: (user: typeof mockUser) => void
      }

      vm.openUserDialog(mockUser)
      expect(vm.userDialog.visible).toBe(true)
      expect(vm.userDialog.user).toEqual(mockUser)
    })
  })

  describe('Password Dialog', () => {
    it('should have password dialog state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        passwordDialog: { visible: boolean; loading: boolean; user: null }
      }

      expect(vm.passwordDialog.visible).toBe(false)
      expect(vm.passwordDialog.loading).toBe(false)
      expect(vm.passwordDialog.user).toBe(null)
    })

    it('should open password dialog with user', async () => {
      const wrapper = await mountComponent()
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        email: 'test@example.com',
      }
      const vm = wrapper.vm as unknown as {
        passwordDialog: { visible: boolean; user: typeof mockUser | null }
        openPasswordDialog: (user: typeof mockUser) => void
      }

      vm.openPasswordDialog(mockUser)
      expect(vm.passwordDialog.visible).toBe(true)
      expect(vm.passwordDialog.user).toEqual(mockUser)
    })
  })

  describe('User Details Drawer', () => {
    it('should have user details drawer state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        userDetailsDrawer: { visible: boolean; user: null }
      }

      expect(vm.userDetailsDrawer.visible).toBe(false)
      expect(vm.userDetailsDrawer.user).toBe(null)
    })

    it('should open user details drawer with user', async () => {
      const wrapper = await mountComponent()
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
        is_active: true,
        is_superuser: false,
        organization_id: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      const vm = wrapper.vm as unknown as {
        userDetailsDrawer: { visible: boolean; user: typeof mockUser | null }
        showUserDetails: (user: typeof mockUser) => void
      }

      vm.showUserDetails(mockUser)
      expect(vm.userDetailsDrawer.visible).toBe(true)
      expect(vm.userDetailsDrawer.user).toEqual(mockUser)
    })
  })

  describe('Organization handlers', () => {
    it('should handle organization delete', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleOrgDelete: (orgId: string) => void
      }

      vm.handleOrgDelete('org-1')
      expect(mockDeleteOrganization).toHaveBeenCalledWith('org-1')
    })

    it('should handle organization save (create)', async () => {
      mockCreateOrganization.mockResolvedValue({ id: 'new-org', name: 'New Org' })
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgDialog: { visible: boolean }
        handleOrgSave: (data: { name: string }, isEdit: boolean, editId?: string) => Promise<void>
      }

      const createData = { name: 'New Org', slug: '', description: '' }
      await vm.handleOrgSave(createData, false)

      expect(mockCreateOrganization).toHaveBeenCalled()
    })

    it('should handle organization save (update)', async () => {
      mockUpdateOrganization.mockResolvedValue({ id: 'org-1', name: 'Updated' })
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleOrgSave: (data: { name: string }, isEdit: boolean, editId?: string) => Promise<void>
      }

      const updateData = { name: 'Updated Org', description: 'Updated' }
      await vm.handleOrgSave(updateData, true, 'org-1')

      expect(mockUpdateOrganization).toHaveBeenCalledWith('org-1', updateData)
    })
  })

  describe('User handlers', () => {
    it('should handle user delete', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleUserDelete: (userId: string) => void
      }

      vm.handleUserDelete('user-1')
      expect(mockDeleteUser).toHaveBeenCalledWith('user-1')
    })

    it('should handle user save (create)', async () => {
      mockCreateUser.mockResolvedValue({ id: 'new-user', username: 'newuser' })
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleUserSave: (data: { username: string; email: string; password: string }, isEdit: boolean, editId?: string) => Promise<void>
      }

      const createData = {
        username: 'newuser',
        email: 'new@example.com',
        password: 'password123',
      }
      await vm.handleUserSave(createData, false)

      expect(mockCreateUser).toHaveBeenCalled()
    })

    it('should handle user save (update)', async () => {
      mockUpdateUser.mockResolvedValue({ id: 'user-1', username: 'updateduser' })
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        handleUserSave: (data: { email: string }, isEdit: boolean, editId?: string) => Promise<void>
      }

      const updateData = { email: 'updated@example.com' }
      await vm.handleUserSave(updateData, true, 'user-1')

      expect(mockUpdateUser).toHaveBeenCalledWith('user-1', updateData)
    })
  })

  describe('Password handler', () => {
    it('should handle password save', async () => {
      mockUpdatePassword.mockResolvedValue(undefined)
      const wrapper = await mountComponent()
      const mockUser = { id: 'user-1', username: 'testuser', email: 'test@example.com' }
      const vm = wrapper.vm as unknown as {
        passwordDialog: { visible: boolean; loading: boolean; user: typeof mockUser | null }
        handlePasswordSave: (password: string) => Promise<void>
      }

      // Set up the user first
      vm.passwordDialog.user = mockUser
      await vm.handlePasswordSave('newpassword123')

      expect(mockUpdatePassword).toHaveBeenCalledWith('user-1', 'newpassword123')
    })
  })

  describe('Bulk operations state', () => {
    it('should have bulk delete dialog state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        bulkDeleteDialogVisible: boolean
        bulkDeleting: boolean
        selectedUserIds: string[]
      }

      expect(vm.bulkDeleteDialogVisible).toBe(false)
      expect(vm.bulkDeleting).toBe(false)
      expect(vm.selectedUserIds).toEqual([])
    })

    it('should have bulk assign dialog state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        bulkAssignDialogVisible: boolean
        bulkAssigning: boolean
      }

      expect(vm.bulkAssignDialogVisible).toBe(false)
      expect(vm.bulkAssigning).toBe(false)
    })

    it('should have org bulk delete dialog state', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        orgBulkDeleteDialogVisible: boolean
        bulkDeletingOrgs: boolean
      }

      expect(vm.orgBulkDeleteDialogVisible).toBe(false)
      expect(vm.bulkDeletingOrgs).toBe(false)
    })
  })

  describe('Helper functions', () => {
    it('should get org name correctly', async () => {
      const wrapper = await mountComponent()
      const mockOrg = { id: 'org-1', name: 'Test Org', slug: 'test-org' }
      const vm = wrapper.vm as unknown as {
        getOrgName: (org: typeof mockOrg) => string
      }

      expect(vm.getOrgName(mockOrg)).toBe('Test Org')
    })

    it('should get user label correctly', async () => {
      const wrapper = await mountComponent()
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        email: 'test@example.com',
        full_name: 'Test User',
      }
      const vm = wrapper.vm as unknown as {
        getUserLabel: (user: typeof mockUser) => string
      }

      expect(vm.getUserLabel(mockUser)).toBe('Test User (test@example.com)')
    })

    it('should get user label with username when no full name', async () => {
      const wrapper = await mountComponent()
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        email: 'test@example.com',
        full_name: null,
      }
      const vm = wrapper.vm as unknown as {
        getUserLabel: (user: typeof mockUser) => string
      }

      expect(vm.getUserLabel(mockUser)).toBe('testuser (test@example.com)')
    })
  })
})
