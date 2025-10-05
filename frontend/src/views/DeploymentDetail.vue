<template>
  <div class="deployment-detail">
    <el-card v-if="deploymentsStore.currentDeployment">
      <template #header>
        <div class="card-header">
          <span>Deployment Details</span>
          <el-tag :type="getStatusType(deploymentsStore.currentDeployment.status)">
            {{ deploymentsStore.currentDeployment.status }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ deploymentsStore.currentDeployment.id }}</el-descriptions-item>
        <el-descriptions-item label="Status">{{ deploymentsStore.currentDeployment.status }}</el-descriptions-item>
        <el-descriptions-item label="Created">{{ deploymentsStore.currentDeployment.created_at }}</el-descriptions-item>
        <el-descriptions-item label="Updated">{{ deploymentsStore.currentDeployment.updated_at }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 20px">
        <h3>Logs</h3>
        <el-input v-model="logs" type="textarea" :rows="15" readonly />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useDeploymentsStore } from '@/stores'

const route = useRoute()
const deploymentsStore = useDeploymentsStore()
const logs = ref('')
let unsubscribeLogs: (() => void) | null = null

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

onMounted(async () => {
  const id = route.params.id as string
  await deploymentsStore.fetchDeployment(id)
  
  // Subscribe to real-time logs
  unsubscribeLogs = deploymentsStore.subscribeToDeploymentLogs(id, (log: string) => {
    logs.value += log + '\n'
  })
})

onUnmounted(() => {
  if (unsubscribeLogs) {
    unsubscribeLogs()
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
