/**
 * Tests du service WebSocket (canal général) — STORY-164.3 :
 * consommation de la politique unifiée `ws-reconnect`, logout sur fermeture
 * fatale (1008/1003 ou épuisement — non-régression UX), re-souscription des
 * abonnements serveur après reconnexion.
 *
 * WebSocket global mocké (statiques OPEN/CONNECTING/… requises par le service,
 * handlers pilotés manuellement) ; timers virtuels — aucun sleep réel.
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
  // Constantes statiques obligatoires (le service teste readyState === OPEN)
  Object.assign(wsConstructor, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 })
  vi.stubGlobal('WebSocket', wsConstructor)
}

// Store auth mocké — on vérifie l'appel à logout(), jamais le token lui-même.
const mockLogout = vi.fn()
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ logout: mockLogout }),
}))

import wsService from '@/services/websocket'

function openAndAuthenticate(): void {
  mockWs.readyState = 1
  mockWs.onopen?.()
  mockWs.onmessage?.({ data: JSON.stringify({ type: 'auth_success', data: {} }) })
}

function emitServerMessage(type: string, data: unknown): void {
  mockWs.onmessage?.({ data: JSON.stringify({ type, data }) })
}

describe('WebSocketService — politique de reconnexion unifiée (STORY-164.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    installWebSocketMock()
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
    // Nettoie l'état du singleton entre les tests (socket morte, timers).
    wsService.disconnect()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('consomme la politique partagée : coupure 1006 → retry après backoff', () => {
    wsService.connect('jwt-token')
    openAndAuthenticate()

    mockWs.readyState = 3
    mockWs.onclose?.({ code: 1006 })
    expect(mockLogout).not.toHaveBeenCalled()

    // Nouvelle socket créée après le délai (backoff base ~1 s ± 25 % jitter)
    vi.advanceTimersByTime(1250)
    expect(wsConstructor.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('1008 (auth) → aucun retry, logout immédiat (non-régression)', async () => {
    wsService.connect('jwt-token')
    openAndAuthenticate()

    mockWs.readyState = 3
    mockWs.onclose?.({ code: 1008, reason: 'Invalid token' })
    expect(mockLogout).not.toHaveBeenCalled() // logout asynchrone (import dynamique)

    await vi.advanceTimersByTimeAsync(0)
    expect(mockLogout).toHaveBeenCalledTimes(1)

    // Aucune reconnexion programmée
    const calls = wsConstructor.mock.calls.length
    vi.advanceTimersByTime(60000)
    expect(wsConstructor.mock.calls.length).toBe(calls)
  })

  it('épuisement des 3 tentatives → logout (comportement historique conservé)', async () => {
    wsService.connect('jwt-token')
    openAndAuthenticate()

    // 3 fermetures réseau consommées par des reconnexions SANS ré-auth
    // (auth_success) : les tentatives ne sont jamais remises à zéro.
    for (let i = 0; i < 3; i++) {
      mockWs.readyState = 3
      mockWs.onclose?.({ code: 1006 })
      vi.advanceTimersByTime(10000) // au-delà du délai plafonné (8 s + jitter)
      mockWs.readyState = 1
      mockWs.onopen?.() // la nouvelle socket s'ouvre puis retombe
    }

    // 4ᵉ fermeture : politique épuisée → logout, plus aucun retry
    mockWs.readyState = 3
    mockWs.onclose?.({ code: 1006 })
    await vi.advanceTimersByTimeAsync(0)
    expect(mockLogout).toHaveBeenCalledTimes(1)

    const calls = wsConstructor.mock.calls.length
    vi.advanceTimersByTime(60000)
    expect(wsConstructor.mock.calls.length).toBe(calls)
  })

  it('reconnexion → abonnements serveur rétablis (re-souscription automatique)', () => {
    wsService.connect('jwt-token')
    openAndAuthenticate()

    // Abonnement serveur (topic system_event) — le auth passerait aussi par
    // send(), mais authenticate() appelle ws.send directement : sent = [auth…, subscribe]
    wsService.send('subscribe', { event_type: 'system_event' })
    const firstSocketSent = [...mockWs.sent]

    // Coupure réseau puis reconnexion (mockWs re-pointe sur la nouvelle socket)
    mockWs.readyState = 3
    mockWs.onclose?.({ code: 1006 })
    vi.advanceTimersByTime(1250)
    openAndAuthenticate()

    // Le subscribe initial a été rejoué sur la nouvelle socket (en plus de son auth)
    const resubscribeSent = mockWs.sent.filter((raw) => raw.includes('system_event'))
    expect(resubscribeSent).toHaveLength(1)
    expect(JSON.parse(resubscribeSent[0] as string)).toEqual({
      type: 'subscribe',
      data: { event_type: 'system_event' },
    })
    expect(firstSocketSent.some((raw) => raw.includes('system_event'))).toBe(true)
  })

  it('unsubscribe retire le topic de la re-souscription', () => {
    wsService.connect('jwt-token')
    openAndAuthenticate()

    wsService.send('subscribe', { event_type: 'system_event' })
    wsService.send('unsubscribe', { event_type: 'system_event' })

    mockWs.readyState = 3
    mockWs.onclose?.({ code: 1006 })
    vi.advanceTimersByTime(1250)
    openAndAuthenticate()

    // Sur la NOUVELLE socket : aucun system_event rejoué (unsubscribed avant coupure)
    const resubscribeSent = mockWs.sent.filter((raw) => raw.includes('system_event'))
    expect(resubscribeSent).toHaveLength(0)
  })

  it('disconnect() arrête la politique : plus de reconnexion automatique', () => {
    wsService.connect('jwt-token')
    openAndAuthenticate()

    wsService.disconnect()
    mockWs.readyState = 3
    mockWs.onclose?.({ code: 1006 })

    const calls = wsConstructor.mock.calls.length
    vi.advanceTimersByTime(60000)
    expect(wsConstructor.mock.calls.length).toBe(calls)
    expect(mockLogout).not.toHaveBeenCalled()
  })

  it('dispatch les événements connus aux callbacks (non-régression)', () => {
    const cb = vi.fn()
    wsService.on('DEPLOYMENT_STATUS_CHANGED', cb)

    wsService.connect('jwt-token')
    openAndAuthenticate()
    emitServerMessage('DEPLOYMENT_STATUS_CHANGED', { deployment_id: 'dep-1' })

    expect(cb).toHaveBeenCalledWith({ deployment_id: 'dep-1' })
  })
})
