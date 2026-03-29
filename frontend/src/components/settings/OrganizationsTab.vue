<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span>Gestion des Organisations</span>
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
        <el-input
          v-model="filters.search"
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
          v-if="filters.search"
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
            {{ selectedIds.length }} sélectionnée{{ selectedIds.length > 1 ? 's' : '' }}
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

    <!-- Organizations Table -->
    <el-table
      ref="tableRef"
      v-loading="loading"
      stripe
      :data="filteredOrganizations"
      @selection-change="handleSelectionChange"
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
            @action="handleAction($event, row)"
          />
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { Search, Delete } from '@element-plus/icons-vue'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import type { Organization } from '@/types/api'

interface Props {
  organizations: Organization[]
  total: number
  loading: boolean
  bulkDeleting?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  bulkDeleting: false,
})

const emit = defineEmits<{
  'add': []
  'edit': [organization: Organization]
  'delete': [organizationId: string]
  'bulk-delete': [organizationIds: string[]]
}>()

// Table ref
const tableRef = ref()

// Filters
const filters = reactive({
  search: '',
})

// Selection
const selectedOrganizations = ref<Organization[]>([])
const selectedIds = computed(() => selectedOrganizations.value.map(o => o.id))

// Computed filtered organizations
const filteredOrganizations = computed(() => {
  let result = props.organizations

  const searchTerm = filters.search.toLowerCase().trim()
  if (searchTerm) {
    result = result.filter(o =>
      o.name.toLowerCase().includes(searchTerm) ||
      (o.slug && o.slug.toLowerCase().includes(searchTerm)) ||
      (o.description && o.description.toLowerCase().includes(searchTerm))
    )
  }

  return result
})

const resultsCountText = computed(() => {
  const total = props.organizations.length
  const filtered = filteredOrganizations.value.length

  if (filters.search && filtered !== total) {
    return `${filtered} organisations (sur ${total})`
  }
  return `${total} organisations`
})

// Methods
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function clearFilters(): void {
  filters.search = ''
}

function handleSelectionChange(selection: Organization[]): void {
  selectedOrganizations.value = selection
}

function clearSelection(): void {
  tableRef.value?.clearSelection()
  selectedOrganizations.value = []
}

function handleAction(action: ActionType, org: Organization): void {
  switch (action) {
    case 'edit':
      emit('edit', org)
      break
    case 'delete':
      if (org.id) {
        emit('delete', org.id)
      }
      break
  }
}

// Expose clearSelection for parent component
defineExpose({
  clearSelection,
})
</script>

<script lang="ts">
export default {
  name: 'OrganizationsTab',
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
  padding: 12px 16px;
  margin-bottom: 16px;
  background-color: var(--color-bg-secondary);
  border-radius: 8px;
}

.filters-left {
  display: flex;
  align-items: center;
  gap: 12px;
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
</style>
