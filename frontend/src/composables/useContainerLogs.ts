/**
 * useContainerLogs Composable
 * Handles WebSocket connection for real-time container logs streaming
 */

import { ref, computed, onUnmounted, watch, unref, type Ref, type ComputedRef } from 'vue'
import { useAuthStore } from '@/stores'

export type LogStreamStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface UseContainerLogsOptions {
  containerId: string
  tail?: number | Ref<number>
  autoConnect?: boolean
}

export interface UseContainerLogsReturn {
  logs: Ref<string>
  status: Ref<LogStreamStatus>
  error: Ref<string | null>
  isStreaming: ComputedRef<boolean>
  connect: () => void
  disconnect: () => void
  reconnect: () => void
  clearLogs: () => void
  downloadLogs: (filename?: string) => void
}

// WebSocket base URL - constructed from current location to use Vite proxy in dev
const getWebSocketBaseUrl = (): string => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}`
}

export function useContainerLogs(options: UseContainerLogsOptions): UseContainerLogsReturn {
  const { containerId, tail = 100, autoConnect = true } = options

  // State
  const logs = ref<string>('')
  const status = ref<LogStreamStatus>('disconnected')
  const error = ref<string | null>(null)

  // WebSocket instance
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5
  const reconnectDelay = 2000

  // Internal line buffer for efficient trimming
  let lineBuffer: string[] = []

  /**
   * Get the current max lines limit from the (possibly reactive) tail option.
   */
  function getMaxLines(): number {
    return unref(tail)
  }

  /**
   * Trim the line buffer to the configured max lines and sync to the reactive `logs` ref.
   */
  function trimAndSync(): void {
    const max = getMaxLines()
    if (lineBuffer.length > max) {
      lineBuffer = lineBuffer.slice(lineBuffer.length - max)
    }
    logs.value = lineBuffer.join('\n')
  }

  // Track if component is still mounted
  let isMounted = false

  // Computed
  const isStreaming = computed(() => status.value === 'connected')

  // Get auth token
  const authStore = useAuthStore()
  const token = computed(() => authStore.token)

  /**
   * Build WebSocket URL with authentication
   */
  function buildWsUrl(): string | null {
    if (!token.value) {
      error.value = 'Authentication required'
      return null
    }
    const baseUrl = getWebSocketBaseUrl()
    const tailValue = unref(tail)
    return `${baseUrl}/api/v1/ws/docker/containers/${containerId}/logs?token=${encodeURIComponent(token.value)}&tail=${tailValue}`
  }

  /**
   * Connect to WebSocket and start streaming logs
   */
  function connect(): void {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    const url = buildWsUrl()
    if (!url) {
      return
    }

    status.value = 'connecting'
    error.value = null

    try {
      ws = new WebSocket(url)

      ws.onopen = () => {
        status.value = 'connected'
        reconnectAttempts = 0
        console.log(`[ContainerLogs] Connected to container ${containerId}`)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          switch (data.type) {
            case 'initial':
              // Initial logs from server — populate buffer and trim
              if (data.logs) {
                lineBuffer = data.logs.split('\n')
                trimAndSync()
              }
              break

            case 'log':
              // Real-time log entry — append to buffer and trim to max lines
              if (data.data) {
                lineBuffer.push(data.data)
                trimAndSync()
              }
              break

            case 'stream_status':
              // Stream status updates from server
              console.log(`[ContainerLogs] Stream status: ${data.status} - ${data.message}`)
              if (data.status === 'container_stopped' || data.status === 'ended') {
                // Container stopped or stream ended - update status but don't disconnect
                // The server will handle cleanup
                console.log(`[ContainerLogs] Stream ended: ${data.message}`)
              }
              break

            case 'pong':
              // Heartbeat response - ignore
              break

            case 'ping':
              // Server heartbeat - respond with pong
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('pong')
              }
              break

            case 'error':
              error.value = data.message || 'WebSocket error'
              status.value = 'error'
              break
          }
        } catch (e) {
          console.error('[ContainerLogs] Failed to parse message:', e)
        }
      }

      ws.onerror = (event) => {
        console.error('[ContainerLogs] WebSocket error:', event)
        status.value = 'error'
        error.value = 'Connection error'
      }

      ws.onclose = (event) => {
        console.log(`[ContainerLogs] Connection closed: code=${event.code}, reason=${event.reason}`)
        status.value = 'disconnected'

        // Attempt reconnect if not closed intentionally and component is still mounted
        if (isMounted && event.code !== 1000 && event.code !== 1008 && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++
          console.log(`[ContainerLogs] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttempts}/${maxReconnectAttempts})`)
          setTimeout(connect, reconnectDelay)
        }
      }
    } catch (e) {
      status.value = 'error'
      error.value = e instanceof Error ? e.message : 'Failed to connect'
    }
  }

  /**
   * Disconnect WebSocket
   */
  function disconnect(): void {
    if (ws) {
      ws.close(1000, 'User disconnected')
      ws = null
    }
    status.value = 'disconnected'
  }

  /**
   * Reconnect to WebSocket
   */
  function reconnect(): void {
    disconnect()
    reconnectAttempts = 0
    connect()
  }

  /**
   * Clear logs buffer
   */
  function clearLogs(): void {
    lineBuffer = []
    logs.value = ''
  }

  /**
   * Download logs as text file
   */
  function downloadLogs(filename?: string): void {
    if (!logs.value) {
      return
    }

    const defaultFilename = `container-${containerId.substring(0, 12)}-logs-${new Date().toISOString().split('T')[0]}.txt`
    const finalFilename = filename || defaultFilename

    const blob = new Blob([logs.value], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = url
    link.download = finalFilename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  /**
   * Send heartbeat to keep connection alive
   */
  function sendHeartbeat(): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }

  // Setup heartbeat interval
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null

  function startHeartbeat(): void {
    if (heartbeatInterval) return
    heartbeatInterval = setInterval(sendHeartbeat, 30000) // Every 30 seconds
  }

  function stopHeartbeat(): void {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }

  // Watch for status changes to start/stop heartbeat
  watch(status, (newStatus) => {
    if (newStatus === 'connected') {
      startHeartbeat()
    } else {
      stopHeartbeat()
    }
  })

  // Mark as mounted and auto-connect if enabled
  isMounted = true
  if (autoConnect && token.value) {
    connect()
  }

  // Watch for token changes
  watch(token, (newToken) => {
    if (newToken && autoConnect && status.value === 'disconnected') {
      connect()
    } else if (!newToken) {
      disconnect()
    }
  })

  // Cleanup on unmount
  onUnmounted(() => {
    isMounted = false
    stopHeartbeat()
    disconnect()
  })

  return {
    logs,
    status,
    error,
    isStreaming,
    connect,
    disconnect,
    reconnect,
    clearLogs,
    downloadLogs,
  }
}
