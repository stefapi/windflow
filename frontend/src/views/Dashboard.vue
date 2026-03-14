<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <el-alert v-if="dashboardStore.error" :title="dashboardStore.error" type="error" show-icon closable style="margin-bottom: 20px" />

    <!-- Statistiques globales -->
    <el-row :gutter="20" v-loading="dashboardStore.loading">
      <el-col :span="6">
        <el-card class="clickable-card" @click="$router.push('/targets')">
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
        <el-card class="clickable-card" @click="$router.push('/stacks')">
          <el-statistic title="Total Stacks" :value="dashboardStore.totalStacks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="clickable-card" @click="$router.push('/deployments')">
          <el-statistic title="Active Deployments" :value="dashboardStore.activeDeployments" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="clickable-card" @click="$router.push('/workflows')">
          <el-statistic title="Workflows" :value="dashboardStore.totalWorkflows" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Graphiques temps réel CPU/RAM -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <ResourceChartsWidget :metrics="dashboardStore.resourceMetrics" />
      </el-col>
    </el-row>

    <!-- Métriques déploiements -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <DeploymentMetricsWidget :metrics="dashboardStore.deploymentMetrics" />
      </el-col>
    </el-row>

    <!-- Alertes + Santé targets -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <AlertsNotificationsWidget :alerts="dashboardStore.alerts" />
      </el-col>
      <el-col :span="12">
        <TargetHealthWidget
          :target-health="dashboardStore.targetHealth"
          :targets-detail="dashboardStore.targetsDetail"
        />
      </el-col>
    </el-row>

    <!-- Activité récente -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <ActivityFeedWidget :activities="dashboardStore.recentActivity" />
      </el-col>
    </el-row>

    <!-- Actions rapides -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card header="Quick Actions">
          <el-button type="primary" @click="$router.push('/stacks')">Create Stack</el-button>
          <el-button type="success" @click="$router.push('/deployments')">Deploy</el-button>
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
import AlertsNotificationsWidget from '@/components/dashboard/AlertsNotificationsWidget.vue'
import ResourceChartsWidget from '@/components/dashboard/ResourceChartsWidget.vue'

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

.clickable-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.clickable-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
</style>
