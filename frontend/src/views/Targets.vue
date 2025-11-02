<template>
  <div class="targets">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Targets Management</span>
          <el-button type="primary" @click="showDialog = true">Add Target</el-button>
        </div>
      </template>
      <el-table :data="targetsStore.targets" v-loading="targetsStore.loading">
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
        <el-table-column label="Actions" width="120">
          <template #default="{ row }">
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
import type { TargetCreate } from '@/types/api'

const targetsStore = useTargetsStore()
const authStore = useAuthStore()
const showDialog = ref(false)

const form = reactive<TargetCreate>({
  name: '',
  type: 'docker',
  host: '',
  port: 22,
  description: '',
  organization_id: authStore.organizationId || '',
})

const handleCreate = async () => {
  try {
    await targetsStore.createTarget({ ...form })
    ElMessage.success('Target created successfully')
    showDialog.value = false
    Object.assign(form, { name: '', type: 'docker', host: '', port: 22, description: '' })
  } catch (_error) {
    ElMessage.error('Failed to create target')
  }
}

const deleteTarget = async (id: string) => {
  try {
    await targetsStore.deleteTarget(id)
    ElMessage.success('Target deleted successfully')
  } catch (_error) {
    ElMessage.error('Failed to delete target')
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
</style>
