<template>
  <div class="flex flex-col h-full bg-bg-secondary rounded-lg overflow-hidden">
    <!-- En-tête avec actions -->
    <div class="logs-header flex-between">
      <div class="flex items-center font-semibold text-sm">
        <span class="i-carbon-document-blank mr-2" />
        <span>Logs de déploiement</span>
        <el-tag
          v-if="isConnected"
          type="success"
          size="small"
          class="ml-2"
        >
          <span class="i-carbon-dot-mark animate-pulse" />
          En direct
        </el-tag>
        <el-tag
          v-else
          type="info"
          size="small"
          class="ml-2"
        >
          Hors ligne
        </el-tag>
      </div>

      <div class="flex items-center gap-2">
        <!-- Nombre de lignes -->
        <span class="text-label mr-4">
          {{ logs.length }} ligne{{ logs.length > 1 ? 's' : '' }}
        </span>

        <!-- Auto-scroll toggle -->
        <el-tooltip
          content="Défilement automatique"
          placement="top"
        >
          <el-button
            :type="autoScroll ? 'primary' : 'default'"
            size="small"
            circle
            @click="toggleAutoScroll"
          >
            <span :class="autoScroll ? 'i-carbon-arrow-down' : 'i-carbon-pause-outline'" />
          </el-button>
        </el-tooltip>

        <!-- Effacer les logs -->
        <el-tooltip
          content="Effacer les logs"
          placement="top"
        >
          <el-button
            type="default"
            size="small"
            circle
            :disabled="logs.length === 0"
            @click="handleClearLogs"
          >
            <span class="i-carbon-clean" />
          </el-button>
        </el-tooltip>

        <!-- Copier dans le presse-papier -->
        <el-tooltip
          content="Copier dans le presse-papier"
          placement="top"
        >
          <el-button
            type="default"
            size="small"
            circle
            :disabled="logs.length === 0"
            @click="copyToClipboard"
          >
            <span class="i-carbon-copy" />
          </el-button>
        </el-tooltip>

        <!-- Télécharger les logs -->
        <el-tooltip
          content="Télécharger les logs"
          placement="top"
        >
          <el-button
            type="default"
            size="small"
            circle
            :disabled="logs.length === 0"
            @click="downloadLogs"
          >
            <span class="i-carbon-download" />
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- Conteneur des logs avec barre de progression -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Barre de progression si disponible -->
      <div
        v-if="progress > 0"
        class="px-4 py-3 bg-bg-card border-b border-border"
      >
        <el-progress
          :percentage="progress"
          :status="status === 'failed' ? 'exception' : status === 'completed' ? 'success' : undefined"
          :stroke-width="8"
        >
          <template #default="{ percentage }">
            <span class="text-xs">{{ percentage }}% - {{ currentStep }}</span>
          </template>
        </el-progress>
      </div>

      <!-- Logs avec auto-scroll -->
      <div
        ref="logsScrollContainer"
        class="logs-content flex-1 overflow-y-auto"
        :class="{ 'scroll-smooth': autoScroll }"
        @scroll="handleScroll"
      >
        <div
          v-if="logs.length === 0"
          class="flex flex-col items-center justify-center h-full text-text-muted"
        >
          <span class="i-carbon-document-blank text-4xl mb-2" />
          <p class="text-text-secondary">
            Aucun log disponible
          </p>
          <p
            v-if="!isConnected"
            class="text-sm text-text-muted mt-2"
          >
            Connexion aux logs en temps réel...
          </p>
        </div>

        <div
          v-else
          class="flex flex-col"
        >
          <div
            v-for="(line, index) in logs"
            :key="index"
            class="log-line"
            :class="getLogLevel(line)"
          >
            <span class="log-line-number">{{ index + 1 }}</span>
            <span class="log-line-content">{{ line }}</span>
          </div>
        </div>
      </div>

      <!-- Message d'erreur si présent -->
      <div
        v-if="errorMessage"
        class="px-4 py-3 bg-bg-card border-t border-border"
      >
        <el-alert
          type="error"
          :closable="false"
          show-icon
        >
          <template #title>
            <span class="font-semibold">Erreur de déploiement</span>
          </template>
          {{ errorMessage }}
        </el-alert>
      </div>
    </div>

    <!-- Footer avec dernière mise à jour -->
    <div
      v-if="lastUpdate"
      class="logs-footer"
    >
      <span class="text-xs text-text-muted">
        Dernière mise à jour : {{ formatDate(lastUpdate) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useDeploymentWebSocket } from '@/composables/useDeploymentWebSocket'

interface Props {
  deploymentId: string
  deploymentName?: string
  autoConnect?: boolean
  debug?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoConnect: true,
  debug: false
})

// Utiliser le composable WebSocket
const {
  status,
  logs,
  progress,
  currentStep,
  errorMessage,
  isConnected,
  lastUpdate,
  clearLogs
} = useDeploymentWebSocket(props.deploymentId, {
  autoConnect: props.autoConnect,
  debug: props.debug
})

// État local
const logsScrollContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)

/**
 * Déterminer le niveau de log basé sur le contenu de la ligne
 */
const getLogLevel = (line: string): string => {
  const lowerLine = line.toLowerCase()

  if (lowerLine.includes('error') || lowerLine.includes('err:') || lowerLine.includes('failed')) {
    return 'log-error'
  }
  if (lowerLine.includes('warn') || lowerLine.includes('warning')) {
    return 'log-warning'
  }
  if (lowerLine.includes('info') || lowerLine.includes('✓') || lowerLine.includes('success')) {
    return 'log-info'
  }
  if (lowerLine.includes('debug') || lowerLine.includes('trace')) {
    return 'log-debug'
  }

  return ''
}

/**
 * Scroller automatiquement vers le bas quand de nouveaux logs arrivent
 */
const scrollToBottom = () => {
  if (autoScroll.value && logsScrollContainer.value) {
    nextTick(() => {
      if (logsScrollContainer.value) {
        logsScrollContainer.value.scrollTop = logsScrollContainer.value.scrollHeight
      }
    })
  }
}

/**
 * Gérer le scroll manuel (désactiver auto-scroll si l'utilisateur scroll vers le haut)
 */
const handleScroll = () => {
  if (!logsScrollContainer.value) return

  const { scrollTop, scrollHeight, clientHeight } = logsScrollContainer.value
  const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 50

  // Si l'utilisateur scroll manuellement vers le haut, désactiver auto-scroll
  if (!isAtBottom && autoScroll.value) {
    autoScroll.value = false
  }
}

/**
 * Toggle auto-scroll
 */
const toggleAutoScroll = () => {
  autoScroll.value = !autoScroll.value
  if (autoScroll.value) {
    scrollToBottom()
  }
}

/**
 * Effacer les logs avec confirmation
 */
const handleClearLogs = () => {
  ElMessage.warning('Logs effacés (uniquement en local)')
  clearLogs()
}

/**
 * Copier les logs dans le presse-papier
 */
const copyToClipboard = async () => {
  try {
    const logsText = logs.value.join('\n')
    await navigator.clipboard.writeText(logsText)
    ElMessage.success('Logs copiés dans le presse-papier')
  } catch (_err) {
    ElMessage.error('Échec de la copie dans le presse-papier')
  }
}

/**
 * Télécharger les logs en fichier texte
 */
const downloadLogs = () => {
  const logsText = logs.value.join('\n')
  const blob = new Blob([logsText], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  const filename = props.deploymentName
    ? `${props.deploymentName}-logs.txt`
    : `deployment-${props.deploymentId}-logs.txt`

  link.href = url
  link.download = filename
  link.click()

  URL.revokeObjectURL(url)
  ElMessage.success('Logs téléchargés')
}

/**
 * Formater la date de dernière mise à jour
 */
const formatDate = (date: Date): string => {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'medium'
  }).format(date)
}

// Watcher pour scroller automatiquement quand de nouveaux logs arrivent
watch(logs, () => {
  scrollToBottom()
}, { deep: true })
</script>

<style scoped>
.logs-header {
  padding: 12px 16px;
  background-color: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
}

.logs-content {
  padding: 12px;
  font-size: 13px;
  font-family: var(--font-mono);
  color: var(--color-code-fg);
  background: var(--color-code-bg);
  line-height: 1.6;
}

.log-line {
  display: flex;
  padding: 2px 0;
  transition: background-color 0.2s;
}

.log-line:hover {
  background-color: var(--color-log-hover-bg);
}

.log-line-number {
  flex-shrink: 0;
  width: 50px;
  padding-right: 12px;
  font-size: 12px;
  text-align: right;
  color: var(--color-log-line-number);
  user-select: none;
}

.log-line-content {
  flex: 1;
  word-break: break-all;
  white-space: pre-wrap;
}

/* Log levels styling - colors use UnoCSS shortcuts via getLogLevel() */

/* Only font styles remain here; colors are applied via log-error, log-warning, log-info, log-debug classes */
.log-error .log-line-content {
  font-weight: 500;
}

.log-debug .log-line-content {
  font-style: italic;
}

.logs-footer {
  padding: 8px 16px;
  text-align: right;
  background-color: var(--color-bg-card);
  border-top: 1px solid var(--color-border);
}
</style>
