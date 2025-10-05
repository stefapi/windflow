/**
 * Deployments Store
 * Manages deployment state and operations
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { deploymentsApi } from '@/services/api'
import type { Deployment, DeploymentCreate } from '@/types/api'
import { deploymentEvents } from '@/services/websocket'

export const useDeploymentsStore = defineStore('deployments', () => {
  // State
  const deployments = ref<Deployment[]>([])
  const currentDeployment = ref<Deployment | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Actions
  async function fetchDeployments(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await deploymentsApi.list({ organization_id: organizationId })
      deployments.value = response.data.items
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch deployments'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchDeployment(id: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await deploymentsApi.get(id)
      currentDeployment.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch deployment'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createDeployment(data: DeploymentCreate): Promise<Deployment> {
    loading.value = true
    error.value = null

    try {
      const response = await deploymentsApi.create(data)
      const deployment = response.data
      deployments.value.unshift(deployment)
      return deployment
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to create deployment'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function cancelDeployment(id: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await deploymentsApi.cancel(id)
      updateDeploymentInList(response.data)
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to cancel deployment'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function retryDeployment(id: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await deploymentsApi.retry(id)
      deployments.value.unshift(response.data)
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to retry deployment'
      throw err
    } finally {
      loading.value = false
    }
  }

  function updateDeploymentInList(deployment: Deployment): void {
    const index = deployments.value.findIndex(d => d.id === deployment.id)
    if (index !== -1) {
      deployments.value[index] = deployment
    }
    if (currentDeployment.value?.id === deployment.id) {
      currentDeployment.value = deployment
    }
  }

  function subscribeToDeploymentLogs(deploymentId: string, callback: (log: string) => void): () => void {
    return deploymentEvents.subscribeToLogs(deploymentId, callback)
  }

  function subscribeToDeploymentStatus(deploymentId: string, callback: (status: string) => void): () => void {
    return deploymentEvents.subscribeToStatus(deploymentId, (status) => {
      // Update deployment status in store
      const deployment = deployments.value.find(d => d.id === deploymentId)
      if (deployment) {
        deployment.status = status as Deployment['status']
      }
      if (currentDeployment.value?.id === deploymentId) {
        currentDeployment.value.status = status as Deployment['status']
      }
      callback(status)
    })
  }

  return {
    deployments,
    currentDeployment,
    loading,
    error,
    fetchDeployments,
    fetchDeployment,
    createDeployment,
    cancelDeployment,
    retryDeployment,
    updateDeploymentInList,
    subscribeToDeploymentLogs,
    subscribeToDeploymentStatus,
  }
})
