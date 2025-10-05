<template>
  <div class="deployments">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Deployments</span>
          <el-button type="primary" @click="showDialog = true">New Deployment</el-button>
        </div>
      </template>
      <el-table :data="deploymentsStore.deployments" v-loading="deploymentsStore.loading">
        <el-table-column prop="id" label="ID" width="100" />
        <el-table-column prop="status" label="Status">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created At" />
        <el-table-column label="Actions" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetails(row.id)">Details</el-button>
            <el-button size="small" type="warning" @click="cancelDeployment(row.id)" v-if="row.status === 'running'">Cancel</el-button>
            <el-button size="small" type="info" @click="retryDeployment(row.id)" v-if="row.status === 'failed'">Retry</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" title="Create Deployment" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="Stack">
          <el-select v-model="form.stack_id" placeholder="Select Stack" style="width: 100%">
            <el-option v-for="stack in stacksStore.stacks" :key="stack.id" :label="stack.name" :value="stack.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Target">
          <el-select v-model="form.target_id" placeholder="Select Target" style="width: 100%">
            <el-option v-for="target in targetsStore.targets" :key="target.id" :label="target.name" :value="target.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">Cancel</el-button>
        <el-button type="primary" @click="handleCreate">Deploy</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDeploymentsStore, useStacksStore, useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import type { DeploymentCreate } from '@/types/api'

const router = useRouter()
const deploymentsStore = useDeploymentsStore()
const stacksStore = useStacksStore()
const targetsStore = useTargetsStore()
const authStore = useAuthStore()
const showDialog = ref(false)

const form = reactive<DeploymentCreate>({
  stack_id: '',
  target_id: '',
})

const getStatusType = (status: string) => {
  const map: Record<string, any> = {
    completed: 'success',
    running: 'primary',
    pending: 'info',
    failed: 'danger',
    cancelled: 'warning',
  }
  return map[status] || 'info'
}

const handleCreate = async () => {
  try {
    await deploymentsStore.createDeployment({ ...form })
    ElMessage.success('Deployment started successfully')
    showDialog.value = false
    form.stack_id = ''
    form.target_id = ''
  } catch (error) {
    ElMessage.error('Failed to create deployment')
  }
}

const viewDetails = (id: string) => {
  router.push(`/deployments/${id}`)
}

const cancelDeployment = async (id: string) => {
  try {
    await deploymentsStore.cancelDeployment(id)
    ElMessage.success('Deployment cancelled')
  } catch (error) {
    ElMessage.error('Failed to cancel deployment')
  }
}

const retryDeployment = async (id: string) => {
  try {
    await deploymentsStore.retryDeployment(id)
    ElMessage.success('Deployment retried')
  } catch (error) {
    ElMessage.error('Failed to retry deployment')
  }
}

onMounted(async () => {
  const orgId = authStore.organizationId || undefined
  await Promise.all([
    deploymentsStore.fetchDeployments(orgId),
    stacksStore.fetchStacks(orgId),
    targetsStore.fetchTargets(orgId),
  ])
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
