<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import {
  Delete,
  CopyDocument,
} from '@element-plus/icons-vue'
import { useTerminal } from '@/composables/useTerminal'
import { useAuthStore } from '@/stores/auth'

// Types pour les props
interface Props {
  containerId: string
  shell?: string
  user?: string
  theme?: 'dark' | 'light'
  fontSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  shell: '/bin/sh',
  user: 'root',
  theme: 'dark',
  fontSize: 14
})

// Shells prédéfinis
const PREDEFINED_SHELLS = [
  { value: '/bin/sh', label: 'sh' },
  { value: '/bin/bash', label: 'bash' },
  { value: '/bin/ash', label: 'ash' },
]

// Mode de commande : 'shell' pour les prédéfinis, 'custom' pour commande libre
const commandMode = ref<'shell' | 'custom'>('shell')
const selectedShell = ref(props.shell)
const customCommand = ref('')
const loginUser = ref(props.user)

// La commande effective à envoyer au serveur
const effectiveCommand = computed(() => {
  return commandMode.value === 'custom' ? customCommand.value : selectedShell.value
})

// Refs
const terminalRef = ref<HTMLElement | null>(null)
const fontSize = ref(props.fontSize)
const isReady = ref(false)

// Store auth pour récupérer le token
const authStore = useAuthStore()

// Utiliser le composable terminal
const {
  connected,
  connecting,
  error,
  execId,
  terminal,
  activeShell,
  activeUser,
  connect,
  disconnect,
  sendInput,
  resize,
  clear,
  copyOutput
} = useTerminal({
  containerId: props.containerId,
  shell: props.shell,
  user: props.user,
  onConnected: () => {
    isReady.value = true
    nextTick(() => fitTerminal())
  },
  onDisconnected: (reason) => {
    isReady.value = false
    console.log('Disconnected:', reason)
  },
  onError: (err) => {
    console.error('Terminal error:', err)
  }
})

// Instances xterm
let xterm: Terminal | null = null
let fitAddon: FitAddon | null = null
let webLinksAddon: WebLinksAddon | null = null

/**
 * Connexion avec les paramètres choisis par l'utilisateur
 */
function connectWithOptions() {
  if (!authStore.token) return
  const cmd = effectiveCommand.value.trim()
  if (!cmd) return

  connect(authStore.token, {
    shell: cmd,
    user: loginUser.value.trim() || 'root',
  })
}

// Initialiser xterm.js
function initTerminal() {
  if (!terminalRef.value) return

  // Récupérer la police mono depuis les variables CSS
  const computedStyle = getComputedStyle(document.documentElement)
  const fontMono = computedStyle.getPropertyValue('--font-mono').trim() || '"JetBrains Mono", monospace'

  // Créer le terminal xterm
  xterm = new Terminal({
    cursorBlink: true,
    fontFamily: fontMono,
    fontSize: fontSize.value,
    theme: props.theme === 'dark' ? {
      background: '#0c0c0c',
      foreground: '#cccccc',
      cursor: '#ffffff',
      cursorAccent: '#000000',
      selectionBackground: '#264f78',
      black: '#000000',
      red: '#cd3131',
      green: '#0dbc79',
      yellow: '#e5e510',
      blue: '#2472c8',
      magenta: '#bc3fbc',
      cyan: '#11a8cd',
      white: '#e5e5e5',
      brightBlack: '#666666',
      brightRed: '#f14c4c',
      brightGreen: '#23d18b',
      brightYellow: '#f5f543',
      brightBlue: '#3b8eea',
      brightMagenta: '#d670d6',
      brightCyan: '#29b8db',
      brightWhite: '#ffffff',
    } : {
      background: '#ffffff',
      foreground: '#000000',
      cursor: '#000000',
      cursorAccent: '#ffffff',
      selectionBackground: '#add6ff',
    },
    scrollback: 1000,
    cursorInactiveStyle: 'none',
    allowProposedApi: true,
  })

  // Charger les addons
  fitAddon = new FitAddon()
  webLinksAddon = new WebLinksAddon()

  xterm.loadAddon(fitAddon)
  xterm.loadAddon(webLinksAddon)

  // Ouvrir le terminal dans le DOM
  xterm.open(terminalRef.value)

  // Masquer le curseur tant que non connecté (cursorInactiveStyle: 'none')
  xterm.blur()

  // Ajuster à la taille du container
  nextTick(() => fitTerminal())

  // Gérer les événements clavier
  xterm.onData((data) => {
    if (connected.value) {
      sendInput(data)
    }
  })

  // Gérer le redimensionnement
  xterm.onResize(({ cols, rows }) => {
    if (connected.value) {
      resize(cols, rows)
    }
  })

  // Configurer les raccourcis clavier
  xterm.attachCustomKeyEventHandler((e: KeyboardEvent) => {
    // Ctrl/Cmd + L: Clear
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
      e.preventDefault()
      clear()
      return false
    }
    return true
  })

  // Stocker la référence pour le composable
  terminal.value = xterm

  // Connecter automatiquement si on a un token
  if (authStore.token) {
    connectWithOptions()
  }
}

// Ajuster la taille du terminal
function fitTerminal() {
  if (fitAddon && xterm) {
    try {
      fitAddon.fit()
    } catch (e) {
      // fitAddon.fit() peut échouer si le conteneur n'est pas encore visible
      console.warn('fitAddon.fit() failed:', e)
      return
    }
    if (connected.value) {
      // Envoyer les dimensions actuelles du terminal au backend
      // (fitAddon.fit() a déjà redimensionné le terminal localement)
      resize(xterm.cols, xterm.rows)
    }
  }
}

// Changer la taille de police
function changeFontSize() {
  if (xterm) {
    xterm.options.fontSize = fontSize.value
    nextTick(() => fitTerminal())
  }
}

// Gestion du redimensionnement window
let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  initTerminal()

  // Observer les changements de taille
  if (terminalRef.value?.parentElement) {
    resizeObserver = new ResizeObserver(() => {
      if (connected.value) {
        fitTerminal()
      }
    })
    resizeObserver.observe(terminalRef.value.parentElement)
  }

  // Écouter les changements de taille window
  window.addEventListener('resize', fitTerminal)
})

onUnmounted(() => {
  // Nettoyer
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  window.removeEventListener('resize', fitTerminal)
  disconnect()
  xterm?.dispose()
})

// Surveiller les changements de connexion pour ajuster automatiquement
watch(connected, (newVal) => {
  if (newVal) {
    nextTick(() => {
      fitTerminal()
      xterm?.focus()
    })
  } else {
    // Masquer le curseur quand déconnecté (cursorInactiveStyle: 'none')
    xterm?.blur()
  }
})

// Exposer des fonctions pour le parent
defineExpose({
  clear,
  copyOutput,
  fit: fitTerminal
})
</script>

<template>
  <div class="terminal-wrapper">
    <!-- Toolbar -->
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <!-- Statut de connexion -->
        <el-tag
          :type="connected ? 'success' : connecting ? 'warning' : 'info'"
          size="small"
          class="status-tag"
        >
          <span
            v-if="connected"
            class="status-dot connected"
          />
          <span
            v-else-if="connecting"
            class="status-dot connecting"
          />
          <span
            v-else
            class="status-dot disconnected"
          />
          {{ connected ? 'Connected' : connecting ? 'Connecting...' : 'Disconnected' }}
        </el-tag>

        <!-- Exec ID si connecté -->
        <span
          v-if="execId"
          class="exec-id"
        >
          Session: {{ execId }}
        </span>

        <!-- Shell/commande actif (affiché quand connecté) -->
        <span
          v-if="connected"
          class="shell-info"
        >
          {{ activeShell }}
        </span>

        <!-- User actif (affiché quand connecté) -->
        <span
          v-if="connected"
          class="shell-info"
        >
          {{ activeUser }}
        </span>
      </div>

      <div class="toolbar-right">
        <!-- Contrôles shell/user (éditables quand déconnecté) -->
        <template v-if="!connected && !connecting">
          <!-- Mode : shell prédéfini ou commande custom -->
          <el-radio-group
            v-model="commandMode"
            size="small"
          >
            <el-radio-button value="shell">
              Shell
            </el-radio-button>
            <el-radio-button value="custom">
              Custom
            </el-radio-button>
          </el-radio-group>

          <!-- Sélecteur de shell prédéfini -->
          <el-select
            v-if="commandMode === 'shell'"
            v-model="selectedShell"
            size="small"
            class="shell-select"
          >
            <el-option
              v-for="s in PREDEFINED_SHELLS"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>

          <!-- Champ commande custom -->
          <el-input
            v-else
            v-model="customCommand"
            size="small"
            class="custom-command-input"
            placeholder="e.g. /usr/bin/python3"
            clearable
            @keyup.enter="connectWithOptions"
          />

          <!-- Champ utilisateur -->
          <el-input
            v-model="loginUser"
            size="small"
            class="user-input"
            placeholder="user, user:group, uid, uid:gid"
          >
            <template #prepend>
              @
            </template>
          </el-input>
        </template>

        <!-- Taille de police -->
        <el-select
          v-model="fontSize"
          size="small"
          class="font-size-select"
          @change="changeFontSize"
        >
          <el-option
            label="10px"
            :value="10"
          />
          <el-option
            label="12px"
            :value="12"
          />
          <el-option
            label="14px"
            :value="14"
          />
          <el-option
            label="16px"
            :value="16"
          />
          <el-option
            label="18px"
            :value="18"
          />
        </el-select>

        <!-- Boutons d'action -->
        <el-button-group size="small">
          <el-button
            :disabled="!connected"
            title="Clear terminal (Ctrl+L)"
            @click="clear"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
          <el-button
            :disabled="!connected"
            title="Copy output"
            @click="copyOutput"
          >
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- Container Terminal -->
    <div
      ref="terminalRef"
      class="terminal-container"
      :class="{ 'theme-dark': theme === 'dark', 'theme-light': theme === 'light' }"
    />

    <!-- Message d'erreur -->
    <div
      v-if="error"
      class="error-message"
    >
      <el-alert
        type="error"
        :closable="false"
      >
        {{ error }}
      </el-alert>
    </div>

    <!-- Overlay de connexion si pas connecté -->
    <div
      v-if="!connected && !connecting"
      class="not-connected-message"
    >
      <el-button
        type="primary"
        :disabled="!authStore.token || (commandMode === 'custom' && !customCommand.trim())"
        @click="connectWithOptions"
      >
        Connect to Terminal
      </el-button>
      <p
        v-if="!authStore.token"
        class="login-hint"
      >
        Please login to access the terminal
      </p>
      <p
        v-else-if="commandMode === 'custom' && !customCommand.trim()"
        class="login-hint"
      >
        Enter a custom command above
      </p>
    </div>

    <!-- Bouton Disconnect flottant quand connecté -->
    <div
      v-if="connected || connecting"
      class="disconnect-bar"
    >
      <el-button
        type="danger"
        size="small"
        plain
        @click="disconnect"
      >
        Disconnect
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.terminal-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
  background-color: var(--el-bg-color);
  border-radius: 4px;
  overflow: hidden;
}

.terminal-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background-color: var(--el-bg-color-overlay);
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-tag {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.connected {
  background-color: #67c23a;
  animation: pulse 2s infinite;
}

.status-dot.connecting {
  background-color: #e6a23c;
}

.status-dot.disconnected {
  background-color: #909399;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.exec-id {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.shell-info {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  padding: 2px 8px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  font-family: monospace;
}

.shell-select {
  width: 100px;
}

.custom-command-input {
  width: 200px;
}

.user-input {
  width: 200px;
}

.user-input :deep(.el-input-group__prepend) {
  padding: 0 8px;
  font-family: monospace;
}

.font-size-select {
  width: 80px;
}

.terminal-container {
  flex: 1;
  padding: 8px;
  overflow: hidden;
}

.terminal-container.theme-dark {
  background-color: #0c0c0c;
}

.terminal-container.theme-light {
  background-color: #ffffff;
}

.terminal-container :deep(.xterm) {
  height: 100%;
}

.terminal-container :deep(.xterm-viewport) {
  overflow-y: auto !important;
}

.error-message {
  padding: 8px 12px;
  flex-shrink: 0;
}

.not-connected-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  flex: 1;
}

.login-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.disconnect-bar {
  display: flex;
  justify-content: center;
  padding: 6px 12px;
  background-color: var(--el-bg-color-overlay);
  border-top: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}
</style>
