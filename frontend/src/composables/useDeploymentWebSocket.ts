/**
 * Composable pour gérer les événements WebSocket de déploiement en temps réel
 *
 * Fonctionnalités :
 * - Suivi du statut de déploiement en temps réel
 * - Streaming des logs de déploiement
 * - Barre de progression en temps réel
 * - Reconnexion automatique
 *
 * Usage :
 * const { status, logs, progress, isConnected } = useDeploymentWebSocket(deploymentId)
 */

import { ref, onMounted, onUnmounted, computed, type Ref } from 'vue'
import wsService from '@/services/websocket'
import { WebSocketEventType } from '@/services/websocket/types'
import { deploymentsApi } from '@/services/api'
import type {
  DeploymentStatusChangedEvent,
  DeploymentLogsUpdateEvent,
  DeploymentProgressEvent
} from '@/types/websocket'
import type { DeploymentStatus } from '@/types/api'

export interface DeploymentWebSocketState {
  status: Ref<DeploymentStatus | null>
  logs: Ref<string[]>
  progress: Ref<number>
  currentStep: Ref<string>
  totalSteps: Ref<number>
  errorMessage: Ref<string | null>
  isConnected: Ref<boolean>
  lastUpdate: Ref<Date | null>
}

export interface DeploymentWebSocketOptions {
  /**
   * Se connecter automatiquement au montage du composable
   * @default true
   */
  autoConnect?: boolean

  /**
   * Nombre maximum de lignes de logs à garder en mémoire
   * @default 1000
   */
  maxLogsLines?: number

  /**
   * Activer le mode debug
   * @default false
   */
  debug?: boolean
}

/**
 * Composable pour gérer les événements WebSocket de déploiement
 */
export function useDeploymentWebSocket(
  deploymentId: string | Ref<string>,
  options: DeploymentWebSocketOptions = {}
): DeploymentWebSocketState & {
  connect: () => void
  disconnect: () => void
  clearLogs: () => void
} {
  const {
    autoConnect = true,
    maxLogsLines = 1000,
    debug = false
  } = options

  // État réactif
  const status = ref<DeploymentStatus | null>(null)
  const logs = ref<string[]>([])
  const progress = ref<number>(0)
  const currentStep = ref<string>('')
  const totalSteps = ref<number>(100)
  const errorMessage = ref<string | null>(null)
  const isConnected = ref<boolean>(false)
  const lastUpdate = ref<Date | null>(null)

  // Fonction helper pour logger en mode debug
  const logDebug = (...args: any[]) => {
    if (debug) {
      console.log('[useDeploymentWebSocket]', ...args)
    }
  }

  // Récupérer l'ID de déploiement (peut être une ref ou une string)
  const getDeploymentId = (): string => {
    return typeof deploymentId === 'string' ? deploymentId : deploymentId.value
  }

  // Fonctions de nettoyage des événements
  let unsubscribeStatus: (() => void) | null = null
  let unsubscribeLogs: (() => void) | null = null
  let unsubscribeProgress: (() => void) | null = null

  /**
   * Gestionnaire d'événement de changement de statut
   */
  const handleStatusChange = (data: unknown) => {
    const event = data as DeploymentStatusChangedEvent

    logDebug('Status changed event:', event)

    // Vérifier que l'événement concerne notre déploiement
    if (event.deployment_id === getDeploymentId()) {
      status.value = event.new_status

      // Mettre à jour le message d'erreur si présent
      if (event.error_message) {
        errorMessage.value = event.error_message
      }

      lastUpdate.value = new Date()

      logDebug('Status updated to:', event.new_status)
    }
  }

  /**
   * Gestionnaire d'événement de mise à jour des logs
   */
  const handleLogsUpdate = (data: unknown) => {
    const event = data as DeploymentLogsUpdateEvent

    logDebug('Logs update event:', event)

    // Vérifier que l'événement concerne notre déploiement
    if (event.deployment_id === getDeploymentId()) {
      if (event.append) {
        // Ajouter les nouveaux logs
        const newLines = event.logs.split('\n').filter(line => line.trim())
        logs.value.push(...newLines)

        // Limiter le nombre de lignes en mémoire
        if (logs.value.length > maxLogsLines) {
          logs.value = logs.value.slice(-maxLogsLines)
        }
      } else {
        // Remplacer tous les logs
        logs.value = event.logs.split('\n').filter(line => line.trim())
      }

      lastUpdate.value = new Date()

      logDebug('Logs updated, total lines:', logs.value.length)
    }
  }

  /**
   * Gestionnaire d'événement de progression
   */
  const handleProgress = (data: unknown) => {
    const event = data as DeploymentProgressEvent

    logDebug('Progress event:', event)

    // Vérifier que l'événement concerne notre déploiement
    if (event.deployment_id === getDeploymentId()) {
      progress.value = event.progress
      currentStep.value = event.current_step
      totalSteps.value = event.total_steps
      lastUpdate.value = new Date()

      logDebug('Progress updated:', {
        progress: event.progress,
        step: event.current_step
      })
    }
  }

  /**
   * Charger les logs initiaux depuis l'API REST
   */
  const loadInitialLogs = async () => {
    try {
      logDebug('Loading initial logs from API...')
      const response = await deploymentsApi.get(getDeploymentId())
      const deployment = response.data
      logDebug('Deployment data received:', deployment)

      // Initialiser le statut
      if (deployment.status) {
        status.value = deployment.status
        logDebug('Status initialized:', deployment.status)
      }

      // Initialiser les logs si présents
      if (deployment.logs) {
        logDebug('Raw logs length:', deployment.logs.length)
        const logLines = deployment.logs.split('\n').filter(line => line.trim())
        logs.value = logLines
        logDebug('Initial logs loaded:', logLines.length, 'lines')
      } else {
        logDebug('No logs in deployment object')
      }

      // Initialiser le message d'erreur si présent
      if (deployment.error_message) {
        errorMessage.value = deployment.error_message
      }

      lastUpdate.value = new Date()
    } catch (error) {
      logDebug('Error loading initial logs:', error)
      // Ne pas bloquer la connexion WebSocket en cas d'erreur
    }
  }

  /**
   * Se connecter aux événements WebSocket
   */
  const connect = async () => {
    logDebug('Connecting to WebSocket for deployment:', getDeploymentId())

    // Charger les logs initiaux avant de se connecter au WebSocket
    await loadInitialLogs()

    // S'assurer que le service WebSocket est connecté
    if (!wsService.isConnected()) {
      logDebug('WebSocket not connected, connecting with auth...')
      wsService.connectWithAuth()
    }

    // S'abonner aux événements de statut
    unsubscribeStatus = wsService.on(
      WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
      handleStatusChange
    )

    // S'abonner aux événements de logs
    unsubscribeLogs = wsService.on(
      WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
      handleLogsUpdate
    )

    // S'abonner aux événements de progression
    unsubscribeProgress = wsService.on(
      WebSocketEventType.DEPLOYMENT_PROGRESS,
      handleProgress
    )

    // Envoyer une demande d'abonnement au serveur pour ce déploiement
    wsService.send('deployment_logs', {
      deployment_id: getDeploymentId()
    })

    isConnected.value = true
    logDebug('Successfully subscribed to deployment events')
  }

  /**
   * Se déconnecter des événements WebSocket
   */
  const disconnect = () => {
    logDebug('Disconnecting from WebSocket events')

    // Se désabonner des événements
    if (unsubscribeStatus) {
      unsubscribeStatus()
      unsubscribeStatus = null
    }

    if (unsubscribeLogs) {
      unsubscribeLogs()
      unsubscribeLogs = null
    }

    if (unsubscribeProgress) {
      unsubscribeProgress()
      unsubscribeProgress = null
    }

    // Envoyer une demande de désabonnement au serveur
    if (wsService.isConnected()) {
      wsService.send('unsubscribe', {
        event_type: 'deployment',
        deployment_id: getDeploymentId()
      })
    }

    isConnected.value = false
    logDebug('Successfully unsubscribed from deployment events')
  }

  /**
   * Nettoyer les logs
   */
  const clearLogs = () => {
    logs.value = []
    logDebug('Logs cleared')
  }

  // Connexion automatique au montage du composable
  onMounted(() => {
    if (autoConnect) {
      logDebug('Auto-connecting on mount')
      connect()
    }
  })

  // Déconnexion lors du démontage du composable
  onUnmounted(() => {
    logDebug('Unmounting, disconnecting...')
    disconnect()
  })

  return {
    // État réactif
    status,
    logs,
    progress,
    currentStep,
    totalSteps,
    errorMessage,
    isConnected,
    lastUpdate,

    // Méthodes
    connect,
    disconnect,
    clearLogs
  }
}

/**
 * Composable simplifié pour surveiller plusieurs déploiements
 * Utile pour les vues de liste
 */
export function useDeploymentStatusMonitor() {
  const deploymentStatuses = ref<Map<string, DeploymentStatus>>(new Map())
  let unsubscribe: (() => void) | null = null

  const connect = () => {
    if (!wsService.isConnected()) {
      wsService.connectWithAuth()
    }

    // S'abonner à tous les changements de statut
    unsubscribe = wsService.on(
      WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
      (data: unknown) => {
        const event = data as DeploymentStatusChangedEvent
        deploymentStatuses.value.set(event.deployment_id, event.new_status)
      }
    )
  }

  const disconnect = () => {
    if (unsubscribe) {
      unsubscribe()
      unsubscribe = null
    }
  }

  const getStatus = (deploymentId: string): DeploymentStatus | undefined => {
    return deploymentStatuses.value.get(deploymentId)
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return {
    deploymentStatuses: computed(() => deploymentStatuses.value),
    getStatus
  }
}
