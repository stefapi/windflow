/**
 * Plugin de navigation pilotée par le serveur
 * Permet au backend de contrôler la navigation du frontend
 */

import type { WebSocketPlugin, PluginContext } from '../plugin'
import { WebSocketEventType } from '../types'
import type { UINavigationRequest } from '../types'

export const NavigationPlugin: WebSocketPlugin = {
  name: 'navigation',
  version: '1.0.0',
  description: 'Gère la navigation pilotée par le serveur',

  listensFor: [WebSocketEventType.UI_NAVIGATION_REQUEST],

  handleEvent(event: WebSocketEventType, data: any, context: PluginContext) {
    if (event === WebSocketEventType.UI_NAVIGATION_REQUEST) {
      const request = data as UINavigationRequest

      context.logger.info('Navigation request from server:', request.route)

      try {
        context.navigate(request.route, {
          params: request.params,
          query: request.query,
          replace: request.replace,
          state: request.state
        })
      } catch (error) {
        context.logger.error('Failed to navigate:', error)
        context.showNotification({
          message: 'Erreur lors de la navigation',
          type: 'error'
        })
      }
    }
  }
}
