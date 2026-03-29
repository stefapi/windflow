<template>
  <div class="compute-view p-6">
    <!-- A. Header -->
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100">
          Containers — vue globale
        </h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ computeStore.stats?.targets_count ?? 0 }} targets
          · {{ techCount }} technologies
        </p>
      </div>
      <div class="flex items-center gap-2">
        <el-button
          :type="!groupByTarget ? 'primary' : 'default'"
          size="small"
          @click="groupByTarget = false"
        >
          Tout
        </el-button>
        <el-button
          :type="groupByTarget ? 'primary' : 'default'"
          size="small"
          @click="groupByTarget = true"
        >
          Par machine
        </el-button>
        <el-button
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
            ● Stacks WindFlow
          </el-radio-button>
          <el-radio-button value="discovered">
            ● Discovered
          </el-radio-button>
          <el-radio-button value="standalone">
            ● Standalone
          </el-radio-button>
        </el-radio-group>

        <span class="text-gray-300">|</span>

        <el-input
          v-model="filterSearch"
          size="small"
          placeholder="Rechercher..."
          clearable
          style="width: 200px"
        />
      </div>

      <!-- Ligne 2 : Pills technologie + pills target -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-gray-500 font-semibold">Tech :</span>
        <span
          v-for="tech in availableTechnologies"
          :key="tech"
          class="pill"
          :class="activeTechnologies.includes(tech) ? 'pill-selected' : 'pill-default'"
          @click="toggleTechnology(tech)"
        >
          {{ tech }}
        </span>

        <span class="text-xs text-gray-500 font-semibold ml-2">Target :</span>
        <span
          v-for="target in targetsStore.targets"
          :key="target.id"
          class="pill"
          :class="activeTargets.includes(target.id) ? 'pill-selected' : 'pill-default'"
          @click="toggleTarget(target.id)"
        >
          {{ target.name }}
        </span>
      </div>
    </div>

    <!-- C. Bandeau métriques -->
    <div class="mb-6">
      <ComputeStatsBanner
        :stats="computeStore.stats"
        :loading="computeStore.statsLoading"
      />
    </div>

    <!-- Mode normal (D + E + F) -->
    <template v-if="!groupByTarget">
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
      v-if="groupByTarget"
      :groups="filteredTargetGroups"
      :loading="computeStore.loading"
    />

    <!-- Adoption Wizard -->
    <AdoptionWizard
      v-model="adoptionWizardVisible"
      :item-type="adoptionWizardItemType"
      :item-id="adoptionWizardItemId"
      :item-name="adoptionWizardItemName"
      @adopted="onAdopted"
    />

    <!-- H. Légende -->
    <div class="flex flex-wrap gap-6 mt-8 text-sm text-gray-500 border-t pt-4">
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
 */

import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useComputeStore, useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import ComputeStatsBanner from '@/components/ComputeStatsBanner.vue'
import {
  ManagedStacksSection,
  DiscoveredSection,
  StandaloneSection,
  TargetGroupView,
  AdoptionWizard,
} from '@/components/compute'
import type { ControlLevel, AdoptionResponse } from '@/types/api'

const computeStore = useComputeStore()
const targetsStore = useTargetsStore()
const authStore = useAuthStore()

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
  computeStore.managedStacks.filter(stack => stack.services_total > 0),
)

const visibleDiscoveredItems = computed(() =>
  computeStore.discoveredItems.filter(item => item.services_total > 0),
)

const filteredTargetGroups = computed(() =>
  computeStore.targetGroups.map(group => ({
    ...group,
    stacks: group.stacks.filter(stack => stack.services_total > 0),
    discovered: group.discovered.filter(item => item.services_total > 0),
  })),
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
  targetsStore.fetchTargets(orgId)
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

.pill-default {
  color: var(--color-text-secondary, #6b7280);
  background-color: var(--color-bg-secondary, #f3f4f6);
  border-color: var(--color-border, #e5e7eb);
}

.pill-default:hover {
  background-color: var(--color-bg-elevated, #e9ecef);
}

.pill-selected {
  color: var(--el-color-primary, #409eff);
  background-color: var(--el-color-primary-light-8, #ecf5ff);
  border-color: var(--el-color-primary, #409eff);
}
</style>
