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
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
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
} from '@element-plus/icons-vue'
import { containersApi } from '@/services/api'
import { formatBytes } from '@/utils/format'
import { isSecretKey, useSecretMasker } from '@/composables/useSecretMasker'
import type {
  ContainerDetail,
  ContainerUpdateRestartPolicyRequest,
  ContainerUpdateResourcesRequest,
} from '@/types/api'

const props = defineProps<{
  detail: ContainerDetail | null
}>()

const emit = defineEmits<{
  (e: 'recreate-success', newId: string): void
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

// ─── Env Vars actions ───
function addEnvVar(): void {
  envVars.value.push({ key: '', value: '' })
}

function removeEnvVar(index: number): void {
  envVars.value.splice(index, 1)
}

async function applyEnvVars(): Promise<void> {
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
    ElMessage.info('Fonctionnalité de recréation à venir')
  } catch {
    // cancelled — do nothing
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
    ElMessage.info('Fonctionnalité de recréation à venir')
  } catch {
    // cancelled — do nothing
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
</style>
