<template>
  <div class="config-tab">
    <!-- Section 1 : Variables d'environnement -->
    <div class="config-section">
      <div class="section-header">
        <h3>Variables d'environnement</h3>
      </div>

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
    </div>

    <!-- Section 2 : Labels -->
    <div class="config-section">
      <div class="section-header">
        <h3>Labels</h3>
      </div>

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
    </div>

    <!-- Section 3 : Restart Policy -->
    <div class="config-section">
      <div class="section-header">
        <h3>Restart Policy</h3>
      </div>

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
    </div>

    <!-- Section 4 : Resource Limits -->
    <div class="config-section">
      <div class="section-header">
        <h3>Resource Limits</h3>
      </div>

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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CirclePlus, Delete } from '@element-plus/icons-vue'
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

const masker = useSecretMasker()

// ─── Env Vars ───
interface KeyValue {
  key: string
  value: string
}

const envVars = ref<KeyValue[]>([])
const labels = ref<KeyValue[]>([])

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
  gap: 24px;
  padding: 8px 0;
}

.config-section {
  background-color: var(--color-bg-secondary, #f5f7fa);
  border-radius: 8px;
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

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
