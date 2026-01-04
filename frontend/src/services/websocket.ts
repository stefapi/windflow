/**
 * WebSocket/SSE Service
 * Real-time communication for deployment logs, notifications, status updates
 * Extended with plugin system for easy extensibility
 */

import { pluginManager } from './websocket/plugin'
import { WebSocketEventType } from './websocket/types'

type EventCallback = (data: unknown) => void

interface WebSocketMessage {
  type: string
  data: unknown
}

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 3 // Aligned with HTTP retry logic
  private reconnectDelays = [1000, 2000, 4000] // Exponential backoff: 1s, 2s, 4s
  private isReconnecting = false // Prevent simultaneous reconnection attempts
  private listeners: Map<string, Set<EventCallback>> = new Map()
  private url: string
  private authenticated = false
  private authToken: string | null = null

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

    // Stocker le token d'authentification si fourni
    if (authToken) {
      this.authToken = authToken
    }

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        console.log('🔗 WebSocket connected successfully!')
        this.reconnectAttempts = 0
        this.isReconnecting = false

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

        // Check for authentication/policy violation errors that should not retry
        // Code 1008 = Policy Violation (used for auth errors by backend)
        // Code 1003 = Unsupported Data
        // Code 1011 = Internal Server Error
        const authErrorCodes = [1008, 1003]
        const authErrorReasons = [
          'User not found or inactive',
          'Invalid token',
          'Authentication required',
          'Authentication timeout'
        ]

        const isAuthError = authErrorCodes.includes(event.code) ||
                           authErrorReasons.some(reason => event.reason?.includes(reason))

        if (isAuthError) {
          console.error(`WebSocket authentication error (code: ${event.code}, reason: ${event.reason}), logging out`)
          this.reconnectAttempts = 0
          this.isReconnecting = false

          // Import and use auth store for logout
          import('@/stores/auth').then(({ useAuthStore }) => {
            const authStore = useAuthStore()
            authStore.logout()
          }).catch(error => {
            console.error('Failed to logout after WebSocket auth error:', error)
            // Fallback: redirect to login
            window.location.href = '/login'
          })
          return
        }

        // For normal disconnections, attempt to reconnect
        this.attemptReconnect()
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
  }

  /**
   * Authenticate with the WebSocket server
   */
  private authenticate(token: string): void {
    console.log('🔐 Attempting WebSocket authentication...')
    console.log('🔐 WebSocket readyState:', this.ws?.readyState)
    console.log('🔐 Token length:', token.length)

    if (this.ws?.readyState === WebSocket.OPEN) {
      const authMessage = {
        type: 'auth',
        token: token
      }
      console.log('🔐 Sending auth message:', { type: 'auth', token: `${token.substring(0, 10)}...` })
      this.ws.send(JSON.stringify(authMessage))
      console.log('✅ Authentication message sent successfully')
      this.authToken = token
    } else {
      console.error('❌ Cannot authenticate: WebSocket not connected, readyState:', this.ws?.readyState)
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
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.reconnectAttempts = 0
    this.isReconnecting = false
  }

  /**
   * Attempt to reconnect with exponential backoff (aligned with HTTP retry logic)
   */
  private attemptReconnect(): void {
    // If max attempts reached, logout user
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error(`Max reconnection attempts (${this.maxReconnectAttempts}) reached, logging out`)
      this.reconnectAttempts = 0
      this.isReconnecting = false

      // Import and use auth store for logout
      import('@/stores/auth').then(({ useAuthStore }) => {
        const authStore = useAuthStore()
        authStore.logout()
      }).catch(error => {
        console.error('Failed to logout after max WebSocket reconnection attempts:', error)
        // Fallback: redirect to login
        window.location.href = '/login'
      })
      return
    }

    // Prevent simultaneous reconnection attempts
    if (this.isReconnecting) {
      console.warn('Reconnection already in progress, skipping')
      return
    }

    this.isReconnecting = true
    const delay = this.reconnectDelays[this.reconnectAttempts]
    this.reconnectAttempts++

    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    setTimeout(() => {
      this.isReconnecting = false
      this.connect()
    }, delay)
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
    } else if (type === 'error') {
      console.error('WebSocket server error:', data)
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
    } else {
      console.warn('WebSocket is not connected')
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
    console.log('🔐 Attempting to connect with authentication...')

    // Essayer d'abord le localStorage directement avec plus de détails
    const storedToken = localStorage.getItem('access_token')
    console.log('🔐 localStorage keys:', Object.keys(localStorage))
    console.log('🔐 access_token key exists:', localStorage.getItem('access_token') !== null)
    console.log('🔐 Token from localStorage:', storedToken ? `${storedToken.substring(0, 20)}...` : 'null')

    if (storedToken && storedToken.length > 0) {
      console.log('🔐 Connecting with localStorage token...')
      this.connect(storedToken)
      return
    }

    // Fallback vers le store d'authentification si pas de token en localStorage
    console.log('🔐 No token in localStorage, trying auth store...')
    import('@/stores/auth').then(({ useAuthStore }) => {
      const authStore = useAuthStore()
      console.log('🔐 Auth store state:', {
        hasToken: !!authStore.token,
        hasUser: !!authStore.user,
        isAuthenticated: authStore.isAuthenticated
      })

      if (authStore.token) {
        console.log('🔐 Connecting with store token...')
        this.connect(authStore.token)
      } else {
        console.warn('⚠️ No authentication token available in store either - connecting without auth')
        console.warn('🔐 This means the user is not logged in or the session expired')
        this.connect()
      }
    }).catch(error => {
      console.error('❌ Failed to load auth store:', error)
      console.warn('⚠️ Falling back to connection without auth')
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
    const wrappedCallback = (data: any) => {
      if (data && data.deploymentId === deploymentId) {
        // Extraire les logs du message et les passer au callback
        if (data.logs && Array.isArray(data.logs)) {
          data.logs.forEach((log: string) => callback(log))
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
