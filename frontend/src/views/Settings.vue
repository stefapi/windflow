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
        <el-card>
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <span>Gestion des Organisations</span>
                <el-badge
                  :value="orgsStore.total.value"
                  type="primary"
                  class="counter-badge"
                >
                  <el-tag type="info">
                    Total
                  </el-tag>
                </el-badge>
              </div>
              <el-button
                type="primary"
                @click="openOrgDialog()"
              >
                Ajouter
              </el-button>
            </div>
          </template>

          <!-- Filters Bar -->
          <div class="filters-bar">
            <div class="filters-left">
              <el-input
                v-model="orgFilters.search"
                placeholder="Rechercher par nom, slug ou description..."
                clearable
                class="search-input"
              >
                <template #prefix>
                  <el-icon>
                    <Search />
                  </el-icon>
                </template>
              </el-input>

              <el-button
                v-if="orgFilters.search"
                text
                @click="clearOrgFilters"
              >
                Effacer les filtres
              </el-button>
            </div>

            <div class="filters-right">
              <span class="results-count">
                {{ orgsResultsCountText }}
              </span>
            </div>
          </div>

          <!-- Bulk Actions Bar -->
          <transition name="slide-down">
            <div
              v-if="selectedOrgIds.length > 0"
              class="bulk-actions-bar"
            >
              <div class="bulk-actions-left">
                <el-tag
                  type="primary"
                  effect="dark"
                >
                  {{ selectedOrgIds.length }} sélectionnée{{ selectedOrgIds.length > 1 ? 's' : '' }}
                </el-tag>
                <el-button
                  text
                  size="small"
                  @click="clearOrgSelection"
                >
                  Annuler la sélection
                </el-button>
              </div>
              <div class="bulk-actions-right">
                <el-button
                  type="danger"
                  size="small"
                  :loading="bulkDeletingOrgs"
                  @click="showOrgBulkDeleteDialog"
                >
                  <el-icon class="el-icon--left">
                    <Delete />
                  </el-icon>
                  Supprimer
                </el-button>
              </div>
            </div>
          </transition>

          <!-- Organizations Table -->
          <el-table
            ref="orgsTableRef"
            v-loading="orgsStore.loading.value"
            :data="filteredOrganizations"
            @selection-change="handleOrgSelectionChange"
          >
            <el-table-column
              type="selection"
              width="55"
            />

            <el-table-column
              prop="name"
              label="Nom"
              min-width="140"
            />

            <el-table-column
              prop="slug"
              label="Slug"
              min-width="120"
            >
              <template #default="{ row }">
                <el-tag
                  type="info"
                  size="small"
                >
                  {{ row.slug || '—' }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column
              prop="description"
              label="Description"
              min-width="200"
            >
              <template #default="{ row }">
                {{ row.description || '—' }}
              </template>
            </el-table-column>

            <el-table-column
              prop="created_at"
              label="Créé le"
              width="180"
            >
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>

            <el-table-column
              label="Actions"
              width="120"
              fixed="right"
            >
              <template #default="{ row }">
                <ActionButtons
                  :actions="['edit', 'delete']"
                  @action="handleOrgAction($event, row)"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Users Tab -->
      <el-tab-pane
        label="Utilisateurs"
        name="users"
      >
        <el-card>
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <span>Gestion des Utilisateurs</span>
                <el-badge
                  :value="usersStore.total.value"
                  type="primary"
                  class="counter-badge"
                >
                  <el-tag type="info">
                    Total
                  </el-tag>
                </el-badge>
              </div>
              <el-button
                type="primary"
                @click="openUserDialog()"
              >
                Ajouter
              </el-button>
            </div>
          </template>

          <!-- Filters Bar -->
          <div class="filters-bar">
            <div class="filters-left">
              <el-select
                v-model="userFilters.admin"
                placeholder="Admin"
                clearable
                class="filter-select"
              >
                <el-option
                  label="Tous"
                  value="all"
                />
                <el-option
                  label="Admins"
                  value="admins"
                />
                <el-option
                  label="Non-admins"
                  value="non-admins"
                />
              </el-select>

              <el-input
                v-model="userFilters.search"
                placeholder="Rechercher par nom ou email..."
                clearable
                class="search-input"
              >
                <template #prefix>
                  <el-icon>
                    <Search />
                  </el-icon>
                </template>
              </el-input>

              <el-button
                v-if="userFilters.admin !== 'all' || userFilters.search"
                text
                @click="clearUserFilters"
              >
                Effacer les filtres
              </el-button>
            </div>

            <div class="filters-right">
              <span class="results-count">
                {{ usersResultsCountText }}
              </span>
            </div>
          </div>

          <!-- Bulk Actions Bar -->
          <transition name="slide-down">
            <div
              v-if="selectedUserIds.length > 0"
              class="bulk-actions-bar"
            >
              <div class="bulk-actions-left">
                <el-tag
                  type="primary"
                  effect="dark"
                >
                  {{ selectedUserIds.length }} sélectionné{{ selectedUserIds.length > 1 ? 's' : '' }}
                </el-tag>
                <el-button
                  text
                  size="small"
                  @click="clearUserSelection"
                >
                  Annuler la sélection
                </el-button>
              </div>
              <div class="bulk-actions-right">
                <el-button
                  size="small"
                  @click="showBulkAssignDialog"
                >
                  <el-icon class="el-icon--left">
                    <OfficeBuilding />
                  </el-icon>
                  Affecter à une organisation
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  :loading="bulkDeleting"
                  @click="showBulkDeleteDialog"
                >
                  <el-icon class="el-icon--left">
                    <Delete />
                  </el-icon>
                  Supprimer
                </el-button>
              </div>
            </div>
          </transition>

          <!-- Users Table -->
          <el-table
            ref="usersTableRef"
            v-loading="usersStore.loading.value"
            :data="filteredUsers"
            @selection-change="handleUserSelectionChange"
            @row-click="showUserDetails"
          >
            <el-table-column
              type="selection"
              width="55"
            />

            <el-table-column
              prop="username"
              label="Nom d'utilisateur"
              min-width="140"
            />

            <el-table-column
              prop="email"
              label="Email"
              min-width="200"
            />

            <el-table-column
              prop="full_name"
              label="Nom complet"
              min-width="140"
            >
              <template #default="{ row }">
                {{ row.full_name || '—' }}
              </template>
            </el-table-column>

            <el-table-column
              prop="is_active"
              label="Actif"
              width="80"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.is_active ? 'success' : 'danger'"
                  size="small"
                >
                  {{ row.is_active ? 'Oui' : 'Non' }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column
              prop="is_superuser"
              label="Admin"
              width="80"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.is_superuser ? 'warning' : 'info'"
                  size="small"
                >
                  {{ row.is_superuser ? 'Oui' : 'Non' }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column
              label="Actions"
              width="160"
              fixed="right"
            >
              <template #default="{ row }">
                <ActionButtons
                  :actions="['edit', 'password', 'delete']"
                  @action="handleUserAction($event, row)"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Organization Dialog -->
    <el-dialog
      v-model="orgDialog.visible"
      :title="orgDialog.isEdit ? 'Modifier l\'Organisation' : 'Ajouter une Organisation'"
      width="500px"
    >
      <el-form
        :model="orgDialog.form"
        label-width="120px"
      >
        <el-form-item
          label="Nom"
          required
        >
          <el-input v-model="orgDialog.form.name" />
        </el-form-item>
        <el-form-item label="Slug">
          <el-input
            v-model="orgDialog.form.slug"
            placeholder="Laisser vide pour générer automatiquement"
          >
            <template #prepend>
              <el-icon><Link /></el-icon>
            </template>
          </el-input>
          <div class="form-hint">
            Identifiant unique pour l'URL (ex: mon-organisation). Lettres minuscules, chiffres et tirets uniquement.
          </div>
        </el-form-item>
        <el-form-item label="Description">
          <el-input
            v-model="orgDialog.form.description"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="orgDialog.visible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          @click="saveOrg"
        >
          {{ orgDialog.isEdit ? 'Modifier' : 'Créer' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Bulk Delete Organizations Confirmation Dialog -->
    <el-dialog
      v-model="orgBulkDeleteDialogVisible"
      title="Confirmer la suppression groupée"
      width="500px"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="bulk-delete-alert"
      >
        <template #title>
          Vous êtes sur le point de supprimer <strong>{{ selectedOrgIds.length }}</strong> organisation{{ selectedOrgIds.length > 1 ? 's' : '' }}.
        </template>
      </el-alert>
      <div class="bulk-delete-list">
        <p>Organisations concernées :</p>
        <ul>
          <li
            v-for="id in selectedOrgIds.slice(0, 5)"
            :key="id"
          >
            {{ getOrgName(id) }}
          </li>
          <li
            v-if="selectedOrgIds.length > 5"
            class="more-items"
          >
            ... et {{ selectedOrgIds.length - 5 }} autre{{ selectedOrgIds.length - 5 > 1 ? 's' : '' }}
          </li>
        </ul>
      </div>
      <template #footer>
        <el-button @click="orgBulkDeleteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="danger"
          :loading="bulkDeletingOrgs"
          @click="confirmOrgBulkDelete"
        >
          Supprimer {{ selectedOrgIds.length }} organisation{{ selectedOrgIds.length > 1 ? 's' : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Password Dialog -->
    <el-dialog
      v-model="passwordDialog.visible"
      title="Changer le mot de passe"
      width="450px"
    >
      <el-form
        :model="passwordDialog.form"
        label-width="180px"
        @submit.prevent="savePassword"
      >
        <el-form-item label="Utilisateur">
          <el-input
            :value="passwordDialog.user?.username"
            disabled
          />
        </el-form-item>
        <el-form-item
          label="Nouveau mot de passe"
          required
        >
          <el-input
            v-model="passwordDialog.form.password"
            type="password"
            show-password
            placeholder="Minimum 8 caractères"
          />
        </el-form-item>
        <el-form-item
          label="Confirmer le mot de passe"
          required
        >
          <el-input
            v-model="passwordDialog.form.confirmPassword"
            type="password"
            show-password
            placeholder="Confirmer le mot de passe"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialog.visible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="passwordDialog.loading"
          @click="savePassword"
        >
          Enregistrer
        </el-button>
      </template>
    </el-dialog>

    <!-- User Dialog -->
    <el-dialog
      v-model="userDialog.visible"
      :title="userDialog.isEdit ? 'Modifier l\'Utilisateur' : 'Ajouter un Utilisateur'"
      width="500px"
    >
      <el-form
        :model="userDialog.form"
        label-width="140px"
      >
        <el-form-item
          label="Nom d'utilisateur"
          required
        >
          <el-input
            v-model="userDialog.form.username"
            :disabled="userDialog.isEdit"
          />
        </el-form-item>
        <el-form-item
          label="Email"
          required
        >
          <el-input v-model="userDialog.form.email" />
        </el-form-item>
        <el-form-item label="Nom complet">
          <el-input v-model="userDialog.form.full_name" />
        </el-form-item>
        <el-form-item
          v-if="!userDialog.isEdit"
          label="Mot de passe"
          required
        >
          <el-input
            v-model="userDialog.form.password"
            type="password"
            show-password
          />
        </el-form-item>
        <el-form-item label="Administrateur">
          <el-switch v-model="userDialog.form.is_superuser" />
        </el-form-item>
        <el-form-item label="Organisation">
          <el-select
            v-model="userDialog.form.organization_id"
            placeholder="Sélectionner une organisation"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="org in orgsStore.organizations.value"
              :key="org.id"
              :label="org.name"
              :value="org.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Actif">
          <el-switch v-model="userDialog.form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialog.visible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          @click="saveUser"
        >
          {{ userDialog.isEdit ? 'Modifier' : 'Créer' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- User Details Drawer -->
    <el-drawer
      v-model="userDetailsDrawer.visible"
      title="Détails de l'utilisateur"
      direction="rtl"
      size="400px"
    >
      <el-descriptions
        :column="1"
        border
      >
        <el-descriptions-item label="Nom d'utilisateur">
          {{ userDetailsDrawer.user?.username }}
        </el-descriptions-item>
        <el-descriptions-item label="Email">
          {{ userDetailsDrawer.user?.email }}
        </el-descriptions-item>
        <el-descriptions-item label="Nom complet">
          {{ userDetailsDrawer.user?.full_name || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="Statut">
          <el-tag
            :type="userDetailsDrawer.user?.is_active ? 'success' : 'danger'"
            size="small"
          >
            {{ userDetailsDrawer.user?.is_active ? 'Actif' : 'Inactif' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Administrateur">
          <el-tag
            :type="userDetailsDrawer.user?.is_superuser ? 'warning' : 'info'"
            size="small"
          >
            {{ userDetailsDrawer.user?.is_superuser ? 'Oui' : 'Non' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Organisation">
          {{ getOrganizationName(userDetailsDrawer.user?.organization_id) }}
        </el-descriptions-item>
        <el-descriptions-item label="Date de création">
          {{ formatDateTime(userDetailsDrawer.user?.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="Dernière modification">
          {{ formatDateTime(userDetailsDrawer.user?.updated_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="Dernière connexion">
          {{ userDetailsDrawer.user?.last_login ? formatDateTime(userDetailsDrawer.user?.last_login) : 'Jamais' }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="userDetailsDrawer.visible = false">
          Fermer
        </el-button>
        <el-button
          v-if="userDetailsDrawer.user"
          type="primary"
          @click="openUserDialog(userDetailsDrawer.user); userDetailsDrawer.visible = false"
        >
          Modifier
        </el-button>
      </template>
    </el-drawer>

    <!-- Bulk Delete Confirmation Dialog -->
    <el-dialog
      v-model="bulkDeleteDialogVisible"
      title="Confirmer la suppression groupée"
      width="500px"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="bulk-delete-alert"
      >
        <template #title>
          Vous êtes sur le point de supprimer <strong>{{ selectedUserIds.length }}</strong> utilisateur{{ selectedUserIds.length > 1 ? 's' : '' }}.
        </template>
      </el-alert>
      <div class="bulk-delete-list">
        <p>Utilisateurs concernés :</p>
        <ul>
          <li
            v-for="id in selectedUserIds.slice(0, 5)"
            :key="id"
          >
            {{ getUserName(id) }} ({{ getUserEmail(id) }})
          </li>
          <li
            v-if="selectedUserIds.length > 5"
            class="more-items"
          >
            ... et {{ selectedUserIds.length - 5 }} autre{{ selectedUserIds.length - 5 > 1 ? 's' : '' }}
          </li>
        </ul>
      </div>
      <template #footer>
        <el-button @click="bulkDeleteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="danger"
          :loading="bulkDeleting"
          @click="confirmBulkDelete"
        >
          Supprimer {{ selectedUserIds.length }} utilisateur{{ selectedUserIds.length > 1 ? 's' : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Bulk Assign Organization Dialog -->
    <el-dialog
      v-model="bulkAssignDialogVisible"
      title="Affecter à une organisation"
      width="500px"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="bulk-assign-alert"
      >
        <template #title>
          <strong>{{ selectedUserIds.length }}</strong> utilisateur{{ selectedUserIds.length > 1 ? 's' : '' }} seront affectés.
        </template>
      </el-alert>
      <el-form
        :model="bulkAssignForm"
        label-width="140px"
        class="bulk-assign-form"
      >
        <el-form-item
          label="Organisation"
          required
        >
          <el-select
            v-model="bulkAssignForm.organization_id"
            placeholder="Sélectionner une organisation"
            style="width: 100%"
          >
            <el-option
              v-for="org in orgsStore.organizations.value"
              :key="org.id"
              :label="org.name"
              :value="org.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="bulk-assign-list">
        <p>Utilisateurs concernés :</p>
        <ul>
          <li
            v-for="id in selectedUserIds.slice(0, 5)"
            :key="id"
          >
            {{ getUserName(id) }}
          </li>
          <li
            v-if="selectedUserIds.length > 5"
            class="more-items"
          >
            ... et {{ selectedUserIds.length - 5 }} autre{{ selectedUserIds.length - 5 > 1 ? 's' : '' }}
          </li>
        </ul>
      </div>
      <template #footer>
        <el-button @click="bulkAssignDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="bulkAssigning"
          :disabled="!bulkAssignForm.organization_id"
          @click="confirmBulkAssign"
        >
          Affecter {{ selectedUserIds.length }} utilisateur{{ selectedUserIds.length > 1 ? 's' : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * Settings Page
 * Administration page for managing Organizations and Users
 * Access restricted to superusers only
 */

import { ref, reactive, computed, onMounted } from 'vue'
import { Lock, Search, Delete, OfficeBuilding, Link } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useOrganizations } from '@/composables/useOrganizations'
import { useUsers } from '@/composables/useUsers'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import type { Organization, OrganizationCreate, OrganizationUpdate } from '@/types/api'
import type { User, UserCreate, UserUpdate } from '@/types/api'

// Stores
const authStore = useAuthStore()
const orgsStore = useOrganizations({ autoFetch: false })
const usersStore = useUsers({ autoFetch: false })

// Active tab
const activeTab = ref('organizations')

// Organizations table ref for selection
const orgsTableRef = ref()

// Organization filters
const orgFilters = reactive({
  search: '',
})

// Selection state for org bulk operations
const selectedOrgs = ref<Organization[]>([])
const selectedOrgIds = computed(() => selectedOrgs.value.map(o => o.id))

// Organization bulk operation state
const orgBulkDeleteDialogVisible = ref(false)
const bulkDeletingOrgs = ref(false)

// Users table ref for selection
const usersTableRef = ref()

// User filters
const userFilters = reactive({
  admin: 'all' as 'all' | 'admins' | 'non-admins',
  search: '',
})

// Selection state for bulk operations
const selectedUsers = ref<User[]>([])
const selectedUserIds = computed(() => selectedUsers.value.map(u => u.id))

// Bulk operation state
const bulkDeleteDialogVisible = ref(false)
const bulkDeleting = ref(false)
const bulkAssignDialogVisible = ref(false)
const bulkAssigning = ref(false)
const bulkAssignForm = reactive({
  organization_id: '' as string,
})

// Date formatting helper
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// DateTime formatting helper for details
function formatDateTime(dateStr: string | undefined | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// Get organization name by ID
function getOrganizationName(orgId: string | null | undefined): string {
  if (!orgId) return '—'
  const org = orgsStore.organizations.value.find(o => o.id === orgId)
  return org?.name || orgId
}

// Get user name by ID
function getUserName(id: string): string {
  const user = usersStore.users.value.find(u => u.id === id)
  return user?.full_name || user?.username || id
}

// Get user email by ID
function getUserEmail(id: string): string {
  const user = usersStore.users.value.find(u => u.id === id)
  return user?.email || id
}

// Get organization name by ID (for bulk delete dialog)
function getOrgName(id: string): string {
  const org = orgsStore.organizations.value.find(o => o.id === id)
  return org?.name || id
}

// =====================
// Organization Filters
// =====================

const filteredOrganizations = computed(() => {
  let result = orgsStore.organizations.value

  // Filter by search (name, slug, description)
  const searchTerm = orgFilters.search.toLowerCase().trim()
  if (searchTerm) {
    result = result.filter(o =>
      o.name.toLowerCase().includes(searchTerm) ||
      (o.slug && o.slug.toLowerCase().includes(searchTerm)) ||
      (o.description && o.description.toLowerCase().includes(searchTerm))
    )
  }

  return result
})

const orgsResultsCountText = computed(() => {
  const total = orgsStore.organizations.value.length
  const filtered = filteredOrganizations.value.length

  if (orgFilters.search && filtered !== total) {
    return `${filtered} organisations (sur ${total})`
  }
  return `${total} organisations`
})

function clearOrgFilters(): void {
  orgFilters.search = ''
}

// =====================
// Organization Selection
// =====================

function handleOrgSelectionChange(selection: Organization[]): void {
  selectedOrgs.value = selection
}

function clearOrgSelection(): void {
  orgsTableRef.value?.clearSelection()
  selectedOrgs.value = []
}

// =====================
// Organization Bulk Operations
// =====================

function showOrgBulkDeleteDialog(): void {
  orgBulkDeleteDialogVisible.value = true
}

async function confirmOrgBulkDelete(): Promise<void> {
  bulkDeletingOrgs.value = true

  try {
    const result = await orgsStore.deleteOrganizations(selectedOrgIds.value)

    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} organisation(s) supprimée(s)`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de la suppression de ${result.failed.length} organisation(s)`)
    } else {
      ElMessage.warning(`${result.success.length} supprimée(s), ${result.failed.length} échec(s)`)
    }

    orgBulkDeleteDialogVisible.value = false
    clearOrgSelection()
  } finally {
    bulkDeletingOrgs.value = false
  }
}

// =====================
// User Filters
// =====================

const filteredUsers = computed(() => {
  let result = usersStore.users.value

  // Filter by admin status
  if (userFilters.admin === 'admins') {
    result = result.filter(u => u.is_superuser)
  } else if (userFilters.admin === 'non-admins') {
    result = result.filter(u => !u.is_superuser)
  }

  // Filter by search
  const searchTerm = userFilters.search.toLowerCase().trim()
  if (searchTerm) {
    result = result.filter(u =>
      u.username.toLowerCase().includes(searchTerm) ||
      u.email.toLowerCase().includes(searchTerm) ||
      (u.full_name && u.full_name.toLowerCase().includes(searchTerm))
    )
  }

  return result
})

const usersResultsCountText = computed(() => {
  const total = usersStore.users.value.length
  const filtered = filteredUsers.value.length

  if ((userFilters.admin !== 'all' || userFilters.search) && filtered !== total) {
    return `${filtered} utilisateurs (sur ${total})`
  }
  return `${total} utilisateurs`
})

function clearUserFilters(): void {
  userFilters.admin = 'all'
  userFilters.search = ''
}

// =====================
// User Selection
// =====================

function handleUserSelectionChange(selection: User[]): void {
  selectedUsers.value = selection
}

function clearUserSelection(): void {
  usersTableRef.value?.clearSelection()
  selectedUsers.value = []
}

// =====================
// Bulk Operations
// =====================

function showBulkDeleteDialog(): void {
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
    clearUserSelection()
  } finally {
    bulkDeleting.value = false
  }
}

function showBulkAssignDialog(): void {
  bulkAssignForm.organization_id = ''
  bulkAssignDialogVisible.value = true
}

async function confirmBulkAssign(): Promise<void> {
  if (!bulkAssignForm.organization_id) return

  bulkAssigning.value = true

  try {
    const result = await usersStore.assignOrganization(selectedUserIds.value, bulkAssignForm.organization_id)

    if (result.failed.length === 0) {
      ElMessage.success(`${result.success.length} utilisateur(s) réassigné(s)`)
    } else if (result.success.length === 0) {
      ElMessage.error(`Échec de la réassignation de ${result.failed.length} utilisateur(s)`)
    } else {
      ElMessage.warning(`${result.success.length} réassigné(s), ${result.failed.length} échec(s)`)
    }

    bulkAssignDialogVisible.value = false
    clearUserSelection()
  } finally {
    bulkAssigning.value = false
  }
}

// =====================
// Organization Dialog
// =====================
const orgDialog = reactive({
  visible: false,
  isEdit: false,
  editId: null as string | null,
  form: {
    name: '',
    description: '',
  } as OrganizationCreate | OrganizationUpdate,
})

function openOrgDialog(org?: Organization) {
  if (org) {
    orgDialog.isEdit = true
    orgDialog.editId = org.id
    orgDialog.form = {
      name: org.name,
      slug: org.slug || '',
      description: org.description || '',
    }
  } else {
    orgDialog.isEdit = false
    orgDialog.editId = null
    orgDialog.form = { name: '', slug: '', description: '' }
  }
  orgDialog.visible = true
}

async function saveOrg() {
  if (orgDialog.isEdit && orgDialog.editId) {
    await orgsStore.updateOrganization(orgDialog.editId, orgDialog.form as OrganizationUpdate)
  } else {
    await orgsStore.createOrganization(orgDialog.form as OrganizationCreate)
  }
  orgDialog.visible = false
}

function handleOrgAction(action: ActionType, org: Organization) {
  switch (action) {
    case 'edit':
      openOrgDialog(org)
      break
    case 'delete':
      if (org.id) {
        orgsStore.deleteOrganization(org.id)
      }
      break
  }
}

// =====================
// User Dialog
// =====================
interface UserDialogForm {
  username: string
  email: string
  full_name: string
  password: string
  is_active: boolean
  is_superuser: boolean
  organization_id: string | null
}

const userDialog = reactive({
  visible: false,
  isEdit: false,
  editId: null as string | null,
  form: {
    username: '',
    email: '',
    full_name: '',
    password: '',
    is_active: true,
    is_superuser: false,
    organization_id: null,
  } as UserDialogForm,
})

function openUserDialog(user?: User) {
  if (user) {
    userDialog.isEdit = true
    userDialog.editId = user.id
    userDialog.form = {
      username: user.username,
      email: user.email,
      full_name: user.full_name || '',
      is_active: user.is_active,
      is_superuser: user.is_superuser,
      organization_id: user.organization_id || null,
      password: '',
    }
  } else {
    userDialog.isEdit = false
    userDialog.editId = null
    userDialog.form = {
      username: '',
      email: '',
      full_name: '',
      password: '',
      is_active: true,
      is_superuser: false,
      organization_id: null,
    }
  }
  userDialog.visible = true
}

async function saveUser() {
  if (userDialog.isEdit && userDialog.editId) {
    const updateData: UserUpdate = {
      email: userDialog.form.email,
      full_name: userDialog.form.full_name || undefined,
      is_active: userDialog.form.is_active,
      is_superuser: userDialog.form.is_superuser,
      organization_id: userDialog.form.organization_id || undefined,
    }
    await usersStore.updateUser(userDialog.editId, updateData)
  } else {
    const createData: UserCreate = {
      username: userDialog.form.username,
      email: userDialog.form.email,
      password: userDialog.form.password,
      full_name: userDialog.form.full_name || undefined,
      organization_id: userDialog.form.organization_id || undefined,
    }
    await usersStore.createUser(createData)
  }
  userDialog.visible = false
}

function handleUserAction(action: ActionType, user: User) {
  switch (action) {
    case 'edit':
      openUserDialog(user)
      break
    case 'password':
      openPasswordDialog(user)
      break
    case 'delete':
      if (user.id) {
        usersStore.deleteUser(user.id)
      }
      break
  }
}

// =====================
// Password Dialog
// =====================
const passwordDialog = reactive({
  visible: false,
  loading: false,
  user: null as User | null,
  form: {
    password: '',
    confirmPassword: '',
  },
})

function openPasswordDialog(user: User) {
  passwordDialog.user = user
  passwordDialog.form.password = ''
  passwordDialog.form.confirmPassword = ''
  passwordDialog.visible = true
}

async function savePassword() {
  if (!passwordDialog.form.password || passwordDialog.form.password.length < 8) {
    ElMessage.error('Le mot de passe doit contenir au moins 8 caractères')
    return
  }

  if (passwordDialog.form.password !== passwordDialog.form.confirmPassword) {
    ElMessage.error('Les mots de passe ne correspondent pas')
    return
  }

  if (!passwordDialog.user?.id) {
    return
  }

  passwordDialog.loading = true
  try {
    await usersStore.updatePassword(passwordDialog.user.id, passwordDialog.form.password)
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

function showUserDetails(row: User) {
  userDetailsDrawer.user = row
  userDetailsDrawer.visible = true
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
  background: white;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.counter-badge {
  margin-left: 8px;
}

:deep(.el-tab-pane) {
  padding-top: 16px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: var(--el-fill-color-light);
}

/* Filters Bar */
.filters-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background-color: var(--el-fill-color-light);
  border-radius: 8px;
}

.filters-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-select {
  width: 140px;
}

.search-input {
  width: 280px;
}

.filters-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.results-count {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

/* Bulk Actions Bar */
.bulk-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 16px;
  background-color: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 8px;
}

.bulk-actions-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bulk-actions-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Slide down transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Bulk Delete Dialog */
.bulk-delete-alert {
  margin-bottom: 16px;
}

.bulk-delete-list {
  margin-bottom: 16px;
}

.bulk-delete-list p {
  font-weight: 500;
  margin-bottom: 8px;
}

.bulk-delete-list ul {
  margin: 0;
  padding-left: 20px;
  max-height: 150px;
  overflow-y: auto;
}

.bulk-delete-list li {
  margin-bottom: 4px;
}

.bulk-delete-list .more-items {
  font-style: italic;
  color: var(--el-text-color-secondary);
}

/* Bulk Assign Dialog */
.bulk-assign-alert {
  margin-bottom: 16px;
}

.bulk-assign-form {
  margin-bottom: 16px;
}

.bulk-assign-list p {
  font-weight: 500;
  margin-bottom: 8px;
}

.bulk-assign-list ul {
  margin: 0;
  padding-left: 20px;
  max-height: 150px;
  overflow-y: auto;
}

.bulk-assign-list li {
  margin-bottom: 4px;
}

.bulk-assign-list .more-items {
  font-style: italic;
  color: var(--el-text-color-secondary);
}

/* Form Hint */
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}
</style>
