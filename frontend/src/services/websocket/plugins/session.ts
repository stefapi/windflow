/**
 * Plugin de gestion de session temps réel
 * Gère les événements de session (auth, permissions, organisation)
 */

import type { WebSocketPlugin, PluginContext } from '../plugin'
import { WebSocketEventType } from '../types'
import type { SessionEvent } from '../types'

export const SessionPlugin: WebSocketPlugin = {
  name: 'session',
  version: '1.0.0',
  description: 'Gère les événements de session utilisateur',

  listensFor: [
    WebSocketEventType.SESSION_AUTH_REQUIRED,
    WebSocketEventType.SESSION_PERMISSION_CHANGED,
    WebSocketEventType.SESSION_ORGANIZATION_CHANGED,
    WebSocketEventType.SESSION_EXPIRED
  ],

  handleEvent(event: WebSocketEventType, data: any, context: PluginContext) {
    const sessionEvent = data as SessionEvent

    switch (event) {
      case WebSocketEventType.SESSION_AUTH_REQUIRED:
        context.logger.warn('Authentication required')

        context.showNotification({
          title: 'Authentification requise',
          message: sessionEvent.message || 'Veuillez vous reconnecter',
          type: 'warning',
          duration: 5000
        })

        // Rediriger vers la page de login si spécifié
        if (sessionEvent.redirectTo) {
          setTimeout(() => {
            context.navigate(sessionEvent.redirectTo!, { replace: true })
          }, 1000)
        } else {
          setTimeout(() => {
            context.navigate('/login', { replace: true })
          }, 1000)
        }
        break

      case WebSocketEventType.SESSION_EXPIRED:
        context.logger.warn('Session expired')

        context.showNotification({
          title: 'Session expirée',
          message: 'Votre session a expiré, veuillez vous reconnecter',
          type: 'error',
          duration: 5000
        })

        // Rediriger vers login après un délai
        setTimeout(() => {
          context.navigate('/login', { replace: true })
        }, 2000)
        break

      case WebSocketEventType.SESSION_PERMISSION_CHANGED:
        context.logger.info('Permissions changed')

        context.showNotification({
          title: 'Permissions modifiées',
          message: sessionEvent.message || 'Vos permissions ont été mises à jour',
          type: 'info',
          duration: 4000
        })

        // Recharger les données utilisateur
        // TODO: Appeler le store auth pour rafraîchir les permissions
        break

      case WebSocketEventType.SESSION_ORGANIZATION_CHANGED:
        context.logger.info('Organization changed')

        context.showNotification({
          title: 'Organisation modifiée',
          message: sessionEvent.message || 'Votre organisation a été modifiée',
          type: 'info',
          duration: 4000
        })

        // Rafraîchir la page pour charger les nouvelles données d'organisation
        if (sessionEvent.data?.requiresReload) {
          setTimeout(() => {
            window.location.reload()
          }, 2000)
        }
        break
    }
  }
}
