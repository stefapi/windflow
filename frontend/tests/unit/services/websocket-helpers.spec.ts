/**
 * Tests du service WebSocket (canal général) — STORY-165 Tâche 10 :
 * zones hors reconnexion de `services/websocket.ts`.
 *
 * Couvert ici (le fichier websocket.spec.ts de STORY-164.3 reste dédié à la
 * reconnexion — fichier séparé car le cumul dépasserait ~400 lignes) :
 *
 * - helpers `deploymentEvents` (subscribeToLogs : filtrage deploymentId +
 *   un appel par ligne + message `deployment_logs` ; subscribeToStatus /
 *   subscribeToDeployment : double abonnement + désabonnement) ;
 * - `notificationEvents.subscribe`/`subscribeToSystemEvents` et
 *   `eventHelpers.subscribe`/`unsubscribe` (messages serveur attendus) ;
 * - `syncServerSubscriptions` : topics tracés puis rejoués à la
 *   reconnexion (`subscribe`/`deployment_logs`), clé fallback
 *   `JSON.stringify(data)` sans event_type ni deployment_id ;
 * - `handleMessage` : dispatch `pluginManager` pour les
 *   WebSocketEventType (spy), callback qui lève n'empêche pas les
 *   suivants, message `error` avec champ `message` puis avec `data` seul ;
 * - `connectWithAuth` : token localStorage → connect(token) ; fallback
 *   store auth ; aucun token → connect() sans token (warning) ;
 * - `send` hors OPEN → warning, rien envoyé ; `authenticateWithToken` WS
 *   fermée → error logguée, pas d'envoi ; `isConnected()`/`isAuthenticated()`.
 *
 * Sécurité (rules 35/40) : le token n'apparaît QUE dans le message
 * d'authentification ; aucun secret dans les payloads `subscribe` /
 * `deployment_logs` (assertions sur le contenu parse, jamais le token
 * loggué).
 *
 * Patterns du fichier 164.3 : installWebSocketMock (statiques OPEN/…),
 * pilotage manuel onopen/onmessage/onclose, timers virtuels, mock
 * `@/stores/auth` (on asserte les appels, jamais le token lui-même).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

type CloseHandler = (event: { code: number; reason?: string }) => void
type OpenHandler = () => void
type MessageHandler = (event: { data: string }) => void

interface MockWebSocket {
  readyState: number
  sent: string[]
  onopen: OpenHandler | null
  onmessage: MessageHandler | null
  onclose: CloseHandler | null
  send: ReturnType<typeof vi.fn>
  close: ReturnType<typeof vi.fn>
}

let mockWs: MockWebSocket
let wsConstructor: ReturnType<typeof vi.fn>
let consoleErrorSpy: ReturnType<typeof vi.spyOn>

/** Installe un mock WebSocket avec les constantes statiques du standard. */
function installWebSocketMock(): void {
  wsConstructor = vi.fn().mockImplementation(() => {
    mockWs = {
      readyState: 0,
      sent: [],
      onopen: null,
      onmessage: null,
      onclose: null,
      send: vi.fn().mockImplementation((data: string) => {
        mockWs.sent.push(data)
      }),
      close: vi.fn().mockImplementation(() => {
        mockWs.readyState = 3
      }),
    }
    return mockWs
  })
  Object.assign(wsConstructor, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 })
  vi.stubGlobal('WebSocket', wsConstructor)
}

// Store auth mocké — token contrôlable pour connectWithAuth ; on vérifie
// les appels (logout/token consommé), jamais le token affiché.
const mockAuthStore = { token: null as string | null, logout: vi.fn() }
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

import { pluginManager } from '@/services/websocket/plugin'
import wsService, { deploymentEvents, eventHelpers, notificationEvents } from '@/services/websocket'

function openSocket(): void {
  mockWs.readyState = 1
  mockWs.onopen?.()
}

function openAndAuthenticate(): void {
  openSocket()
  mockWs.onmessage?.({ data: JSON.stringify({ type: 'auth_success', data: {} }) })
}

function emitServerMessage(type: string, data: unknown, extra?: Record<string, unknown>): void {
  mockWs.onmessage?.({ data: JSON.stringify({ type, data, ...extra }) })
}

function sentParsed(): Array<{ type: string; data: unknown; [key: string]: unknown }> {
  return mockWs.sent.map((raw) => JSON.parse(raw))
}

describe('WebSocketService — helpers & zones hors reconnexion (STORY-165 T10)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    installWebSocketMock()
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockAuthStore.token = null
    localStorage.clear()
    // Nettoie l'état du singleton entre les tests : socket morte, timers,
    // et surtout authToken/authenticated/listeners/serverSubscriptions —
    // champs privés que disconnect() ne purge PAS (sans ce reset, les
    // abonnements des tests précédents seraient rejoués à la première
    // auth_success du test courant).
    wsService.disconnect()
    const internals = wsService as unknown as {
      authenticated: boolean
      authToken: string | null
      listeners: Map<string, Set<unknown>>
      serverSubscriptions: Map<string, unknown>
    }
    internals.authenticated = false
    internals.authToken = null
    internals.listeners.clear()
    internals.serverSubscriptions.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  // =========================================================================
  // deploymentEvents
  // =========================================================================

  describe('deploymentEvents.subscribeToLogs', () => {
    it('envoie deployment_logs au serveur et reçoit uniquement les logs du bon deploymentId', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      deploymentEvents.subscribeToLogs('dep-1', cb)

      // Message serveur d'abonnement (snake_case, deployment_id uniquement)
      const sub = sentParsed().find((m) => m.type === 'deployment_logs')
      expect(sub).toEqual({ type: 'deployment_logs', data: { deployment_id: 'dep-1' } })

      // Logs du bon déploiement : un appel par ligne
      emitServerMessage('DEPLOYMENT_LOGS_UPDATE', { deploymentId: 'dep-1', logs: ['line-1', 'line-2'] })
      expect(cb).toHaveBeenCalledTimes(2)
      expect(cb).toHaveBeenNthCalledWith(1, 'line-1')
      expect(cb).toHaveBeenNthCalledWith(2, 'line-2')

      // Logs d'un AUTRE déploiement : filtrés par le wrapper
      emitServerMessage('DEPLOYMENT_LOGS_UPDATE', { deploymentId: 'dep-other', logs: ['nope'] })
      expect(cb).toHaveBeenCalledTimes(2)
    })

    it('ignore les payloads sans tableau logs', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      deploymentEvents.subscribeToLogs('dep-1', cb)
      emitServerMessage('DEPLOYMENT_LOGS_UPDATE', { deploymentId: 'dep-1' })
      emitServerMessage('DEPLOYMENT_LOGS_UPDATE', { deploymentId: 'dep-1', logs: 'not-an-array' })

      expect(cb).not.toHaveBeenCalled()
    })

    it('la désabonnement retire le listener', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      const unsubscribe = deploymentEvents.subscribeToLogs('dep-1', cb)
      unsubscribe()
      emitServerMessage('DEPLOYMENT_LOGS_UPDATE', { deploymentId: 'dep-1', logs: ['ignored'] })

      expect(cb).not.toHaveBeenCalled()
    })
  })

  describe('deploymentEvents.subscribeToStatus / subscribeToDeployment', () => {
    it('subscribeToStatus écoute le canal de statut du déploiement', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      deploymentEvents.subscribeToStatus('dep-7', cb)
      emitServerMessage('deployment:dep-7:status', { status: 'running' })
      emitServerMessage('deployment:dep-9:status', { status: 'failed' })

      expect(cb).toHaveBeenCalledTimes(1)
      expect(cb).toHaveBeenCalledWith({ status: 'running' })
    })

    it('subscribeToDeployment : double abonnement logs+status, message serveur envoyé, unsubscribe retire les deux', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      const unsubscribe = deploymentEvents.subscribeToDeployment('dep-3', cb)

      const sub = sentParsed().find((m) => m.type === 'deployment_logs')
      expect(sub).toEqual({ type: 'deployment_logs', data: { deployment_id: 'dep-3' } })

      emitServerMessage('deployment:dep-3:logs', { line: 'x' })
      emitServerMessage('deployment:dep-3:status', { status: 'done' })
      expect(cb).toHaveBeenCalledTimes(2)

      unsubscribe()
      emitServerMessage('deployment:dep-3:logs', { line: 'y' })
      emitServerMessage('deployment:dep-3:status', { status: 'archived' })
      expect(cb).toHaveBeenCalledTimes(2)
    })
  })

  // =========================================================================
  // notificationEvents / eventHelpers
  // =========================================================================

  describe('notificationEvents', () => {
    it('subscribe écoute le canal notification (client-only, aucun message serveur)', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()
      const sentBefore = mockWs.sent.length

      notificationEvents.subscribe(cb)
      emitServerMessage('notification', { title: 'Hi' })

      expect(cb).toHaveBeenCalledWith({ title: 'Hi' })
      // Pas d'abonnement serveur pour ce helper : rien de nouveau envoyé.
      expect(mockWs.sent.length).toBe(sentBefore)
    })

    it('subscribeToSystemEvents envoie subscribe {event_type: system_event}', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      const unsubscribe = notificationEvents.subscribeToSystemEvents(cb)

      const sub = sentParsed().find((m) => m.type === 'subscribe')
      expect(sub).toEqual({ type: 'subscribe', data: { event_type: 'system_event' } })

      emitServerMessage('system_event', { message: 'maintenance' })
      expect(cb).toHaveBeenCalledWith({ message: 'maintenance' })

      unsubscribe()
      emitServerMessage('system_event', { message: 'after' })
      expect(cb).toHaveBeenCalledTimes(1)
    })
  })

  describe('eventHelpers', () => {
    it('subscribe envoie subscribe {event_type} ; unsubscribe envoie unsubscribe et retire le listener', () => {
      const cb = vi.fn()
      wsService.connect('jwt-token')
      openAndAuthenticate()

      eventHelpers.subscribe('metrics_alert', cb)
      expect(sentParsed().some((m) => m.type === 'subscribe' && (m.data as { event_type: string }).event_type === 'metrics_alert')).toBe(true)

      emitServerMessage('metrics_alert', { cpu: 92 })
      expect(cb).toHaveBeenCalledWith({ cpu: 92 })

      eventHelpers.unsubscribe('metrics_alert', cb)
      expect(sentParsed().some((m) => m.type === 'unsubscribe' && (m.data as { event_type: string }).event_type === 'metrics_alert')).toBe(true)

      emitServerMessage('metrics_alert', { cpu: 11 })
      expect(cb).toHaveBeenCalledTimes(1)
    })
  })

  // =========================================================================
  // syncServerSubscriptions — rejeu des abonnements à la reconnexion
  // =========================================================================

  describe('syncServerSubscriptions (rejeu après reconnexion)', () => {
    it('les abonnements deployment_logs sont rejoués sur la nouvelle socket', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      wsService.send('deployment_logs', { deployment_id: 'dep-replay' })

      // Coupure réseau puis reconnexion + ré-authentification
      mockWs.readyState = 3
      mockWs.onclose?.({ code: 1006 })
      vi.advanceTimersByTime(1250)
      openAndAuthenticate()

      const replay = sentParsed().filter(
        (m) => m.type === 'deployment_logs' && (m.data as { deployment_id?: string }).deployment_id === 'dep-replay'
      )
      expect(replay).toHaveLength(1)
    })

    it('clé fallback JSON.stringify quand ni event_type ni deployment_id', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      // Payload sans event_type/deployment_id → clé fallback, toujours rejoué
      wsService.send('subscribe', { custom_topic: 42 })

      mockWs.readyState = 3
      mockWs.onclose?.({ code: 1006 })
      vi.advanceTimersByTime(1250)
      openAndAuthenticate()

      const replay = sentParsed().filter((m) => m.type === 'subscribe')
      expect(replay).toContainEqual({ type: 'subscribe', data: { custom_topic: 42 } })
    })

    it('unsubscribe retire l’entrée subscribe:<event_type> (pas de rejeu)', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      wsService.send('subscribe', { event_type: 'to_remove' })
      wsService.send('unsubscribe', { event_type: 'to_remove' })

      mockWs.readyState = 3
      mockWs.onclose?.({ code: 1006 })
      vi.advanceTimersByTime(1250)
      openAndAuthenticate()

      const replay = sentParsed().filter((raw) => JSON.stringify(raw).includes('to_remove'))
      expect(replay).toHaveLength(0)
    })

    it('un type non-abonnement n’est pas tracé (jamais rejoué)', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      wsService.send('ping', { anything: true })

      mockWs.readyState = 3
      mockWs.onclose?.({ code: 1006 })
      vi.advanceTimersByTime(1250)
      openAndAuthenticate()

      expect(sentParsed().some((m) => m.type === 'ping')).toBe(false)
    })
  })

  // =========================================================================
  // handleMessage — dispatch plugins + callbacks
  // =========================================================================

  describe('handleMessage — dispatch plugins & callbacks', () => {
    it('dispatch les WebSocketEventType vers pluginManager (spy)', async () => {
      const dispatchSpy = vi.spyOn(pluginManager, 'dispatch').mockResolvedValue(undefined)
      wsService.connect('jwt-token')
      openAndAuthenticate()

      emitServerMessage('DEPLOYMENT_STATUS_CHANGED', { deploymentId: 'd1', newStatus: 'running' })
      await vi.advanceTimersByTimeAsync(0)

      expect(dispatchSpy).toHaveBeenCalledWith('DEPLOYMENT_STATUS_CHANGED', {
        deploymentId: 'd1',
        newStatus: 'running'
      })
    })

    it('ne dispatch PAS les types hors enum', async () => {
      const dispatchSpy = vi.spyOn(pluginManager, 'dispatch').mockResolvedValue(undefined)
      wsService.connect('jwt-token')
      openAndAuthenticate()

      emitServerMessage('totally_custom_type', { x: 1 })
      await vi.advanceTimersByTimeAsync(0)

      expect(dispatchSpy).not.toHaveBeenCalled()
    })

    it('un callback qui lève n’empêche pas les suivants (console.error)', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      const exploding = vi.fn(() => {
        throw new Error('callback boom')
      })
      const after = vi.fn()
      wsService.on('SYSTEM_BROADCAST', exploding)
      wsService.on('SYSTEM_BROADCAST', after)

      emitServerMessage('SYSTEM_BROADCAST', { message: 'hello' })

      expect(exploding).toHaveBeenCalled()
      expect(after).toHaveBeenCalledWith({ message: 'hello' })
      expect(consoleErrorSpy).toHaveBeenCalled()
    })

    it('message error avec champ message → loggué tel quel', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      emitServerMessage('error', undefined, { message: 'Something broke' })

      expect(consoleErrorSpy).toHaveBeenCalledWith('WebSocket server error:', 'Something broke')
    })

    it('message error avec data seul → data logguée', () => {
      wsService.connect('jwt-token')
      openAndAuthenticate()

      emitServerMessage('error', 'fallback payload')

      expect(consoleErrorSpy).toHaveBeenCalledWith('WebSocket server error:', 'fallback payload')
    })
  })

  // =========================================================================
  // connectWithAuth — 3 branches
  // =========================================================================

  describe('connectWithAuth', () => {
    it('token présent dans localStorage → connect(token) immédiat', async () => {
      localStorage.setItem('access_token', 'local-jwt')
      wsService.connectWithAuth()
      // Branche synchrone : la socket est créée sans attendre le store.
      expect(wsConstructor).toHaveBeenCalledTimes(1)

      openSocket()
      const auth = sentParsed().find((m) => m.type === 'auth')
      expect(auth).toEqual({ type: 'auth', token: 'local-jwt' })
    })

    it('localStorage vide → fallback store auth (authStore.token)', async () => {
      mockAuthStore.token = 'store-jwt'
      wsService.connectWithAuth()
      // Import dynamique du store → microtask.
      await vi.advanceTimersByTimeAsync(0)

      expect(wsConstructor).toHaveBeenCalledTimes(1)
      openSocket()
      const auth = sentParsed().find((m) => m.type === 'auth')
      expect(auth).toEqual({ type: 'auth', token: 'store-jwt' })
    })

    it('aucun token nulle part → connect() sans token + warning', async () => {
      wsService.connectWithAuth()
      await vi.advanceTimersByTimeAsync(0)

      expect(wsConstructor).toHaveBeenCalledTimes(1)
      openSocket()

      // Aucun message d’auth émis, warning émis (token absent).
      expect(sentParsed().some((m) => m.type === 'auth')).toBe(false)
      expect(vi.mocked(console.warn)).toHaveBeenCalled()
    })
  })

  // =========================================================================
  // send hors OPEN / authenticateWithToken / état
  // =========================================================================

  describe('send hors OPEN, authenticateWithToken, état du service', () => {
    it('send hors OPEN → warning, rien d’envoyé', () => {
      wsService.connect('jwt-token')
      // readyState 0 (CONNECTING) : pas encore OPEN
      wsService.send('subscribe', { event_type: 'nope' })

      expect(mockWs.sent).toHaveLength(0)
      expect(vi.mocked(console.warn)).toHaveBeenCalledWith('WebSocket is not connected')
    })

    it('authenticateWithToken WS fermée → error logguée, aucun envoi', () => {
      wsService.connect('jwt-token')
      // readyState 0 : authenticate ne peut pas envoyer
      wsService.authenticateWithToken('fresh-jwt')

      expect(mockWs.sent).toHaveLength(0)
      expect(consoleErrorSpy).toHaveBeenCalledWith('❌ Cannot authenticate: WebSocket not connected')
    })

    it('isConnected/isAuthenticated reflètent l’état', async () => {
      wsService.connect('jwt-token')
      expect(wsService.isConnected()).toBe(false)
      expect(wsService.isAuthenticated()).toBe(false)

      openSocket()
      expect(wsService.isConnected()).toBe(true)
      expect(wsService.isAuthenticated()).toBe(false)

      mockWs.onmessage?.({ data: JSON.stringify({ type: 'auth_success', data: {} }) })
      await vi.advanceTimersByTimeAsync(0)
      expect(wsService.isAuthenticated()).toBe(true)
    })
  })

  // =========================================================================
  // Sécurité — token uniquement dans le message d’auth (rules 35/40)
  // =========================================================================

  describe('sécurité : aucun secret dans les payloads diffusés', () => {
    it('le token n’apparaît que dans le message d’auth', async () => {
      wsService.connect('super-secret-jwt')
      openAndAuthenticate()

      // Activité variée : abonnements serveur de tous types
      wsService.send('subscribe', { event_type: 'system_event' })
      wsService.send('deployment_logs', { deployment_id: 'dep-sec' })
      wsService.send('unsubscribe', { event_type: 'system_event' })
      eventHelpers.subscribe('metrics_alert', vi.fn())

      // Le token n'est présent que dans l'unique message d'authentification.
      const withToken = mockWs.sent.filter((raw) => raw.includes('super-secret-jwt'))
      expect(withToken).toHaveLength(1)
      expect(JSON.parse(withToken[0] as string)).toEqual({ type: 'auth', token: 'super-secret-jwt' })
    })

    it('les payloads subscribe/deployment_logs ne contiennent aucun secret', () => {
      wsService.connect('super-secret-jwt')
      openAndAuthenticate()

      wsService.send('subscribe', { event_type: 'system_event' })
      wsService.send('deployment_logs', { deployment_id: 'dep-sec' })

      for (const raw of mockWs.sent) {
        const message = JSON.parse(raw) as { type: string; data: Record<string, unknown> }
        if (message.type === 'auth') continue // seul porteur légitime du token
        expect(JSON.stringify(message)).not.toContain('super-secret-jwt')
        expect(message.data).not.toHaveProperty('token')
        expect(message.data).not.toHaveProperty('password')
      }

      const payloads = sentParsed().filter((m) => m.type === 'subscribe' || m.type === 'deployment_logs')
      expect(payloads).toEqual([
        { type: 'subscribe', data: { event_type: 'system_event' } },
        { type: 'deployment_logs', data: { deployment_id: 'dep-sec' } }
      ])
    })
  })
})
