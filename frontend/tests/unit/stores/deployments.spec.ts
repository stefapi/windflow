/**
 * Tests du store deployments contre un backend enveloppé (STORY-126.3).
 * Après unwrap centralisé, `response.data` est soit une liste, soit
 * `{items, total, skip, limit}` (PaginatedResponse post-unwrap).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/services/websocket', () => ({
  deploymentEvents: { onEvent: vi.fn(), offEvent: vi.fn() },
  default: { connect: vi.fn(), disconnect: vi.fn() },
}))

const mockDeployment = {
  id: 'dep-1',
  name: 'deploy-nextcloud',
  stack_id: 'stack-1',
  stack_name: 'nextcloud',
  status: 'running',
  organization_id: 'org-1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const { deploymentsApi } = await import('@/services/api')

function asResponse<T>(data: T) {
  return { data, status: 200, statusText: 'OK', headers: {}, config: {} as never } as never
}

describe('useDeploymentsStore — enveloppes spec 09 (STORY-126.3)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it("lit data.items d'une liste paginée enveloppée (post-unwrap)", async () => {
    // Ce que l'interceptor livre au store : le contenu de `data`,
    // ici une PaginatedResponse {items, total, skip, limit}
    vi.spyOn(deploymentsApi, 'list').mockResolvedValue(asResponse({ items: [mockDeployment], total: 1, skip: 0, limit: 20 }))

    const { useDeploymentsStore } = await import('@/stores/deployments')
    const store = useDeploymentsStore()

    await store.fetchDeployments()

    expect(store.deployments).toHaveLength(1)
    expect(store.deployments[0]?.id).toBe('dep-1')
  })

  it('retourne une liste vide si data est vide (post-unwrap, pas de crash)', async () => {
    vi.spyOn(deploymentsApi, 'list').mockResolvedValue(asResponse({ items: [], total: 0, skip: 0, limit: 20 }))

    const { useDeploymentsStore } = await import('@/stores/deployments')
    const store = useDeploymentsStore()

    await store.fetchDeployments()

    expect(store.deployments).toEqual([])
  })

  it("expose l'erreur sans crash si la liste échoue (erreur enveloppée)", async () => {
    vi.spyOn(deploymentsApi, 'list').mockRejectedValueOnce(new Error('Request failed with status code 500'))

    const { useDeploymentsStore } = await import('@/stores/deployments')
    const store = useDeploymentsStore()

    await expect(store.fetchDeployments()).rejects.toBeTruthy()
    expect(store.error).toBeTruthy()
  })
})
