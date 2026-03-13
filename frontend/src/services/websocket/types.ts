/**
 * Types et interfaces pour le système WebSocket étendu avec plugins
 */

/**
 * Types d'événements WebSocket supportés.
 *
 * IMPORTANT: Ces types doivent correspondre exactement aux types définis
 * dans backend/app/schemas/websocket_events.py
 *
 * Organisés par catégorie pour faciliter la maintenance
 */
export enum WebSocketEventType {
  // ============================================================================
  // Authentification
  // ============================================================================
  AUTH_LOGIN_SUCCESS = 'AUTH_LOGIN_SUCCESS',
  AUTH_LOGOUT = 'AUTH_LOGOUT',
  AUTH_TOKEN_REFRESH = 'AUTH_TOKEN_REFRESH',

  // ============================================================================
  // Notifications
  // ============================================================================
  NOTIFICATION_SYSTEM = 'NOTIFICATION_SYSTEM',
  NOTIFICATION_USER = 'NOTIFICATION_USER',
  NOTIFICATION_DEPLOYMENT = 'NOTIFICATION_DEPLOYMENT',

  // ============================================================================
  // Session
  // ============================================================================
  SESSION_EXPIRED = 'SESSION_EXPIRED',
  SESSION_AUTH_REQUIRED = 'SESSION_AUTH_REQUIRED',
  SESSION_PERMISSION_CHANGED = 'SESSION_PERMISSION_CHANGED',
  SESSION_ORGANIZATION_CHANGED = 'SESSION_ORGANIZATION_CHANGED',

  // ============================================================================
  // UI Navigation (server-driven UI)
  // ============================================================================
  UI_NAVIGATION_REQUEST = 'UI_NAVIGATION_REQUEST',
  UI_MODAL_DISPLAY = 'UI_MODAL_DISPLAY',
  UI_TOAST_DISPLAY = 'UI_TOAST_DISPLAY',
  UI_WORKFLOW_STEP = 'UI_WORKFLOW_STEP',

  // ============================================================================
  // Déploiements
  // ============================================================================
  DEPLOYMENT_STATUS_CHANGED = 'DEPLOYMENT_STATUS_CHANGED',
  DEPLOYMENT_LOGS_UPDATE = 'DEPLOYMENT_LOGS_UPDATE',
  DEPLOYMENT_PROGRESS = 'DEPLOYMENT_PROGRESS',

  // ============================================================================
  // Système
  // ============================================================================
  SYSTEM_MAINTENANCE = 'SYSTEM_MAINTENANCE',
  SYSTEM_BROADCAST = 'SYSTEM_BROADCAST',

  // ============================================================================
  // Types système internes (ne passent pas par le système de plugins)
  // ============================================================================
  PONG = 'pong',
  ERROR = 'error',
  SUBSCRIBED = 'subscribed',
  UNSUBSCRIBED = 'unsubscribed',
  LOGS_SUBSCRIBED = 'logs_subscribed',
  MESSAGE_RECEIVED = 'message_received',
  TEXT_RECEIVED = 'text_received'
}

/**
 * Données pour les événements de notification
 */
export interface NotificationEvent {
  title: string
  message: string
  severity: 'info' | 'warning' | 'error' | 'success'
  duration?: number
  action?: {
    label: string
    handler: string
  }
}

/**
 * Requête de navigation pilotée par le serveur
 */
export interface UINavigationRequest {
  route: string
  params?: Record<string, any>
  query?: Record<string, any>
  replace?: boolean
  state?: any
}

/**
 * Affichage de modale piloté par le serveur
 */
export interface UIModalDisplay {
  component: string
  props?: Record<string, any>
  persistent?: boolean
}

/**
 * Toast/notification temporaire
 */
export interface UIToastDisplay {
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

/**
 * Étape de workflow guidé
 */
export interface UIWorkflowStep {
  stepId: string
  workflowId: string
  title: string
  description?: string
  required: boolean
  timeout?: number
  data?: Record<string, any>
}

/**
 * Événement de changement de session
 */
export interface SessionEvent {
  type: 'auth_required' | 'permission_changed' | 'organization_changed' | 'expired'
  message?: string
  redirectTo?: string
  data?: Record<string, any>
}

/**
 * Données pour les événements de déploiement
 */
export interface DeploymentStatusEvent {
  deploymentId: string
  deploymentName: string
  oldStatus: string
  newStatus: string
  timestamp: string
}

export interface DeploymentLogsEvent {
  deploymentId: string
  logs: string[]
  timestamp: string
}

export interface DeploymentProgressEvent {
  deploymentId: string
  progress: number
  step: string
  timestamp: string
}

/**
 * Données pour les événements d'authentification
 */
export interface AuthEvent {
  userId?: string
  message?: string
  timestamp?: string
}

/**
 * Données pour les événements système
 */
export interface SystemEvent {
  message: string
  scheduledAt?: string
  duration?: number
  timestamp?: string
}

/**
 * Données pour les événements de souscription
 */
export interface SubscriptionEvent {
  channel?: string
  topic?: string
  message?: string
}

/**
 * Mapping des types d'événements vers leurs données
 */
export interface EventDataMap {
  // Authentification
  [WebSocketEventType.AUTH_LOGIN_SUCCESS]: AuthEvent
  [WebSocketEventType.AUTH_LOGOUT]: AuthEvent
  [WebSocketEventType.AUTH_TOKEN_REFRESH]: AuthEvent

  // Notifications
  [WebSocketEventType.NOTIFICATION_SYSTEM]: NotificationEvent
  [WebSocketEventType.NOTIFICATION_USER]: NotificationEvent
  [WebSocketEventType.NOTIFICATION_DEPLOYMENT]: NotificationEvent

  // Session
  [WebSocketEventType.SESSION_AUTH_REQUIRED]: SessionEvent
  [WebSocketEventType.SESSION_PERMISSION_CHANGED]: SessionEvent
  [WebSocketEventType.SESSION_ORGANIZATION_CHANGED]: SessionEvent
  [WebSocketEventType.SESSION_EXPIRED]: SessionEvent

  // UI Navigation
  [WebSocketEventType.UI_NAVIGATION_REQUEST]: UINavigationRequest
  [WebSocketEventType.UI_MODAL_DISPLAY]: UIModalDisplay
  [WebSocketEventType.UI_TOAST_DISPLAY]: UIToastDisplay
  [WebSocketEventType.UI_WORKFLOW_STEP]: UIWorkflowStep

  // Déploiements
  [WebSocketEventType.DEPLOYMENT_STATUS_CHANGED]: DeploymentStatusEvent
  [WebSocketEventType.DEPLOYMENT_LOGS_UPDATE]: DeploymentLogsEvent
  [WebSocketEventType.DEPLOYMENT_PROGRESS]: DeploymentProgressEvent

  // Système
  [WebSocketEventType.SYSTEM_MAINTENANCE]: SystemEvent
  [WebSocketEventType.SYSTEM_BROADCAST]: SystemEvent

  // Types système internes
  [WebSocketEventType.PONG]: SubscriptionEvent
  [WebSocketEventType.ERROR]: { message: string; code?: string }
  [WebSocketEventType.SUBSCRIBED]: SubscriptionEvent
  [WebSocketEventType.UNSUBSCRIBED]: SubscriptionEvent
  [WebSocketEventType.LOGS_SUBSCRIBED]: SubscriptionEvent
  [WebSocketEventType.MESSAGE_RECEIVED]: SubscriptionEvent
  [WebSocketEventType.TEXT_RECEIVED]: SubscriptionEvent
}

/**
 * Message WebSocket générique
 */
export interface WebSocketMessage<T = any> {
  type: string
  data?: T
  timestamp?: string
}
