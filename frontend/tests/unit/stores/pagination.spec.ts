/**
 * Tests des stores contre les enveloppes paginées STORY-128.
 *
 * Après unwrap centralisé (http.ts), `response.data` est la liste (nouveau
 * format paginé) et `response.pagination` porte {page, per_page, total,
 * pages}. Fallback de transition : `{items}` legacy et liste nue tolérés.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/services/websocket', () => ({
  deploymentEvents: { onEvent: vi.fn(), offEvent: vi.fn() },
  default: { connect: vi.fn(), disconnect: vi.fn() },
}))

const { stacksApi, deploymentsApi } = await import('@/services/api')

/** Simule une AxiosResponse post-unwrap : liste + pagination rattachée. */
function asPaginatedResponse<T>(items: T[], pagination?: { page: number; per_page: number; total: number; pages: number }) {
  return { data: items, pagination, status: 200, statusText: 'OK', headers: {}, config: {} as never } as never
}

describe('useStacksStore — enveloppes paginées (STORY-128)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('alimente le store depuis la liste dépliée et expose les métadonnées', async () => {
    const stacks = [
      { id: 'st-1', name: 'nextcloud', is_archived: false },
      { id: 'st-2', name: 'pihole', is_archived: false },
    ]
    vi.spyOn(stacksApi, 'list').mockResolvedValue(asPaginatedResponse(stacks, { page: 1, per_page: 20, total: 25, pages: 2 }))

    const { useStacksStore } = await import('@/stores/stacks')
    const store = useStacksStore()

    await store.fetchStacks()

    expect(store.stacks).toHaveLength(2)
    expect(store.stacks[0]?.id).toBe('st-1')
    expect(store.pagination?.total).toBe(25)
    expect(store.pagination?.pages).toBe(2)
  })

  it('liste vide paginée → store vide, méta total=0 pages=0', async () => {
    vi.spyOn(stacksApi, 'list').mockResolvedValue(asPaginatedResponse([], { page: 1, per_page: 20, total: 0, pages: 0 }))

    const { useStacksStore } = await import('@/stores/stacks')
    const store = useStacksStore()

    await store.fetchStacks()

    expect(store.stacks).toEqual([])
    expect(store.pagination?.total).toBe(0)
    expect(store.pagination?.pages).toBe(0)
  })

  it('fallback transition : body {items} legacy toléré, pagination null', async () => {
    vi.spyOn(stacksApi, 'list').mockResolvedValue({ data: { items: [{ id: 'st-legacy', name: 'old', is_archived: false }] }, status: 200, statusText: 'OK', headers: {}, config: {} as never } as never)

    const { useStacksStore } = await import('@/stores/stacks')
    const store = useStacksStore()

    await store.fetchStacks()

    expect(store.stacks).toHaveLength(1)
    expect(store.stacks[0]?.id).toBe('st-legacy')
    expect(store.pagination).toBeNull()
  })
})

describe('useDeploymentsStore — enveloppes paginées (STORY-128)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it("lit la liste dépliée + expose total/pages pour l'UI", async () => {
    const deployments = [
      { id: 'dep-1', name: 'd1', stack_id: 's1', stack_name: 'nextcloud', status: 'running', organization_id: 'org-1', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      { id: 'dep-2', name: 'd2', stack_id: 's1', stack_name: 'nextcloud', status: 'completed', organization_id: 'org-1', created_at: '2026-01-02T00:00:00Z', updated_at: '2026-01-02T00:00:00Z' },
    ]
    vi.spyOn(deploymentsApi, 'list').mockResolvedValue(asPaginatedResponse(deployments, { page: 1, per_page: 20, total: 120, pages: 6 }))

    const { useDeploymentsStore } = await import('@/stores/deployments')
    const store = useDeploymentsStore()

    await store.fetchDeployments()

    expect(store.deployments).toHaveLength(2)
    expect(store.pagination?.total).toBe(120)
    expect(store.pagination?.pages).toBe(6)
  })

  it('fallback transition : {items} legacy (pré-128) toujours lu sans crash', async () => {
    vi.spyOn(deploymentsApi, 'list').mockResolvedValue({ data: { items: [], total: 0, skip: 0, limit: 20 }, status: 200, statusText: 'OK', headers: {}, config: {} as never } as never)

    const { useDeploymentsStore } = await import('@/stores/deployments')
    const store = useDeploymentsStore()

    await store.fetchDeployments()

    expect(store.deployments).toEqual([])
    expect(store.pagination).toBeNull()
  })
})
