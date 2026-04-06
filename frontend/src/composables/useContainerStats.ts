/**
 * useContainerStats Composable
 * Handles WebSocket connection for real-time container stats streaming
 */

import { ref, computed, onUnmounted, watch, type Ref, type ComputedRef } from 'vue'
import { useAuthStore } from '@/stores'

export type StatsStreamStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface NetworkInterfaceData {
  name: string
  rx_bytes: number
  tx_bytes: number
  rx_packets: number
  tx_packets: number
  rx_errors: number
  tx_errors: number
  rx_dropped: number
  tx_dropped: number
}

export interface BlkioDeviceData {
  major: number
  minor: number
  read_bytes: number
  write_bytes: number
  read_ops: number
  write_ops: number
}

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
  // Enriched network data (STORY-029.2)
  network_interfaces: NetworkInterfaceData[]
  total_rx_errors: number
  total_tx_errors: number
  total_rx_dropped: number
  total_tx_dropped: number
  // Enriched block I/O data (STORY-029.2)
  blkio_devices: BlkioDeviceData[]
  // Calculated rates (bytes/s)
  network_rx_rate: number
  network_tx_rate: number
  block_read_rate: number
  block_write_rate: number
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
  fetchOnce: () => void
  clearHistory: () => void
}

// History entry for sparkline charts (last 5 minutes)
export interface StatsHistoryEntry {
  cpu_percent: number
  memory_percent: number
  memory_used: number
  network_rx_bytes: number
  network_tx_bytes: number
  block_read_bytes: number
  block_write_bytes: number
  // Calculated rates (bytes/s)
  network_rx_rate: number
  network_tx_rate: number
  block_read_rate: number
  block_write_rate: number
  timestamp: number
}

const MAX_HISTORY_LENGTH = 60 // 60 entries at 5 second intervals = 5 minutes

// WebSocket base URL - constructed from current location to use Vite proxy in dev
const getWebSocketBaseUrl = (): string => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}`
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function parseNetworkInterfaces(raw: any[]): NetworkInterfaceData[] {
  return raw.map((iface) => ({
    name: String(iface['name'] ?? ''),
    rx_bytes: Number(iface['rx_bytes'] ?? 0),
    tx_bytes: Number(iface['tx_bytes'] ?? 0),
    rx_packets: Number(iface['rx_packets'] ?? 0),
    tx_packets: Number(iface['tx_packets'] ?? 0),
    rx_errors: Number(iface['rx_errors'] ?? 0),
    tx_errors: Number(iface['tx_errors'] ?? 0),
    rx_dropped: Number(iface['rx_dropped'] ?? 0),
    tx_dropped: Number(iface['tx_dropped'] ?? 0),
  }))
}

function parseBlkioDevices(raw: any[]): BlkioDeviceData[] {
  return raw.map((dev) => ({
    major: Number(dev['major'] ?? 0),
    minor: Number(dev['minor'] ?? 0),
    read_bytes: Number(dev['read_bytes'] ?? 0),
    write_bytes: Number(dev['write_bytes'] ?? 0),
    read_ops: Number(dev['read_ops'] ?? 0),
    write_ops: Number(dev['write_ops'] ?? 0),
  }))
}
/* eslint-enable @typescript-eslint/no-explicit-any */

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

  // Manual mode flag - when true, disconnect after receiving stats
  let manualMode = false

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
              const now = Date.now()
              const previousStats = stats.value

              // Calculate rates (bytes/s) by delta with previous sample
              let networkRxRate = 0
              let networkTxRate = 0
              let blockReadRate = 0
              let blockWriteRate = 0

              if (previousStats) {
                const prevTime = new Date(previousStats.timestamp).getTime()
                const deltaTimeMs = now - prevTime
                if (deltaTimeMs > 0) {
                  const deltaSeconds = deltaTimeMs / 1000
                  const newRx = data.network?.rx_bytes ?? 0
                  const newTx = data.network?.tx_bytes ?? 0
                  const newRead = data.block_io?.read_bytes ?? 0
                  const newWrite = data.block_io?.write_bytes ?? 0
                  networkRxRate = Math.max(0, (newRx - previousStats.network_rx_bytes) / deltaSeconds)
                  networkTxRate = Math.max(0, (newTx - previousStats.network_tx_bytes) / deltaSeconds)
                  blockReadRate = Math.max(0, (newRead - previousStats.block_read_bytes) / deltaSeconds)
                  blockWriteRate = Math.max(0, (newWrite - previousStats.block_write_bytes) / deltaSeconds)
                }
              }

              // Parse enriched data from backend (STORY-029.1)
              const networkInterfaces = parseNetworkInterfaces(data.network?.interfaces ?? [])
              const blkioDevices = parseBlkioDevices(data.block_io?.devices ?? [])

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
                // Enriched network data
                network_interfaces: networkInterfaces,
                total_rx_errors: data.network?.total_rx_errors ?? 0,
                total_tx_errors: data.network?.total_tx_errors ?? 0,
                total_rx_dropped: data.network?.total_rx_dropped ?? 0,
                total_tx_dropped: data.network?.total_tx_dropped ?? 0,
                // Enriched block I/O data
                blkio_devices: blkioDevices,
                // Calculated rates
                network_rx_rate: networkRxRate,
                network_tx_rate: networkTxRate,
                block_read_rate: blockReadRate,
                block_write_rate: blockWriteRate,
              }

              // Update stats
              stats.value = newStats

              // Add to history for sparklines
              addStatsToHistory(newStats, now)

              // In manual mode, disconnect after receiving stats
              if (manualMode) {
                manualMode = false
                disconnect()
              }
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
   * Fetch stats once (manual mode)
   * Connects, waits for one stats update, then disconnects
   */
  function fetchOnce(): void {
    manualMode = true
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
  function addStatsToHistory(newStats: ContainerStats, timestampMs?: number): void {
    history.value.push({
      cpu_percent: newStats.cpu_percent,
      memory_percent: newStats.memory_percent,
      memory_used: newStats.memory_used,
      network_rx_bytes: newStats.network_rx_bytes,
      network_tx_bytes: newStats.network_tx_bytes,
      block_read_bytes: newStats.block_read_bytes,
      block_write_bytes: newStats.block_write_bytes,
      // Calculated rates
      network_rx_rate: newStats.network_rx_rate,
      network_tx_rate: newStats.network_tx_rate,
      block_read_rate: newStats.block_read_rate,
      block_write_rate: newStats.block_write_rate,
      timestamp: timestampMs ?? Date.now(),
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
    fetchOnce,
    clearHistory,
  }
}
