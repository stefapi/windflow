<template>
  <div class="compute-view p-6">
    <!-- A. Header -->
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100">
          {{ modeStore.isAppMode ? 'Mes Apps' : 'Containers — vue globale' }}
        </h1>
        <p class="text-sm text-gray-500 mt-1">
          <template v-if="modeStore.isAppMode">
            {{ totalAppCount }} app{{ totalAppCount !== 1 ? 's' : '' }}
          </template>
          <template v-else>
            {{ computeStore.stats?.targets_count ?? 0 }} targets
            · {{ techCount }} technologies
          </template>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <el-button
          v-if="modeStore.isInfraMode"
          :type="!groupByTarget ? 'primary' : 'default'"
          size="small"
          @click="groupByTarget = false"
        >
          Tout
        </el-button>
        <el-button
          v-if="modeStore.isInfraMode"
          :type="groupByTarget ? 'primary' : 'default'"
          size="small"
          @click="groupByTarget = true"
        >
          Par machine
        </el-button>
        <el-button
          type="primary"
          size="small"
          @click="createDialogVisible = true"
        >
          {{ modeStore.isAppMode ? '+ Nouvelle App' : '+ Créer un container' }}
        </el-button>
        <el-button
          v-if="modeStore.isInfraMode"
          size="small"
          disabled
        >
          + Déployer
        </el-button>
      </div>
    </div>

    <!-- B. Barre de filtres -->
    <div class="filter-bar mb-6 flex flex-col gap-3">
      <!-- Ligne 1 : Type + Recherche -->
      <div class="flex flex-wrap items-center gap-3">
        <el-radio-group
          v-model="filterType"
          size="small"
        >
          <el-radio-button value="all">
            Tout
          </el-radio-button>
          <el-radio-button value="managed">
            {{ modeStore.isAppMode ? '● Mes Apps' : '● Stacks WindFlow' }}
          </el-radio-button>
          <el-radio-button value="discovered">
            {{ modeStore.isAppMode ? '● Apps détectées' : '● Discovered' }}
          </el-radio-button>
          <el-radio-button value="standalone">
            {{ modeStore.isAppMode ? '● Apps autonomes' : '● Standalone' }}
          </el-radio-button>
        </el-radio-group>

        <span class="text-gray-300">|</span>

        <el-input
          v-model="filterSearch"
          size="small"
          :placeholder="modeStore.isAppMode ? 'Rechercher une app...' : 'Rechercher...'"
          clearable
          style="width: 200px"
        />
      </div>

      <!-- Ligne 2 : Pills technologie + pills target (Mode Infra uniquement) -->
      <div
        v-if="modeStore.isInfraMode"
        class="flex flex-wrap items-center gap-2"
      >
        <span class="text-xs text-gray-500 font-semibold">Tech :</span>
        <span
          v-for="tech in availableTechnologies"
          :key="tech"
          class="pill"
          :class="activeTechnologies.includes(tech) ? 'text-accent bg-accent-light border-accent' : 'text-text-secondary bg-bg-secondary border-border hover:bg-bg-elevated'"
          @click="toggleTechnology(tech)"
        >
          {{ tech }}
        </span>

        <span class="text-xs text-gray-500 font-semibold ml-2">Host :</span>
        <span
          v-for="target in hostsStore.hosts"
          :key="target.id"
          class="pill"
          :class="activeTargets.includes(target.id) ? 'text-accent bg-accent-light border-accent' : 'text-text-secondary bg-bg-secondary border-border hover:bg-bg-elevated'"
          @click="toggleTarget(target.id)"
        >
          {{ target.name }}
        </span>
      </div>
    </div>

    <!-- C. Bandeau métriques (Mode Infra uniquement) -->
    <div
      v-if="modeStore.isInfraMode"
      class="mb-6"
    >
      <ComputeStatsBanner
        :stats="computeStore.stats"
        :loading="computeStore.statsLoading"
      />
    </div>

    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <!-- MODE APP : Cards par section                                          -->
    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <template v-if="modeStore.isAppMode">
      <!-- Section Mes Apps (managed) -->
      <div
        v-if="filterType === 'all' || filterType === 'managed'"
        class="section mb-6"
      >
        <div class="section-header border-b border-border py-2 mb-3 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded-sm bg-blue-600" />
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Mes Apps
            <span class="text-gray-400 font-normal">({{ filteredManagedCards.length }})</span>
          </span>
        </div>

        <div
          v-if="computeStore.loading"
          class="flex justify-center py-8"
        >
          <el-icon class="is-loading text-2xl text-blue-500">
            <Loading />
          </el-icon>
        </div>
        <el-empty
          v-else-if="filteredManagedCards.length === 0"
          description="Aucune app managée"
        />
        <div
          v-else
          class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          <AppCard
            v-for="card in filteredManagedCards"
            :key="card.id"
            :app="card"
            @refresh="refreshGlobal"
            @action="handleCardAction"
          />
        </div>
      </div>

      <!-- Section Apps autonomes (standalone) -->
      <div
        v-if="filterType === 'all' || filterType === 'standalone'"
        class="section mb-6"
      >
        <div class="section-header border-b border-border py-2 mb-3 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded-sm bg-gray-400" />
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Apps autonomes
            <span class="text-gray-400 font-normal">({{ filteredStandaloneCards.length }})</span>
          </span>
        </div>

        <div
          v-if="computeStore.loading"
          class="flex justify-center py-8"
        >
          <el-icon class="is-loading text-2xl text-blue-500">
            <Loading />
          </el-icon>
        </div>
        <el-empty
          v-else-if="filteredStandaloneCards.length === 0"
          description="Aucune app autonome"
        />
        <div
          v-else
          class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          <AppCard
            v-for="card in filteredStandaloneCards"
            :key="card.id"
            :app="card"
            @refresh="refreshGlobal"
            @action="handleCardAction"
          />
        </div>
      </div>

      <!-- Section Apps détectées (discovered) -->
      <div
        v-if="filterType === 'all' || filterType === 'discovered'"
        class="section mb-6"
      >
        <div class="section-header border-b border-border py-2 mb-3 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded-sm bg-orange-500" />
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Apps détectées
            <span class="text-gray-400 font-normal">({{ filteredDiscoveredCards.length }})</span>
          </span>
        </div>

        <div
          v-if="computeStore.loading"
          class="flex justify-center py-8"
        >
          <el-icon class="is-loading text-2xl text-blue-500">
            <Loading />
          </el-icon>
        </div>
        <el-empty
          v-else-if="filteredDiscoveredCards.length === 0"
          description="Aucune app détectée"
        />
        <div
          v-else
          class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
        >
          <AppCard
            v-for="card in filteredDiscoveredCards"
            :key="card.id"
            :app="card"
            @refresh="refreshGlobal"
            @action="handleCardAction"
          />
        </div>
      </div>
    </template>

    <!-- ═══════════════════════════════════════════════════════════════════════ -->
    <!-- MODE INFRA : Sections techniques (existant, inchangé)                 -->
    <!-- ═══════════════════════════════════════════════════════════════════════ -->

    <!-- Mode normal (D + E + F) -->
    <template v-if="modeStore.isInfraMode && !groupByTarget">
      <ManagedStacksSection
        v-if="filterType === 'all' || filterType === 'managed'"
        :stacks="visibleManagedStacks"
        :loading="computeStore.loading"
        @refresh="refreshGlobal"
        @copy-id="copyToClipboard"
      />

      <DiscoveredSection
        v-if="filterType === 'all' || filterType === 'discovered'"
        :items="visibleDiscoveredItems"
        :loading="computeStore.loading"
        @refresh="refreshGlobal"
        @adopt="openAdoptionWizard"
      />

      <StandaloneSection
        v-if="filterType === 'all' || filterType === 'standalone'"
        :containers="computeStore.standaloneContainers"
        :loading="computeStore.loading"
        @refresh="refreshGlobal"
      />
    </template>

    <!-- G. Mode "Par machine" -->
    <TargetGroupView
      v-if="modeStore.isInfraMode && groupByTarget"
      :groups="filteredTargetGroups"
      :loading="computeStore.loading"
    />

    <!-- Container Create Dialog -->
    <ContainerCreateDialog
      v-model="createDialogVisible"
      @created="handleContainerCreated"
    />

    <!-- Adoption Wizard -->
    <AdoptionWizard
      v-model="adoptionWizardVisible"
      :item-type="adoptionWizardItemType"
      :item-id="adoptionWizardItemId"
      :item-name="adoptionWizardItemName"
      @adopted="onAdopted"
    />

    <!-- H. Légende (Mode Infra uniquement) -->
    <div
      v-if="modeStore.isInfraMode"
      class="flex flex-wrap gap-6 mt-8 text-sm text-gray-500 border-t pt-4"
    >
      <span>
        <span class="inline-block w-3 h-3 rounded-sm bg-blue-600 mr-1" />
        Stack WindFlow — géré, éditable
      </span>
      <span>
        <span class="inline-block w-3 h-3 rounded-sm bg-orange-500 mr-1" />
        Discovered — observé, adoptable
      </span>
      <span>
        <span class="inline-block w-3 h-3 rounded-sm bg-gray-400 mr-1" />
        Standalone — container individuel géré
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Compute View — Orchestrator
 *
 * Lightweight orchestrator that delegates rendering to dedicated
 * sub-components for each compute section.
 *
 * In Mode App: displays apps as cards with non-technical vocabulary.
 * In Mode Infra: displays the technical compute view (tables, stats).
 */

import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useComputeStore, useHostsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { useModeStore } from '@/stores/mode'
import ComputeStatsBanner from '@/components/ComputeStatsBanner.vue'
import ContainerCreateDialog from '@/components/ContainerCreateDialog.vue'
import {
  ManagedStacksSection,
  DiscoveredSection,
  StandaloneSection,
  TargetGroupView,
  AdoptionWizard,
  AppCard,
  stackToAppCards,
  discoveredToAppCards,
  standaloneToAppCard,
} from '@/components/compute'
import type { ControlLevel, AdoptionResponse } from '@/types/api'
import type { AppCardData } from '@/components/compute/helpers'

const computeStore = useComputeStore()
const hostsStore = useHostsStore()
const authStore = useAuthStore()
const modeStore = useModeStore()

// ─── Filters ─────────────────────────────────────────────────────────────────
const groupByTarget = ref(false)
const filterType = ref<ControlLevel | 'all'>('all')
const activeTechnologies = ref<string[]>([])
const activeTargets = ref<string[]>([])
const filterSearch = ref('')

// Debounce 300ms on filterSearch
const debouncedSearch = ref('')
let debounceTimer: number | undefined

watch(filterSearch, (val) => {
  if (debounceTimer !== undefined) {
    window.clearTimeout(debounceTimer)
  }
  debounceTimer = window.setTimeout(() => {
    debouncedSearch.value = val
  }, 300)
})

// ─── Computed Data ────────────────────────────────────────────────────────────

const availableTechnologies = computed<string[]>(() => {
  const techs = new Set<string>()
  computeStore.managedStacks.forEach(s => techs.add(s.technology))
  computeStore.discoveredItems.forEach(d => techs.add(d.technology))
  return Array.from(techs)
})

const techCount = computed(() => availableTechnologies.value.length)

const visibleManagedStacks = computed(() =>
  computeStore.managedStacks,
)

const visibleDiscoveredItems = computed(() =>
  computeStore.discoveredItems,
)

const filteredTargetGroups = computed(() =>
  computeStore.targetGroups.map(group => ({
    ...group,
    stacks: group.stacks,
    discovered: group.discovered,
  })),
)

// ─── Mode App: App Card Computeds ────────────────────────────────────────────

/** All managed app cards from stacks */
const managedAppCards = computed<AppCardData[]>(() => {
  const cards: AppCardData[] = []
  for (const stack of computeStore.managedStacks) {
    cards.push(...stackToAppCards(stack))
  }
  return cards
})

/** All standalone app cards */
const standaloneAppCards = computed<AppCardData[]>(() =>
  computeStore.standaloneContainers.map(standaloneToAppCard),
)

/** All discovered app cards */
const discoveredAppCards = computed<AppCardData[]>(() => {
  const cards: AppCardData[] = []
  for (const item of computeStore.discoveredItems) {
    cards.push(...discoveredToAppCards(item))
  }
  return cards
})

/** Filter managed cards by search */
const filteredManagedCards = computed<AppCardData[]>(() => {
  if (!debouncedSearch.value) return managedAppCards.value
  const q = debouncedSearch.value.toLowerCase()
  return managedAppCards.value.filter(c =>
    c.displayName.toLowerCase().includes(q) ||
    c.statusLabel.toLowerCase().includes(q),
  )
})

/** Filter standalone cards by search */
const filteredStandaloneCards = computed<AppCardData[]>(() => {
  if (!debouncedSearch.value) return standaloneAppCards.value
  const q = debouncedSearch.value.toLowerCase()
  return standaloneAppCards.value.filter(c =>
    c.displayName.toLowerCase().includes(q) ||
    c.statusLabel.toLowerCase().includes(q),
  )
})

/** Filter discovered cards by search */
const filteredDiscoveredCards = computed<AppCardData[]>(() => {
  if (!debouncedSearch.value) return discoveredAppCards.value
  const q = debouncedSearch.value.toLowerCase()
  return discoveredAppCards.value.filter(c =>
    c.displayName.toLowerCase().includes(q) ||
    c.statusLabel.toLowerCase().includes(q),
  )
})

/** Total app count across all categories */
const totalAppCount = computed(() =>
  managedAppCards.value.length +
  standaloneAppCards.value.length +
  discoveredAppCards.value.length,
)

// ─── Filter Params ────────────────────────────────────────────────────────────

const filterParams = computed(() => ({
  type: filterType.value !== 'all' ? (filterType.value as ControlLevel) : undefined,
  technology: activeTechnologies.value.length > 0 ? activeTechnologies.value[0] : undefined,
  target_id: activeTargets.value.length > 0 ? activeTargets.value[0] : undefined,
  search: debouncedSearch.value || undefined,
}))

// ─── Toggle Helpers ───────────────────────────────────────────────────────────

function toggleTechnology(tech: string): void {
  const idx = activeTechnologies.value.indexOf(tech)
  if (idx === -1) {
    activeTechnologies.value.push(tech)
  } else {
    activeTechnologies.value.splice(idx, 1)
  }
}

function toggleTarget(targetId: string): void {
  const idx = activeTargets.value.indexOf(targetId)
  if (idx === -1) {
    activeTargets.value.push(targetId)
  } else {
    activeTargets.value.splice(idx, 1)
  }
}

// ─── Container Create Dialog ─────────────────────────────────────────────────

const createDialogVisible = ref(false)

function handleContainerCreated(): void {
  refreshGlobal()
}

// ─── Adoption Wizard ─────────────────────────────────────────────────────────

const adoptionWizardVisible = ref(false)
const adoptionWizardItemType = ref<'container' | 'composition' | 'helm_release'>('composition')
const adoptionWizardItemId = ref('')
const adoptionWizardItemName = ref('')

function openAdoptionWizard(discoveredId: string): void {
  // Trouver l'item dans les discovered items pour récupérer le type et le nom
  const item = computeStore.discoveredItems.find(d => d.id === discoveredId)
  if (!item) return

  adoptionWizardItemType.value = item.type
  adoptionWizardItemId.value = discoveredId
  adoptionWizardItemName.value = item.name
  adoptionWizardVisible.value = true
}

function onAdopted(_response: AdoptionResponse): void {
  // Rafraîchir les données après adoption
  refreshGlobal()
}

// ─── Actions ─────────────────────────────────────────────────────────────────

function copyToClipboard(text: string): void {
  window.navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('ID copié dans le presse-papiers')
  })
}

function refreshGlobal(): void {
  const orgId = authStore.organizationId ?? undefined
  if (groupByTarget.value) {
    computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: orgId })
  } else {
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  }
}

/** Handle card action events from AppCard */
function handleCardAction(actionType: string, _appId: string): void {
  // Actions are already handled inside AppCard component
  // This handler is for any parent-level action routing if needed
  void actionType
}

// ─── Watchers ─────────────────────────────────────────────────────────────────

watch(filterParams, () => {
  const orgId = authStore.organizationId ?? undefined
  if (!groupByTarget.value) {
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  } else {
    computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: orgId })
  }
})

watch(groupByTarget, (val) => {
  const orgId = authStore.organizationId ?? undefined
  if (val) {
    computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: orgId })
  } else {
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  }
})

// ─── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(() => {
  const orgId = authStore.organizationId ?? undefined
  computeStore.fetchStats(orgId)
  computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  hostsStore.fetchHosts(orgId)
})
</script>

<style scoped>
.compute-view {
  max-width: 1400px;
  margin: 0 auto;
}

.filter-bar :deep(.el-radio-button__inner) {
  padding: 5px 12px;
  font-size: 13px;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  font-size: 12px;
  border: 1px solid transparent;
  border-radius: 999px;
  transition: all 0.2s;
  cursor: pointer;
  user-select: none;
}
</style>
