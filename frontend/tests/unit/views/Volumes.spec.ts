/**
 * Volumes.vue Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import Volumes from '@/views/Volumes.vue'
import type { VolumeResponse } from '@/types/api'

// Mock data
const mockVolumes: VolumeResponse[] = [
  {
    name: 'postgres-data',
    driver: 'local',
    mountpoint: '/var/lib/docker/volumes/postgres-data/_data',
    created_at: '2025-01-15T10:30:00Z',
    labels: {},
    scope: 'local',
  },
  {
    name: 'redis-cache',
    driver: 'local',
    mountpoint: '/var/lib/docker/volumes/redis-cache/_data',
    created_at: '2025-01-14T08:00:00Z',
    labels: { app: 'redis' },
    scope: 'local',
  },
  {
    name: 'app-uploads',
    driver: 'nfs',
    mountpoint: '/mnt/nfs/uploads',
    created_at: '2025-01-13T12:00:00Z',
    labels: {},
    scope: 'global',
  },
]

// Mock volumesApi.list, create, remove
const mockList = vi.fn()
const mockCreate = vi.fn()
const mockRemove = vi.fn()
vi.mock('@/services/api', () => ({
  volumesApi: {
    list: (...args: unknown[]) => mockList(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    remove: (...args: unknown[]) => mockRemove(...args),
  },
}))

// Mock ElMessage + ElMessageBox
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      ...((await vi.importActual('element-plus')) as Record<string, unknown>).ElMessage as Record<string, unknown>,
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
    },
    ElMessageBox: {
      confirm: vi.fn(),
    },
  }
})

// Helper to mount component
function mountComponent() {
  return mount(Volumes, {
    global: {
      plugins: [ElementPlus],
    },
  })
}

describe('Volumes.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockList.mockResolvedValue({ data: mockVolumes })
  })

  it('affiche les volumes dans le tableau après chargement', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(3)
  })

  it('affiche le nom, driver et mountpoint de chaque volume', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.text()).toContain('postgres-data')
    expect(wrapper.text()).toContain('redis-cache')
    expect(wrapper.text()).toContain('app-uploads')
    expect(wrapper.text()).toContain('local')
    expect(wrapper.text()).toContain('nfs')
  })

  it('filtre les volumes par nom', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('postgres')
    await flushPromises()

    const rows = wrapper.findAll('.el-table__body-wrapper tbody tr')
    expect(rows.length).toBe(1)
    expect(wrapper.text()).toContain('postgres-data')
    expect(wrapper.text()).not.toContain('redis-cache')
  })

  it('affiche el-empty si la liste est vide', async () => {
    mockList.mockResolvedValue({ data: [] })

    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.find('.el-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('Aucun volume trouvé')
  })

  it('ouvre le dialog au clic sur "Créer un volume"', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const createButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Créer un volume'))
    expect(createButton).toBeDefined()
    await createButton!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.el-dialog').exists()).toBe(true)
    expect(wrapper.text()).toContain('Créer un volume')
  })

  it('appelle volumesApi.create avec les bons paramètres', async () => {
    mockCreate.mockResolvedValue({ data: mockVolumes[0] })
    const wrapper = mountComponent()
    await flushPromises()

    // Ouvre le dialog
    const createButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Créer un volume'))
    await createButton!.trigger('click')
    await flushPromises()

    // Saisie nom + driver
    const inputs = wrapper.findAll('.el-dialog input')
    await inputs[0].setValue('my-new-volume')
    await inputs[1].setValue('local')
    await flushPromises()

    // Clique sur Créer
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Créer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockCreate).toHaveBeenCalledWith({ name: 'my-new-volume', driver: 'local' })
  })

  it('ferme le dialog et rafraîchit la liste après création réussie', async () => {
    mockCreate.mockResolvedValue({ data: mockVolumes[0] })
    const wrapper = mountComponent()
    await flushPromises()

    const createButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Créer un volume'))
    await createButton!.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('.el-dialog input')
    await inputs[0].setValue('test-volume')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Créer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    // La liste doit être rafraîchie (mockList appelée 2 fois : initial + refresh)
    expect(mockList).toHaveBeenCalledTimes(2)
  })

  it('affiche ElMessage.success après création réussie', async () => {
    const { ElMessage } = await import('element-plus')
    mockCreate.mockResolvedValue({ data: mockVolumes[0] })
    const wrapper = mountComponent()
    await flushPromises()

    const createButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Créer un volume'))
    await createButton!.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('.el-dialog input')
    await inputs[0].setValue('test-volume')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Créer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('test_create_volume_warns_if_name_empty', async () => {
    const { ElMessage } = await import('element-plus')
    const wrapper = mountComponent()
    await flushPromises()

    // Ouvre le dialog (name vide par défaut)
    const createButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Créer un volume'))
    await createButton!.trigger('click')
    await flushPromises()

    // Clique directement sur Créer sans saisir de nom
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Créer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.warning).toHaveBeenCalled()
    expect(mockCreate).not.toHaveBeenCalled()
  })

  it('test_create_volume_shows_error_on_failure', async () => {
    const { ElMessage } = await import('element-plus')
    mockCreate.mockRejectedValue(new Error('Erreur réseau'))
    const wrapper = mountComponent()
    await flushPromises()

    const createButton = wrapper.findAll('.card-header .el-button').find(b => b.text().includes('Créer un volume'))
    await createButton!.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('.el-dialog input')
    await inputs[0].setValue('fail-volume')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Créer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('test_no_sensitive_data_in_dom', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    expect(wrapper.html()).not.toContain('Bearer')
    expect(wrapper.html()).not.toContain('token')
    expect(wrapper.html()).not.toContain('password')
    expect(wrapper.html()).not.toContain('secret')
  })

  it('affiche ElMessage.error quand le chargement échoue', async () => {
    const { ElMessage } = await import('element-plus')
    mockList.mockRejectedValue(new Error('Network error'))

    mountComponent()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })

  // ── Tests de suppression ──────────────────────────────────────────────────

  it('affiche un bouton Supprimer pour chaque volume', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    expect(deleteButtons.length).toBe(3) // un par volume
  })

  it('ouvre le dialog de confirmation au clic sur Supprimer', async () => {
    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Supprimer le volume')
    expect(wrapper.text()).toContain('postgres-data')
  })

  it('appelle volumesApi.remove après confirmation', async () => {
    mockRemove.mockResolvedValue({})
    const wrapper = mountComponent()
    await flushPromises()

    // Ouvre le dialog pour le premier volume
    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    // Clique sur Supprimer dans le footer du dialog
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Supprimer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockRemove).toHaveBeenCalledWith('postgres-data', false)
  })

  it('transmet le flag force quand la checkbox est cochée', async () => {
    mockRemove.mockResolvedValue({})
    const wrapper = mountComponent()
    await flushPromises()

    // Ouvre le dialog
    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    // Coche la checkbox "Forcer la suppression"
    const checkbox = wrapper.find('.el-dialog .el-checkbox__input input')
    await checkbox.setValue(true)
    await flushPromises()

    // Confirme la suppression
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Supprimer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(mockRemove).toHaveBeenCalledWith('postgres-data', true)
  })

  it('affiche ElMessage.success après suppression réussie', async () => {
    const { ElMessage } = await import('element-plus')
    mockRemove.mockResolvedValue({})
    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Supprimer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('rafraîchit la liste après suppression réussie', async () => {
    mockRemove.mockResolvedValue({})
    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Supprimer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    // mockList appelé 2 fois : initial + refresh après suppression
    expect(mockList).toHaveBeenCalledTimes(2)
  })

  it("n'appelle pas volumesApi.remove si confirmation annulée", async () => {
    const wrapper = mountComponent()
    await flushPromises()

    // Ouvre le dialog
    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    // Clique sur Annuler
    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const cancelBtn = dialogButtons.find(b => b.text().includes('Annuler'))
    await cancelBtn!.trigger('click')
    await flushPromises()

    expect(mockRemove).not.toHaveBeenCalled()
  })

  it('affiche ElMessage.error si la suppression échoue', async () => {
    const { ElMessage } = await import('element-plus')
    mockRemove.mockRejectedValue(new Error('volume in use'))
    const wrapper = mountComponent()
    await flushPromises()

    const deleteButtons = wrapper.findAll('.el-button--danger')
    await deleteButtons[0].trigger('click')
    await flushPromises()

    const dialogButtons = wrapper.findAll('.el-dialog__footer .el-button')
    const confirmBtn = dialogButtons.find(b => b.text().includes('Supprimer'))
    await confirmBtn!.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalled()
  })
})
