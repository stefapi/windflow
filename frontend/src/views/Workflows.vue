<template>
  <div class="workflows">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Workflows</span>
          <el-button type="primary" @click="createWorkflow">Create Workflow</el-button>
        </div>
      </template>
      <el-table :data="workflowsStore.workflows" v-loading="workflowsStore.loading">
        <el-table-column prop="name" label="Name" />
        <el-table-column prop="description" label="Description" />
        <el-table-column label="Nodes" width="100">
          <template #default="{ row }">
            {{ row.nodes?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="editWorkflow(row.id)">Edit</el-button>
            <el-button size="small" type="success" @click="executeWorkflow(row.id)">Execute</el-button>
            <el-button size="small" type="danger" @click="deleteWorkflow(row.id)">Delete</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkflowsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const workflowsStore = useWorkflowsStore()
const authStore = useAuthStore()

const createWorkflow = () => {
  router.push('/workflows/new/edit')
}

const editWorkflow = (id: string) => {
  router.push(`/workflows/${id}/edit`)
}

const executeWorkflow = async (id: string) => {
  try {
    const executionId = await workflowsStore.executeWorkflow(id)
    ElMessage.success(`Workflow execution started: ${executionId}`)
  } catch (error) {
    ElMessage.error('Failed to execute workflow')
  }
}

const deleteWorkflow = async (id: string) => {
  try {
    await workflowsStore.deleteWorkflow(id)
    ElMessage.success('Workflow deleted successfully')
  } catch (error) {
    ElMessage.error('Failed to delete workflow')
  }
}

onMounted(() => {
  workflowsStore.fetchWorkflows(authStore.organizationId || undefined)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
