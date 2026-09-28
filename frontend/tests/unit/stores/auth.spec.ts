/**
 * Tests du store auth contre un backend enveloppé (STORY-126.3).
 * Le mock simule ce que voit le store APRÈS l'unwrap centralisé de
 * l'interceptor : `response.data` = contenu de l'enveloppe `data`.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/services/websocket', () => ({
  default: {
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
  wsService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
  },
}))

const mockLoginPayload = {
  access_token: 'jwt-token-123',
  refresh_token: 'refresh-token-456',
  token_type: 'bearer',
  expires_in: 3600,
  user: {
    id: 'user-1',
    username: 'admin',
    email: 'admin@windflow.local',
    is_superuser: true,
    organization_id: 'org-1',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
}

const { authApi } = await import('@/services/api')

describe('useAuthStore — enveloppes spec 09 (STORY-126.3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    vi.spyOn(authApi, 'login').mockResolvedValue({
      data: mockLoginPayload,
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {} as never,
    } as never)
  })

  it("stocke les tokens depuis la charge utile dépliée de l'enveloppe", async () => {
    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    await store.login({ username: 'admin', password: 'pass' })

    // response.data post-unwrap = payload de tokens — l'ancien niveau
    // d'accès (data.access_token) reste valide, preuve de transparence
    expect(store.token).toBe('jwt-token-123')
    expect(store.refreshToken).toBe('refresh-token-456')
    expect(store.user?.id).toBe('user-1')
    expect(store.isAuthenticated).toBe(true)

    expect(localStorage.getItem('access_token')).toBe('jwt-token-123')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-token-456')
  })

  it("propage l'erreur d'authentification sans stocker de token", async () => {
    vi.spyOn(authApi, 'login').mockRejectedValueOnce({
      response: {
        status: 401,
        data: { error: { code: 'INVALID_CREDENTIALS', message: 'Incorrect username or password' } },
      },
    })

    const { useAuthStore } = await import('@/stores/auth')
    const store = useAuthStore()

    await expect(store.login({ username: 'admin', password: 'wrong' })).rejects.toBeTruthy()

    expect(store.token).toBeNull()
    expect(store.isAuthenticated).toBe(false)
  })
})
