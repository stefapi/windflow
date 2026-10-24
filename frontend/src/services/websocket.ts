/**
 * WebSocket/SSE Service
 * Real-time communication for deployment logs, notifications, status updates
 * Extended with plugin system for easy extensibility
 *
 * STORY-164.3 : la reconnexion consomme la politique unifiée `ws-reconnect`
 * (backoff exponentiel + jitter borné, machine à états). Comportements
 * historiques préservés : aucun retry sur 1008/1003 (auth) et **logout sur
 * épuisement des tentatives** (preset `generalChannel`, 3 tentatives).
 */

import { pluginManager } from './websocket/plugin'
import { WebSocketEventType } from './websocket/types'
import { createReconnectPolicy, WS_RECONNECT_PRESETS, type ReconnectController } from './ws-reconnect'

type EventCallback = (data: unknown) => void

interface WebSocketMessage {
  type: string
  data: unknown
}

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private listeners: Map<string, Set<EventCallback>> = new Map()
  /** Abonnements serveur actifs (`subscribe`/`deployment_logs`) — rétablis après reconnexion. */
  private serverSubscriptions: Map<string, unknown> = new Map()
  private url: string
  private authenticated = false
  private authToken: string | null = null

  /**
   * Politique de reconnexion unifiée (STORY-164.3) :
   * - logout sur fermeture d'auth (1008/1003 + raisons auth) — aucun retry ;
   * - logout sur épuisement des tentatives (comportement historique conservé) ;
   * - re-souscription des abonnements serveur actifs à chaque réouverture.
   */
  private reconnect: ReconnectController = createReconnectPolicy({
    ...WS_RECONNECT_PRESETS.generalChannel,
    onAuthError: () => this.handleFatalClose(),
    onExhausted: () => this.handleFatalClose(),
    onResubscribe: () => this.resubscribeActiveTopics(),
  })

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const apiUrl = import.meta.env['VITE_API_BASE_URL'] || `${protocol}//${host}`

    // Utiliser l'endpoint WebSocket sécurisé (authentification obligatoire)
    this.url = apiUrl.replace(/^http/, 'ws').replace(/\/$/, '') + '/api/v1/ws/'
  }

  /**
   * Connect to WebSocket server with optional authentication
   */
  connect(authToken?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    // Reconnexion volontaire après un arrêt de la politique (logout/login,
    // disconnect()) : la politique repart de zéro.
    if (this.reconnect.getState() === 'stopped') {
      this.reconnect.reset()
    }
    this.reconnect.recordConnecting()

    // Stocker le token d'authentification si fourni
    if (authToken) {
      this.authToken = authToken
    }

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('🔗 WebSocket connected successfully!')

        // Authentifier immédiatement si un token est disponible
        if (this.authToken) {
          console.log('🔐 Sending authentication...')
          this.authenticate(this.authToken)
        } else {
          console.warn('⚠️ No auth token available for WebSocket authentication')
        }
      }

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        this.authenticated = false

        // Politique unifiée (STORY-164.3) : la décision de retry est portée par
        // `ws-reconnect` — 1008/1003 (auth) → stop + logout via onAuthError ;
        // épuisement des tentatives → logout via onExhausted ; sinon backoff
        // exponentiel + jitter borné via scheduleReconnect.
        const delay = this.reconnect.recordClose(event.code, event.reason ?? '')
        if (delay !== null) {
          this.scheduleReconnect(delay)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
  }

  /**
   * Authenticate with the WebSocket server
   */
  private authenticate(token: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const authMessage = {
        type: 'auth',
        token: token
      }
      this.ws.send(JSON.stringify(authMessage))
      this.authToken = token
      console.log('🔐 WebSocket authentication sent')
    } else {
      console.error('❌ Cannot authenticate: WebSocket not connected')
    }
  }

  /**
   * Authenticate with a new token
   */
  authenticateWithToken(token: string): void {
    this.authToken = token
    this.authenticate(token)
  }

  /**
   * Disconnect from WebSocket server — fin de session (BUG-009).
   *
   * Réinitialise tout l'état de session du singleton : token d'auth,
   * statut authentifié, listeners et abonnements serveur — un `connect()`
   * ultérieur (nouvel utilisateur) part d'un état neutre, sans hériter des
   * abonnements serveur ni de l'identité d'authentification de la session
   * précédente. Les handlers de la socket sont détachés AVANT `close()` :
   * le `onclose` différé de l'ancienne socket ne peut plus corrompre l'état
   * d'une session suivante (course du « handler fantôme »).
   *
   * Pour une rotation de token au sein de la MÊME session (refresh JWT),
   * utiliser `reconnectWithToken()`.
   */
  disconnect(): void {
    // Arrêt volontaire : plus aucune reconnexion automatique ne sera tentée.
    this.reconnect.stop()
    this.clearReconnectTimer()
    if (this.ws) {
      this.detachSocketHandlers()
      this.ws.close()
      this.ws = null
    }
    // Purge de fin de session (BUG-009) : le successeur ne doit rien
    // hériter — ni le token (donnée sensible au-delà de sa session), ni
    // les abonnements serveur, ni les callbacks de la session précédente.
    this.authenticated = false
    this.authToken = null
    this.listeners.clear()
    this.serverSubscriptions.clear()
  }

  /**
   * Rotation de token au sein de la même session (refresh JWT — flux
   * `refreshAccessToken` du store auth, BUG-009) : ferme la socket courante
   * et la recrée immédiatement avec le nouveau token, SANS purger
   * `listeners`/`serverSubscriptions` — les abonnements serveur sont
   * rejoués par `resubscribeActiveTopics()` à l'`auth_success` suivant et
   * les callbacks continuent de recevoir les événements.
   *
   * Le backend n'offre pas de ré-authentification sur connexion ouverte
   * (auth au premier message uniquement) : la rotation recrée la socket
   * côté client. La politique de reconnexion est remise à zéro par
   * `connect()` lui-même (retour depuis `stopped`) — pas de `reset()` manuel.
   */
  reconnectWithToken(token: string): void {
    this.clearReconnectTimer()
    this.reconnect.stop()
    if (this.ws) {
      this.detachSocketHandlers()
      this.ws.close()
      this.ws = null
    }
    this.connect(token)
  }

  /**
   * Détache les handlers de la socket courante avant fermeture volontaire
   * (`onclose`/`onmessage`/`onopen`/`onerror` = null) — neutralise la
   * course du « handler fantôme » (BUG-009) : le close event asynchrone de
   * l'ancienne socket ne peut plus écraser l'état d'une nouvelle session
   * (`authenticated = false`) ni déclencher une reconnexion parasite.
   */
  private detachSocketHandlers(): void {
    if (!this.ws) {
      return
    }
    this.ws.onclose = null
    this.ws.onmessage = null
    this.ws.onopen = null
    this.ws.onerror = null
  }

  /**
   * Programme la prochaine tentative avec le délai (backoff + jitter) calculé
   * par la politique unifiée (STORY-164.3).
   */
  private scheduleReconnect(delay: number): void {
    this.clearReconnectTimer()
    console.log(
      `[ws-reconnect] Next attempt in ${delay}ms (attempt ${this.reconnect.getAttempts()}/${WS_RECONNECT_PRESETS.generalChannel.maxAttempts})`
    )
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, delay)
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  /**
   * Fermeture fatale : erreur d'authentification (1008/1003) ou épuisement des
   * tentatives → logout (comportement historique du canal général, conservé —
   * arbitrage STORY-164.3).
   */
  private handleFatalClose(): void {
    this.clearReconnectTimer()
    // Import and use auth store for logout
    import('@/stores/auth')
      .then(({ useAuthStore }) => {
        const authStore = useAuthStore()
        authStore.logout()
      })
      .catch((error) => {
        console.error('Failed to logout after WebSocket fatal close:', error)
        // Fallback: redirect to login
        window.location.href = '/login'
      })
  }

  /**
   * Rétablit les abonnements serveur actifs après une reconnexion
   * (re-souscription automatique, STORY-164.3). Les abonnements sont tracés
   * dans `serverSubscriptions` au fil des messages `subscribe`/`deployment_logs`.
   */
  private resubscribeActiveTopics(): void {
    if (this.serverSubscriptions.size === 0) {
      return
    }
    console.log(`[ws-reconnect] Re-establishing ${this.serverSubscriptions.size} server subscription(s)`)
    for (const [key, data] of this.serverSubscriptions) {
      const type = key.split(':')[0] ?? 'subscribe'
      this.send(type, data)
    }
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(message: WebSocketMessage): void {
    const { type, data } = message

    // Gestion spéciale des messages d'authentification
    if (type === 'auth_success') {
      this.authenticated = true
      console.log('WebSocket authentication successful')
      // Connexion réellement établie (canal général : auth au premier message)
      // → déclenche la re-souscription des abonnements actifs (STORY-164.3).
      this.reconnect.recordOpen()
    } else if (type === 'error') {
      // Le backend peut envoyer soit {type: "error", data: ...} soit {type: "error", message: ...}
      const errorMessage = (message as WebSocketMessage & { message?: string }).message || data || 'Unknown error'
      console.error('WebSocket server error:', errorMessage)
    }

    // Dispatcher l'événement aux plugins si le type correspond à un WebSocketEventType
    if (Object.values(WebSocketEventType).includes(type as WebSocketEventType)) {
      pluginManager.dispatch(type as WebSocketEventType, data).catch(error => {
        console.error('Error dispatching event to plugins:', error)
      })
    }

    // Conserver le système de callbacks existant pour la compatibilité
    const callbacks = this.listeners.get(type)

    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in WebSocket callback for type "${type}":`, error)
        }
      })
    }
  }

  /**
   * Subscribe to a specific event type
   */
  on(eventType: string, callback: EventCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set())
    }

    this.listeners.get(eventType)?.add(callback)

    // Return unsubscribe function
    return () => {
      this.off(eventType, callback)
    }
  }

  /**
   * Unsubscribe from an event type
   */
  off(eventType: string, callback: EventCallback): void {
    const callbacks = this.listeners.get(eventType)
    if (callbacks) {
      callbacks.delete(callback)
      if (callbacks.size === 0) {
        this.listeners.delete(eventType)
      }
    }
  }

  /**
   * Send message to server
   */
  send(type: string, data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = { type, data }
      this.ws.send(JSON.stringify(message))
      this.syncServerSubscriptions(type, data)
    } else {
      console.warn('WebSocket is not connected')
    }
  }

  /**
   * Trace les abonnements serveur (`subscribe`/`deployment_logs`) pour pouvoir
   * les rétablir après une reconnexion ; retire les désabonnements.
   */
  private syncServerSubscriptions(type: string, data: unknown): void {
    const payload = (data ?? {}) as { event_type?: string; deployment_id?: string }
    if (type === 'subscribe' || type === 'deployment_logs') {
      const topic = payload.event_type ?? payload.deployment_id ?? JSON.stringify(data)
      this.serverSubscriptions.set(`${type}:${topic}`, data)
    } else if (type === 'unsubscribe' && payload.event_type) {
      this.serverSubscriptions.delete(`subscribe:${payload.event_type}`)
    }
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * Check if WebSocket is authenticated
   */
  isAuthenticated(): boolean {
    return this.authenticated
  }

  /**
   * Connect with automatic authentication using auth store
   */
  connectWithAuth(): void {
    // Essayer d'abord le localStorage directement
    const storedToken = localStorage.getItem('access_token')

    if (storedToken && storedToken.length > 0) {
      this.connect(storedToken)
      return
    }

    // Fallback vers le store d'authentification si pas de token en localStorage
    import('@/stores/auth').then(({ useAuthStore }) => {
      const authStore = useAuthStore()

      if (authStore.token) {
        this.connect(authStore.token)
      } else {
        console.warn('⚠️ No authentication token available')
        this.connect()
      }
    }).catch(error => {
      console.error('❌ Failed to load auth store:', error)
      this.connect()
    })
  }
}

// Singleton instance
const wsService = new WebSocketService()

export default wsService

// Event-specific helpers
export const deploymentEvents = {
  subscribeToLogs: (deploymentId: string, callback: (data: unknown) => void) => {
    // S'abonner au type d'événement global DEPLOYMENT_LOGS_UPDATE
    // et filtrer les messages pour ce deploymentId spécifique
    const wrappedCallback = (data: unknown) => {
      const eventData = data as { deploymentId?: string; logs?: string[] }
      if (eventData && eventData.deploymentId === deploymentId) {
        // Extraire les logs du message et les passer au callback
        if (eventData.logs && Array.isArray(eventData.logs)) {
          eventData.logs.forEach((log: string) => callback(log))
        }
      }
    }

    const unsubscribe = wsService.on(WebSocketEventType.DEPLOYMENT_LOGS_UPDATE, wrappedCallback)

    // Envoyer un message pour s'abonner aux logs côté serveur
    wsService.send('deployment_logs', { deployment_id: deploymentId })

    return unsubscribe
  },

  subscribeToStatus: (deploymentId: string, callback: (data: unknown) => void) => {
    return wsService.on(`deployment:${deploymentId}:status`, callback)
  },

  subscribeToDeployment: (deploymentId: string, callback: (data: unknown) => void) => {
    // S'abonner aux logs et au statut d'un déploiement spécifique
    const unsubscribeLogs = wsService.on(`deployment:${deploymentId}:logs`, callback)
    const unsubscribeStatus = wsService.on(`deployment:${deploymentId}:status`, callback)

    // Envoyer un message pour s'abonner côté serveur
    wsService.send('deployment_logs', { deployment_id: deploymentId })

    // Retourner une fonction pour se désabonner des deux événements
    return () => {
      unsubscribeLogs()
      unsubscribeStatus()
    }
  }
}

export const notificationEvents = {
  subscribe: (callback: (data: unknown) => void) => {
    return wsService.on('notification', callback)
  },

  subscribeToSystemEvents: (callback: (data: unknown) => void) => {
    // S'abonner aux événements système généraux
    const unsubscribe = wsService.on('system_event', callback)

    // Envoyer un message pour s'abonner côté serveur
    wsService.send('subscribe', { event_type: 'system_event' })

    return unsubscribe
  }
}

// Helper pour les événements personnalisés
export const eventHelpers = {
  /**
   * S'abonner à un événement personnalisé
   */
  subscribe: (eventType: string, callback: (data: unknown) => void) => {
    const unsubscribe = wsService.on(eventType, callback)

    // Envoyer un message pour s'abonner côté serveur
    wsService.send('subscribe', { event_type: eventType })

    return unsubscribe
  },

  /**
   * Se désabonner d'un événement personnalisé
   */
  unsubscribe: (eventType: string, callback: (data: unknown) => void) => {
    wsService.off(eventType, callback)
    wsService.send('unsubscribe', { event_type: eventType })
  }
}
