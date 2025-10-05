import { defineStore } from 'pinia'
import { ref } from 'vue'
import { targetsApi } from '@/services/api'
import type { Target, TargetCreate, TargetUpdate } from '@/types/api'

export const useTargetsStore = defineStore('targets', () => {
  const targets = ref<Target[]>([])
  const currentTarget = ref<Target | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchTargets(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.list({ organization_id: organizationId })
      targets.value = response.data.items
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch targets'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchTarget(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.get(id)
      currentTarget.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createTarget(data: TargetCreate): Promise<Target> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.create(data)
      targets.value.unshift(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to create target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateTarget(id: string, data: TargetUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.update(id, data)
      const index = targets.value.findIndex(t => t.id === id)
      if (index !== -1) targets.value[index] = response.data
      if (currentTarget.value?.id === id) currentTarget.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to update target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteTarget(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await targetsApi.delete(id)
      targets.value = targets.value.filter(t => t.id !== id)
      if (currentTarget.value?.id === id) currentTarget.value = null
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to delete target'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function testConnection(id: string): Promise<{ success: boolean; message: string }> {
    loading.value = true
    error.value = null
    try {
      const response = await targetsApi.testConnection(id)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Connection test failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    targets,
    currentTarget,
    loading,
    error,
    fetchTargets,
    fetchTarget,
    createTarget,
    updateTarget,
    deleteTarget,
    testConnection,
  }
})
