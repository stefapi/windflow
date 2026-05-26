<script setup lang="ts">
/**
 * AppCard Component
 *
 * Displays a single application as a card in Mode App.
 * Shows app info (icon, name, version, domain, status, RAM) and
 * provides inline actions (Open, Logs, Terminal, Stop/Start) plus
 * a context menu [⋯ Plus] via AppContextMenu.
 *
 * @see docs/general_specs/11-UI-mockups.md — Écran 2
 */

import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { containersApi } from '@/services/api'
import AppContextMenu from '@/components/ui/AppContextMenu.vue'
import type { AppCardData } from './helpers'

export interface AppCardProps {
  /** The app data to display */
  app: AppCardData
}

const props = defineProps<AppCardProps>()

const emit = defineEmits<{
  /** Emitted after a lifecycle action completes to refresh parent data */
  (e: 'refresh'): void
  /** Emitted when any action is triggered */
  (e: 'action', actionType: string, appId: string): void
}>()

const router = useRouter()

/** Whether the app is in a running state */
const isRunning = computed(() =>
  ['running', 'restarting'].includes(props.app.status.toLowerCase()),
)

/** Whether the app is in a stopped state */
const isStopped = computed(() =>
  ['stopped', 'exited', 'dead', 'created'].includes(props.app.status.toLowerCase()),
)

/** Status dot CSS class based on status color */
const statusDotClass = computed(() => {
  switch (props.app.statusColor) {
    case 'success': return 'bg-green-500'
    case 'danger': return 'bg-red-500'
    case 'warning': return 'bg-yellow-500'
    default: return 'bg-blue-400'
  }
})

/** Whether the app has a domain that can be opened */
const hasDomain = computed(() => !!props.app.domain)

/** Services summary text */
const servicesText = computed(() => {
  if (props.app.servicesTotal <= 1) return ''
  return `${props.app.servicesRunning}/${props.app.servicesTotal} services`
})

/** Handle the "Open" action — navigate to domain URL */
function handleOpen(): void {
  if (props.app.domain) {
    window.open(props.app.domain, '_blank', 'noopener')
  }
}

/** Handle the "Logs" action — navigate to container detail */
function handleLogs(): void {
  router.push(`/containers/${props.app.containerId}`)
}

/** Handle the "Terminal" action — navigate to container detail terminal tab */
function handleTerminal(): void {
  router.push(`/containers/${props.app.containerId}`)
}

/** Handle the "Stop" action */
async function handleStop(): Promise<void> {
  try {
    await containersApi.stop(props.app.containerId)
    ElMessage.success(`"${props.app.displayName}" arrêté`)
    emit('refresh')
  } catch {
    ElMessage.error(`Erreur lors de l'arrêt de "${props.app.displayName}"`)
  }
}

/** Handle the "Start" action */
async function handleStart(): Promise<void> {
  try {
    await containersApi.start(props.app.containerId)
    ElMessage.success(`"${props.app.displayName}" démarré`)
    emit('refresh')
  } catch {
    ElMessage.error(`Erreur lors du démarrage de "${props.app.displayName}"`)
  }
}

/** Handle context menu action */
function handleContextMenuAction(action: string): void {
  emit('action', action, props.app.id)

  switch (action) {
    case 'open':
      handleOpen()
      break
    case 'logs':
      handleLogs()
      break
    case 'console':
      handleTerminal()
      break
    case 'stop':
      handleStop()
      break
    case 'start':
      handleStart()
      break
    case 'restart':
      handleRestart()
      break
    default:
      break
  }
}

/** Handle the "Restart" action */
async function handleRestart(): Promise<void> {
  try {
    await containersApi.restart(props.app.containerId)
    ElMessage.success(`"${props.app.displayName}" redémarré`)
    emit('refresh')
  } catch {
    ElMessage.error(`Erreur lors du redémarrage de "${props.app.displayName}"`)
  }
}
</script>

<template>
  <el-card
    shadow="hover"
    class="app-card"
    data-testid="app-card"
  >
    <!-- Header: icon, name, version, status -->
    <div class="app-card-header flex items-center gap-3 mb-3">
      <span class="app-card-icon text-2xl">{{ app.icon }}</span>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <span class="font-semibold text-sm truncate">{{ app.displayName }}</span>
          <el-tag
            v-if="app.version"
            size="small"
            type="info"
          >
            {{ app.version }}
          </el-tag>
          <span
            v-if="app.updateAvailable"
            class="text-xs"
            title="Mise à jour disponible"
            data-testid="update-badge"
          >⬆</span>
        </div>
        <div class="flex items-center gap-2 mt-1 text-xs text-gray-500">
          <span
            class="inline-block w-2 h-2 rounded-full"
            :class="statusDotClass"
            data-testid="status-dot"
          />
          <span data-testid="status-label">{{ app.statusLabel }}</span>
        </div>
      </div>
    </div>

    <!-- Body: domain, target, services, RAM -->
    <div class="app-card-body text-xs text-gray-600 dark:text-gray-400 space-y-1 mb-3">
      <div
        v-if="hasDomain"
        class="flex items-center gap-1"
      >
        <a
          :href="app.domain!"
          target="_blank"
          rel="noopener"
          class="text-accent hover:underline truncate"
          data-testid="domain-link"
          @click.stop
        >
          {{ app.domain }}
        </a>
      </div>
      <div class="flex items-center gap-2 flex-wrap">
        <el-tag
          size="small"
          type="info"
        >
          {{ app.targetName }}
        </el-tag>
        <span v-if="servicesText">{{ servicesText }}</span>
        <span v-if="app.ram">RAM : {{ app.ram }}</span>
      </div>
    </div>

    <!-- Footer: inline actions + context menu -->
    <div class="app-card-actions flex items-center gap-1 flex-wrap">
      <el-button
        v-if="hasDomain"
        size="small"
        @click="handleOpen"
      >
        🔗 Ouvrir
      </el-button>
      <el-button
        size="small"
        @click="handleLogs"
      >
        📋 Logs
      </el-button>
      <el-button
        v-if="isRunning"
        size="small"
        @click="handleTerminal"
      >
        >_ Terminal
      </el-button>
      <el-button
        v-if="isRunning"
        size="small"
        @click="handleStop"
      >
        ⏸ Stop
      </el-button>
      <el-button
        v-if="isStopped"
        size="small"
        type="primary"
        @click="handleStart"
      >
        ▶ Start
      </el-button>
      <AppContextMenu
        :container-id="app.containerId"
        :container-name="app.displayName"
        :container-status="app.status"
        :domain="app.domain ?? undefined"
        :labels="app.labels"
        size="small"
        @action="handleContextMenuAction"
      />
    </div>
  </el-card>
</template>

<style scoped>
.app-card {
  border-radius: 12px;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.app-card:hover {
  transform: translateY(-1px);
}

.app-card-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.app-card-actions :deep(.el-button) {
  padding: 4px 8px;
  font-size: 12px;
}
</style>
