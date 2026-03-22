<template>
  <div class="settings-page">
    <!-- Access denied for non-superusers -->
    <el-card
      v-if="!authStore.isSuperuser"
      class="access-denied"
    >
      <el-empty description="Accès refusé">
        <template #image>
          <el-icon :size="80">
            <Lock />
          </el-icon>
        </template>
        <p>Seuls les administrateurs peuvent accéder à cette page.</p>
        <el-button
          type="primary"
          @click="$router.push('/')"
        >
          Retour au Dashboard
        </el-button>
      </el-empty>
    </el-card>

    <!-- Settings tabs for superusers -->
    <el-tabs
      v-else
      v-model="activeTab"
      class="settings-tabs"
    >
      <!-- Organizations Tab -->
      <el-tab-pane
        label="Organisations"
        name="organizations"
      >
        <OrganizationsTab
          ref="orgsTabRef"
          :organizations="orgsStore.organizations.value"
          :total="orgsStore.total.value"
          :loading="orgsStore.loading.value"
          :bulk-deleting="bulkDeletingOrgs"
          @add="openOrgDialog()"
          @edit="openOrgDialog"
          @delete="handleOrgDelete"
          @bulk-delete="showOrgBulkDeleteDialog"
        />
      </el-tab-pane>

      <!-- Users Tab -->
      <el-tab-pane
        label="Utilisateurs"
        name="users"
      >
        <UsersTab
          ref="usersTabRef"
          :users="usersStore.users.value"
          :total="usersStore.total.value"
          :loading="usersStore.loading.value"
          :bulk-deleting="bulkDeleting"
          @add="openUserDialog()"
          @edit="openUserDialog"
          @password="openPasswordDialog"
          @delete="handleUserDelete"
          @bulk-delete="showBulkDeleteDialog"
          @bulk-assign="showBulkAssignDialog"
          @show-details="showUserDetails"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- Organization Dialog -->
    <OrganizationDialog
      v-model:visible="orgDialog.visible"
      :organization="orgDialog.organization"
      @save="handleOrgSave"
    />

    <!-- Organization Bulk Delete Dialog -->
    <BulkDeleteDialog
      v-model:visible="orgBulkDeleteDialogVisible"
      :items="selectedOrgsForDelete"
      item-label="organisation"
      list-label="Organisations concernées"
      :loading="bulkDeletingOrgs"
      :get-item-label="getOrgName"
      :get-item-key="(org: Organization) => org.id"
      @confirm="confirmOrgBulkDelete"
    />

    <!-- User Dialog -->
    <UserDialog
      v-model:visible="userDialog.visible"
      :user="userDialog.user"
      :organizations="orgsStore.organizations.value"
      @save="handleUserSave"
    />

    <!-- Password Dialog -->
    <PasswordDialog
      v-model:visible="passwordDialog.visible"
      :user="passwordDialog.user"
      :loading="passwordDialog.loading"
      @save="handlePasswordSave"
    />

    <!-- User Details Drawer -->
    <UserDetailsDrawer
      v-model:visible="userDetailsDrawer.visible"
      :user="userDetailsDrawer.user"
      :organizations="orgsStore.organizations.value"
      @edit="openUserDialog"
    />

    <!-- User Bulk Delete Dialog -->
    <BulkDeleteDialog
      v-model:visible="bulkDeleteDialogVisible"
      :items="selectedUsersForDelete"
      item-label="utilisateur"
      list-label="Utilisateurs concernés"
      :loading="bulkDeleting"
      :get-item-label="getUserLabel"
      :get-item-key="(user: User) => user.id"
      @confirm="confirmBulkDelete"
    />

    <!-- Bulk Assign Organization Dialog -->
    <BulkAssignDialog
      v-model:visible="bulkAssignDialogVisible"
      :user-ids="selectedUserIds"
      :user-labels="selectedUserLabels"
      :organizations="orgsStore.organizations.value"
      :loading="bulkAssigning"
      @confirm="confirmBulkAssign"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * Settings Page
 * Administration page for managing Organizations and Users
 * Access restricted to superusers only
 */

import { ref, reactive, computed, onMounted } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useOrganizations } from '@/composables/useOrganizations'
import { useUsers } from '@/composables/useUsers'
import type { Organization, OrganizationCreate, OrganizationUpdate } from '@/types/api'
import type { User, UserCreate, UserUpdate } from '@/types/api'

// Settings components
import OrganizationsTab from '@/components/settings/OrganizationsTab.vue'
import UsersTab from '@/components/settings/UsersTab.vue'
import OrganizationDialog from '@/components/settings/OrganizationDialog.vue'
import UserDialog from '@/components/settings/UserDialog.vue'
import PasswordDialog from '@/components/settings/PasswordDialog.vue'
import UserDetailsDrawer from '@/components/settings/UserDetailsDrawer.vue'
import BulkDeleteDialog from '@/components/settings/BulkDeleteDialog.vue'
import BulkAssignDialog from '@/components/settings/BulkAssignDialog.vue'

// Stores
const authStore = useAuthStore()
const orgsStore = useOrganizations({ autoFetch: false })
const usersStore = useUsers({ autoFetch: false })

// Active tab
const activeTab = ref('organizations')

// Tab refs for selection clearing
const orgsTabRef = ref<InstanceType<typeof OrganizationsTab>>()
const usersTabRef = ref<InstanceType<typeof UsersTab>>()

// =====================
// Organization Dialog
// =====================
const orgDialog = reactive({
  visible: false,
  organization: null as Organization | null,
})

function openOrgDialog(org?: Organization) {
  orgDialog.organization = org || null
  orgDialog.visible = true
}

async function handleOrgSave(data: OrganizationCreate | OrganizationUpdate, isEdit: boolean, editId?: string) {
  if (isEdit && editId) {
    await orgsStore.updateOrganization(editId, data as OrganizationUpdate)
  } else {
    await orgsStore.createOrganization(data as OrganizationCreate)
  }
  orgDialog.visible = false
}

function handleOrgDelete(orgId: string) {
  orgsStore.deleteOrganization(orgId)
}

// =====================
// Organization Bulk Operations
// =====================
const orgBulkDeleteDialogVisible = ref(false)
const bulkDeletingOrgs = ref(false)
const selectedOrgIdsForDelete = ref<string[]>([])

const selectedOrgsForDelete = computed(() =>
  orgsStore.organizations.value.filter(o => selectedOrgIdsForDelete.value.includes(o.id))
)

function getOrgName(org: Organization): string {
  return org.name
}

function showOrgBulkDeleteDialog(orgIds: string[]) {
  selectedOrgIdsForDelete.value = orgIds
  orgBulkDeleteDialogVisible.value = true
}

async function confirmOrgBulkDelete(): Promise<void> {
  bulkDeletingOrgs.value = true

  try {
    const result = await orgsStore.deleteOrganizations(selectedOrgIdsForDelete.value)

    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} organisation(s) supprimée(s)`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de la suppression de ${result.failed.length} organisation(s)`)
    } else {
      ElMessage.warning(`${result.success.length} supprimée(s), ${result.failed.length} échec(s)`)
    }

    orgBulkDeleteDialogVisible.value = false
    orgsTabRef.value?.clearSelection()
  } finally {
    bulkDeletingOrgs.value = false
  }
}

// =====================
// User Dialog
// =====================
const userDialog = reactive({
  visible: false,
  user: null as User | null,
})

function openUserDialog(user?: User) {
  userDialog.user = user || null
  userDialog.visible = true
}

async function handleUserSave(data: UserCreate | UserUpdate, isEdit: boolean, editId?: string) {
  if (isEdit && editId) {
    await usersStore.updateUser(editId, data as UserUpdate)
  } else {
    await usersStore.createUser(data as UserCreate)
  }
  userDialog.visible = false
}

function handleUserDelete(userId: string) {
  usersStore.deleteUser(userId)
}

// =====================
// Password Dialog
// =====================
const passwordDialog = reactive({
  visible: false,
  loading: false,
  user: null as User | null,
})

function openPasswordDialog(user: User) {
  passwordDialog.user = user
  passwordDialog.visible = true
}

async function handlePasswordSave(password: string) {
  if (!passwordDialog.user?.id) return

  passwordDialog.loading = true
  try {
    await usersStore.updatePassword(passwordDialog.user.id, password)
    passwordDialog.visible = false
  } finally {
    passwordDialog.loading = false
  }
}

// =====================
// User Details Drawer
// =====================
const userDetailsDrawer = reactive({
  visible: false,
  user: null as User | null,
})

function showUserDetails(user: User) {
  userDetailsDrawer.user = user
  userDetailsDrawer.visible = true
}

// =====================
// User Bulk Operations
// =====================
const bulkDeleteDialogVisible = ref(false)
const bulkDeleting = ref(false)
const bulkAssignDialogVisible = ref(false)
const bulkAssigning = ref(false)
const selectedUserIds = ref<string[]>([])

const selectedUsersForDelete = computed(() =>
  usersStore.users.value.filter(u => selectedUserIds.value.includes(u.id))
)

const selectedUserLabels = computed(() =>
  selectedUserIds.value.map(id => {
    const user = usersStore.users.value.find(u => u.id === id)
    return user?.full_name || user?.username || id
  })
)

function getUserLabel(user: User): string {
  return `${user.full_name || user.username} (${user.email})`
}

function showBulkDeleteDialog(userIds: string[]) {
  selectedUserIds.value = userIds
  bulkDeleteDialogVisible.value = true
}

async function confirmBulkDelete(): Promise<void> {
  bulkDeleting.value = true

  try {
    const result = await usersStore.deleteUsers(selectedUserIds.value)

    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} utilisateur(s) supprimé(s)`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de la suppression de ${result.failed.length} utilisateur(s)`)
    } else {
      ElMessage.warning(`${result.success.length} supprimé(s), ${result.failed.length} échec(s)`)
    }

    bulkDeleteDialogVisible.value = false
    usersTabRef.value?.clearSelection()
  } finally {
    bulkDeleting.value = false
  }
}

function showBulkAssignDialog(userIds: string[]) {
  selectedUserIds.value = userIds
  bulkAssignDialogVisible.value = true
}

async function confirmBulkAssign(organizationId: string): Promise<void> {
  bulkAssigning.value = true

  try {
    const result = await usersStore.assignOrganization(selectedUserIds.value, organizationId)

    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} utilisateur(s) réassigné(s)`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de la réassignation de ${result.failed.length} utilisateur(s)`)
    } else {
      ElMessage.warning(`${result.success.length} réassigné(s), ${result.failed.length} échec(s)`)
    }

    bulkAssignDialogVisible.value = false
    usersTabRef.value?.clearSelection()
  } finally {
    bulkAssigning.value = false
  }
}

// =====================
// Lifecycle
// =====================
onMounted(() => {
  if (authStore.isSuperuser) {
    orgsStore.fetchOrganizations()
    usersStore.fetchUsers()
  }
})
</script>

<style scoped>
.settings-page {
  padding: 20px;
}

.settings-tabs {
  background-color: var(--color-bg-card);
  border-radius: 8px;
  padding: 16px;
}

.access-denied {
  text-align: center;
  padding: 40px;
}

.access-denied .el-icon {
  color: #f56c6c;
}

:deep(.el-tab-pane) {
  padding-top: 16px;
}
</style>
