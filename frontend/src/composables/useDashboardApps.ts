/**
 * useDashboardApps Composable
 *
 * Aggregates all apps (managed stacks, standalone containers, discovered items)
 * from the compute store into a flat list of AppCardData[] ready for display
 * in the dashboard grid. Sorted alphabetically by displayName.
 *
 * @see docs/general_specs/11-UI-mockups.md — Écran 1 (Dashboard)
 */

import { computed } from 'vue'
import { useComputeStore } from '@/stores'
import {
  stackToAppCards,
  discoveredToAppCards,
  standaloneToAppCard,
  type AppCardData,
} from '@/components/compute/helpers'

export function useDashboardApps() {
  const computeStore = useComputeStore()

  /** Aggregated and sorted list of all apps */
  const apps = computed<AppCardData[]>(() => {
    const allApps: AppCardData[] = []

    // Managed stacks → each service becomes a card
    for (const stack of computeStore.managedStacks) {
      allApps.push(...stackToAppCards(stack))
    }

    // Discovered items → each service becomes a card
    for (const item of computeStore.discoveredItems) {
      allApps.push(...discoveredToAppCards(item))
    }

    // Standalone containers → one card each
    for (const container of computeStore.standaloneContainers) {
      allApps.push(standaloneToAppCard(container))
    }

    // Sort alphabetically by displayName
    allApps.sort((a, b) => a.displayName.localeCompare(b.displayName))

    return allApps
  })

  /** Whether apps are currently being loaded */
  const loading = computed(() => computeStore.loading)

  /** Error from the compute store, if any */
  const error = computed(() => computeStore.error)

  /**
   * Fetch the global compute view and aggregate apps.
   * @param orgId — Optional organization ID to filter by
   */
  async function fetchApps(orgId?: string): Promise<void> {
    await computeStore.fetchGlobal({ organization_id: orgId })
  }

  return {
    apps,
    loading,
    error,
    fetchApps,
  }
}
