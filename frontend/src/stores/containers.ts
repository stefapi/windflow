/**
 * Containers Store
 * Pinia store for Docker containers management
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { containersApi } from '@/services/api'
import type { Container, ContainerState } from '@/types/api'

export const useContainersStore = defineStore('containers', () => {
  // State
  const containers = ref<Container[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentContainer = ref<Container | null>(null)

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

  async function startContainer(id: string): Promise<void> {
    try {
      await containersApi.start(id)
      // Update local state
      const container = containers.value.find(c => c.id === id)
      if (container) {
        container.state = 'running'
        container.status = 'Up'
      }
    } catch (err) {
      throw err
    }
  }

  async function stopContainer(id: string, timeout: number = 10): Promise<void> {
    try {
      await containersApi.stop(id, timeout)
      // Update local state
      const container = containers.value.find(c => c.id === id)
      if (container) {
        container.state = 'exited'
        container.status = 'Exited'
      }
    } catch (err) {
      throw err
    }
  }

  async function restartContainer(id: string, timeout: number = 10): Promise<void> {
    try {
      await containersApi.restart(id, timeout)
      // Update local state
      const container = containers.value.find(c => c.id === id)
      if (container) {
        container.state = 'running'
        container.status = 'Restarted'
      }
    } catch (err) {
      throw err
    }
  }

  async function removeContainer(id: string, force: boolean = false): Promise<void> {
    try {
      await containersApi.remove(id, force)
      // Remove from local state
      containers.value = containers.value.filter(c => c.id !== id)
    } catch (err) {
      throw err
    }
  }

  async function getContainerLogs(id: string, tail: number = 100): Promise<string> {
    try {
      const response = await containersApi.getLogs(id, tail)
      return response.data.logs
    } catch (err) {
      throw err
    }
  }

  function $reset(): void {
    containers.value = []
    loading.value = false
    error.value = null
    currentContainer.value = null
  }

  return {
    // State
    containers,
    loading,
    error,
    currentContainer,
    // Getters
    runningContainers,
    stoppedContainers,
    containersByState,
    // Actions
    fetchContainers,
    fetchContainer,
    startContainer,
    stopContainer,
    restartContainer,
    removeContainer,
    getContainerLogs,
    $reset,
  }
})
