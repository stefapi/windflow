import { ref } from 'vue'
import { defineStore } from 'pinia'
import { schedulesApi } from '@/services/api'
import type { ScheduledTask, ScheduledTaskCreate, ScheduledTaskUpdate } from '@/types/api'

export const useSchedulesStore = defineStore('schedules', () => {
  const tasks = ref<ScheduledTask[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchTasks(organizationId?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await schedulesApi.list(organizationId)
      tasks.value = response.data
    } catch (e: unknown) {
      error.value = 'Failed to fetch scheduled tasks'
    } finally {
      loading.value = false
    }
  }

  async function createTask(data: ScheduledTaskCreate): Promise<ScheduledTask> {
    const response = await schedulesApi.create(data)
    tasks.value.unshift(response.data)
    return response.data
  }

  async function updateTask(id: string, data: ScheduledTaskUpdate): Promise<ScheduledTask> {
    const response = await schedulesApi.update(id, data)
    const idx = tasks.value.findIndex(t => t.id === id)
    if (idx !== -1) tasks.value[idx] = response.data
    return response.data
  }

  async function deleteTask(id: string): Promise<void> {
    await schedulesApi.delete(id)
    tasks.value = tasks.value.filter(t => t.id !== id)
  }

  async function toggleTask(id: string): Promise<ScheduledTask> {
    const response = await schedulesApi.toggle(id)
    const idx = tasks.value.findIndex(t => t.id === id)
    if (idx !== -1) tasks.value[idx] = response.data
    return response.data
  }

  return {
    tasks,
    loading,
    error,
    fetchTasks,
    createTask,
    updateTask,
    deleteTask,
    toggleTask,
  }
})
