<template>
  <div class="container-logs">
    <!-- Header with controls -->
    <div class="logs-header">
      <div class="logs-status">
        <el-tag
          :type="connectionTagType"
          size="small"
        >
          {{ connectionStatusText }}
        </el-tag>
      </div>

      <div class="logs-controls">
        <!-- Log filter -->
        <el-select
          v-model="logFilter"
          size="small"
          placeholder="Filtrer par flux"
          clearable
          class="filter-select"
        >
          <el-option label="Tous" value="all" />
          <el-option label="stdout" value="stdout" />
          <el-option label="stderr" value="stderr" />
        </el-select>

        <!-- Tail selector -->
        <el-input-number
          v-model="tailLines"
          :min="10"
          :max="10000"
          size="small"
          class="tail-input"
          @change="handleTailChange"
        />
        <span class="tail-label">lignes</span>

        <!-- Action buttons -->
        <el-button-group class="action-buttons">
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
      class="logs-container"
      @scroll="handleScroll"
    >
      <!-- Loading state -->
      <div
        v-if="status === 'connecting'"
        class="logs-loading"
      >
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>Connexion en cours...</span>
      </div>

      <!-- Empty state -->
      <div
        v-else-if="!filteredLogs.length"
        class="logs-empty"
      >
        <el-empty description="Aucun log disponible" />
      </div>

      <!-- Logs lines -->
      <div
        v-else
        class="logs-content"
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
      class="scroll-to-bottom-btn"
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
const logsContainerRef = ref<HTMLElement | null>(null)

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
.container-logs {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
}

.logs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.logs-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logs-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-select {
  width: 120px;
}

.tail-input {
  width: 100px;
}

.tail-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.action-buttons {
  margin-left: auto;
}

.logs-container {
  flex: 1;
  overflow: auto;
  background-color: #1e1e1e;
  border-radius: 4px;
  position: relative;
  max-height: calc(100vh - 300px);
  min-height: 200px;
}

.logs-loading,
.logs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--el-text-color-secondary);
}

.logs-loading {
  flex-direction: row;
  gap: 8px;
}

.logs-content {
  padding: 8px 12px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-line {
  padding: 2px 4px;
  white-space: pre-wrap;
  word-break: break-all;
  color: #d4d4d4;
}

.log-line.log-error {
  color: #f48771;
  background-color: rgba(244, 67, 54, 0.1);
}

.log-line.log-warning {
  color: #cca700;
  background-color: rgba(204, 153, 0, 0.1);
}

.log-line.log-info {
  color: #4fc3f7;
}

.scroll-to-bottom-btn {
  position: absolute;
  bottom: 20px;
  right: 20px;
  z-index: 10;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .logs-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .logs-controls {
    flex-wrap: wrap;
  }
}
</style>
