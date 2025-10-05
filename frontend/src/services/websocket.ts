/**
 * WebSocket/SSE Service
 * Real-time communication for deployment logs, notifications, status updates
 */

type EventCallback = (data: unknown) => void

interface WebSocketMessage {
  type: string
  data: unknown
}

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private listeners: Map<string, Set<EventCallback>> = new Map()
  private url: string

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.url = `${protocol}//${host}/ws`
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    const token = localStorage.getItem('access_token')
    if (!token) {
      console.warn('Cannot connect to WebSocket: No access token')
      return
    }

    try {
      this.ws = new WebSocket(`${this.url}?token=${token}`)

      this.ws.onopen = () => {
        console.log('WebSocket connected')
        this.reconnectAttempts = 0
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

      this.ws.onclose = () => {
        console.log('WebSocket disconnected')
        this.attemptReconnect()
      }
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
    }
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
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => {
      this.connect()
    }, delay)
  }

  /**
   * Handle incoming WebSocket message
   */
  private handleMessage(message: WebSocketMessage): void {
    const { type, data } = message
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
}

// Singleton instance
const wsService = new WebSocketService()

export default wsService

// Event-specific helpers
export const deploymentEvents = {
  subscribeToLogs: (deploymentId: string, callback: (log: string) => void) => {
    return wsService.on(`deployment:${deploymentId}:logs`, callback)
  },

  subscribeToStatus: (deploymentId: string, callback: (status: string) => void) => {
    return wsService.on(`deployment:${deploymentId}:status`, callback)
  },
}

export const notificationEvents = {
  subscribe: (callback: (notification: unknown) => void) => {
    return wsService.on('notification', callback)
  },
}
