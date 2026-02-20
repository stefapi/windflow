<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <el-alert v-if="dashboardStore.error" :title="dashboardStore.error" type="error" show-icon closable style="margin-bottom: 20px" />

    <!-- Statistiques globales -->
    <el-row :gutter="20" v-loading="dashboardStore.loading">
      <el-col :span="6">
        <el-card>
          <el-statistic title="Total Targets" :value="dashboardStore.totalTargets">
            <template #suffix>
              <el-tag type="success" size="small" v-if="dashboardStore.onlineTargets > 0">
                {{ dashboardStore.onlineTargets }} online
              </el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="Total Stacks" :value="dashboardStore.totalStacks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="Active Deployments" :value="dashboardStore.activeDeployments" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <el-statistic title="Workflows" :value="dashboardStore.totalWorkflows" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Métriques déploiements -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <DeploymentMetricsWidget :metrics="dashboardStore.deploymentMetrics" />
      </el-col>
    </el-row>

    <!-- Santé targets + Activité récente -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <TargetHealthWidget
          :target-health="dashboardStore.targetHealth"
          :targets-detail="dashboardStore.targetsDetail"
        />
      </el-col>
      <el-col :span="12">
        <ActivityFeedWidget :activities="dashboardStore.recentActivity" />
      </el-col>
    </el-row>

    <!-- Actions rapides -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card header="Quick Actions">
          <el-button type="primary" @click="$router.push('/stacks')">Create Stack</el-button>
          <el-button type="success" @click="$router.push('/deployments')">Deploy</el-button>
          <el-button type="info" @click="$router.push('/marketplace')">Browse Templates</el-button>
          <el-button @click="refreshDashboard" :loading="dashboardStore.loading">
            Refresh
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useDashboardStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import TargetHealthWidget from '@/components/dashboard/TargetHealthWidget.vue'
import ActivityFeedWidget from '@/components/dashboard/ActivityFeedWidget.vue'
import DeploymentMetricsWidget from '@/components/dashboard/DeploymentMetricsWidget.vue'

const authStore = useAuthStore()
const dashboardStore = useDashboardStore()

async function refreshDashboard(): Promise<void> {
  const orgId = authStore.organizationId || undefined
  await dashboardStore.fetchDashboardStats(orgId)
}

onMounted(() => {
  refreshDashboard()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}
</style>
