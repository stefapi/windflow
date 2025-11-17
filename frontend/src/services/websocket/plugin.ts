/**
 * Système de plugins pour WebSocket
 * Permet d'étendre facilement les fonctionnalités temps réel
 */

import type { Router } from 'vue-router'
import type { Pinia } from 'pinia'
import type { WebSocketEventType } from './types'

/**
 * Contexte fourni aux plugins pour accéder aux services de l'application
 */
export interface PluginContext {
  /** Router Vue pour la navigation */
  router: Router

  /** Store Pinia pour l'état global */
  pinia: Pinia

  /** Fonction helper pour afficher une notification */
  showNotification: (notification: NotificationPayload) => void

  /** Fonction helper pour la navigation */
  navigate: (route: string, options?: NavigationOptions) => void

  /** Fonction helper pour afficher une modale */
  showModal: (component: string, props?: Record<string, any>) => void

  /** Logger pour le debugging */
  logger: {
    debug: (message: string, ...args: any[]) => void
    info: (message: string, ...args: any[]) => void
    warn: (message: string, ...args: any[]) => void
    error: (message: string, ...args: any[]) => void
  }
}

/**
 * Notification payload simplifié
 */
export interface NotificationPayload {
  title?: string
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

/**
 * Options de navigation
 */
export interface NavigationOptions {
  params?: Record<string, any>
  query?: Record<string, any>
  replace?: boolean
  state?: any
}

/**
 * Interface que chaque plugin WebSocket doit implémenter
 */
export interface WebSocketPlugin {
  /** Nom unique du plugin */
  name: string

  /** Version du plugin (optionnel) */
  version?: string

  /** Description du plugin (optionnel) */
  description?: string

  /** Liste des événements que ce plugin écoute */
  listensFor: WebSocketEventType[]

  /**
   * Initialise le plugin au démarrage
   * @param context Contexte de l'application
   */
  initialize?(context: PluginContext): Promise<void> | void

  /**
   * Traite un événement WebSocket
   * @param event Type d'événement
   * @param data Données de l'événement
   * @param context Contexte de l'application
   */
  handleEvent(
    event: WebSocketEventType,
    data: any,
    context: PluginContext
  ): Promise<void> | void

  /**
   * Nettoie les ressources du plugin lors de la déconnexion
   */
  cleanup?(): Promise<void> | void
}

/**
 * Gestionnaire de plugins WebSocket
 */
export class WebSocketPluginManager {
  private plugins = new Map<string, WebSocketPlugin>()
  private context: PluginContext | null = null
  private eventHandlers = new Map<WebSocketEventType, Set<WebSocketPlugin>>()

  /**
   * Enregistre un plugin
   */
  register(plugin: WebSocketPlugin): void {
    if (this.plugins.has(plugin.name)) {
      console.warn(`Plugin "${plugin.name}" is already registered, replacing...`)
    }

    this.plugins.set(plugin.name, plugin)

    // Construire l'index des handlers par type d'événement
    plugin.listensFor.forEach(eventType => {
      if (!this.eventHandlers.has(eventType)) {
        this.eventHandlers.set(eventType, new Set())
      }
      this.eventHandlers.get(eventType)!.add(plugin)
    })

    console.log(`✅ WebSocket plugin "${plugin.name}" registered`)
  }

  /**
   * Désenregistre un plugin
   */
  unregister(pluginName: string): void {
    const plugin = this.plugins.get(pluginName)
    if (!plugin) {
      console.warn(`Plugin "${pluginName}" not found`)
      return
    }

    // Retirer des handlers d'événements
    plugin.listensFor.forEach(eventType => {
      const handlers = this.eventHandlers.get(eventType)
      if (handlers) {
        handlers.delete(plugin)
        if (handlers.size === 0) {
          this.eventHandlers.delete(eventType)
        }
      }
    })

    this.plugins.delete(pluginName)
    console.log(`✅ WebSocket plugin "${pluginName}" unregistered`)
  }

  /**
   * Obtient un plugin par son nom
   */
  get(pluginName: string): WebSocketPlugin | undefined {
    return this.plugins.get(pluginName)
  }

  /**
   * Liste tous les plugins enregistrés
   */
  list(): WebSocketPlugin[] {
    return Array.from(this.plugins.values())
  }

  /**
   * Initialise tous les plugins avec le contexte
   */
  async initializeAll(context: PluginContext): Promise<void> {
    this.context = context

    for (const plugin of this.plugins.values()) {
      try {
        if (plugin.initialize) {
          await plugin.initialize(context)
          context.logger.debug(`Plugin "${plugin.name}" initialized`)
        }
      } catch (error) {
        context.logger.error(`Failed to initialize plugin "${plugin.name}":`, error)
      }
    }
  }

  /**
   * Dispatche un événement à tous les plugins qui l'écoutent
   */
  async dispatch(event: WebSocketEventType, data: any): Promise<void> {
    if (!this.context) {
      console.warn('PluginManager not initialized, cannot dispatch events')
      return
    }

    const handlers = this.eventHandlers.get(event)
    if (!handlers || handlers.size === 0) {
      return
    }

    // Exécuter tous les handlers en parallèle
    const promises = Array.from(handlers).map(async (plugin) => {
      try {
        await plugin.handleEvent(event, data, this.context!)
      } catch (error) {
        this.context!.logger.error(
          `Error in plugin "${plugin.name}" handling event "${event}":`,
          error
        )
      }
    })

    await Promise.all(promises)
  }

  /**
   * Nettoie tous les plugins
   */
  async cleanupAll(): Promise<void> {
    for (const plugin of this.plugins.values()) {
      try {
        if (plugin.cleanup) {
          await plugin.cleanup()
        }
      } catch (error) {
        console.error(`Failed to cleanup plugin "${plugin.name}":`, error)
      }
    }
  }
}

/**
 * Instance singleton du gestionnaire de plugins
 */
export const pluginManager = new WebSocketPluginManager()
