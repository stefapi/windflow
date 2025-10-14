/**
 * Composable pour gérer la connexion WebSocket aux logs de déploiement.
 *
 * Utilise le service WebSocket avec authentification pour recevoir les logs en temps réel.
 */

import { ref, onUnmounted, computed, Ref } from 'vue'
import wsService, { deploymentEvents } from '@/services/websocket'

export interface DeploymentLogMessage {
  type: 'log' | 'status' | 'error' | 'complete' | 'pong' | 'auth_success'
  timestamp: string
  message?: string
  level?: 'info' | 'warning' | 'error'
  data?: Record<string, unknown>
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

  const deploymentIdValue = computed(() =>
    typeof deploymentId === 'string' ? deploymentId : deploymentId.value
  )

  /**
   * Gestionnaire pour les messages de log de déploiement
   */
  const handleDeploymentMessage = (data: unknown) => {
    const message = data as DeploymentLogMessage

    // Traiter selon le type de message
    switch (message.type) {
      case 'log':
        logs.value.push(message)
        break

      case 'status':
        if (message.data?.['status']) {
          currentStatus.value = message.data['status'] as string
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

      case 'auth_success':
        console.log('🔐 WebSocket authentication successful for deployment logs')
        connected.value = true
        connecting.value = false
        onConnect?.()
        break

      case 'pong':
        // Heartbeat response - ne rien faire
        break
    }
  }

  /**
   * Connecte aux logs de déploiement avec authentification
   */
  function connect() {
    if (connecting.value || connected.value) {
      return
    }

    connecting.value = true
    error.value = null

    console.log('🔗 Connecting to deployment logs with authentication...')

    // S'assurer que le WebSocket est connecté avec authentification
    if (!wsService.isConnected()) {
      wsService.connectWithAuth()
    }

    // S'abonner aux logs du déploiement spécifique
    if (deploymentIdValue.value) {
      console.log('📋 Subscribing to deployment logs:', deploymentIdValue.value)
      deploymentEvents.subscribeToDeployment(deploymentIdValue.value, handleDeploymentMessage)
    }
  }

  /**
   * Déconnecte des logs de déploiement
   */
  function disconnect() {
    console.log('🔌 Disconnecting from deployment logs')

    if (deploymentIdValue.value) {
      // Se désabonner des logs du déploiement
      deploymentEvents.subscribeToDeployment(deploymentIdValue.value, handleDeploymentMessage)()
    }

    connected.value = false
    connecting.value = false
    error.value = null
  }

  /**
   * Efface tous les logs
   */
  function clearLogs() {
    logs.value = []
    error.value = null
  }

  /**
   * Récupère les logs d'un certain niveau
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
   * Indique si le déploiement est terminé
   */
  const isComplete = computed(() => {
    return logs.value.some(log => log.type === 'complete')
  })

  /**
   * Indique si le déploiement a réussi
   */
  const isSuccess = computed(() => {
    const completeLog = logs.value.find(log => log.type === 'complete')
    return completeLog?.data?.['success'] === true
  })

  /**
   * Récupère le dernier message de log
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
