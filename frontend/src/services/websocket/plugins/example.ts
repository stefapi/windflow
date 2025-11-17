/**
 * Exemple de plugin WebSocket personnalisé
 *
 * Ce fichier sert de référence pour créer vos propres plugins.
 * Il démontre toutes les fonctionnalités et bonnes pratiques du système de plugins.
 */

import type { WebSocketPlugin, PluginContext } from '../plugin'
import { WebSocketEventType } from '../types'
import type { EventDataMap } from '../types'

/**
 * Plugin de gestion des déploiements avec fonctionnalités avancées
 *
 * Fonctionnalités:
 * - Suivi du statut des déploiements en temps réel
 * - Notifications pour les changements de statut
 * - Navigation automatique vers les détails en cas d'erreur
 * - Gestion d'un cache local des déploiements actifs
 * - Logging détaillé pour debugging
 */
export class DeploymentMonitorPlugin implements WebSocketPlugin {
  // Nom unique du plugin
  name = 'deployment-monitor-plugin'

  // Liste des événements WebSocket écoutés par ce plugin
  listensFor = [
    WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    WebSocketEventType.DEPLOYMENT_LOGS_UPDATE,
    WebSocketEventType.DEPLOYMENT_PROGRESS,
  ]

  // Contexte fourni par le PluginManager
  private context?: PluginContext

  // État interne du plugin
  private activeDeployments: Map<string, { name: string; status: string; progress: number }> = new Map()
  private notificationTimeouts: Map<string, NodeJS.Timeout> = new Map()

  /**
   * Initialisation du plugin avec le contexte
   * Appelé une seule fois au démarrage de l'application
   */
  initialize(context: PluginContext): void {
    this.context = context

    // Log de démarrage
    this.context.helpers.logger.log('[DeploymentMonitorPlugin] Plugin initialized')

    // Afficher une notification de bienvenue (optionnel)
    this.context.helpers.showNotification({
      type: 'info',
      title: 'Monitoring actif',
      message: 'Le suivi des déploiements en temps réel est activé',
      duration: 2000
    })
  }

  /**
   * Gestion des événements WebSocket
   * Appelé à chaque fois qu'un événement correspondant arrive
   */
  async handleEvent(
    type: WebSocketEventType,
    data: EventDataMap[typeof type]
  ): Promise<void> {
    try {
      // Dispatcher vers le handler approprié selon le type d'événement
      switch (type) {
        case WebSocketEventType.DEPLOYMENT_STATUS_CHANGED:
          await this.handleStatusChanged(data as any)
          break

        case WebSocketEventType.DEPLOYMENT_LOGS_UPDATE:
          await this.handleLogsUpdate(data as any)
          break

        case WebSocketEventType.DEPLOYMENT_PROGRESS:
          await this.handleProgress(data as any)
          break
      }
    } catch (error) {
      // Toujours gérer les erreurs pour éviter de casser le système
      this.context?.helpers.logger.error('[DeploymentMonitorPlugin] Error handling event:', error)
    }
  }

  /**
   * Handler pour les changements de statut de déploiement
   */
  private async handleStatusChanged(data: {
    deploymentId: string
    deploymentName: string
    oldStatus: string
    newStatus: string
    timestamp: string
  }): Promise<void> {
    const { deploymentId, deploymentName, oldStatus, newStatus } = data

    // Mise à jour de l'état local
    const deployment = this.activeDeployments.get(deploymentId)
    if (deployment) {
      deployment.status = newStatus
    } else {
      this.activeDeployments.set(deploymentId, {
        name: deploymentName,
        status: newStatus,
        progress: 0
      })
    }

    // Log du changement
    this.context?.helpers.logger.log(
      `[DeploymentMonitorPlugin] Deployment ${deploymentName}: ${oldStatus} → ${newStatus}`
    )

    // Notifications selon le nouveau statut
    switch (newStatus) {
      case 'running':
        this.showNotificationWithTimeout(deploymentId, {
          type: 'info',
          title: 'Déploiement démarré',
          message: `${deploymentName} est en cours de déploiement`,
          duration: 3000
        })
        break

      case 'success':
        this.showNotificationWithTimeout(deploymentId, {
          type: 'success',
          title: 'Déploiement réussi',
          message: `${deploymentName} a été déployé avec succès`,
          duration: 5000
        })

        // Nettoyer du cache après succès
        setTimeout(() => {
          this.activeDeployments.delete(deploymentId)
        }, 10000)
        break

      case 'failed':
        this.showNotificationWithTimeout(deploymentId, {
          type: 'error',
          title: 'Déploiement échoué',
          message: `${deploymentName} a échoué. Cliquez pour voir les détails`,
          duration: 10000
        })

        // Navigation automatique vers les détails en cas d'erreur
        // (uniquement si l'utilisateur n'est pas déjà sur une autre page)
        if (this.context?.router.currentRoute.value.path === '/deployments') {
          setTimeout(() => {
            this.context?.helpers.navigate(`/deployments/${deploymentId}`)
          }, 2000)
        }
        break

      case 'cancelled':
        this.showNotificationWithTimeout(deploymentId, {
          type: 'warning',
          title: 'Déploiement annulé',
          message: `${deploymentName} a été annulé`,
          duration: 4000
        })

        // Nettoyer du cache
        this.activeDeployments.delete(deploymentId)
        break
    }
  }

  /**
   * Handler pour les mises à jour de logs
   */
  private async handleLogsUpdate(data: {
    deploymentId: string
    logs: string[]
    timestamp: string
  }): Promise<void> {
    const { deploymentId, logs } = data

    // Log uniquement si on est en mode verbose
    if (import.meta.env.DEV) {
      this.context?.helpers.logger.log(
        `[DeploymentMonitorPlugin] New logs for deployment ${deploymentId}:`,
        logs
      )
    }

    // Chercher des patterns d'erreur dans les logs
    const hasError = logs.some(log =>
      log.toLowerCase().includes('error') ||
      log.toLowerCase().includes('failed')
    )

    if (hasError) {
      const deployment = this.activeDeployments.get(deploymentId)
      if (deployment) {
        this.context?.helpers.showNotification({
          type: 'warning',
          title: 'Erreur détectée',
          message: `Des erreurs ont été détectées dans ${deployment.name}`,
          duration: 5000
        })
      }
    }
  }

  /**
   * Handler pour les mises à jour de progression
   */
  private async handleProgress(data: {
    deploymentId: string
    progress: number
    step: string
    timestamp: string
  }): Promise<void> {
    const { deploymentId, progress, step } = data

    // Mise à jour de la progression dans le cache
    const deployment = this.activeDeployments.get(deploymentId)
    if (deployment) {
      deployment.progress = progress

      // Notification aux étapes clés (25%, 50%, 75%)
      if ([25, 50, 75].includes(progress)) {
        this.context?.helpers.logger.log(
          `[DeploymentMonitorPlugin] ${deployment.name}: ${progress}% - ${step}`
        )
      }
    }
  }

  /**
   * Helper pour afficher des notifications avec timeout
   * Évite de spammer l'utilisateur avec plusieurs notifications pour le même déploiement
   */
  private showNotificationWithTimeout(
    deploymentId: string,
    notification: {
      type: 'success' | 'warning' | 'error' | 'info'
      title: string
      message: string
      duration?: number
    }
  ): void {
    // Annuler la notification précédente si elle existe
    const existingTimeout = this.notificationTimeouts.get(deploymentId)
    if (existingTimeout) {
      clearTimeout(existingTimeout)
    }

    // Afficher la nouvelle notification
    this.context?.helpers.showNotification(notification)

    // Définir un nouveau timeout pour nettoyer
    const timeout = setTimeout(() => {
      this.notificationTimeouts.delete(deploymentId)
    }, notification.duration || 5000)

    this.notificationTimeouts.set(deploymentId, timeout)
  }

  /**
   * Nettoyage du plugin
   * Appelé quand le plugin est désactivé ou que l'application se ferme
   */
  cleanup(): void {
    // Annuler tous les timeouts en cours
    this.notificationTimeouts.forEach(timeout => clearTimeout(timeout))
    this.notificationTimeouts.clear()

    // Nettoyer le cache
    this.activeDeployments.clear()

    // Log de nettoyage
    this.context?.helpers.logger.log('[DeploymentMonitorPlugin] Plugin cleaned up')
  }

  /**
   * Méthodes publiques pour interagir avec le plugin depuis l'extérieur
   * (optionnel, selon vos besoins)
   */

  /**
   * Récupère le statut d'un déploiement depuis le cache
   */
  public getDeploymentStatus(deploymentId: string): string | undefined {
    return this.activeDeployments.get(deploymentId)?.status
  }

  /**
   * Récupère la progression d'un déploiement
   */
  public getDeploymentProgress(deploymentId: string): number | undefined {
    return this.activeDeployments.get(deploymentId)?.progress
  }

  /**
   * Liste tous les déploiements actifs suivis
   */
  public getActiveDeployments(): Array<{ id: string; name: string; status: string; progress: number }> {
    return Array.from(this.activeDeployments.entries()).map(([id, data]) => ({
      id,
      ...data
    }))
  }
}

// Export d'une instance du plugin prête à l'emploi
export const deploymentMonitorPlugin = new DeploymentMonitorPlugin()

/**
 * EXEMPLE D'UTILISATION
 *
 * 1. Enregistrer le plugin dans main.ts:
 *
 *    import { deploymentMonitorPlugin } from './services/websocket/plugins/example'
 *
 *    pluginManager.register(deploymentMonitorPlugin)
 *
 *
 * 2. Utiliser les méthodes publiques dans un composant:
 *
 *    import { deploymentMonitorPlugin } from '@/services/websocket/plugins/example'
 *
 *    const activeDeployments = deploymentMonitorPlugin.getActiveDeployments()
 *    console.log('Déploiements actifs:', activeDeployments)
 *
 *
 * 3. Tester le plugin:
 *
 *    import { describe, it, expect, vi } from 'vitest'
 *    import { DeploymentMonitorPlugin } from './example'
 *    import { WebSocketEventType } from '../types'
 *
 *    describe('DeploymentMonitorPlugin', () => {
 *      it('should track deployment status changes', async () => {
 *        const plugin = new DeploymentMonitorPlugin()
 *
 *        const mockContext = {
 *          router: { currentRoute: { value: { path: '/deployments' } }, push: vi.fn() },
 *          pinia: {},
 *          helpers: {
 *            showNotification: vi.fn(),
 *            navigate: vi.fn(),
 *            showModal: vi.fn(),
 *            logger: { log: vi.fn(), error: vi.fn() }
 *          }
 *        }
 *
 *        plugin.initialize(mockContext)
 *
 *        await plugin.handleEvent(
 *          WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
 *          {
 *            deploymentId: 'deploy-123',
 *            deploymentName: 'Test Deployment',
 *            oldStatus: 'pending',
 *            newStatus: 'running',
 *            timestamp: new Date().toISOString()
 *          }
 *        )
 *
 *        expect(plugin.getDeploymentStatus('deploy-123')).toBe('running')
 *        expect(mockContext.helpers.showNotification).toHaveBeenCalled()
 *      })
 *    })
 */
