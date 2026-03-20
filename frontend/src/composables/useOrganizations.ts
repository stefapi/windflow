/**
 * useOrganizations Composable
 * Handles CRUD operations for organizations
 */

import { ref, type Ref } from 'vue'
import { organizationsApi } from '@/services/api'
import type { Organization, OrganizationCreate, OrganizationUpdate } from '@/types/api'
import { ElMessage } from 'element-plus'

export interface UseOrganizationsOptions {
  autoFetch?: boolean
}

export interface BulkOperationResult {
  success: string[]
  failed: string[]
}

export interface UseOrganizationsReturn {
  organizations: Ref<Organization[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  total: Ref<number>
  fetchOrganizations: (skip?: number, limit?: number) => Promise<void>
  getOrganization: (id: string) => Promise<Organization | null>
  createOrganization: (data: OrganizationCreate) => Promise<Organization | null>
  updateOrganization: (id: string, data: OrganizationUpdate) => Promise<Organization | null>
  deleteOrganization: (id: string) => Promise<boolean>
  deleteOrganizations: (ids: string[]) => Promise<BulkOperationResult>
  refresh: () => Promise<void>
}

const DEFAULT_LIMIT = 100

/**
 * Composable for managing organizations
 *
 * @param options - Configuration options
 * @returns Organization data and CRUD methods
 */
export function useOrganizations(options: UseOrganizationsOptions = {}): UseOrganizationsReturn {
  const { autoFetch = true } = options

  // State
  const organizations = ref<Organization[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  /**
   * Fetch all organizations
   */
  async function fetchOrganizations(skip = 0, limit = DEFAULT_LIMIT): Promise<void> {
    if (loading.value) return

    loading.value = true
    error.value = null

    try {
      const response = await organizationsApi.list({ skip, limit })
      // Backend returns a simple array, not a paginated response
      const data = Array.isArray(response.data) ? response.data : response.data.items || []
      organizations.value = data
      total.value = Array.isArray(response.data) ? data.length : (response.data.total || data.length)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la récupération des organisations'
      error.value = errorMessage
      ElMessage.error(errorMessage)
    } finally {
      loading.value = false
    }
  }

  /**
   * Get a single organization by ID
   */
  async function getOrganization(id: string): Promise<Organization | null> {
    try {
      const response = await organizationsApi.get(id)
      return response.data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la récupération de l\'organisation'
      ElMessage.error(errorMessage)
      return null
    }
  }

  /**
   * Create a new organization
   */
  async function createOrganization(data: OrganizationCreate): Promise<Organization | null> {
    try {
      const response = await organizationsApi.create(data)
      const newOrg = response.data
      organizations.value.push(newOrg)
      total.value++
      ElMessage.success('Organisation créée avec succès')
      return newOrg
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la création de l\'organisation'
      ElMessage.error(errorMessage)
      return null
    }
  }

  /**
   * Update an existing organization
   */
  async function updateOrganization(id: string, data: OrganizationUpdate): Promise<Organization | null> {
    try {
      const response = await organizationsApi.update(id, data)
      const updatedOrg = response.data
      const index = organizations.value.findIndex(o => o.id === id)
      if (index !== -1) {
        organizations.value[index] = updatedOrg
      }
      ElMessage.success('Organisation mise à jour avec succès')
      return updatedOrg
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la mise à jour de l\'organisation'
      ElMessage.error(errorMessage)
      return null
    }
  }

  /**
   * Delete an organization
   */
  async function deleteOrganization(id: string): Promise<boolean> {
    try {
      await organizationsApi.delete(id)
      organizations.value = organizations.value.filter(o => o.id !== id)
      total.value--
      ElMessage.success('Organisation supprimée avec succès')
      return true
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la suppression de l\'organisation'
      ElMessage.error(errorMessage)
      return false
    }
  }

  /**
   * Delete multiple organizations (bulk operation)
   */
  async function deleteOrganizations(ids: string[]): Promise<BulkOperationResult> {
    const result: BulkOperationResult = { success: [], failed: [] }

    try {
      const response = await organizationsApi.bulkDelete(ids)
      result.success = response.data.success
      result.failed = response.data.failed

      // Remove successfully deleted organizations from local state
      organizations.value = organizations.value.filter(o => !result.success.includes(o.id))
      total.value -= result.success.length
    } catch (err) {
      // If the bulk endpoint fails, all operations failed
      result.failed = ids
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la suppression des organisations'
      ElMessage.error(errorMessage)
    }

    return result
  }

  /**
   * Refresh organizations list
   */
  async function refresh(): Promise<void> {
    await fetchOrganizations()
  }

  // Auto-fetch if enabled
  if (autoFetch) {
    fetchOrganizations()
  }

  return {
    organizations,
    loading,
    error,
    total,
    fetchOrganizations,
    getOrganization,
    createOrganization,
    updateOrganization,
    deleteOrganization,
    deleteOrganizations,
    refresh,
  }
}
