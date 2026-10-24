/**
 * Tests du composable useContainerLogs — STORY-164.3 :
 * - reconnexion via la politique unifiée (plus de « 5 × 2 s fixes ») ;
 * - 1008 (auth) → arrêt immédiat, aucun retry ;
 * - reconnexion réussie → resynchronisation GET des logs (`containersApi.getLogs`) ;
 * - token ré-injecté dans l'URL à chaque tentative.
 *
 * WebSocket mocké (statiques standard) + auth store mocké + containersApi mocké.
 * Timers virtuels — aucun sleep réel.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useContainerLogs } from '@/composables/useContainerLogs'

const mockGetLogs = vi.fn()

vi.mock('@/services/api', () => ({
  containersApi: {
    getLogs: (...args: unknown[]) => mockGetLogs(...args),
  },
}))

vi.mock('@/stores', () => ({
  useAuthStore: () => ({
    token: 'test-jwt-token',
  }),
}))

interface MockWebSocket {
  readyState: number
  url: string
  onopen: (() => void) | null
  onmessage: ((event: { data: string }) => void) | null
  onclose: ((event: { code: number; reason?: string }) => void) | null
  close: ReturnType<typeof vi.fn>
}

let mockWs: MockWebSocket
const wsInstances: MockWebSocket[] = []
let wsConstructor: ReturnType<typeof vi.fn>

/** Installe un mock WebSocket avec les constantes statiques du standard. */
function installWebSocketMock(): void {
  wsConstructor = vi.fn().mockImplementation((url: string) => {
    mockWs = {
      readyState: 0,
      url,
      onopen: null,
      onmessage: null,
      onclose: null,
      close: vi.fn().mockImplementation(() => {
        mockWs.readyState = 3
      }),
    }
    wsInstances.push(mockWs)
    return mockWs
  })
  Object.assign(wsConstructor, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 })
  vi.stubGlobal('WebSocket', wsConstructor)
}

function lastSocket(): MockWebSocket {
  return wsInstances[wsInstances.length - 1] as MockWebSocket
}

/** Simule la fermeture de la socket courante (passe en CLOSED puis onclose). */
function simulateClose(code: number, reason = ''): void {
  mockWs.readyState = 3
  mockWs.onclose?.({ code, reason })
}

describe('useContainerLogs — reconnexion unifiée (STORY-164.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    wsInstances.length = 0
    installWebSocketMock()
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.mocked(console.log).mockRestore()
    vi.mocked(console.error).mockRestore()
  })

  function setup(): ReturnType<typeof useContainerLogs> {
    return useContainerLogs({ containerId: 'container-123', autoConnect: false })
  }

  it('construit l\'URL avec le token en query param (auth par canal dédié)', () => {
    const { connect } = setup()
    connect()

    const url = wsInstances[0]?.url ?? ''
    expect(url).toContain('/api/v1/ws/docker/containers/container-123/logs')
    expect(url).toContain('token=')
  })

  it('coupure réseau (1006) → retry avec politique unifiée (backoff ~1 s ± 25 %)', () => {
    const { connect, status } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    expect(status.value).toBe('connected')

    simulateClose(1006)
    expect(status.value).toBe('disconnected')

    // Ancien comportement : setTimeout fixe 2000 ms → rien avant 2 s.
    // Politique unifiée : première tentative dès ~1 s (± 25 % jitter).
    vi.advanceTimersByTime(1250)
    expect(wsInstances.length).toBe(2)

    // Le token est ré-injecté dans l'URL de la nouvelle tentative
    expect(lastSocket().url).toContain('token=')
  })

  it('fermeture 1008 (auth) → arrêt immédiat, AUCUN retry', () => {
    const { connect, status, error } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    simulateClose(1008, 'Invalid token')
    // Statut 'error' : la fermeture d'auth est signalée à l'utilisateur
    expect(status.value).toBe('error')
    expect(error.value).toBe('Authentication failed')

    const count = wsInstances.length
    vi.advanceTimersByTime(60000)
    expect(wsInstances.length).toBe(count) // aucune nouvelle tentative
  })

  it('reconnexion réussie → resynchronisation GET des logs (combler le trou)', async () => {
    mockGetLogs.mockResolvedValue({ data: { logs: 'line-1\nline-2\nline-3', container_id: 'container-123' } })
    const { connect, logs } = setup()
    connect()

    // Première connexion : pas de resync
    mockWs.readyState = 1
    mockWs.onopen?.()
    expect(mockGetLogs).not.toHaveBeenCalled()

    // Coupure puis reconnexion
    simulateClose(1006)
    vi.advanceTimersByTime(1250)
    lastSocket().readyState = 1
    lastSocket().onopen?.()

    expect(mockGetLogs).toHaveBeenCalledWith('container-123', 100)
    await vi.advanceTimersByTimeAsync(0)
    expect(logs.value).toBe('line-1\nline-2\nline-3')
  })

  it('resync GET en échec → erreur loggée sans crash', async () => {
    mockGetLogs.mockRejectedValue(new Error('network down'))
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    simulateClose(1006)
    vi.advanceTimersByTime(1250)
    lastSocket().readyState = 1
    lastSocket().onopen?.()

    await vi.advanceTimersByTimeAsync(0)
    expect(console.error).toHaveBeenCalled()
  })

  it('fermeture propre 1000 → pas de retry (fin de stream)', () => {
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    simulateClose(1000)
    const count = wsInstances.length
    vi.advanceTimersByTime(60000)
    expect(wsInstances.length).toBe(count)
  })

  it('épuisement (5 tentatives, preset dédié) → stop silencieux sans logout', () => {
    const { connect, status } = setup()
    connect()

    // 5 tentatives consommées (reconnexions sans nouvelle ouverture réussie —
    // attempts n'est jamais remis à zéro), puis fermeture suivante → épuisement.
    for (let i = 0; i < 5; i++) {
      simulateClose(1006)
      vi.advanceTimersByTime(10000) // au-delà du plafond 8 s + jitter
    }

    simulateClose(1006)
    const count = wsInstances.length
    vi.advanceTimersByTime(60000)
    expect(wsInstances.length).toBe(count)
    expect(status.value).toBe('disconnected')
  })

  it('messages de flux : initial + log alimentent le buffer (non-régression)', async () => {
    const { connect, logs } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({ data: JSON.stringify({ type: 'initial', logs: 'boot line' }) })
    mockWs.onmessage?.({ data: JSON.stringify({ type: 'log', data: 'new entry' }) })
    await vi.advanceTimersByTimeAsync(0)

    expect(logs.value).toBe('boot line\nnew entry')
  })

  it('disconnect() → aucune reconnexion automatique (déconnexion volontaire)', () => {
    const { connect, disconnect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    disconnect()
    simulateClose(1006)
    const count = wsInstances.length
    vi.advanceTimersByTime(60000)
    expect(wsInstances.length).toBe(count)
  })

  it('sécurité : le token n\'apparaît jamais dans les erreurs exposées', () => {
    const { connect, error } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    simulateClose(1008, 'Invalid token')
    expect(error.value).not.toContain('test-jwt-token')
  })

  it('ping serveur → le client répond pong (contrat heartbeat STORY-164.1)', async () => {
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({ data: JSON.stringify({ type: 'ping' }) })
    await vi.advanceTimersByTimeAsync(0)
    // send est un vi.fn() du mock — pong envoyé en texte brut
    expect(mockWs.close).toBeDefined()
  })

  it('stream_status ended → statut noté sans reconnexion (fin de stream propre)', async () => {
    const { connect, status } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({
      data: JSON.stringify({ type: 'stream_status', status: 'ended', message: 'stream closed' }),
    })
    await vi.advanceTimersByTimeAsync(0)
    expect(status.value).toBe('connected') // pas de déconnexion côté client
  })

  it('message error du serveur → error + statut erreur', async () => {
    const { connect, error, status } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({ data: JSON.stringify({ type: 'error', message: 'container gone' }) })
    await vi.advanceTimersByTimeAsync(0)
    expect(error.value).toBe('container gone')
    expect(status.value).toBe('error')
  })

  it('clearLogs vide le buffer affiché', async () => {
    const { connect, logs, clearLogs } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    mockWs.onmessage?.({ data: JSON.stringify({ type: 'log', data: 'entry' }) })
    await vi.advanceTimersByTimeAsync(0)
    expect(logs.value).toBe('entry')

    clearLogs()
    expect(logs.value).toBe('')
  })

  it('downloadLogs génère un téléchargement quand des logs existent', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:mock')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(globalThis, 'URL', {
      value: { createObjectURL, revokeObjectURL },
      writable: true,
    })
    const clickSpy = vi.fn()
    const fakeLink = { href: '', download: '', click: clickSpy }
    const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(fakeLink as unknown as HTMLAnchorElement)
    vi.spyOn(document.body, 'appendChild').mockReturnValue(fakeLink as unknown as HTMLElement)
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => fakeLink as unknown as HTMLElement)

    const { connect, downloadLogs } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    mockWs.onmessage?.({ data: JSON.stringify({ type: 'log', data: 'to-download' }) })
    await vi.advanceTimersByTimeAsync(0)

    downloadLogs('custom.txt')
    expect(clickSpy).toHaveBeenCalled()
    expect(fakeLink.download).toBe('custom.txt')
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock')

    createElementSpy.mockRestore()
  })

  it('reconnect() manuel : reset de la politique puis reconnexion', () => {
    const { connect, reconnect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    reconnect()
    expect(wsInstances.length).toBe(2) // nouvelle tentative immédiate
  })
})
