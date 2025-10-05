import { defineStore } from 'pinia'
import { ref } from 'vue'
import { workflowsApi } from '@/services/api'
import type { Workflow, WorkflowCreate } from '@/types/api'

export const useWorkflowsStore = defineStore('workflows', () => {
  const workflows = ref<Workflow[]>([])
  const currentWorkflow = ref<Workflow | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchWorkflows(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await workflowsApi.list({ organization_id: organizationId })
      workflows.value = response.data.items
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch workflows'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkflow(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await workflowsApi.get(id)
      currentWorkflow.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch workflow'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createWorkflow(data: WorkflowCreate): Promise<Workflow> {
    loading.value = true
    error.value = null
    try {
      const response = await workflowsApi.create(data)
      workflows.value.unshift(response.data)
      return response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to create workflow'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateWorkflow(id: string, data: Partial<WorkflowCreate>): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await workflowsApi.update(id, data)
      const index = workflows.value.findIndex(w => w.id === id)
      if (index !== -1) workflows.value[index] = response.data
      if (currentWorkflow.value?.id === id) currentWorkflow.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to update workflow'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function deleteWorkflow(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await workflowsApi.delete(id)
      workflows.value = workflows.value.filter(w => w.id !== id)
      if (currentWorkflow.value?.id === id) currentWorkflow.value = null
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to delete workflow'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function executeWorkflow(id: string, params?: Record<string, unknown>): Promise<string> {
    loading.value = true
    error.value = null
    try {
      const response = await workflowsApi.execute(id, params)
      return response.data.execution_id
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to execute workflow'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    workflows,
    currentWorkflow,
    loading,
    error,
    fetchWorkflows,
    fetchWorkflow,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    executeWorkflow,
  }
})
