<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <el-alert
      v-if="dashboardStore.error"
      :title="dashboardStore.error"
      type="error"
      show-icon
      closable
      style="margin-bottom: 20px"
    />

    <!-- Statistiques globales (STORY-432) -->
    <el-row
      v-loading="dashboardStore.loading"
      :gutter="20"
    >
      <el-col :span="6">
        <CounterCard
          :count="dashboardStore.containers.total"
          label="Containers"
          :icon="Box"
          to="/containers"
          :running-count="dashboardStore.containers.running"
          :stopped-count="dashboardStore.containers.stopped"
        />
      </el-col>
      <el-col :span="6">
        <CounterCard
          :count="dashboardStore.stacks.total"
          label="Stacks"
          :icon="Files"
          to="/stacks"
          :running-count="dashboardStore.stacks.running"
          :stopped-count="dashboardStore.stacks.stopped"
        />
      </el-col>
      <el-col :span="6">
        <CounterCard
          :count="0"
          label="VMs"
          :icon="Monitor"
          to="/vms"
          badge="Coming soon"
          badge-type="info"
        />
      </el-col>
    </el-row>

    <!-- Derniers déploiements (STORY-433) -->
    <el-row
      :gutter="20"
      style="margin-top: 20px"
    >
      <el-col :span="24">
        <RecentDeploymentsWidget :limit="10" />
      </el-col>
    </el-row>

    <!-- Métriques système unifiées (valeurs actuelles + historique) -->
    <el-row
      :gutter="20"
      style="margin-top: 20px"
    >
      <el-col :span="24">
        <ResourceMetricsWidget
          :metrics="dashboardStore.resourceMetrics"
          :error="metricsError"
          :target-name="targetsStore.currentTarget?.name ?? undefined"
          :loading="dashboardStore.loading"
          :no-target="!targetsStore.currentTarget"
        />
      </el-col>
    </el-row>

    <!-- Métriques déploiements -->
    <el-row
      :gutter="20"
      style="margin-top: 20px"
    >
      <el-col :span="24">
        <DeploymentMetricsWidget :metrics="dashboardStore.deploymentMetrics" />
      </el-col>
    </el-row>

    <!-- Alertes + Santé targets -->
    <el-row
      :gutter="20"
      style="margin-top: 20px"
    >
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
    <el-row
      :gutter="20"
      style="margin-top: 20px"
    >
      <el-col :span="24">
        <ActivityFeedWidget :activities="dashboardStore.recentActivity" />
      </el-col>
    </el-row>

    <!-- Actions rapides -->
    <el-row
      :gutter="20"
      style="margin-top: 20px"
    >
      <el-col :span="24">
        <el-card header="Quick Actions">
          <el-button
            type="primary"
            @click="$router.push('/stacks')"
          >
            Create Stack
          </el-button>
          <el-button
            type="success"
            @click="$router.push('/deployments')"
          >
            Deploy
          </el-button>
          <el-button
            :loading="dashboardStore.loading"
            @click="refreshDashboard"
          >
            Refresh
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- Zone widgets plugins (STORY-434) -->
    <PluginWidgetZone />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Monitor, Files, Box } from '@element-plus/icons-vue'
import { useDashboardStore, usePluginWidgetStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useTargetsStore } from '@/stores/targets'
import CounterCard from '@/components/ui/CounterCard.vue'
import TargetHealthWidget from '@/components/dashboard/TargetHealthWidget.vue'
import ActivityFeedWidget from '@/components/dashboard/ActivityFeedWidget.vue'
import DeploymentMetricsWidget from '@/components/dashboard/DeploymentMetricsWidget.vue'
import AlertsNotificationsWidget from '@/components/dashboard/AlertsNotificationsWidget.vue'
import ResourceMetricsWidget from '@/components/dashboard/ResourceMetricsWidget.vue'
import RecentDeploymentsWidget from '@/components/dashboard/RecentDeploymentsWidget.vue'
import PluginWidgetZone from '@/components/dashboard/PluginWidgetZone.vue'

// Dev-only: import placeholder widget
const PlaceholderWidget = import.meta.env.DEV
  ? () => import('@/components/dashboard/plugins/PlaceholderWidget.vue')
  : null

const authStore = useAuthStore()
const dashboardStore = useDashboardStore()
const targetsStore = useTargetsStore()
const pluginWidgetStore = usePluginWidgetStore()

// Polling pour les métriques système (toutes les 30s)
let metricsInterval: number | null = null
const metricsError = ref<string | null>(null)

// Dev-only: register placeholder widget
async function registerDevPlaceholderWidget(): Promise<void> {
  if (PlaceholderWidget) {
    try {
      const module = await PlaceholderWidget()
      pluginWidgetStore.registerWidget({
        pluginId: 'dev-placeholder',
        widget: {
          id: 'dev-placeholder-widget',
          component: module.default,
          title: 'Demo Widget (Dev Mode)',
          order: 999,
          props: {
            pluginName: 'dev-placeholder',
            version: '1.0.0',
          },
        },
      })
    } catch (error) {
      console.error('Failed to load placeholder widget:', error)
    }
  }
}

async function refreshDashboard(): Promise<void> {
  const orgId = authStore.organizationId || undefined
  try {
    metricsError.value = null
    await dashboardStore.fetchDashboardStats(orgId)
  } catch {
    metricsError.value = 'Unable to retrieve system metrics'
  }
}

onMounted(() => {
  refreshDashboard()
  // Polling toutes les 30 secondes
  metricsInterval = window.setInterval(refreshDashboard, 30000)
  // Dev-only: register placeholder widget
  registerDevPlaceholderWidget()
})

onUnmounted(() => {
  if (metricsInterval) {
    window.clearInterval(metricsInterval)
    metricsInterval = null
  }
  // Dev-only: unregister placeholder widget
  if (import.meta.env.DEV) {
    pluginWidgetStore.unregisterPlugin('dev-placeholder')
  }
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
