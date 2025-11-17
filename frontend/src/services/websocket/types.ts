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
