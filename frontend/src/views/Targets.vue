<template>
  <div class="targets">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Targets Management</span>
          <el-button type="primary" @click="showDialog = true">Add Target</el-button>
        </div>
      </template>
      <el-table
        :data="targetsStore.targets"
        v-loading="targetsStore.loading"
        :expand-row-keys="expandedRowId ? [expandedRowId] : []"
        row-key="id"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="capabilities-section" v-loading="loadingCapabilities.has(row.id)">
              <h4 class="capabilities-title">Detected Capabilities</h4>
              <el-table
                :data="row.capabilities"
                v-if="row.capabilities && row.capabilities.length > 0"
                class="capabilities-table"
              >
                <el-table-column prop="capability_type" label="Capability Type" width="250">
                  <template #default="{ row: capRow }">
                    <el-tag size="small">{{ capRow.capability_type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="version" label="Version">
                  <template #default="{ row: capRow }">
                    {{ capRow.version || 'N/A' }}
                  </template>
                </el-table-column>
              </el-table>
              <div v-else-if="!loadingCapabilities.has(row.id)" class="no-capabilities">
                <el-empty description="No capabilities detected. Click 'Scan' to detect capabilities." />
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="host" label="Host" />
        <el-table-column prop="port" label="Port" width="100" />
        <el-table-column label="Status" width="150">
          <template #default="{ row }">
            <div class="status-indicator">
              <span class="status-dot" :class="`status-${row.status}`" />
              {{ row.status }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="250">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              :icon="Refresh"
              @click="refreshCapabilities(row.id)"
              :loading="scanningTargets.has(row.id)"
              title="Refresh capabilities"
            >
              Scan
            </el-button>
            <el-button size="small" type="danger" @click="deleteTarget(row.id)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="Add Target" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="Type">
          <el-select v-model="form.type" style="width: 100%">
            <el-option label="Docker" value="docker" />
            <el-option label="Docker Swarm" value="docker_swarm" />
            <el-option label="Kubernetes" value="kubernetes" />
            <el-option label="VM" value="vm" />
            <el-option label="Physical" value="physical" />
          </el-select>
        </el-form-item>
        <el-form-item label="Host">
          <el-input v-model="form.host" />
        </el-form-item>
        <el-form-item label="Port">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="Description">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">Cancel</el-button>
        <el-button type="primary" @click="handleCreate">Create</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { targetsApi } from '@/services/api'
import type { TargetCreate, Target } from '@/types/api'

const targetsStore = useTargetsStore()
const authStore = useAuthStore()
const showDialog = ref(false)
const scanningTargets = ref<Set<string>>(new Set())
const expandedRowId = ref<string | null>(null)
const loadingCapabilities = ref<Set<string>>(new Set())

const form = reactive<TargetCreate>({
  name: '',
  type: 'docker',
  host: '',
  port: 22,
  description: '',
  organization_id: authStore.organizationId || '',
})

const handleExpandChange = async (row: Target, expandedRows: Target[]) => {
  if (expandedRows.length === 0) {
    expandedRowId.value = null
  } else {
    expandedRowId.value = row.id

    // Charger les capabilities si elles ne sont pas déjà présentes
    if (!row.capabilities || row.capabilities.length === 0) {
      await loadCapabilities(row.id)
    }
  }
}

const loadCapabilities = async (targetId: string) => {
  loadingCapabilities.value.add(targetId)

  try {
    const response = await targetsApi.getCapabilities(targetId)

    // Mettre à jour le target dans le store avec les capabilities
    const targetIndex = targetsStore.targets.findIndex(t => t.id === targetId)
    if (targetIndex !== -1) {
      targetsStore.targets[targetIndex].capabilities = response.data.capabilities
    }
  } catch (error) {
    ElMessage.error('Failed to load capabilities')
    console.error('Error loading capabilities:', error)
  } finally {
    loadingCapabilities.value.delete(targetId)
  }
}

const handleCreate = async () => {
  try {
    await targetsStore.createTarget({ ...form })
    ElMessage.success('Target created successfully')
    showDialog.value = false
    Object.assign(form, { name: '', type: 'docker', host: '', port: 22, description: '' })
  } catch {
    ElMessage.error('Failed to create target')
  }
}

const deleteTarget = async (id: string) => {
  try {
    await targetsStore.deleteTarget(id)
    ElMessage.success('Target deleted successfully')
  } catch {
    ElMessage.error('Failed to delete target')
  }
}

const refreshCapabilities = async (targetId: string) => {
  try {
    scanningTargets.value.add(targetId)
    await targetsStore.scanTarget(targetId)

    // Recharger les capabilities après le scan
    await loadCapabilities(targetId)

    ElMessage.success('Capabilities refreshed successfully')
  } catch {
    ElMessage.error('Failed to refresh capabilities')
  } finally {
    scanningTargets.value.delete(targetId)
  }
}

onMounted(() => {
  targetsStore.fetchTargets(authStore.organizationId || undefined)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-online {
  background-color: #67c23a; /* Green */
}

.status-offline {
  background-color: #f56c6c; /* Red */
}

.status-error {
  background-color: #e6a23c; /* Orange */
}

.status-maintenance {
  background-color: #f0ad4e; /* Yellow */
}

.capabilities-section {
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin: 10px 0;
}

.capabilities-title {
  margin: 0 0 15px 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.capabilities-table {
  background-color: white;
  border-radius: 4px;
}

.no-capabilities {
  padding: 20px;
  text-align: center;
}
</style>
