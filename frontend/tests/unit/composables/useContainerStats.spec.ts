/**
 * Tests du composable useContainerStats — STORY-164.3 :
 * - reconnexion via la politique unifiée (remplace le « 5 × 2 s fixes ») ;
 * - 1008 (auth) → arrêt immédiat, aucun retry ;
 * - reconnexion réussie → resynchronisation GET du snapshot stats
 *   (`containersApi.getStats`) ;
 * - token présent dans l'URL de chaque tentative.
 *
 * WebSocket mocké (statiques standard) + auth store mocké + containersApi mocké
 * + timers virtuels.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useContainerStats } from '@/composables/useContainerStats'

const mockGetStats = vi.fn()

vi.mock('@/services/api', () => ({
  containersApi: {
    getStats: (...args: unknown[]) => mockGetStats(...args),
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

describe('useContainerStats — reconnexion unifiée (STORY-164.3)', () => {
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

  function setup(): ReturnType<typeof useContainerStats> {
    return useContainerStats({ containerId: 'container-123', autoConnect: false })
  }

  it('construit l\'URL avec le token en query param', () => {
    const { connect } = setup()
    connect()

    const url = wsInstances[0]?.url ?? ''
    expect(url).toContain('/api/v1/ws/docker/containers/container-123/stats')
    expect(url).toContain('token=')
  })

  it('coupure réseau (1006) → retry avec la politique unifiée (~1 s ± 25 %)', () => {
    const { connect, status } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    expect(status.value).toBe('connected')

    simulateClose(1006)
    vi.advanceTimersByTime(1250)
    expect(wsInstances.length).toBe(2)
    expect(lastSocket().url).toContain('token=') // token ré-injecté
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
    expect(wsInstances.length).toBe(count)
  })

  it('reconnexion réussie → resynchronisation GET du snapshot stats', async () => {
    mockGetStats.mockResolvedValue({
      data: {
        container_id: 'container-123',
        timestamp: '2026-10-23T22:00:00Z',
        cpu: { percent: 12.5 },
        memory: { percent: 40, used: 1024, limit: 4096 },
        network: { rx_bytes: 100, tx_bytes: 200 },
        block_io: { read_bytes: 10, write_bytes: 20 },
      },
    })
    const { connect, stats } = setup()
    connect()

    // Première connexion : pas de resync
    mockWs.readyState = 1
    mockWs.onopen?.()
    expect(mockGetStats).not.toHaveBeenCalled()

    // Coupure puis reconnexion
    simulateClose(1006)
    vi.advanceTimersByTime(1250)
    lastSocket().readyState = 1
    lastSocket().onopen?.()

    expect(mockGetStats).toHaveBeenCalledWith('container-123')
    await vi.advanceTimersByTimeAsync(0)
    expect(stats.value?.cpu_percent).toBe(12.5)
    expect(stats.value?.timestamp).toBe('2026-10-23T22:00:00Z')
  })

  it('resync GET sans timestamp → snapshot non remplacé', async () => {
    mockGetStats.mockResolvedValue({ data: { container_id: 'container-123' } })
    const { connect, stats } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    simulateClose(1006)
    vi.advanceTimersByTime(1250)
    lastSocket().readyState = 1
    lastSocket().onopen?.()

    await vi.advanceTimersByTimeAsync(0)
    expect(stats.value).toBeNull() // pas d'écrasement avec un snapshot vide
  })

  it('resync GET en échec → erreur loggée sans crash', async () => {
    mockGetStats.mockRejectedValue(new Error('network down'))
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

  it('fermeture propre 1000 → pas de retry', () => {
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    simulateClose(1000)
    const count = wsInstances.length
    vi.advanceTimersByTime(60000)
    expect(wsInstances.length).toBe(count)
  })

  it('épuisement (5 tentatives, preset dédié) → stop silencieux', () => {
    const { connect, status } = setup()
    connect()

    for (let i = 0; i < 5; i++) {
      simulateClose(1006)
      vi.advanceTimersByTime(10000) // au-delà du plafond 8 s + jitter
    }

    // 6ᵉ fermeture : politique épuisée → stop, plus AUCUNE nouvelle socket
    // (statut : 'connecting' — la 6ᵉ tentative était en cours à sa fermeture).
    simulateClose(1006)
    const count = wsInstances.length
    vi.advanceTimersByTime(60000)
    expect(wsInstances.length).toBe(count)
    expect(['disconnected', 'connecting']).toContain(status.value)
  })

  it('messages de flux : stats alimente l\'état et l\'historique (non-régression)', async () => {
    const { connect, stats, history } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({
      data: JSON.stringify({
        type: 'stats',
        timestamp: '2026-10-23T22:00:01Z',
        cpu: { percent: 50 },
        memory: { percent: 60, used: 2048, limit: 4096 },
        network: { rx_bytes: 1, tx_bytes: 2 },
        block_io: { read_bytes: 3, write_bytes: 4 },
      }),
    })
    await vi.advanceTimersByTimeAsync(0)

    expect(stats.value?.cpu_percent).toBe(50)
    expect(history.value).toHaveLength(1)
  })

  it('disconnect() → aucune reconnexion automatique', () => {
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

  it('initial container_status non-running → déconnexion immédiate (non-régression)', async () => {
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({
      data: JSON.stringify({ type: 'initial', container_status: 'exited' }),
    })
    await vi.advanceTimersByTimeAsync(0)
    expect(mockWs.close).toHaveBeenCalled()
  })

  it('stream_status container_stopped → déconnexion (non-régression)', async () => {
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({
      data: JSON.stringify({ type: 'stream_status', status: 'container_stopped' }),
    })
    await vi.advanceTimersByTimeAsync(0)
    expect(mockWs.close).toHaveBeenCalled()
  })

  it('message error du serveur → error + statut erreur (non-régression)', async () => {
    const { connect, error, status } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({ data: JSON.stringify({ type: 'error', message: 'docker down' }) })
    await vi.advanceTimersByTimeAsync(0)
    expect(error.value).toBe('docker down')
    expect(status.value).toBe('error')
  })

  it('fetchOnce : reçoit une stats puis se déconnecte (mode manuel)', async () => {
    const { connect, fetchOnce, status } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    // (re)connexion du mode manuel
    fetchOnce()
    mockWs.readyState = 1
    mockWs.onopen?.()

    mockWs.onmessage?.({
      data: JSON.stringify({
        type: 'stats',
        timestamp: '2026-10-23T22:00:02Z',
        cpu: { percent: 5 },
        memory: { percent: 10, used: 512, limit: 4096 },
        network: { rx_bytes: 1, tx_bytes: 1 },
        block_io: { read_bytes: 1, write_bytes: 1 },
      }),
    })
    await vi.advanceTimersByTimeAsync(0)
    expect(mockWs.close).toHaveBeenCalled() // déconnexion après réception
  })

  it('clearHistory vide l\'historique (non-régression)', async () => {
    const { connect, history, clearHistory } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.onopen?.()
    mockWs.onmessage?.({
      data: JSON.stringify({
        type: 'stats',
        timestamp: '2026-10-23T22:00:03Z',
        cpu: { percent: 1 },
        memory: { percent: 1, used: 1, limit: 2 },
        network: { rx_bytes: 0, tx_bytes: 0 },
        block_io: { read_bytes: 0, write_bytes: 0 },
      }),
    })
    await vi.advanceTimersByTimeAsync(0)
    expect(history.value).toHaveLength(1)

    clearHistory()
    expect(history.value).toHaveLength(0)
  })

  it('heartbeat périodique : ping JSON envoyé au serveur (contrat 164.1)', async () => {
    const sendSpy = vi.fn()
    const { connect } = setup()
    connect()
    mockWs.readyState = 1
    mockWs.send = sendSpy
    mockWs.onopen?.()

    await vi.advanceTimersByTimeAsync(30000)
    expect(sendSpy).toHaveBeenCalledWith(JSON.stringify({ type: 'ping' }))
  })

  it('autoConnect: true → connexion immédiate si token présent', () => {
    useContainerStats({ containerId: 'container-123', autoConnect: true })
    expect(wsInstances.length).toBe(1)
  })
})
