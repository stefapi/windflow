/**
 * Export centralisé des plugins WebSocket
 */

export { NavigationPlugin } from './navigation'
export { NotificationPlugin } from './notification'
export { SessionPlugin } from './session'

/**
 * Liste des plugins de base à enregistrer automatiquement
 */
import { NavigationPlugin } from './navigation'
import { NotificationPlugin } from './notification'
import { SessionPlugin } from './session'

export const defaultPlugins = [
  NavigationPlugin,
  NotificationPlugin,
  SessionPlugin
]
