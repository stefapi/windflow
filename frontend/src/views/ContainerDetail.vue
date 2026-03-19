<template>
  <div class="container-detail-page">
    <!-- Header with container info and actions -->
    <el-card class="page-header">
      <template #header>
        <div class="header-content">
          <div class="header-left">
            <el-button
              link
              @click="goBack"
            >
              <el-icon class="el-icon--left">
                <ArrowLeft />
              </el-icon>
              Retour
            </el-button>
            <div class="container-title">
              <h2>{{ containerDetail?.name || 'Container' }}</h2>
              <el-tag
                :type="containerState === 'running' ? 'success' : 'danger'"
                size="large"
              >
                {{ containerState }}
              </el-tag>
            </div>
          </div>
          <div class="header-actions">
            <el-button
              v-if="containerState === 'running'"
              type="warning"
              @click="handleAction('stop')"
            >
              <el-icon class="el-icon--left">
                <VideoPause />
              </el-icon>
              Arrêter
            </el-button>
            <el-button
              v-if="containerState === 'running'"
              type="primary"
              @click="handleAction('restart')"
            >
              <el-icon class="el-icon--left">
                <RefreshRight />
              </el-icon>
              Redémarrer
            </el-button>
            <el-button
              type="default"
              @click="showInspectDrawer"
            >
              <el-icon class="el-icon--left">
                <ZoomIn />
              </el-icon>
              Inspect
            </el-button>
          </div>
        </div>
      </template>

      <!-- Loading state -->
      <div
        v-if="containersStore.detailLoading"
        v-loading="containersStore.detailLoading"
        class="loading-container"
      >
        <el-icon class="is-loading">
          <Loading />
        </el-icon>
        Chargement des détails...
      </div>

      <!-- Error state -->
      <el-alert
        v-if="containersStore.error"
        :title="containersStore.error"
        type="error"
        show-icon
        closable
        @close="containersStore.error = null"
      />

      <!-- Tabs -->
      <el-tabs v-model="activeTab">
        <el-tab-pane label="Infos" name="infos">
          <div class="info-sections">
            <!-- General Info -->
            <div class="info-section">
              <h3>Informations générales</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="ID">
                  <template #default>
                    <div class="id-with-copy">
                      <code>{{ truncateId(containerDetail?.id) }}</code>
                      <el-button
                        link
                        size="small"
                        @click="copyId"
                      >
                        <el-icon><CopyDocument /></el-icon>
                      </el-button>
                    </div>
                  </template>
                </el-descriptions-item>
                <el-descriptions-item label="Image">
                  <template #default>
                    <code>{{ containerDetail?.image || '-' }}</code>
                  </template>
                </el-descriptions-item>
                <el-descriptions-item label="Créé le">
                  <template #default>
                    {{ formatDate(containerDetail?.created) }}
                  </template>
                </el-descriptions-item>
                <el-descriptions-item label="Commande">
                  <template #default>
                    <code class="command-text">{{ containerDetail?.path }} {{ containerDetail?.args?.join(' ') }}</code>
                  </template>
                </el-descriptions-item>
                <el-descriptions-item label="Stack parente">
                  <template #default>
                    <el-tag v-if="parentStack" size="small">
                      {{ parentStack }}
                    </el-tag>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- Ports Section -->
            <div class="info-section">
              <h3>Ports</h3>
              <el-table
                :data="parsedPorts"
                empty-text="Aucun port exposé"
                stripe
                size="small"
              >
                <el-table-column prop="hostIp" label="Host IP" width="140" />
                <el-table-column prop="hostPort" label="Host Port" width="120" />
                <el-table-column prop="containerPort" label="Container Port" width="140" />
                <el-table-column prop="protocol" label="Protocole" width="100" />
              </el-table>
            </div>

            <!-- Volumes Section -->
            <div class="info-section">
              <h3>Volumes</h3>
              <el-table
                :data="parsedMounts"
                empty-text="Aucun volume monté"
                stripe
                size="small"
              >
                <el-table-column prop="type" label="Type" width="100">
                  <template #default="{ row }">
                    <el-tag size="small">{{ row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="source" label="Source" min-width="200" />
                <el-table-column prop="destination" label="Destination" min-width="200" />
                <el-table-column label="Actions" width="120">
                  <template #default>
                    <el-button
                      link
                      size="small"
                      disabled
                      title="Parcourir (bientôt disponible)"
                    >
                      <el-icon><FolderOpened /></el-icon>
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- Network Section -->
            <div class="info-section">
              <h3>Réseau</h3>
              <el-table
                :data="parsedNetworks"
                empty-text="Aucune information réseau"
                stripe
                size="small"
              >
                <el-table-column prop="networkName" label="Réseau" width="150" />
                <el-table-column prop="ipAddress" label="Adresse IP" width="150" />
                <el-table-column prop="macAddress" label="Adresse MAC" width="180" />
                <el-table-column prop="gateway" label="Passerelle" width="150" />
              </el-table>
            </div>

            <!-- Environment Variables Section -->
            <div class="info-section">
              <div class="section-header">
                <h3>Variables d'environnement</h3>
                <el-input
                  v-model="envSearch"
                  placeholder="Rechercher..."
                  size="small"
                  clearable
                  class="env-search"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
              </div>
              <el-table
                :data="filteredEnvVars"
                empty-text="Aucune variable d'environnement"
                stripe
                size="small"
                max-height="400"
              >
                <el-table-column prop="key" label="Variable" min-width="200">
                  <template #default="{ row }">
                    <code>{{ row.key }}</code>
                    <el-tag v-if="row.isSecret" type="warning" size="small" class="secret-tag">
                      Secret
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Valeur" min-width="300">
                  <template #default="{ row }">
                    <div class="value-cell">
                      <code v-if="!row.isSecret || isRevealed(row.key)">{{ row.value }}</code>
                      <code v-else class="masked-value">{{ maskValue(row.value) }}</code>
                      <el-button
                        v-if="row.isSecret"
                        link
                        size="small"
                        @click="toggleSecret(row.key)"
                      >
                        <el-icon>
                          <View v-if="!isRevealed(row.key)" />
                          <Hide v-else />
                        </el-icon>
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <!-- Logs Tab -->
        <el-tab-pane label="Logs" name="logs">
          <ContainerLogs
            v-if="containerId"
            :container-id="containerId"
            :container-name="containerDetail?.name"
          />
        </el-tab-pane>

        <!-- Terminal Tab -->
        <el-tab-pane
          label="Terminal"
          name="terminal"
          :disabled="containerState !== 'running'"
        >
          <ContainerTerminal
            v-if="containerState === 'running' && containerId"
            :container-id="containerId"
            :container-name="containerDetail?.name"
          />
          <div v-else class="placeholder-content">
            <el-empty description="Le terminal n'est disponible que lorsque le container est en cours d'exécution (running)" />
          </div>
        </el-tab-pane>

        <!-- Placeholder tabs for future features -->
        <el-tab-pane label="Stats" name="stats" disabled>
          <div class="placeholder-content">
            <el-empty description="Statistiques disponibles prochainement" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Inspect Drawer -->
    <el-drawer
      v-model="inspectDrawerVisible"
      :title="`Inspect - ${containerDetail?.name || ''}`"
      direction="rtl"
      size="50%"
    >
      <div class="inspect-container">
        <el-input
          v-model="inspectContent"
          type="textarea"
          :rows="30"
          readonly
          class="inspect-textarea"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  CopyDocument,
  VideoPause,
  RefreshRight,
  Search,
  View,
  Hide,
  Loading,
  FolderOpened,
  ZoomIn,
} from '@element-plus/icons-vue'
import { useContainersStore } from '@/stores'
import { isSecretKey, maskValue, useSecretMasker } from '@/composables/useSecretMasker'
import ContainerLogs from '@/components/ContainerLogs.vue'
import ContainerTerminal from '@/components/ContainerTerminal.vue'
import type { ContainerDetail, ContainerEnvVar, ContainerPortMapping, ContainerMount, ContainerNetworkInfo } from '@/types/api'

const route = useRoute()
const router = useRouter()
const containersStore = useContainersStore()

// State
const containerDetail = ref<ContainerDetail | null>(null)
const activeTab = ref('infos')
const envSearch = ref('')
const inspectDrawerVisible = ref(false)
const inspectContent = ref('')

// Secret masker - only use functions, revealedKeys is internal
const { toggleSecret, isRevealed } = useSecretMasker()

// Computed
const containerId = computed(() => route.params['id'] as string | undefined)

const containerState = computed(() => {
  const state = containerDetail.value?.state
  if (typeof state === 'object' && state !== null) {
    const stateRecord = state as Record<string, unknown>
    const status = stateRecord['Status']
    return typeof status === 'string' ? status : 'unknown'
  }
  return 'unknown'
})

const parentStack = computed(() => {
  const labels = containerDetail.value?.config
  if (labels && typeof labels === 'object') {
    const config = labels as Record<string, unknown>
    const project = config['com.docker.compose.project']
    return typeof project === 'string' ? project : null
  }
  return null
})

// Parse ports from container details
const parsedPorts = computed<ContainerPortMapping[]>(() => {
  const hostConfig = containerDetail.value?.host_config
  if (!hostConfig || typeof hostConfig !== 'object') return []

  const config = hostConfig as Record<string, unknown>
  const portBindings = config['PortBindings'] as Record<string, Array<{ HostIp: string; HostPort: string }>> | undefined
  if (!portBindings) return []

  const ports: ContainerPortMapping[] = []
  for (const [containerPort, bindings] of Object.entries(portBindings)) {
    if (bindings && bindings.length > 0) {
      for (const binding of bindings) {
        const match = containerPort.match(/^(\d+)\/(tcp|udp)$/i)
        ports.push({
          hostIp: binding.HostIp || '0.0.0.0',
          hostPort: binding.HostPort,
          containerPort: match?.[1] ?? containerPort,
          protocol: match?.[2]?.toUpperCase() ?? 'TCP',
        })
      }
    }
  }
  return ports
})

// Parse mounts from container details
const parsedMounts = computed<ContainerMount[]>(() => {
  const mounts = containerDetail.value?.mounts
  if (!mounts || !Array.isArray(mounts)) return []

  return mounts.map((mount: Record<string, unknown>) => ({
    type: String(mount['Type'] || mount['type'] || 'unknown'),
    source: String(mount['Source'] || mount['source'] || '-'),
    destination: String(mount['Destination'] || mount['destination'] || '-'),
    mode: String(mount['Mode'] || mount['mode'] || 'rw'),
    name: mount['Name'] !== undefined ? String(mount['Name']) : mount['name'] !== undefined ? String(mount['name']) : undefined,
  }))
})

// Parse networks from container details
const parsedNetworks = computed<ContainerNetworkInfo[]>(() => {
  const networkSettings = containerDetail.value?.network_settings
  if (!networkSettings || typeof networkSettings !== 'object') return []

  const settings = networkSettings as Record<string, unknown>
  const networks = settings['Networks'] as Record<string, Record<string, unknown>> | undefined
  if (!networks) return []

  const result: ContainerNetworkInfo[] = []
  for (const [networkName, networkConfig] of Object.entries(networks)) {
    result.push({
      networkId: String(networkConfig['NetworkID'] || '-'),
      networkName,
      ipAddress: String(networkConfig['IPAddress'] || '-'),
      macAddress: String(networkConfig['MacAddress'] || '-'),
      gateway: String(networkConfig['Gateway'] || '-'),
    })
  }
  return result
})

// Parse environment variables
const parsedEnvVars = computed<ContainerEnvVar[]>(() => {
  const config = containerDetail.value?.config
  if (!config || typeof config !== 'object') return []

  const cfg = config as Record<string, unknown>
  const envArray = cfg['Env'] as string[] | undefined
  if (!envArray || !Array.isArray(envArray)) return []

  return envArray.map(env => {
    const equalIndex = env.indexOf('=')
    if (equalIndex === -1) {
      return { key: env, value: '', isSecret: false }
    }
    const key = env.substring(0, equalIndex)
    const value = env.substring(equalIndex + 1)
    return {
      key,
      value,
      isSecret: isSecretKey(key),
    }
  })
})

// Filtered environment variables
const filteredEnvVars = computed(() => {
  if (!envSearch.value.trim()) {
    return parsedEnvVars.value
  }
  const search = envSearch.value.toLowerCase()
  return parsedEnvVars.value.filter(
    env => env.key.toLowerCase().includes(search)
  )
})

// Methods
function truncateId(id: string | undefined): string {
  if (!id) return '-'
  return id.length > 12 ? id.substring(0, 12) : id
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

async function copyId(): Promise<void> {
  const id = containerDetail.value?.['id']
  if (!id || typeof id !== 'string') return
  try {
    await window.navigator.clipboard.writeText(id)
    ElMessage.success('ID copié dans le presse-papier')
  } catch {
    ElMessage.error('Erreur lors de la copie')
  }
}

async function loadContainerDetail(): Promise<void> {
  const id = containerId.value
  if (!id) return

  try {
    await containersStore.inspectContainer(id)
    containerDetail.value = containersStore.containerDetail
  } catch (error) {
    ElMessage.error('Erreur lors du chargement des détails du container')
    console.error(error)
  }
}

async function handleAction(action: string): Promise<void> {
  const id = containerId.value
  if (!id) return

  try {
    switch (action) {
      case 'stop':
        await containersStore.stopContainer(id)
        ElMessage.success('Container arrêté')
        await loadContainerDetail()
        break
      case 'restart':
        await containersStore.restartContainer(id)
        ElMessage.success('Container redémarré')
        await loadContainerDetail()
        break
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de l\'action'
    ElMessage.error(message)
  }
}

function goBack(): void {
  router.push({ name: 'Containers' })
}

function showInspectDrawer(): void {
  if (containerDetail.value) {
    inspectContent.value = JSON.stringify(containerDetail.value, null, 2)
  } else {
    inspectContent.value = ''
  }
  inspectDrawerVisible.value = true
}

// Lifecycle
onMounted(() => {
  loadContainerDetail()
})
</script>

<style scoped>
.container-detail-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.container-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.container-title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  gap: 12px;
  color: var(--el-text-color-secondary);
}

.is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.info-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-section {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
}

.info-section h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.id-with-copy {
  display: flex;
  align-items: center;
  gap: 8px;
}

.id-with-copy code {
  font-family: monospace;
  font-size: 13px;
}

.command-text {
  font-family: monospace;
  font-size: 13px;
  background-color: var(--el-fill-color-light);
  padding: 4px 8px;
  border-radius: 4px;
}

.text-muted {
  color: var(--el-text-color-placeholder);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.env-search {
  width: 200px;
}

.value-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.value-cell code {
  font-family: monospace;
  font-size: 12px;
  word-break: break-all;
}

.masked-value {
  color: var(--el-text-color-placeholder);
}

.secret-tag {
  margin-left: 8px;
}

/* Placeholder content */
.placeholder-content {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

/* Inspect Drawer */
.inspect-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.inspect-textarea :deep(textarea) {
  font-family: monospace;
  font-size: 11px;
  line-height: 1.4;
  background-color: #1e1e1e;
  color: #d4d4d4;
}

/* Responsive adjustments for mobile */
@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-left {
    flex-wrap: wrap;
  }

  .container-title {
    width: 100%;
    margin-top: 8px;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .header-actions .el-button {
    flex: 1;
    min-width: 100px;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .env-search {
    width: 100%;
  }
}
</style>
