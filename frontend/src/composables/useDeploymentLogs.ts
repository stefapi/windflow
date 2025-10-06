/**
 * Composable pour gérer la connexion WebSocket aux logs de déploiement.
 *
 * Gère la connexion, reconnexion automatique, et réception des logs en temps réel.
 */

import { ref, onUnmounted, computed, Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

export interface DeploymentLogMessage {
  type: 'log' | 'status' | 'error' | 'complete' | 'pong'
  timestamp: string
  message?: string
  level?: 'info' | 'warning' | 'error'
  data?: Record<string, any>
}

export interface DeploymentLogsOptions {
  autoConnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
}

export function useDeploymentLogs(
  deploymentId: Ref<string> | string,
  options: DeploymentLogsOptions = {}
) {
  const {
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    onConnect,
    onDisconnect,
    onError
  } = options

  // État
  const logs = ref<DeploymentLogMessage[]>([])
  const connected = ref(false)
  const connecting = ref(false)
  const currentStatus = ref<string>('')
  const error = ref<string | null>(null)

  // WebSocket
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null

  const deploymentIdValue = computed(() =>
    typeof deploymentId === 'string' ? deploymentId : deploymentId.value
  )

  /**
   * Construit l'URL WebSocket avec le token d'authentification.
   */
  function getWebSocketUrl(): string {
    const authStore = useAuthStore()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const apiUrl = import.meta.env['VITE_API_BASE_URL'] || `${protocol}//${host}`

    // Normaliser l'URL
    const wsUrl = apiUrl.replace(/^http/, 'ws').replace(/\/$/, '')

    // Ajouter le token JWT comme query parameter
    const token = authStore.token
    const url = `${wsUrl}/api/v1/ws/deployments/${deploymentIdValue.value}/logs`

    return token ? `${url}?token=${token}` : url
  }

  /**
   * Démarre le heartbeat pour maintenir la connexion.
   */
  function startHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
    }

    heartbeatInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000) // Ping toutes les 30 secondes
  }

  /**
   * Arrête le heartbeat.
   */
  function stopHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }

  /**
   * Connecte au WebSocket.
   */
  function connect() {
    if (connecting.value || connected.value) {
      return
    }

    connecting.value = true
    error.value = null

    try {
      const url = getWebSocketUrl()
      ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WebSocket] Connected to deployment logs')
        connected.value = true
        connecting.value = false
        reconnectAttempts = 0
        startHeartbeat()

        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const message: DeploymentLogMessage = JSON.parse(event.data)

          // Traiter selon le type de message
          switch (message.type) {
            case 'log':
              logs.value.push(message)
              break

            case 'status':
              if (message.data?.['status']) {
                currentStatus.value = message.data['status']
              }
              logs.value.push(message)
              break

            case 'error':
              error.value = message.message || 'Erreur WebSocket'
              logs.value.push(message)
              break

            case 'complete':
              logs.value.push(message)
              break

            case 'pong':
              // Heartbeat response - ne rien faire
              break
          }
        } catch (err) {
          console.error('[WebSocket] Error parsing message:', err)
        }
      }

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event)
        error.value = 'Erreur de connexion WebSocket'
        onError?.(event)
      }

      ws.onclose = (event) => {
        console.log('[WebSocket] Closed:', event.code, event.reason)
        connected.value = false
        connecting.value = false
        stopHeartbeat()

        onDisconnect?.()

        // Reconnexion automatique si non intentionnelle
        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++
          console.log(`[WebSocket] Reconnecting... (attempt ${reconnectAttempts}/${maxReconnectAttempts})`)

          reconnectTimeout = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }
    } catch (err) {
      console.error('[WebSocket] Connection error:', err)
      error.value = 'Impossible de se connecter au WebSocket'
      connecting.value = false
    }
  }

  /**
   * Déconnecte du WebSocket.
   */
  function disconnect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    stopHeartbeat()

    if (ws) {
      ws.close(1000, 'Client disconnect')
      ws = null
    }

    connected.value = false
    connecting.value = false
    reconnectAttempts = maxReconnectAttempts // Empêcher la reconnexion
  }

  /**
   * Efface tous les logs.
   */
  function clearLogs() {
    logs.value = []
    error.value = null
  }

  /**
   * Récupère les logs d'un certain niveau.
   */
  const logsByLevel = computed(() => {
    return {
      all: logs.value,
      info: logs.value.filter(log => log.level === 'info' || log.type === 'status'),
      warnings: logs.value.filter(log => log.level === 'warning'),
      errors: logs.value.filter(log => log.level === 'error' || log.type === 'error')
    }
  })

  /**
   * Indique si le déploiement est terminé.
   */
  const isComplete = computed(() => {
    return logs.value.some(log => log.type === 'complete')
  })

  /**
   * Indique si le déploiement a réussi.
   */
  const isSuccess = computed(() => {
    const completeLog = logs.value.find(log => log.type === 'complete')
    return completeLog?.data?.['success'] === true
  })

  /**
   * Récupère le dernier message de log.
   */
  const lastLog = computed(() => {
    return logs.value[logs.value.length - 1] || null
  })

  // Auto-connect si activé
  if (autoConnect && deploymentIdValue.value) {
    connect()
  }

  // Cleanup à la destruction
  onUnmounted(() => {
    disconnect()
  })

  return {
    // État
    logs,
    connected,
    connecting,
    currentStatus,
    error,

    // Computed
    logsByLevel,
    isComplete,
    isSuccess,
    lastLog,

    // Actions
    connect,
    disconnect,
    clearLogs
  }
}
