/**
 * useContainerStats Composable
 * Handles WebSocket connection for real-time container stats streaming
 */

import { ref, computed, onUnmounted, watch, type Ref, type ComputedRef } from 'vue'
import { useAuthStore } from '@/stores'

export type StatsStreamStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface ContainerStats {
  cpu_percent: number
  memory_percent: number
  memory_used: number
  memory_limit: number
  network_rx_bytes: number
  network_tx_bytes: number
  block_read_bytes: number
  block_write_bytes: number
  timestamp: string
}

export interface UseContainerStatsOptions {
  containerId: string
  autoConnect?: boolean
}

export interface UseContainerStatsReturn {
  stats: Ref<ContainerStats | null>
  status: Ref<StatsStreamStatus>
  error: Ref<string | null>
  isStreaming: ComputedRef<boolean>
  history: Ref<StatsHistoryEntry[]>
  connect: () => void
  disconnect: () => void
  reconnect: () => void
  clearHistory: () => void
}

// History entry for sparkline charts (last 5 minutes)
export interface StatsHistoryEntry {
  cpu_percent: number
  memory_percent: number
  memory_used: number
  timestamp: number
}

const MAX_HISTORY_LENGTH = 60 // 60 entries at 5 second intervals = 5 minutes

// WebSocket base URL - constructed from current location to use Vite proxy in dev
const getWebSocketBaseUrl = (): string => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}`
}

export function useContainerStats(options: UseContainerStatsOptions): UseContainerStatsReturn {
  const { containerId, autoConnect = true } = options

  // State
  const stats = ref<ContainerStats | null>(null)
  const status = ref<StatsStreamStatus>('disconnected')
  const error = ref<string | null>(null)

  // History for sparklines (last 5 minutes)
  const history = ref<StatsHistoryEntry[]>([])

  // WebSocket instance
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5
  const reconnectDelay = 2000

  // Heartbeat interval
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null

  // Auth token
  const token = computed(() => useAuthStore().token)
  const isStreaming = computed(() => status.value === 'connected')

  /**
   * Build WebSocket URL with authentication
   */
  const buildUrl = (): string => {
    const baseUrl = getWebSocketBaseUrl()
    const wsToken = token.value
    return `${baseUrl}/api/v1/ws/docker/containers/${containerId}/stats?token=${wsToken}`
  }

  /**
   * Connect to WebSocket
   */
  function connect(): void {
    if (!token.value) {
      error.value = 'Authentication required'
      status.value = 'error'
      return
    }

    status.value = 'connecting'
    error.value = null

    try {
      ws = new WebSocket(buildUrl())

      ws.onopen = () => {
        status.value = 'connected'
        reconnectAttempts = 0
        console.log(`[ContainerStats] Connected to container ${containerId}`)
        startHeartbeat()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          switch (data.type) {
            case 'initial':
              // Initial state info - check if container is running
              if (data.container_status && data.container_status !== 'running') {
                // Container not running, stop streaming
                disconnect()
                return
              }
              break

            case 'stats': {
              // Real-time stats update
              const newStats: ContainerStats = {
                cpu_percent: data.cpu?.percent ?? 0,
                memory_percent: data.memory?.percent ?? 0,
                memory_used: data.memory?.used ?? 0,
                memory_limit: data.memory?.limit ?? 1,
                network_rx_bytes: data.network?.rx_bytes ?? 0,
                network_tx_bytes: data.network?.tx_bytes ?? 0,
                block_read_bytes: data.block_io?.read_bytes ?? 0,
                block_write_bytes: data.block_io?.write_bytes ?? 0,
                timestamp: data.timestamp,
              }

              // Update stats
              stats.value = newStats

              // Add to history for sparklines
              addStatsToHistory(newStats)
              break
            }

            case 'error':
              error.value = data.message
              status.value = 'error'
              break

            case 'stream_status':
              if (data.status === 'container_stopped') {
                // Container stopped, stop streaming
                disconnect()
              }
              break
          }
        } catch (e) {
          console.error('[ContainerStats] Error parsing message:', e)
        }
      }

      ws.onerror = (event) => {
        console.error(`[ContainerStats] WebSocket error:`, event)
        error.value = 'WebSocket error'
        status.value = 'error'

        // Attempt reconnection
        if (reconnectAttempts < maxReconnectAttempts) {
          setTimeout(() => {
            reconnectAttempts++
            connect()
          }, reconnectDelay)
        }
      }

      ws.onclose = (event) => {
        console.log(`[ContainerStats] Connection closed:`, event)
        if (status.value === 'connected') {
          status.value = 'disconnected'
          stopHeartbeat()
        }
      }
    } catch {
      error.value = 'Failed to connect'
      status.value = 'error'
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
    stopHeartbeat()
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
   * Clear stats history
   */
  function clearHistory(): void {
    history.value = []
  }

  /**
   * Add stats to history for sparklines
   */
  function addStatsToHistory(newStats: ContainerStats): void {
    history.value.push({
      cpu_percent: newStats.cpu_percent,
      memory_percent: newStats.memory_percent,
      memory_used: newStats.memory_used,
      timestamp: Date.now(),
    })

    // Keep only last 60 entries (5 minutes at 5 second intervals)
    while (history.value.length > MAX_HISTORY_LENGTH) {
      history.value.shift()
    }
  }

  /**
   * Start heartbeat to keep connection alive
   */
  function startHeartbeat(): void {
    heartbeatInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  /**
   * Stop heartbeat
   */
  function stopHeartbeat(): void {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }

  // Watch for token changes
  watch(token, (newToken) => {
    if (newToken && autoConnect && status.value === 'disconnected') {
      connect()
    } else if (!newToken) {
      disconnect()
    }
  })

  // Auto-connect if enabled
  if (autoConnect && token.value) {
    connect()
  }

  // Cleanup on unmount
  onUnmounted(() => {
    stopHeartbeat()
    disconnect()
  })

  return {
    stats,
    status,
    error,
    isStreaming,
    history,
    connect,
    disconnect,
    reconnect,
    clearHistory,
  }
}
