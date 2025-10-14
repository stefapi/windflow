<template>
  <div class="dashboard">
    <h1>Dashboard</h1>
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card>
          <el-statistic title="Total Targets" :value="targetsStore.targets?.length || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="Total Stacks" :value="stacksStore.stacks?.length || 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="Active Deployments" :value="activeDeployments" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="Workflows" :value="workflowsStore.workflows?.length || 0" />
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card header="Recent Deployments">
          <el-table :data="recentDeployments" style="width: 100%">
            <el-table-column prop="id" label="ID" width="180" />
            <el-table-column prop="status" label="Status" />
            <el-table-column prop="created_at" label="Created" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="Quick Actions">
          <el-button type="primary" @click="$router.push('/stacks')">Create Stack</el-button>
          <el-button type="success" @click="$router.push('/deployments')">Deploy</el-button>
          <el-button type="info" @click="$router.push('/marketplace')">Browse Templates</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useTargetsStore, useStacksStore, useDeploymentsStore, useWorkflowsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const targetsStore = useTargetsStore()
const stacksStore = useStacksStore()
const deploymentsStore = useDeploymentsStore()
const workflowsStore = useWorkflowsStore()

const activeDeployments = computed(() =>
  deploymentsStore.deployments?.filter(d => d.status === 'running' || d.status === 'pending').length || 0
)

const recentDeployments = computed(() =>
  deploymentsStore.deployments?.slice(0, 5) || []
)

onMounted(async () => {
  const orgId = authStore.organizationId || undefined
  await Promise.all([
    targetsStore.fetchTargets(orgId),
    stacksStore.fetchStacks(orgId),
    deploymentsStore.fetchDeployments(orgId),
    workflowsStore.fetchWorkflows(orgId),
  ])
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}
</style>
