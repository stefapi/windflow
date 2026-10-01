/**
 * Tests de l'interceptor axios — unwrap centralisé des enveloppes spec 09.
 * STORY-126.3 : réponses 2xx `{"data": ..., "message": ...}` → payload nu ;
 * erreurs `{"error": {code, message}}` lues via `.error.message` (fallback
 * `detail` legacy).
 * STORY-128 : enveloppes paginées `{data, pagination}` — la liste est dépliée
 * dans `response.data` ET le bloc `pagination` reste accessible via
 * `response.pagination` pour les stores/UI.
 *
 * Stratégie : adaptateur axios mocké (roule la vraie chaîne d'interceptors
 * de l'instance `http`, y compris le retry 401 qui passe par axios.request).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import http from '@/services/http'
import type { ApiEnvelope } from '@/types/api'

// Le module http logge l'URL de base au chargement — muet en test
vi.spyOn(console, 'log').mockImplementation(() => {})

type MockResponder = (config: { url?: string; method?: string }) => {
  status: number
  data: unknown
}

function mockAdapter(responder: MockResponder): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(http.defaults as any).adapter = (config: { url?: string; method?: string }) => {
    const r = responder(config)
    const response = {
      status: r.status,
      data: r.data,
      statusText: r.status >= 400 ? 'Error' : 'OK',
      headers: {},
      config,
    }
    // Comportement axios natif (settle) : non-2xx → rejet AxiosError
    if (r.status >= 400) {
      return Promise.reject(new AxiosError('Request failed', String(r.status), config, null, response))
    }
    return Promise.resolve(response)
  }
}

describe('http interceptor — unwrap enveloppes spec 09 (STORY-126.3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    localStorage.clear()
  })

  afterEach(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(http.defaults as any).adapter = undefined
    localStorage.clear()
  })

  it('déplie l\'enveloppe {"data", "message"} d\'une réponse 2xx objet', async () => {
    const payload = { id: 'stack-1', name: 'nextcloud' }
    const envelope: ApiEnvelope<typeof payload> = { data: payload, message: null }
    mockAdapter(() => ({ status: 200, data: envelope }))

    const response = await http.get('/stacks/stack-1')
    expect(response.data).toEqual(payload)
  })

  it("déplie l'enveloppe d'une liste (data = tableau)", async () => {
    const payload = [{ id: 'a' }, { id: 'b' }]
    mockAdapter(() => ({ status: 200, data: { data: payload, message: '2 items' } }))

    const response = await http.get('/stacks')
    expect(response.data).toEqual(payload)
  })

  it("déplie l'enveloppe paginée (data + pagination)", async () => {
    const items = [{ id: 'u1' }]
    mockAdapter(() => ({
      status: 200,
      data: { data: items, pagination: { page: 1, per_page: 20, total: 1, pages: 1 } },
    }))

    const response = await http.get('/users')
    expect(response.data).toEqual(items)
  })

  it('STORY-128 : préserve le bloc pagination accessible sur la réponse dépliée', async () => {
    const items = [{ id: 'u1' }, { id: 'u2' }]
    const pagination = { page: 2, per_page: 20, total: 25, pages: 2 }
    mockAdapter(() => ({ status: 200, data: { data: items, pagination, message: null } }))

    const response = await http.get('/users')
    expect(response.data).toEqual(items)
    expect(response.pagination).toEqual(pagination)
    expect(response.pagination?.total).toBe(25)
  })

  it('STORY-128 : pas de bloc pagination sur une enveloppe standard', async () => {
    const payload = { id: 'stack-1' }
    mockAdapter(() => ({ status: 200, data: { data: payload, message: null } }))

    const response = await http.get('/stacks/stack-1')
    expect(response.data).toEqual(payload)
    expect(response.pagination).toBeUndefined()
  })

  it('STORY-128 : liste vide paginée — data: [] + méta exactes', async () => {
    mockAdapter(() => ({
      status: 200,
      data: { data: [], pagination: { page: 1, per_page: 20, total: 0, pages: 0 } },
    }))

    const response = await http.get('/workflows')
    expect(response.data).toEqual([])
    expect(response.pagination).toEqual({ page: 1, per_page: 20, total: 0, pages: 0 })
  })

  it('laisse intact un corps non-enveloppé (compat transition)', async () => {
    const raw = { items: [{ id: 'x' }], total: 1, skip: 0, limit: 20 }
    mockAdapter(() => ({ status: 200, data: raw }))

    const response = await http.get('/deployments')
    expect(response.data).toEqual(raw)
  })

  it('laisse intacte une liste nue (tableau racine)', async () => {
    const raw = [{ id: 'a' }]
    mockAdapter(() => ({ status: 200, data: raw }))

    const response = await http.get('/targets')
    expect(response.data).toEqual(raw)
  })

  it('laisse intact un corps null (204 sans contenu)', async () => {
    mockAdapter(() => ({ status: 204, data: null }))

    const response = await http.delete('/stacks/stack-1')
    expect(response.data).toBeNull()
  })

  it('expose error.message / error.code sur une erreur enveloppée (sans crash)', async () => {
    // token présent : évite le logout-immédiat du 401-sans-token (404 ici,
    // mais le request-interceptor exige un token pour ne pas déclencher
    // la branche no-token qui consomme l'erreur avant l'assert)
    localStorage.setItem(
      'access_token',
      // JWT factice à 3 segments, exp loin dans le futur
      `header.${btoa(JSON.stringify({ exp: Date.now() / 1000 + 3600 }))}.sig`
    )
    mockAdapter(() => ({
      status: 404,
      data: {
        error: { code: 'NOT_FOUND', message: 'Stack not found' },
        correlation_id: 'corr-123',
      },
    }))

    const error = await http.get('/stacks/unknown').catch((e: unknown) => e)
    const axiosError = error as { response?: { status: number; data: { error: { code: string; message: string } } } }
    expect(axiosError.response?.status).toBe(404)
    expect(axiosError.response?.data.error.message).toBe('Stack not found')
    expect(axiosError.response?.data.error.code).toBe('NOT_FOUND')
    expect(console.error).toHaveBeenCalled()
  })

  it('lit encore detail en fallback (transition pré-126.2, sans crash)', async () => {
    localStorage.setItem('access_token', `header.${btoa(JSON.stringify({ exp: Date.now() / 1000 + 3600 }))}.sig`)
    mockAdapter(() => ({ status: 500, data: { detail: 'boom legacy' } }))

    const error = await http.get('/stacks').catch((e: unknown) => e)
    const axiosError = error as { response?: { status: number } }
    expect(axiosError.response?.status).toBe(500)
    expect(console.error).toHaveBeenCalledWith('Server error:', 'boom legacy', '')
  })
})
