/**
 * Types et interfaces pour le système WebSocket étendu avec plugins
 */

/**
 * Types d'événements WebSocket supportés
 * Organisés par catégorie pour faciliter la maintenance
 */
export enum WebSocketEventType {
  // Authentification
  AUTH_SUCCESS = 'auth_success',
  AUTH_ERROR = 'auth_error',

  // Notifications
  NOTIFICATION_SYSTEM = 'notification:system',
  NOTIFICATION_USER = 'notification:user',

  // Session utilisateur
  SESSION_AUTH_REQUIRED = 'session:auth_required',
  SESSION_PERMISSION_CHANGED = 'session:permission_changed',
  SESSION_ORGANIZATION_CHANGED = 'session:organization_changed',
  SESSION_EXPIRED = 'session:expired',

  // Navigation et UI pilotée par serveur
  UI_NAVIGATION_REQUEST = 'ui:navigation_request',
  UI_MODAL_DISPLAY = 'ui:modal_display',
  UI_TOAST_DISPLAY = 'ui:toast_display',
  UI_WORKFLOW_STEP = 'ui:workflow_step',

  // Déploiements (legacy support)
  DEPLOYMENT_LOG = 'deployment:log',
  DEPLOYMENT_STATUS = 'deployment:status',
  DEPLOYMENT_ERROR = 'deployment:error',
  DEPLOYMENT_COMPLETE = 'deployment:complete',

  // Système
  SYSTEM_EVENT = 'system_event',
  HEARTBEAT_PONG = 'pong'
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
 * Mapping des types d'événements vers leurs données
 */
export interface EventDataMap {
  [WebSocketEventType.NOTIFICATION_SYSTEM]: NotificationEvent
  [WebSocketEventType.NOTIFICATION_USER]: NotificationEvent
  [WebSocketEventType.UI_NAVIGATION_REQUEST]: UINavigationRequest
  [WebSocketEventType.UI_MODAL_DISPLAY]: UIModalDisplay
  [WebSocketEventType.UI_TOAST_DISPLAY]: UIToastDisplay
  [WebSocketEventType.UI_WORKFLOW_STEP]: UIWorkflowStep
  [WebSocketEventType.SESSION_AUTH_REQUIRED]: SessionEvent
  [WebSocketEventType.SESSION_PERMISSION_CHANGED]: SessionEvent
  [WebSocketEventType.SESSION_ORGANIZATION_CHANGED]: SessionEvent
  [WebSocketEventType.SESSION_EXPIRED]: SessionEvent
}

/**
 * Message WebSocket générique
 */
export interface WebSocketMessage<T = any> {
  type: string
  data?: T
  timestamp?: string
}
