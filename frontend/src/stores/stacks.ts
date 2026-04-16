import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { stacksApi } from '@/services/api'
import type { Stack, StackCreate, StackUpdate } from '@/types/api'

export const useStacksStore = defineStore('stacks', () => {
  const stacks = ref<Stack[]>([])
  const currentStack = ref<Stack | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Computed: active stacks (not archived)
  const activeStacks = computed(() => stacks.value.filter(s => !s.is_archived))

  // Computed: archived stacks
  const archivedStacks = computed(() => stacks.value.filter(s => s.is_archived))

  async function fetchStacks(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await stacksApi.list({ organization_id: organizationId })
      // Backend returns List[StackResponse] directly, not wrapped in {items:[]}
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      stacks.value = (response.data as any).items || response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch stacks'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchStack(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await stacksApi.get(id)
      currentStack.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch stack'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createStack(data: StackCreate): Promise<Stack> {
    loading.value = true
    error.value = null
    try {
      const response = await stacksApi.create(data)
      stacks.value.unshift(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to create stack'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateStack(id: string, data: StackUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await stacksApi.update(id, data)
      const index = stacks.value.findIndex(s => s.id === id)
      if (index !== -1) stacks.value[index] = response.data
      if (currentStack.value?.id === id) currentStack.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to update stack'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteStack(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await stacksApi.delete(id)
      stacks.value = stacks.value.filter(s => s.id !== id)
      if (currentStack.value?.id === id) currentStack.value = null
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to delete stack'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function archiveStack(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await stacksApi.archive(id)
      const stack = stacks.value.find(s => s.id === id)
      if (stack) {
        stack.is_archived = true
        stack.archived_at = new Date().toISOString()
      }
      if (currentStack.value?.id === id) {
        currentStack.value = { ...currentStack.value, is_archived: true, archived_at: new Date().toISOString() }
      }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to archive stack'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function unarchiveStack(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await stacksApi.unarchive(id)
      const stack = stacks.value.find(s => s.id === id)
      if (stack) {
        stack.is_archived = false
        stack.archived_at = null
      }
      if (currentStack.value?.id === id) {
        currentStack.value = { ...currentStack.value, is_archived: false, archived_at: null }
      }
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to unarchive stack'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    stacks,
    currentStack,
    loading,
    error,
    activeStacks,
    archivedStacks,
    fetchStacks,
    fetchStack,
    createStack,
    updateStack,
    deleteStack,
    archiveStack,
    unarchiveStack,
  }
})
