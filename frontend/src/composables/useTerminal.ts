/**
 * Composable pour le terminal interactif WebSocket
 *
 * Gère la connexion WebSocket et l'intégration avec xterm.js
 */

import { ref, onUnmounted, type Ref } from 'vue'
import type { Terminal } from '@xterm/xterm'

export interface UseTerminalOptions {
  containerId: string
  shell?: string
  user?: string
  onConnected?: () => void
  onDisconnected?: (reason?: string) => void
  onError?: (error: string) => void
}

export interface ConnectOptions {
  shell?: string
  user?: string
}

export interface UseTerminalReturn {
  terminal: Ref<Terminal | null>
  connected: Ref<boolean>
  connecting: Ref<boolean>
  error: Ref<string | null>
  execId: Ref<string | null>
  activeShell: Ref<string>
  activeUser: Ref<string>
  connect: (token: string, options?: ConnectOptions) => Promise<void>
  disconnect: () => void
  sendInput: (data: string) => void
  resize: (cols: number, rows: number) => void
  clear: () => void
  copyOutput: () => Promise<string>
}

/**
 * Composable pour gérer une session terminal WebSocket
 *
 * @example
 * const { connected, connect, disconnect, sendInput } = useTerminal({
 *   containerId: 'container-123',
 *   shell: '/bin/bash',
 *   onConnected: () => console.log('Connected!'),
 *   onError: (err) => console.error(err)
 * })
 */
export function useTerminal(options: UseTerminalOptions): UseTerminalReturn {
  const {
    containerId,
    shell = '/bin/sh',
    user = 'root',
    onConnected,
    onDisconnected,
    onError
  } = options

  // Refs
  const terminal = ref<Terminal | null>(null) as Ref<Terminal | null>
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref<string | null>(null)
  const execId = ref<string | null>(null)
  const activeShell = ref(shell)
  const activeUser = ref(user)

  // WebSocket connection
  let ws: WebSocket | null = null

  /**
   * Établit la connexion WebSocket au terminal
   *
   * @param token - JWT token pour l'authentification
   * @param connectOpts - Options de connexion (shell, user) qui surchargent les défauts
   */
  async function connect(token: string, connectOpts?: ConnectOptions): Promise<void> {
    // Nettoyer un WebSocket stale (fermé ou en cours de fermeture)
    if (ws && (ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING)) {
      ws = null
    }

    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      console.warn('Already connected or connecting')
      return
    }

    // Utiliser les options de connexion ou les défauts
    const connectShell = connectOpts?.shell || shell
    const connectUser = connectOpts?.user || user
    activeShell.value = connectShell
    activeUser.value = connectUser

    connecting.value = true
    error.value = null

    // Construire l'URL WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/v1/ws/terminal/${containerId}?shell=${encodeURIComponent(connectShell)}&user=${encodeURIComponent(connectUser)}`

    try {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('WebSocket opened, authenticating...')

        // Envoyer le message d'authentification
        ws?.send(JSON.stringify({
          type: 'auth',
          token
        }))
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleMessage(message)
        } catch (e) {
          console.error('Failed to parse message:', e)
        }
      }

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        connecting.value = false
        error.value = 'Connection error'
        onError?.('Connection error')
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.reason)
        ws = null
        connected.value = false
        connecting.value = false
        execId.value = null

        if (!event.wasClean && error.value) {
          onDisconnected?.(event.reason || 'Connection closed')
        } else if (event.wasClean) {
          onDisconnected?.('User disconnected')
        }
      }

    } catch (e) {
      connecting.value = false
      error.value = e instanceof Error ? e.message : 'Failed to connect'
      onError?.(error.value)
    }
  }

  /**
   * Gère les messages reçus du serveur
   */
  function handleMessage(message: { type: string; [key: string]: unknown }) {
    switch (message.type) {
      case 'ready':
        // Authentification réussie
        connected.value = true
        execId.value = message['exec_id'] as string
        connecting.value = false
        onConnected?.()

        // Envoyer les dimensions initiales
        if (terminal.value) {
          sendResize(terminal.value.cols, terminal.value.rows)
        }
        break

      case 'output':
        // Afficher la sortie dans le terminal
        if (terminal.value && message['data']) {
          terminal.value.write(message['data'] as string)
        }
        break

      case 'error':
        // Erreur du serveur
        error.value = message['message'] as string
        connecting.value = false
        onError?.(message['message'] as string)

        if (terminal.value) {
          terminal.value.writeln(`\x1b[31mError: ${message['message']}\x1b[0m`)
        }
        break

      case 'exit': {
        // Session terminée — fermer proprement le WebSocket
        const code = message['code'] as number
        if (terminal.value) {
          terminal.value.writeln(`\r\n\x1b[90mSession ended with code ${code}\x1b[0m`)
        }
        connected.value = false
        execId.value = null

        // Fermer le WebSocket (onclose mettra ws = null)
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close(1000, `Session ended with code ${code}`)
        }

        onDisconnected?.(`Session ended with code ${code}`)
        break
      }

      case 'pong':
        // Heartbeat response
        break

      default:
        console.log('Unknown message type:', message.type)
    }
  }

  /**
   * Envoie des données d'entrée au terminal
   */
  function sendInput(data: string): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'input',
        data
      }))
    }
  }

  /**
   * Envoie les nouvelles dimensions du terminal
   */
  function sendResize(cols: number, rows: number): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'resize',
        cols,
        rows
      }))
    }
  }

  /**
   * Redimensionne le terminal
   */
  function resize(cols: number, rows: number): void {
    if (terminal.value) {
      const intCols = Math.max(1, Math.floor(cols))
      const intRows = Math.max(1, Math.floor(rows))
      terminal.value.resize(intCols, intRows)
      sendResize(intCols, intRows)
    }
  }

  /**
   * Déconnecte le WebSocket
   */
  function disconnect(): void {
    if (ws) {
      ws.close(1000, 'User disconnect')
      ws = null
    }
    connected.value = false
    connecting.value = false
    execId.value = null
  }

  /**
   * Efface le contenu du terminal
   */
  function clear(): void {
    if (terminal.value) {
      terminal.value.clear()
    }
  }

  /**
   * Copie le contenu du terminal vers le presse-papiers
   */
  async function copyOutput(): Promise<string> {
    if (!terminal.value) return ''

    let text = ''

    // Si une sélection est active, copier uniquement la sélection
    if (terminal.value.hasSelection()) {
      text = terminal.value.getSelection()
    } else {
      // Sinon, copier l'intégralité du buffer
      const buffer = terminal.value.buffer.active
      for (let i = 0; i < buffer.length; i++) {
        const line = buffer.getLine(i)
        if (line) {
          text += line.translateToString(true) + '\n'
        }
      }
      text = text.trim()
    }

    try {
      await navigator.clipboard.writeText(text)
    } catch (e) {
      console.error('Failed to copy:', e)
    }

    return text
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    terminal,
    connected,
    connecting,
    error,
    execId,
    activeShell,
    activeUser,
    connect,
    disconnect,
    sendInput,
    resize,
    clear,
    copyOutput
  }
}

/**
 * Options pour FitAddon avec xterm.js
 */
export interface FitAddonOptions {
  terminal?: Terminal
  cols?: number
  rows?: number
}

/**
 * Calcule les dimensions optimales pour le terminal
 * Basé sur l'implémentation de @xterm/addon-fit
 */
export function proposeDimensions(
  terminal: Terminal,
  options: FitAddonOptions = {}
): { cols: number; rows: number } | null {
  if (!terminal.element) {
    return null
  }

  const dims = {
    cols: options.cols || terminal.cols,
    rows: options.rows || terminal.rows
  }

  // Récupérer les dimensions du container
  const parent = terminal.element.parentElement
  if (!parent) {
    return dims
  }

  // Calculer en utilisant les dimensions du.CharWidth et CharHeight
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const terminalAny = terminal as any
  if (terminalAny._core?._renderService?._renderer?._cellSize) {
    const cellWidth = terminalAny._core._renderService._renderer._cellSize.width
    const cellHeight = terminalAny._core._renderService._renderer._cellSize.height

    if (cellWidth > 0 && cellHeight > 0) {
      const availableWidth = parent.clientWidth
      const availableHeight = parent.clientHeight

      // Soustraire les bordures et paddings
      const paddingLeft = parseInt(getComputedStyle(parent).paddingLeft) || 0
      const paddingRight = parseInt(getComputedStyle(parent).paddingRight) || 0
      const paddingTop = parseInt(getComputedStyle(parent).paddingTop) || 0
      const paddingBottom = parseInt(getComputedStyle(parent).paddingBottom) || 0

      const usableWidth = availableWidth - paddingLeft - paddingRight
      const usableHeight = availableHeight - paddingTop - paddingBottom

      dims.cols = Math.max(1, Math.floor(usableWidth / cellWidth))
      dims.rows = Math.max(1, Math.floor(usableHeight / cellHeight))
    }
  }

  return dims
}
