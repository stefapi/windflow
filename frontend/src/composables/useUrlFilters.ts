/**
 * useUrlFilters Composable
 *
 * Synchronizes filter state with URL query parameters for shareable links.
 * Supports debounce for search input and type-safe filter values.
 */

import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export type ContainerStatusFilter = 'all' | 'running' | 'stopped' | 'error'

export interface ContainerFilters {
  status: ContainerStatusFilter
  target: string
  search: string
}

const STATUS_OPTIONS: ContainerStatusFilter[] = ['all', 'running', 'stopped', 'error']

/**
 * Parse status from query param with fallback to default
 */
function parseStatus(value: string | null): ContainerStatusFilter {
  if (value && STATUS_OPTIONS.includes(value as ContainerStatusFilter)) {
    return value as ContainerStatusFilter
  }
  return 'all'
}

/**
 * Composable for managing container filters with URL synchronization
 */
export function useUrlFilters(debounceMs: number = 300) {
  const route = useRoute()
  const router = useRouter()

  // Filter state initialized from URL
  const status = ref<ContainerStatusFilter>(parseStatus(route.query['status'] as string))
  const target = ref<string>((route.query['target'] as string) || '')
  const search = ref<string>((route.query['search'] as string) || '')

  // Debounce tracking
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null
  const debouncedSearch = ref(search.value)

  // Computed: check if any filter is active
  const hasActiveFilters = computed(() => {
    return status.value !== 'all' || target.value !== '' || search.value !== ''
  })

  // Computed: get filters as object
  const filters = computed<ContainerFilters>(() => ({
    status: status.value,
    target: target.value,
    search: debouncedSearch.value,
  }))

  // Update URL with current filters
  function updateUrl(): void {
    const query: Record<string, string> = {}

    if (status.value !== 'all') {
      query['status'] = status.value
    }
    if (target.value) {
      query['target'] = target.value
    }
    if (search.value) {
      query['search'] = search.value
    }

    router.replace({
      path: route.path,
      query,
    }).catch(() => {
      // Ignore navigation errors (e.g., same route)
    })
  }

  // Watch for filter changes and update URL
  watch([status, target], () => {
    updateUrl()
  })

  // Debounced search update
  watch(search, (newValue) => {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer)
    }
    searchDebounceTimer = setTimeout(() => {
      debouncedSearch.value = newValue
      updateUrl()
    }, debounceMs)
  })

  // Reset all filters
  function resetFilters(): void {
    status.value = 'all'
    target.value = ''
    search.value = ''
    debouncedSearch.value = ''
  }

  // Set filters programmatically
  function setFilters(newFilters: Partial<ContainerFilters>): void {
    if (newFilters.status !== undefined) {
      status.value = newFilters.status
    }
    if (newFilters.target !== undefined) {
      target.value = newFilters.target
    }
    if (newFilters.search !== undefined) {
      search.value = newFilters.search
      debouncedSearch.value = newFilters.search
    }
  }

  return {
    // Filter refs
    status,
    target,
    search,
    debouncedSearch,
    // Computed
    hasActiveFilters,
    filters,
    // Actions
    resetFilters,
    setFilters,
  }
}

export type UseUrlFiltersReturn = ReturnType<typeof useUrlFilters>
