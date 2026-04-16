<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'

// Type pour le thème xterm.js
interface XtermTheme {
  background?: string
  foreground?: string
  cursor?: string
  cursorAccent?: string
  selectionBackground?: string
  black?: string
  red?: string
  green?: string
  yellow?: string
  blue?: string
  magenta?: string
  cyan?: string
  white?: string
  brightBlack?: string
  brightRed?: string
  brightGreen?: string
  brightYellow?: string
  brightBlue?: string
  brightMagenta?: string
  brightCyan?: string
  brightWhite?: string
}
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import {
  Delete,
  CopyDocument,
} from '@element-plus/icons-vue'
import { useTerminal } from '@/composables/useTerminal'
import { useAuthStore } from '@/stores/auth'
import { containersApi } from '@/services/api'
import type { ContainerShell } from '@/types/api'

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

// Shells disponibles (chargés dynamiquement via l'API)
const availableShells = ref<ContainerShell[]>([])
const shellsLoading = ref(false)

// Mode de commande : 'shell' pour les prédéfinis, 'custom' pour commande libre
const commandMode = ref<'shell' | 'custom'>('shell')
const selectedShell = ref(props.shell)
const customCommand = ref('')
const loginUser = ref(props.user)

/**
 * Charge les shells disponibles depuis l'API.
 * Fallback sur /bin/sh en cas d'erreur ou liste vide.
 */
async function loadShells() {
  shellsLoading.value = true
  try {
    const response = await containersApi.getShells(props.containerId)
    const shells = response.data.filter((s: ContainerShell) => s.available)
    if (shells.length > 0) {
      availableShells.value = shells
      selectedShell.value = shells[0]?.path ?? '/bin/sh'
    } else {
      // Fallback si aucun shell disponible
      availableShells.value = [{ path: '/bin/sh', label: 'sh', available: true }]
      selectedShell.value = '/bin/sh'
    }
  } catch {
    // Fallback en cas d'erreur API
    availableShells.value = [{ path: '/bin/sh', label: 'sh', available: true }]
    selectedShell.value = '/bin/sh'
  } finally {
    shellsLoading.value = false
  }
}

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
 * Lit les variables CSS du thème terminal et retourne un objet theme compatible xterm.js
 * xterm.js ne supporte pas les variables CSS directement, donc on les lit via getComputedStyle
 */
function getTerminalThemeFromCSS(): XtermTheme {
  const style = getComputedStyle(document.documentElement)
  const getVar = (name: string) => style.getPropertyValue(name).trim()

  return {
    background: getVar('--color-terminal-bg'),
    foreground: getVar('--color-terminal-fg'),
    cursor: getVar('--color-terminal-cursor'),
    cursorAccent: getVar('--color-terminal-bg'),
    selectionBackground: getVar('--color-terminal-selection'),
    black: getVar('--color-terminal-black'),
    red: getVar('--color-terminal-red'),
    green: getVar('--color-terminal-green'),
    yellow: getVar('--color-terminal-yellow'),
    blue: getVar('--color-terminal-blue'),
    magenta: getVar('--color-terminal-magenta'),
    cyan: getVar('--color-terminal-cyan'),
    white: getVar('--color-terminal-white'),
    brightBlack: getVar('--color-terminal-bright-black'),
    brightRed: getVar('--color-terminal-bright-red'),
    brightGreen: getVar('--color-terminal-bright-green'),
    brightYellow: getVar('--color-terminal-bright-yellow'),
    brightBlue: getVar('--color-terminal-bright-blue'),
    brightMagenta: getVar('--color-terminal-bright-magenta'),
    brightCyan: getVar('--color-terminal-bright-cyan'),
    brightWhite: getVar('--color-terminal-bright-white'),
  }
}

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
    theme: getTerminalThemeFromCSS(),
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
  loadShells()

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

          <!-- Sélecteur de shell dynamique -->
          <el-select
            v-if="commandMode === 'shell'"
            v-model="selectedShell"
            size="small"
            class="shell-select"
            :loading="shellsLoading"
            placeholder="Loading shells..."
          >
            <el-option
              v-for="s in availableShells"
              :key="s.path"
              :label="s.label"
              :value="s.path"
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
  overflow: hidden;
  height: 100%;
  min-height: 400px;
  background-color: var(--color-bg-card);
  border-radius: 4px;
  flex-direction: column;
}

.terminal-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  padding: 8px 12px;
  background-color: var(--color-bg-elevated);
  border-bottom: 1px solid var(--color-border-light);
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
  background-color: var(--color-success);
  animation: pulse 2s infinite;
}

.status-dot.connecting {
  background-color: var(--color-warning);
}

.status-dot.disconnected {
  background-color: var(--color-info);
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
  font-family: monospace;
  color: var(--color-text-secondary);
}

.shell-info {
  padding: 2px 8px;
  font-size: 12px;
  font-family: monospace;
  color: var(--color-text-secondary);
  background-color: var(--color-bg-hover);
  border-radius: 4px;
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
  overflow: hidden;
  padding: 8px;
  background-color: var(--color-terminal-bg);
  flex: 1;
}


.terminal-container :deep(.xterm) {
  height: 100%;
}

.terminal-container :deep(.xterm-viewport) {
  overflow-y: auto !important;
}

.error-message {
  flex-shrink: 0;
  padding: 8px 12px;
}

.not-connected-message {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.login-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.disconnect-bar {
  display: flex;
  justify-content: center;
  flex-shrink: 0;
  padding: 6px 12px;
  background-color: var(--color-bg-elevated);
  border-top: 1px solid var(--color-border-light);
}
</style>
