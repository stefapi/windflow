<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <el-alert v-if="dashboardStore.error" :title="dashboardStore.error" type="error" show-icon closable style="margin-bottom: 20px" />

    <!-- Statistiques globales -->
    <el-row :gutter="20" v-loading="dashboardStore.loading">
      <el-col :span="6">
        <CounterCard
          :count="dashboardStore.totalTargets"
          label="Targets"
          :icon="Monitor"
          to="/targets"
          :badge="dashboardStore.onlineTargets > 0 ? `${dashboardStore.onlineTargets} online` : undefined"
          badge-type="success"
        />
      </el-col>
      <el-col :span="6">
        <CounterCard
          :count="dashboardStore.totalStacks"
          label="Stacks"
          :icon="Files"
          to="/stacks"
        />
      </el-col>
      <el-col :span="6">
        <CounterCard
          :count="dashboardStore.activeDeployments"
          label="Deployments"
          :icon="Upload"
          to="/deployments"
        />
      </el-col>
      <el-col :span="6">
        <CounterCard
          :count="dashboardStore.totalWorkflows"
          label="Workflows"
          :icon="Connection"
          to="/workflows"
        />
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
import { Monitor, Files, Upload, Connection } from '@element-plus/icons-vue'
import { useDashboardStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import CounterCard from '@/components/ui/CounterCard.vue'
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
