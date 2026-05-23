<template>
  <div class="config-tab">
    <!-- Section 1 : Variables d'environnement (gris) -->
    <el-card
      class="config-card card-config-env"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-grey">
          <el-icon><Document /></el-icon>
          <span>Variables d'environnement</span>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ⚠️ Modifier les variables d'environnement nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir.
      </el-alert>

      <el-table
        :data="envVars"
        class="config-table"
      >
        <el-table-column
          label="Variable"
          min-width="200"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.key"
              placeholder="KEY"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Valeur"
          min-width="300"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.value"
              :type="isSecretKey(row.key) && !masker.isRevealed(row.key) ? 'password' : 'text'"
              placeholder="value"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="80"
          align="center"
        >
          <template #default="{ $index }">
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              circle
              @click="removeEnvVar($index)"
            />
          </template>
        </el-table-column>
      </el-table>

      <div class="section-actions">
        <el-button
          :icon="CirclePlus"
          size="small"
          @click="addEnvVar"
        >
          Ajouter une variable
        </el-button>
        <el-button
          type="primary"
          size="small"
          :loading="loadingRecreate"
          :disabled="loadingRecreate"
          @click="applyEnvVars"
        >
          Appliquer
        </el-button>
      </div>
    </el-card>

    <!-- Section 2 : Labels (gris) -->
    <el-card
      class="config-card card-config-labels"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-grey">
          <el-icon><PriceTag /></el-icon>
          <span>Labels</span>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ⚠️ Modifier les labels nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir.
      </el-alert>

      <el-table
        :data="labels"
        class="config-table"
      >
        <el-table-column
          label="Clé"
          min-width="200"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.key"
              placeholder="com.example.label"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Valeur"
          min-width="300"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.value"
              placeholder="value"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="80"
          align="center"
        >
          <template #default="{ $index }">
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              circle
              @click="removeLabel($index)"
            />
          </template>
        </el-table-column>
      </el-table>

      <div class="section-actions">
        <el-button
          :icon="CirclePlus"
          size="small"
          @click="addLabel"
        >
          Ajouter un label
        </el-button>
        <el-button
          type="primary"
          size="small"
          :loading="loadingRecreate"
          :disabled="loadingRecreate"
          @click="applyLabels"
        >
          Appliquer
        </el-button>
      </div>
    </el-card>

    <!-- Section 3 : Image (violet) -->
    <el-card
      class="config-card card-config-image"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-purple">
          <el-icon><Picture /></el-icon>
          <span>Image</span>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ⚠️ Modifier l'image nécessite de recréer le container. Le layer writable sera perdu.
      </el-alert>

      <el-form label-position="top">
        <el-form-item label="Image Docker">
          <el-input
            v-model="newImage"
            placeholder="ex: nginx:latest"
            size="small"
            clearable
          />
          <div
            v-if="detail?.image"
            class="current-hint"
          >
            Image actuelle : {{ detail.image }}
          </div>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="pullImage">
            Puller la nouvelle image avant recréation
          </el-checkbox>
        </el-form-item>
      </el-form>

      <div class="section-actions">
        <el-button
          type="primary"
          size="small"
          :loading="loadingRecreate"
          :disabled="loadingRecreate"
          @click="updateImage"
        >
          Mettre à jour l'image
        </el-button>
      </div>
    </el-card>

    <!-- Section 4 : Ports (violet) -->
    <el-card
      class="config-card card-config-ports"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-purple">
          <el-icon><MapLocation /></el-icon>
          <span>Ports</span>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ⚠️ Modifier les ports nécessite de recréer le container.
      </el-alert>

      <el-table
        :data="portBindings"
        class="config-table"
      >
        <el-table-column
          label="Host IP"
          min-width="140"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.hostIp"
              placeholder="0.0.0.0"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Host Port"
          min-width="120"
        >
          <template #default="{ row }">
            <el-input-number
              v-model="row.hostPort"
              :min="1"
              :max="65535"
              size="small"
              controls-position="right"
              style="width: 100px"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Container Port"
          min-width="120"
        >
          <template #default="{ row }">
            <el-input-number
              v-model="row.containerPort"
              :min="1"
              :max="65535"
              size="small"
              controls-position="right"
              style="width: 100px"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Protocole"
          min-width="100"
        >
          <template #default="{ row }">
            <el-select
              v-model="row.protocol"
              size="small"
              style="width: 80px"
            >
              <el-option
                label="TCP"
                value="tcp"
              />
              <el-option
                label="UDP"
                value="udp"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column
          label="Action"
          width="80"
          align="center"
        >
          <template #default="{ $index }">
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              circle
              @click="removePortBinding($index)"
            />
          </template>
        </el-table-column>
      </el-table>

      <div class="section-actions">
        <el-button
          :icon="CirclePlus"
          size="small"
          @click="addPortBinding"
        >
          Ajouter un port
        </el-button>
        <el-button
          type="primary"
          size="small"
          :loading="loadingRecreate"
          :disabled="loadingRecreate"
          @click="applyPortBindings"
        >
          Appliquer
        </el-button>
      </div>
    </el-card>

    <!-- Section 5 : Restart Policy (orange) -->
    <el-card
      class="config-card card-config-restart"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-orange">
          <el-icon><RefreshRight /></el-icon>
          <span>Restart Policy</span>
        </div>
      </template>

      <el-descriptions
        :column="1"
        border
        size="small"
      >
        <el-descriptions-item label="Politique">
          <el-select
            v-model="restartPolicyName"
            size="small"
          >
            <el-option
              label="no"
              value="no"
            />
            <el-option
              label="always"
              value="always"
            />
            <el-option
              label="on-failure"
              value="on-failure"
            />
            <el-option
              label="unless-stopped"
              value="unless-stopped"
            />
          </el-select>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="restartPolicyName === 'on-failure'"
          label="Max retry count"
        >
          <el-input-number
            v-model="maxRetryCount"
            :min="0"
            size="small"
          />
        </el-descriptions-item>
      </el-descriptions>

      <div class="section-actions">
        <el-button
          type="primary"
          size="small"
          :loading="loadingRestart"
          :disabled="loadingRestart"
          @click="applyRestartPolicy"
        >
          Appliquer
        </el-button>
      </div>
    </el-card>

    <!-- Section 6 : Resource Limits (rouge) -->
    <el-card
      class="config-card card-config-resources"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-red">
          <el-icon><Cpu /></el-icon>
          <span>Resource Limits</span>
        </div>
      </template>

      <el-descriptions
        :column="1"
        border
        size="small"
      >
        <el-descriptions-item label="Memory limit">
          <div class="resource-input-row">
            <el-input-number
              v-model="memoryValue"
              :min="0"
              size="small"
              controls-position="right"
            />
            <el-select
              v-model="memoryUnit"
              size="small"
              style="width: 90px"
            >
              <el-option
                label="MB"
                value="MB"
              />
              <el-option
                label="GB"
                value="GB"
              />
            </el-select>
            <span
              v-if="detail?.host_config?.resources?.memory"
              class="current-hint"
            >
              (actuel : {{ formatBytes(detail.host_config.resources.memory) }})
            </span>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="CPU shares">
          <div class="resource-input-row">
            <el-input-number
              v-model="cpuShares"
              :min="0"
              size="small"
              controls-position="right"
            />
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="PIDs limit">
          <div class="resource-input-row">
            <el-input-number
              v-model="pidsLimit"
              :min="-1"
              size="small"
              controls-position="right"
            />
            <span class="current-hint">(-1 = illimité)</span>
          </div>
        </el-descriptions-item>
      </el-descriptions>

      <div class="section-actions">
        <el-button
          type="primary"
          size="small"
          :loading="loadingResources"
          :disabled="loadingResources"
          @click="applyResources"
        >
          Appliquer
        </el-button>
      </div>
    </el-card>

    <!-- Section 7 : Volumes (vert) -->
    <el-card
      class="config-card card-config-volumes"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-green">
          <el-icon><Coin /></el-icon>
          <span>Volumes</span>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ⚠️ Modifier les volumes nécessite de recréer le container.
      </el-alert>

      <el-table
        :data="volumeEntries"
        class="config-table"
      >
        <el-table-column
          label="Type"
          width="120"
        >
          <template #default="{ row }">
            <el-select
              v-model="row.type"
              size="small"
            >
              <el-option
                label="bind"
                value="bind"
              />
              <el-option
                label="volume"
                value="volume"
              />
              <el-option
                label="tmpfs"
                value="tmpfs"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column
          label="Source"
          min-width="200"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.source"
              placeholder="Chemin hôte ou nom du volume"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Destination"
          min-width="200"
        >
          <template #default="{ row }">
            <el-input
              v-model="row.destination"
              placeholder="Point de montage dans le container"
              size="small"
            />
          </template>
        </el-table-column>
        <el-table-column
          label="Mode"
          width="100"
        >
          <template #default="{ row }">
            <el-select
              v-model="row.mode"
              size="small"
            >
              <el-option
                label="rw"
                value="rw"
              />
              <el-option
                label="ro"
                value="ro"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column
          label="Action"
          width="80"
          align="center"
        >
          <template #default="{ $index }">
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              circle
              @click="removeVolumeEntry($index)"
            />
          </template>
        </el-table-column>
      </el-table>

      <div class="section-actions">
        <el-button
          :icon="CirclePlus"
          size="small"
          @click="addVolumeEntry"
        >
          Ajouter un volume
        </el-button>
        <el-button
          type="primary"
          size="small"
          :loading="loadingRecreate"
          :disabled="loadingRecreate"
          @click="applyVolumesAndSecurity"
        >
          Appliquer
        </el-button>
      </div>
    </el-card>

    <!-- Section 8 : Sécurité (rouge) -->
    <el-card
      class="config-card card-config-security"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-red">
          <el-icon><Lock /></el-icon>
          <span>Sécurité</span>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ⚠️ Ces modifications nécessitent de recréer le container.
      </el-alert>

      <el-descriptions
        :column="1"
        border
        size="small"
      >
        <el-descriptions-item label="Mode privilégié">
          <el-switch v-model="privileged" />
        </el-descriptions-item>
        <el-descriptions-item label="Read-only rootfs">
          <el-switch v-model="readonlyRootfs" />
        </el-descriptions-item>
      </el-descriptions>

      <div class="cap-section">
        <div class="cap-label">
          Capabilities ajoutées (cap_add) :
        </div>
        <div class="cap-tags">
          <el-tag
            v-for="(cap, index) in capAdd"
            :key="'add-' + index"
            closable
            size="small"
            @close="removeCapAdd(index)"
          >
            {{ cap }}
          </el-tag>
        </div>
        <div class="cap-input-row">
          <el-input
            v-model="newCapAdd"
            placeholder="ex: NET_ADMIN"
            size="small"
            style="width: 180px"
            @keyup.enter="addCapAdd"
          />
          <el-button
            size="small"
            :disabled="!newCapAdd.trim()"
            @click="addCapAdd"
          >
            Ajouter
          </el-button>
        </div>
      </div>

      <div class="cap-section">
        <div class="cap-label">
          Capabilities retirées (cap_drop) :
        </div>
        <div class="cap-tags">
          <el-tag
            v-for="(cap, index) in capDrop"
            :key="'drop-' + index"
            closable
            type="danger"
            size="small"
            @close="removeCapDrop(index)"
          >
            {{ cap }}
          </el-tag>
        </div>
        <div class="cap-input-row">
          <el-input
            v-model="newCapDrop"
            placeholder="ex: SETUID"
            size="small"
            style="width: 180px"
            @keyup.enter="addCapDrop"
          />
          <el-button
            size="small"
            :disabled="!newCapDrop.trim()"
            @click="addCapDrop"
          >
            Ajouter
          </el-button>
        </div>
      </div>

      <div class="section-actions">
        <el-button
          type="primary"
          size="small"
          :loading="loadingRecreate"
          :disabled="loadingRecreate"
          @click="applyVolumesAndSecurity"
        >
          Appliquer les modifications (recréation)
        </el-button>
      </div>
    </el-card>

    <!-- Section 9 : Réseaux (vert) -->
    <el-card
      class="config-card card-config-networks"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-green">
          <el-icon><Connection /></el-icon>
          <span>Réseaux</span>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="section-alert"
      >
        ℹ️ Les connexions/déconnexions se font sans redémarrage
      </el-alert>

      <el-table
        :data="connectedNetworks"
        class="config-table"
        empty-text="Aucun réseau connecté"
      >
        <el-table-column
          label="Réseau"
          min-width="200"
        >
          <template #default="{ row }">
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="IP Address"
          min-width="150"
        >
          <template #default="{ row }">
            <span>{{ row.ip_address }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="120"
          align="center"
        >
          <template #default="{ row }">
            <el-button
              type="danger"
              size="small"
              :loading="loadingDisconnect[row.name]"
              :disabled="loadingDisconnect[row.name]"
              @click="disconnectNetwork(row.name)"
            >
              Déconnecter
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="section-actions">
        <el-select
          v-model="selectedNetwork"
          placeholder="Sélectionner un réseau..."
          size="small"
          style="width: 240px"
          :loading="loadingNetworks"
        >
          <el-option
            v-for="net in filteredAvailableNetworks"
            :key="net.id"
            :label="net.name"
            :value="net.id"
          />
        </el-select>
        <el-button
          type="primary"
          size="small"
          :loading="loadingConnect"
          :disabled="loadingConnect || !selectedNetwork"
          @click="connectNetwork"
        >
          Connecter
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CirclePlus,
  Delete,
  Document,
  PriceTag,
  RefreshRight,
  Cpu,
  Picture,
  MapLocation,
  Connection,
  Lock,
  Coin,
} from '@element-plus/icons-vue'
import { containersApi, networksApi } from '@/services/api'
import { formatBytes } from '@/utils/format'
import { isSecretKey, useSecretMasker } from '@/composables/useSecretMasker'
import type {
  ContainerDetail,
  ContainerUpdateRestartPolicyRequest,
  ContainerUpdateResourcesRequest,
  NetworkResponse,
  ContainerNetworkConnectRequest,
  ContainerNetworkDisconnectRequest,
} from '@/types/api'

const props = defineProps<{
  detail: ContainerDetail | null
}>()

const emit = defineEmits<{
  (e: 'recreate-success', newId: string): void
  (e: 'network-changed'): void
}>()

const masker = useSecretMasker()

// ─── Env Vars ───
interface KeyValue {
  key: string
  value: string
}

const envVars = ref<KeyValue[]>([])
const labels = ref<KeyValue[]>([])

// ─── Image ───
const newImage = ref('')
const pullImage = ref(false)
const loadingRecreate = ref(false)

// ─── Ports ───
interface PortBindingRow {
  hostIp: string
  hostPort: number | ''
  containerPort: string
  protocol: 'tcp' | 'udp'
}

const portBindings = ref<PortBindingRow[]>([])

// ─── Restart Policy ───
const restartPolicyName = ref<string>('no')
const maxRetryCount = ref<number>(0)
const loadingRestart = ref(false)

// ─── Resources ───
const memoryValue = ref<number>(0)
const memoryUnit = ref<'MB' | 'GB'>('MB')
const cpuShares = ref<number>(0)
const pidsLimit = ref<number>(-1)
const loadingResources = ref(false)

// ─── Volumes ───
interface VolumeEntry {
  type: 'bind' | 'volume' | 'tmpfs'
  source: string
  destination: string
  mode: 'ro' | 'rw'
}

const volumeEntries = ref<VolumeEntry[]>([])

// ─── Security ───
const privileged = ref(false)
const readonlyRootfs = ref(false)
const capAdd = ref<string[]>([])
const capDrop = ref<string[]>([])
const newCapAdd = ref('')
const newCapDrop = ref('')

// ─── Networks ───
const availableNetworks = ref<NetworkResponse[]>([])
const selectedNetwork = ref('')
const loadingNetworks = ref(false)
const loadingConnect = ref(false)
const loadingDisconnect = ref<Record<string, boolean>>({})

const connectedNetworks = computed(() => {
  const networks = props.detail?.network_settings?.networks
  if (!networks) return []
  return Object.entries(networks).map(([name, info]) => ({
    name,
    ip_address: info.ip_address ?? '-',
    network_id: info.network_id ?? name,
  }))
})

const filteredAvailableNetworks = computed(() => {
  const connectedNames = new Set(connectedNetworks.value.map((n) => n.name))
  return availableNetworks.value.filter((n) => !connectedNames.has(n.name))
})

async function loadAvailableNetworks(): Promise<void> {
  loadingNetworks.value = true
  try {
    const response = await networksApi.list()
    availableNetworks.value = response.data
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors du chargement des réseaux'
    ElMessage.error(message)
  } finally {
    loadingNetworks.value = false
  }
}

async function connectNetwork(): Promise<void> {
  if (!props.detail?.id || !selectedNetwork.value) return

  const data: ContainerNetworkConnectRequest = {
    network_id: selectedNetwork.value,
  }

  loadingConnect.value = true
  try {
    await containersApi.connectNetwork(props.detail.id, data)
    ElMessage.success('Réseau connecté avec succès')
    selectedNetwork.value = ''
    emit('network-changed')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la connexion au réseau'
    ElMessage.error(message)
  } finally {
    loadingConnect.value = false
  }
}

async function disconnectNetwork(networkName: string): Promise<void> {
  if (!props.detail?.id) return

  const data: ContainerNetworkDisconnectRequest = {
    network_id: networkName,
  }

  loadingDisconnect.value = { ...loadingDisconnect.value, [networkName]: true }
  try {
    await containersApi.disconnectNetwork(props.detail.id, data)
    ElMessage.success('Réseau déconnecté avec succès')
    emit('network-changed')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la déconnexion du réseau'
    ElMessage.error(message)
  } finally {
    loadingDisconnect.value = { ...loadingDisconnect.value, [networkName]: false }
  }
}

onMounted(() => {
  loadAvailableNetworks()
})

// ─── Watch detail changes to populate fields ───
watch(
  () => props.detail,
  (detail) => {
    if (!detail) return

    // Env vars
    if (detail.config?.env) {
      envVars.value = detail.config.env.map((entry) => {
        const equalIndex = entry.indexOf('=')
        if (equalIndex === -1) {
          return { key: entry, value: '' }
        }
        return {
          key: entry.substring(0, equalIndex),
          value: entry.substring(equalIndex + 1),
        }
      })
    } else {
      envVars.value = []
    }

    // Labels
    if (detail.config?.labels) {
      labels.value = Object.entries(detail.config.labels).map(([key, value]) => ({ key, value }))
    } else {
      labels.value = []
    }

    // Image
    newImage.value = detail.image ?? ''

    // Ports
    const pb = detail.host_config?.port_bindings
    if (pb) {
      portBindings.value = parsePortBindings(pb)
    } else {
      portBindings.value = []
    }

    // Restart policy
    const rp = detail.host_config?.restart_policy
    if (rp) {
      restartPolicyName.value = rp.name ?? 'no'
      maxRetryCount.value = rp.maximum_retry_count ?? 0
    }

    // Resources
    const res = detail.host_config?.resources
    if (res) {
      if (res.memory && res.memory > 0) {
        // Convert bytes to MB or GB
        const mb = res.memory / (1024 * 1024)
        if (mb >= 1024 && mb % 1024 === 0) {
          memoryValue.value = mb / 1024
          memoryUnit.value = 'GB'
        } else {
          memoryValue.value = Math.round(mb)
          memoryUnit.value = 'MB'
        }
      } else {
        memoryValue.value = 0
        memoryUnit.value = 'MB'
      }
      cpuShares.value = res.cpu_shares ?? 0
      pidsLimit.value = res.pids_limit ?? -1
    }

    // Volumes
    if (detail.mounts && Array.isArray(detail.mounts) && detail.mounts.length > 0) {
      volumeEntries.value = detail.mounts.map((m: Record<string, unknown>) => ({
        type: (String(m['Type'] || 'bind')) as VolumeEntry['type'],
        source: String(m['Source'] || ''),
        destination: String(m['Destination'] || ''),
        mode: String(m['RW']) === 'false' ? 'ro' as const : 'rw' as const,
      }))
    } else if (detail.host_config?.binds) {
      volumeEntries.value = detail.host_config.binds.map((bind: string) => {
        const parts = bind.split(':')
        return {
          type: 'bind' as const,
          source: parts[0] || '',
          destination: parts[1] || '',
          mode: (parts[2] || 'rw') as 'ro' | 'rw',
        }
      })
    } else {
      volumeEntries.value = []
    }

    // Security
    privileged.value = detail.host_config?.privileged ?? false
    readonlyRootfs.value = detail.host_config?.readonly_rootfs ?? false
    capAdd.value = detail.host_config?.cap_add ? [...detail.host_config.cap_add] : []
    capDrop.value = detail.host_config?.cap_drop ? [...detail.host_config.cap_drop] : []
  },
  { immediate: true },
)

// ─── Port bindings parsing ───
function parsePortBindings(
  pb: Record<string, Array<{ HostIp: string; HostPort: string }>>,
): PortBindingRow[] {
  const rows: PortBindingRow[] = []
  for (const [key, bindings] of Object.entries(pb)) {
    const [containerPort, protocol] = key.split('/') as [string, 'tcp' | 'udp']
    for (const binding of bindings) {
      const hostPortNum = binding.HostPort ? parseInt(binding.HostPort, 10) : ''
      rows.push({
        hostIp: binding.HostIp || '0.0.0.0',
        hostPort: isNaN(hostPortNum as number) ? '' : hostPortNum,
        containerPort: containerPort || '',
        protocol: protocol || 'tcp',
      })
    }
  }
  return rows
}

function buildPortBindingsPayload(): Record<string, Array<{ HostIp: string; HostPort: string }>> {
  const payload: Record<string, Array<{ HostIp: string; HostPort: string }>> = {}
  for (const row of portBindings.value) {
    if (!row.containerPort || !row.protocol) continue
    const key = `${row.containerPort}/${row.protocol}`
    if (!payload[key]) {
      payload[key] = []
    }
    payload[key].push({
      HostIp: row.hostIp || '0.0.0.0',
      HostPort: String(row.hostPort || ''),
    })
  }
  return payload
}

function validatePortBindings(): string | null {
  const seen = new Set<string>()
  for (const row of portBindings.value) {
    if (row.hostPort !== '') {
      const hp = Number(row.hostPort)
      if (isNaN(hp) || hp < 1 || hp > 65535) {
        return `Host port invalide : ${row.hostPort} (doit être entre 1 et 65535)`
      }
    }
    if (row.containerPort !== '') {
      const cp = Number(row.containerPort)
      if (isNaN(cp) || cp < 1 || cp > 65535) {
        return `Container port invalide : ${row.containerPort} (doit être entre 1 et 65535)`
      }
    }
    if (row.hostPort !== '' && row.hostIp) {
      const combo = `${row.hostIp}:${row.hostPort}`
      if (seen.has(combo)) {
        return `Doublon détecté : ${combo}`
      }
      seen.add(combo)
    }
  }
  return null
}

function validateEnvVars(): string | null {
  const seen = new Set<string>()
  for (const row of envVars.value) {
    if (!row.key.trim()) {
      return 'Une variable d\'environnement a une clé vide'
    }
    const normalizedKey = row.key.trim()
    if (seen.has(normalizedKey)) {
      return `Doublon détecté pour la variable d'environnement : ${normalizedKey}`
    }
    seen.add(normalizedKey)
  }
  return null
}

function validateLabels(): string | null {
  const seen = new Set<string>()
  for (const row of labels.value) {
    if (!row.key.trim()) {
      return 'Un label a une clé vide'
    }
    const normalizedKey = row.key.trim()
    if (seen.has(normalizedKey)) {
      return `Doublon détecté pour le label : ${normalizedKey}`
    }
    seen.add(normalizedKey)
  }
  return null
}

// ─── Env Vars actions ───
function addEnvVar(): void {
  envVars.value.push({ key: '', value: '' })
}

function removeEnvVar(index: number): void {
  envVars.value.splice(index, 1)
}

async function applyEnvVars(): Promise<void> {
  if (!props.detail?.id) return

  const validationError = validateEnvVars()
  if (validationError) {
    ElMessage.error(validationError)
    return
  }

  try {
    await ElMessageBox.confirm(
      'Modifier les variables d\'environnement nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir. Continuer ?',
      'Confirmation requise',
      {
        confirmButtonText: 'Confirmer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
  } catch {
    // cancelled
    return
  }

  loadingRecreate.value = true
  try {
    const response = await containersApi.recreate(props.detail.id, {
      env: envVars.value.map(e => `${e.key}=${e.value}`),
    })
    ElMessage.success('Container recréé avec succès')
    emit('recreate-success', response.data.new_container_id)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la recréation'
    ElMessage.error(message)
  } finally {
    loadingRecreate.value = false
  }
}

// ─── Labels actions ───
function addLabel(): void {
  labels.value.push({ key: '', value: '' })
}

function removeLabel(index: number): void {
  labels.value.splice(index, 1)
}

async function applyLabels(): Promise<void> {
  if (!props.detail?.id) return

  const validationError = validateLabels()
  if (validationError) {
    ElMessage.error(validationError)
    return
  }

  try {
    await ElMessageBox.confirm(
      'Modifier les labels nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir. Continuer ?',
      'Confirmation requise',
      {
        confirmButtonText: 'Confirmer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
  } catch {
    // cancelled
    return
  }

  loadingRecreate.value = true
  try {
    const response = await containersApi.recreate(props.detail.id, {
      labels: Object.fromEntries(labels.value.map(l => [l.key, l.value])),
    })
    ElMessage.success('Container recréé avec succès')
    emit('recreate-success', response.data.new_container_id)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la recréation'
    ElMessage.error(message)
  } finally {
    loadingRecreate.value = false
  }
}

// ─── Image actions ───
async function updateImage(): Promise<void> {
  if (!props.detail?.id) return
  const image = newImage.value.trim()
  if (!image) {
    ElMessage.error('L\'image ne peut pas être vide')
    return
  }

  try {
    await ElMessageBox.confirm(
      'Modifier l\'image nécessite de recréer le container. Le layer writable sera perdu. Continuer ?',
      'Confirmation requise',
      {
        confirmButtonText: 'Confirmer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
  } catch {
    // cancelled
    return
  }

  loadingRecreate.value = true
  try {
    const response = await containersApi.recreate(props.detail.id, {
      image,
      pull_image: pullImage.value,
    })
    ElMessage.success('Container recréé avec succès')
    emit('recreate-success', response.data.new_container_id)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la recréation'
    ElMessage.error(message)
  } finally {
    loadingRecreate.value = false
  }
}

// ─── Ports actions ───
function addPortBinding(): void {
  portBindings.value.push({
    hostIp: '0.0.0.0',
    hostPort: '',
    containerPort: '',
    protocol: 'tcp',
  })
}

function removePortBinding(index: number): void {
  portBindings.value.splice(index, 1)
}

async function applyPortBindings(): Promise<void> {
  if (!props.detail?.id) return

  const error = validatePortBindings()
  if (error) {
    ElMessage.error(error)
    return
  }

  try {
    await ElMessageBox.confirm(
      'Modifier les ports nécessite de recréer le container. Le layer writable sera perdu. Continuer ?',
      'Confirmation requise',
      {
        confirmButtonText: 'Confirmer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
  } catch {
    // cancelled
    return
  }

  loadingRecreate.value = true
  try {
    const payload = buildPortBindingsPayload()
    const response = await containersApi.recreate(props.detail.id, {
      port_bindings: payload,
    })
    ElMessage.success('Container recréé avec succès')
    emit('recreate-success', response.data.new_container_id)
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Erreur lors de la recréation'
    ElMessage.error(message)
  } finally {
    loadingRecreate.value = false
  }
}

// ─── Restart Policy actions ───
async function applyRestartPolicy(): Promise<void> {
  if (!props.detail?.id) return

  const data: ContainerUpdateRestartPolicyRequest = {
    name: restartPolicyName.value,
  }
  if (restartPolicyName.value === 'on-failure') {
    data.maximum_retry_count = maxRetryCount.value
  }

  loadingRestart.value = true
  try {
    await containersApi.updateRestartPolicy(props.detail.id, data)
    ElMessage.success('Restart policy mise à jour')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la mise à jour'
    ElMessage.error(message)
  } finally {
    loadingRestart.value = false
  }
}

// ─── Resources actions ───
async function applyResources(): Promise<void> {
  if (!props.detail?.id) return

  // Convert memory to bytes
  let memoryBytes: number | undefined
  if (memoryValue.value > 0) {
    memoryBytes =
      memoryUnit.value === 'GB'
        ? memoryValue.value * 1024 * 1024 * 1024
        : memoryValue.value * 1024 * 1024
  }

  const data: ContainerUpdateResourcesRequest = {
    memory_limit: memoryBytes,
    cpu_shares: cpuShares.value || undefined,
    pids_limit: pidsLimit.value,
  }

  loadingResources.value = true
  try {
    await containersApi.updateResources(props.detail.id, data)
    ElMessage.success('Resource limits mises à jour')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la mise à jour'
    ElMessage.error(message)
  } finally {
    loadingResources.value = false
  }
}
// ─── Volume actions ───
function addVolumeEntry(): void {
  volumeEntries.value.push({ type: 'bind', source: '', destination: '', mode: 'rw' })
}

function removeVolumeEntry(index: number): void {
  volumeEntries.value.splice(index, 1)
}

function buildMountsPayload(): Array<Record<string, unknown>> {
  return volumeEntries.value.map((entry) => ({
    Type: entry.type,
    Source: entry.source,
    Target: entry.destination,
    ReadOnly: entry.mode === 'ro',
  }))
}

function validateVolumes(): string | null {
  const destinations = new Set<string>()
  for (const entry of volumeEntries.value) {
    if (!entry.destination.trim()) {
      return 'La destination du volume ne peut pas être vide'
    }
    if (destinations.has(entry.destination)) {
      return `Doublon de destination détecté : ${entry.destination}`
    }
    destinations.add(entry.destination)
  }
  return null
}

// ─── Capabilities actions ───
function addCapAdd(): void {
  const cap = newCapAdd.value.trim().toUpperCase()
  if (cap && !capAdd.value.includes(cap)) {
    capAdd.value.push(cap)
  }
  newCapAdd.value = ''
}

function removeCapAdd(index: number): void {
  capAdd.value.splice(index, 1)
}

function addCapDrop(): void {
  const cap = newCapDrop.value.trim().toUpperCase()
  if (cap && !capDrop.value.includes(cap)) {
    capDrop.value.push(cap)
  }
  newCapDrop.value = ''
}

function removeCapDrop(index: number): void {
  capDrop.value.splice(index, 1)
}

// ─── Volumes & Security recreate ───
async function applyVolumesAndSecurity(): Promise<void> {
  if (!props.detail?.id) return

  const volError = validateVolumes()
  if (volError) {
    ElMessage.error(volError)
    return
  }

  try {
    await ElMessageBox.confirm(
      'Modifier les volumes et/ou la sécurité nécessite de recréer le container. Le layer writable sera perdu. Continuer ?',
      'Confirmation requise',
      {
        confirmButtonText: 'Confirmer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
  } catch {
    // cancelled
    return
  }

  loadingRecreate.value = true
  try {
    const payload: Record<string, unknown> = {}
    payload['mounts'] = buildMountsPayload()
    payload['privileged'] = privileged.value
    payload['readonly_rootfs'] = readonlyRootfs.value
    payload['cap_add'] = capAdd.value.length > 0 ? [...capAdd.value] : undefined
    payload['cap_drop'] = capDrop.value.length > 0 ? [...capDrop.value] : undefined

    const response = await containersApi.recreate(props.detail.id, payload)
    ElMessage.success('Container recréé avec succès')
    emit('recreate-success', response.data.new_container_id)
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Erreur lors de la recréation'
    ElMessage.error(message)
  } finally {
    loadingRecreate.value = false
  }
}
</script>

<style scoped>
.config-tab {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0;
}

/* ─── Card header pattern (same as ContainerOverviewTab) ─── */
.config-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

/* ─── Header color classes ─── */
.header-grey {
  color: var(--el-color-info);
}

.header-purple {
  color: #9b59b6;
}

.header-orange {
  color: var(--el-color-warning);
}

.header-red {
  color: var(--el-color-danger);
}

.header-green {
  color: var(--el-color-success);
}

/* ─── Card border-bottom colors ─── */
.card-config-env :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-info);
}

.card-config-labels :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-info);
}

.card-config-image :deep(.el-card__header) {
  border-bottom: 3px solid #9b59b6;
}

.card-config-ports :deep(.el-card__header) {
  border-bottom: 3px solid #9b59b6;
}

.card-config-restart :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-warning);
}

.card-config-resources :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-danger);
}

.card-config-networks :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-success);
}

.card-config-volumes :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-success);
}

.card-config-security :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-danger);
}

/* ─── Section content styles ─── */
.section-alert {
  margin-bottom: 12px;
}

.config-table {
  margin-bottom: 12px;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.resource-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-hint {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}

/* ─── Capabilities styles ─── */
.cap-section {
  margin-top: 16px;
}

.cap-label {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.cap-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.cap-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
