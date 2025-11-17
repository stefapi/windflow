/**
 * Plugin de gestion des notifications temps réel
 * Affiche les notifications système et utilisateur
 */

import type { WebSocketPlugin, PluginContext } from '../plugin'
import { WebSocketEventType } from '../types'
import type { NotificationEvent, UIToastDisplay } from '../types'

export const NotificationPlugin: WebSocketPlugin = {
  name: 'notification',
  version: '1.0.0',
  description: 'Gère les notifications temps réel système et utilisateur',

  listensFor: [
    WebSocketEventType.NOTIFICATION_SYSTEM,
    WebSocketEventType.NOTIFICATION_USER,
    WebSocketEventType.UI_TOAST_DISPLAY
  ],

  handleEvent(event: WebSocketEventType, data: any, context: PluginContext) {
    // Gestion des notifications complètes
    if (event === WebSocketEventType.NOTIFICATION_SYSTEM ||
        event === WebSocketEventType.NOTIFICATION_USER) {
      const notification = data as NotificationEvent

      context.logger.info(`${event} notification:`, notification.title)

      context.showNotification({
        title: notification.title,
        message: notification.message,
        type: notification.severity || 'info',
        duration: notification.duration
      })

      // Si une action est définie, on pourrait l'enregistrer pour plus tard
      if (notification.action) {
        context.logger.debug('Notification has action:', notification.action)
        // TODO: Gérer les actions de notification si nécessaire
      }
    }

    // Gestion des toasts simples
    if (event === WebSocketEventType.UI_TOAST_DISPLAY) {
      const toast = data as UIToastDisplay

      context.showNotification({
        message: toast.message,
        type: toast.type,
        duration: toast.duration
      })
    }
  }
}
