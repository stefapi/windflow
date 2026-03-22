/**
 * useUsers Composable
 * Handles CRUD operations for users
 */

import { ref, type Ref } from 'vue'
import { usersApi } from '@/services/api'
import type { User, UserCreate, UserUpdate } from '@/types/api'
import { ElMessage } from 'element-plus'

export interface UseUsersOptions {
  autoFetch?: boolean
}

export interface BulkOperationResult {
  success: string[]
  failed: string[]
  message: string
}

export interface UseUsersReturn {
  users: Ref<User[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  total: Ref<number>
  fetchUsers: (skip?: number, limit?: number) => Promise<void>
  getUser: (id: string) => Promise<User | null>
  createUser: (data: UserCreate) => Promise<User | null>
  updateUser: (id: string, data: UserUpdate) => Promise<User | null>
  updatePassword: (id: string, password: string) => Promise<boolean>
  deleteUser: (id: string) => Promise<boolean>
  deleteUsers: (ids: string[]) => Promise<BulkOperationResult>
  assignOrganization: (userIds: string[], organizationId: string) => Promise<BulkOperationResult>
  refresh: () => Promise<void>
}

const DEFAULT_LIMIT = 100

/**
 * Composable for managing users
 *
 * @param options - Configuration options
 * @returns User data and CRUD methods
 */
export function useUsers(options: UseUsersOptions = {}): UseUsersReturn {
  const { autoFetch = true } = options

  // State
  const users = ref<User[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  /**
   * Fetch all users
   */
  async function fetchUsers(skip = 0, limit = DEFAULT_LIMIT): Promise<void> {
    if (loading.value) return

    loading.value = true
    error.value = null

    try {
      const response = await usersApi.list({ skip, limit })
      // Backend returns paginated response
      users.value = response.data.items
      total.value = response.data.total
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la récupération des utilisateurs'
      error.value = errorMessage
      ElMessage.error(errorMessage)
    } finally {
      loading.value = false
    }
  }

  /**
   * Get a single user by ID
   */
  async function getUser(id: string): Promise<User | null> {
    try {
      const response = await usersApi.get(id)
      return response.data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la récupération de l\'utilisateur'
      ElMessage.error(errorMessage)
      return null
    }
  }

  /**
   * Create a new user
   */
  async function createUser(data: UserCreate): Promise<User | null> {
    try {
      const response = await usersApi.create(data)
      const newUser = response.data
      users.value.push(newUser)
      total.value++
      ElMessage.success('Utilisateur créé avec succès')
      return newUser
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la création de l\'utilisateur'
      ElMessage.error(errorMessage)
      return null
    }
  }

  /**
   * Update an existing user
   */
  async function updateUser(id: string, data: UserUpdate): Promise<User | null> {
    try {
      const response = await usersApi.update(id, data)
      const updatedUser = response.data
      const index = users.value.findIndex(u => u.id === id)
      if (index !== -1) {
        users.value[index] = updatedUser
      }
      ElMessage.success('Utilisateur mis à jour avec succès')
      return updatedUser
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la mise à jour de l\'utilisateur'
      ElMessage.error(errorMessage)
      return null
    }
  }

  /**
   * Delete a user
   */
  async function deleteUser(id: string): Promise<boolean> {
    try {
      await usersApi.delete(id)
      users.value = users.value.filter(u => u.id !== id)
      total.value--
      ElMessage.success('Utilisateur supprimé avec succès')
      return true
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la suppression de l\'utilisateur'
      ElMessage.error(errorMessage)
      return false
    }
  }

  /**
   * Update user password
   */
  async function updatePassword(id: string, password: string): Promise<boolean> {
    try {
      await usersApi.update(id, { password })
      ElMessage.success('Mot de passe modifié avec succès')
      return true
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la modification du mot de passe'
      ElMessage.error(errorMessage)
      return false
    }
  }

  /**
   * Delete multiple users in bulk
   */
  async function deleteUsers(ids: string[]): Promise<BulkOperationResult> {
    try {
      const response = await usersApi.bulkDelete(ids)
      const result = response.data as BulkOperationResult

      // Remove deleted users from local state
      users.value = users.value.filter(u => !result.success.includes(u.id))
      total.value -= result.success.length

      if (result.failed.length === 0) {
        ElMessage.success(result.message)
      } else {
        ElMessage.warning(result.message)
      }

      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la suppression groupée'
      ElMessage.error(errorMessage)
      return { success: [], failed: ids, message: errorMessage }
    }
  }

  /**
   * Assign multiple users to an organization in bulk
   */
  async function assignOrganization(userIds: string[], organizationId: string): Promise<BulkOperationResult> {
    try {
      const response = await usersApi.bulkAssignOrganization(userIds, organizationId)
      const result = response.data as BulkOperationResult

      // Update organization_id for affected users in local state
      for (const userId of result.success) {
        const index = users.value.findIndex(u => u.id === userId)
        if (index !== -1) {
          users.value[index] = { ...users.value[index], organization_id: organizationId } as unknown as User
        }
      }

      if (result.failed.length === 0) {
        ElMessage.success(result.message)
      } else {
        ElMessage.warning(result.message)
      }

      return result
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de l\'affectation groupée'
      ElMessage.error(errorMessage)
      return { success: [], failed: userIds, message: errorMessage }
    }
  }

  /**
   * Refresh users list
   */
  async function refresh(): Promise<void> {
    await fetchUsers()
  }

  // Auto-fetch if enabled
  if (autoFetch) {
    fetchUsers()
  }

  return {
    users,
    loading,
    error,
    total,
    fetchUsers,
    getUser,
    createUser,
    updateUser,
    updatePassword,
    deleteUser,
    deleteUsers,
    assignOrganization,
    refresh,
  }
}
