import { defineStore } from 'pinia'
import { ref } from 'vue'
import { templatesApi } from '@/services/api'
import type { Template } from '@/types/api'

export const useMarketplaceStore = defineStore('marketplace', () => {
  const templates = ref<Template[]>([])
  const currentTemplate = ref<Template | null>(null)
  const categories = ref<string[]>([])
  const popularTemplates = ref<Template[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchTemplates(params?: {
    category?: string
    tags?: string[]
    search?: string
  }): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await templatesApi.list(params)
      templates.value = response.data.items
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch templates'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchTemplate(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await templatesApi.get(id)
      currentTemplate.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch template'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchCategories(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await templatesApi.categories()
      categories.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch categories'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchPopularTemplates(limit = 10): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await templatesApi.popular(limit)
      popularTemplates.value = response.data
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch popular templates'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function downloadTemplate(id: string): Promise<string> {
    loading.value = true
    error.value = null
    try {
      const response = await templatesApi.download(id)
      return response.data.stack_id
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to download template'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function rateTemplate(id: string, rating: number): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await templatesApi.rate(id, rating)
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to rate template'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    templates,
    currentTemplate,
    categories,
    popularTemplates,
    loading,
    error,
    fetchTemplates,
    fetchTemplate,
    fetchCategories,
    fetchPopularTemplates,
    downloadTemplate,
    rateTemplate,
  }
})
