<template>
  <div class="flex flex-col h-[calc(100vh-350px)] min-h-400px">
    <!-- Header with controls -->
    <div class="logs-header flex-between">
      <div class="flex items-center gap-2">
        <el-tag
          :type="connectionTagType"
          size="small"
        >
          {{ connectionStatusText }}
        </el-tag>
      </div>

      <div class="flex items-center gap-3">
        <!-- Log filter -->
        <el-select
          v-model="logFilter"
          size="small"
          placeholder="Filtrer par flux"
          clearable
          class="w-120px"
        >
          <el-option
            label="Tous"
            value="all"
          />
          <el-option
            label="stdout"
            value="stdout"
          />
          <el-option
            label="stderr"
            value="stderr"
          />
        </el-select>

        <!-- Tail selector -->
        <el-input-number
          v-model="tailLines"
          :min="10"
          :max="10000"
          size="small"
          style="width: 160px"
          controls-position="right"
          @change="handleTailChange"
        />
        <span class="text-label">lignes</span>

        <!-- Action buttons -->
        <el-button-group class="ml-auto">
          <el-button
            size="small"
            @click="toggleAutoScroll"
          >
            <el-icon>
              <Bottom v-if="autoScroll" />
              <Lock v-else />
            </el-icon>
            {{ autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF' }}
          </el-button>
          <el-button
            v-show="!isScrolledToBottom && !autoScroll"
            size="small"
            type="primary"
            @click="scrollToBottom"
          >
            <el-icon><Bottom /></el-icon>
            Descendre
          </el-button>
          <el-button
            size="small"
            @click="handleDownload"
          >
            <el-icon><Download /></el-icon>
            Télécharger
          </el-button>
          <el-button
            size="small"
            @click="handleClear"
          >
            <el-icon><Delete /></el-icon>
            Effacer
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- Error alert -->
    <el-alert
      v-if="logError"
      :title="logError"
      type="error"
      show-icon
      closable
      @close="logError = null"
    />

    <!-- Logs content -->
    <div
      ref="logsContainerRef"
      class="logs-container flex-1 overflow-auto rounded position-relative min-h-200px"
      @scroll="handleScroll"
    >
      <!-- Loading state -->
      <div
        v-if="status === 'connecting'"
        class="flex-center gap-2 h-200px text-text-secondary"
      >
        <el-icon class="is-loading">
          <Loading />
        </el-icon>
        <span>Connexion en cours...</span>
      </div>

      <!-- Empty state -->
      <div
        v-else-if="!filteredLogs.length"
        class="flex-center h-200px"
      >
        <el-empty description="Aucun log disponible" />
      </div>

      <!-- Logs lines -->
      <div
        v-else
        class="logs-content font-mono text-xs leading-relaxed"
      >
        <div
          v-for="(line, index) in filteredLogs"
          :key="index"
          :class="['log-line', getLogLineClass(line)]"
        >
          {{ line }}
        </div>
      </div>
    </div>

    <!-- Scroll to bottom button (floating) -->
    <el-button
      v-show="!isScrolledToBottom && !autoScroll && filteredLogs.length > 10"
      class="!absolute !bottom-5 !right-5 !z-10 shadow-md"
      circle
      type="primary"
      size="small"
      @click="scrollToBottom"
    >
      <el-icon><Bottom /></el-icon>
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  Download,
  Delete,
  Bottom,
  Lock,
  Loading,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useContainerLogs } from '@/composables/useContainerLogs'

// Props
interface Props {
  containerId: string
  containerName?: string
}

const props = defineProps<Props>()

// State
const logFilter = ref<'all' | 'stdout' | 'stderr'>('all')
const tailLines = ref(100)
const autoScroll = ref(true)
const isScrolledToBottom = ref(true)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const logsContainerRef = ref<any>(null)

// Use the composable for WebSocket connection
// Pass tailLines as a ref so that handleTailChange can use the updated value
const {
  logs,
  status,
  error: logError,
  connect,
  disconnect,
  clearLogs,
  downloadLogs,
} = useContainerLogs({
  containerId: props.containerId,
  tail: tailLines,
  autoConnect: true,
})

// Computed
const connectionTagType = computed(() => {
  switch (status.value) {
    case 'connected':
      return 'success'
    case 'connecting':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
})

const connectionStatusText = computed(() => {
  switch (status.value) {
    case 'connected':
      return 'Connecté'
    case 'connecting':
      return 'Connexion...'
    case 'error':
      return 'Erreur'
    default:
      return 'Déconnecté'
  }
})

// Parse logs into lines and filter them
const logLines = computed(() => {
  if (!logs.value) return []
  return logs.value.split('\n').filter(line => line.trim().length > 0)
})

// Filter logs by type (stdout/stderr)
const filteredLogs = computed(() => {
  if (logFilter.value === 'all') {
    return logLines.value
  }

  // Check if line is stderr based on [ERR] prefix (from backend) or content heuristics
  const isStderr = (line: string): boolean => {
    // Check for explicit [ERR] prefix added by backend
    if (line.startsWith('[ERR]')) {
      return true
    }
    // Fallback: content heuristics
    const lowerLine = line.toLowerCase()
    return (
      lowerLine.includes('error') ||
      lowerLine.includes('warn') ||
      lowerLine.includes('fail') ||
      lowerLine.includes('exception') ||
      lowerLine.includes('fatal') ||
      /^\s*(error|warn|fatal)/i.test(line)
    )
  }

  const isStdout = (line: string): boolean => !isStderr(line)

  if (logFilter.value === 'stderr') {
    return logLines.value.filter(isStderr)
  }
  return logLines.value.filter(isStdout)
})

// Methods
function getLogLineClass(line: string): string {
  const lowerLine = line.toLowerCase()
  if (
    lowerLine.includes('error') ||
    lowerLine.includes('fail') ||
    lowerLine.includes('fatal') ||
    lowerLine.includes('exception')
  ) {
    return 'log-error'
  }
  if (lowerLine.includes('warn')) {
    return 'log-warning'
  }
  if (
    lowerLine.includes('info') ||
    lowerLine.includes('debug') ||
    lowerLine.includes('trace')
  ) {
    return 'log-info'
  }
  return ''
}

function handleScroll(): void {
  if (!logsContainerRef.value) return

  const container = logsContainerRef.value
  const { scrollTop, scrollHeight, clientHeight } = container
  const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10

  isScrolledToBottom.value = isAtBottom
}

function scrollToBottom(): void {
  if (!logsContainerRef.value) return

  nextTick(() => {
    logsContainerRef.value!.scrollTop = logsContainerRef.value!.scrollHeight
    isScrolledToBottom.value = true
  })
}

function toggleAutoScroll(): void {
  autoScroll.value = !autoScroll.value
  if (autoScroll.value) {
    scrollToBottom()
  }
  ElMessage.success(autoScroll.value ? 'Auto-scroll activé' : 'Auto-scroll désactivé')
}

function handleTailChange(): void {
  // Reconnect with new tail value
  disconnect()
  clearLogs()
  connect()
}

function handleDownload(): void {
  const filename = `logs-${props.containerName || props.containerId.substring(0, 12)}-${new Date().toISOString().split('.')[0]}.txt`
  downloadLogs(filename)
  ElMessage.success('Logs téléchargés')
}

function handleClear(): void {
  clearLogs()
  ElMessage.success('Logs effacés')
}

// Auto-scroll effect
watch([logLines, autoScroll], () => {
  if (autoScroll.value && logLines.value.length > 0) {
    scrollToBottom()
  }
})

// Lifecycle
onMounted(() => {
  // Initial scroll to bottom
  scrollToBottom()
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
/* Log line styling - colors handled by UnoCSS shortcuts (log-error, log-warning, log-info) */
.log-line {
  padding: 2px 4px;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-code-fg);
}

/* Log level backgrounds use CSS variables for theme support */
.log-line.log-error {
  background-color: var(--color-log-error-bg);
}

.log-line.log-warning {
  background-color: var(--color-log-warning-bg);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .logs-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
