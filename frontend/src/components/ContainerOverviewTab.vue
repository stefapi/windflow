<template>
  <div class="overview-grid">
    <!-- Card Services (bleu) -->
    <el-card class="overview-card card-services" shadow="hover">
      <template #header>
        <div class="card-header header-blue">
          <el-icon><Monitor /></el-icon>
          <span>Services</span>
          <el-tag
            v-if="projectName"
            size="small"
            type="info"
            class="ml-2"
          >
            {{ projectName }}
          </el-tag>
        </div>
      </template>
      <div v-loading="servicesLoading">
        <el-table
          v-if="stackServices.length > 0"
          :data="stackServices"
          stripe
          size="small"
          max-height="300"
        >
          <el-table-column
            label="Nom"
            min-width="140"
          >
            <template #default="{ row }">
              {{ row.name }}
            </template>
          </el-table-column>
          <el-table-column
            label="Image"
            min-width="160"
          >
            <template #default="{ row }">
              <code class="text-xs">{{ row.image }}</code>
            </template>
          </el-table-column>
          <el-table-column
            label="Statut"
            width="120"
          >
            <template #default="{ row }">
              <el-tag
                :type="getContainerStatusType(row.state, row.healthStatus)"
                size="small"
                effect="dark"
              >
                {{ getContainerStatusLabel(row.state, row.healthStatus) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Ports"
            min-width="180"
          >
            <template #default="{ row }">
              <span
                v-if="row.ports && row.ports.length > 0"
                class="text-xs"
              >
                {{ formatContainerPorts(row.ports) }}
              </span>
              <span
                v-else
                class="text-muted"
              >-</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-else-if="!servicesLoading"
          description="Aucun service trouvé"
          :image-size="60"
        />
      </div>
    </el-card>

    <!-- Card Volumes (vert) -->
    <el-card class="overview-card card-volumes" shadow="hover">
      <template #header>
        <div class="card-header header-green">
          <el-icon><FolderOpened /></el-icon>
          <span>Volumes</span>
          <el-tag
            v-if="parsedMounts.length > 0"
            size="small"
            type="info"
            class="ml-2"
          >
            {{ parsedMounts.length }}
          </el-tag>
        </div>
      </template>
      <el-table
        v-if="parsedMounts.length > 0"
        :data="parsedMounts"
        stripe
        size="small"
        max-height="300"
      >
        <el-table-column
          label="Type"
          width="100"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.type === 'volume' ? 'success' : 'warning'"
              size="small"
            >
              {{ row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="Source / Nom"
          min-width="180"
        >
          <template #default="{ row }">
            <code class="text-xs">{{ row.name || row.source }}</code>
          </template>
        </el-table-column>
        <el-table-column
          label="Destination"
          min-width="180"
        >
          <template #default="{ row }">
            <code class="text-xs">{{ row.destination }}</code>
          </template>
        </el-table-column>
        <el-table-column
          label="Mode"
          width="80"
        >
          <template #default="{ row }">
            {{ row.mode }}
          </template>
        </el-table-column>
        <el-table-column
          label=""
          width="50"
          align="center"
        >
          <template #default>
            <el-button
              link
              size="small"
              disabled
              title="Volume browser — bientôt disponible"
            >
              📂
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else
        description="Aucun volume monté"
        :image-size="60"
      />
    </el-card>

    <!-- Card Réseau (violet) -->
    <el-card class="overview-card card-network" shadow="hover">
      <template #header>
        <div class="card-header header-purple">
          <el-icon><Connection /></el-icon>
          <span>Réseau</span>
          <el-tag
            v-if="parsedNetworks.length > 0"
            size="small"
            type="info"
            class="ml-2"
          >
            {{ parsedNetworks.length }}
          </el-tag>
        </div>
      </template>
      <el-table
        v-if="parsedNetworks.length > 0"
        :data="parsedNetworks"
        stripe
        size="small"
        max-height="300"
      >
        <el-table-column
          label="Réseau"
          min-width="140"
        >
          <template #default="{ row }">
            {{ row.networkName }}
          </template>
        </el-table-column>
        <el-table-column
          label="Adresse IP"
          width="150"
        >
          <template #default="{ row }">
            <code>{{ row.ipAddress }}</code>
          </template>
        </el-table-column>
        <el-table-column
          label="Passerelle"
          width="150"
        >
          <template #default="{ row }">
            <code>{{ row.gateway }}</code>
          </template>
        </el-table-column>
        <el-table-column
          label="MAC"
          width="170"
        >
          <template #default="{ row }">
            <code class="text-xs">{{ row.macAddress }}</code>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else
        description="Aucune information réseau"
        :image-size="60"
      />
    </el-card>

    <!-- Card Santé (orange) — visible uniquement si health check défini -->
    <el-card
      v-if="healthInfo"
      class="overview-card card-health"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-orange">
          <el-icon><FirstAidKit /></el-icon>
          <span>Santé</span>
        </div>
      </template>
      <!-- Container arrêté → message indisponibilité -->
      <div v-if="containerState !== 'running'">
        <el-alert
          type="info"
          :closable="false"
          show-icon
        >
          <template #title>
            Non disponible — container arrêté
          </template>
        </el-alert>
      </div>
      <!-- Container running → afficher les infos de santé -->
      <div v-else>
        <el-descriptions
          :column="2"
          border
          size="small"
        >
          <el-descriptions-item label="Statut">
            <template #default>
              <el-tag
                :type="healthTagType"
                size="small"
                effect="dark"
              >
                {{ healthInfo.status ?? '-' }}
              </el-tag>
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="healthInfo.failing_streak != null"
            label="Échecs consécutifs"
          >
            <template #default>
              <span :class="{ 'text-red-500': (healthInfo.failing_streak ?? 0) > 0 }">
                {{ healthInfo.failing_streak }}
              </span>
            </template>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <!-- Card Ressources (rouge) -->
    <el-card class="overview-card card-resources" shadow="hover">
      <template #header>
        <div class="card-header header-red">
          <el-icon><Cpu /></el-icon>
          <span>Ressources</span>
          <el-tag
            v-if="isStreaming"
            size="small"
            type="success"
            class="ml-2"
          >
            Live
          </el-tag>
        </div>
      </template>
      <!-- Container arrêté -->
      <div v-if="containerState !== 'running'">
        <el-alert
          type="info"
          :closable="false"
          show-icon
        >
          <template #title>
            Non disponible — container arrêté
          </template>
        </el-alert>
      </div>
      <!-- Container running → métriques -->
      <div v-else>
        <!-- CPU -->
        <div class="stat-section">
          <div class="stat-header">
            <el-icon><Cpu /></el-icon>
            <span>CPU</span>
          </div>
          <ResourceBar
            :value="stats?.cpu_percent ?? 0"
            label="Utilisation"
            :show-value="true"
          />
        </div>
        <!-- RAM -->
        <div class="stat-section">
          <div class="stat-header">
            <el-icon><Odometer /></el-icon>
            <span>Mémoire</span>
          </div>
          <ResourceBar
            :value="stats?.memory_percent ?? 0"
            label="Utilisation"
            :show-value="true"
          />
          <div class="memory-details">
            {{ formatBytes(stats?.memory_used) }} / {{ formatBytes(stats?.memory_limit) }}
          </div>
        </div>
        <!-- Network I/O -->
        <div class="stat-section">
          <div class="stat-header">
            <el-icon><Connection /></el-icon>
            <span>Réseau</span>
          </div>
          <div class="io-grid">
            <div class="io-item">
              <span class="io-label">↓ Reçu</span>
              <span class="io-value">{{ formatBytes(stats?.network_rx_bytes) }}</span>
            </div>
            <div class="io-item">
              <span class="io-label">↑ Envoyé</span>
              <span class="io-value">{{ formatBytes(stats?.network_tx_bytes) }}</span>
            </div>
          </div>
        </div>
        <!-- Disk I/O -->
        <div class="stat-section">
          <div class="stat-header">
            <el-icon><Coin /></el-icon>
            <span>Disque</span>
          </div>
          <div class="io-grid">
            <div class="io-item">
              <span class="io-label">Lecture</span>
              <span class="io-value">{{ formatBytes(stats?.block_read_bytes) }}</span>
            </div>
            <div class="io-item">
              <span class="io-label">Écriture</span>
              <span class="io-value">{{ formatBytes(stats?.block_write_bytes) }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Monitor,
  FolderOpened,
  Connection,
  FirstAidKit,
  Cpu,
  Odometer,
  Coin,
} from '@element-plus/icons-vue'
import { containersApi } from '@/services/api'
import { getContainerStatusType, getContainerStatusLabel } from '@/components/compute/helpers'
import { useContainerStats } from '@/composables/useContainerStats'
import { formatBytes } from '@/utils/format'
import ResourceBar from '@/components/ui/ResourceBar.vue'
import type {
  ContainerDetail,
  Container,
  ContainerPort,
} from '@/types/api'

const props = defineProps<{
  detail: ContainerDetail | null
  containerId: string
  containerState: string
}>()

// ─── Services Card ──────────────────────────────────────────────────────────

const servicesLoading = ref(false)
const allContainers = ref<Container[]>([])

const projectName = computed<string | null>(() => {
  return props.detail?.config?.labels?.['com.docker.compose.project'] ?? null
})

const stackServices = computed<Container[]>(() => {
  if (!props.detail) return []
  const project = projectName.value
  if (!project) {
    // Standalone : afficher uniquement le container courant
    return allContainers.value.filter(c => c.id === props.containerId)
  }
  // Filtrer par label compose project
  return allContainers.value.filter(
    c => c.labels?.['com.docker.compose.project'] === project,
  )
})

async function fetchStackServices(): Promise<void> {
  servicesLoading.value = true
  try {
    const response = await containersApi.list(true)
    allContainers.value = (response.data as Container[]) ?? []
  } catch {
    allContainers.value = []
  } finally {
    servicesLoading.value = false
  }
}

function formatContainerPorts(ports: ContainerPort[]): string {
  if (!ports || ports.length === 0) return '-'
  return ports
    .filter(p => p.PublicPort != null)
    .map(p => `${p.IP ?? '0.0.0.0'}:${p.PublicPort}→${p.PrivatePort}/${p.Type ?? 'tcp'}`)
    .join(', ')
}

// ─── Volumes Card ───────────────────────────────────────────────────────────

interface ParsedMount {
  type: string
  source: string
  destination: string
  mode: string
  name?: string
}

const parsedMounts = computed<ParsedMount[]>(() => {
  const mounts = props.detail?.mounts
  if (!mounts || !Array.isArray(mounts)) return []
  return mounts.map((mount: Record<string, unknown>) => ({
    type: String(mount['Type'] || mount['type'] || 'unknown'),
    source: String(mount['Source'] || mount['source'] || '-'),
    destination: String(mount['Destination'] || mount['destination'] || '-'),
    mode: String(mount['Mode'] || mount['mode'] || 'rw'),
    name: mount['Name'] !== undefined
      ? String(mount['Name'])
      : mount['name'] !== undefined
        ? String(mount['name'])
        : undefined,
  }))
})

// ─── Network Card ───────────────────────────────────────────────────────────

interface ParsedNetwork {
  networkName: string
  ipAddress: string
  gateway: string
  macAddress: string
}

const parsedNetworks = computed<ParsedNetwork[]>(() => {
  const networks = props.detail?.network_settings?.networks
  if (!networks) return []
  return Object.entries(networks).map(([networkName, endpoint]) => ({
    networkName,
    ipAddress: endpoint.ip_address ?? '-',
    gateway: endpoint.gateway ?? '-',
    macAddress: endpoint.mac_address ?? '-',
  }))
})

// ─── Health Card ────────────────────────────────────────────────────────────

const healthInfo = computed(() => props.detail?.state?.health ?? null)

const healthTagType = computed(() => {
  const status = healthInfo.value?.status
  if (status === 'healthy') return 'success'
  if (status === 'unhealthy') return 'danger'
  if (status === 'starting') return 'warning'
  return 'info'
})

// ─── Resources Card ─────────────────────────────────────────────────────────

const { stats, connect, disconnect, isStreaming } = useContainerStats({
  containerId: props.containerId,
  autoConnect: false,
})

// ─── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(() => {
  fetchStackServices()
})

watch(() => props.containerState, (newState) => {
  if (newState === 'running') {
    connect()
  } else {
    disconnect()
  }
}, { immediate: true })
</script>

<style scoped>
.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  padding: 4px 0;
}

@media (width <= 768px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}

.overview-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.header-blue {
  color: var(--el-color-primary);
}

.header-green {
  color: var(--el-color-success);
}

.header-purple {
  color: #9b59b6;
}

.header-orange {
  color: var(--el-color-warning);
}

.card-services :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-primary);
}

.card-volumes :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-success);
}

.card-network :deep(.el-card__header) {
  border-bottom: 3px solid #9b59b6;
}

.card-health :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-warning);
}

.header-red {
  color: var(--el-color-danger);
}

.card-resources :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-danger);
}

.stat-section {
  margin-bottom: 12px;
}

.stat-section:last-child {
  margin-bottom: 0;
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 6px;
}

.memory-details {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
  text-align: right;
}

.io-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.io-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  padding: 4px 8px;
  background: var(--color-bg-secondary);
  border-radius: 4px;
}

.io-label {
  color: var(--color-text-secondary);
}

.io-value {
  font-family: monospace;
  font-weight: 500;
}

.text-muted {
  color: var(--color-text-placeholder);
}

.text-red-500 {
  color: var(--el-color-danger);
  font-weight: 600;
}

.text-xs {
  font-size: 12px;
}

code {
  font-family: monospace;
  font-size: 12px;
}
</style>
