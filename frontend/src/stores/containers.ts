/**
 * Containers Store
 * Pinia store for Docker containers management
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { containersApi } from '@/services/api'
import type { Container, ContainerDetail, ContainerState } from '@/types/api'

export const useContainersStore = defineStore('containers', () => {
  // State
  const containers = ref<Container[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentContainer = ref<Container | null>(null)
  const containerDetail = ref<ContainerDetail | null>(null)
  const detailLoading = ref(false)

  // Getters
  const runningContainers = computed(() =>
    containers.value.filter(c => c.state === 'running')
  )

  const stoppedContainers = computed(() =>
    containers.value.filter(c => c.state !== 'running')
  )

  const containersByState = computed(() => {
    const result: Record<ContainerState, Container[]> = {
      running: [],
      exited: [],
      paused: [],
      restarting: [],
      created: [],
      dead: [],
    }
    for (const container of containers.value) {
      if (result[container.state]) {
        result[container.state].push(container)
      }
    }
    return result
  })

  // Actions
  async function fetchContainers(all: boolean = true): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await containersApi.list(all)
      containers.value = response.data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement des containers'
      error.value = errorMessage
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchContainer(id: string): Promise<Container> {
    loading.value = true
    error.value = null

    try {
      const response = await containersApi.get(id)
      currentContainer.value = response.data
      return response.data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement du container'
      error.value = errorMessage
      throw err
    } finally {
      loading.value = false
    }
  }

  async function inspectContainer(id: string): Promise<ContainerDetail> {
    detailLoading.value = true
    error.value = null

    try {
      const response = await containersApi.inspect(id)
      containerDetail.value = response.data
      return response.data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement des détails du container'
      error.value = errorMessage
      throw err
    } finally {
      detailLoading.value = false
    }
  }

  async function startContainer(id: string): Promise<void> {
    await containersApi.start(id)
    // Update local state
    const container = containers.value.find(c => c.id === id)
    if (container) {
      container.state = 'running'
      container.status = 'Up'
    }
  }

  async function stopContainer(id: string, timeout: number = 10): Promise<void> {
    await containersApi.stop(id, timeout)
    // Update local state
    const container = containers.value.find(c => c.id === id)
    if (container) {
      container.state = 'exited'
      container.status = 'Exited'
    }
  }

  async function restartContainer(id: string, timeout: number = 10): Promise<void> {
    await containersApi.restart(id, timeout)
    // Update local state
    const container = containers.value.find(c => c.id === id)
    if (container) {
      container.state = 'running'
      container.status = 'Restarted'
    }
  }

  async function removeContainer(id: string, force: boolean = false): Promise<void> {
    await containersApi.remove(id, force)
    // Remove from local state
    containers.value = containers.value.filter(c => c.id !== id)
  }

  async function getContainerLogs(id: string, tail: number = 100): Promise<string> {
    const response = await containersApi.getLogs(id, tail)
    return response.data.logs
  }

  // Batch actions for multiple containers
  async function startContainers(ids: string[]): Promise<{ success: string[]; failed: string[] }> {
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        await containersApi.start(id)
        // Update local state
        const container = containers.value.find(c => c.id === id)
        if (container) {
          container.state = 'running'
          container.status = 'Up'
        }
        return id
      })
    )

    const success: string[] = []
    const failed: string[] = []

    results.forEach((result, index) => {
      const id = ids[index]
      if (id !== undefined) {
        if (result.status === 'fulfilled') {
          success.push(id)
        } else {
          failed.push(id)
        }
      }
    })

    return { success, failed }
  }

  async function stopContainers(ids: string[], timeout: number = 10): Promise<{ success: string[]; failed: string[] }> {
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        await containersApi.stop(id, timeout)
        // Update local state
        const container = containers.value.find(c => c.id === id)
        if (container) {
          container.state = 'exited'
          container.status = 'Exited'
        }
        return id
      })
    )

    const success: string[] = []
    const failed: string[] = []

    results.forEach((result, index) => {
      const id = ids[index]
      if (id !== undefined) {
        if (result.status === 'fulfilled') {
          success.push(id)
        } else {
          failed.push(id)
        }
      }
    })

    return { success, failed }
  }

  async function restartContainers(ids: string[], timeout: number = 10): Promise<{ success: string[]; failed: string[] }> {
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        await containersApi.restart(id, timeout)
        // Update local state
        const container = containers.value.find(c => c.id === id)
        if (container) {
          container.state = 'running'
          container.status = 'Restarted'
        }
        return id
      })
    )

    const success: string[] = []
    const failed: string[] = []

    results.forEach((result, index) => {
      const id = ids[index]
      if (id !== undefined) {
        if (result.status === 'fulfilled') {
          success.push(id)
        } else {
          failed.push(id)
        }
      }
    })

    return { success, failed }
  }

  async function removeContainers(ids: string[], force: boolean = false): Promise<{ success: string[]; failed: string[] }> {
    const results = await Promise.allSettled(
      ids.map(async (id) => {
        await containersApi.remove(id, force)
        return id
      })
    )

    const success: string[] = []
    const failed: string[] = []

    results.forEach((result, index) => {
      const id = ids[index]
      if (id !== undefined) {
        if (result.status === 'fulfilled') {
          success.push(id)
        } else {
          failed.push(id)
        }
      }
    })

    // Remove successful deletions from local state
    containers.value = containers.value.filter(c => !success.includes(c.id))

    return { success, failed }
  }

  function $reset(): void {
    containers.value = []
    loading.value = false
    error.value = null
    currentContainer.value = null
    containerDetail.value = null
    detailLoading.value = false
  }

  return {
    // State
    containers,
    loading,
    error,
    currentContainer,
    containerDetail,
    detailLoading,
    // Getters
    runningContainers,
    stoppedContainers,
    containersByState,
    // Actions
    fetchContainers,
    fetchContainer,
    inspectContainer,
    startContainer,
    stopContainer,
    restartContainer,
    removeContainer,
    getContainerLogs,
    // Batch actions
    startContainers,
    stopContainers,
    restartContainers,
    removeContainers,
    $reset,
  }
})
