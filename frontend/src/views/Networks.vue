<template>
  <div class="networks">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Réseaux Docker</span>
          <el-input
            v-model="searchQuery"
            placeholder="Rechercher par nom..."
            clearable
            style="width: 300px"
            :prefix-icon="Search"
          />
        </div>
      </template>
      <el-table
        v-loading="loading"
        :data="filteredNetworks"
        stripe
      >
        <el-table-column
          label="ID"
          width="140"
        >
          <template #default="{ row }">
            <el-tooltip
              :content="row.id"
              placement="top"
            >
              <span class="monospace">{{ row.id.substring(0, 12) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column
          label="Nom"
          min-width="150"
        >
          <template #default="{ row }">
            <span :title="row.name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Driver"
          width="120"
          prop="driver"
        />
        <el-table-column
          label="Scope"
          width="100"
          prop="scope"
        />
        <el-table-column
          label="Subnet"
          width="160"
        >
          <template #default="{ row }">
            <span v-if="row.subnet">{{ row.subnet }}</span>
            <span
              v-else
              class="text-muted"
            >—</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Gateway"
          width="140"
        >
          <template #default="{ row }">
            <span v-if="row.gateway">{{ row.gateway }}</span>
            <span
              v-else
              class="text-muted"
            >—</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Interne"
          width="110"
        >
          <template #default="{ row }">
            <el-tag
              v-if="row.internal"
              type="warning"
              size="small"
            >
              Interne
            </el-tag>
            <el-tag
              v-else
              type="success"
              size="small"
            >
              Externe
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!loading && networks.length === 0"
        description="Aucun réseau trouvé"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { networksApi } from '@/services/api'
import type { NetworkResponse } from '@/types/api'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

const networks = ref<NetworkResponse[]>([])
const loading = ref(false)
const searchQuery = ref('')

const filteredNetworks = computed(() => {
  if (!searchQuery.value) return networks.value
  const query = searchQuery.value.toLowerCase()
  return networks.value.filter((net) =>
    net.name.toLowerCase().includes(query),
  )
})

async function fetchNetworks() {
  loading.value = true
  try {
    const { data } = await networksApi.list()
    networks.value = data
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors du chargement des réseaux'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchNetworks()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.monospace {
  font-family: monospace;
  font-size: 0.85em;
}

.text-muted {
  color: var(--el-text-color-secondary);
}
</style>
