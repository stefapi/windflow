<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span>Gestion des Utilisateurs</span>
          <el-badge
            :value="total"
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
          @click="$emit('add')"
        >
          Ajouter
        </el-button>
      </div>
    </template>

    <!-- Filters Bar -->
    <div class="filters-bar">
      <div class="filters-left">
        <el-select
          v-model="filters.admin"
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
          v-model="filters.search"
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
          v-if="filters.admin !== 'all' || filters.search"
          text
          @click="clearFilters"
        >
          Effacer les filtres
        </el-button>
      </div>

      <div class="filters-right">
        <span class="results-count">
          {{ resultsCountText }}
        </span>
      </div>
    </div>

    <!-- Bulk Actions Bar -->
    <transition name="slide-down">
      <div
        v-if="selectedIds.length > 0"
        class="bulk-actions-bar"
      >
        <div class="bulk-actions-left">
          <el-tag
            type="primary"
            effect="dark"
          >
            {{ selectedIds.length }} sélectionné{{ selectedIds.length > 1 ? 's' : '' }}
          </el-tag>
          <el-button
            text
            size="small"
            @click="clearSelection"
          >
            Annuler la sélection
          </el-button>
        </div>
        <div class="bulk-actions-right">
          <el-button
            size="small"
            @click="$emit('bulk-assign', selectedIds)"
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
            @click="$emit('bulk-delete', selectedIds)"
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
      ref="tableRef"
      v-loading="loading"
      stripe
      :data="filteredUsers"
      @selection-change="handleSelectionChange"
      @row-click="handleRowClick"
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
            @action="handleAction($event, row)"
          />
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Search, Delete, OfficeBuilding } from '@element-plus/icons-vue'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import type { User } from '@/types/api'

interface Props {
  users: User[]
  total: number
  loading: boolean
  bulkDeleting?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  bulkDeleting: false,
})

const emit = defineEmits<{
  'add': []
  'edit': [user: User]
  'password': [user: User]
  'delete': [userId: string]
  'bulk-delete': [userIds: string[]]
  'bulk-assign': [userIds: string[]]
  'show-details': [user: User]
}>()

// Table ref
const tableRef = ref()

// Filters
const filters = reactive({
  admin: 'all' as 'all' | 'admins' | 'non-admins',
  search: '',
})

// Selection
const selectedUsers = ref<User[]>([])
const selectedIds = computed(() => selectedUsers.value.map(u => u.id))

// Computed filtered users
const filteredUsers = computed(() => {
  let result = props.users

  // Filter by admin status
  if (filters.admin === 'admins') {
    result = result.filter(u => u.is_superuser)
  } else if (filters.admin === 'non-admins') {
    result = result.filter(u => !u.is_superuser)
  }

  // Filter by search
  const searchTerm = filters.search.toLowerCase().trim()
  if (searchTerm) {
    result = result.filter(u =>
      u.username.toLowerCase().includes(searchTerm) ||
      u.email.toLowerCase().includes(searchTerm) ||
      (u.full_name && u.full_name.toLowerCase().includes(searchTerm))
    )
  }

  return result
})

const resultsCountText = computed(() => {
  const total = props.users.length
  const filtered = filteredUsers.value.length

  if ((filters.admin !== 'all' || filters.search) && filtered !== total) {
    return `${filtered} utilisateurs (sur ${total})`
  }
  return `${total} utilisateurs`
})

// Methods
function clearFilters(): void {
  filters.admin = 'all'
  filters.search = ''
}

function handleSelectionChange(selection: User[]): void {
  selectedUsers.value = selection
}

function clearSelection(): void {
  tableRef.value?.clearSelection()
  selectedUsers.value = []
}

function handleAction(action: ActionType, user: User): void {
  switch (action) {
    case 'edit':
      emit('edit', user)
      break
    case 'password':
      emit('password', user)
      break
    case 'delete':
      if (user.id) {
        emit('delete', user.id)
      }
      break
  }
}

function handleRowClick(row: User): void {
  emit('show-details', row)
}

// Expose clearSelection for parent component
defineExpose({
  clearSelection,
})
</script>

<script lang="ts">
export default {
  name: 'UsersTab',
}
</script>

<style scoped>
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

/* Filters Bar */
.filters-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background-color: var(--color-bg-secondary);
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

/* Table row cursor */
:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: var(--el-fill-color-light);
}
</style>
