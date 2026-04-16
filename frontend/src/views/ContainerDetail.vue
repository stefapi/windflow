<template>
  <div class="container-detail-page">
    <!-- Header with container info and actions -->
    <el-card class="page-header">
      <template #header>
        <div class="header-content">
          <!-- Ligne 1 : Retour + Identité -->
          <div class="header-top">
            <el-button
              link
              @click="goBack"
            >
              <el-icon class="el-icon--left">
                <ArrowLeft />
              </el-icon>
              Retour
            </el-button>
          </div>

          <div class="header-identity">
            <h2 class="container-name">
              {{ containerDetail?.name || 'Container' }}
            </h2>
            <el-button
              v-if="containerDetail"
              link
              type="primary"
              :icon="Edit"
              @click="openRenameDialog"
            >
              Renommer
            </el-button>
            <code
              v-if="containerDetail?.image"
              class="container-image"
            >{{ containerDetail.image }}</code>
            <el-tag
              :type="statusTagType"
              size="large"
              effect="dark"
            >
              {{ statusLabel }}
            </el-tag>
            <span
              v-if="containerUptime"
              class="container-uptime"
            >{{ containerUptime }}</span>
          </div>

          <!-- Ligne 2 : Métadonnées inline -->
          <div class="header-meta">
            <span
              v-if="targetName"
              class="meta-item"
            >
              <el-icon><Monitor /></el-icon>
              Target : {{ targetName }}
            </span>
            <span
              v-if="headerStats.cpuPercent !== null"
              class="meta-item"
            >
              <el-icon><Cpu /></el-icon>
              CPU : {{ headerStats.cpuPercent.toFixed(1) }}%
            </span>
            <span
              v-if="headerStats.memoryUsage"
              class="meta-item"
            >
              <el-icon><Memo /></el-icon>
              RAM : {{ headerStats.memoryUsage }}
            </span>
            <span class="meta-item">
              <el-icon><RefreshRight /></el-icon>
              Restart :
              <el-tag
                size="small"
                type="info"
              >
                {{ restartPolicyLabel }}
              </el-tag>
              <el-button
                link
                type="primary"
                size="small"
                @click="openRestartPolicyDialog"
              >
                Modifier
              </el-button>
            </span>
            <span class="meta-item">
              <el-icon><Setting /></el-icon>
              Ressources : {{ resourcesSummary }}
              <el-button
                link
                type="primary"
                size="small"
                @click="openResourcesDialog"
              >
                Modifier
              </el-button>
            </span>
          </div>

          <!-- Ligne 3 : Barre d'actions -->
          <div class="header-actions">
            <el-tooltip
              v-if="!['exited', 'dead', 'created'].includes(containerState)"
              content="Container déjà en cours d'exécution"
              placement="top"
            >
              <el-button
                type="success"
                disabled
              >
                <el-icon class="el-icon--left">
                  <VideoPlay />
                </el-icon>
                Démarrer
              </el-button>
            </el-tooltip>
            <el-button
              v-else
              type="success"
              @click="handleAction('start')"
            >
              <el-icon class="el-icon--left">
                <VideoPlay />
              </el-icon>
              Démarrer
            </el-button>

            <el-tooltip
              v-if="containerState !== 'running'"
              content="Le container doit être en cours d'exécution"
              placement="top"
            >
              <el-button
                type="warning"
                disabled
              >
                <el-icon class="el-icon--left">
                  <VideoPause />
                </el-icon>
                Pause
              </el-button>
            </el-tooltip>
            <el-button
              v-else
              type="warning"
              @click="handleAction('pause')"
            >
              <el-icon class="el-icon--left">
                <VideoPause />
              </el-icon>
              Pause
            </el-button>

            <el-button
              v-if="containerState === 'paused'"
              type="success"
              @click="handleAction('unpause')"
            >
              <el-icon class="el-icon--left">
                <VideoPlay />
              </el-icon>
              Reprendre
            </el-button>

            <el-tooltip
              v-if="!['running', 'paused'].includes(containerState)"
              content="Le container est déjà arrêté"
              placement="top"
            >
              <el-button
                type="danger"
                disabled
              >
                <el-icon class="el-icon--left">
                  <SwitchButton />
                </el-icon>
                Arrêter
              </el-button>
            </el-tooltip>
            <el-button
              v-else
              type="danger"
              @click="handleAction('stop')"
            >
              <el-icon class="el-icon--left">
                <SwitchButton />
              </el-icon>
              Arrêter
            </el-button>

            <el-tooltip
              v-if="containerState !== 'running'"
              content="Le container doit être en cours d'exécution"
              placement="top"
            >
              <el-button
                type="primary"
                disabled
              >
                <el-icon class="el-icon--left">
                  <RefreshRight />
                </el-icon>
                Redémarrer
              </el-button>
            </el-tooltip>
            <el-button
              v-else
              type="primary"
              @click="handleAction('restart')"
            >
              <el-icon class="el-icon--left">
                <RefreshRight />
              </el-icon>
              Redémarrer
            </el-button>

            <el-button
              type="danger"
              plain
              @click="handleDelete"
            >
              <el-icon class="el-icon--left">
                <Delete />
              </el-icon>
              Supprimer
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

            <el-divider direction="vertical" />

            <el-button
              v-if="isStandalone"
              type="primary"
              plain
              @click="openPromoteDialog"
            >
              <el-icon class="el-icon--left">
                <Upload />
              </el-icon>
              Promouvoir en stack
            </el-button>

            <el-divider
              v-if="isStandalone"
              direction="vertical"
            />

            <el-button
              type="default"
              @click="openRestartPolicyDialog"
            >
              <el-icon class="el-icon--left">
                <RefreshRight />
              </el-icon>
              Restart Policy
            </el-button>
            <el-button
              type="default"
              @click="openResourcesDialog"
            >
              <el-icon class="el-icon--left">
                <Cpu />
              </el-icon>
              Ressources
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
        <el-tab-pane
          label="Aperçu"
          name="apercu"
        >
          <ContainerOverviewTab
            v-if="containerId"
            :detail="containerDetail"
            :container-id="containerId!"
            :container-state="containerState"
          />
        </el-tab-pane>

        <el-tab-pane
          label="Infos"
          name="infos"
        >
          <ContainerInfoTab :detail="containerDetail" />
        </el-tab-pane>

        <!-- Logs Tab -->
        <el-tab-pane
          label="Logs"
          name="logs"
        >
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
          <div
            v-else
            class="placeholder-content"
          >
            <el-empty description="Le terminal n'est disponible que lorsque le container est en cours d'exécution (running)" />
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="Stats"
          name="stats"
          :disabled="containerState !== 'running'"
        >
          <ContainerStats
            v-if="containerState === 'running' && containerId"
            :container-id="containerId"
            :container-name="containerDetail?.name"
          />
          <div
            v-else
            class="placeholder-content"
          >
            <el-empty description="L'onglet Stats n'est disponible que lorsque le container est en cours d'exécution (running)" />
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="Config"
          name="config"
        >
          <ContainerConfigTab :detail="containerDetail" />
        </el-tab-pane>

        <el-tab-pane
          label="Processus"
          name="processes"
          :disabled="containerState !== 'running'"
        >
          <ContainerProcesses
            v-if="containerState === 'running' && containerId"
            :container-id="containerId"
            :container-name="containerDetail?.name"
          />
          <div
            v-else
            class="placeholder-content"
          >
            <el-empty description="L'onglet Processus n'est disponible que lorsque le container est en cours d'exécution (running)" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Rename Dialog -->
    <el-dialog
      v-model="renameDialogVisible"
      title="Renommer le container"
      width="450px"
      :close-on-click-modal="false"
      @closed="onRenameDialogClosed"
    >
      <el-form @submit.prevent="handleRename">
        <el-form-item
          :error="renameError"
        >
          <el-input
            ref="renameInputRef"
            v-model="renameNewName"
            placeholder="Nouveau nom du container"
            clearable
            :disabled="renameLoading"
            @keyup.enter="handleRename"
          />
        </el-form-item>
        <div class="rename-hint">
          Le nom doit commencer par une lettre ou un chiffre et ne contenir que des lettres, chiffres, <code>_</code>, <code>.</code>, <code>-</code>.
        </div>
      </el-form>
      <template #footer>
        <el-button @click="renameDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="renameLoading"
          :disabled="!isRenameValid"
          @click="handleRename"
        >
          Confirmer
        </el-button>
      </template>
    </el-dialog>

    <!-- Restart Policy Dialog -->
    <el-dialog
      v-model="restartPolicyDialogVisible"
      title="Modifier la restart policy"
      width="450px"
      :close-on-click-modal="false"
    >
      <el-form
        label-position="top"
        @submit.prevent="handleUpdateRestartPolicy"
      >
        <el-form-item label="Politique de redémarrage">
          <el-select
            v-model="restartPolicyForm.name"
            style="width: 100%"
          >
            <el-option
              label="no — Ne jamais redémarrer"
              value="no"
            />
            <el-option
              label="always — Toujours redémarrer"
              value="always"
            />
            <el-option
              label="on-failure — Redémarrer en cas d'erreur"
              value="on-failure"
            />
            <el-option
              label="unless-stopped — Redémarrer sauf arrêt manuel"
              value="unless-stopped"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="restartPolicyForm.name === 'on-failure'"
          label="Maximum retry count"
        >
          <el-input-number
            v-model="restartPolicyForm.maximumRetryCount"
            :min="0"
            :step="1"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="restartPolicyDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="restartPolicyLoading"
          @click="handleUpdateRestartPolicy"
        >
          Confirmer
        </el-button>
      </template>
    </el-dialog>

    <!-- Resources Dialog -->
    <el-dialog
      v-model="resourcesDialogVisible"
      title="Modifier les ressources"
      width="450px"
      :close-on-click-modal="false"
    >
      <el-form
        label-position="top"
        @submit.prevent="handleUpdateResources"
      >
        <el-form-item label="Limite mémoire (MB)">
          <el-input-number
            v-model="resourcesForm.memoryLimit"
            :min="0"
            :step="64"
            style="width: 100%"
          />
        </el-form-item>
        <div class="form-hint">
          Laisser à 0 pour illimité
        </div>
        <el-form-item label="CPU shares">
          <el-input-number
            v-model="resourcesForm.cpuShares"
            :min="0"
            :max="1024"
            style="width: 100%"
          />
        </el-form-item>
        <div class="form-hint">
          Laisser à 0 pour illimité
        </div>
        <el-form-item label="Limite PIDs">
          <el-input-number
            v-model="resourcesForm.pidsLimit"
            :min="0"
            style="width: 100%"
          />
        </el-form-item>
        <div class="form-hint">
          Laisser à 0 pour illimité
        </div>
      </el-form>
      <template #footer>
        <el-button @click="resourcesDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="resourcesLoading"
          @click="handleUpdateResources"
        >
          Confirmer
        </el-button>
      </template>
    </el-dialog>

    <!-- Promote Dialog -->
    <el-dialog
      v-model="promoteDialogVisible"
      title="Promouvoir en stack"
      width="450px"
      :close-on-click-modal="false"
      @closed="onPromoteDialogClosed"
    >
      <el-form @submit.prevent="handlePromote">
        <el-form-item
          :error="promoteError"
        >
          <el-input
            v-model="promoteStackName"
            placeholder="Nom de la stack"
            clearable
            :disabled="promoteLoading"
            @keyup.enter="handlePromote"
          />
        </el-form-item>
        <div class="rename-hint">
          Le nom doit commencer par une lettre ou un chiffre.
        </div>
      </el-form>
      <template #footer>
        <el-button @click="promoteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="promoteLoading"
          :disabled="!isPromoteValid"
          @click="handlePromote"
        >
          Confirmer
        </el-button>
      </template>
    </el-dialog>

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
          class="code-block inspect-textarea"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  VideoPause,
  VideoPlay,
  SwitchButton,
  Delete,
  RefreshRight,
  Loading,
  ZoomIn,
  Monitor,
  Cpu,
  Memo,
  Edit,
  Setting,
  Upload,
} from '@element-plus/icons-vue'
import { useContainersStore } from '@/stores'
import { containersApi } from '@/services/api'
import { getContainerStatusType, getContainerStatusLabel } from '@/components/compute/helpers'
import ContainerOverviewTab from '@/components/ContainerOverviewTab.vue'
import ContainerInfoTab from '@/components/ContainerInfoTab.vue'
import ContainerLogs from '@/components/ContainerLogs.vue'
import ContainerTerminal from '@/components/ContainerTerminal.vue'
import ContainerStats from '@/components/ContainerStats.vue'
import ContainerConfigTab from '@/components/ContainerConfigTab.vue'
import ContainerProcesses from '@/components/ContainerProcesses.vue'
import type { ContainerDetail, ContainerUpdateRestartPolicyRequest, ContainerUpdateResourcesRequest, ContainerPromoteRequest } from '@/types/api'

const route = useRoute()
const router = useRouter()
const containersStore = useContainersStore()

// State
const containerDetail = ref<ContainerDetail | null>(null)
const activeTab = ref('apercu')
const inspectDrawerVisible = ref(false)
const inspectContent = ref('')

// Rename state
const renameDialogVisible = ref(false)
const renameNewName = ref('')
const renameLoading = ref(false)
const renameError = ref('')
const renameInputRef = ref<InstanceType<typeof import('element-plus')['ElInput']> | null>(null)

// Restart Policy state
const restartPolicyDialogVisible = ref(false)
const restartPolicyLoading = ref(false)
const restartPolicyForm = reactive({
  name: 'no' as string,
  maximumRetryCount: 0 as number | null,
})

// Resources state
const resourcesDialogVisible = ref(false)
const resourcesLoading = ref(false)
const resourcesForm = reactive({
  memoryLimit: 0 as number | null,
  cpuShares: 0 as number | null,
  pidsLimit: 0 as number | null,
})

// Promote state
const promoteDialogVisible = ref(false)
const promoteStackName = ref('')
const promoteLoading = ref(false)
const promoteError = ref('')

/** Docker container name validation pattern */
const CONTAINER_NAME_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/

/** Stack name validation pattern */
const STACK_NAME_REGEX = /^[a-zA-Z0-9].{0,254}$/

/** Computed: is the rename form valid */
const isRenameValid = computed(() => {
  return renameNewName.value.trim().length > 0 && CONTAINER_NAME_REGEX.test(renameNewName.value.trim())
})

/** Computed: is the container standalone (not managed by WindFlow or Docker Compose) */
const isStandalone = computed(() => {
  const labels = containerDetail.value?.config?.labels
  if (!labels) return true
  return !labels['windflow.managed'] && !labels['com.docker.compose.project']
})

/** Computed: is the promote form valid */
const isPromoteValid = computed(() => {
  const name = promoteStackName.value.trim()
  return name.length > 0 && name.length <= 255 && STACK_NAME_REGEX.test(name)
})

/** Computed: restart policy display label */
const restartPolicyLabel = computed(() => {
  return containerDetail.value?.host_config?.restart_policy?.name ?? 'non défini'
})

/** Computed: resources summary for header-meta display */
const resourcesSummary = computed(() => {
  const resources = containerDetail.value?.host_config?.resources
  if (!resources) return 'non défini'
  const parts: string[] = []
  if (resources.memory && resources.memory > 0) {
    parts.push(`Mémoire ${Math.round(resources.memory / 1024 / 1024)} MB`)
  }
  if (resources.cpu_shares && resources.cpu_shares > 0) {
    parts.push(`CPU ${resources.cpu_shares}`)
  }
  if (resources.pids_limit && resources.pids_limit > 0) {
    parts.push(`PIDs ${resources.pids_limit}`)
  }
  return parts.length > 0 ? parts.join(' · ') : 'illimité'
})

// Computed
const containerId = computed(() => route.params['id'] as string | undefined)

const containerState = computed(() => {
  return containerDetail.value?.state?.status ?? 'unknown'
})

const containerHealth = computed<string | null>(() => {
  return containerDetail.value?.state?.health?.status ?? null
})

const statusTagType = computed(() => getContainerStatusType(containerState.value, containerHealth.value))
const statusLabel = computed(() => getContainerStatusLabel(containerState.value, containerHealth.value))

// Target name from query params
const targetName = computed(() => {
  return (route.query['targetName'] as string) || (route.query['target'] as string) || null
})

// Uptime computed from state.started_at / state.finished_at
const containerUptime = computed(() => {
  const state = containerDetail.value?.state
  if (!state) return null

  const isRunning = state.running === true || state.status === 'running'
  if (isRunning && state.started_at) {
    const duration = formatDuration(state.started_at)
    return duration ? `En cours (${duration})` : null
  }

  if (state.finished_at) {
    const since = formatDuration(state.finished_at)
    return since ? `Arrêté depuis ${since}` : null
  }

  return null
})

// Header stats snapshot (CPU/RAM)
const headerStats = reactive({
  cpuPercent: null as number | null,
  memoryUsage: null as string | null,
})

// Methods

/** Format a duration between a past ISO date string and now */
function formatDuration(isoDateStr: string | null): string | null {
  if (!isoDateStr) return null
  try {
    const date = new Date(isoDateStr)
    if (isNaN(date.getTime())) return null
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    if (diffMs < 0) return null

    const seconds = Math.floor(diffMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) return `${days}j ${hours % 24}h`
    if (hours > 0) return `${hours}h ${minutes % 60}min`
    if (minutes > 0) return `${minutes} min`
    return 'quelques secondes'
  } catch {
    return null
  }
}

/** Fetch a single stats snapshot for the header */
async function fetchHeaderStats(): Promise<void> {
  const id = containerId.value
  if (!id || containerState.value !== 'running') return
  try {
    const response = await containersApi.getStats(id)
    const data = response.data as Record<string, unknown>
    if (!data) return

    // Docker stats API returns cpu_percent and memory_usage or similar fields
    headerStats.cpuPercent = typeof data['cpu_percent'] === 'number' ? data['cpu_percent'] : null
    headerStats.memoryUsage = typeof data['memory_usage'] === 'string' ? data['memory_usage'] : null

    // Fallback: compute from raw cpu_stats if direct field not available
    if (headerStats.cpuPercent === null && data['cpu_stats'] && typeof data['cpu_stats'] === 'object') {
      const cpuStats = data['cpu_stats'] as Record<string, unknown>
      const cpuUsage = cpuStats['cpu_usage'] as Record<string, unknown> | undefined
      if (cpuUsage && typeof cpuUsage['percent'] === 'number') {
        headerStats.cpuPercent = cpuUsage['percent']
      }
    }

    // Fallback: compute memory from memory_stats if direct field not available
    if (headerStats.memoryUsage === null && data['memory_stats'] && typeof data['memory_stats'] === 'object') {
      const memStats = data['memory_stats'] as Record<string, unknown>
      const usage = memStats['usage']
      if (typeof usage === 'number' && usage > 0) {
        headerStats.memoryUsage = `${Math.round(usage / 1024 / 1024)} MB`
      }
    }
  } catch {
    // Stats are optional for the header — silently ignore errors
  }
}

/** Delete with ElMessageBox confirmation */
async function handleDelete(): Promise<void> {
  const id = containerId.value
  if (!id) return

  try {
    await ElMessageBox.confirm(
      `Voulez-vous vraiment supprimer le container "${containerDetail.value?.name || id}" ? Cette action est irréversible.`,
      'Confirmer la suppression',
      {
        confirmButtonText: 'Supprimer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
    await containersStore.removeContainer(id, true)
    ElMessage.success('Container supprimé')
    router.push('/compute')
  } catch (error) {
    if (error !== 'cancel' && error instanceof Error) {
      ElMessage.error(error.message || 'Erreur lors de la suppression')
    }
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
      case 'start':
        await containersStore.startContainer(id)
        ElMessage.success('Container démarré')
        await loadContainerDetail()
        break
      case 'pause':
        await containersStore.pauseContainer(id)
        ElMessage.success('Container mis en pause')
        await loadContainerDetail()
        break
      case 'unpause':
        await containersStore.unpauseContainer(id)
        ElMessage.success('Container repris')
        await loadContainerDetail()
        break
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
      case 'remove':
        await containersStore.removeContainer(id, true)
        ElMessage.success('Container supprimé')
        router.push('/compute')
        break
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de l\'action'
    ElMessage.error(message)
  }
}

function goBack(): void {
  router.back()
}

/** Open the rename dialog, pre-filled with the current name */
function openRenameDialog(): void {
  renameNewName.value = containerDetail.value?.name ?? ''
  renameError.value = ''
  renameDialogVisible.value = true
  // Focus input after dialog opens
  setTimeout(() => {
    renameInputRef.value?.focus()
  }, 100)
}

/** Handle rename confirmation */
async function handleRename(): Promise<void> {
  const id = containerId.value
  if (!id) return

  const newName = renameNewName.value.trim()

  // Validate
  if (!newName) {
    renameError.value = 'Le nom ne peut pas être vide'
    return
  }
  if (!CONTAINER_NAME_REGEX.test(newName)) {
    renameError.value = 'Nom invalide. Utilisez uniquement des lettres, chiffres, _ . - (sans commencer par _ . -)'
    return
  }
  if (newName === containerDetail.value?.name) {
    renameDialogVisible.value = false
    return
  }

  renameError.value = ''
  renameLoading.value = true

  try {
    await containersApi.rename(id, { new_name: newName })
    ElMessage.success(`Container renommé en "${newName}"`)
    renameDialogVisible.value = false
    await loadContainerDetail()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors du renommage'
    renameError.value = message
    ElMessage.error(message)
  } finally {
    renameLoading.value = false
  }
}

/** Reset rename state when dialog closes */
function onRenameDialogClosed(): void {
  renameNewName.value = ''
  renameError.value = ''
}

/** Open the promote dialog, pre-filled with the container name */
function openPromoteDialog(): void {
  promoteStackName.value = containerDetail.value?.name ?? ''
  promoteError.value = ''
  promoteDialogVisible.value = true
}

/** Handle promote confirmation */
async function handlePromote(): Promise<void> {
  const id = containerId.value
  if (!id) return

  const name = promoteStackName.value.trim()

  if (!name) {
    promoteError.value = 'Le nom ne peut pas être vide'
    return
  }
  if (!STACK_NAME_REGEX.test(name)) {
    promoteError.value = 'Nom invalide. Le nom doit commencer par une lettre ou un chiffre.'
    return
  }

  promoteError.value = ''
  promoteLoading.value = true

  try {
    const data: ContainerPromoteRequest = { name }
    await containersApi.promote(id, data)
    ElMessage.success(`Stack "${name}" créée avec succès`)
    promoteDialogVisible.value = false
    router.push('/stacks')
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la promotion'
    promoteError.value = message
    ElMessage.error(message)
  } finally {
    promoteLoading.value = false
  }
}

/** Reset promote state when dialog closes */
function onPromoteDialogClosed(): void {
  promoteStackName.value = ''
  promoteError.value = ''
}

/** Open the restart policy dialog, pre-filled with current values */
function openRestartPolicyDialog(): void {
  const policy = containerDetail.value?.host_config?.restart_policy
  restartPolicyForm.name = policy?.name ?? 'no'
  restartPolicyForm.maximumRetryCount = policy?.maximum_retry_count ?? 0
  restartPolicyDialogVisible.value = true
}

/** Handle restart policy update confirmation */
async function handleUpdateRestartPolicy(): Promise<void> {
  const id = containerId.value
  if (!id) return

  restartPolicyLoading.value = true
  try {
    const data: ContainerUpdateRestartPolicyRequest = {
      name: restartPolicyForm.name,
    }
    if (restartPolicyForm.name === 'on-failure' && restartPolicyForm.maximumRetryCount !== null) {
      data.maximum_retry_count = restartPolicyForm.maximumRetryCount
    }
    await containersApi.updateRestartPolicy(id, data)
    ElMessage.success('Restart policy mise à jour')
    restartPolicyDialogVisible.value = false
    await loadContainerDetail()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la mise à jour de la restart policy'
    ElMessage.error(message)
  } finally {
    restartPolicyLoading.value = false
  }
}

/** Open the resources dialog, pre-filled with current values */
function openResourcesDialog(): void {
  const resources = containerDetail.value?.host_config?.resources
  resourcesForm.memoryLimit = resources?.memory ? Math.round(resources.memory / 1024 / 1024) : 0
  resourcesForm.cpuShares = resources?.cpu_shares ?? 0
  resourcesForm.pidsLimit = resources?.pids_limit ?? 0
  resourcesDialogVisible.value = true
}

/** Handle resources update confirmation */
async function handleUpdateResources(): Promise<void> {
  const id = containerId.value
  if (!id) return

  resourcesLoading.value = true
  try {
    const data: ContainerUpdateResourcesRequest = {}
    data.memory_limit = resourcesForm.memoryLimit ? resourcesForm.memoryLimit * 1024 * 1024 : undefined
    data.cpu_shares = resourcesForm.cpuShares || undefined
    data.pids_limit = resourcesForm.pidsLimit || undefined
    await containersApi.updateResources(id, data)
    ElMessage.success('Ressources mises à jour')
    resourcesDialogVisible.value = false
    await loadContainerDetail()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la mise à jour des ressources'
    ElMessage.error(message)
  } finally {
    resourcesLoading.value = false
  }
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
onMounted(async () => {
  await loadContainerDetail()
  // Fetch stats snapshot after detail is loaded (non-blocking)
  fetchHeaderStats()
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
  flex-direction: column;
  gap: 12px;
}

.header-top {
  display: flex;
  align-items: center;
}

.header-identity {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.container-name {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.container-image {
  font-size: 13px;
  font-family: monospace;
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
  padding: 2px 8px;
  border-radius: 4px;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.container-uptime {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 4px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px;
  color: var(--color-text-secondary);
  flex-direction: column;
  gap: 12px;
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

.id-with-copy {
  display: flex;
  align-items: center;
  gap: 8px;
}

.id-with-copy code {
  font-size: 13px;
  font-family: monospace;
}

.command-text {
  padding: 4px 8px;
  font-size: 13px;
  font-family: monospace;
  background-color: var(--color-bg-hover);
  border-radius: 4px;
}

.text-muted {
  color: var(--color-text-placeholder);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.env-search {
  width: 200px;
  color: var(--color-text-placeholder);
}

.value-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.value-cell code {
  font-size: 12px;
  font-family: monospace;
  word-break: break-all;
}

.masked-value {
  color: var(--color-text-placeholder);
}

.secret-tag {
  margin-left: 8px;
}

.placeholder-content {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
}

.inspect-container {
  display: flex;
  height: 100%;
  flex-direction: column;
}

.rename-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  line-height: 1.5;
}

.rename-hint code {
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}

.form-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: -8px;
  margin-bottom: 12px;
  line-height: 1.5;
}

.inspect-textarea :deep(textarea) {
  font-size: 11px;
  font-family: monospace;
  line-height: 1.4;
}

@media (width <= 768px) {
  .header-identity {
    flex-direction: column;
    align-items: flex-start;
  }

  .container-name {
    max-width: 100%;
  }

  .container-image {
    max-width: 100%;
  }

  .header-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
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
