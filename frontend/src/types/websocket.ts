/**
 * Types pour les événements WebSocket de déploiement
 * Correspond aux événements définis dans backend/app/services/deployment_events.py
 */

import type { DeploymentStatus } from './api'

/**
 * Événement de changement de statut de déploiement
 */
export interface DeploymentStatusChangedEvent {
  deployment_id: string
  new_status: DeploymentStatus
  old_status?: DeploymentStatus
  name?: string
  error_message?: string | null
  timestamp: string
}

/**
 * Événement de mise à jour des logs de déploiement
 */
export interface DeploymentLogsUpdateEvent {
  deployment_id: string
  logs: string
  append: boolean
  timestamp: string
}

/**
 * Événement de progression de déploiement
 */
export interface DeploymentProgressEvent {
  deployment_id: string
  progress: number
  current_step: string
  total_steps: number
  timestamp: string
}

/**
 * Énumération des types d'événements de déploiement
 */
export enum DeploymentEventType {
  STATUS_CHANGED = 'DEPLOYMENT_STATUS_CHANGED',
  LOGS_UPDATE = 'DEPLOYMENT_LOGS_UPDATE',
  PROGRESS = 'DEPLOYMENT_PROGRESS'
}

/**
 * Union type pour tous les événements de déploiement
 */
export type DeploymentEvent =
  | DeploymentStatusChangedEvent
  | DeploymentLogsUpdateEvent
  | DeploymentProgressEvent
