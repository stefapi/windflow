/**
 * Store Pinia pour la marketplace WindFlow.
 *
 * Gère l'état global de la marketplace (stacks, catégories, filtres).
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { marketplaceService } from '@/services/marketplaceService'
import type { MarketplaceStack, StackDetails } from '@/types/marketplace'
import { ElMessage } from 'element-plus'

export const useMarketplaceStore = defineStore('marketplace', () => {
  // État
  const stacks = ref<MarketplaceStack[]>([])
  const currentStack = ref<StackDetails | null>(null)
  const categories = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Filtres
  const selectedCategory = ref<string>('')
  const searchQuery = ref('')
  const currentPage = ref(0)
  const pageSize = ref(20)
  const totalStacks = ref(0)

  // Getters
  const filteredStacks = computed(() => {
    let filtered = [...stacks.value]

    if (selectedCategory.value) {
      filtered = filtered.filter(s => s.category === selectedCategory.value)
    }

    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      filtered = filtered.filter(s =>
        s.name.toLowerCase().includes(query) ||
        s.description?.toLowerCase().includes(query) ||
        s.tags.some(tag => tag.toLowerCase().includes(query))
      )
    }

    return filtered
  })

  const totalPages = computed(() =>
    Math.ceil(totalStacks.value / pageSize.value)
  )

  const hasMoreStacks = computed(() =>
    currentPage.value < totalPages.value - 1
  )

  // Actions
  async function fetchStacks(params?: {
    category?: string
    search?: string
    reset?: boolean
  }) {
    if (params?.reset) {
      currentPage.value = 0
      stacks.value = []
    }

    loading.value = true
    error.value = null

    try {
      const response = await marketplaceService.listStacks({
        category: params?.category || selectedCategory.value || undefined,
        search: params?.search || searchQuery.value || undefined,
        skip: currentPage.value * pageSize.value,
        limit: pageSize.value
      })

      if (params?.reset) {
        stacks.value = response.data
      } else {
        stacks.value.push(...response.data)
      }

      totalStacks.value = response.total

    } catch (err: any) {
      error.value = err.message || 'Erreur lors du chargement des stacks'
      ElMessage.error(error.value)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (!loading.value && hasMoreStacks.value) {
      currentPage.value++
      await fetchStacks()
    }
  }

  async function fetchStackDetails(stackId: string) {
    loading.value = true
    error.value = null

    try {
      currentStack.value = await marketplaceService.getStackDetails(stackId)
      return currentStack.value
    } catch (err: any) {
      error.value = err.message || 'Erreur lors du chargement des détails'
      ElMessage.error(error.value)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchCategories() {
    try {
      categories.value = await marketplaceService.getCategories()
    } catch (err: any) {
      console.error('Erreur lors du chargement des catégories:', err)
    }
  }

  async function deployStack(
    stackId: string,
    targetId: string,
    configuration: Record<string, any>,
    name?: string
  ) {
    loading.value = true
    error.value = null

    try {
      const response = await marketplaceService.deployStack(stackId, {
        target_id: targetId,
        configuration,
        name
      })

      ElMessage.success('Déploiement lancé avec succès !')
      return response
    } catch (err: any) {
      error.value = err.message || 'Erreur lors du déploiement'
      ElMessage.error(error.value)
      throw err
    } finally {
      loading.value = false
    }
  }

  async function installStack(stackId: string) {
    loading.value = true
    error.value = null

    try {
      const installedStack = await marketplaceService.installStack(stackId)
      ElMessage.success(`Stack "${installedStack.name}" installé dans votre organisation !`)
      return installedStack
    } catch (err: any) {
      error.value = err.message || "Erreur lors de l'installation"
      ElMessage.error(error.value)
      throw err
    } finally {
      loading.value = false
    }
  }

  function setCategory(category: string) {
    selectedCategory.value = category
    fetchStacks({ reset: true })
  }

  function setSearch(query: string) {
    searchQuery.value = query
    fetchStacks({ reset: true })
  }

  function clearFilters() {
    selectedCategory.value = ''
    searchQuery.value = ''
    fetchStacks({ reset: true })
  }

  function reset() {
    stacks.value = []
    currentStack.value = null
    categories.value = []
    selectedCategory.value = ''
    searchQuery.value = ''
    currentPage.value = 0
    totalStacks.value = 0
    error.value = null
  }

  return {
    // État
    stacks,
    currentStack,
    categories,
    loading,
    error,

    // Filtres
    selectedCategory,
    searchQuery,
    currentPage,
    pageSize,
    totalStacks,

    // Getters
    filteredStacks,
    totalPages,
    hasMoreStacks,

    // Actions
    fetchStacks,
    loadMore,
    fetchStackDetails,
    fetchCategories,
    deployStack,
    installStack,
    setCategory,
    setSearch,
    clearFilters,
    reset
  }
})
